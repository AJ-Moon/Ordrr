"""Database-enforced tenant isolation (RLS) proof.

Runs only when pointed at a Postgres database that has migration 0012 applied and
an `order_app`-style NOBYPASSRLS role available:

    RLS_OWNER_DSN   owner/superuser connection (used to seed; bypasses RLS)
    RLS_APP_DSN     application role connection (NOBYPASSRLS; RLS enforced)

Example (local):
    RLS_OWNER_DSN='postgresql://postgres@/order_test?host=/tmp&port=5599' \
    RLS_APP_DSN='postgresql://order_app:testpw@/order_test?host=/tmp&port=5599' \
    pytest tests/test_rls_isolation.py -q

When the variables are unset the test is skipped, so it never breaks default CI.
"""
import os
import unittest

import psycopg2

OWNER_DSN = os.getenv("RLS_OWNER_DSN")
APP_DSN = os.getenv("RLS_APP_DSN")

skip_reason = "RLS_OWNER_DSN and RLS_APP_DSN must be set to run RLS isolation tests"


@unittest.skipUnless(OWNER_DSN and APP_DSN, skip_reason)
class RlsIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner = psycopg2.connect(OWNER_DSN)
        cls.owner.autocommit = True
        with cls.owner.cursor() as cur:
            cur.execute(
                "INSERT INTO restaurants (id, name, slug, status) VALUES "
                "(901,'RLS-A','rls-a','active'),(902,'RLS-B','rls-b','active') "
                "ON CONFLICT (id) DO NOTHING"
            )
            cur.execute("DELETE FROM orders WHERE id IN ('RLS-A-1','RLS-B-1')")
            cur.execute(
                "INSERT INTO orders (id, restaurant_id, guest_name, total, status) VALUES "
                "('RLS-A-1',901,'A',1,'placed'),('RLS-B-1',902,'B',1,'placed')"
            )
        cls.app = psycopg2.connect(APP_DSN)
        cls.app.autocommit = True

    @classmethod
    def tearDownClass(cls):
        with cls.owner.cursor() as cur:
            cur.execute("DELETE FROM orders WHERE id IN ('RLS-A-1','RLS-B-1')")
            cur.execute("DELETE FROM restaurants WHERE id IN (901,902)")
        cls.app.close()
        cls.owner.close()

    def _ids(self, tenant=None, platform=False):
        with self.app.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.tenant_id', %s, false), set_config('app.is_platform', %s, false)",
                ("" if tenant is None else str(tenant), "on" if platform else "off"),
            )
            # Deliberately UNSCOPED: no WHERE clause. RLS must do the scoping.
            cur.execute("SELECT id FROM orders WHERE id IN ('RLS-A-1','RLS-B-1')")
            return {r[0] for r in cur.fetchall()}

    def test_tenant_sees_only_its_own_rows_unscoped(self):
        self.assertEqual(self._ids(tenant=901), {"RLS-A-1"})
        self.assertEqual(self._ids(tenant=902), {"RLS-B-1"})

    def test_no_context_denies_all(self):
        self.assertEqual(self._ids(tenant=None), set())

    def test_platform_sees_all(self):
        self.assertEqual(self._ids(platform=True), {"RLS-A-1", "RLS-B-1"})

    def test_cross_tenant_write_is_blocked(self):
        with self.app.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', '901', false), set_config('app.is_platform','off',false)")
            with self.assertRaises(psycopg2.errors.Error):
                cur.execute(
                    "INSERT INTO orders (id, restaurant_id, guest_name, total, status) "
                    "VALUES ('RLS-HACK',902,'M',1,'placed')"
                )
        # connection is aborted after the error; reset for any later tests
        self.app.rollback()


if __name__ == "__main__":
    unittest.main()
