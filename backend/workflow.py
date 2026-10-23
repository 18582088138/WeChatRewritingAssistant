from . import store
from .agents import RewritingAgent, ReviewAgent
from .research import download_assets, extract, search


def ingest(article_id):
    store.event(article_id, '抓取来源', '提取文章或论文正文，保存来源与原始文件')
    article = store.read(article_id)
    if article['sources']:
        return
    source = extract(article['url'], store.folder(article_id) / 'materials' / 'source-1' / 'text')
    assets = download_assets(source, article_id, 1)
    article = store.read(article_id)
    article['sources'] = [source]
    article['assets'] = assets
    article['title'] = source['title']
    store.save(article)


def run(article_id, options, review_only=False):
    try:
        if not review_only:
            ingest(article_id)
            article = store.read(article_id)
            if options['research']:
                store.event(article_id, '关联检索', '搜索关联报道与一手资料；无法获取的来源将记录提示')
                urls = list(options.get('related_urls', []))
                try:
                    urls += [r['url'] for r in search(article['title'][:100] + ' official paper announcement')]
                except Exception:
                    store.event(article_id, '关联检索', '自动检索不可用，继续处理已有来源；可补充关联来源链接')
                known = {s['url'] for s in article['sources']}
                for url in urls[:6]:
                    if url in known or len(article['sources']) >= 4:
                        continue
                    try:
                        index = len(article['sources']) + 1
                        source = extract(url, store.folder(article_id) / 'materials' / f'source-{index}' / 'text')
                        article['sources'].append(source)
                        known.add(source['url'])
                        article['assets'] += download_assets(source, article_id, index)
                        current = store.read(article_id)
                        article['events'] = current['events']
                        store.save(article)
                    except Exception:
                        store.event(article_id, '关联检索', f'关联来源获取失败：{url[:180]}')
                # Reload to retain progress messages added during research.
                current = store.read(article_id)
                article['events'] = current['events']
                store.save(article)
            store.event(article_id, '原创撰写', '写作 Agent 整理事实、组织解读并添加逐项来源')
            article = store.read(article_id)
            draft = RewritingAgent().run(article, options, article.get('review') if options.get('revise') else None)
            article.update(draft)
            article['revision'] += 1
            article['review'] = None
            store.save(article, snapshot=True)
        store.event(article_id, '独立审稿', '审稿 Agent 检查技术事实、排版、原创性与平台风险')
        article = store.read(article_id)
        article['review'] = ReviewAgent().run(article, options)
        article['status'] = 'Done'
        article['stage'] = '待人工确认' if any(i['severity'] == 'high' for i in article['review']['issues']) else '生成完成'
        article['error'] = None
        article['events'].append(dict(at=store.now(), stage=article['stage'], message='本轮写作与审稿结果已落盘，发布前请人工确认'))
        store.save(article, snapshot=True)
    except Exception as exc:
        article = store.read(article_id)
        article['status'] = 'New' if not article['body'] else 'Done'
        article['stage'] = '处理失败，可重试'
        # Avoid persisting API responses, credentials, or signed URLs from exceptions.
        message = str(exc) if isinstance(exc, ValueError) else f'{type(exc).__name__}：处理失败，请检查来源、网络或模型配置'
        article['error'] = message[:400]
        article['events'].append(dict(at=store.now(), stage='失败', message=article['error']))
        store.save(article, snapshot=True)
