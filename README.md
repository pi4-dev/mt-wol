# MT WoL

Inventory of hosts in the LANs visible from a MikroTik router, with remote Wake-on-LAN
through the RouterOS API (`/tool/wol`).

**The app has no authentication of its own** and `docker-compose.yaml` publishes its port directly.
Anyone who can reach the port can wake hosts and read the inventory, so run it only on a trusted
network or put your own reverse proxy / auth in front of it.

## Setup
1. `cp .env.example .env` and fill in the router address and credentials.
2. On the MikroTik, enable the API service (`/ip service`: api on 8728 or api-ssl on 8729) and create
   a user with `api,read,test` policies (`/tool wol` needs `test`, reading DHCP needs `read`):
   `/user group add name=wol policy=api,read,test` and `/user add name=wol group=wol password=...`
3. Run `docker compose up -d --build` and open `http://<docker-host>:8000` (port set by `APP_PORT`).

## How it works
- **LAN** of a host = the interface of its DHCP server on the router (e.g. `bridge-lan`, `vlan20`).
  It is passed as `interface=` to `/tool/wol`.
- **Import from DHCP** lists static leases (optionally dynamic ones too) and skips MACs already in the inventory.
- **Wake** runs `/tool/wol` on the router for the host's interface and MAC.
- Data is stored in SQLite at `./data/hosts.db`.

## Environment variables
`MT_HOST`, `MT_PORT`, `MT_USER`, `MT_PASSWORD`, `MT_SSL` (api-ssl), `MT_SSL_ADH` (api-ssl without a router certificate),
`MT_TIMEOUT`, `DB_PATH`; `APP_PORT` (compose only: published host port).

## Tests
`pip install -r requirements-dev.txt && pytest`
