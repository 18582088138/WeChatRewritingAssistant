"""Settings API routes."""

import os

from fastapi import APIRouter, Depends

from .. import store
from ..agents import provider_config
from ..dependencies import auth
from ..publishing import PLATFORMS
from ..schemas import Settings
from ..settings_store import read_settings

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/api/settings")
def settings():
    return dict(
        **read_settings(),
        platforms=PLATFORMS,
        providers=[
            dict(id=p, configured=bool(provider_config(p)[0]), model=provider_config(p)[2])
            for p in ["deepseek", "openrouter"]
        ],
        wechat_configured=bool(os.getenv("WECHAT_APP_ID") and os.getenv("WECHAT_APP_SECRET")),
    )


@router.post("/api/settings")
def save_settings(payload: Settings):
    store.DATA.mkdir(parents=True, exist_ok=True)
    with store.LOCK:
        temp = store.DATA / "settings.tmp"
        temp.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        temp.replace(store.DATA / "settings.json")
    return settings()
