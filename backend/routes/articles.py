"""Articles API routes."""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from .. import store
from ..dependencies import auth, get_article
from ..network import validate_url
from ..schemas import Edit, ImportArticle
from ..tasks import background_job, launch, reserve

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/api/articles")
def articles():
    return store.listing()


@router.post("/api/articles", status_code=201)
def import_article(payload: ImportArticle, background: BackgroundTasks):
    try:
        validate_url(payload.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if payload.text and len(payload.text.strip()) < 150:
        raise HTTPException(422, "粘贴的原文至少需要 150 字")
    article = store.create(payload.url, payload.title or "待抓取的行业要闻")
    if payload.text:
        path = store.folder(article["id"]) / "materials" / "source-1" / "text"
        path.mkdir(parents=True)
        (path / "text.txt").write_text(payload.text, encoding="utf-8")
        article["sources"] = [
            dict(
                title=payload.title or "手动导入来源",
                url=payload.url,
                text=payload.text,
                retrieved_at=store.now(),
                images=[],
                videos=[],
            )
        ]
        article["stage"] = "来源已就绪"
        store.save(article)
    else:
        reserve(article["id"])
        article.update(status="Process", stage="抓取来源")
        store.save(article)
        background.add_task(background_job, article["id"], fetch_only=True)
    return article


@router.get("/api/articles/{article_id}")
def detail(article_id: str):
    return get_article(article_id)


@router.patch("/api/articles/{article_id}")
def edit(article_id: str, payload: Edit):
    result = []

    def operation():
        article = get_article(article_id)
        if payload.revision != article["revision"]:
            raise HTTPException(409, "文章已更新，请刷新后再编辑")
        article.update(payload.model_dump(exclude={"revision"}))
        article["revision"] += 1
        article["review"] = None
        article["stage"] = "人工编辑，待审稿"
        result.append(store.save(article, snapshot=True))

    launch(article_id, operation)
    return result[0]


@router.get("/api/articles/{article_id}/versions")
def versions(article_id: str):
    get_article(article_id)
    return [
        dict(**json.loads(p.read_text(encoding="utf-8")), version_id=p.stem)
        for p in sorted((store.folder(article_id) / "versions").glob("*.json"), reverse=True)
    ][:30]
