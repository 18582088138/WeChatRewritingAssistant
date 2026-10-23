"""Real feedback revision and current-revision artifact validation."""

import hashlib
import io
import json
import re
import shutil
import subprocess
import zipfile

from PIL import Image


def revision_checks(api, result, output):
    article_id = result["article_id"]
    route = "/api/articles/" + article_id
    before = api.call("GET", route)
    assert before["review"]["draft_revision"] == before["revision"]
    options = dict(before.get("options", {}), research=False, revise=True)
    options["word_count"] = max(1800, options.get("word_count", 1200))
    api.call("POST", route + "/generate", json=options)
    after = api.idle(article_id)
    assert after["revision"] == before["revision"] + 1
    assert after["body"] != before["body"]
    assert after["review"]["draft_revision"] == after["revision"]
    assert [s["url"] for s in after["sources"]] == [s["url"] for s in before["sources"]]
    paragraphs = [p.strip() for p in after["body"].split("\n\n") if len(p.strip()) > 70]
    assert len(paragraphs) == len(set(paragraphs)), "修订后仍有完全重复的长段落"
    after = api.call("POST", route + "/cards")
    card_assets = [
        a for a in after["assets"] if a["id"].startswith(f"card-r{after['revision']}-")
    ]
    assert card_assets and all(
        a["id"].startswith(f"card-r{after['revision']}-") for a in card_assets
    )
    for asset in card_assets:
        with Image.open(output / "articles" / article_id / asset["path"]) as card:
            assert card.size == (1080, 1440)
            card.verify()
    exports = {}
    for platform in ["wechat", "x", "xiaohongshu", "weibo"]:
        raw = api.call("GET", route + "/export/" + platform)
        (output / (result["name"] + "-revised-" + platform + ".zip")).write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            assert after["body"] in archive.read("draft.md").decode("utf8")
            preview = archive.read("preview.html").decode("utf8")
            images = re.findall(r'<img[^>]+src="([^"]+)"', preview)
            assert all(path in archive.namelist() for path in images)
            referenced = re.findall(
                r"!\[[^]]*\]\((/api/articles/[^)]+)\)", after["body"]
            )
            assert len(images) == len(referenced), "正文配图引用在导出时丢失"
            assert all(
                a["id"] not in "\n".join(archive.namelist())
                for a in after["assets"]
                if not a["approved"]
            )
        exports[platform] = "passed"
    return dict(
        status="passed",
        before_revision=before["revision"],
        after_revision=after["revision"],
        before_score=before["review"]["score"],
        after_score=after["review"]["score"],
        before_issues=before["review"]["issues"],
        after_issues=after["review"]["issues"],
        fact_checks=after["review"]["fact_checks"],
        body_chars=len(after["body"]),
        card_count=len(card_assets),
        card_dimensions=[1080, 1440],
        exports=exports,
        duplicate_paragraphs=0,
    )


def material_checks(api, result, output):
    article = api.call("GET", "/api/articles/" + result["article_id"])
    evidence = []
    for asset in article["assets"]:
        if not asset.get("source_url"):
            continue
        path = output / "articles" / article["id"] / asset["path"]
        if asset["type"] == "video":
            probe = shutil.which("ffprobe")
            if not probe:
                evidence.append(
                    dict(
                        id=asset["id"],
                        type="video",
                        path=asset["path"],
                        validation="ffprobe_unavailable",
                    )
                )
                continue
            data = json.loads(
                subprocess.check_output(
                    [
                        probe,
                        "-v",
                        "error",
                        "-show_streams",
                        "-show_format",
                        "-of",
                        "json",
                        str(path),
                    ],
                    timeout=30,
                )
            )
            streams = [s for s in data["streams"] if s["codec_type"] == "video"]
            assert streams and float(data["format"]["duration"]) > 0
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == asset["sha256"]
            evidence.append(
                dict(
                    id=asset["id"],
                    type="video",
                    path=asset["path"],
                    sha256=digest,
                    codec=streams[0]["codec_name"],
                    width=streams[0]["width"],
                    height=streams[0]["height"],
                    duration_seconds=float(data["format"]["duration"]),
                    validation="ffprobe_passed",
                )
            )
            continue
        with Image.open(path) as image:
            size, frames = image.size, getattr(image, "n_frames", 1)
            image.verify()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if asset.get("saved_sha256"):
            assert digest == asset["saved_sha256"]
        if asset.get("animated") and path.suffix == ".gif":
            assert frames > 1 and digest == asset["sha256"]
        evidence.append(
            dict(
                id=asset["id"],
                type="image",
                path=asset["path"],
                size=size,
                frames=frames,
                sha256=digest,
                downloaded_sha256=asset["sha256"],
                approved=asset["approved"],
            )
        )
    return evidence
