"""Generation API routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from .. import store
from ..agents import RewritingAgent, provider_config
from ..dependencies import auth, get_article
from ..schemas import Options, Paragraph
from ..tasks import background_job, launch, reserve

router = APIRouter(dependencies=[Depends(auth)])


@router.post("/api/articles/{article_id}/generate", status_code=202)
def generate(article_id: str, options: Options, background: BackgroundTasks):
    article = get_article(article_id)
    if not provider_config(options.provider)[0]:
        raise HTTPException(422, "所选模型未配置 API key")
    reserve(article_id)
    article.update(status="Process", stage="排队生成", error=None, options=options.model_dump())
    store.save(article)
    background.add_task(background_job, article_id, options.model_dump())
    return article


@router.post("/api/articles/{article_id}/review", status_code=202)
def review(article_id: str, options: Options, background: BackgroundTasks):
    article = get_article(article_id)
    if not article["body"]:
        raise HTTPException(422, "请先生成或保存正文")
    if not provider_config(options.provider)[0]:
        raise HTTPException(422, "所选模型未配置 API key")
    reserve(article_id)
    article.update(status="Process", stage="独立审稿", error=None)
    store.save(article)
    background.add_task(background_job, article_id, options.model_dump(), review_only=True)
    return article


@router.post("/api/articles/{article_id}/paragraph")
def paragraph(article_id: str, payload: Paragraph):
    result = []

    def operation():
        article = get_article(article_id)
        if article["revision"] != payload.revision:
            raise HTTPException(409, "文章已更新，请刷新后再选择段落")
        if not 0 <= payload.start < payload.end <= len(article["body"]):
            raise HTTPException(422, "请选择有效的正文段落")
        selected = article["body"][payload.start : payload.end]
        try:
            text = RewritingAgent().paragraph(
                article, selected, payload.instruction, payload.provider
            )
        except Exception as exc:
            raise HTTPException(
                502,
                str(exc)[:300] if isinstance(exc, ValueError) else "段落生成失败，请检查模型与网络",
            )
        article["body"] = article["body"][: payload.start] + text + article["body"][payload.end :]
        article["revision"] += 1
        article["review"] = None
        article["stage"] = "局部重写，待审稿"
        result.append(store.save(article, snapshot=True))

    launch(article_id, operation)
    return result[0]
