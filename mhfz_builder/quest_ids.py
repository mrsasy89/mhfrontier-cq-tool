"""Read-only filename allocation for custom quests; never queries the database."""
from pathlib import Path
import os
import re

FIRST_CUSTOM_ID = 65001
LAST_CUSTOM_ID = 65535
PROTECTED_IDS = {65005}
QUEST_FILE = re.compile(r"^(\d+)[a-z]\d+\.bin$", re.IGNORECASE)


def occupied_ids(config):
    server = config.get("server_quest_directory")
    roots = [Path(config["source"])]
    if server:
        roots.insert(0, Path(server))
    roots.append(Path(config["workspace"]) / "custom-quests")
    occupied = set(PROTECTED_IDS)
    checked = []
    def fail(error):
        raise error
    for root in dict.fromkeys(roots):
        if not root.is_dir():
            if root == roots[-1] and not root.exists():
                continue
            raise ValueError(f"Quest ID scan directory not found: {root}")
        checked.append(str(root))
        for _, _, names in os.walk(root, onerror=fail):
            for name in names:
                match = QUEST_FILE.fullmatch(name)
                if match:
                    occupied.add(int(match[1]))
    return occupied, checked, bool(server or config.get("source_kind") == "server")


def first_available(occupied):
    for quest_id in range(FIRST_CUSTOM_ID, LAST_CUSTOM_ID + 1):
        if quest_id not in occupied:
            return quest_id
    raise ValueError("No free custom quest ID in 65001-65535 in the checked folders.")
