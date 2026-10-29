const assert = require('node:assert/strict');
const test = require('node:test');
const { convertFileSrc } = require('@tauri-apps/api/tauri');

test('map asset URLs work without the helper absent from Tauri 1.2.4', () => {
  // Tauri 1.2.4 provides an API object but no convertFileSrc helper.
  const oldWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
  const oldNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { __TAURI__: {} } });
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { userAgent: 'Windows' } });
  try {
    const path = 'C:\\local maps\\Siege Fortress Day.png';
    assert.equal(convertFileSrc(path), `https://asset.localhost/${encodeURIComponent(path)}`);
  } finally {
    for (const [key, descriptor] of [['window', oldWindow], ['navigator', oldNavigator]]) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
});
