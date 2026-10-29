"""Build a small source-only beta. Never enumerate private workspace content."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mhfz_builder import __version__


def package(destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    app = destination / "quest-builder.pyz"
    with zipfile.ZipFile(app, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("__main__.py", "from mhfz_builder.cli import main\nraise SystemExit(main())\n")
        for path in sorted((ROOT / "mhfz_builder").glob("*.py")):
            archive.write(path, path.relative_to(ROOT).as_posix())
        for name in ("catalog.json", "domain_rules.json", "map_tracing.json", "items.json"):
            path = ROOT / "mhfz_builder/data" / name
            archive.write(path, path.relative_to(ROOT).as_posix())
    bundle = destination / f"mhfz-ai-quest-builder-{__version__}.zip"
    public = ["Start.cmd", "GUI.cmd", "Dev.cmd", "Inspect.cmd", "README.md", "LICENSE", "NOTICE.md"]
    public += ["knowledge/SOURCES.md", "knowledge/sources.json", "knowledge/rules.md"]
    public += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "docs").glob("*.md"))]
    with zipfile.ZipFile(bundle, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(app, app.name)
        for name in public:
            archive.write(ROOT / name, name)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (app, bundle)}
    (destination / "SHA256SUMS").write_text("".join(f"{sha}  {name}\n" for name, sha in hashes.items()), encoding="utf-8")
    manifest = {"version": __version__, "source_commit": commit,
                "source_revision_note": "Working tree changes may be present in local packages; CI packages use the checked-out commit.",
                "python_required": ">=3.11", "includes_corpus": False, "sha256": hashes}
    (destination / "package-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / f"beta-{__version__}")
    print(json.dumps(package(parser.parse_args().output), indent=2))
