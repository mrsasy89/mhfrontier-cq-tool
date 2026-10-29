from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path
from .binary import digest, inspect_bytes
from .config import contains


def probe(executable: Path) -> dict:
    if not executable.is_file():
        raise ValueError(f"ReFrontier not found: {executable}")
    result = subprocess.run([str(executable)], cwd=executable.parent, capture_output=True,
                            text=True, errors="replace", timeout=10)
    output = result.stdout + result.stderr
    if "-decryptOnly" in output or "-close" in output:
        mode = "legacy"
    elif "unpack" in output.lower():
        mode = "modern"
    else:
        raise ValueError("Unrecognized ReFrontier help: adapter compatibility must be checked")
    return {"path": str(executable), "mode": mode, "returncode": result.returncode,
            "help_excerpt": output[:1800]}


def unpack(config: dict, source: Path) -> dict:
    source = source.resolve()
    original = source.read_bytes()
    sha = digest(original)
    workspace = Path(config["workspace"]).resolve()
    if contains(Path(config["source"]), workspace):
        raise ValueError("Workspace is inside the corpus")
    job = workspace / "extractions" / sha / source.name
    manifest_path = job / "manifest.json"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if all(Path(x["path"]).is_file() and digest(Path(x["path"]).read_bytes()) == x["sha256"]
               for x in old["files"]):
            return old
        raise ValueError("Working copy modified: preserve it and choose a new workspace")
    if job.exists():
        raise ValueError(f"Incomplete extraction preserved: {job}; choose another workspace")
    executable = Path(config.get("refrontier") or "").resolve()
    mode = probe(executable)["mode"]
    editable = job / "editable"
    editable.mkdir(parents=True)
    (job / "original.bin").write_bytes(original)
    target = editable / source.name
    target.write_bytes(original)
    args = ([str(executable), str(target), "-log", "-close"] if mode == "legacy"
            else [str(executable), "unpack", str(target)])
    result = subprocess.run(args, cwd=editable, capture_output=True, text=True,
                            errors="replace", timeout=120)
    (job / "tool-output.txt").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if digest(source.read_bytes()) != sha:
        raise ValueError("The source changed during extraction")
    if result.returncode != 0:
        raise ValueError(f"ReFrontier exited with code {result.returncode}; logs in {job}")
    files = [{"path": str(p.resolve()), "sha256": digest(p.read_bytes())}
             for p in sorted(editable.rglob("*")) if p.is_file() and not p.is_symlink()]
    if not files:
        raise ValueError("ReFrontier produced no files")
    quest_files = []
    for row in files:
        try:
            inspect_bytes(Path(row["path"]).read_bytes())
            quest_files.append(row["path"])
        except (ValueError, OSError, IndexError):
            pass
    report = {"schema_version": 1, "source": str(source), "source_sha256": sha,
              "tool": str(executable), "tool_mode": mode, "command": args,
              "files": files, "quest_files": quest_files,
              "original_backup": str((job / "original.bin").resolve()),
              "source_unchanged": True, "working_directory": str(editable.resolve())}
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def read_summary(config: dict, path: Path) -> dict:
    data = path.read_bytes()
    from .binary import packed
    if not packed(data):
        return inspect_bytes(data)
    report = unpack(config, path)
    if len(report["quest_files"]) != 1:
        raise ValueError("Ambiguous extraction: explicitly select the quest BIN from the output files")
    return inspect_bytes(Path(report["quest_files"][0]).read_bytes())
