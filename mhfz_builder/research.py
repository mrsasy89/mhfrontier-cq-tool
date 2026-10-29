"""Host-executed read-only research requests; no model scripts or file paths."""
from pathlib import Path
from .binary import CATALOG, digest
from .config import contains
from .corpus import search
from .planning import coverage
from .items import ITEMS, normalize


def research(config, queries, references):
    if len(queries) > 6:
        raise ValueError('At most six research queries are allowed per round')
    rows = list(references)
    results = []
    known = {r['source_sha256']: r for r in rows}
    for query in queries:
        if query['kind'] == 'items':
            terms = normalize(query['text']).split()
            found = [{'item': int(key), 'name': name} for key, name in ITEMS.items()
                     if terms and all(term in normalize(name) for term in terms)]
            results.append({'query': query, 'items': found[:40], 'matches': len(found)})
            continue
        if query['map_id'] is not None and str(query['map_id']) not in CATALOG['maps']:
            raise ValueError('Research map is not in the catalog')
        if query['monster_id'] is not None and str(query['monster_id']) not in CATALOG['monsters']:
            raise ValueError('Research monster is not in the catalog')
        found = search(config, monster=str(query['monster_id']) if query['monster_id'] is not None else None,
                       map_filter=str(query['map_id']) if query['map_id'] is not None else None,
                       limit=max(1, coverage(config)['parsed']))
        filtered = []
        for row in found:
            quest = row['quest']
            if query['quest_id'] is not None and query['quest_id'] != quest['quest_id']:
                continue
            if query['stage'] is not None and not any(m['stage'] == query['stage'] and (query['monster_id'] is None or m['id'] == query['monster_id']) for m in quest['monsters']):
                continue
            if query['text'] and normalize(query['text']) not in normalize(quest['title']):
                continue
            filtered.append(row)
        ids = []
        for row in filtered:
            if len(ids) >= 6 or len(rows) >= 60:
                break
            sha = row['source_sha256']
            path = Path(row['source'])
            if not contains(Path(config['source']), path) or digest(path.read_bytes()) != sha:
                raise ValueError('Research reference is missing, changed or outside the configured corpus')
            if sha not in known:
                item = {'reference_id': f'R{len(rows)+1}', 'source_sha256': sha,
                        'source_variants': [str(path)], 'quest': row['quest']}
                rows.append(item); known[sha] = item
            item = known[sha]
            if item['reference_id'] not in ids:
                ids.append(item['reference_id'])
        # Record every physical role for the selected hashes, including identical files.
        for row in filtered:
            if row['source_sha256'] in known and known[row['source_sha256']]['reference_id'] in ids:
                target = known[row['source_sha256']]
                if row['source'] not in target['source_variants']:
                    path = Path(row['source'])
                    if not contains(Path(config['source']), path) or digest(path.read_bytes()) != row['source_sha256']:
                        raise ValueError('Research variant changed; reindex')
                    target['source_variants'].append(row['source'])
        results.append({'query': query, 'reference_ids': ids, 'matches': len(filtered)})
    return rows, results
