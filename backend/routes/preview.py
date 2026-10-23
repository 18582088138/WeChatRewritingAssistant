"""Preview API routes."""

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from ..dependencies import auth, get_article
from ..render import document, html

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/api/articles/{article_id}/preview", response_class=HTMLResponse)
def preview(article_id: str):
    return document(get_article(article_id))


@router.get("/api/articles/{article_id}/render")
def rendered(article_id: str):
    return {"html": html(get_article(article_id)["body"])}
