"""Structured graphical workflow sharing the terminal's authoring services."""
import json
import os
from pathlib import Path
import sys
from .wizard import Back, Console, configure_paths, create_quest, ensure_provider
from .config import load, configure_ai
from .providers import settings, local_api_key


def emit(kind, **values):
    print(json.dumps({"kind": kind, **values}, ensure_ascii=False), flush=True)


def receive():
    line = sys.stdin.readline()
    if not line:
        raise EOFError()
    answer = json.loads(line)
    if not isinstance(answer, dict) or not isinstance(answer.get("answer"), str):
        raise ValueError("Expected a JSON answer string.")
    return answer["answer"]


def prepare_references(config, ui):
    from .corpus import scan
    ui.screen("Prepare reference library")
    method = ui.number("Prepare references", 0, 2, 1)
    if not method:
        raise Back()
    result = scan(config, decode=method == 2, progress=ui.index_progress)
    ui.write(json.dumps(result, indent=2))


class GuiConsole(Console):
    def __init__(self):
        super().__init__(receive, self.output, interactive=False)
        self.key_reader = self.secret
        self.proposed_id = None

    def output(self, value):
        text = str(value)
        if text.startswith("Proposed quest ID: "):
            self.proposed_id = int(text.rsplit(" ", 1)[1])
        emit("output", text=text)

    def progress(self, text):
        emit('progress', text=text)

    def ask(self, label, default=None):
        control, extra = "text", {}
        if label.startswith("Blank preserves all flags"):
            from .authoring import FLAG_GROUPS
            control = "flags"
            extra["flags"] = [{"key": f"{group}:{1 << bit}", "name": value[0] if value else "Unknown / reserved",
                               "description": value[1] if value else "Unconfirmed. Preserve the native bit.",
                               "editable": bool(value) and group < 4}
                              for group, values in enumerate(FLAG_GROUPS, 1) for bit, value in enumerate(values)]
        elif label.startswith("Use this ID?"):
            control, extra = "quest_id", {"proposed_id": self.proposed_id}
        elif label.startswith("Monster Status table"):
            control = "stat_table"
        elif label.startswith("Source type:"):
            control, extra = "choice", {"options": [{"value": "server", "label": "Existing server quest folder"}, {"value": "project", "label": "Internal / project reference library"}]}
        emit("question", label=label, control=control, default=default, multiline=False, **extra)
        value = receive().strip()
        if value.lower() in ("b", "back", "indietro") or value == "\x1b":
            raise Back()
        return value or (str(default) if default is not None else "")

    def number(self, label, low, high, default=None):
        options = {
            "Position": [{"value": "1", "label": "Use a compatible native spawn"}, {"value": "2", "label": "Choose an area using corpus positions"}],
            "Rewards": [{"value": "1", "label": "Keep native monster rewards"}, {"value": "2", "label": "Custom rewards from the quest description"}],
            "Login method": [{"value": "1", "label": "Sign in through browser"}, {"value": "2", "label": "Use a device code"}, {"value": "0", "label": "Back to AI selection"}],
            "Next action": [{"value": "1", "label": "Export laboratory BINs"}, {"value": "2", "label": "Revise the proposal"}, {"value": "0", "label": "Save without export"}],
            "Prepare references": [{"value": "1", "label": "Index readable quest files"}, {"value": "2", "label": "Decode copies with ReFrontier and index all"}, {"value": "0", "label": "Back"}],
        }.get(label, [])
        while True:
            emit("question", label=label, control="choice" if options else "number", options=options,
                 minimum=low, maximum=high, default=default, multiline=False)
            value = receive().strip()
            if value.lower() in ("b", "back"):
                raise Back()
            try:
                number = int(value or str(default))
                if low <= number <= high:
                    return number
            except ValueError:
                pass
            self.write(f"Choose a value between {low} and {high}.")

    def secret(self, label):
        emit("question", label=label, control="secret", multiline=False, secret=True)
        return receive()

    def screen(self, heading, content=None):
        self.heading, self.content = heading, content
        emit("screen", title=heading, text=content or "")

    def description(self, previous=""):
        emit("question", label="Describe the quest", control="description", multiline=True, previous=previous)
        value = receive().strip()
        if value.lower() in ("b", "back"):
            raise Back()
        return value or previous

    def map_picker(self, config):
        from .map_browser import rows
        items = [{"id": item["id"], "name": item["name"], "references": item["references"],
                  "overviews": [{**record, "path": str(record["path"])} for record in item["overviews"]]}
                 for item in rows(config)]
        while True:
            emit("question", label="Choose the map", control="map", maps=items, multiline=False)
            value = receive().strip()
            if value.lower() in ("b", "back"):
                raise Back()
            if not value:
                return ""
            match = next((item for item in items if item["id"] == value), None)
            if match:
                return f" Use the native {match['name']} map package (map ID {value}); preserve its zones and transitions."
            self.write("Choose a map from the catalog.")


def run(config_path):
    ui = GuiConsole()
    reuse_codex = os.environ.get("MHFZ_EDITOR_CODEX_READY") == "1"
    config_path = Path(config_path)
    try:
        try:
            config = load(config_path)
        except (ValueError, OSError):
            ui.screen("First setup / quest library")
            config = configure_paths(config_path, ui)
        while True:
            try:
                provider = settings(config)
                if reuse_codex and provider["kind"] == "codex":
                    choice = {"kind": "codex", "model": provider.get("model")}
                    ui.write("Reusing Codex sign-in for this editor session.")
                else:
                    ui.screen("AI account")
                    emit("question", label="Choose your AI", control="provider", provider=provider["kind"],
                         model=provider.get("model"), multiline=False)
                    choice = json.loads(receive())
                if not isinstance(choice, dict) or choice.get("kind") not in ("codex", "gemini", "openai"):
                    raise ValueError("Choose Codex, Gemini or OpenAI API.")
                if choice.get("action") == "paths":
                    config = configure_paths(config_path, ui)
                    continue
                if choice.get("action") == "index":
                    prepare_references(config, ui)
                    emit("question", label="Library analysis complete", control="choice", multiline=False,
                         options=[{"value": "back", "label": "Back to AI selection"}])
                    receive()
                    continue
                if choice.get("action") == "quest_fix":
                    from .quest_fix import run as diagnose
                    from uuid import uuid4
                    path = ui.ask("Quest BIN path")
                    count = ui.number("Desired faint count", 1, 255, 3)
                    folder = Path(config["workspace"]) / "quest-fix" / uuid4().hex
                    ui.write(json.dumps(diagnose(config, Path(path.strip('"')), folder, count), indent=2))
                    emit("question", label="Diagnosis saved", control="choice", multiline=False,
                         options=[{"value": "back", "label": "Back to AI selection"}])
                    receive()
                    continue
                model = choice.get("model") or None
                if choice["kind"] != provider["kind"] or model != provider.get("model"):
                    configure_ai(config_path, model, provider=choice["kind"],
                                 executable=provider.get("executable") if choice["kind"] == "codex" else None)
                    config = load(config_path)
                if not ensure_provider(config, ui):
                    reuse_codex = False
                    continue
                reuse_codex = settings(config)["kind"] == "codex"
                if reuse_codex:
                    emit("codex-ready")
                from .planning import coverage
                if not coverage(config)["parsed"]:
                    prepare_references(config, ui)
                with local_api_key(config, settings(config)["kind"] != "codex", ui.secret):
                    ui.screen("Create quest")
                    create_quest(config, ui)
                emit("complete", text="Session saved. Choose Create another quest or return to the editor.")
                emit("question", label="Next step", control="choice", multiline=False,
                     options=[{"value": "again", "label": "Create another quest"}, {"value": "exit", "label": "Finish"}])
                if receive() != "again":
                    return 0
            except Back:
                reuse_codex = False
                ui.write("Returned to AI selection. Saved files are preserved.")
            except (ValueError, OSError) as exc:
                reuse_codex = False
                emit("error", text=str(exc))
    except (EOFError, KeyboardInterrupt):
        return 0
    except (ValueError, OSError) as exc:
        emit("error", text=str(exc))
        return 1
