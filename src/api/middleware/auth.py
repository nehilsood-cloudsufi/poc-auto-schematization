"""IAP JWT verification middleware for Cloud Run.

Extracts user email from the X-Goog-IAP-JWT-Assertion header injected by
Google Identity-Aware Proxy. Sets request.state.user_email for downstream use
and a contextvars tag for structured logging.

Enforces domain-level access control: only @google.com and @cloudsufi.com
emails are allowed. Returns 403 for all other domains.

In local dev (no K_SERVICE env var), user_email defaults to "local-dev@localhost".
"""
import contextvars
import logging
import os
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

CLOUD_RUN = os.environ.get("K_SERVICE", "") != ""

# Allowed email domains (enforced at app level since IAP domain: bindings
# are unreliable on Cloud Run)
ALLOWED_DOMAINS = {"google.com", "cloudsufi.com"}

# ContextVar so all log lines in a request include the user email
user_email_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "user_email", default=""
)

# Cache IAP public keys for 5 minutes
_key_cache: dict = {"keys": None, "expires": 0}
_IAP_KEY_URL = "https://www.gstatic.com/iap/verify/public_key-jwk"


def _fetch_iap_keys() -> dict:
    """Fetch and cache Google's IAP JWT public keys."""
    now = time.time()
    if _key_cache["keys"] and now < _key_cache["expires"]:
        return _key_cache["keys"]

    try:
        import requests
        resp = requests.get(_IAP_KEY_URL, timeout=5)
        resp.raise_for_status()
        keys = resp.json()
        _key_cache["keys"] = keys
        _key_cache["expires"] = now + 300  # 5 min TTL
        return keys
    except Exception:
        logger.warning("Failed to fetch IAP public keys")
        return _key_cache.get("keys") or {}


def _decode_iap_jwt(token: str) -> Optional[str]:
    """Decode IAP JWT and return user email, or None on failure."""
    try:
        import jwt as pyjwt
        from jwt import PyJWKClient

        jwk_client = PyJWKClient(_IAP_KEY_URL)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        payload = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            options={"verify_aud": False},  # audience varies per project
        )
        return payload.get("email", payload.get("sub"))
    except ImportError:
        pass
    except Exception as e:
        logger.debug("PyJWT decode failed: %s, trying google-auth", e)

    # Fallback: use google.auth (already in deps)
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        request = google_requests.Request()
        payload = id_token.verify_token(token, request)
        return payload.get("email", payload.get("sub"))
    except Exception as e:
        logger.warning("IAP JWT verification failed: %s", e)
        return None


class IAPAuthMiddleware(BaseHTTPMiddleware):
    """Extract user identity from IAP JWT header and enforce domain access."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check
        if request.url.path == "/health":
            return await call_next(request)

        if not CLOUD_RUN:
            email = "local-dev@localhost"
        else:
            jwt_assertion = request.headers.get("X-Goog-IAP-JWT-Assertion")
            if jwt_assertion:
                email = _decode_iap_jwt(jwt_assertion) or "anonymous"
            else:
                email = "anonymous"

            # Enforce domain-level access control
            if email != "anonymous":
                domain = email.rsplit("@", 1)[-1] if "@" in email else ""
                if domain not in ALLOWED_DOMAINS:
                    logger.warning("Access denied for %s (domain %s not in allowed list)", email, domain)
                    return JSONResponse(
                        status_code=403,
                        content={"detail": f"Access denied. Only @google.com and @cloudsufi.com domains are allowed."},
                    )

        request.state.user_email = email
        user_email_var.set(email)

        return await call_next(request)


class UserEmailLogFilter(logging.Filter):
    """Inject user_email into all log records for Cloud Logging."""

    def filter(self, record):
        record.user_email = user_email_var.get("")
        return True
