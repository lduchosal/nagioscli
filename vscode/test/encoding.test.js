const test = require('node:test');
const assert = require('node:assert/strict');
const { decodeBody } = require('../src/encoding');

const bytes = (...parts) =>
  Buffer.concat(parts.map((p) => (typeof p === 'string' ? Buffer.from(p) : Buffer.from(p))));

test('valid UTF-8 is kept as-is', () => {
  assert.equal(decodeBody(Buffer.from('OK — «déjà» ✓ 𝄞')), 'OK — «déjà» ✓ 𝄞');
  assert.equal(decodeBody(Buffer.alloc(0)), '');
});

test('cp1252 bytes inside a UTF-8 body are read as cp1252 (ken #1104)', () => {
  // « é » € ’ as cp1252, next to genuine UTF-8 "✓".
  const body = bytes('a ', [0xab, 0x20, 0xe9, 0x20, 0xbb, 0x20, 0x80, 0x92], ' ✓');
  assert.equal(decodeBody(body), 'a « é » €’ ✓');
});

test('bytes cp1252 leaves undefined become U+FFFD, never throws', () => {
  assert.equal(decodeBody(bytes([0x81, 0x8d, 0x8f, 0x90, 0x9d])), '�'.repeat(5));
});

test('truncated and malformed multi-byte sequences fall back byte by byte', () => {
  // E2 82 (truncated €) at the end, then an overlong-looking F4 90 80 80.
  assert.equal(decodeBody(bytes('x', [0xe2, 0x82])), 'xâ‚');
  assert.equal(decodeBody(bytes([0xf4, 0x90, 0x80, 0x80])), 'ô�€€');
  assert.equal(decodeBody(bytes([0xc3, 0xa9, 0xff])), 'éÿ');
});
