"""Append-only spawn/reward packages based on the native CQ layouts.

Only top-level pointers change in the original file. Opaque spawn bytes and native
reward header flags are retained. Cross-species coordinates are terrain evidence,
not proof of monster AI, simultaneous combat or migration behavior.
"""
import math
import struct
from .binary import Reader, inspect_bytes, CATALOG


def spawn_record(raw, index):
    summary = inspect_bytes(raw)
    if type(index) is not int or not 0 <= index < len(summary["monsters"]):
        raise ValueError("Spawn evidence index is outside the referenced roster")
    reader = Reader(raw)
    pointer = reader.u32(reader.u32(24) + 12) + index * 60
    record = reader.read('<60s', pointer)[0]
    if not all(math.isfinite(value) for value in struct.unpack_from('<3f', record, 32)):
        raise ValueError("Non-finite spawn coordinates in reference")
    return record, summary


def custom_spawns(base, edits, evidence):
    base_summary = inspect_bytes(base)
    records, warnings = [], []
    for request in edits:
        if request['reference_id'] not in evidence:
            raise ValueError("Unknown spawn evidence reference")
        record, donor = spawn_record(evidence[request['reference_id']], request['spawn_index'])
        if donor['map'] != base_summary['map']:
            raise ValueError("Spawn references must use the same native map ID as the base variant")
        if request['position_reference_id'] is not None:
            if request['position_reference_id'] not in evidence:
                raise ValueError("Unknown position evidence reference")
            position, terrain = spawn_record(evidence[request['position_reference_id']], request['position_spawn_index'])
            if terrain['map'] != donor['map']:
                raise ValueError("Position evidence uses another map")
            updated = bytearray(record)
            updated[8:12] = position[8:12]
            updated[28:44] = position[28:44]
            if record[0] != position[0]:
                warnings.append("Cross-species placement: stage/orientation/XYZ are terrain evidence only; AI and migration require a client test.")
            record = bytes(updated)
        stage = struct.unpack_from('<I', record, 8)[0]
        if stage not in {row['id'] for row in CATALOG['maps'][str(donor['map'])]['stages']}:
            raise ValueError("Spawn stage is not in this map's stage catalog")
        records.append(record)
    if len(records) > 1:
        warnings.append("An ordered multi-monster roster does not prove simultaneous spawns; native mode flags and client behavior must be checked.")
    return records, warnings


def append_spawns(out, source, records):
    r = Reader(source)
    original_header = r.u32(24)
    if not original_header:
        raise ValueError("Base has no native boss pointer package")
    header = bytearray(r.read('<32s', original_header)[0])
    out.extend(bytes((-len(out)) % 4))
    header_ptr = len(out); out.extend(header)
    ids_ptr = len(out)
    for record in records:
        out.extend(struct.pack('<I', record[0]))
    out.extend(b'\xff' * 4)
    spawns_ptr = len(out)
    out.extend(b''.join(records) + b'\xff\xff')
    struct.pack_into('<II', out, header_ptr + 8, ids_ptr, spawns_ptr)
    struct.pack_into('<I', out, 24, header_ptr)


def append_rewards(out, source, edits):
    native = inspect_bytes(source)['rewards']
    tables = [dict(table, rows=list(table['rows'])) for table in native]
    warnings = []
    for edit in edits:
        matches = [table for table in tables if table['table'] == edit['table']]
        if len(matches) > 1:
            raise ValueError("Ambiguous native reward table ID; cannot replace it safely")
        rows = edit['rows']
        if matches:
            matches[0]['rows'] = rows
        else:
            # This is the CQ editor's explicit new-table profile, not a guessed UNK value.
            tables.append({'table': edit['table'], 'header_unknown0': 128, 'header_unknown1': 0, 'rows': rows})
        total = sum(row['rate'] for row in rows)
        if total != 100:
            warnings.append(f"Reward table {edit['table']} configured weights total {total}, not 100; preserved without normalization.")
    if len(tables) > 63:
        raise ValueError("Too many reward tables")
    out.extend(bytes((-len(out)) % 4))
    header_ptr = len(out)
    out.extend(bytes(8 * len(tables)) + b'\xff\xff')
    for index, table in enumerate(tables):
        pointer = len(out)
        for row in table['rows']:
            out.extend(struct.pack('<3H', row['rate'], row['item'], row['amount']))
        out.extend(b'\xff\xff')
        struct.pack_into('<BBHI', out, header_ptr + index * 8, table['table'], table['header_unknown0'], table['header_unknown1'], pointer)
    struct.pack_into('<I', out, 12, header_ptr)
    return warnings
