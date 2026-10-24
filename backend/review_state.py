"""A saved review remains visible; its fingerprint indicates whether it is current."""

import hashlib
import json


def fingerprint(article):
    data = dict(title=article["title"], body=article["body"], assets=[{k: a.get(k) for k in ("id", "sha256", "approved", "alt")} for a in article["assets"]], sources=[dict(url=s["url"], text=s["text"]) for s in article["sources"]])
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def current(article):
    review = article.get("review")
    return bool(review and (review.get("fingerprint") == fingerprint(article) if review.get("fingerprint") else review.get("draft_revision") == article["revision"]))
