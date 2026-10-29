"""Registration preview only. No database connection or server installation."""
from pathlib import Path
import json
from .binary import digest
from .config import contains


def export_registration(config, manifest_path, category=54, players=4, flags=9):
    from .cli import export_sql
    manifest_path = Path(manifest_path).resolve()
    if not contains(Path(config["workspace"]), manifest_path) or contains(Path(config["source"]), manifest_path):
        raise ValueError("Registration exports require a build manifest inside the workspace")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "built_unverified" or not manifest.get("outputs"):
        raise ValueError("A completed build is required")
    for row in manifest["outputs"]:
        output = Path(row["path"]).resolve()
        if output.parent != manifest_path.parent or digest(output.read_bytes()) != row["output_raw_sha256"]:
            raise ValueError("Build output hash/path changed; registration preview refused")
    query = export_sql(manifest["quest_id"], category, players, flags)
    destination = manifest_path.parent / "register-event-quest.sql"
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(query)
    return {"saved": str(destination), "executed": False, "profile": "event_quests schema; verify against your Erupe installation"}
