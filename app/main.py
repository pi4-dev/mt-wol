from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db
from .mikrotik import MikroTik, MikroTikError, get_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    yield


app = FastAPI(title="MT WoL", lifespan=lifespan)
STATIC = Path(__file__).parent / "static"


class HostIn(BaseModel):
    name: str
    mac: str
    ip: str = ""
    lan: str = ""
    comment: str = ""


class ImportIn(BaseModel):
    hosts: list[HostIn]


def _norm(h: HostIn) -> dict:
    try:
        mac = db.normalize_mac(h.mac)
    except ValueError as e:
        raise HTTPException(422, str(e))
    name = h.name.strip() or mac
    return dict(name=name, mac=mac, ip=h.ip.strip(), lan=h.lan.strip(), comment=h.comment.strip())


# ---------- host inventory ----------

@app.get("/api/hosts")
def list_hosts():
    with db.connect() as c:
        rows = c.execute("SELECT * FROM hosts ORDER BY lan, name COLLATE NOCASE")
        return [dict(r) for r in rows]


@app.post("/api/hosts", status_code=201)
def create_host(h: HostIn):
    d = _norm(h)
    with db.connect() as c:
        try:
            cur = c.execute(
                "INSERT INTO hosts(name,mac,ip,lan,comment) VALUES(:name,:mac,:ip,:lan,:comment)", d
            )
        except Exception:
            raise HTTPException(409, "A host with this MAC already exists")
        return dict(d, id=cur.lastrowid, last_wol=None)


@app.put("/api/hosts/{host_id}")
def update_host(host_id: int, h: HostIn):
    d = _norm(h)
    with db.connect() as c:
        try:
            cur = c.execute(
                "UPDATE hosts SET name=:name,mac=:mac,ip=:ip,lan=:lan,comment=:comment WHERE id=:id",
                dict(d, id=host_id),
            )
        except Exception:
            raise HTTPException(409, "A host with this MAC already exists")
        if not cur.rowcount:
            raise HTTPException(404, "Host not found")
        return dict(d, id=host_id)


@app.delete("/api/hosts/{host_id}", status_code=204)
def delete_host(host_id: int):
    with db.connect() as c:
        c.execute("DELETE FROM hosts WHERE id=?", (host_id,))


# ---------- MikroTik ----------

def _mt_call(fn):
    try:
        return fn()
    except MikroTikError as e:
        raise HTTPException(502, str(e))


@app.get("/api/lans")
def lans(mt: MikroTik = Depends(get_client)):
    """LANs visible from the router = DHCP servers (name -> interface)."""
    return _mt_call(mt.dhcp_servers)


@app.get("/api/import/candidates")
def import_candidates(include_dynamic: bool = False, mt: MikroTik = Depends(get_client)):
    """DHCP leases from the router, flagged if already present in the inventory."""
    servers = {s["name"]: s["interface"] for s in _mt_call(mt.dhcp_servers)}
    leases = _mt_call(mt.leases)
    with db.connect() as c:
        known = {r["mac"] for r in c.execute("SELECT mac FROM hosts")}
    out = []
    for lease in leases:
        mac = lease.get("mac-address") or lease.get("active-mac-address")
        if not mac:
            continue
        dynamic = bool(lease.get("dynamic", False))
        if dynamic and not include_dynamic:
            continue
        mac = db.normalize_mac(mac)
        server = lease.get("server", "")
        out.append(
            {
                "name": lease.get("comment") or lease.get("host-name") or lease.get("active-host-name") or "",
                "mac": mac,
                "ip": lease.get("address") or lease.get("active-address") or "",
                "lan": servers.get(server, server),
                "comment": "",
                "dynamic": dynamic,
                "exists": mac in known,
            }
        )
    out.sort(key=lambda x: (x["lan"], x["ip"]))
    return out


@app.post("/api/import")
def import_hosts(body: ImportIn):
    added = skipped = 0
    with db.connect() as c:
        for h in body.hosts:
            cur = c.execute(
                "INSERT OR IGNORE INTO hosts(name,mac,ip,lan,comment) VALUES(:name,:mac,:ip,:lan,:comment)",
                _norm(h),
            )
            added += cur.rowcount
            skipped += 1 - cur.rowcount
    return {"added": added, "skipped": skipped}


@app.post("/api/hosts/{host_id}/wake")
def wake(host_id: int, mt: MikroTik = Depends(get_client)):
    with db.connect() as c:
        row = c.execute("SELECT * FROM hosts WHERE id=?", (host_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Host not found")
        if not row["lan"]:
            raise HTTPException(422, "Host has no LAN (MikroTik interface) assigned")
        _mt_call(lambda: mt.wol(row["lan"], row["mac"]))
        c.execute(
            "UPDATE hosts SET last_wol=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), host_id),
        )
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
