from __future__ import annotations
import subprocess
import json
from pathlib import Path
import sqlite3
from .binary import digest, packed, inspect_bytes
from .config import contains
from .refrontier import read_summary


def database(config: dict) -> sqlite3.Connection:
    workspace = Path(config["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(workspace / "catalog.sqlite3")
    db.execute("CREATE TABLE IF NOT EXISTS quests (path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, status TEXT NOT NULL, summary TEXT, error TEXT)")
    return db


def scan(config: dict, decode: bool = False, decode_limit: int | None = None, progress=None) -> dict:
    source = Path(config["source"]).resolve()
    files = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() == ".bin"
                   and not p.is_symlink() and contains(source, p))
    db = database(config)
    seen = set()
    decoded_count = 0
    parsed_count = error_count = 0
    try:
        for index, path in enumerate(files, 1):
            if progress:
                progress({"processed": index - 1, "total": len(files), "parsed": parsed_count, "errors": error_count})
            key = str(path.resolve())
            seen.add(key)
            sha = "unreadable"
            summary = None
            error = None
            try:
                data = path.read_bytes()
                sha = digest(data)
                old = db.execute("SELECT sha256,status FROM quests WHERE path=?", (key,)).fetchone()
                if old and old[0] == sha and old[1] == "parsed":
                    parsed_count += 1
                    continue
                if packed(data):
                    if not decode or (decode_limit is not None and decoded_count >= decode_limit):
                        status = "needs_decode"
                    else:
                        decoded_count += 1
                        summary = read_summary(config, path)
                        status = "parsed"
                else:
                    summary = inspect_bytes(data)
                    status = "parsed"
            except (ValueError, OSError, IndexError, TimeoutError, subprocess.SubprocessError) as exc:
                status, error = "error", str(exc)
            db.execute("INSERT OR REPLACE INTO quests VALUES (?,?,?,?,?)",
                       (key, sha, status, json.dumps(summary, ensure_ascii=False) if summary else None, error))
            parsed_count += status == "parsed"
            error_count += status == "error"
            if index % 100 == 0:
                db.commit()
        existing = [row[0] for row in db.execute("SELECT path FROM quests")]
        for key in existing:
            if key not in seen:
                db.execute("UPDATE quests SET status='missing' WHERE path=?", (key,))
        db.commit()
        counts = dict(db.execute("SELECT status,COUNT(*) FROM quests GROUP BY status"))
        if progress:
            progress({"processed": len(files), "total": len(files), "parsed": parsed_count, "errors": error_count})
        return {"source": str(source), "found_bin_files": len(files), "statuses": counts,
                "decoded_this_run": decoded_count,
                "coverage_complete": not any(counts.get(k, 0) for k in ("needs_decode", "error", "missing")),
                "note": "All variants inventoried; parsed does not imply in-game verification"}
    finally:
        db.commit()
        db.close()


def search(config: dict, monster: str | None = None, map_filter: str | None = None,
           limit: int = 20) -> list[dict]:
    if limit < 1:
        raise ValueError("limit must be positive")
    db = database(config)
    result = []
    try:
        for path, sha, summary in db.execute("SELECT path,sha256,summary FROM quests WHERE status='parsed' ORDER BY path"):
            row = json.loads(summary)
            if monster and not any(monster.casefold() in m["name"].casefold() or monster == str(m["id"]) for m in row["monsters"]):
                continue
            if map_filter:
                if map_filter.isdecimal():
                    if int(map_filter) != row["map"]:
                        continue
                elif map_filter.casefold() not in row["map_name"].casefold():
                    continue
            result.append({"source": path, "source_sha256": sha, "quest": row})
            if len(result) >= limit:
                break
        return result
    finally:
        db.close()
