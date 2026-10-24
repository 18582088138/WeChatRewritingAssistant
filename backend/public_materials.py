"""Shared files are separate from article archives; selected items are copied for stability."""

import copy
import hashlib
import json
import shutil
import uuid

from . import store
from .manual_materials import sync, upload
from .research import extract, download_assets
from .archive import safe_name, save_source_document, material_folder
from .video_posters import ensure_posters


def root():
    path = store.DATA / "public-materials"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(library):
    path = root() / "library.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(library, ensure_ascii=False, indent=2), encoding="utf8")
    temp.replace(path)
    return library


def read():
    with store.LOCK:
        path = root() / "library.json"
        library = json.loads(path.read_text(encoding="utf8")) if path.exists() else dict(id="public", title="公共素材库", sources=[], assets=[], manual_files={})
        sync(library, root(), persist=False)
        library["storage_path"] = str(root())
        return save(library)


def add_file(name, raw):
    with store.LOCK:
        library = read()
        return save(upload("public", name, raw, root=root(), article=library))


def add_url(url):
    stage = root() / "imports" / uuid.uuid4().hex
    source = extract(url, stage / "text")
    source["storage_dir"] = "."
    assets = download_assets(source, "public", 1, article_root=stage)
    save_source_document(source, stage / "原文")
    key = hashlib.sha256(source["url"].encode()).hexdigest()[:16]
    with store.LOCK:
        library = read()
        relative = "references/" + safe_name(source["title"]) + " · " + key[:6]
        destination = root() / relative
        shutil.copytree(stage, destination, dirs_exist_ok=True)
        source["public_key"] = key
        source["public_storage_dir"] = relative
        library["sources"] = [s for s in library["sources"] if s.get("public_key") != key] + [source]
        for asset in assets:
            asset["id"] = key + "-" + asset["id"]
            asset["path"] = relative + "/" + asset["path"]
        library["assets"] = [a for a in library["assets"] if not a["id"].startswith(key + "-")] + assets
        return save(library)


def attach(article, source_index=None, asset_id=None):
    library = read()
    result = dict(article=article)
    if source_index is not None:
        if not 0 <= source_index < len(library["sources"]):
            raise ValueError("公共参考资料不存在")
        source = copy.deepcopy(library["sources"][source_index])
        key = hashlib.sha256((source["url"] + source["text"]).encode()).hexdigest()
        existing = next((i for i, s in enumerate(article["sources"]) if s.get("public_origin") == key), None)
        if existing is None:
            source.pop("storage_dir", None)
            destination = material_folder(store.folder(article["id"]), source, len(article["sources"]) + 1)
            destination.mkdir(parents=True, exist_ok=True)
            shared_dir = source.get("public_storage_dir")
            if shared_dir:
                original = (root() / shared_dir).resolve()
                if not original.is_relative_to(root().resolve()):
                    raise ValueError("公共资料目录无效")
                shutil.copytree(original, destination, dirs_exist_ok=True)
                for asset in library["assets"]:
                    if asset["path"].startswith(shared_dir + "/"):
                        copied = copy.deepcopy(asset)
                        copied["id"] = "public-source-" + key[:12] + "-" + asset["id"]
                        copied["path"] = destination.relative_to(store.folder(article["id"])).as_posix() + "/" + asset["path"][len(shared_dir) + 1:]
                        article["assets"].append(copied)
            elif source.get("manual_path"):
                original = (root() / source["manual_path"]).resolve()
                if not original.is_relative_to(root().resolve()) or not original.is_file():
                    raise ValueError("公共文档文件不存在")
                (destination / "text").mkdir(exist_ok=True)
                shutil.copy2(original, destination / "text" / original.name)
                source["public_manual_path"] = source.pop("manual_path")
            source["storage_dir"] = destination.relative_to(store.folder(article["id"])).as_posix()
            save_source_document(source, destination)
            source.update(public_origin=key, reference_role=dict(kind="manual", reason="公共素材库补充"))
            article["sources"].append(source)
            existing = len(article["sources"]) - 1
        result["source_id"] = existing + 1
    if asset_id is not None:
        original = next((a for a in library["assets"] if a["id"] == asset_id), None)
        if not original:
            raise ValueError("公共媒体不存在")
        asset = copy.deepcopy(original)
        asset["id"] = "public-" + hashlib.sha256((asset_id + str(asset.get("sha256", ""))).encode()).hexdigest()[:20]
        src = (root() / asset["path"]).resolve()
        if not src.is_relative_to(root().resolve()) or not src.is_file():
            raise ValueError("公共素材文件不存在")
        relative = "materials/public/" + asset["id"] + src.suffix
        dest = store.folder(article["id"]) / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        asset.update(path=relative, public_origin=asset_id)
        if not any(a["id"] == asset["id"] for a in article["assets"]):
            article["assets"].append(asset)
        result["asset"] = asset
        ensure_posters(article, store.folder(article["id"]))
    ensure_posters(article, store.folder(article["id"]))
    result["article"] = store.save(article, snapshot=bool(article.get("body")))
    return result
