from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.app_automation.models import AppTestCase
from apps.ui_automation.models import AIExecutionRecord
from apps.ui_automation.views import AIExecutionRecordViewSet


class SaveAIExecutionAsAppTestCaseTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            username='save_app_case_user',
            password='password123',
        )
        self.view = AIExecutionRecordViewSet.as_view({'post': 'save_as_app_test_case'})

    def _post(self, record, payload=None):
        request = self.factory.post(
            f'/api/ui-automation/ai-execution-records/{record.id}/save_as_app_test_case/',
            payload or {},
            format='json',
        )
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=record.id)
        response.render()
        return response

    def test_successful_mobile_record_creates_app_test_case(self):
        record = AIExecutionRecord.objects.create(
            case_name='Adhoc Task',
            task_description='打开应用并点击登录',
            execution_mode='mobile',
            status='passed',
            ui_flow_snapshot=[
                {'type': 'start_app', 'package_name': 'com.example.demo', 'debug': 'drop'},
                {'type': 'tap_text', 'text': '登录', 'actual_coordinate': [100, 200]},
            ],
            executed_by=self.user,
        )

        response = self._post(record, {'name': '登录用例', 'description': 'AI 跑通后保存'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['already_saved'])
        app_case = AppTestCase.objects.get(id=response.data['app_test_case']['id'])
        self.assertEqual(app_case.name, '登录用例')
        self.assertEqual(app_case.created_by, self.user)
        self.assertIsNone(app_case.project)
        self.assertIsNone(app_case.app_package)
        self.assertEqual(app_case.variables, [])
        self.assertEqual(
            app_case.ui_flow,
            [
                {'type': 'start_app', 'package_name': 'com.example.demo'},
                {'type': 'tap_text', 'text': '登录'},
            ],
        )
        self.assertIn('AI 跑通后保存', app_case.description)
        self.assertIn(f'AIExecutionRecord #{record.id}', app_case.description)
        record.refresh_from_db()
        self.assertEqual(record.saved_app_test_case_id, app_case.id)

    def test_repeated_save_returns_existing_app_test_case(self):
        app_case = AppTestCase.objects.create(
            name='已有用例',
            ui_flow=[{'type': 'screenshot'}],
            created_by=self.user,
        )
        record = AIExecutionRecord.objects.create(
            case_name='Adhoc Task',
            task_description='打开应用并截图',
            execution_mode='mobile',
            status='passed',
            ui_flow_snapshot=[{'type': 'screenshot'}],
            saved_app_test_case=app_case,
            executed_by=self.user,
        )

        response = self._post(record, {'name': '新名字'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['already_saved'])
        self.assertEqual(response.data['app_test_case']['id'], app_case.id)
        self.assertEqual(AppTestCase.objects.count(), 1)

    def test_failed_record_cannot_be_saved(self):
        record = AIExecutionRecord.objects.create(
            case_name='Adhoc Task',
            task_description='打开应用并截图',
            execution_mode='mobile',
            status='failed',
            ui_flow_snapshot=[{'type': 'screenshot'}],
            executed_by=self.user,
        )

        response = self._post(record, {'name': '失败用例'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(AppTestCase.objects.count(), 0)

    def test_record_without_snapshot_cannot_be_saved(self):
        record = AIExecutionRecord.objects.create(
            case_name='Adhoc Task',
            task_description='打开应用并截图',
            execution_mode='mobile',
            status='passed',
            executed_by=self.user,
        )

        response = self._post(record, {'name': '空快照用例'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(AppTestCase.objects.count(), 0)

    def test_name_is_required_for_first_save(self):
        record = AIExecutionRecord.objects.create(
            case_name='Adhoc Task',
            task_description='打开应用并截图',
            execution_mode='mobile',
            status='passed',
            ui_flow_snapshot=[{'type': 'screenshot'}],
            executed_by=self.user,
        )

        response = self._post(record, {'name': '   '})

        self.assertEqual(response.status_code, 400)
        self.assertIn('name', str(response.data))
