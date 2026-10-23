from . import store
from .agents import ReviewAgent, RewritingAgent
from .research import download_assets, extract
from .research_quality import failure_reason
from .research_related import related_report
from .research_related import queries
from .research_temporal import classify
from .configuration import settings, archive_configuration
from .archive import attach_source
from .draft_media import ensure_media
from .research_search import source_identity


def ingest(article_id):
    store.event(article_id, "抓取来源", "提取文章或论文正文，保存来源与原始文件")
    article = store.read(article_id)
    if article["sources"]:
        return
    source = extract(
        article["url"], store.folder(article_id) / "materials" / "source-1" / "text"
    )
    article = store.read(article_id)
    article["sources"] = [source]
    store.save(article)
    attach_source(article_id, source, 1, "materials/source-1/text")
    assets = download_assets(source, article_id, 1)
    article = store.read(article_id)
    article["sources"] = [source]
    article["assets"] = assets
    article["title"] = source["title"]
    store.save(article)
    saved = source["quality"]
    store.event(
        article_id,
        "抓取质量",
        f"正文 {len(source['text'])} 字符；图片 {saved['saved_images']}/{len(source['images'])}；视频 {saved['saved_videos']}/{len(source['videos'])}；外部播放器 {len(source.get('embedded_media', []))}",
    )
    for warning in saved["warnings"]:
        store.event(article_id, "抓取质量", warning)


def run(article_id, options, review_only=False):
    try:
        if not review_only:
            ingest(article_id)
            article = store.read(article_id)
            if options["research"]:
                store.event(
                    article_id,
                    "关联检索",
                    "搜索关联报道与一手资料；无法获取的来源将记录提示",
                )
                urls = list(options.get("related_urls", []))
                manual_urls = {source_identity(url) for url in urls}
                report = dict(results=[], admission=[])
                try:
                    report = related_report(article["sources"][0])
                    article["research_report"] = report
                    urls += [r["url"] for r in report["results"]]
                    store.event(
                        article_id,
                        "关联检索",
                        f"检索到 {len(report['results'])} 个相关候选来源；检索详情已保存",
                    )
                    for warning in report["warnings"]:
                        store.event(article_id, "关联检索", warning)
                except Exception as exc:
                    store.event(article_id, "关联检索", failure_reason(exc))
                known = {
                    source_identity(s.get("requested_url", s["url"]))
                    for s in article["sources"]
                }
                known.update(source_identity(s["url"]) for s in article["sources"])
                for url in urls[: settings("research")["max_candidates"]]:
                    if (
                        source_identity(url) in known
                        or len(article["sources"])
                        >= settings("research")["max_sources"]
                    ):
                        continue
                    try:
                        index = len(article["sources"]) + 1
                        source = extract(
                            url,
                            store.folder(article_id)
                            / "materials"
                            / f"source-{index}"
                            / "text",
                        )
                        if source_identity(source["url"]) in known:
                            continue
                        admission = dict(accepted=True, kind="manual", reason="用户补充链接") if source_identity(url) in manual_urls else classify(
                            article["sources"][0],
                            source,
                            queries(article["sources"][0]),
                        )
                        report.setdefault("admission", []).append(
                            dict(url=source["url"], **admission)
                        )
                        if not admission["accepted"]:
                            store.event(
                                article_id,
                                "资料筛选",
                                f"{source['title']}：{admission['reason']}",
                            )
                            continue
                        source["reference_role"] = admission
                        attach_source(
                            article_id, source, index, f"materials/source-{index}/text"
                        )
                        article["sources"].append(source)
                        known.update(
                            [source_identity(url), source_identity(source["url"])]
                        )
                        article["assets"] += download_assets(source, article_id, index)
                        current = store.read(article_id)
                        article["events"] = current["events"]
                        store.save(article)
                    except Exception as exc:
                        store.event(
                            article_id,
                            "关联检索",
                            f"关联来源获取失败：{url[:180]}；{failure_reason(exc)}",
                        )
                # Reload to retain progress messages added during research.
                current = store.read(article_id)
                article["events"] = current["events"]
                store.save(article)
            store.event(
                article_id, "原创撰写", "写作 Agent 整理事实、组织解读并添加逐项来源"
            )
            article = store.read(article_id)
            config_version = archive_configuration(store.folder(article_id))
            draft = RewritingAgent().run(
                article,
                options,
                article.get("review") if options.get("revise") else None,
            )
            article.update(draft)
            ensure_media(article)
            article["config_version"] = config_version
            article["revision"] += 1
            article["review"] = None
            store.save(article, snapshot=True)
        store.event(
            article_id, "独立审稿", "审稿 Agent 检查技术事实、排版、原创性与平台风险"
        )
        article = store.read(article_id)
        article["review"] = ReviewAgent().run(article, options)
        article["status"] = "Done"
        article["stage"] = (
            "待人工确认"
            if any(i["severity"] == "high" for i in article["review"]["issues"])
            else "生成完成"
        )
        article["error"] = None
        article["events"].append(
            dict(
                at=store.now(),
                stage=article["stage"],
                message="本轮写作与审稿结果已落盘，发布前请人工确认",
            )
        )
        store.save(article, snapshot=True)
    except Exception as exc:
        article = store.read(article_id)
        article["status"] = "New" if not article["body"] else "Done"
        article["stage"] = "处理失败，可重试"
        # Avoid persisting API responses, credentials, or signed URLs from exceptions.
        message = (
            str(exc)
            if isinstance(exc, ValueError)
            else f"{type(exc).__name__}：处理失败，请检查来源、网络或模型配置"
        )
        article["error"] = message[:400]
        article["events"].append(
            dict(at=store.now(), stage="失败", message=article["error"])
        )
        store.save(article, snapshot=True)
