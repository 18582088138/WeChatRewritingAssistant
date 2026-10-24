"""Shared library API; explicit selection adds evidence to an article."""

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import public_materials as library
from .. import store
from ..dependencies import auth, get_article
from ..tasks import launch

router = APIRouter(dependencies=[Depends(auth)])


class Link(BaseModel):
    url: str = Field(max_length=2000)


class Item(BaseModel):
    source_index: int | None = Field(default=None, ge=0)
    asset_id: str | None = Field(default=None, max_length=120)


@router.get("/api/materials/public")
def listing():
    return library.read()


@router.post("/api/materials/public")
async def upload(file: UploadFile = File(...)):
    raw = await file.read(25_000_001)
    if len(raw) > 25_000_000:
        raise HTTPException(413, "素材上限 25 MB")
    try:
        return library.add_file(file.filename or "素材.txt", raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/api/materials/public/references")
def add_url(payload: Link):
    try:
        return library.add_url(payload.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/api/materials/public/assets/{asset_id}/file")
def file(asset_id: str):
    asset = next((a for a in library.read()["assets"] if a["id"] == asset_id), None)
    if not asset:
        raise HTTPException(404, "素材不存在")
    path = (library.root() / asset["path"]).resolve()
    if not path.is_relative_to(library.root().resolve()) or not path.is_file():
        raise HTTPException(404, "素材文件不存在")
    return FileResponse(path)


@router.post("/api/articles/{article_id}/materials/public")
def attach(article_id: str, payload: Item):
    if payload.source_index is None and not payload.asset_id:
        raise HTTPException(422, "请选择公共素材")
    result = []
    try:
        launch(article_id, lambda: result.append(library.attach(get_article(article_id), payload.source_index, payload.asset_id)))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return result[0]
