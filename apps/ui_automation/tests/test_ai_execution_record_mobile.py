from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.app_automation.models import AppTestCase
from apps.ui_automation.models import AIExecutionRecord
from apps.ui_automation.serializers import AIExecutionRecordSerializer


class AIExecutionRecordMobileSerializerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='ai_mobile_serializer_user',
            password='password123',
        )

    def test_model_defaults_for_app_test_case_snapshot_fields(self):
        record = AIExecutionRecord.objects.create(
            case_name='Adhoc Task',
            task_description='打开应用并截图',
            execution_mode='mobile',
            status='pending',
            executed_by=self.user,
        )

        self.assertEqual(record.ui_flow_snapshot, [])
        self.assertIsNone(record.saved_app_test_case)

    def test_serializer_exposes_save_state_for_successful_mobile_record(self):
        record = AIExecutionRecord.objects.create(
            case_name='Adhoc Task',
            task_description='打开应用并截图',
            execution_mode='mobile',
            status='passed',
            ui_flow_snapshot=[
                {'type': 'start_app', 'package_name': 'com.example.demo'},
                {'type': 'screenshot', 'name': '结果截图'},
            ],
            executed_by=self.user,
        )

        data = AIExecutionRecordSerializer(instance=record).data

        self.assertIsNone(data['saved_app_test_case'])
        self.assertIsNone(data['saved_app_test_case_name'])
        self.assertTrue(data['can_save_as_app_test_case'])
        self.assertNotIn('ui_flow_snapshot', data)

    def test_serializer_reports_existing_saved_app_test_case(self):
        app_test_case = AppTestCase.objects.create(
            name='已保存用例',
            ui_flow=[{'type': 'screenshot'}],
            created_by=self.user,
        )
        record = AIExecutionRecord.objects.create(
            case_name='Adhoc Task',
            task_description='打开应用并截图',
            execution_mode='mobile',
            status='passed',
            ui_flow_snapshot=[{'type': 'screenshot'}],
            saved_app_test_case=app_test_case,
            executed_by=self.user,
        )

        data = AIExecutionRecordSerializer(instance=record).data

        self.assertEqual(data['saved_app_test_case'], app_test_case.id)
        self.assertEqual(data['saved_app_test_case_name'], '已保存用例')
        self.assertFalse(data['can_save_as_app_test_case'])

    def test_serializer_disallows_failed_record_save(self):
        record = AIExecutionRecord.objects.create(
            case_name='Adhoc Task',
            task_description='打开应用并截图',
            execution_mode='mobile',
            status='failed',
            ui_flow_snapshot=[{'type': 'screenshot'}],
            executed_by=self.user,
        )

        data = AIExecutionRecordSerializer(instance=record).data

        self.assertFalse(data['can_save_as_app_test_case'])
