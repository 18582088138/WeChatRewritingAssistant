"""HTTP authentication and article lookup shared by route groups."""

import os

from fastapi import HTTPException, Request

from . import store


def auth(request: Request):
    import secrets

    token = os.getenv("APP_TOKEN", "")
    if token and not secrets.compare_digest(
        request.headers.get("Authorization", ""), "Bearer " + token
    ):
        raise HTTPException(401, "请在设置中填写后端访问令牌")


def get_article(article_id):
    try:
        return store.read(article_id)
    except (OSError, ValueError):
        raise HTTPException(404, "文章不存在")
