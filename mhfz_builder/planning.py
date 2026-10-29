"""Provider-independent quest plans and verified reference context; never writes BINs."""
from __future__ import annotations
from contextlib import closing
from pathlib import Path
import sqlite3
from .binary import CATALOG, digest
from .config import contains
from .corpus import search


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string"}
TEXTS = {"type": "array", "items": TEXT}
RESEARCH_QUERY = obj({
    'kind': {'type': 'string', 'enum': ['corpus', 'items']},
    'monster_id': {'type': ['integer', 'null']},
    'map_id': {'type': ['integer', 'null']},
    'stage': {'type': ['integer', 'null']},
    'quest_id': {'type': ['integer', 'null']},
    'text': {'type': 'string'}})
INTENT_SCHEMA = obj({
    "monster_ids": {"type": "array", "items": {"type": "integer"}},
    "monster_match": {"type": "string", "enum": ["all", "any"], "description": "Use any when listed monsters are alternatives (choose one/or); use all when every listed monster must appear together."},
    "map_id": {"type": ["integer", "null"]},
    "spawn_stage": {"type": ["integer", "null"], "description": "Requested native stage ID from the map's stages catalog (not the visible area number). Null means no requested area. Never guess a stage."},
    "reference_quest_id": {"type": ["integer", "null"], "description": "Existing quest explicitly requested as a reference; keep null for a new quest ID, which belongs in requirements."},
    "requirements": TEXTS, "questions": TEXTS})
PLAN_SCHEMA = obj({
    'research_requests': {'type': 'array', 'items': RESEARCH_QUERY, 'description': 'Optional further read-only corpus or item-name searches needed before choosing a plan. Empty when evidence is sufficient or a user decision is needed. No paths, scripts or invented coordinates.'},
    "summary": TEXT,
    "base_reference_id": {"type": ["string", "null"]},
    "base_reason": TEXT,
    "changes": {"type": "array", "items": obj({
        "field": {"type": "string", "enum": ["quest_id", "title", "description", "time_minutes", "stat_table", "variants", "quest_flags", "main_objective", "sub_a", "sub_b", "finish_requirement", "map_package", "monster_spawns", "player_spawns", "rewards"]},
        "requested_value": TEXT,
        "evidence_reference_ids": TEXTS,
        "confidence": {"type": "string", "enum": ["requested", "supported", "experimental", "unknown"], "description": "requested means explicitly supplied by the user (for example a new title). supported requires cited binary evidence. experimental is a proposal requiring client proof."}})},
    "questions": TEXTS, "warnings": TEXTS,
    "requires_game_test": {"type": "boolean", "enum": [True]}})


def validate_shape(value, schema, path="root"):
    """Validate the exact small JSON Schema subset used by the two plan schemas."""
    types = schema["type"]
    types = types if isinstance(types, list) else [types]
    checks = {"object": lambda v: type(v) is dict, "array": lambda v: type(v) is list,
              "string": lambda v: type(v) is str, "integer": lambda v: type(v) is int,
              "boolean": lambda v: type(v) is bool, "null": lambda v: v is None}
    if not any(checks[t](value) for t in types):
        raise ValueError(f"Invalid type at {path}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"Invalid value at {path}")
    if type(value) is dict:
        if set(value) != set(schema["properties"]):
            raise ValueError(f"Unexpected or missing fields at {path}")
        for key, child in value.items():
            validate_shape(child, schema["properties"][key], f"{path}.{key}")
    elif type(value) is list:
        if len(value) > 100:
            raise ValueError(f"Too many items at {path}")
        for i, child in enumerate(value):
            validate_shape(child, schema["items"], f"{path}[{i}]")
    elif type(value) is str and len(value) > 12000:
        raise ValueError(f"Text too long at {path}")
    return value


def validate_intent(value):
    # Older saved intents required every listed monster together.
    value = {"monster_match": "all", "spawn_stage": None, **value}
    validate_shape(value, INTENT_SCHEMA)
    for mid in value["monster_ids"]:
        if str(mid) not in CATALOG["monsters"]:
            raise ValueError("Model returned an unknown monster ID")
    if value["map_id"] is not None and str(value["map_id"]) not in CATALOG["maps"]:
        raise ValueError("Model returned an unknown map ID")
    if value["reference_quest_id"] is not None and not 1 <= value["reference_quest_id"] <= 65535:
        raise ValueError("Model returned an invalid quest ID")
    if value['spawn_stage'] is not None:
        if value['map_id'] is None or value['spawn_stage'] not in {s['id'] for s in CATALOG['maps'][str(value['map_id'])]['stages']}:
            raise ValueError('Requested stage does not belong to the selected map catalog')
    return value


def coverage(config):
    path = Path(config["workspace"]) / "catalog.sqlite3"
    if not path.is_file():
        raise ValueError("No corpus index: run index first")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        counts = dict(db.execute("SELECT status,COUNT(*) FROM quests GROUP BY status"))
    if not counts:
        raise ValueError("Empty corpus index: run index first")
    return {"statuses": counts, "parsed": counts.get("parsed", 0),
            "complete": not any(counts.get(k, 0) for k in ("needs_decode", "error", "missing"))}


def references(config, intent, limit=12):
    intent = validate_intent(intent)
    # Search every parsed record before applying the quest-ID filter and output limit.
    count = coverage(config)["parsed"]
    rows = search(config, map_filter=str(intent["map_id"]) if intent["map_id"] is not None else None, limit=max(1, count))
    found = []
    by_hash = {}
    for row in rows:
        quest = row["quest"]
        if intent["reference_quest_id"] is not None and quest["quest_id"] != intent["reference_quest_id"]:
            continue
        if intent["monster_ids"]:
            requested = set(intent["monster_ids"])
            present = {m["id"] for m in quest["monsters"]}
            matches = bool(requested & present) if intent["monster_match"] == "any" else requested.issubset(present)
            if not matches:
                continue
        source = Path(row["source"])
        if not contains(Path(config["source"]), source) or not source.is_file():
            raise ValueError("Indexed reference is outside the configured corpus or missing; reindex")
        if digest(source.read_bytes()) != row["source_sha256"]:
            raise ValueError("Indexed reference changed; reindex before planning")
        sha = row["source_sha256"]
        if sha in by_hash:
            by_hash[sha]["source_variants"].append(str(source))
            continue
        if len(found) >= limit:
            continue
        item = {"reference_id": f"R{len(found)+1}", "source_variants": [str(source)],
                "source_sha256": sha, "quest": quest}
        by_hash[sha] = item
        found.append(item)
    return found


def research_references(config, intent, primary, limit=32):
    """Add complementary species and placement evidence from the entire parsed map.

    Missing multi-monster combinations must not hide single-species donor records.
    A custom-range quest remains a reference, never labelled an original/game-tested base.
    """
    intent = validate_intent(intent)
    if intent['map_id'] is None:
        return primary
    rows = search(config, map_filter=str(intent['map_id']), limit=max(1, coverage(config)['parsed']))
    wanted = set(intent['monster_ids'])
    stage = intent['spawn_stage']
    selected = list(primary)
    by_hash = {row['source_sha256']: row for row in selected}
    candidates = []
    # Favor complete rosters, then add distinct same-species/stage evidence.
    for species in sorted(wanted):
        matching = [row for row in rows if any(m['id'] == species for m in row['quest']['monsters'])]
        matching.sort(key=lambda row: (
            not any(m['id'] == species and m['stage'] == stage for m in row['quest']['monsters']),
            -len(wanted & {m['id'] for m in row['quest']['monsters']})))
        seen = set()
        for row in matching:
            if row['source_sha256'] not in seen:
                candidates.append(row); seen.add(row['source_sha256'])
            if len(seen) == 4:
                break
    if stage is not None:
        terrain = [row for row in rows if any(m['stage'] == stage for m in row['quest']['monsters'])]
        seen = set()
        for row in terrain:
            if row['source_sha256'] not in seen:
                candidates.append(row); seen.add(row['source_sha256'])
            if len(seen) == 4:
                break
    for row in candidates:
        sha = row['source_sha256']
        if sha in by_hash or len(selected) >= limit:
            continue
        path = Path(row['source'])
        if not contains(Path(config['source']), path) or digest(path.read_bytes()) != sha:
            raise ValueError('Research reference changed or is outside the configured corpus; reindex')
        item = {'reference_id': f'R{len(selected)+1}', 'source_variants': [str(path)], 'source_sha256': sha, 'quest': row['quest']}
        by_hash[sha] = item; selected.append(item)
    # Retain all physical roles of each selected hash, even outside the output limit.
    for row in rows:
        if row['source_sha256'] in by_hash:
            item = by_hash[row['source_sha256']]
            if row['source'] not in item['source_variants']:
                path = Path(row['source'])
                if not contains(Path(config['source']), path) or digest(path.read_bytes()) != row['source_sha256']:
                    raise ValueError('Research variant changed; reindex')
                item['source_variants'].append(row['source'])
    return selected


def public_references(rows):
    """Only structural summaries are sent; machine paths and full quest text stay local."""
    keys = ("quest_id", "title", "map", "map_name", "stat_table", "class", "variants", "quest_flags", "time_minutes", "player_stages", "return_stage", "objectives", "finish_raw", "monsters", "rewards", "limitations")
    return [{"reference_id": r["reference_id"], "source_sha256": r["source_sha256"],
             "quest": {k: r["quest"][k] for k in keys}} for r in rows]


def validate_plan(value, rows):
    if isinstance(value, dict):
        value.setdefault('research_requests', [])
    validate_shape(value, PLAN_SCHEMA)
    ids = {r["reference_id"] for r in rows}
    if value["base_reference_id"] is not None and value["base_reference_id"] not in ids:
        raise ValueError("Model selected a reference outside the supplied candidates")
    for change in value["changes"]:
        if not set(change["evidence_reference_ids"]).issubset(ids):
            raise ValueError("Model cited an unknown evidence reference")
        if change["confidence"] == "supported" and not change["evidence_reference_ids"]:
            raise ValueError("Supported changes must cite evidence")
    return value
