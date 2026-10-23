import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import { maps } from '../src/utils/maps.ts';
import { mapImagePath, hasCalibration, toCanvasPoint, toGamePoint, pointerToCanvas } from '../src/utils/mapPreview.ts';

for (const [id, folder] of [[11, 'Snowy Mountain Day'], [21, 'Snowy Mountain Night']]) {
  const map = maps.find(value => value.id === id);
  for (const stage of map.stages.filter(stage => stage.areaNumber !== 'Secret')) {
    test(`${map.name} ${stage.areaNumber} resolves the existing asset name`, () => {
      const number = stage.areaNumber === 'Base' ? '0' : stage.areaNumber.split(' ')[1];
      const path = mapImagePath(map.name, stage.areaNumber);
      assert.equal(path, `/maps/${encodeURIComponent(folder)}/${number}.png`);
      // CI uses the complete checkout; local partial checkout may lack assets.
      if (existsSync(fileURLToPath(new URL('../resources', import.meta.url)))) {
        assert.equal(existsSync(fileURLToPath(new URL(`../resources/maps/${folder}/${number}.png`, import.meta.url))), true);
      }
    });
  }
}
test('secret area never requests undefined.png or an unrelated base image', () => {
  assert.equal(mapImagePath('Snowy Mountains Day', 'Secret'), undefined);
});
test('normal map folders keep their paths', () => assert.equal(mapImagePath('Highlands Day', 'Area 2'), '/maps/Highlands%20Day/2.png'));
test('unknown area labels have no image path', () => assert.equal(mapImagePath('Highlands Day', 'Unknown'), undefined));
test('missing calibration cannot interpret pixels as game coordinates', () => {
  assert.equal(hasCalibration({}), false);
  assert.equal(toGamePoint({ x: 50, y: 50 }, {}, true), undefined);
  assert.equal(toCanvasPoint({ x: 10000, y: 5000 }, {}, true), undefined);
});
test('pixel mode still works in the calibration tool', () => {
  assert.deepEqual(toGamePoint({ x: 50, y: 60 }, {}, false), { x: 50, y: 60 });
});
const calibrated = { calculationX: { a: 100, b: -1000 }, calculationY: { a: -50, b: 5000 } };
test('calibrated conversion supports negative slopes and round-trips', () => {
  const point = { x: 8000, y: 3500 };
  const canvas = toCanvasPoint(point, calibrated, true);
  assert.deepEqual(canvas, { x: 90, y: 30 });
  assert.deepEqual(toGamePoint(canvas, calibrated, true), point);
});
for (const a of [0, NaN, Infinity]) {
  test(`invalid calibration slope ${a} blocks conversion`, () => {
    assert.equal(hasCalibration({ ...calibrated, calculationX: { a, b: 0 } }), false);
  });
}
test('one calibrated axis is insufficient', () => assert.equal(hasCalibration({ calculationX: calibrated.calculationX }), false));
test('nonfinite coordinates are refused', () => assert.equal(toGamePoint({ x: NaN, y: 3 }, calibrated, true), undefined));
test('scaled canvas click uses intrinsic dimensions', () => {
  assert.deepEqual(pointerToCanvas(75, 120, { left: 25, top: 20, width: 100, height: 200 }, 400, 800), { x: 200, y: 400 });
});
test('zero-size or outside canvas clicks are ignored', () => {
  assert.equal(pointerToCanvas(0, 0, { left: 0, top: 0, width: 0, height: 100 }, 200, 200), undefined);
  assert.equal(pointerToCanvas(110, 10, { left: 0, top: 0, width: 100, height: 100 }, 200, 200), undefined);
});
