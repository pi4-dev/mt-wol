import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.mikrotik import MikroTikError


class FakeMT:
    def __init__(self):
        self.wols = []
        self.fail = False

    def dhcp_servers(self):
        return [{"name": "dhcp-lan", "interface": "bridge-lan"}, {"name": "dhcp-iot", "interface": "vlan20"}]

    def leases(self):
        return [
            {"mac-address": "aa:bb:cc:00:00:01", "address": "192.168.88.10", "server": "dhcp-lan", "comment": "nas", "dynamic": False},
            {"mac-address": "AA-BB-CC-00-00-02", "address": "10.0.20.5", "server": "dhcp-iot", "host-name": "cam", "dynamic": False},
            {"mac-address": "aa:bb:cc:00:00:03", "address": "192.168.88.99", "server": "dhcp-lan", "dynamic": True},
        ]

    def wol(self, interface, mac):
        if self.fail:
            raise MikroTikError("boom")
        self.wols.append((interface, mac))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))
    fake = FakeMT()
    main.app.dependency_overrides[main.get_client] = lambda: fake
    with TestClient(main.app) as c:
        c.fake = fake
        yield c
    main.app.dependency_overrides.clear()


def test_import_and_wake(client):
    cands = client.get("/api/import/candidates").json()
    assert len(cands) == 2
    assert {c["lan"] for c in cands} == {"bridge-lan", "vlan20"}
    assert len(client.get("/api/import/candidates?include_dynamic=true").json()) == 3

    assert client.post("/api/import", json={"hosts": cands}).json() == {"added": 2, "skipped": 0}
    assert client.post("/api/import", json={"hosts": cands}).json() == {"added": 0, "skipped": 2}
    assert all(c["exists"] for c in client.get("/api/import/candidates").json())

    nas = next(h for h in client.get("/api/hosts").json() if h["name"] == "nas")
    assert client.post(f"/api/hosts/{nas['id']}/wake").status_code == 200
    assert client.fake.wols == [("bridge-lan", "AA:BB:CC:00:00:01")]
    assert next(h for h in client.get("/api/hosts").json() if h["id"] == nas["id"])["last_wol"]


def test_crud_and_errors(client):
    r = client.post("/api/hosts", json={"name": "pc", "mac": "11-22-33-44-55-66", "lan": "br"})
    assert r.status_code == 201 and r.json()["mac"] == "11:22:33:44:55:66"
    assert client.post("/api/hosts", json={"name": "x", "mac": "112233445566"}).status_code == 409
    assert client.post("/api/hosts", json={"name": "x", "mac": "zz"}).status_code == 422
    hid = r.json()["id"]
    assert client.put(f"/api/hosts/{hid}", json={"name": "pc2", "mac": "112233445566", "lan": "br"}).status_code == 200
    client.fake.fail = True
    assert client.post(f"/api/hosts/{hid}/wake").status_code == 502
    assert client.delete(f"/api/hosts/{hid}").status_code == 204
    assert client.post(f"/api/hosts/{hid}/wake").status_code == 404
