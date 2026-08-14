"""Anonymous, browser-scoped identity helpers.

The browser stores a random bearer token in an HttpOnly cookie.  The database
only stores a one-way digest of that token, so leaked database rows cannot be
turned directly into working browser credentials.
"""

import hashlib
import re
import secrets


COOKIE_NAME = "insightreview_device"
COOKIE_MAX_AGE_SECONDS = 400 * 24 * 60 * 60
_TOKEN_RE = re.compile(r"^[0-9a-f]{64}$")


def is_valid_token(token: object) -> bool:
    return isinstance(token, str) and _TOKEN_RE.fullmatch(token) is not None


def new_token() -> str:
    return secrets.token_hex(32)


def owner_id_from_token(token: str) -> str:
    """Return the stable, non-reversible database owner id for a valid token."""
    if not is_valid_token(token):
        raise ValueError("Invalid anonymous device token")
    digest = hashlib.sha256(
        ("insightreview-device-v1:" + token).encode("ascii")
    ).hexdigest()
    return "device:" + digest
