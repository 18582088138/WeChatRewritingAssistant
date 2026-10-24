"""Assets API routes."""

import io
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image

from .. import store
from ..dependencies import auth, get_article
from ..materials import stock_images
from ..card_layout import cards
from ..schemas import Approval, StockQuery
from ..tasks import launch

router = APIRouter(dependencies=[Depends(auth)])


@router.post("/api/articles/{article_id}/assets")
async def upload(article_id: str, file: UploadFile = File(...)):
    raw = await file.read(12_000_001)
    if len(raw) > 12_000_000:
        raise HTTPException(413, "图片不能超过 12 MB")
    try:
        image = Image.open(io.BytesIO(raw))
        if image.width * image.height > 30_000_000:
            raise ValueError("图片像素过大")
        image.load()
    except Exception:
        raise HTTPException(422, "请上传有效的 PNG、JPEG 或 WebP 图片")
    result = []

    def operation():
        article = get_article(article_id)
        asset_id = uuid.uuid4().hex
        path = (
            store.folder(article_id)
            / "materials"
            / "local"
            / "images"
            / (asset_id + ".jpg")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        image.convert("RGB").save(path, quality=92)
        article["assets"].append(
            dict(
                id=asset_id,
                type="image",
                path=str(path.relative_to(store.folder(article_id))).replace("\\", "/"),
                alt=Path(file.filename or "本地图片").stem[:240],
                approved=False,
                watermark="unchecked",
                rights="本地上传，需确认授权与水印",
                source_url="",
                attribution="",
                width=image.width,
                height=image.height,
            )
        )
        result.append(store.save(article, snapshot=bool(article.get("body"))))

    launch(article_id, operation)
    return result[0]


@router.patch("/api/articles/{article_id}/assets/{asset_id}")
def approve(article_id: str, asset_id: str, payload: Approval):
    result = []

    def operation():
        article = get_article(article_id)
        asset = next((a for a in article["assets"] if a["id"] == asset_id), None)
        if not asset:
            raise HTTPException(404, "素材不存在")
        asset.update(
            approved=payload.approved,
            alt=payload.alt,
            watermark="manually_checked" if payload.approved else "unchecked",
        )
        for derived in article["assets"]:
            if derived.get("derived_from") == asset_id:
                derived.update(approved=payload.approved, watermark="manually_checked" if payload.approved else "unchecked")
        result.append(store.save(article, snapshot=bool(article.get("body"))))

    launch(article_id, operation)
    return result[0]


@router.get("/api/articles/{article_id}/assets/{asset_id}/file")
def asset_file(article_id: str, asset_id: str):
    article = get_article(article_id)
    asset = next((a for a in article["assets"] if a["id"] == asset_id), None)
    if not asset:
        raise HTTPException(404, "素材不存在")
    root = store.folder(article_id).resolve()
    path = (root / asset["path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "素材文件不存在")
    return FileResponse(path)


@router.post("/api/articles/{article_id}/cards")
def make_cards(article_id: str):
    result = []

    def operation():
        article = get_article(article_id)
        if not article["body"]:
            raise HTTPException(422, "请先生成正文")
        created = cards(article)
        created_ids = {a["id"] for a in created}
        referenced = set(re.findall(r"/assets/(card-[^/]+)/file", article["body"]))
        article["assets"] = [
            a
            for a in article["assets"]
            if not a["id"].startswith("card-") or a["id"] in referenced - created_ids
        ] + created
        result.append(store.save(article))

    launch(article_id, operation)
    return result[0]


@router.post("/api/articles/{article_id}/stock")
def stock(article_id: str, payload: StockQuery):
    result = []

    def operation():
        article = get_article(article_id)
        try:
            assets = stock_images(article_id, payload.query)
        except Exception as exc:
            raise HTTPException(
                502,
                str(exc)[:300]
                if isinstance(exc, ValueError)
                else "图库搜索失败，请检查网络",
            )
        article["assets"] += assets
        result.append(store.save(article))

    launch(article_id, operation)
    return result[0]
