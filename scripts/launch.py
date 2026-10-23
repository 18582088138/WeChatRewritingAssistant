"""One command starts the complete local app and opens its GUI."""

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from backend.configuration import settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    cfg = settings("app")
    os.environ["SERVE_FRONTEND"] = "true"
    url = f"http://127.0.0.1:{cfg['port']}"
    import httpx

    try:
        health = httpx.get(url + "/api/health", timeout=2, trust_env=False)
        if health.is_success:
            if not args.no_browser and cfg["open_browser"]:
                webbrowser.open(url)
            print("App already running:", url)
            return
    except httpx.HTTPError:
        pass
    from migrate_data import migrate

    print("Local GUI and API:", url, "/ migrated tasks:", migrate())
    if not args.no_browser and cfg["open_browser"]:

        def open_when_ready():
            for _ in range(80):
                try:
                    if httpx.get(
                        url + "/api/health", timeout=1, trust_env=False
                    ).is_success:
                        webbrowser.open(url)
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)

        threading.Thread(target=open_when_ready, daemon=True).start()
    import uvicorn

    uvicorn.run(
        "backend.app:app", host=cfg["host"], port=cfg["port"], app_dir=str(ROOT)
    )


if __name__ == "__main__":
    main()
