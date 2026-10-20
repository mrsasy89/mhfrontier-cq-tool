import assert from 'node:assert/strict';
import { test } from 'node:test';
import { wrapTranslation, translationEntries, translateEntries, validateEndpoint } from '../src/utils/questTranslation.ts';

test('wraps English at words without discarding text', () => {
  const r = wrapTranslation('A hunter needs your help today.', 12, 3);
  assert.equal(r.text, 'A hunter\nneeds your\nhelp today.');
  assert.equal(r.fits, true);
});
test('overflow is reported without truncation', () => {
  const r = wrapTranslation('one two three four five six', 9, 1);
  assert.equal(r.fits, false);
  assert.equal(r.text.replace(/\n/g, ' '), 'one two three four five six');
});
test('long words require review', () => assert.equal(wrapTranslation('supercalifragilistic', 5, 4).fits, false));
test('rejects invalid layout limits', () => assert.throws(() => wrapTranslation('x', 0, 3)));
test('preserves empty text', () => assert.equal(wrapTranslation('', 28, 1).text, ''));
test('preserves manually edited hard line breaks', () => {
  assert.equal(wrapTranslation('Hello\nHunter', 28, 2).text, 'Hello\nHunter');
});
test('preserves blank lines and normalizes Windows newlines', () => {
  const result = wrapTranslation('Hello\r\n\r\nHunter', 28, 3);
  assert.equal(result.text, 'Hello\n\nHunter');
  assert.equal(result.lines, 3);
});
test('selects Japanese fields and preserves existing English', () => {
  assert.deepEqual(translationEntries({ title: '狩猟', description: 'Already English' }, ['title', 'description'], true).map(x => x.field), ['title']);
});
test('optional replacement can include existing English', () => {
  assert.equal(translationEntries({ title: 'English' }, ['title'], false).length, 1);
});
test('empty fields are not submitted', () => assert.equal(translationEntries({ title: '' }, ['title'], false).length, 0));
test('accepts localhost HTTP and remote HTTPS', () => {
  assert.equal(validateEndpoint('http://localhost:5000/'), 'http://localhost:5000');
  assert.equal(validateEndpoint('https://translate.example.org/base/'), 'https://translate.example.org/base');
});
for (const url of ['http://remote.example.org', 'https://user:secret@example.org', 'file:///tmp/x', 'https://a.org/?key=secret', 'https://a.org/#secret']) {
  test(`rejects unsafe endpoint ${url}`, () => assert.throws(() => validateEndpoint(url)));
}
test('deduplicates identical text within a batch and reuses memory across calls', async () => {
  let count = 0;
  const request = async texts => { count += texts.length; return texts.map(() => 'Hunt the monster'); };
  const cache = new Map();
  const entries = [{ field: 'title', source: '狩猟' }, { field: 'description', source: '狩猟' }];
  const a = await translateEntries(entries, request, cache, 'local');
  const b = await translateEntries(entries, request, cache, 'local');
  assert.equal(count, 1);
  assert.equal(a[0].translation, b[1].translation);
});
test('provider-specific caches do not mix', async () => {
  let count = 0;
  const request = async () => { count++; return ['Hunt']; };
  const cache = new Map(), entries = [{ field: 'title', source: '狩猟' }];
  await translateEntries(entries, request, cache, 'a');
  await translateEntries(entries, request, cache, 'b');
  assert.equal(count, 2);
});
test('invalid responses do not enter translation memory', async () => {
  const cache = new Map();
  await assert.rejects(translateEntries([{ field: 'title', source: '狩猟' }], async () => [], cache, 'a'));
  assert.equal(cache.size, 0);
});
test('cancellation prevents further requests', async () => {
  await assert.rejects(translateEntries([{ field: 'title', source: '狩猟' }], async () => { throw Error('must not run'); }, new Map(), 'a', () => true), /cancel/i);
});
test('literal newlines from source determine description line budget', () => {
  const r = translationEntries({ description: '依頼\n説明\n終わり' }, ['description'], true);
  assert.equal(r[0].maxLines, 3);
});
