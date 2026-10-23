"""Persistent non-secret publishing settings."""

import json

from . import store


def read_settings():
    file = store.DATA / "settings.json"
    return (
        json.loads(file.read_text(encoding="utf-8"))
        if file.exists()
        else {"wechat": {"author": "", "thumb_media_id": ""}}
    )
