"""Exercise real source extraction and both configured agents in an isolated directory."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import app
from backend import store
from backend.workflow import run

store.DATA = ROOT / 'test-results' / 'live-data'
existing = store.listing()
article = existing[0] if existing else store.create('https://arxiv.org/abs/2412.19437', '真实接口验证：DeepSeek-V3 技术报告（历史论文）')
options = dict(word_count=1200, style='专业、简洁；明确本文讨论 2024 年历史论文，不称为最新发布',
               platform='wechat', provider='deepseek', research=False, related_urls=[], revise=False)
run(article['id'], options)
saved = store.read(article['id'])
result = dict(status=saved['status'], stage=saved['stage'], sources=len(saved['sources']),
              body_length=len(saved['body']), review_score=saved['review']['score'] if saved['review'] else None,
              error=saved['error'])
print(json.dumps(result, ensure_ascii=False))
if saved['error'] or not saved['review']:
    sys.exit(1)
