"""Tolerant decoding of Nagios CGI response bodies.

Nagios CGIs pass plugin output through as raw bytes, with no declared
encoding: a Windows plugin on a French locale emits cp1252 (« » è) in
the middle of an otherwise UTF-8 body (ken #1104). Valid UTF-8 is kept
as-is; each undecodable span is read as cp1252, and bytes cp1252 leaves
undefined become U+FFFD — decoding a response never raises.
"""

import codecs

CP1252_FALLBACK = "nagioscli.cp1252_fallback"


def _cp1252_fallback(error: UnicodeError) -> tuple[str, int]:
    """Codec error handler: decode the offending byte span as cp1252."""
    if not isinstance(error, UnicodeDecodeError):
        raise error
    span = error.object[error.start : error.end]
    return span.decode("cp1252", errors="replace"), error.end


codecs.register_error(CP1252_FALLBACK, _cp1252_fallback)


def decode_body(raw: bytes) -> str:
    """Decode a Nagios CGI response body without ever raising."""
    return raw.decode("utf-8", errors=CP1252_FALLBACK)
