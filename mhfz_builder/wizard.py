"""Guided beta terminal interface. Uses the same services as the explicit CLI."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import os
import sys
import time
from contextlib import closing
from uuid import uuid4
from . import __version__
from .binary import CATALOG, digest
from .config import initialize, load, replace_config, configure_ai
from .providers import settings, status, create_plan, create_client, local_api_key
from .planning import coverage
from .corpus import scan
from .build_service import compile_project, build
from .registration import export_registration
from .quest_ids import occupied_ids, first_available
from .authoring import collect_preferences, preferences_text, enforce_preferences


class Back(Exception):
    """Return to the parent page without retrying model calls."""


class Console:
    def __init__(self, read=None, write=None, interactive=None):
        self.interactive = (read is None and write is None and sys.stdin.isatty() and sys.stdout.isatty()) if interactive is None else interactive
        self.read = read or input
        self.write = write or print
        self.heading = "Welcome"
        self.content = None
        self.last_progress = 0
        self.key_reader = None

    def index_progress(self, event):
        if self.interactive and os.name == "nt":
            import msvcrt
            if msvcrt.kbhit() and msvcrt.getwch().lower() in ("b", "\x1b"):
                raise Back()
        now = time.monotonic()
        if event["processed"] == event["total"] or now - self.last_progress >= 2:
            self.write(f"Indexed {event['processed']} / {event['total']} | parsed: {event['parsed']} | errors: {event['errors']}")
            self.last_progress = now

    def clear(self):
        if self.interactive:
            if os.name == "nt":
                subprocess.run(["cmd.exe", "/c", "cls"], check=False)
            else:
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.flush()

    def screen(self, heading, content=None):
        self.heading, self.content = heading, content
        self.clear()
        self.write("=" * 66)
        self.write(f"  MHFZ AI QUEST BUILDER                         {__version__}")
        self.write("  " + heading)
        self.write("=" * 66)
        if content:
            self.write(content)
        self.write("")
        self.write("[B] Back   |   cls: redraw   |   Ctrl+C: stop")

    def pause(self):
        if self.interactive:
            self.read("\nPress Enter to return to the menu...")

    def ask(self, label, default=None):
        while True:
            value = self.read(f"{label}" + (f" [{default}]" if default is not None else "") + ": ").strip()
            if value.lower() in ("cls", "clear"):
                self.screen(self.heading, self.content)
                continue
            if value.lower() in ("b", "back", "indietro") or value == "\x1b":
                raise Back()
            return value if value else str(default) if default is not None else ""

    def number(self, label, low, high, default=None):
        while True:
            try:
                value = int(self.ask(label, default))
                if low <= value <= high:
                    return value
            except ValueError:
                pass
            self.write(f"Enter an integer between {low} and {high}.")

    def description(self, previous=""):
        self.write("Describe the quest: paste one or more lines. Type END on a separate line to finish. B returns.")
        if previous:
            self.write("Previous description:\n" + previous)
            self.write("END without new text keeps the previous description.")
        lines = []
        while True:
            line = self.ask(">")
            if line.upper() == "END":
                text = "\n".join(lines).strip() or previous
                if text:
                    return text
                self.write("Enter a description before END.")
            else:
                lines.append(line)

    def save(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)

    def edit_rewards(self, path):
        from .reward_editor import launch
        return launch(path)

    def progress(self, text):
        self.write(text)


def configure_paths(path, ui):
    ui.screen("Setup / local paths", "Four steps. Enter keeps the value in [brackets].\nUse cls at a prompt to redraw this screen.")
    previous = json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}
    ui.write("[1/4] Source type -- enter a word here, not a folder path.")
    ui.write("  server  = existing quest folder on your server\n  project = your own local collection of quests")
    kind = ui.ask("Source type: server or project", previous.get("source_kind", "project"))
    if kind not in ("server", "project"):
        raise ValueError("Corpus type must be server or project")
    ui.write("\n[2/4] Quest folder -- paste the full directory path here.")
    while True:
        source_text = ui.ask("Quest corpus directory", previous.get("source", str(path.parent / "corpus/quests")))
        source = Path(source_text.strip('"')).expanduser().resolve()
        if kind == "project" or source.is_dir():
            break
        ui.write(f"Folder not found: {source}\nEnter your existing quest directory; this step will be repeated.")
    if kind == "project" and not source.exists():
        source.mkdir(parents=True)
    ui.write("\n[3/4] ReFrontier -- full executable path, including its filename.")
    while True:
        refrontier = ui.ask("ReFrontier executable (optional; '-' disables it)", previous.get("refrontier") or "").strip('"')
        if refrontier == "-":
            refrontier = ""
        if not refrontier:
            break
        executable = Path(refrontier).expanduser().resolve()
        if executable.is_file():
            refrontier = str(executable)
            break
        ui.write(f"Executable not found: {executable}\nCheck the filename, including .exe on Windows, or enter '-' to skip.")
    ui.write("\n[4/4] Workspace -- generated projects and backups, separate from quests.")
    workspace = Path(ui.ask("Local workspace directory", previous.get("workspace", str(path.parent / ".workspace"))).strip('"')).expanduser().resolve()
    if previous:
        candidate = dict(previous, source_kind=kind, source=str(source), workspace=str(workspace),
                         refrontier=str(Path(refrontier.strip('"')).expanduser().resolve()) if refrontier else None)
        backup = replace_config(path, candidate)
        ui.write(f"Configuration updated. Previous bytes preserved: {backup}")
    else:
        initialize(path, source, refrontier.strip('"') or None, kind, workspace)
        ui.write("Configuration created. Corpus files remain read-only.")
    return load(path)


def choose_provider(path, ui):
    ui.write("1. Codex personal account (primary)\n2. Gemini API (free tier depends on your project/quotas)\n3. OpenAI Platform API (separate API billing)")
    choice = ui.number("Provider", 1, 3, 1)
    provider = {1: "codex", 2: "gemini", 3: "openai"}[choice]
    model = ui.ask("Model override (blank uses provider default)") or None
    executable = (ui.ask("Custom official Codex executable path (optional)").strip('"') or None) if provider == "codex" else None
    result = configure_ai(path, model, provider=provider, executable=executable)
    if result.get("notice"):
        ui.write(result["notice"])
    return load(path)


def ensure_provider(config, ui):
    if settings(config)["kind"] != "codex":
        ui.write("The selected API provider uses your local key. No provider or billing fallback is enabled.")
        return True
    from . import codex_provider
    state = status(config)
    if not state.get("installed"):
        ui.write("Official Codex CLI was not found. Installation requires Node.js/npm.")
        if ui.ask("Install the official CLI locally now? y/n", "n").lower() != "y":
            return False
        codex_provider.install(config)
        state = codex_provider.login_status(config)
    if state.get("account_ready"):
        ui.write("Your personal Codex/ChatGPT login is ready.")
        return True
    ui.write("Sign in through the official CLI. This uses its shared local account store.")
    ui.write("1. Browser login\n2. Device-code login\n0. Back")
    method = ui.number("Login method", 0, 2, 1)
    if not method:
        return False
    return codex_provider.login(config, method == 2).get("account_ready", False)


def choose_map(ui, config=None):
    if hasattr(ui, "map_picker"):
        return ui.map_picker(config)
    from .map_browser import rows, legend, gallery
    items, page = rows(config), 0
    ui.write(legend(items, page))
    while True:
        query = ui.ask("Map name or ID (blank lets the prompt decide)")
        if query.lower() in ("l", "?"):
            ui.screen("Map legend / all catalog maps", legend(items, page_size=max(1, len(items))))
            continue
        if query.lower() in ("n", "p"):
            page += 1 if query.lower() == "n" else -1
            ui.screen("Create / map selection", legend(items, page))
            continue
        if query.lower() == "r":
            ui.write("Map association review is handled in chat. Use V for previews or L for the complete legend.")
            continue
        if query.lower() == "v" or query.lower().startswith("v "):
            if not config:
                ui.write("Configure a workspace before opening a gallery.")
                continue
            try:
                result = gallery(config, open_browser=True, map_id=query[2:].strip() or None)
                ui.write(f"Gallery: {result['saved']} ({result['maps_with_previews']} maps with local previews)")
                if not result["opened"]:
                    ui.write("Open that HTML file in your browser, then return here to select an ID.")
            except (ValueError, OSError) as exc:
                ui.write(f"Could not open gallery: {exc}")
            continue
        if not query:
            return ""
        matches = [(key, value["name"]) for key, value in CATALOG["maps"].items()
                   if key == query or query.casefold() in value["name"].casefold()]
        if len(matches) == 1:
            key, name = matches[0]
            ui.write(f"Selected map: {name} ({key}). A native reference package is still required.")
            return f" Use the native {name} map package (map ID {key}); preserve its zones and transitions."
        if not matches:
            ui.write("No catalog match. Try another name, a map ID, or leave blank.")
        else:
            ui.write("Matching maps: " + ", ".join(f"{key}: {name}" for key, name in matches[:20]))


def index_ready(config):
    state = coverage(config)
    if not state["parsed"]:
        raise ValueError("No parsed quest references. Index/decode a batch first.")
    source = Path(config["source"])
    db_path = Path(config["workspace"]) / "catalog.sqlite3"
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        for (path,) in db.execute("SELECT path FROM quests WHERE status='parsed'"):
            if not Path(path).is_relative_to(source):
                raise ValueError("The index belongs to another corpus. Run indexing before making model requests.")
    return state


def registration_dialog(config, manifest, ui):
    ui.write("Registration SQL preview only. No database connection or installation will occur.")
    category = ui.number("Quest category", 0, 65535, 54)
    players = ui.number("Maximum players", 1, 255, 4)
    flags = ui.number("Event flags", 0, 255, 9)
    result = export_registration(config, manifest, category, players, flags)
    ui.write(f"Saved SQL: {result['saved']}")
    ui.write("Check the server schema and database ID availability before using the query.")


def choose_quest_id(config, ui):
    occupied, checked, server_checked = occupied_ids(config)
    for directory in checked:
        ui.write("ID scan: " + directory)
    if not server_checked:
        ui.write("No server folder configured: only the reference library and local exports were checked. Set the server folder in Settings > 4 to include it.")
    ui.write("Custom range: 65001-65535. Quest 65005 is reserved. Database availability is NOT checked.")
    candidate = first_available(occupied)
    while True:
        ui.write(f"Proposed quest ID: {candidate}")
        answer = ui.ask("Use this ID? Type yes to confirm, or enter another custom ID")
        if answer.lower() in ("yes", "y"):
            # Files may have changed while the user reviewed the proposal.
            current, _, _ = occupied_ids(config)
            if candidate not in current:
                return candidate
            ui.write("That ID has become occupied. Scanning again.")
            candidate = first_available(current)
            occupied = current
        else:
            try:
                replacement = int(answer)
            except ValueError:
                ui.write("Type yes to confirm, a numeric ID to change it, or B to return.")
                continue
            occupied, _, _ = occupied_ids(config)
            if not 65001 <= replacement <= 65535 or replacement in occupied:
                ui.write("Choose an unused custom ID in 65001-65535; 65005 is reserved.")
                continue
            candidate = replacement


def create_quest(config, ui):
    state = index_ready(config)
    total = sum(state["statuses"].values())
    ui.write(f"Searchable references: {state['parsed']} / {total}; pending decode: {state['statuses'].get('needs_decode', 0)}; errors: {state['statuses'].get('error', 0)}.")
    if not state["complete"]:
        ui.write("Coverage is incomplete. Use Corpus > Analyze all to include remaining readable quests.")
    step = 0
    map_constraint = prompt = ""
    quest_id = None
    choices = None
    while step < 4:
        try:
            if step == 0:
                map_constraint = choose_map(ui, config)
            elif step == 1:
                prompt = ui.description(prompt)
            elif step == 2:
                choices = collect_preferences(ui)
            else:
                quest_id = choose_quest_id(config, ui)
            step += 1
        except Back:
            if step == 0:
                raise
            step -= 1
            ui.write("Returned to the previous step. No model request made.")
    if not prompt:
        return
    prompt += map_constraint + preferences_text(choices)
    session = Path(config["workspace"]) / "sessions" / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8])
    session.mkdir(parents=True, exist_ok=False)
    ui.save(session / "authoring-request.json", {"quest_id": quest_id, "prompt": prompt, "choices": choices})
    ui.write(f"Session: {session}")
    if not ensure_provider(config, ui):
        return
    ask_key = settings(config)["kind"] != "codex"
    with local_api_key(config, ask_key, ui.key_reader):
        ui.write("Planning with the selected provider; targeted corpus research may require additional model turns...")
        ui.progress('Interpreting the quest request')
        project = create_plan(dict(config, _progress=ui.progress), prompt)
        project_file = session / "plan.json"
        ui.save(project_file, project)
        ui.write(project["plan"]["summary"])
        for row in project["references"]:
            ui.write(f"{row['reference_id']}: quest {row['quest']['quest_id']}, {row['quest']['map_name']}, {len(row['source_variants'])} file variant(s)")
        for question in project["plan"]["questions"]:
            ui.write("Question: " + question)
        if project["status"] == "needs_reference":
            ui.write("No usable base. Plan saved; decode more corpus content or revise the request.")
            return
        notes = ui.ask("Additional decisions, thresholds or corrections (optional)")
        for attempt in range(1, 4):
            ui.write("Compiling typed values (one additional model turn)...")
            ui.progress('Waiting for Codex: compiling typed quest edits')
            try:
                spec = compile_project(dict(config, _progress=ui.progress), project, digest(project_file.read_bytes()), quest_id, notes, create_client(config), choices=choices)
            except ValueError as exc:
                ui.save(session / f'compile-failed-{attempt}.json', {'error': str(exc), 'notes': notes, 'bin_generated': False})
                ui.write(f'Compilation stopped: {exc}. Request and diagnostics are preserved in {session}.')
                return
            enforce_preferences(config, spec, choices)
            ui.save(session / f"spec-{attempt}.json", spec)
            blockers = spec["unresolved"] + spec["unsupported"]
            if blockers:
                for issue in blockers:
                    ui.write("Unresolved/unsupported: " + issue)
                extra = ui.ask("Add decisions for another compiler turn, or leave blank to stop")
                if not extra:
                    return
                notes += "\n" + extra
                continue
            ui.write("Build preview (null fields preserve the base):")
            ui.write(json.dumps(spec["edits"], ensure_ascii=False, indent=2))
            for warning in spec["provenance"].get("warnings", []):
                ui.write("Note: " + warning)
            ui.write("1. Export laboratory BINs\n2. Add notes and recompile\n0. Save without export")
            action = ui.number("Next action", 0, 2, 1)
            if action == 0:
                return
            if action == 2:
                notes += "\n" + ui.ask("Corrections")
                continue
            ui.progress('Validating and exporting laboratory BIN variants')
            result = build(config, spec, Path(config["workspace"]) / "custom-quests" / session.name)
            for filename in result["outputs"]:
                ui.write("Exported: " + filename)
            ui.write("Manifest: " + result["manifest"])
            ui.write("Not installed. Client gameplay remains unverified.")
            if ui.ask("Also prepare event_quests SQL? y/n", "y").lower() == "y":
                try:
                    registration_dialog(config, result["manifest"], ui)
                except Back:
                    ui.write("SQL export skipped. Generated quest files are preserved.")
            return
        ui.write("Compiler attempt limit reached; session files are preserved for review.")


def settings_page(config_path, ui):
    while True:
        config = load(config_path)
        ui.screen("Settings / paths, provider and account")
        ui.write("1. Reference library / ReFrontier / workspace paths\n2. Provider / model\n3. Codex login/status\n4. Optional server destination (no automatic transfer)\n5. Local map preview images (optional)\n0. Back")
        choice = ui.number("Settings", 0, 5, 0)
        if choice == 0:
            return
        try:
            if choice == 1:
                configure_paths(config_path, ui)
            elif choice == 2:
                ui.screen("Settings / provider")
                choose_provider(config_path, ui)
            elif choice == 3:
                ui.screen("Settings / Codex account")
                ui.write(json.dumps(status(config), indent=2))
                if settings(config)["kind"] == "codex":
                    ensure_provider(config, ui)
            elif choice == 4:
                ui.screen("Settings / optional server destination")
                value = ui.ask("Server quest directory ('-' disables; no files will be transferred)", config.get("server_quest_directory") or "").strip('"')
                target = Path(value).expanduser().resolve() if value and value != "-" else None
                if target and not target.is_dir():
                    raise ValueError("Server destination directory not found")
                candidate = dict(config, server_quest_directory=str(target) if target else None)
                ui.write("Previous configuration preserved: " + str(replace_config(config_path, candidate)))
            else:
                ui.screen("Settings / local map previews")
                value = ui.ask("Existing map images directory ('-' disables; no images will be copied)", config.get("map_images_directory") or "").strip('"')
                target = Path(value).expanduser().resolve() if value and value != "-" else None
                if target and not target.is_dir():
                    raise ValueError("Map images directory not found")
                candidate = dict(config, map_images_directory=str(target) if target else None)
                ui.write("Previous configuration preserved: " + str(replace_config(config_path, candidate)))
            ui.pause()
        except Back:
            continue
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            ui.write(f"Could not update settings: {exc}")
            ui.pause()


def start(config_path, ui=None):
    ui = ui or Console()
    config_path = Path(config_path).resolve()
    ui.screen("Welcome / terminal beta")
    ui.write("Builds stay in the workspace. The application does not install quests or execute SQL.")
    try:
        while True:
            try:
                try:
                    config = load(config_path)
                except (ValueError, OSError, KeyError):
                    ui.write("First setup or unavailable configuration paths.")
                    if ui.ask("Configure paths now? y/n", "y").lower() != "y":
                        return 0
                    config = configure_paths(config_path, ui)
                provider = settings(config)["kind"]
                ui.screen("Main menu", f"Provider : {provider}\nLibrary  : {config['source']}\nCustoms  : {Path(config['workspace']) / 'custom-quests'}\nServer   : {config.get('server_quest_directory') or 'not configured (optional)'}\n\n  CREATE & REVIEW\n  1. Create quest from prompt\n  2. Inspect a BIN\n  6. Quest Fix diagnosis\n\n  SETUP\n  3. Index/decode corpus\n  4. Settings / account login\n\n  5. Exit\n\nType cls to clear and redraw. Sources remain read-only.")
                action = ui.number("Action", 1, 6, 5)
                if action == 5:
                    return 0
                if action == 6:
                    ui.screen("Quest Fix / diagnosis")
                    from .quest_fix import run
                    path = ui.ask("Quest BIN inside the configured corpus")
                    if path:
                        count = ui.number("Desired faint count (conditional analysis)", 1, 255, 3)
                        folder = Path(config["workspace"]) / "quest-fix" / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8])
                        ui.write(json.dumps(run(config, Path(path.strip('"')), folder, count), indent=2))
                        ui.write("Diagnosis only. Read the report before choosing an explicit candidate profile in the CLI.")
                elif action == 1:
                    ui.screen("Create / quest from prompt")
                    create_quest(config, ui)
                elif action == 2:
                    ui.screen("Inspect / quest BIN")
                    from .refrontier import read_summary
                    path = ui.ask("BIN path")
                    if path:
                        ui.write(json.dumps(read_summary(config, Path(path.strip('"'))), ensure_ascii=False, indent=2))
                elif action == 3:
                    ui.screen("Corpus / inventory and decoding")
                    ui.write("Indexing reads the corpus and updates only the local catalog/cache.")
                    ui.write("Completed records are saved incrementally. B/Esc pauses on Windows; Ctrl+C also preserves progress.")
                    ui.write("1. Inventory only\n2. Decode a bounded batch\n3. Analyze all quests (resumable)\n0. Back")
                    choice = ui.number("Index mode", 0, 3, 3)
                    if choice:
                        limit = ui.number("Maximum compressed files this batch", 1, 1000, 10) if choice == 2 else None
                        ui.write(json.dumps(scan(config, choice in (2, 3), limit, progress=ui.index_progress), indent=2))
                else:
                    settings_page(config_path, ui)
                ui.pause()
            except Back:
                if not config_path.exists() or ui.heading == "Main menu":
                    return 0
                ui.write("Returned to the parent menu. Saved files are preserved.")
            except (ValueError, OSError, IndexError, KeyError, sqlite3.Error, subprocess.SubprocessError) as exc:
                ui.write(f"Could not complete this action: {exc}")
                ui.write("Existing session files are preserved. No automatic model retry was made.")
                ui.pause()
    except (EOFError, KeyboardInterrupt):
        ui.write("\nSession ended. Saved work is preserved.")
        return 0
