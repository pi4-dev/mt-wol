import os


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


MT_HOST = os.getenv("MT_HOST", "192.168.88.1")
MT_USER = os.getenv("MT_USER", "admin")
MT_PASSWORD = os.getenv("MT_PASSWORD", "")
MT_SSL = _bool("MT_SSL")
MT_SSL_ADH = _bool("MT_SSL_ADH")
MT_PORT = int(os.getenv("MT_PORT", "8729" if MT_SSL else "8728"))
MT_TIMEOUT = float(os.getenv("MT_TIMEOUT", "8"))
DB_PATH = os.getenv("DB_PATH", "/data/hosts.db")
