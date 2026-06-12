from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.app_automation.models import AppDevice, AppPackage
from apps.ui_automation.models import AIExecutionRecord
from apps.ui_automation.serializers import AIExecutionRecordSerializer


class AIExecutionRecordMobileSerializerTests(TestCase):
    def test_serializer_includes_mobile_target_fields(self):
        user = get_user_model().objects.create_user(
            username='ai_mobile_serializer_user',
            password='password123',
        )
        device = AppDevice.objects.create(
            device_id='emulator-5554',
            name='Pixel 8',
            status='online',
        )
        app_package = AppPackage.objects.create(
            name='测试应用',
            package_name='com.example.demo',
        )

        record = AIExecutionRecord.objects.create(
            case_name='Adhoc Task',
            task_description='打开测试应用并登录',
            execution_mode='mobile',
            status='running',
            executed_by=user,
            app_device=device,
            app_package=app_package,
        )

        data = AIExecutionRecordSerializer(instance=record).data

        assert data['execution_mode'] == 'mobile'
        assert data['app_device'] == device.id
        assert data['app_device_name'] == 'Pixel 8'
        assert data['app_device_serial'] == 'emulator-5554'
        assert data['app_package'] == app_package.id
        assert data['app_package_name'] == '测试应用'
        assert data['app_package_identifier'] == 'com.example.demo'
