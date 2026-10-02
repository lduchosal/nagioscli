// @ts-check
// Tolerant decoding of Nagios CGI response bodies, port of
// nagioscli/core/encoding.py (ken #1104): plugin output is passed through
// as raw bytes with no declared encoding, so a cp1252 plugin (« » è) can
// sit in an otherwise UTF-8 body. Valid UTF-8 is kept as-is, each byte
// outside a valid UTF-8 sequence is read as cp1252, and the five bytes
// cp1252 leaves undefined become U+FFFD — decoding never throws.

const REPLACEMENT = '�';

/** cp1252 code points of bytes 0x80-0x9F (0 = undefined in cp1252). */
const CP1252_HIGH = [
  0x20ac, 0, 0x201a, 0x0192, 0x201e, 0x2026, 0x2020, 0x2021, 0x02c6, 0x2030, 0x0160, 0x2039, 0x0152,
  0, 0x017d, 0, 0, 0x2018, 0x2019, 0x201c, 0x201d, 0x2022, 0x2013, 0x2014, 0x02dc, 0x2122, 0x0161,
  0x203a, 0x0153, 0, 0x017e, 0x0178,
];

const strictUtf8 = new TextDecoder('utf-8', { fatal: true });

/**
 * One byte read as cp1252.
 * @param {number} byte
 * @returns {string}
 */
function cp1252Char(byte) {
  if (byte < 0x80 || byte > 0x9f) return String.fromCharCode(byte);
  const code = CP1252_HIGH[byte - 0x80];
  return code ? String.fromCharCode(code) : REPLACEMENT;
}

/**
 * Length of the valid UTF-8 sequence starting at `i`, or 0 if invalid.
 * @param {Uint8Array} bytes
 * @param {number} i
 * @returns {number}
 */
function utf8Length(bytes, i) {
  const lead = bytes[i];
  let length = 0;
  if (lead >= 0xc2 && lead <= 0xdf) length = 2;
  else if (lead >= 0xe0 && lead <= 0xef) length = 3;
  else if (lead >= 0xf0 && lead <= 0xf4) length = 4;
  if (!length || i + length > bytes.length) return 0;
  try {
    strictUtf8.decode(bytes.subarray(i, i + length));
    return length;
  } catch {
    return 0;
  }
}

/**
 * Decode a Nagios CGI response body without ever throwing.
 * @param {Uint8Array} bytes
 * @returns {string}
 */
function decodeBody(bytes) {
  try {
    return strictUtf8.decode(bytes);
  } catch {
    // Mixed body: walk it, keeping valid UTF-8 sequences.
  }
  let out = '';
  let i = 0;
  while (i < bytes.length) {
    if (bytes[i] < 0x80) {
      out += String.fromCharCode(bytes[i]);
      i += 1;
      continue;
    }
    const length = utf8Length(bytes, i);
    if (length) {
      out += strictUtf8.decode(bytes.subarray(i, i + length));
      i += length;
    } else {
      out += cp1252Char(bytes[i]);
      i += 1;
    }
  }
  return out;
}

module.exports = { decodeBody };
