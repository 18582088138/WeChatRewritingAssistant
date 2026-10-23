"""Material imports and selected reference synthesis; serialized by article task lock."""

from typing import Literal
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .. import store
from ..agents import complete
from ..reference_fusion import synthesize
from ..archive import attach_source
from ..configuration import settings
from ..dependencies import auth, get_article
from ..manual_materials import sync, upload
from ..research import extract, download_assets
from ..tasks import launch

router = APIRouter(dependencies=[Depends(auth)])


class Reference(BaseModel):
    url: str = Field(max_length=2000)


class Selection(BaseModel):
    source_id: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(ge=1)


class Fusion(BaseModel):
    selections: list[Selection] = Field(min_length=1, max_length=12)
    position: int = Field(ge=0)
    revision: int
    instruction: str = Field(
        default="自然衔接，保留关键技术细节与来源", max_length=1000
    )
    provider: Literal["deepseek", "openrouter"] = Field(default_factory=lambda: settings("generation")["provider"])


@router.post("/api/articles/{article_id}/materials")
async def add_material(article_id: str, file: UploadFile = File(...)):
    get_article(article_id)
    raw = await file.read(25_000_001)
    if len(raw) > 25_000_000:
        raise HTTPException(413, "素材上限 25 MB")
    result = []
    try:
        launch(
            article_id,
            lambda: result.append(upload(article_id, file.filename or "素材.txt", raw)),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return result[0]


@router.post("/api/articles/{article_id}/materials/sync")
def synchronize(article_id: str):
    result = []
    launch(article_id, lambda: result.append(sync(get_article(article_id))))
    return result[0]


@router.post("/api/articles/{article_id}/references")
def add_reference(article_id: str, payload: Reference):
    result = []

    def operation():
        article = get_article(article_id)
        index = len(article["sources"]) + 1
        relative = f"materials/source-{index}/text"
        source = extract(payload.url, store.folder(article_id) / relative)
        if any(s["url"] == source["url"] for s in article["sources"]):
            result.append(article)
            return
        attach_source(article_id, source, index, relative)
        source["reference_role"] = dict(kind="manual", reason="用户补充链接")
        article["sources"].append(source)
        article["assets"] += download_assets(source, article_id, index)
        article["review"] = None
        result.append(store.save(article))

    try:
        launch(article_id, operation)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return result[0]


@router.post("/api/articles/{article_id}/fuse")
def fuse(article_id: str, payload: Fusion):
    result = []

    def operation():
        article = get_article(article_id)
        if payload.revision != article["revision"]:
            raise HTTPException(409, "文案已更新，请重新选择插入位置")
        if payload.position > len(article["body"]):
            raise HTTPException(422, "插入位置无效")
        selections = []
        for selection in payload.selections:
            if selection.source_id > len(article["sources"]):
                raise HTTPException(422, "来源编号无效")
            source = article["sources"][selection.source_id - 1]
            if not 0 <= selection.start < selection.end <= len(source["text"]):
                raise HTTPException(422, "参考选区无效")
            selections.append(
                dict(
                    source_id="S" + str(selection.source_id),
                    title=source["title"],
                    text=source["text"][selection.start : selection.end],
                    url=source["url"],
                )
            )
        try:
            text = synthesize(
                selections, payload.instruction, article["body"], payload.provider,
                completion=complete,
            )
        except (ValueError, httpx.HTTPError, KeyError) as exc:
            message = str(exc) if isinstance(exc, ValueError) and str(exc).startswith("融合段落缺少") else "融合模型调用失败，原稿未修改；请检查网络、模型配置或重试"
            raise HTTPException(502, message) from exc
        article["body"] = (
            article["body"][: payload.position]
            + "\n\n"
            + text.strip()
            + "\n\n"
            + article["body"][payload.position :]
        )
        article["revision"] += 1
        article["review"] = None
        article["stage"] = "参考融合插入，待复审"
        result.append(store.save(article, snapshot=True))

    launch(article_id, operation)
    return result[0]


@router.get("/api/config")
def configuration():
    return {name: settings(name) for name in ["generation", "research", "platforms"]}
