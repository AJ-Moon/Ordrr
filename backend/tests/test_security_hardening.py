import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

import dependencies.auth as auth
from dependencies.auth import (
    TenantContext,
    _allow_dev_tenant_header,
    _enforce_token_tenant,
    _is_production,
    request_hostname,
    resolve_public_tenant,
)


def request_for(headers: dict) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw})


class ProductionSafetyTests(unittest.TestCase):
    def test_production_detected_from_either_var(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "ENVIRONMENT": ""}, clear=False):
            self.assertTrue(_is_production())
        with patch.dict(os.environ, {"APP_ENV": "", "ENVIRONMENT": "production"}, clear=False):
            self.assertTrue(_is_production())
        with patch.dict(os.environ, {"APP_ENV": "development", "ENVIRONMENT": "development"}, clear=False):
            self.assertFalse(_is_production())

    def test_dev_header_hard_disabled_in_production(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "ALLOW_DEV_TENANT_HEADER": "true"}, clear=False):
            self.assertFalse(_allow_dev_tenant_header())

    def test_production_rejects_local_host_and_dev_header(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                resolve_public_tenant(request_for({"host": "localhost"}), "1")
        self.assertEqual(raised.exception.status_code, 404)

    def test_production_rejects_empty_host(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                resolve_public_tenant(request_for({"host": ""}), None)
        self.assertEqual(raised.exception.status_code, 404)


class ForwardedHostTests(unittest.TestCase):
    def test_ignores_forwarded_host_when_not_trusted(self):
        with patch.dict(os.environ, {"TRUST_FORWARDED_HOST": "false"}, clear=False):
            host = request_hostname(request_for({"host": "backend.internal", "x-forwarded-host": "xyz.com"}))
        self.assertEqual(host, "backend.internal")

    def test_uses_forwarded_host_when_trusted(self):
        with patch.dict(os.environ, {"TRUST_FORWARDED_HOST": "true"}, clear=False):
            host = request_hostname(request_for({"host": "backend.internal", "x-forwarded-host": "XYZ.com, proxy"}))
        self.assertEqual(host, "xyz.com")


class TokenTenantBindingTests(unittest.TestCase):
    def test_cross_tenant_rejected_on_domain_source(self):
        tenant = TenantContext(id=2, source="domain")
        with self.assertRaises(HTTPException) as raised:
            _enforce_token_tenant({"restaurant_id": 1}, tenant)
        self.assertEqual(raised.exception.status_code, 403)

    def test_dev_default_tolerated_only_in_dev(self):
        tenant = TenantContext(id=2, source="development_default")
        with patch.dict(os.environ, {"APP_ENV": "development", "ALLOW_DEV_TENANT_HEADER": "true"}, clear=False):
            self.assertEqual(_enforce_token_tenant({"restaurant_id": 1}, tenant), 1)
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            with self.assertRaises(HTTPException):
                _enforce_token_tenant({"restaurant_id": 1}, tenant)


class SuspendedTenantTests(unittest.TestCase):
    def test_suspended_tenant_storefront_blocked(self):
        # Simulate the DB returning a suspended restaurant row.
        class _Cur:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def execute(self, *a, **k): self._row = (1, "X", "x", "suspended")
            def fetchone(self): return self._row
        class _Conn:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def cursor(self): return _Cur()
            def rollback(self): pass
        from contextlib import contextmanager

        @contextmanager
        def fake_db():
            yield _Conn()

        with patch.object(auth, "get_db", fake_db):
            with self.assertRaises(HTTPException) as raised:
                auth._lookup_tenant(hostname="xyz.com")
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
