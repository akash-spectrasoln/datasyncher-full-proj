"""Tests for pipeline run revoke API and service."""

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.elttool.models import (
    Company,
    Connection,
    DestinationConfig,
    DestinationModel,
    MigrationRecord,
    Pipeline,
    PipelineRun,
    Plan,
    Role,
    SourceConfig,
    SourceModel,
    User,
)
from apps.elttool.services.pipeline_run_revoke_service import revoke_pipeline_run
from apps.elttool.tasks.pipeline_tasks import _TERMINAL_RUN_STATUSES


class PipelineRunRevokeTests(TestCase):
    def setUp(self):
        Plan.objects.get_or_create(plan_id=1, defaults={"name": "Free", "pod_count": 2})
        role, _ = Role.objects.get_or_create(role_name="Administrator", defaults={})
        now = timezone.now()
        self.company = Company.objects.create(
            cmp_name="Revoke Co",
            start_date=now,
            end_date=now,
        )
        self.user = User.objects.create(
            company_email="revoke@example.com",
            cmp=self.company,
            first_name="Rev",
            last_name="Oke",
            roles=role,
        )
        self.source_model = SourceModel.objects.create(
            name="MicrosoftDynamics365_FO",
            display_name="Dynamics",
        )
        self.dest_model = DestinationModel.objects.create(name="Databricks")
        self.source_config = SourceConfig.objects.create(
            name="src",
            cmp=self.company,
            src=self.source_model,
            is_active=True,
        )
        self.dest_config = DestinationConfig.objects.create(
            name="dest",
            cmp=self.company,
            dst=self.dest_model,
            is_active=True,
        )
        self.connection = Connection.objects.create(
            cmp=self.company,
            src_config=self.source_config,
            dst_config=self.dest_config,
            dst_schema="LANDING",
            status="A",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_terminal_run_statuses_include_revoked(self):
        self.assertIn("revoked", _TERMINAL_RUN_STATUSES)

    @patch(
        "apps.elttool.v1.pipeline_views._teardown_pipeline_flow_fleet",
        autospec=True,
    )
    @patch(
        "apps.elttool.services.pipeline_notifications.send_pipeline_flow_notification",
        autospec=True,
    )
    @patch(
        "apps.elttool.v1.pipeline_views._pipeline_run_participating_node_ids",
        return_value=[5],
    )
    def test_revoke_queued_run_marks_revoked(self, _participating, _notify, _teardown):
        pipeline = Pipeline.objects.create(
            cmp=self.company,
            name="revoke-test",
            status="active",
            validated_graph={
                "fingerprint": "fp",
                "node_ids": [5],
                "nodes": [{"node_id": 5}],
            },
            created_by=self.user,
        )
        run = PipelineRun.objects.create(
            pipeline=pipeline,
            status="queued",
            metadata={
                "graph_source": "validated",
                "waiting_for_capacity": True,
            },
        )
        result = revoke_pipeline_run(run)
        self.assertEqual(result["status"], "revoked")
        run.refresh_from_db()
        self.assertEqual(run.status, "revoked")
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(run.metadata["nodes"]["5"]["status"], "revoked")
        _teardown.assert_called_once_with(run.id)

    @patch(
        "apps.elttool.v1.pipeline_views._teardown_pipeline_flow_fleet",
        autospec=True,
    )
    @patch(
        "apps.elttool.services.celery_inspect_service.get_migration_celery_app",
    )
    @patch(
        "apps.elttool.services.pipeline_notifications.send_pipeline_flow_notification",
        autospec=True,
    )
    @patch(
        "apps.elttool.v1.pipeline_views._pipeline_run_participating_node_ids",
        return_value=[5],
    )
    def test_revoke_running_run_revokes_active_migration_records(
        self, _participating, _notify, mock_celery_app, _teardown,
    ):
        mock_celery_app.return_value.control.revoke.return_value = None
        pipeline = Pipeline.objects.create(
            cmp=self.company,
            name="revoke-mr",
            status="active",
            created_by=self.user,
        )
        run = PipelineRun.objects.create(
            pipeline=pipeline,
            status="running",
            metadata={
                "nodes": {
                    "5": {
                        "status": "running",
                        "connection_id": self.connection.connection_id,
                        "migration_session_id": 99,
                        "pipeline_job_name": f"pipeline_run_999_node_5",
                    }
                }
            },
        )
        job_name = f"pipeline_run_{run.id}_node_5"
        mr = MigrationRecord.objects.create(
            connection=self.connection,
            migration_session_id=99,
            table_name="acct",
            job_name=job_name,
            task_id="child-task-1",
            status="in_progress",
        )
        result = revoke_pipeline_run(run)
        self.assertEqual(result["status"], "revoked")
        mr.refresh_from_db()
        self.assertEqual(mr.status, "revoked")
        mock_celery_app.return_value.control.revoke.assert_called_once()
        run.refresh_from_db()
        self.assertEqual(run.metadata["nodes"]["5"]["status"], "revoked")

    @patch("apps.elttool.services.pipeline_run_revoke_service.redis")
    def test_revoke_purges_redis_orchestration_keys(self, mock_redis_module):
        mock_client = mock_redis_module.from_url.return_value
        from apps.elttool.services.pipeline_run_revoke_service import (
            _collect_run_job_names,
            _purge_job_orchestration_redis,
        )

        names = _collect_run_job_names(
            42,
            {"7": {"pipeline_job_name": "pipeline_run_42_node_7"}},
        )
        self.assertIn("pipeline_run_42", names)
        self.assertIn("pipeline_run_42_node_7", names)
        _purge_job_orchestration_redis(mock_client, names)
        self.assertTrue(mock_client.delete.called)

    def test_revoke_completed_run_is_noop(self):
        pipeline = Pipeline.objects.create(
            cmp=self.company,
            name="done",
            status="active",
            created_by=self.user,
        )
        run = PipelineRun.objects.create(
            pipeline=pipeline,
            status="completed",
            finished_at=timezone.now(),
        )
        result = revoke_pipeline_run(run)
        self.assertEqual(result["status"], "noop")
