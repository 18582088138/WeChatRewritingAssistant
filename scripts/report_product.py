"""Summarize live acceptance evidence and optionally copy validated drafts into the GUI."""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import store
from backend.archive import safe_name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--import-drafts', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'test-results/product-revision-e2e'
    report = json.loads((output / 'e2e-report.json').read_text(encoding='utf8'))
    index = {json.loads(p.read_text(encoding='utf8'))['id']: p.parent for p in (output / 'articles').glob('*/article.json')}
    results = []
    for case in report['articles']:
        source = index[case['article_id']]
        article = json.loads((source / 'article.json').read_text(encoding='utf8'))
        row = dict(name=case['name'], id=article['id'], status=case['status'], source_chars=case['source_chars'],
                   original_images=case['quality']['saved_images'], sources=len(article['sources']),
                   original_review=case['review_score'], final_review=article['review']['score'],
                   revision=case['feedback_revision']['status'], body_chars=len(article['body']),
                   cards=case['feedback_revision'].get('card_count'),
                   videos=[m for m in case.get('materials_verified', []) if m['type']=='video'],
                   gifs=[m for m in case.get('materials_verified', []) if m.get('frames', 1)>1],
                   reference_roles=[dict(title=s['title'],date=s.get('published_at'),role=s.get('reference_role')) for s in article['sources']])
        if args.import_drafts:
            assert row['status']=='passed' and row['revision']=='passed'
            target = store.DATA / 'articles' / (safe_name(article['archive_title'])[:70] + ' · 实测 ' + article['id'][:8])
            assert source.resolve().is_relative_to(output.resolve())
            assert target.resolve().is_relative_to((store.DATA / 'articles').resolve())
            if not target.exists():
                shutil.copytree(source, target)
            imported = store.read(article['id'])
            imported['validation_label'] = '本轮真实 E2E 样稿'
            store.save(imported)
            row['gui_archive'] = str(target)
        results.append(row)
    (output / 'product-summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
