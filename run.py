"""Entry point: levanta la app FastAPI (`apps.web.app`) con uvicorn.

Es el `ExecStart` del servicio systemd en producción (deploy/monitores.service:
`venv/bin/python run.py`) y el comando de desarrollo local: `py -3.12 run.py`.
El reinicio ante caídas lo hace systemd (`Restart=always`): acá no hay wrapper.
"""

import sys

# Pinneado a Python 3.12 (ver requirements.txt). deploy.sh valida lo mismo al crear
# el venv; este guard es la segunda red para un arranque a mano con otro intérprete.
if sys.version_info[:2] != (3, 12):
    raise SystemExit(
        f"[Web] Requiere Python 3.12.x — estás usando {sys.version.split()[0]}.\n"
        "Local: `py -3.12 run.py`. Servidor: `venv/bin/python run.py`."
    )

from config.settings import settings, setup_logging  # noqa: E402

setup_logging()


def main() -> None:
    import uvicorn

    # log_config=None → uvicorn no pisa nuestro setup_logging.
    uvicorn.run("apps.web.app:app", host=settings.host, port=settings.port, log_config=None)


if __name__ == "__main__":
    print(f"  Web personal + terminal de bonos → http://localhost:{settings.port}")
    main()
