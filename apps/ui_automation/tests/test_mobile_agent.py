from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.app_automation.models import AppPackage
from apps.ui_automation.models import AIExecutionRecord


class RunMobileExecutionSnapshotTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='mobile_snapshot_user',
            password='password123',
        )
        self.app_package = AppPackage.objects.create(
            name='Demo App',
            package_name='com.example.demo',
        )
        self.record = AIExecutionRecord.objects.create(
            case_name='Mobile flow case',
            task_description='Open app and capture screen',
            app_package=self.app_package,
            execution_mode='mobile',
            status='running',
            executed_by=self.user,
        )

    @mock.patch('apps.ui_automation.mobile_agent.UiFlowRunner')
    @mock.patch('apps.ui_automation.mobile_agent.MobileFlowPlanner')
    def test_run_mobile_execution_persists_ui_flow_snapshot_before_runner_starts(self, mock_planner_cls, mock_runner_cls):
        from apps.ui_automation.mobile_agent import run_mobile_execution

        ui_flow = [
            {'type': 'start_app', 'name': 'Open app', 'package_name': 'com.example.demo'},
            {'type': 'screenshot', 'name': 'Result screenshot'},
        ]
        mock_planner_cls.return_value.generate_ui_flow.return_value = ui_flow

        def assert_snapshot_saved(*args, **kwargs):
            self.record.refresh_from_db()
            self.assertEqual(self.record.ui_flow_snapshot, ui_flow)
            return {'total': 2, 'passed': 2, 'failed': 0}

        mock_runner_cls.return_value.run.side_effect = assert_snapshot_saved

        run_mobile_execution(self.record.id)
        self.record.refresh_from_db()

        mock_runner_cls.return_value.run.assert_called_once()
        self.assertEqual(self.record.ui_flow_snapshot, ui_flow)
        self.assertEqual(self.record.status, 'passed')
