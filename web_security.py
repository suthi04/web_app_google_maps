"""Small, dependency-free web security helpers for the Flask application."""

import secrets

from flask import abort, request, session


CSRF_SESSION_KEY = "_csrf_token"
CSRF_FORM_KEY = "_csrf_token"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def csrf_token() -> str:
    """Return the session CSRF token, creating it on first use."""
    token = session.get(CSRF_SESSION_KEY)
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def protect_csrf() -> None:
    """Reject state-changing requests whose token does not match the session."""
    if request.method not in UNSAFE_METHODS:
        return

    expected = session.get(CSRF_SESSION_KEY)
    supplied = request.form.get(CSRF_FORM_KEY) or request.headers.get(CSRF_HEADER)
    if not (
        isinstance(expected, str)
        and isinstance(supplied, str)
        and expected
        and secrets.compare_digest(expected, supplied)
    ):
        abort(400, description="CSRF token is missing or invalid")


def add_security_headers(response):
    """Apply conservative browser headers without breaking the current UI."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    if request.endpoint != "static":
        response.headers.setdefault("Cache-Control", "no-store")
    return response
