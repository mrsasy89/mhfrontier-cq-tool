from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import subprocess
from . import __version__
from .config import CONFIG_NAME, initialize, load, contains, configure_ai
from .refrontier import probe, unpack, read_summary
from .corpus import scan, search


def export_sql(quest_id: int, category: int, players: int, flags: int) -> str:
    if not 1 <= quest_id <= 65535 or not 0 <= category <= 65535 or not 1 <= players <= 255 or not 0 <= flags <= 255:
        raise ValueError("Registration values are out of range")
    return ("-- Prepared, NOT executed. Check the server schema/profile and quest ID.\n"
            "INSERT INTO public.event_quests\n"
            "(quest_id,quest_type,max_players,mark,flags,start_time,active_days,inactive_days)\n"
            f"SELECT {quest_id},{category},{players},0,{flags},NOW(),NULL,NULL\n"
            f"WHERE NOT EXISTS (SELECT 1 FROM public.event_quests WHERE quest_id={quest_id})\n"
            "RETURNING *;\n")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="MHFZ AI Quest Builder: CLI foundation, corpus and ReFrontier")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--config", type=Path, default=Path(CONFIG_NAME))
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("start", help="Open the guided terminal beta")
    sub.add_parser("gui-session", help="JSON-lines bridge for the optional native interface")
    maps = sub.add_parser("maps", help="List map IDs/names and optionally open a local visual gallery")
    maps.add_argument("--gallery", action="store_true")
    maps.add_argument("--open", action="store_true", help="Open the gallery in your browser")
    maps.add_argument("--images", type=Path, help="Existing local map image directory; never copied")
    fix = sub.add_parser("quest-fix", help="Diagnose all quest variants; optionally export profiled faint candidates")
    fix.add_argument("path", type=Path)
    fix.add_argument("--output-dir", type=Path, required=True)
    fix.add_argument("--faints", type=int, default=3)
    fix.add_argument("--candidate-profile", choices=["hr-penalty", "g-carts"], help="Explicit laboratory candidate only; never installs")
    registration = sub.add_parser("registration", help="Save SQL for a hash-verified workspace build")
    registration.add_argument("--manifest", type=Path, required=True)
    registration.add_argument("--category", type=int, default=54)
    registration.add_argument("--players", type=int, default=4)
    registration.add_argument("--flags", type=int, default=9)
    init = sub.add_parser("init", help="Configure separate corpus and workspace directories")
    init.add_argument("--source", type=Path, required=True)
    init.add_argument("--source-kind", choices=["server", "project"], default="project")
    init.add_argument("--refrontier")
    init.add_argument("--workspace", type=Path)
    ai = sub.add_parser("ai-configure", help="Select Codex account mode (default), Gemini or OpenAI API")
    ai.add_argument("--provider", choices=["codex", "gemini", "openai"], default="codex")
    ai.add_argument("--model")
    ai.add_argument("--codex-path", help="Optional official Codex executable path")
    ai.add_argument("--max-output-tokens", type=int, default=4096, help="API response token cap; not a Codex account quota")
    check = sub.add_parser("roundtrip", help="Verify an opaque-preserving raw BIN round trip")
    check.add_argument("path", type=Path)
    template = sub.add_parser("spec-template", help="Prepare an editable typed build specification from all base variants")
    template.add_argument("--source", type=Path, required=True)
    template.add_argument("--id", type=int, required=True)
    template.add_argument("--output", type=Path, required=True)
    compiler = sub.add_parser("compile", help="Compile a reviewed AI plan into a typed build specification")
    compiler.add_argument("--project", type=Path, required=True)
    compiler.add_argument("--id", type=int, required=True)
    compiler.add_argument("--notes", default="")
    compiler.add_argument("--output", type=Path, required=True)
    compiler.add_argument("--ask-key", action="store_true", help="Masked key prompt for API alternatives only")
    builder = sub.add_parser("build", help="Export new raw BIN variants without installing them")
    builder.add_argument("--spec", type=Path, required=True)
    builder.add_argument("--output-dir", type=Path, required=True)
    builder.add_argument("--dry-run", action="store_true")
    damage = sub.add_parser("damage", help="Quantize a percentage of supplied HP to Damage units")
    damage.add_argument("--hp", type=int, required=True)
    damage.add_argument("--percent", required=True)
    damage.add_argument("--rounding", choices=["exact", "ceil", "floor"], default="exact")
    sub.add_parser("codex-status", help="Check official CLI installation and personal account login")
    sub.add_parser("codex-install", help="Reuse the installed CLI or install the official npm package locally")
    login = sub.add_parser("codex-login", help="Sign in through the official Codex browser/device flow")
    login.add_argument("--device-auth", action="store_true")
    plan = sub.add_parser("plan", help="Interpret a prompt and propose a referenced plan with the selected provider")
    plan.add_argument("--prompt", required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--ask-key", action="store_true", help="Prompt for the API key locally without saving it")
    plan.add_argument("--dry-run", action="store_true", help="Check local readiness without API calls")
    sub.add_parser("doctor", help="Check configuration and ReFrontier syntax")
    index = sub.add_parser("index", help="Inventory all BINs; --decode also analyzes compressed files")
    index.add_argument("--decode", action="store_true")
    index.add_argument("--decode-limit", type=int)
    query = sub.add_parser("search", help="Search references across the entire indexed corpus")
    query.add_argument("--monster")
    query.add_argument("--map", dest="map_filter")
    query.add_argument("--limit", type=int, default=20)
    for name in ("inspect", "unpack"):
        command = sub.add_parser(name)
        command.add_argument("path", type=Path)
    draft = sub.add_parser("draft", help="Prepare a project and AI context without generating BINs yet")
    draft.add_argument("--prompt", required=True)
    draft.add_argument("--monster")
    draft.add_argument("--map", dest="map_filter")
    draft.add_argument("--output", type=Path, required=True)
    sql = sub.add_parser("sql", help="Print SQL without connecting to the database")
    sql.add_argument("--id", type=int, required=True)
    sql.add_argument("--category", type=int, default=54)
    sql.add_argument("--players", type=int, default=4)
    sql.add_argument("--flags", type=int, required=True)
    gui = sub.add_parser("gui", help="Optional read-only graphical inspector")
    gui.add_argument("path", type=Path, nargs="?")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    arguments = sys.argv[1:] if argv is None else argv
    args = parser().parse_args(arguments or ["start"])
    try:
        if args.command == "start":
            from .wizard import start
            return start(args.config)
        if args.command == "gui-session":
            from .gui_session import run
            return run(args.config)
        if args.command == "damage":
            from .writer import damage_threshold
            print(json.dumps(damage_threshold(args.hp, args.percent, args.rounding), indent=2))
            return 0
        if args.command == "sql":
            print(export_sql(args.id, args.category, args.players, args.flags), end="")
            return 0
        if args.command == "ai-configure":
            result = configure_ai(args.config.resolve(), args.model, args.max_output_tokens, args.provider, args.codex_path)
        elif args.command == "init":
            result = initialize(args.config.resolve(), args.source, args.refrontier, args.source_kind, args.workspace)
        else:
            config = load(args.config.resolve())
            if args.command == "maps":
                from .map_browser import rows, gallery
                selected = dict(config, map_images_directory=str(args.images.resolve())) if args.images else config
                result = gallery(selected, args.open) if args.gallery or args.open else [{k: v for k, v in r.items() if k not in ("images", "overviews")} | {"area_crop_assets": len(r["images"]), "complete_overviews": [{**v, "path": str(v["path"])} for v in r["overviews"]]} for r in rows(selected)]
            elif args.command == "quest-fix":
                from .quest_fix import run
                result = run(config, args.path, args.output_dir, args.faints, args.candidate_profile)
            elif args.command == "registration":
                from .registration import export_registration
                result = export_registration(config, args.manifest, args.category, args.players, args.flags)
            elif args.command == "doctor":
                from .providers import status
                result = {"version": __version__, "config": config, "ai": status(config),
                          "gui_optional": True,
                          "refrontier": probe(Path(config["refrontier"])) if config.get("refrontier") else "not configured"}
            elif args.command in ("codex-status", "codex-install", "codex-login"):
                from . import codex_provider
                if args.command == "codex-status":
                    result = codex_provider.login_status(config)
                elif args.command == "codex-install":
                    result = codex_provider.install(config)
                else:
                    result = codex_provider.login(config, args.device_auth)
            elif args.command == "roundtrip":
                from .build_service import roundtrip
                result = roundtrip(config, args.path)
            elif args.command in ("spec-template", "compile"):
                from .build_service import output_directory, prepare_spec, compile_project
                output = output_directory(config, args.output)
                if args.command == "spec-template":
                    result = prepare_spec(config, args.source, args.id)
                else:
                    from .providers import create_client, local_api_key
                    from .binary import digest
                    project_data = args.project.read_bytes()
                    project = json.loads(project_data)
                    with local_api_key(config, args.ask_key):
                        result = compile_project(config, project, digest(project_data), args.id, args.notes, create_client(config))
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("x", encoding="utf-8") as stream:
                    json.dump(result, stream, ensure_ascii=False, indent=2)
                result = {"saved": str(output), "quest_id": result["quest_id"],
                          "status": "needs_decisions" if result["unresolved"] or result["unsupported"] else "ready_for_build",
                          "bin_generated": False}
            elif args.command == "build":
                from .build_service import build
                result = build(config, json.loads(args.spec.read_text(encoding="utf-8-sig")), args.output_dir, args.dry_run)
            elif args.command == "index":
                if args.decode_limit is not None and args.decode_limit < 1:
                    raise ValueError("decode-limit must be positive")
                result = scan(config, args.decode, args.decode_limit)
            elif args.command == "search":
                result = search(config, args.monster, args.map_filter, args.limit)
            elif args.command == "inspect":
                result = read_summary(config, args.path.resolve())
            elif args.command == "unpack":
                result = unpack(config, args.path.resolve())
            elif args.command == "plan":
                from .providers import create_plan, settings, status, local_api_key
                from .planning import coverage
                output = args.output.resolve()
                if contains(Path(config["source"]), output):
                    raise ValueError("Generated plans cannot be written inside the corpus")
                if output.exists():
                    raise ValueError("Plan output already exists; choose a new path before making API calls")
                selected = settings(config)
                if args.ask_key and selected["kind"] == "codex":
                    raise ValueError("Codex account mode uses codex-login; no API key is required")
                if args.dry_run:
                    result = {"status": "preflight_only", "prompt": args.prompt,
                              "ai": status(config), "coverage": coverage(config),
                              "model_calls": [], "api_calls": [], "expected_model_calls_when_live": 2, "bin_generated": False}
                else:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with local_api_key(config, args.ask_key):
                        result = create_plan(config, args.prompt)
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("x", encoding="utf-8") as stream:
                    json.dump(result, stream, ensure_ascii=False, indent=2)
                result = {"saved": str(output), "status": result["status"],
                          "model_calls": len(result["model_calls"]), "bin_generated": False}
            elif args.command == "draft":
                output = args.output.resolve()
                if contains(Path(config["source"]), output):
                    raise ValueError("Generated projects cannot be written inside the corpus")
                result = {"schema_version": 1, "status": "awaiting_ai_provider",
                          "prompt": args.prompt,
                          "filters": {"monster": args.monster, "map": args.map_filter},
                          "references": search(config, args.monster, args.map_filter, 10),
                          "runtime_verified": False, "bin_generated": False}
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("x", encoding="utf-8") as stream:
                    json.dump(result, stream, ensure_ascii=False, indent=2)
                result = {"saved": str(output), "references": len(result["references"]),
                          "status": "awaiting_ai_provider", "bin_generated": False}
            elif args.command == "gui":
                try:
                    from .gui import launch
                except ImportError as exc:
                    raise ValueError("The optional inspector requires Python tkinter support") from exc
                launch(config, args.path)
                return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, IndexError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
