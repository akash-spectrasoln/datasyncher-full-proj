from django.test import SimpleTestCase

from apps.elttool.v1.ops_views import InternalAdminOpsPushAPIView
from apps.elttool.v1.proxy_agent_progress_views import (
    InternalProxyAgentMigrationProgressAPIView,
)
from apps.elttool.v1.views import (
    InternalCompanyConnectionsStatusPushAPIView,
    InternalConnectionActivityLogPushAPIView,
    InternalConnectionTableStatusPushAPIView,
    InternalMigrationStatusPushAPIView,
    InternalUpdateSchemaStatusPushAPIView,
    UserProfileAPIView,
)


class ApiThrottlingViewConfigTests(SimpleTestCase):
    def test_internal_push_views_are_not_throttled(self):
        views = [
            InternalMigrationStatusPushAPIView,
            InternalConnectionActivityLogPushAPIView,
            InternalConnectionTableStatusPushAPIView,
            InternalUpdateSchemaStatusPushAPIView,
            InternalCompanyConnectionsStatusPushAPIView,
            InternalAdminOpsPushAPIView,
            InternalProxyAgentMigrationProgressAPIView,
        ]
        for view_cls in views:
            with self.subTest(view=view_cls.__name__):
                self.assertEqual(getattr(view_cls, "throttle_classes", None), [])

    def test_user_profile_uses_profile_scope(self):
        self.assertEqual(UserProfileAPIView.throttle_scope, "profile")
        self.assertTrue(UserProfileAPIView.throttle_classes)
