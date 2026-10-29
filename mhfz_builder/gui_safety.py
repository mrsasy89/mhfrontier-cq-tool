"""Guard native editor saves and preserve exact originals before Rust writes."""
import hashlib
import json
from pathlib import Path
import sys
from .config import load


def prepare_save(config, target):
    target = Path(target).resolve()
    workspace = Path(config["workspace"]).resolve()
    protected = [Path(config["source"]).resolve()]
    if config.get("server_quest_directory"):
        protected.append(Path(config["server_quest_directory"]).resolve())
    if not target.is_relative_to(workspace) or any(target.is_relative_to(root) for root in protected):
        raise ValueError("Save only inside the builder workspace. Server and reference files remain read-only.")
    backup = None
    if target.exists():
        data = target.read_bytes(); sha = hashlib.sha256(data).hexdigest()
        folder = workspace / "editor-backups"; folder.mkdir(parents=True, exist_ok=True)
        backup = folder / (sha + ".original")
        if not backup.exists():
            with backup.open("xb") as stream: stream.write(data)
        if hashlib.sha256(backup.read_bytes()).hexdigest() != sha:
            raise ValueError("Editor backup hash mismatch; save cancelled.")
    target.parent.mkdir(parents=True, exist_ok=True)
    return {"target": str(target), "backup": str(backup) if backup else None}


if __name__ == "__main__":
    try:
        print(json.dumps(prepare_save(load(Path(sys.argv[1])), sys.argv[2])))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
