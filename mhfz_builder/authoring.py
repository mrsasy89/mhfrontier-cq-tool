"""Shared terminal/desktop choices. Undocumented flags are never guessed."""
from pathlib import Path
from .refrontier import read_summary

# Labels come from mhfrontier-cq-tool/src/tabs/quest/FlagsTab.tsx.
# Labels are editor evidence, not traced client behavior; dependencies still matter.
FLAG_GROUPS = (
    (("SR/changeable", "Selects the editor's SR/changeable mode."),
     ("HC fixed", "Requests fixed Hardcore mode; requires a compatible base."),
     ("HC/UL toggle", "Requests selectable HC/UL; requires compatible monster data."),
     ("G Rank", "Marks G Rank; changing this alone does not convert an HR quest."),
     None, None, None,
     ("UL fixed", "Requests fixed Unlimited mode; compatibility is required.")),
    (("Level 1", "Editor level-1 marker; client interpretation depends on quest mode."),
     ("Disable Halk potion", "Editor restriction on Halk potion use."),
     ("Disable Halk and Poogie", "Editor restriction on Halk/Poogie support."),
     ("Timer", "Editor timer-mode marker; not the quest duration field."),
     ("Disable active feature", "Editor restriction on the active-feature system."),
     ("Fixed difficulty", "Editor fixed-difficulty marker."),
     ("Level 9999", "Editor level-9999 marker; special-mode dependencies apply."),
     ("Road", "Hunting Road mode marker; additional mode data is required.")),
    (("Disable reward bonus", "Editor restriction on bonus rewards."),
     ("Require GR", "Editor GR requirement marker; rank requirements also need matching data."),
     None, None,
     ("Zenith", "Zenith mode marker; does not turn a normal monster into Zenith."),
     ("Diva Defense / Interception", "Special-mode marker used in sequential-spawn experiments; not a generic spawn switch and may require other native data."),
     None,
     ("No sigils", "Editor restriction on sigil use.")),
    (None,) * 8,
)


def flag_legend():
    rows = ["Quest flags: editor labels, not independently verified client semantics."]
    for group, flags in enumerate(FLAG_GROUPS, 1):
        for bit, detail in enumerate(flags):
            name, meaning = detail or ("Unknown / reserved", "Purpose unconfirmed; preserve the native value. Not selectable.")
            rows.append(f"{group}:{1 << bit:03d}  {name} -- {meaning}")
    rows.append("Variant 4 also overlaps forced-equipment data in the editor definition; it is read-only here.")
    return rows


def parse_flags(text):
    changes = {}
    for token in text.replace(",", " ").split():
        if not token.startswith(("+", "-")):
            raise ValueError("Use +group:mask to enable or -group:mask to disable, for example +1:2 -3:32.")
        try:
            group, mask = map(int, token[1:].split(":"))
            bit = mask.bit_length() - 1
            known = 1 <= group <= 3 and mask > 0 and mask & (mask - 1) == 0 and bit < 8 and FLAG_GROUPS[group-1][bit] is not None
        except (ValueError, IndexError):
            known = False
        if not known:
            raise ValueError("Unknown/reserved flags cannot be changed. Choose a documented single-bit mask in groups 1-3.")
        key = f"{group}:{mask}"
        if key in changes:
            raise ValueError("A flag was specified more than once.")
        changes[key] = token[0] == "+"
    return changes


def collect_preferences(ui):
    result = {}
    step = 0
    # Import here to avoid a module cycle and preserve shared Back navigation.
    from .wizard import Back
    while step < 4:
        try:
            if step == 0:
                ui.write("[1/4] Monster Status table: a table index, not HP. Blank preserves native statistics for the selected reference; no HP/multiplier values are inferred.")
                while True:
                    raw = ui.ask("Monster Status table (blank = original)")
                    if not raw:
                        result["stat_table"] = None
                        break
                    if raw.isdecimal() and 0 <= int(raw) <= 65535:
                        result["stat_table"] = int(raw)
                        break
                    ui.write("Enter a table index from 0 to 65535, or leave blank.")
            elif step == 1:
                ui.write("[2/4] Monster position\n1. Standard: preserve a compatible native spawn for this map/monster\n2. Choose an area/position using corpus evidence")
                result["position"] = "native" if ui.number("Position", 1, 2, 1) == 1 else "manual"
                result["position_request"] = ui.ask("Area/position requirements") if result["position"] == "manual" else ""
            elif step == 2:
                ui.write("[3/4] Preferred flags")
                for row in flag_legend():
                    ui.write(row)
                while True:
                    try:
                        result["flags"] = parse_flags(ui.ask("Blank preserves all flags; otherwise use +group:mask / -group:mask"))
                        break
                    except ValueError as exc:
                        ui.write(str(exc))
            else:
                ui.write("[4/4] Rewards\n1. Standard: preserve rewards from the compatible native monster quest\n2. Custom: compile the reward request from your description; ask for missing quantities/weights")
                result["rewards"] = "native" if ui.number("Rewards", 1, 2, 1) == 1 else "custom"
            step += 1
        except Back:
            if step == 0:
                raise
            step -= 1
            ui.write("Returned to the previous authoring question.")
    return result


def preferences_text(choices):
    return ("\nFixed authoring choices (take precedence over conflicting description text):\n"
            f"Monster Status table: {choices['stat_table'] if choices['stat_table'] is not None else 'preserve original'}.\n"
            + ("Preserve compatible native monster spawns.\n" if choices['position'] == 'native' else f"Requested spawn position: {choices['position_request']}. Use verified corpus positions; do not invent coordinates.\n")
            + ("Preserve native rewards.\n" if choices['rewards'] == 'native' else "Compile the custom Main/Sub A/Sub B rewards requested in the description. Ask for any missing item, quantity or weight.\n")
            +
            f"Flag changes: {choices['flags'] or 'preserve all native flags'}. Undocumented bits must remain unchanged.")


def enforce_preferences(config, spec, choices):
    """Host choices override model edits before structural validation."""
    spec["edits"]["stat_table"] = choices["stat_table"]
    if choices.get('rewards') == 'native':
        spec['edits']['rewards'] = None
    if not choices["flags"]:
        spec["edits"]["quest_flags"] = None
        return
    candidates = []
    for source in spec["sources"]:
        flags = list(read_summary(config, Path(source["path"]))["quest_flags"])
        for key, enabled in choices["flags"].items():
            group, mask = map(int, key.split(":"))
            flags[group-1] = flags[group-1] | mask if enabled else flags[group-1] & ~mask
        candidates.append(flags)
    if any(flags != candidates[0] for flags in candidates[1:]):
        raise ValueError("Native variants have different flags. A shared edit would discard variant data; review separately.")
    spec["edits"]["quest_flags"] = candidates[0]
