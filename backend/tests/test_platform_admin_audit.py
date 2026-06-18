"""Regression tests: every privileged platform-admin (super-admin) action must
write an audit_logs row. Guards against unlogged tenant provisioning, deletion,
admin removal, tenant rename, and admin-password reset (impersonation)."""
import unittest
from collections import deque
from contextlib import contextmanager
from unittest.mock import patch

from routers import platform_admin as PA


class FakeCursor:
    def __init__(self, fetchone_script):
        self.executed = []
        self._fetchone = deque(fetchone_script)

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return self._fetchone.popleft() if self._fetchone else (1,)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        pass


def audited_actions(cursor):
    """Return the `action` value of every INSERT INTO audit_logs call."""
    actions = []
    for query, params in cursor.executed:
        if "INSERT INTO audit_logs" in query and params:
            actions.append(params[3])  # (tenant_id, actor_type, actor_id, action, ...)
    return actions


class PlatformAdminAuditTests(unittest.TestCase):
    ADMIN = {"id": "pa-1", "email": "ops@order.dev"}

    def _run(self, fetchone_script, call):
        cur = FakeCursor(fetchone_script)

        @contextmanager
        def fake_get_db():
            yield FakeConn(cur)

        with patch.object(PA, "get_db", fake_get_db):
            call()
        return audited_actions(cur)

    def test_reset_admin_password_is_audited(self):
        body = PA.ResetAdminPasswordRequest(admin_id="adm-9", new_password="longenough1")
        actions = self._run([(1,)], lambda: PA.reset_admin_password(1, body, self.ADMIN))
        self.assertIn("admin.password_reset", actions)

    def test_delete_tenant_is_audited(self):
        actions = self._run([("Demo Co",)], lambda: PA.delete_tenant(7, self.ADMIN))
        self.assertIn("tenant.deleted", actions)

    def test_update_tenant_is_audited(self):
        body = PA.UpdateTenantRequest(name="Renamed Co")
        actions = self._run([(1,)], lambda: PA.update_tenant(3, body, self.ADMIN))
        self.assertIn("tenant.updated", actions)

    def test_remove_restaurant_admin_is_audited(self):
        actions = self._run([(1,)], lambda: PA.remove_restaurant_admin(3, "adm-2", self.ADMIN))
        self.assertIn("admin.removed", actions)

    def test_create_tenant_is_audited(self):
        body = PA.CreateTenantRequest(
            name="New Co", slug="new-co", primary_domain="new.example",
            admin_email="a@new.example", admin_password="longenough1", admin_name="Ada",
        )
        # SELECT slug -> none (free), INSERT restaurants RETURNING -> id, SELECT admin -> none
        actions = self._run([None, (42,), None], lambda: PA.create_tenant(body, self.ADMIN))
        self.assertIn("tenant.created", actions)


if __name__ == "__main__":
    unittest.main()
