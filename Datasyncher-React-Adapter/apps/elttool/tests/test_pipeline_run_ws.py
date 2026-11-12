import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase, TestCase

from apps.elttool.websocket.auth import user_owns_pipeline_run
from apps.elttool.websocket.consumers.pipeline_run_status import (
    PipelineRunStatusConsumer,
)


class UserOwnsPipelineRunTests(SimpleTestCase):
    def test_unauthenticated_user_denied(self):
        self.assertFalse(user_owns_pipeline_run(None, 1))
        anon = SimpleNamespace(is_authenticated=False)
        self.assertFalse(user_owns_pipeline_run(anon, 1))

    @patch("apps.elttool.websocket.auth.user_belongs_to_company")
    @patch("apps.elttool.models.PipelineRun.objects")
    def test_owner_allowed(self, mock_objects, mock_belongs):
        run = SimpleNamespace(pipeline=SimpleNamespace(cmp_id=10))
        mock_objects.select_related.return_value.only.return_value.get.return_value = run
        user = SimpleNamespace(is_authenticated=True, is_superuser=False)
        mock_belongs.return_value = True
        self.assertTrue(user_owns_pipeline_run(user, 42))
        mock_belongs.assert_called_once_with(user, 10)

    @patch("apps.elttool.models.PipelineRun.objects")
    def test_missing_run_denied(self, mock_objects):
        from apps.elttool.models import PipelineRun

        mock_objects.select_related.return_value.only.return_value.get.side_effect = (
            PipelineRun.DoesNotExist()
        )
        user = SimpleNamespace(is_authenticated=True, is_superuser=False)
        self.assertFalse(user_owns_pipeline_run(user, 99))


class PipelineRunStatusConsumerAuthTests(unittest.IsolatedAsyncioTestCase):
    @patch(
        "apps.elttool.websocket.consumers.pipeline_run_status.user_owns_pipeline_run_async",
        new_callable=AsyncMock,
    )
    @patch(
        "apps.elttool.websocket.consumers.pipeline_run_status.authenticate_ws_user_async",
        new_callable=AsyncMock,
    )
    async def test_connect_closes_4403_when_not_owner(
        self, mock_auth, mock_owns,
    ):
        mock_auth.return_value = SimpleNamespace(is_authenticated=True)
        mock_owns.return_value = False
        consumer = PipelineRunStatusConsumer()
        consumer.scope = {"url_route": {"kwargs": {"run_id": "7"}}}
        consumer.channel_name = "test_channel"
        consumer.close = AsyncMock()
        await consumer.connect()
        consumer.close.assert_awaited_once_with(code=4403)

    @patch(
        "apps.elttool.websocket.consumers.pipeline_run_status.authenticate_ws_user_async",
        new_callable=AsyncMock,
    )
    async def test_connect_closes_4401_when_unauthenticated(self, mock_auth):
        mock_auth.return_value = SimpleNamespace(is_authenticated=False)
        consumer = PipelineRunStatusConsumer()
        consumer.scope = {"url_route": {"kwargs": {"run_id": "7"}}}
        consumer.close = AsyncMock()
        await consumer.connect()
        consumer.close.assert_awaited_once_with(code=4401)


class PipelineRunJobNameTests(SimpleTestCase):
    def test_parses_pipeline_run_job_prefix(self):
        from apps.elttool.services.pipeline_run_job_names import (
            pipeline_run_id_from_job_name,
        )

        self.assertEqual(
            pipeline_run_id_from_job_name("pipeline_run_14753_node_12"),
            14753,
        )
        self.assertIsNone(pipeline_run_id_from_job_name("migrate_batch_1"))
        self.assertIsNone(pipeline_run_id_from_job_name(None))


class PipelineRunWsPushSignalTests(SimpleTestCase):
    @patch("apps.elttool.services.pipeline_run_ws_push.schedule_pipeline_run_ws_push")
    def test_post_save_schedules_push_on_commit(self, mock_schedule):
        from apps.elttool.models import PipelineRun
        from apps.elttool.signals import push_pipeline_run_ws_on_save

        instance = SimpleNamespace(id=5, pipeline_id=9)
        with self.captureOnCommitCallbacks(execute=True):
            push_pipeline_run_ws_on_save(sender=PipelineRun, instance=instance)
        mock_schedule.assert_called_once_with(5, 9)


class MigrationRecordPipelineWsSignalTests(SimpleTestCase):
    @patch("apps.elttool.services.pipeline_run_ws_push.schedule_pipeline_run_ws_push")
    @patch("apps.elttool.websocket.ws_utils.push_admin_ops_snapshot")
    @patch(
        "apps.elttool.services.ops_monitoring_service.build_ops_snapshot",
        return_value={},
    )
    @patch("apps.elttool.models.PipelineRun.objects")
    def test_migration_record_schedules_pipeline_ws(
        self,
        mock_objects,
        _mock_ops,
        _mock_push_ops,
        mock_schedule,
    ):
        from apps.elttool.models import MigrationRecord
        from apps.elttool.signals import push_admin_ops_on_migration_status_change

        mock_objects.only.return_value.values_list.return_value.get.return_value = 9
        instance = SimpleNamespace(
            job_name="pipeline_run_5_node_3",
            status="I",
        )
        instance._old_status = "P"

        with self.captureOnCommitCallbacks(execute=True):
            push_admin_ops_on_migration_status_change(
                sender=MigrationRecord,
                instance=instance,
            )
        mock_schedule.assert_called_once_with(5, 9)
