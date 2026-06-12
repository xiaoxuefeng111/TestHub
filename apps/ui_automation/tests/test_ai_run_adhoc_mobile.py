from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.app_automation.models import AppDevice, AppPackage
from apps.ui_automation.models import AIExecutionRecord
from apps.ui_automation.views import AIExecutionRecordViewSet


class AIExecutionRecordRunAdhocMobileTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            username='ai_mobile_run_user',
            password='password123',
        )
        self.device = AppDevice.objects.create(
            device_id='emulator-5554',
            name='Pixel 8',
            status='online',
        )
        self.app_package = AppPackage.objects.create(
            name='测试应用',
            package_name='com.example.demo',
        )
        self.view = AIExecutionRecordViewSet.as_view({'post': 'run_adhoc'})

    @mock.patch('threading.Thread')
    def test_run_adhoc_mobile_creates_record_and_dispatches_thread(self, mock_thread):
        request = self.factory.post(
            '/api/ui-automation/ai-execution-records/run_adhoc/',
            {
                'task_description': '打开应用并点击登录',
                'execution_mode': 'mobile',
                'device_id': self.device.id,
                'app_package_id': self.app_package.id,
            },
            format='json',
        )
        force_authenticate(request, user=self.user)

        response = self.view(request)
        response.render()

        self.assertEqual(response.status_code, 200)
        record = AIExecutionRecord.objects.get(id=response.data['execution_id'])
        self.assertEqual(record.execution_mode, 'mobile')
        self.assertEqual(record.app_device_id, self.device.id)
        self.assertEqual(record.app_package_id, self.app_package.id)
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def test_run_adhoc_mobile_requires_device_and_package(self):
        request = self.factory.post(
            '/api/ui-automation/ai-execution-records/run_adhoc/',
            {
                'task_description': '打开应用并点击登录',
                'execution_mode': 'mobile',
            },
            format='json',
        )
        force_authenticate(request, user=self.user)

        response = self.view(request)
        response.render()

        self.assertEqual(response.status_code, 400)
        self.assertIn('device_id', str(response.data['error']))
