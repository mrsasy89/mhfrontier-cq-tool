"""Conservative BIN patch engine: preserve opaque data and all original offsets."""
from __future__ import annotations
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from collections import Counter
import struct
from .binary import Reader, digest, inspect_bytes
from .build_schema import validate_edits, integer, TEXT_NAMES, SLOTS, KINDS


def damage_threshold(hp, percent, rounding):
    integer(hp, 1, 4294967295, "reference HP")
    try:
        percentage = Decimal(str(percent))
    except Exception:
        raise ValueError("Invalid HP percentage") from None
    if not percentage.is_finite() or not 0 < percentage <= 100:
        raise ValueError("HP percentage must be greater than zero and at most 100")
    requested = Decimal(hp) * percentage / 100
    units = requested / 100
    if rounding == "ceil":
        quantity = int(units.to_integral_value(rounding=ROUND_CEILING))
    elif rounding == "floor":
        quantity = int(units.to_integral_value(rounding=ROUND_FLOOR))
    elif rounding == "exact" and units == units.to_integral_value():
        quantity = int(units)
    else:
        raise ValueError("Threshold is not exactly representable; select ceil or floor explicitly")
    integer(quantity, 1, 65535, "Damage quantity_raw")
    points = quantity * 100
    return {"reference_hp_supplied": hp, "requested_percent": str(percentage),
            "requested_damage": str(requested), "rounding": rounding,
            "quantity_raw": quantity, "damage_points": points,
            "effective_percent": str(Decimal(points) * 100 / hp), "exceeds_reference_hp": points > hp,
            "note": "Arithmetic only: does not verify the HP table or change monster HP"}


def patch_bytes(source: bytes, quest_id: int, edits: dict, evidence=None):
    integer(quest_id, 1, 65535, "quest_id")
    validate_edits(edits)
    before = inspect_bytes(source)
    reader = Reader(source)
    body = reader.u32(0)
    if body != 192:
        raise ValueError("Writer only supports the verified raw quest layout with body at 0xC0")
    original_table = reader.u32(body + 40)
    if original_table < body + 205:
        raise ValueError("Text table overlaps fixed quest metadata; unsupported layout")
    reader.read("<32s", original_table)
    out = bytearray(source)
    ranges = []
    package_warnings = []
    expected_monsters = before['monsters']
    if edits['monster_spawns'] is not None:
        from .packages import custom_spawns, append_spawns
        records, notes = custom_spawns(source, edits['monster_spawns'], evidence or {})
        append_spawns(out, source, records)
        ranges.append((24, 28))
        expected_monsters = inspect_bytes(bytes(out))['monsters']
        package_warnings.extend(notes)
    expected_rewards = before['rewards']
    if edits['rewards'] is not None:
        from .packages import append_rewards
        package_warnings.extend(append_rewards(out, source, edits['rewards']))
        ranges.append((12, 16))
        expected_rewards = inspect_bytes(bytes(out))['rewards']

    def patch(offset, fmt, *values):
        size = struct.calcsize(fmt)
        reader.read(fmt, offset)
        if not (68 <= offset < 76 or body <= offset and offset + size <= body + 205):
            raise ValueError("Write outside the supported metadata ranges")
        struct.pack_into(fmt, out, offset, *values)
        ranges.append((offset, offset + size))

    patch(body + 46, "<H", quest_id)
    if edits['monster_spawns'] is not None and [m['id'] for m in expected_monsters] != [m['id'] for m in before['monsters']]:
        for index in range(5):
            patch(body + 185 + index, '<B', expected_monsters[index]['id'] if index < len(expected_monsters) else 0)
    if edits["time_minutes"] is not None:
        patch(body + 32, "<I", edits["time_minutes"] * 1800)
    if edits["stat_table"] is not None:
        patch(72, "<I", edits["stat_table"])
    if edits["finish_raw"] is not None:
        patch(body + 72, "<B", edits["finish_raw"])
    if edits["variants"] is not None:
        for offset, value in zip((145, 146, 182, 183, 184), edits["variants"]):
            patch(body + offset, "<B", value)
    if edits["quest_flags"] is not None:
        for i, value in enumerate(edits["quest_flags"]):
            patch(body + 151 + i, "<B", value)
    boss_ids = {row["id"] for row in expected_monsters}
    for objective in edits["objectives"]:
        slot = SLOTS.index(objective["slot"])
        if objective["kind"] not in ("Nothing", "Slay_All", "Slay_Total") and objective["target"] not in boss_ids:
            raise ValueError("Edited objectives must target a large monster already present in the base")
        label = ("main_objective", "sub_a_objective", "sub_b_objective")[slot]
        old = before["objectives"][slot]
        changed = (old["type"], old["target"], old["quantity_raw"]) != (KINDS[objective["kind"]], objective["target"], objective["quantity_raw"])
        if changed and edits["texts"][label] is None:
            raise ValueError(f"An objective change requires explicit matching text: {label}")
        unknown = old["unknown"] if objective["kind"] != "Nothing" else 0
        patch(body + 48 + slot * 8, "<IBBH", KINDS[objective["kind"]], objective["target"], unknown, objective["quantity_raw"])
    # Preserve native duplication, but never introduce additional duplicate objectives.
    if edits["objectives"]:
        old_counts = Counter((r["type"], r["target"], r["quantity_raw"]) for r in before["objectives"] if r["type"])
        active = Counter()
        for i in range(3):
            kind, target, _, quantity = struct.unpack_from("<IBBH", out, body + 48 + 8*i)
            if kind:
                active[(kind, target, quantity)] += 1
        if any(count > 1 and count > old_counts[key] for key, count in active.items()):
            raise ValueError("New duplicate active objectives require investigation; not generated automatically")
    replacements = []
    for i, name in enumerate(TEXT_NAMES):
        value = edits["texts"][name]
        if value is None or value == before["texts"][i]:
            continue
        if "\0" in value:
            raise ValueError("Quest text cannot contain NUL characters")
        try:
            encoded = value.encode("cp932", errors="strict")
        except UnicodeEncodeError:
            raise ValueError(f"Text is not representable in CP932: {name}") from None
        if len(encoded) > 65535 or encoded.decode("cp932") != value:
            raise ValueError(f"Text exceeds the size limit or does not round-trip through CP932: {name}")
        replacements.append((i, encoded))
    if replacements:
        out.extend(bytes((-len(out)) % 4))
        table = len(out)
        out.extend(source[original_table:original_table+32])
        for i, encoded in replacements:
            pointer = len(out)
            if pointer + len(encoded) + 10 > 4294967295:
                raise ValueError("Quest file exceeds the pointer range")
            struct.pack_into("<I", out, table + 4*i, pointer)
            out.extend(encoded + b"\0")
        patch(body + 40, "<I", table)
        # CQ Tool's ARCA footer describes this appended extension, not client gameplay.
        out.extend(struct.pack("<I4sB", table, b"ARCA", 0))
    after = inspect_bytes(bytes(out))
    edited_slots = {SLOTS.index(row["slot"]): row for row in edits["objectives"]}
    for slot, current in enumerate(after["objectives"]):
        if slot not in edited_slots:
            if current != before["objectives"][slot]:
                raise ValueError("An unedited objective changed")
        else:
            row = edited_slots[slot]
            if (current["type"], current["target"], current["quantity_raw"]) != (KINDS[row["kind"]], row["target"], row["quantity_raw"]):
                raise ValueError("Objective read-back verification failed")
    expected = dict(before)
    expected.update(quest_id=quest_id)
    for key in ("time_minutes", "stat_table", "variants", "quest_flags", "finish_raw"):
        if edits[key] is not None:
            expected[key] = edits[key]
    for i, name in enumerate(TEXT_NAMES):
        wanted = edits["texts"][name]
        if wanted is not None and after["texts"][i] != wanted:
            raise ValueError("Text read-back verification failed")
    for key in ("quest_id", "time_minutes", "stat_table", "variants", "quest_flags", "finish_raw"):
        if after[key] != expected[key]:
            raise ValueError(f"Field read-back verification failed: {key}")
    if after['monsters'] != expected_monsters or after['rewards'] != expected_rewards:
        raise ValueError('Spawn/reward package read-back verification failed')
    # A removed boss may not leave a stale native objective behind.
    if edits['monster_spawns'] is not None:
        for objective in after['objectives']:
            if objective['type'] in (1, 257, 513, 32772, 98308) and objective['target'] not in boss_ids:
                raise ValueError('An objective still targets a monster removed from the roster')
    for key in ("map", "return_stage", "player_stages", "class", "size_percent", "size_range", "locale_raw", "return_flags_raw", "failure_value_raw32"):
        if after[key] != before[key]:
            raise ValueError(f"Protected semantic section changed: {key}")
    allowed = set()
    for start, end in ranges:
        allowed.update(range(start, end))
    changed = [i for i, (a, b) in enumerate(zip(source, out)) if a != b]
    if any(i not in allowed for i in changed):
        raise ValueError("Unrequested original bytes changed")
    return bytes(out), {"input_raw_sha256": digest(source), "output_raw_sha256": digest(bytes(out)),
                        "original_bytes": len(source), "output_bytes": len(out),
                        "changed_original_offsets": changed, "appended_bytes": len(out)-len(source),
                        "opaque_bytes_preserved": True, "runtime_verified": False,
                        "warnings": package_warnings,
                        "summary": after}
