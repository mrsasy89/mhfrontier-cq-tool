"""Map names and optional local visual references. No coordinate calibration."""
from contextlib import closing
from html import escape
from pathlib import Path
import sqlite3
import json
import hashlib
from importlib.resources import files
import webbrowser
from uuid import uuid4
from .binary import CATALOG
from .config import contains

FOLDERS = {"7": "Schrade Castle", "11": "Snowy Mountain Day", "21": "Snowy Mountain Night",
           "13": "Tower 01", "14": "Tower 02", "15": "Tower 03"}
TRACING = json.loads(files("mhfz_builder").joinpath("data/map_tracing.json").read_text(encoding="utf-8"))


def native_atlases(config):
    value = config.get("native_map_index") if config else None
    if not value:
        return []
    index = Path(value).expanduser().resolve()
    records = json.loads(index.read_text(encoding="utf-8"))
    result = []
    for record in records:
        path = (index.parent / record["file"].replace("\\", "/")).resolve()
        if not contains(index.parent, path) or path.suffix.lower() != ".png":
            raise ValueError("Native atlas path escapes its index directory")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise ValueError("Native atlas source hash mismatch")
        traced = TRACING["atlas_labels"].get(str(record["index"]), {})
        if traced.get("sha256") != record["sha256"]:
            traced = {}
        label = " / ".join(traced["names"]) if traced else record.get("visualLabel", "Unassigned native atlas")
        result.append({"index": record["index"], "path": path, "label": label,
                       "historical_label": record.get("visualLabel"), "sha256": record["sha256"],
                       "width": record["width"], "height": record["height"],
                       "review_state": traced.get("review_state", "unassigned"),
                       "display_crop": traced.get("display_crop")})
    return result


def traced_overviews(config):
    atlases = {r["index"]: r for r in native_atlases(config)}
    result = {}
    for key, records in TRACING["bindings"].items():
        for record in records:
            atlas = atlases.get(record["native_index"])
            if not atlas or atlas["sha256"] != record["sha256"]:
                continue
            result.setdefault(key, []).append({"path": atlas["path"], "label": record["label"],
                "status": record["review_state"].replace("_", " "), "review_state": record["review_state"],
                "notes": record["notes"], "evidence": record["evidence"],
                "visual_review": record.get("visual_review"), "view_label": record.get("view_label"),
                "coverage": record.get("coverage"),
                "native_index": record["native_index"], "width": atlas["width"], "height": atlas["height"],
                "display_crop": record.get("display_crop")})
    return result


def overview_bindings(config):
    result = traced_overviews(config)
    value = config.get("map_overview_index") if config else None
    if not value:
        return result
    index = Path(value).expanduser().resolve()
    bindings = json.loads(index.read_text(encoding="utf-8"))
    for key, records in bindings.items():
        if key not in CATALOG["maps"] or not isinstance(records, list):
            raise ValueError("Invalid map overview binding")
        result[key] = []
        for record in records:
            path = Path(record["path"]).expanduser().resolve()
            if path.suffix.lower() != ".png" or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise ValueError("Full-map overview hash/type mismatch")
            result[key].append({"path": path, "label": record["label"], "status": record["status"],
                                "review_state": record.get("review_state", "local_reference"),
                                "evidence": record.get("evidence", []), "notes": record.get("notes", ""),
                                "display_crop": record.get("display_crop"),
                                "width": record.get("width"), "height": record.get("height")})
    return result


def rows(config=None):
    counts = {}
    if config:
        database = Path(config["workspace"]) / "catalog.sqlite3"
        if database.is_file():
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
                counts = {str(mid): count for mid, count in db.execute("SELECT json_extract(summary,'$.map'),COUNT(*) FROM quests WHERE status='parsed' GROUP BY json_extract(summary,'$.map')")}
    root = Path(config["map_images_directory"]).expanduser().resolve() if config and config.get("map_images_directory") else None
    bindings = overview_bindings(config)
    result = []
    for key, item in sorted(CATALOG["maps"].items(), key=lambda row: int(row[0])):
        folder = root / FOLDERS.get(key, item["name"]) if root else None
        images = []
        if folder and folder.is_dir() and contains(root, folder):
            images = sorted((p.resolve() for p in folder.glob("*.png") if p.is_file() and contains(root, p)), key=lambda p: (not p.stem.isdigit(), int(p.stem) if p.stem.isdigit() else p.stem))
        result.append({"id": key, "name": item["name"], "references": counts.get(key, 0) if config else None,
                       "images": images, "overviews": bindings.get(key, []), "asset_folder": folder.name if folder else None})
    return result


def legend(items, page=0, page_size=12):
    pages = max(1, (len(items) + page_size - 1) // page_size)
    page %= pages
    lines = [f"MAP LEGEND  |  Page {page + 1}/{pages}", " ID   Map name                         Refs  Preview", "-" * 60]
    for item in items[page * page_size:(page + 1) * page_size]:
        count = str(item["references"]) if item["references"] is not None else "?"
        lines.append(f" {item['id']:>2}   {item['name']:<32} {count:>5}  {len(item['overviews']) if item['overviews'] else '-'}")
    lines += ["", "N/P: next/previous page | L: show ALL map names | V or V <ID>: gallery", "Preview variants may still be provisional.", "Enter an ID or part of a name; blank lets the prompt decide."]
    return "\n".join(lines)


def render_overview(record, title):
    url = escape(record["path"].as_uri(), quote=True)
    image = f'<img loading="lazy" src="{url}" alt="{escape(title)}">'
    crop = record.get("display_crop")
    if crop:
        if (len(crop) != 4 or any(type(v) is not int for v in crop) or
            not record.get("width") or not record.get("height")):
            raise ValueError("Invalid display crop metadata")
        x, y, right, bottom = crop
        if not (0 <= x < right <= record["width"] and 0 <= y < bottom <= record["height"]):
            raise ValueError("Display crop is outside the original image")
        width, height = right - x, bottom - y
        image = f'<div class="map-viewport" style="position:relative;overflow:hidden;aspect-ratio:{width}/{height}"><img loading="lazy" src="{url}" alt="{escape(title)}" style="position:absolute;max-width:none;width:{100 * record["width"] / width}%;height:auto;left:{-100 * x / width}%;top:{-100 * y / height}%"></div>'
    state = record.get("review_state")
    description = {"candidate_review": "Provisional preview", "variant_pending": "Variant not yet confirmed", "partial_overview": "Partial overview; additional views needed"}.get(state, "Visual reference")
    if record.get("visual_review") == "unsure":
        description = "Requires in-game verification"
    elif record.get("coverage") == "partial":
        description = "Partial overview; additional views needed"
    elif record.get("visual_review") == "correct" and state != "user_confirmed":
        description = "Visual identity confirmed; exact quest variant not verified"
    label = record.get("view_label") or title
    return f'<figure class="overview"><a href="{url}" target="_blank" rel="noopener">{image}</a><figcaption>{escape(label)} / {description}<p><a href="{url}">Open original image</a></p></figcaption></figure>'


def gallery(config, open_browser=False, map_id=None):
    items = rows(config)
    atlases = native_atlases(config)
    if map_id is not None and str(map_id) not in CATALOG["maps"]:
        raise ValueError("Unknown map ID")
    workspace = Path(config["workspace"]).resolve()
    if contains(Path(config["source"]), workspace):
        raise ValueError("Gallery workspace cannot be inside the corpus")
    destination = workspace / "map-gallery" / (uuid4().hex + ".html")
    cards = []
    for item in items:
        title = escape(item["name"])
        images = item["images"]
        preview = "".join(render_overview(r, item["name"]) for r in item["overviews"])
        if not preview:
            preview = '<div class="missing">No local preview available for the complete map yet.</div>'
        if images:
            areas = "".join(f'<figure><img loading="lazy" src="{escape(p.as_uri(), quote=True)}" alt="{title} asset {escape(p.stem)}"><figcaption>Asset {escape(p.name)}</figcaption></figure>' for p in images)
            detail = f'<details><summary>Separate area crops ({len(images)}); not a complete map</summary><p>Folder: {escape(item["asset_folder"])}</p><div class="areas">{areas}</div></details>'
        else:
            detail = ''
        cards.append(f'<article id="map-{item["id"]}" data-search="{escape(item["id"] + " " + item["name"], quote=True)}"><span class="tag">MAP {item["id"]} / {item["references"]} references</span><h2>{title}</h2>{preview}{detail}<p class="choose">Enter ID <strong>{item["id"]}</strong> in the terminal to select.</p></article>')
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>MHFZ Map Reference Gallery</title>
<style>body{margin:0;background:#111827;color:#e5e7eb;font:16px system-ui}header{padding:30px max(24px,5vw);background:#172338;border-bottom:1px solid #334155}h1{margin:0 0 10px;color:#fff}header p{max-width:1000px;color:#b9c8dc}input{width:min(92%,600px);padding:14px;border:1px solid #64748b;border-radius:10px;background:#0f172a;color:white;font:inherit}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px;padding:28px max(24px,5vw)}article{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:20px;scroll-margin:20px}article:target{border-color:#67e8f9;box-shadow:0 0 0 2px #0891b2}h2{font-size:21px;margin:12px 0}.tag{color:#67e8f9;font-size:12px;letter-spacing:1px}article>img{display:block;height:190px;max-width:100%;object-fit:contain;margin:auto;image-rendering:pixelated}.missing{height:190px;display:grid;place-items:center;color:#94a3b8}.choose{color:#b9c8dc;font-size:14px}strong{color:#67e8f9}summary{cursor:pointer;padding:12px 0;color:#a5f3fc}.areas{display:flex;flex-wrap:wrap;gap:14px}figure{margin:0}figure img{max-width:230px;max-height:210px;image-rendering:pixelated}figcaption{font-size:12px;color:#94a3b8}[hidden]{display:none}</style>
<header><h1>MHFZ / Complete map overviews</h1><p>Find a map by its catalog name or ID, then enter that ID in the terminal. Every associated overview or layer is shown; variants stay separate. Click an image for its full size.</p><p>Local minimaps are visual references only. Asset filenames and appearance do not certify area transitions, spawn coordinates or the native quest package. Missing associations remain explicit. No game images are bundled or uploaded.</p><input id="filter" type="search" placeholder="Search map name or ID" aria-label="Search maps"></header><main class="grid">'''+"".join(cards)+'''</main><style>.grid{grid-template-columns:repeat(auto-fit,minmax(420px,1fr))}.overview{margin:16px 0}.overview img{display:block;width:100%;height:auto;max-height:none;max-width:none;object-fit:contain;background:#111;image-rendering:pixelated}.overview figcaption{margin-top:8px;line-height:1.5}.missing{height:auto;min-height:160px;padding:15px}a{color:#67e8f9}@media(max-width:500px){.grid{grid-template-columns:minmax(0,1fr);padding:12px}article{padding:14px}}</style><script>document.getElementById('filter').addEventListener('input',function(){const q=this.value.toLowerCase();document.querySelectorAll('article').forEach(card=>card.hidden=!card.dataset.search.toLowerCase().includes(q));});</script></html>'''
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(document)
    url = destination.as_uri() + ("#map-" + str(map_id) if map_id is not None else "")
    opened = bool(webbrowser.open(url)) if open_browser else False
    return {"saved": str(destination), "opened": opened, "maps": len(items),
            "maps_with_previews": sum(bool(r["overviews"]) for r in items),
            "maps_with_area_crops": sum(bool(r["images"]) for r in items),
            "user_confirmed_maps": sum(bool(r["overviews"]) and all(v.get("review_state") == "user_confirmed" for v in r["overviews"]) for r in items),
            "native_atlases": len(atlases), "runtime_verified": False}
