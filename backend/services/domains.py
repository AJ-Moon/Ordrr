"""Custom-domain ownership verification.

Two supported proofs (either succeeds):
  1. DNS TXT record at  _order-verify.<domain>  whose value equals the token.
  2. HTTP file at        http(s)://<domain>/.well-known/order-verify  containing the token.

Verification is deliberately dependency-light and fails closed: a domain is only
marked verified once a real proof is observed, never on insert.
"""
from __future__ import annotations

import os
import secrets
from typing import Tuple

import httpx

TXT_PREFIX = "_order-verify"
WELL_KNOWN_PATH = "/.well-known/order-verify"


def generate_verification_token() -> str:
    return "order-verify-" + secrets.token_urlsafe(24)


def dns_instructions(domain: str, token: str) -> dict:
    """Human-facing instructions shown in the super-admin UI."""
    target = os.getenv("PLATFORM_DOMAIN_TARGET", "cname.order.example")
    return {
        "txtRecord": {"host": f"{TXT_PREFIX}.{domain}", "type": "TXT", "value": token},
        "routing": {
            "host": domain,
            "type": "CNAME",
            "value": target,
            "note": "Root domains that cannot CNAME should use an A/ALIAS record to the "
                    "platform IP provided by support.",
        },
        "httpFallback": {
            "url": f"https://{domain}{WELL_KNOWN_PATH}",
            "body": token,
        },
    }


def _check_dns_txt(domain: str, token: str) -> bool:
    try:
        import dns.resolver  # type: ignore
    except Exception:
        return False
    try:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = 5.0
        answers = resolver.resolve(f"{TXT_PREFIX}.{domain}", "TXT")
        for record in answers:
            value = b"".join(getattr(record, "strings", []) or []).decode("utf-8", "ignore")
            if not value:
                value = str(record).strip('"')
            if value.strip() == token:
                return True
    except Exception:
        return False
    return False


def _check_http_wellknown(domain: str, token: str) -> bool:
    for scheme in ("https", "http"):
        try:
            resp = httpx.get(f"{scheme}://{domain}{WELL_KNOWN_PATH}", timeout=5.0,
                             follow_redirects=False)
            if resp.status_code == 200 and token in resp.text.strip():
                return True
        except Exception:
            continue
    return False


def verify_domain_ownership(domain: str, token: str) -> Tuple[bool, str]:
    """Return (verified, method). method is 'dns_txt' | 'http' | ''."""
    if not token:
        return False, ""
    if _check_dns_txt(domain, token):
        return True, "dns_txt"
    if _check_http_wellknown(domain, token):
        return True, "http"
    return False, ""
