import assert from 'node:assert/strict';
import { test } from 'node:test';
import { suggestObjectives, suggestSuccess, suggestFailure } from '../src/utils/questStringTemplates.ts';

const names = { monster: id => ({ 1: 'Rathian', 2: 'Fatalis' })[id], item: id => ({ 513: 'Potion' })[id] };
const objective = (quest_objective, monster_id = 1, quantity = 1, unk = 0) => ({ quest_objective, monster_id, quantity, unk });
const objectives = (a, b = objective(0), c = objective(0)) => ({ objective1: a, objective2: b, objective3: c });

for (const [code, verb] of [[1, 'Hunt'], [257, 'Capture'], [513, 'Slay']]) {
  test(`formats monster objective ${code}`, () => {
    assert.equal(suggestObjectives(objectives(objective(code, 1, 2)), names).values.main_objective, `${verb} 2 Rathian`);
  });
}
test('combines the low and high target bytes for item IDs', () => {
  assert.equal(suggestObjectives(objectives(objective(2, 1, 3, 2)), names).values.main_objective, 'Deliver 3 Potion');
});
test('empty sub objectives become None', () => {
  const result = suggestObjectives(objectives(objective(513)), names);
  assert.equal(result.values.sub_a_objective, 'None');
  assert.equal(result.values.sub_b_objective, 'None');
  assert.deepEqual(result.warnings, []);
});
test('unknown objective types remain unchanged by omission', () => {
  const result = suggestObjectives(objectives(objective(0x4004)), names);
  assert.equal(Object.hasOwn(result.values, 'main_objective'), false);
  assert.match(result.warnings.join(), /Main objective/);
});
test('unknown target IDs are not replaced by invented names', () => {
  const result = suggestObjectives(objectives(objective(513, 99)), names);
  assert.equal(Object.hasOwn(result.values, 'main_objective'), false);
  assert.equal(result.warnings.length, 1);
});
for (const invalid of [0, -1, 1.5, NaN, Infinity]) {
  test(`invalid quantity ${invalid} leaves text untouched`, () => {
    assert.equal(Object.hasOwn(suggestObjectives(objectives(objective(1, 1, invalid)), names).values, 'main_objective'), false);
  });
}
test('does not mutate objective data', () => {
  const data = objectives(objective(1));
  const before = structuredClone(data);
  suggestObjectives(data, names);
  assert.deepEqual(data, before);
});
test('generates independent sub-objective suggestions', () => {
  const result = suggestObjectives(objectives(objective(1), objective(257), objective(513, 2)), names);
  assert.equal(result.values.sub_a_objective, 'Capture 1 Rathian');
  assert.equal(result.values.sub_b_objective, 'Slay 1 Fatalis');
});
test('high-byte monster IDs do not accidentally resolve to low-byte names', () => {
  assert.equal(Object.hasOwn(suggestObjectives(objectives(objective(1, 1, 1, 1)), names).values, 'main_objective'), false);
});
for (const [id, high] of [[-1, 0], [256, 0], [1, 256], [1, NaN]]) {
  test(`rejects malformed target bytes ${id}, ${high}`, () => {
    assert.equal(Object.hasOwn(suggestObjectives(objectives(objective(1, id, 1, high)), names).values, 'main_objective'), false);
  });
}
test('placeholder names are preserved for manual review', () => {
  for (const name of ['None', 'Unknown', 'UNK', 'Dummy', 'Monster?', ' ']) {
    const result = suggestObjectives(objectives(objective(1)), { ...names, monster: () => name });
    assert.equal(Object.hasOwn(result.values, 'main_objective'), false);
  }
});
for (const [mode, subs, text] of [
  [1, [0, 0], 'Complete the main objective.'],
  [1, [1, 0], 'Complete the main objective\nor sub-objective A.'],
  [1, [0, 1], 'Complete the main objective\nor sub-objective B.'],
  [1, [1, 1], 'Complete the main objective\nor sub-objective A or B.'],
  [2, [1, 1], 'Complete the main objective.'],
  [3, [1, 1], 'Complete the main objective\nand sub-objective A.'],
  [4, [1, 1], 'Complete all objectives.'],
]) {
  test(`success mode ${mode}, sub objectives ${subs}`, () => {
    assert.equal(suggestSuccess(mode, objectives(objective(1), objective(subs[0]), objective(subs[1]))).value, text);
  });
}
test('unknown success modes remain untouched', () => {
  assert.equal(suggestSuccess(99, objectives(objective(1))).value, undefined);
});
test('missing main objective is not described as completable', () => {
  assert.equal(suggestSuccess(2, objectives(objective(0))).value, undefined);
});
test('mode requiring sub A refuses a missing sub A', () => {
  assert.equal(suggestSuccess(3, objectives(objective(1))).value, undefined);
});
test('failure template always requires an explicit policy', () => {
  assert.equal(suggestFailure('preserve', 3).value, undefined);
});
test('faint template uses the chosen count', () => {
  assert.equal(suggestFailure('faints', 3).value, 'Faint 3 times.\nTime runs out.');
});
test('singular faint template', () => {
  assert.equal(suggestFailure('faints', 1).value, 'Faint 1 time.\nTime runs out.');
});
test('zero-reward template is independent of faint limit', () => {
  assert.equal(suggestFailure('reward', 0).value, 'Reward falls to 0z.\nTime runs out.');
});
test('invalid faint count is not fabricated', () => {
  assert.equal(suggestFailure('faints', 0).value, undefined);
});
