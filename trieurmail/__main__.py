"""Lancement : ``python -m trieurmail`` puis ouvrir http://127.0.0.1:8765"""
from __future__ import annotations

import argparse
import threading
import webbrowser


def main() -> None:
    parser = argparse.ArgumentParser(prog="trieurmail", description="Assistant mail local propulsé par une IA.")
    parser.add_argument("--host", default="127.0.0.1", help="interface d'écoute (défaut : 127.0.0.1, local uniquement)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    args = parser.parse_args()

    import uvicorn

    from .web.app import create_app

    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"Trieurmail démarré sur {url}")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
