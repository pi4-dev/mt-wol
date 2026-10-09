# MT WoL

Inventory of hosts in the LANs visible from a MikroTik router, with remote Wake-on-LAN
through the RouterOS API (`/tool/wol`).

**The app has no authentication of its own** and `docker-compose.yaml` publishes its port directly.
Anyone who can reach the port can wake hosts and read the inventory, so run it only on a trusted
network or put your own reverse proxy / auth in front of it.

## Setup
1. `cp mt-wol.env.example mt-wol.env` and fill in the router address and credentials.
2. Create a least-privilege API user on the MikroTik (see below).
3. Run `docker compose up -d --build` and open `http://<docker-host>:8000` (change the port in `docker-compose.override.yaml`).

## Local overrides
Keep machine-specific settings (e.g. a different port) in `docker-compose.override.yaml` next to
`docker-compose.yaml`; Docker Compose merges it automatically and git ignores it (`compose.override.yaml` too).

```yaml
services:
  mt-wol:
    ports:
      - "8080:8000"
```

## Least-privilege MikroTik user
The app needs only three RouterOS policies:

| Policy | Why |
|--------|-----|
| `api`  | log in over the API |
| `read` | list DHCP servers and leases (`/ip/dhcp-server`, `/ip/dhcp-server/lease`) |
| `test` | run `/tool/wol` |

Do **not** grant `write`, `policy`, `sensitive`, `ftp`, `ssh`, `telnet`, `winbox`, `web`, `password`, `reboot`, etc.
Run in the RouterOS terminal (replace the password and the address with your Docker host's IP or subnet):

```routeros
/user group add name=wol-api policy=api,read,test comment="mt-wol: minimal"
/user add name=wol group=wol-api password="<long-random-password>" address=192.168.88.10/32 comment="mt-wol"
```

`address=` makes RouterOS accept this user only from the Docker host. Optionally also restrict the API service itself
(use `api-ssl` + `MT_SSL=true` if the traffic crosses an untrusted segment):

```routeros
/ip service set api address=192.168.88.10/32
/ip service disable telnet,ftp,www
```

Verify: `/user group print where name=wol-api` should list only `api,read,test`.
If the import or Wake fails with "not enough permissions", check that policy list first.

## How it works
- **LAN** of a host = the interface of its DHCP server on the router (e.g. `bridge-lan`, `vlan20`).
  It is passed as `interface=` to `/tool/wol`.
- **Import from DHCP** lists static leases (optionally dynamic ones too) and skips MACs already in the inventory.
- **Wake** runs `/tool/wol` on the router for the host's interface and MAC.
- Data is stored in SQLite at `./data/hosts.db`.

## Environment variables
`MT_HOST`, `MT_PORT`, `MT_USER`, `MT_PASSWORD`, `MT_SSL` (api-ssl), `MT_SSL_ADH` (api-ssl without a router certificate),
`MT_TIMEOUT`, `DB_PATH`.

## Tests
`pip install -r requirements-dev.txt && pytest`
