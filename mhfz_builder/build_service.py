"""Local build preparation/export. Corpus files are never opened for writing."""
from __future__ import annotations
import json
from pathlib import Path
import re
from .binary import digest, inspect_bytes, packed, CATALOG
from .build_schema import COMPILE_SCHEMA, validate_edits, integer, empty_edits
from .config import contains
from .planning import validate_shape, validate_plan, public_references
from .refrontier import unpack
from .writer import patch_bytes

ROLE = re.compile(r"^(\d+)([A-Za-z][0-9]+)\.bin$", re.IGNORECASE)


def raw_bytes(config, source):
    data = source.read_bytes()
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Source exceeds the supported quest size limit")
    if not packed(data):
        return data
    report = unpack(config, source)
    if len(report["quest_files"]) != 1:
        raise ValueError("Compressed input did not yield exactly one quest BIN")
    raw = Path(report["quest_files"][0]).read_bytes()
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError("Decoded source exceeds the supported quest size limit")
    return raw


def source_record(config, path):
    path = Path(path).resolve()
    if not contains(Path(config["source"]), path) or not path.is_file():
        raise ValueError("Build references must be files inside the configured corpus")
    match = ROLE.fullmatch(path.name)
    if not match:
        raise ValueError("Unsupported variant filename; expected a quest ID followed by a role such as d0/n0")
    return {"path": str(path), "sha256": digest(path.read_bytes()), "role": match.group(2).lower()}


def check_source(config, row):
    if not isinstance(row, dict) or set(row) != {"path", "sha256", "role"}:
        raise ValueError("Invalid source record")
    current = source_record(config, row["path"])
    if current != row:
        raise ValueError("Source hash, path or variant changed; prepare a new build specification")
    return Path(row["path"])


def all_variants(config, selected):
    selected = Path(selected).resolve()
    summary = inspect_bytes(raw_bytes(config, selected))
    quest_id = summary["quest_id"]
    rows = []
    seen = {}
    for path in sorted(Path(config["source"]).rglob("*")):
        match = ROLE.fullmatch(path.name)
        if not match or int(match.group(1)) != quest_id or not path.is_file() or path.is_symlink():
            continue
        row = source_record(config, path)
        if row["role"] in seen:
            raise ValueError("Ambiguous duplicate variant roles in corpus; separate the source corpus")
        seen[row["role"]] = row
        rows.append(row)
        if len(rows) > 16:
            raise ValueError("More than 16 variants found; this build profile does not support that set")
    if str(selected) not in {r["path"] for r in rows}:
        raise ValueError("Reference filename ID disagrees with its internal quest ID")
    return rows


def prepare_spec(config, source, quest_id):
    integer(quest_id, 1, 65535, "quest_id")
    rows = all_variants(config, source)
    return {"schema_version": 1, "kind": "mhfz_build_spec", "base_reference_id": "manual",
            "quest_id": quest_id, "sources": rows, "edits": empty_edits(),
            "unresolved": [], "unsupported": [], "provenance": {"mode": "manual", "model_calls": []}}


def verify_sources(config, rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 16:
        raise ValueError("A build requires between 1 and 16 source variants")
    roles = set()
    ids = set()
    for row in rows:
        path = check_source(config, row)
        if row["role"] in roles:
            raise ValueError("Duplicate source variant roles")
        roles.add(row["role"])
        ids.add(inspect_bytes(raw_bytes(config, path))["quest_id"])
    if len(ids) != 1:
        raise ValueError("Build variants must share one internal base quest ID")
    return ids.pop()


def compile_project(config, project, project_sha256, quest_id, notes, client, choices=None):
    integer(quest_id, 1, 65535, "quest_id")
    if not isinstance(notes, str) or len(notes) > 12000:
        raise ValueError("Compiler notes exceed the size limit")
    if not isinstance(project, dict):
        raise ValueError("Invalid quest plan project")
    rows = project.get("references", [])
    proposal = validate_plan(project.get("plan"), rows)
    base = next((r for r in rows if r["reference_id"] == proposal["base_reference_id"]), None)
    if base is None or not base.get("source_variants"):
        raise ValueError("The reviewed plan has no usable base reference")
    for path in base["source_variants"]:
        row = source_record(config, path)
        if row["sha256"] != base["source_sha256"]:
            raise ValueError("Plan reference changed; regenerate the plan")
    sources = all_variants(config, base["source_variants"][0])
    verify_sources(config, sources)
    evidence_rows = []
    for reference in rows:
        for path in reference['source_variants']:
            current = source_record(config, path)
            if current['sha256'] != reference['source_sha256']:
                raise ValueError('Plan evidence changed; regenerate the plan')
        evidence_rows.append({'reference_id': reference['reference_id'], 'source': source_record(config, reference['source_variants'][0])})
    from .items import mentioned_items, ITEM_DATA
    data = {"prompt": project.get("prompt", ""), "plan": proposal, "notes": notes,
            "required_quest_id": quest_id, "required_base_reference_id": base["reference_id"],
            "references": public_references(rows),
            "authoring_choices": choices,
            "items": mentioned_items(project.get('prompt', '') + '\n' + notes),
            "item_catalog_sha256": ITEM_DATA['source_sha256'],
            "map_stages": CATALOG['maps'][str(base['quest']['map'])]['stages'],
            "compiler_rules": [
                "Compile every requested change into supported typed fields. Never silently drop a requested unsupported change.",
                "The target quest ID is fixed by the host. Null fields mean preserve, and an empty objectives list means preserve all objectives.",
                "Preserve the complete native map package. monster_spawns may copy complete records from supplied same-map references, using zero-based spawn_index. To move a monster, copy position evidence from a same-map record in the requested stage; same-species evidence is preferred, other species provide experimental terrain placement only. Never invent XYZ. Null preserves the native roster.",
                "Custom rewards replace named tables using catalog item IDs, quantities and configured weights; preserve unspecified tables. Do not invent missing quantities or weights: ask using unresolved. Existing native values may be retained when explicitly requested. Never normalize configured totals silently.",
                "Each changed objective must include explicit matching text. Damage quantity_raw equals damage points divided by 100; require exact units or explicit user rounding.",
                "Use notes to resolve missing user decisions. Do not invent thresholds, HP, variants or flag meanings. Keep only missing encoding parameters in unresolved; place runtime/review/partial-validation caveats in warnings. Those caveats do not block a laboratory BIN export.",
                "Supported objective kinds: Nothing, Hunt, Capture, Slay, Damage, Slay_or_Damage, targeting the final roster. Slay_All and Slay_Total are aggregate kinds with target=0; the supported native Slay_All encoding uses quantity_raw=1 (not the number of monsters). Slay_Total uses an explicit total. Use only when the user requests all/total kills and explain the completion mode. Do not introduce duplicate objectives. If a requested Main and Sub duplicate each other, ask how to express the intended completion instead of silently dropping either.",
                "finish_raw must match native completion evidence; its meaning is not inferred from a label. Preserve opaque bits and distinguish HC flag requests from proof of HC capability.",
                "Preserving existing unsupported fields is allowed: use null/empty rather than marking preservation unsupported."]}
    repair_log = []
    for attempt in range(3):
        progress = config.get('_progress', lambda text: None)
        progress('Waiting for Codex: compiling typed edits' if not attempt else 'Waiting for Codex: correcting edits using binary validation feedback')
        value = client.request("quest_build_spec", COMPILE_SCHEMA, dict(data, validation_feedback=repair_log))
        verify_sources(config, sources)
        try:
            if isinstance(value, dict) and isinstance(value.get('edits'), dict):
                validate_edits(value['edits'])
            validate_shape(value, COMPILE_SCHEMA)
            if value["quest_id"] != quest_id or value["base_reference_id"] != base["reference_id"]:
                raise ValueError("Compiler changed the required quest ID or base reference")
            spec = {"schema_version": 1, "kind": "mhfz_build_spec", **value, "sources": sources,
                    "provenance": {"spawn_sources": evidence_rows}}
            if choices is not None:
                from .authoring import enforce_preferences
                enforce_preferences(config, spec, choices)
            evidence = resolve_evidence(config, spec)
            if not value["unresolved"] and not value["unsupported"]:
                progress('Validating every proposed BIN variant in memory')
                for row in sources:
                    _, proof = patch_bytes(raw_bytes(config, Path(row["path"])), quest_id, value["edits"], evidence)
                    verify_intent(project.get('intent'), proof['summary'], choices)
                    value['warnings'].extend(note for note in proof['warnings'] if note not in value['warnings'])
            break
        except ValueError as exc:
            repair_log.append({'attempt': attempt + 1, 'error': str(exc), 'rejected_edits': value.get('edits') if isinstance(value, dict) else None})
            if attempt == 2:
                raise ValueError(f'Compiler validation failed after three proposals: {exc}') from exc
    warnings = value.pop("warnings")
    return {"schema_version": 1, "kind": "mhfz_build_spec", **value, "sources": sources,
            "provenance": {"mode": "model_compiler", "project_sha256": project_sha256,
                           "spawn_sources": evidence_rows,
                           "validation_repairs": repair_log,
                           "requested_intent": project.get('intent'), "authoring_choices": choices,
                           "notes": notes, "warnings": warnings, "model_calls": client.calls}}


def verify_intent(intent, summary, choices):
    """Do not accept a typed result that silently drops species, map or requested area."""
    if not intent:
        return
    if intent['map_id'] is not None and summary['map'] != intent['map_id']:
        raise ValueError('A base variant uses a different map than requested; select a compatible base variant set')
    wanted = set(intent['monster_ids'])
    present = {m['id'] for m in summary['monsters']}
    if wanted and (not wanted.intersection(present) if intent.get('monster_match', 'all') == 'any' else not wanted.issubset(present)):
        raise ValueError('The final roster does not contain the requested native monster species')
    stage = intent.get('spawn_stage')
    if stage is not None and (not choices or choices.get('position') != 'native'):
        if any(m['stage'] != stage for m in summary['monsters'] if m['id'] in wanted):
            raise ValueError('The final roster does not place all requested monsters in the requested stage')


def resolve_evidence(config, spec):
    """Resolve only typed, hash-bound corpus sources; model paths are never executed."""
    requested = set()
    for row in spec['edits'].get('monster_spawns') or []:
        requested.add(row['reference_id'])
        if row['position_reference_id'] is not None:
            requested.add(row['position_reference_id'])
    evidence = {}
    for row in spec.get('provenance', {}).get('spawn_sources', []):
        if not isinstance(row, dict) or set(row) != {'reference_id', 'source'}:
            raise ValueError('Invalid spawn evidence source record')
        reference = row['reference_id']
        if reference in evidence:
            raise ValueError('Duplicate spawn evidence reference')
        if reference in requested:
            path = check_source(config, row['source'])
            evidence[reference] = raw_bytes(config, path)
    if requested != set(evidence):
        raise ValueError('A requested spawn/position reference is missing from verified build provenance')
    return evidence


def validate_spec(spec):
    keys = {"schema_version", "kind", "base_reference_id", "quest_id", "sources", "edits", "unresolved", "unsupported", "provenance"}
    if not isinstance(spec, dict) or set(spec) != keys or type(spec["schema_version"]) is not int or spec["schema_version"] != 1 or spec["kind"] != "mhfz_build_spec":
        raise ValueError("Invalid build specification")
    if not isinstance(spec["base_reference_id"], str) or not isinstance(spec["provenance"], dict):
        raise ValueError("Invalid build provenance")
    integer(spec["quest_id"], 1, 65535, "quest_id")
    validate_edits(spec["edits"])
    for key in ("unresolved", "unsupported"):
        if not isinstance(spec[key], list) or any(not isinstance(v, str) for v in spec[key]):
            raise ValueError("Invalid compiler decision list")
        if spec[key]:
            raise ValueError(f"Cannot build while {key} decisions remain")
    return spec


def output_directory(config, destination):
    destination = Path(destination).resolve()
    if not contains(Path(config["workspace"]), destination) or contains(Path(config["source"]), destination):
        raise ValueError("Build output must be inside the configured workspace, outside the corpus")
    if destination.exists():
        raise ValueError("Output directory already exists; existing builds are never overwritten")
    return destination


def build(config, spec, destination, dry_run=False):
    validate_spec(spec)
    destination = output_directory(config, destination)
    base_id = verify_sources(config, spec["sources"])
    quest_id = spec["quest_id"]
    if quest_id != base_id:
        for path in Path(config["source"]).rglob("*"):
            match = ROLE.fullmatch(path.name)
            if match and int(match.group(1)) == quest_id and path.is_file():
                raise ValueError("Target ID is occupied in the corpus; choose a different ID. Database IDs are not checked.")
    prepared = []
    raw_cache = {}
    evidence = resolve_evidence(config, spec)
    for row in spec["sources"]:
        path = check_source(config, row)
        raw = raw_cache.get(row["sha256"])
        if raw is None:
            raw = raw_bytes(config, path)
            raw_cache[row["sha256"]] = raw
        payload, result = patch_bytes(raw, quest_id, spec["edits"], evidence)
        verify_intent(spec.get('provenance', {}).get('requested_intent'), result['summary'], spec.get('provenance', {}).get('authoring_choices'))
        prepared.append((row, payload, result))
    # Validate everything before creating the new output directory.
    if dry_run:
        return {"status": "validated_not_written", "quest_id": quest_id,
                "variants": [{"role": row["role"], "proof": proof} for row, _, proof in prepared],
                "installed": False, "runtime_verified": False}
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "status": "building", "quest_id": quest_id,
                "base_quest_id": base_id, "format": "raw_uncompressed", "outputs": [],
                "database_id_checked": False, "installed": False, "runtime_verified": False,
                "spec_canonical_sha256": digest(json.dumps(spec, sort_keys=True).encode("utf-8")),
                "limitations": ["Partial format validation; client test required", "Native map package and opaque original bytes preserved; custom spawn/reward sections are append-only when requested"],
                "evidence_sources": []}
    manifest_path = destination / "manifest.json"
    try:
        for row in spec.get('provenance', {}).get('spawn_sources', []):
            if row['reference_id'] not in evidence:
                continue
            path = check_source(config, row['source'])
            original = path.read_bytes()
            backup = Path(config['workspace']) / 'source-backups' / f"{row['source']['sha256']}.bin"
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                with backup.open('xb') as stream:
                    stream.write(original)
            if digest(backup.read_bytes()) != row['source']['sha256']:
                raise ValueError('Spawn evidence backup hash verification failed')
            manifest['evidence_sources'].append({**row, 'backup': str(backup)})
        for row, payload, result in prepared:
            original = Path(row["path"]).read_bytes()
            if digest(original) != row["sha256"]:
                raise ValueError("Source changed during build")
            backup = Path(config["workspace"]) / "source-backups" / f"{row['sha256']}.bin"
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                with backup.open("xb") as stream:
                    stream.write(original)
            if digest(backup.read_bytes()) != row["sha256"]:
                raise ValueError("Original source backup failed hash verification")
            output = destination / f"{quest_id:05d}{row['role']}.bin"
            with output.open("xb") as stream:
                stream.write(payload)
            if digest(output.read_bytes()) != result["output_raw_sha256"]:
                raise ValueError("Exported file hash verification failed")
            manifest["outputs"].append({"path": str(output), "source": row, "source_backup": str(backup), **result})
        for row in spec["sources"]:
            check_source(config, row)
        resolve_evidence(config, spec)
        manifest["status"] = "built_unverified"
        (destination / "build-spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        manifest["status"] = "failed"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": str(manifest_path), "status": manifest["status"], "quest_id": quest_id,
            "outputs": [r["path"] for r in manifest["outputs"]], "installed": False, "runtime_verified": False}


def roundtrip(config, source):
    source = Path(source).resolve()
    sha = digest(source.read_bytes())
    raw = raw_bytes(config, source)
    summary = inspect_bytes(raw)
    result, proof = patch_bytes(raw, summary["quest_id"], empty_edits())
    if result != raw or digest(source.read_bytes()) != sha:
        raise ValueError("Lossless round-trip or original-source check failed")
    return {"source": str(source), "source_sha256": sha, "raw_sha256": digest(raw),
            "raw_byte_identical": True, "source_unchanged": True, "bytes": len(raw),
            "runtime_verified": False, "note": "Opaque-preserving raw round trip; not a full serializer reconstruction"}
