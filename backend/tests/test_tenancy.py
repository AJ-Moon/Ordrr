import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from starlette.requests import Request

from dependencies.auth import (
    TenantContext,
    get_current_user,
    is_local_hostname,
    normalize_hostname,
    resolve_public_tenant,
)


def request_for(host: str) -> Request:
    return Request({"type": "http", "headers": [(b"host", host.encode())]})


class TenantResolutionTests(unittest.TestCase):
    def test_normalizes_hostname_and_port(self):
        self.assertEqual(normalize_hostname("Example.COM:443"), "example.com")
        self.assertEqual(normalize_hostname("[::1]:5005"), "::1")
        self.assertTrue(is_local_hostname("shop.localhost"))

    @patch("dependencies.auth._lookup_tenant", return_value=None)
    def test_unknown_production_domain_is_rejected(self, _lookup):
        with self.assertRaises(HTTPException) as raised:
            resolve_public_tenant(request_for("missing.example"), None)
        self.assertEqual(raised.exception.status_code, 404)

    def test_customer_token_cannot_cross_explicit_tenant(self):
        secret = "test-secret-that-is-long-enough"
        token = jwt.encode(
            {"id": "user-1", "email": "u@example.com", "restaurant_id": 1},
            secret,
            algorithm="HS256",
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        tenant = TenantContext(id=2, source="domain", hostname="two.example")
        with patch.dict(os.environ, {"JWT_SECRET": secret}):
            with self.assertRaises(HTTPException) as raised:
                get_current_user(credentials=credentials, tenant=tenant)
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
