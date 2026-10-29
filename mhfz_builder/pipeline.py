"""Shared quest planning pipeline. Never executes model proposals."""
from pathlib import Path
from .binary import CATALOG
from .planning import INTENT_SCHEMA, PLAN_SCHEMA, coverage, references, research_references, public_references, validate_intent, validate_plan
from .prompts import KNOWLEDGE

def create_plan(config, prompt, client):
    if not prompt.strip() or len(prompt) > 12000:
        raise ValueError("Prompt must contain 1 to 12000 characters")
    inventory = coverage(config)
    progress = config.get('_progress', lambda text: None)
    catalog = {"monsters": CATALOG["monsters"],
               "maps": CATALOG["maps"]}
    progress('Waiting for Codex: interpreting the quest request')
    intent = validate_intent(client.request("quest_intent", INTENT_SCHEMA,
                                           {"prompt": prompt, "catalog": catalog}))
    progress('Searching the complete parsed corpus for base, monster and position evidence')
    rows = research_references(config, intent, references(config, intent))
    progress(f'Waiting for Codex: reviewing {len(rows)} verified reference candidates')
    from .items import mentioned_items
    from .research import research
    research_log = []
    validation_log = []
    for attempt in range(4):
        data = {"prompt": prompt, "intent": intent, "coverage": inventory, "historical_case_notes": KNOWLEDGE["case_notes"],
           "items": mentioned_items(prompt), "research_results": research_log,
           "research_rounds_remaining": 3 - attempt,
           "research_instructions": "Request specific corpus/item searches when evidence is insufficient. Prefer native complete map packages and same-species/stage records. Cross-species position data is experimental terrain evidence. Custom IDs are not certified original quests. Return questions for missing user choices, not research facts the host can retrieve. An explicit request for original references excludes authored custom-range bases.",
           "host_verification": {"source_hashes_checked": True, "reference_files_managed_locally": True, "complete_map_validator_available": False},
           "references": public_references(rows)}
        for correction in range(3):
            value = client.request('quest_plan', PLAN_SCHEMA, dict(data, validation_feedback=validation_log,
                evidence_rules='supported changes must cite supplied evidence IDs. Explicit user text/ID/time requests use confidence=requested; never invent evidence for them.'))
            try:
                proposal = validate_plan(value, rows)
                break
            except ValueError as exc:
                validation_log.append({'round': attempt + 1, 'attempt': correction + 1, 'error': str(exc), 'rejected_plan': value})
                if correction == 2:
                    raise ValueError(f'Plan validation failed after three proposals: {exc}') from exc
                progress('Waiting for Codex: correcting the plan using evidence validation feedback')
        if not proposal['research_requests']:
            break
        if attempt == 3:
            proposal['base_reference_id'] = None
            proposal['warnings'].append('Research round limit reached; no build accepted. Review the saved research questions/evidence before continuing.')
            break
        progress(f"Searching corpus/items for {len(proposal['research_requests'])} additional evidence requests")
        rows, results = research(config, proposal['research_requests'], rows)
        research_log.append({'round': attempt + 1, 'results': results})
        progress('Waiting for Codex: comparing additional research evidence')
    if any(row['quest']['quest_id'] >= 65001 for row in rows):
        proposal['warnings'].append('Custom-range references are included as authored evidence, not certified original or game-tested quests.')
    if not inventory["complete"]:
        proposal["warnings"].append("Corpus analysis is incomplete; reference selection only covers parsed files.")
    if not rows:
        proposal["warnings"].append("No matching parsed reference was found; decode more of the corpus or revise the request.")
    # Recheck source hashes after model inference before accepting the local plan.
    from .binary import digest
    for row in rows:
        for path in row["source_variants"]:
            if digest(Path(path).read_bytes()) != row["source_sha256"]:
                raise ValueError("Reference changed during planning; no plan accepted")
    return {"schema_version": 1, "status": "needs_review" if proposal["base_reference_id"] else "needs_reference",
            "prompt": prompt, "intent": intent, "plan": proposal, "references": rows,
            "coverage": inventory, "model_calls": client.calls, "api_calls": client.calls,
            "research_log": research_log,
            "validation_repairs": validation_log,
            "provider": getattr(client, "kind", "openai"),
            "bin_generated": False, "runtime_verified": False}
