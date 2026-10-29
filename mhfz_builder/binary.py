"""Read-only inspection. Unknown bytes are never interpreted as confirmed mechanics."""
from __future__ import annotations
import hashlib
import json
import struct
from importlib.resources import files

CATALOG = json.loads(files("mhfz_builder").joinpath("data/catalog.json").read_text(encoding="utf-8"))
OBJECTIVES = {0: "Nothing", 1: "Hunt", 257: "Capture", 513: "Slay", 32772: "Damage",
              98308: "Slay_or_Damage", 262144: "Slay_All", 131072: "Slay_Total",
              2: "Deliver", 16388: "Break_Part", 4098: "Deliver_Flag", 16: "Esoteric_Action"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def packed(data: bytes) -> bool:
    return data[:3].lower() in (b"jkr", b"ecd", b"exf")


class Reader:
    def __init__(self, data: bytes):
        self.data = data

    def read(self, fmt: str, offset: int):
        if offset < 0 or offset + struct.calcsize(fmt) > len(self.data):
            raise ValueError(f"Read outside file bounds: {offset:#x}, format {fmt}")
        return struct.unpack_from(fmt, self.data, offset)

    def u32(self, offset: int) -> int:
        return self.read("<I", offset)[0]

    def u16(self, offset: int) -> int:
        return self.read("<H", offset)[0]

    def text(self, pointer: int) -> str:
        if pointer == 0:
            return ""
        self.read("<B", pointer)
        end = self.data.find(b"\0", pointer, min(len(self.data), pointer + 65536))
        if end < 0:
            raise ValueError("Unterminated string")
        return self.data[pointer:end].decode("cp932", errors="replace")


def inspect_bytes(data: bytes) -> dict:
    if packed(data):
        raise ValueError("Compressed/encrypted quest: use unpack or index --decode")
    r = Reader(data)
    body = r.u32(0)
    if body < 68:
        raise ValueError("Implausible quest pointer")
    r.read("<205s", body)
    map_ptr = r.u32(36)
    map_id, return_stage = r.read("<II", map_ptr)
    text_table = r.u32(body + 40)
    texts = [r.text(r.u32(text_table + i * 4)) for i in range(8)]
    objectives = []
    for i in range(3):
        kind, target, unknown, quantity = r.read("<IBBH", body + 48 + i * 8)
        obj = {"type": kind, "label": OBJECTIVES.get(kind, "Unknown"),
               "target": target, "unknown": unknown, "quantity_raw": quantity}
        if kind == 32772:
            obj["damage_points"] = quantity * 100
        objectives.append(obj)
    monsters = []
    large_ptr = r.u32(24)
    if large_ptr:
        spawn_ptr = r.u32(large_ptr + 12)
        for i in range(64):
            offset = spawn_ptr + 60 * i
            if r.u16(offset) == 65535:
                break
            r.read("<60s", offset)
            mid = data[offset]
            monsters.append({"id": mid, "name": CATALOG["monsters"].get(str(mid), str(mid)),
                             "amount": r.u32(offset + 4), "stage": r.u32(offset + 8),
                             "orientation_raw": r.u32(offset + 28),
                             "xyz": list(r.read("<3f", offset + 32))})
        else:
            raise ValueError("Boss records are not terminated within the inspection limit")
    rewards = []
    reward_ptr = r.u32(12)
    if reward_ptr:
        for i in range(64):
            offset = reward_ptr + i * 8
            if r.u16(offset) == 65535:
                break
            tid, unknown0, unknown1, items_ptr = r.read("<BBHI", offset)
            rows = []
            for j in range(1024):
                pos = items_ptr + j * 6
                if r.u16(pos) == 65535:
                    break
                rate, item, amount = r.read("<3H", pos)
                rows.append({"rate": rate, "item": item, "amount": amount})
            else:
                raise ValueError("Unterminated reward list")
            rewards.append({"table": tid, "header_unknown0": unknown0,
                            "header_unknown1": unknown1, "rows": rows,
                            "rate_total": sum(row["rate"] for row in rows)})
        else:
            raise ValueError("Unterminated reward tables")
    stages_ptr, stages_end = r.u32(4), r.u32(52)
    if stages_end < stages_ptr or (stages_end - stages_ptr) % 16 or stages_end - stages_ptr > 4096:
        raise ValueError("Invalid entrance section")
    players = [r.u32(offset) for offset in range(stages_ptr, stages_end, 16)]
    return {"schema_version": 1, "sha256": digest(data), "bytes": len(data),
            "quest_id": r.u16(body + 46), "title": texts[0], "texts": texts,
            "map": map_id, "map_name": CATALOG["maps"].get(str(map_id), {}).get("name", str(map_id)),
            "return_stage": return_stage, "player_stages": players,
            "class": data[92], "stat_table": r.u32(72),
            "size_percent": r.u16(68), "size_range": r.u16(70),
            "time_minutes": r.u32(body + 32) / 1800,
            "locale_raw": data[body + 2], "return_flags_raw": data[body + 3],
            "failure_value_raw32": r.u32(body + 20),
            "reward_main_z": r.u32(body + 16), "quest_type_raw": data[body + 10],
            "variants": [data[body + i] for i in (145, 146, 182, 183, 184)],
            "quest_flags": list(data[body + 151:body + 155]),
            "objectives": objectives, "finish_raw": data[body + 72],
            "monsters": monsters, "rewards": rewards,
            "runtime_verified": False,
            "limitations": ["Partial structural inspection; not a client simulation",
                            "Unknown fields and variant/failure semantics are not verified"]}
