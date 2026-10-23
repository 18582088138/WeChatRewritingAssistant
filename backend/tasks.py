"""Single-process article task coordination and restart recovery."""

import threading

from fastapi import HTTPException

from . import store
from .workflow import ingest, run

BUSY = set()
BUSY_LOCK = threading.Lock()


def launch(article_id, fn, *args):
    with BUSY_LOCK:
        if article_id in BUSY:
            raise HTTPException(409, "文章正在处理，请等待当前任务完成")
        BUSY.add(article_id)
    try:
        fn(*args)
    finally:
        with BUSY_LOCK:
            BUSY.discard(article_id)


def reserve(article_id):
    with BUSY_LOCK:
        if article_id in BUSY:
            raise HTTPException(409, "文章正在处理")
        BUSY.add(article_id)


def background_job(article_id, options=None, fetch_only=False, review_only=False):
    try:
        if fetch_only:
            try:
                ingest(article_id)
                article = store.read(article_id)
                article.update(status="New", stage="来源已就绪", error=None)
                store.save(article)
            except Exception as exc:
                article = store.read(article_id)
                article.update(
                    status="New",
                    stage="抓取失败",
                    error=str(exc)[:300]
                    if isinstance(exc, ValueError)
                    else "抓取失败，请检查网络或粘贴原文",
                )
                store.save(article)
        else:
            run(article_id, options, review_only)
    finally:
        with BUSY_LOCK:
            BUSY.discard(article_id)


def recover():
    for article in store.listing():
        if article["status"] == "Process":
            article.update(
                status="Done" if article["body"] else "New",
                stage="任务中断，可重试",
                error="后端已重启，请重新运行任务",
            )
            store.save(article)
