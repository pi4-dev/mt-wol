import os
import re
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS hosts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    mac TEXT NOT NULL UNIQUE,
    ip TEXT NOT NULL DEFAULT '',
    lan TEXT NOT NULL DEFAULT '',        -- MikroTik interface (e.g. bridge-lan, vlan10) used for WoL
    comment TEXT NOT NULL DEFAULT '',
    last_wol TEXT
);
"""


def normalize_mac(mac: str) -> str:
    hexes = re.sub(r"[^0-9A-Fa-f]", "", mac or "").upper()
    if len(hexes) != 12:
        raise ValueError(f"Invalid MAC address: {mac!r}")
    return ":".join(hexes[i : i + 2] for i in range(0, 12, 2))


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    with connect() as c:
        c.executescript(SCHEMA)
