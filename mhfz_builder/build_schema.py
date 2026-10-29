"""Typed compiler contract. No offsets or executable instructions are accepted."""
from .planning import obj, TEXTS, validate_shape

TEXT_NAMES = ("title", "main_objective", "sub_a_objective", "sub_b_objective", "clear_reqs", "fail_reqs", "contractor", "description")
SLOTS = ("main", "sub_a", "sub_b")
KINDS = {"Nothing": 0, "Hunt": 1, "Capture": 257, "Slay": 513, "Damage": 32772, "Slay_or_Damage": 98308, "Slay_All": 262144, "Slay_Total": 131072}
NULL_INT = {"type": ["integer", "null"]}
EDITS_SCHEMA = obj({
    "time_minutes": {"type": ["integer", "null"]},
    "stat_table": NULL_INT,
    "finish_raw": NULL_INT,
    "variants": {"type": ["array", "null"], "items": {"type": "integer"}},
    "quest_flags": {"type": ["array", "null"], "items": {"type": "integer"}},
    "monster_spawns": {"type": ["array", "null"], "description": "Null preserves every native spawn. Otherwise the complete ordered spawn list, copying verified records from supplied references. Position references copy stage, orientation and XYZ only; different-species placement is experimental terrain evidence.", "items": obj({
        "reference_id": {"type": "string"}, "spawn_index": {"type": "integer"},
        "position_reference_id": {"type": ["string", "null"]}, "position_spawn_index": NULL_INT})},
    "rewards": {"type": ["array", "null"], "description": "Null preserves rewards. Otherwise replace only the named table IDs; other tables and native headers are preserved. IDs 1/2/3 are Main/Sub A/Sub B in the editor profile.", "items": obj({
        "table": {"type": "integer"}, "rows": {"type": "array", "items": obj({
            "item": {"type": "integer"}, "amount": {"type": "integer"}, "rate": {"type": "integer"}})}})},
    "texts": obj({name: {"type": ["string", "null"]} for name in TEXT_NAMES}),
    "objectives": {"type": "array", "items": obj({
        "slot": {"type": "string", "enum": list(SLOTS)},
        "kind": {"type": "string", "enum": list(KINDS)},
        "target": {"type": "integer"}, "quantity_raw": {"type": "integer"}})}})
COMPILE_SCHEMA = obj({"base_reference_id": {"type": "string"}, "quest_id": {"type": "integer"},
                      "edits": EDITS_SCHEMA,
                      "unresolved": {**TEXTS, "description": "Only missing user choices needed to encode values, such as an unspecified threshold. Do not include future gameplay tests or partial internal validation."},
                      "unsupported": {**TEXTS, "description": "Requested actual edits outside this writer capability; preservation is supported."},
                      "warnings": {**TEXTS, "description": "Nonblocking review, runtime-test and partial-validation caveats belong here."}})


def empty_edits():
    return {"time_minutes": None, "stat_table": None, "finish_raw": None, "variants": None,
            "quest_flags": None, "monster_spawns": None, "rewards": None,
            "texts": {name: None for name in TEXT_NAMES}, "objectives": []}


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def validate_edits(edits):
    if not isinstance(edits, dict):
        raise ValueError("Invalid edits object")
    # Preserve compatibility with earlier saved specifications.
    for key in ("monster_spawns", "rewards"):
        edits.setdefault(key, None)
    validate_shape(edits, EDITS_SCHEMA)
    if edits["monster_spawns"] is not None:
        if not 1 <= len(edits["monster_spawns"]) <= 5:
            raise ValueError("A custom boss roster requires one to five spawn records")
        for row in edits["monster_spawns"]:
            integer(row["spawn_index"], 0, 63, "spawn_index")
            if (row["position_reference_id"] is None) != (row["position_spawn_index"] is None):
                raise ValueError("Position evidence requires both a reference and a spawn index")
            if row["position_spawn_index"] is not None:
                integer(row["position_spawn_index"], 0, 63, "position_spawn_index")
    if edits["rewards"] is not None:
        from .items import ITEMS
        tables = set()
        for table in edits["rewards"]:
            integer(table["table"], 0, 254, "reward table")
            if table["table"] in tables:
                raise ValueError("Reward table specified more than once")
            tables.add(table["table"])
            if not 1 <= len(table["rows"]) <= 100:
                raise ValueError("A reward table requires one to 100 rows")
            for row in table["rows"]:
                integer(row["item"], 1, 65534, "reward item")
                if str(row["item"]) not in ITEMS:
                    raise ValueError("Reward item is not in the supplied item catalog")
                integer(row["amount"], 1, 65535, "reward amount")
                integer(row["rate"], 1, 65534, "reward weight")
    for name, high, low in (("time_minutes", 1440, 1), ("stat_table", 65535, 0), ("finish_raw", 255, 0)):
        if edits[name] is not None:
            integer(edits[name], low, high, name)
    for name, count in (("variants", 5), ("quest_flags", 4)):
        if edits[name] is not None:
            if len(edits[name]) != count:
                raise ValueError(f"{name} requires exactly {count} values")
            for value in edits[name]:
                integer(value, 0, 255, name)
    slots = set()
    for objective in edits["objectives"]:
        if objective["slot"] in slots:
            raise ValueError("Objective slot specified more than once")
        slots.add(objective["slot"])
        integer(objective["target"], 0, 255, "objective target")
        integer(objective["quantity_raw"], 0, 65535, "objective quantity_raw")
        if objective["kind"] == "Nothing":
            if objective["target"] or objective["quantity_raw"]:
                raise ValueError("Nothing objectives require zero target and quantity")
        elif objective["kind"] in ("Slay_All", "Slay_Total"):
            if objective["target"] or not objective["quantity_raw"]:
                raise ValueError("Aggregate slay objectives require target zero and a nonzero quantity")
            if objective['kind'] == 'Slay_All' and objective['quantity_raw'] != 1:
                raise ValueError('The supported native Slay_All profile requires quantity_raw=1; the roster defines which bosses are present')
        elif not objective["target"] or not objective["quantity_raw"]:
            raise ValueError("Monster objectives require a nonzero target and quantity")
    return edits
