"""Delivery API routes."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from .. import store
from ..dependencies import auth, get_article
from ..publishing import wechat_draft
from ..render import export_zip
from ..schemas import Publish
from ..settings_store import read_settings
from ..tasks import launch

router = APIRouter(dependencies=[Depends(auth)])


@router.post("/api/articles/{article_id}/deliver")
def deliver(article_id: str, payload: Publish):
    results = []

    def operation():
        article = get_article(article_id)
        if not article["body"]:
            raise HTTPException(422, "文章正文为空")
        for platform in dict.fromkeys(payload.platforms):
            try:
                if platform == "wechat":
                    result = wechat_draft(article, read_settings())
                else:
                    exports = store.folder(article_id) / "exports"
                    exports.mkdir(exist_ok=True)
                    (exports / f"{platform}-r{article['revision']}.zip").write_bytes(
                        export_zip(article, platform)
                    )
                    result = dict(
                        platform=platform,
                        status="export_ready",
                        at=store.now(),
                        message="素材包已就绪，请下载后在平台手动保存草稿",
                    )
            except Exception as exc:
                result = dict(
                    platform=platform,
                    status="failed",
                    at=store.now(),
                    message=str(exc)[:300]
                    if isinstance(exc, ValueError)
                    else "平台接口请求失败，请检查网络和配置",
                )
            results.append(result)
        article["deliveries"] += results
        store.save(article, snapshot=True)

    launch(article_id, operation)
    return results


@router.get("/api/articles/{article_id}/export/{platform}")
def export(article_id: str, platform: Literal["wechat", "x", "xiaohongshu", "weibo"]):
    return Response(
        export_zip(get_article(article_id), platform),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{platform}-draft.zip"'},
    )
