"""Preview API routes."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import re

from ..dependencies import auth, get_article
from ..render import document, html
from ..pagination import paginate
from .. import store
from ..revisions import history
from ..draft_highlights import highlighted
from ..video_posters import attach_posters

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/api/articles/{article_id}/preview", response_class=HTMLResponse)
def preview(article_id: str):
    return document(get_article(article_id))


@router.get("/api/articles/{article_id}/render")
def rendered(article_id: str):
    article = get_article(article_id)
    content = html(article["body"])
    return {"html": attach_posters(highlighted(article), article), "pages": paginate(attach_posters(content, article))}


@router.get("/api/articles/{article_id}/versions/{version_id}/preview", response_class=HTMLResponse)
def historical_preview(article_id: str, version_id: str):
    article = get_article(article_id)
    version = next((v for v in history(article, store.folder(article_id)) if v["version_id"] == version_id), None)
    if not version:
        raise HTTPException(404, "修订版本不存在")
    return document(version).replace(f"/api/articles/{article_id}/assets/", f"/api/articles/{article_id}/versions/{version_id}/assets/")


@router.get("/api/articles/{article_id}/versions/{version_id}/assets/{asset_id}/file")
def historical_asset(article_id: str, version_id: str, asset_id: str):
    article = get_article(article_id)
    version = next((v for v in history(article, store.folder(article_id)) if v["version_id"] == version_id), None)
    asset = next((a for a in (version or {}).get("assets", []) if a["id"] == asset_id), None)
    if not asset:
        raise HTTPException(404, "历史素材不存在")
    root = store.folder(article_id).resolve()
    path = (root / asset["path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "历史素材文件不存在")
    return FileResponse(path)
