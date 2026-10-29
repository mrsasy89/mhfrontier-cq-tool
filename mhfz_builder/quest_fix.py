"""Evidence-led diagnosis and explicitly profiled faint candidates. Never installs."""
from pathlib import Path
import json
import struct
from .binary import digest, inspect_bytes
from .build_service import all_variants, check_source, raw_bytes
from .config import contains


def diagnose_summary(summary, desired_faints=3):
    if type(desired_faints) is not int or not 1 <= desired_faints <= 255:
        raise ValueError("Desired faints must be between 1 and 255")
    reward, value = summary["reward_main_z"], summary["failure_value_raw32"]
    facts = {key: summary[key] for key in ("quest_id", "sha256", "reward_main_z", "failure_value_raw32", "quest_type_raw", "quest_flags", "player_stages", "objectives", "finish_raw")}
    facts["g_rank_flag_present"] = bool(summary["quest_flags"][0] & 8)
    facts["interception_diva_bit_present"] = bool(summary["quest_flags"][2] & 32)
    hypotheses = []
    if reward and value:
        count = (reward + value - 1) // value
        hypotheses.append({"kind": "hr_reward_penalty", "conditional_faints": count,
                           "matches_requested": count == desired_faints,
                           "suggested_penalty_u32": (reward + desired_faints - 1) // desired_faints,
                           "display_wrap_example": (reward // value) % 256,
                           "status": "Conditional arithmetic only; client branch/display code has not been traced"})
    else:
        hypotheses.append({"kind": "hr_reward_penalty", "status": "Zero reward/penalty: no finite faint-count inference"})
    hypotheses.append({"kind": "g_direct_carts", "conditional_faints": value,
                       "matches_requested": value == desired_faints,
                       "status": "Requires a matching direct-cart client/quest profile; class/flag alone is not proof"})
    reward_warnings = [{"table": r["table"], "configured_rate_total": r["rate_total"]}
                       for r in summary["rewards"] if r["rows"] and r["rate_total"] != 100]
    return {"facts": facts, "hypotheses": hypotheses, "reward_table_warnings": reward_warnings,
            "npc_checks": ["Player capacity does not establish NPC eligibility", "Compare explicit requirements and effective server card against a known-working quest",
                           "Preserve intentional Diva/Interception sequences; never clear reserved bytes automatically",
                           "Compare the original native base and test companions separately from spawn sequencing"],
            "required_client_checks": ["loading", "player/monster spawn", "NPC companions", "combat and area changes", "faint display and failure", "objectives and rewards"],
            "runtime_verified": False}


def run(config, source, destination, desired_faints=3, mode=None):
    """Always save a report; export candidates only with an explicit semantics profile."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not contains(Path(config["workspace"]), destination) or contains(Path(config["source"]), destination):
        raise ValueError("Quest Fix output must be inside the workspace, outside the corpus")
    if destination.exists():
        raise ValueError("Quest Fix output directory already exists")
    if mode not in (None, "hr-penalty", "g-carts"):
        raise ValueError("Choose an explicit hr-penalty or g-carts profile")
    sources = all_variants(config, source)
    prepared = []
    for row in sources:
        path = check_source(config, row)
        raw = raw_bytes(config, path)
        summary = inspect_bytes(raw)
        report = diagnose_summary(summary, desired_faints)
        candidate = None
        if mode:
            if summary["quest_id"] == 65005:
                raise ValueError("Quest 65005 is protected from candidate edits")
            if struct.unpack_from("<I", raw)[0] != 192:
                raise ValueError("Candidate writer only supports body 0xC0")
            is_g = bool(summary["quest_flags"][0] & 8)
            if is_g != (mode == "g-carts"):
                raise ValueError("Requested profile conflicts with the G-rank marker; review the reference first")
            reward, previous = summary["reward_main_z"], summary["failure_value_raw32"]
            if mode == "hr-penalty":
                if not reward or reward < desired_faints:
                    raise ValueError("Reward cannot represent the requested HR faint count")
                value = previous if previous and (reward + previous - 1) // previous == desired_faints else (reward + desired_faints - 1) // desired_faints
                if (reward + value - 1) // value != desired_faints:
                    raise ValueError("Integer penalty cannot represent the requested HR faint count")
            else:
                value = desired_faints
            data = bytearray(raw); struct.pack_into("<I", data, 212, value)
            candidate = bytes(data)
            inspect_bytes(candidate)
            report["candidate"] = {"profile": mode, "before_u32": previous, "after_u32": value,
                                   "output_raw_sha256": digest(candidate),
                                   "changed_offsets": [i for i, (a, b) in enumerate(zip(raw, candidate)) if a != b],
                                   "runtime_verified": False}
        prepared.append((row, report, candidate))
    for row, _, _ in prepared:
        check_source(config, row)
    destination.mkdir(parents=True, exist_ok=False)
    result = {"schema_version": 1, "status": "diagnosed" if not mode else "candidate_unverified",
              "mode": mode, "desired_faints": desired_faints, "variants": [], "installed": False,
              "limitations": ["Partial structural parser; no complete map/NPC validator", "No base transplant, unknown-field repair or reward normalization", "No database or server card read performed"]}
    for row, report, candidate in prepared:
        report["source"] = row
        if candidate is not None:
            original = check_source(config, row).read_bytes()
            backups = Path(config["workspace"]) / "source-backups"
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / (row["sha256"] + ".bin")
            if not backup.exists():
                with backup.open("xb") as stream:
                    stream.write(original)
            if digest(backup.read_bytes()) != row["sha256"]:
                raise ValueError("Original backup hash mismatch")
            output = destination / f"{report['facts']['quest_id']:05d}{row['role']}.bin"
            with output.open("xb") as stream:
                stream.write(candidate)
            if digest(output.read_bytes()) != digest(candidate):
                raise ValueError("Candidate output hash mismatch")
            report["candidate"].update(path=str(output), source_backup=str(backup))
        result["variants"].append(report)
    for row, _, _ in prepared:
        check_source(config, row)
    with (destination / "quest-fix-report.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return {"saved": str(destination / "quest-fix-report.json"), "status": result["status"], "variants": len(result["variants"]), "installed": False}
