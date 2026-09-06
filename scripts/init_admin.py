"""Crea el PRIMER usuario admin en una `catalog.db` virgen (bootstrap).

    # local (PowerShell)
    $env:MONITOR_ADMIN_PASSWORD='...'; py -3.12 scripts/init_admin.py
    # servidor (read -rs: la clave no queda en bash_history)
    read -rs MONITOR_ADMIN_PASSWORD && export MONITOR_ADMIN_PASSWORD
    venv/bin/python scripts/init_admin.py

Por qué existe: la ABM de usuarios (`/users`) exige un admin ya logueado, así que con
`db_dir` virgen (server nuevo, máquina nueva, base perdida) `/login` responde "Usuario o
contraseña incorrectos" para siempre. Este script rompe ese círculo.

Idempotente sobre el ADMIN, no sobre "algún usuario": si ya existe al menos un admin no
toca nada; si hay usuarios pero ningún admin (backup viejo, admin borrado a mano por
sqlite) promueve al usuario pedido —o lo crea— y le resetea la clave: es el único camino
de vuelta, porque la UI protege al último admin pero no puede recrearlo.

Usuario por default `admin` (override: MONITOR_ADMIN_USER).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings  # noqa: E402  (fija la TZ y resuelve db_dir)
from core.infrastructure.db.catalog_repository import init_db  # noqa: E402
from core.infrastructure.db.engine import SessionLocal, get_engine  # noqa: E402
from core.infrastructure.db.models import UserORM  # noqa: E402
from core.security import get_password_hash  # noqa: E402


def main() -> int:
    password = os.environ.get("MONITOR_ADMIN_PASSWORD", "")
    username = (os.environ.get("MONITOR_ADMIN_USER") or "admin").strip()
    if not password:
        print("MONITOR_ADMIN_PASSWORD no está seteado — nada que hacer.", file=sys.stderr)
        return 2
    get_engine()
    init_db()   # crea la tabla users si falta (forward-only, nunca dropea)
    with SessionLocal() as db:
        admins = db.query(UserORM).filter(UserORM.is_admin.is_(True)).count()
        if admins:
            print(f"Ya hay {admins} admin(s) en {settings.catalog_db}; no se toca nada.")
            return 0
        user = db.query(UserORM).filter(UserORM.username == username).first()
        if user is not None:
            user.is_admin = True
            user.allowed_tabs = ["*"]
            user.hashed_password = get_password_hash(password)
            accion = f"'{username}' promovido a admin (clave reseteada)"
        else:
            db.add(UserORM(username=username, hashed_password=get_password_hash(password),
                           is_admin=True, allowed_tabs=["*"]))
            accion = f"admin '{username}' creado"
        db.commit()
    print(f"{accion} en {settings.catalog_db}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
