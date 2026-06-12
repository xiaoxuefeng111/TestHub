import base64
import subprocess
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.app_automation.constants import DeviceStatus
from apps.app_automation.models import AppDevice
from apps.app_automation.views.device_views import AppDeviceViewSet

PNG_BYTES = b'\x89PNG\r\n\x1a\nmock-png-data'


class AppDeviceScreenshotTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            username='app_device_view_user',
            password='password123',
        )
        self.view = AppDeviceViewSet.as_view({'post': 'screenshot'})

    def _create_device(self, **kwargs):
        defaults = {
            'device_id': 'AKC0218326001973',
            'name': 'Pixel 7',
            'status': DeviceStatus.ONLINE,
        }
        defaults.update(kwargs)
        return AppDevice.objects.create(**defaults)

    def _post_screenshot(self, device):
        request = self.factory.post(f'/api/app-automation/devices/{device.pk}/screenshot/')
        force_authenticate(request, user=self.user)
        response = self.view(request, pk=device.pk)
        response.render()
        return response

    @mock.patch('apps.app_automation.views.device_views.get_adb_path', return_value='adb')
    @mock.patch('apps.app_automation.views.device_views.subprocess.run')
    def test_screenshot_returns_conflict_when_device_is_offline_in_adb(self, mock_run, _mock_adb_path):
        device = self._create_device(status=DeviceStatus.ONLINE)
        mock_run.return_value = subprocess.CompletedProcess(
            args=['adb', 'devices', '-l'],
            returncode=0,
            stdout='List of devices attached\nAKC0218326001973 offline transport_id:7\n',
            stderr='',
        )

        response = self._post_screenshot(device)

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.data['success'])
        self.assertIn('offline', response.data['msg'])
        device.refresh_from_db()
        self.assertEqual(device.status, DeviceStatus.OFFLINE)
        mock_run.assert_called_once()

    @mock.patch('apps.app_automation.views.device_views.get_adb_path', return_value='adb')
    @mock.patch('apps.app_automation.views.device_views.subprocess.run')
    def test_screenshot_returns_forbidden_when_device_is_unauthorized(self, mock_run, _mock_adb_path):
        device = self._create_device(status=DeviceStatus.ONLINE)
        mock_run.return_value = subprocess.CompletedProcess(
            args=['adb', 'devices', '-l'],
            returncode=0,
            stdout='List of devices attached\nAKC0218326001973 unauthorized usb:1-1 transport_id:7\n',
            stderr='',
        )

        response = self._post_screenshot(device)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data['success'])
        self.assertIn('授权', response.data['msg'])
        device.refresh_from_db()
        self.assertEqual(device.status, DeviceStatus.OFFLINE)
        mock_run.assert_called_once()

    @mock.patch('apps.app_automation.views.device_views.get_adb_path', return_value='adb')
    @mock.patch('apps.app_automation.views.device_views.subprocess.run')
    def test_screenshot_returns_conflict_when_device_is_not_listed_by_adb(self, mock_run, _mock_adb_path):
        device = self._create_device(status=DeviceStatus.ONLINE)
        mock_run.return_value = subprocess.CompletedProcess(
            args=['adb', 'devices', '-l'],
            returncode=0,
            stdout='List of devices attached\nemulator-5554 device product:sdk_gphone64 model:sdk_gphone64\n',
            stderr='',
        )

        response = self._post_screenshot(device)

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.data['success'])
        self.assertIn('未发现', response.data['msg'])
        device.refresh_from_db()
        self.assertEqual(device.status, DeviceStatus.OFFLINE)
        mock_run.assert_called_once()

    @mock.patch('apps.app_automation.views.device_views.get_adb_path', return_value='adb')
    @mock.patch('apps.app_automation.views.device_views.subprocess.run')
    def test_screenshot_returns_conflict_when_device_goes_offline_during_exec_out(self, mock_run, _mock_adb_path):
        device = self._create_device(status=DeviceStatus.ONLINE)
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=['adb', 'devices', '-l'],
                returncode=0,
                stdout='List of devices attached\nAKC0218326001973 device usb:1-1 transport_id:7\n',
                stderr='',
            ),
            subprocess.CalledProcessError(
                returncode=1,
                cmd=['adb', '-s', device.device_id, 'exec-out', 'screencap', '-p'],
                stderr=b'error: device offline',
            ),
        ]

        response = self._post_screenshot(device)

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.data['success'])
        self.assertIn('offline', response.data['msg'])
        device.refresh_from_db()
        self.assertEqual(device.status, DeviceStatus.OFFLINE)
        self.assertEqual(mock_run.call_count, 2)

    @mock.patch('apps.app_automation.views.device_views.get_adb_path', return_value='adb')
    @mock.patch('apps.app_automation.views.device_views.subprocess.run')
    @mock.patch('builtins.open', new_callable=mock.mock_open, read_data=PNG_BYTES)
    @mock.patch('tempfile.mkstemp', return_value=(123, r'C:\\temp\\testhub.png'))
    @mock.patch('os.remove')
    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('os.close')
    def test_screenshot_falls_back_to_remote_file_pull_when_exec_out_returns_windows_error(
        self,
        mock_close,
        _mock_exists,
        mock_remove,
        _mock_mkstemp,
        mock_open_file,
        mock_run,
        _mock_adb_path,
    ):
        device = self._create_device(status=DeviceStatus.ONLINE)
        local_path = r'C:\\temp\\testhub.png'
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=['adb', 'devices', '-l'],
                returncode=0,
                stdout='List of devices attached\nAKC0218326001973 device usb:1-1 transport_id:7\n',
                stderr='',
            ),
            subprocess.CalledProcessError(
                returncode=4294967295,
                cmd=['adb', '-s', device.device_id, 'exec-out', 'screencap', '-p'],
                stderr=b'',
                output=b'',
            ),
            subprocess.CompletedProcess(
                args=['adb', '-s', device.device_id, 'shell', 'screencap', '-p', '/data/local/tmp/testhub.png'],
                returncode=0,
                stdout='',
                stderr='',
            ),
            subprocess.CompletedProcess(
                args=['adb', '-s', device.device_id, 'pull', '/data/local/tmp/testhub.png', local_path],
                returncode=0,
                stdout='1 file pulled\n',
                stderr='',
            ),
            subprocess.CompletedProcess(
                args=['adb', '-s', device.device_id, 'shell', 'rm', '-f', '/data/local/tmp/testhub.png'],
                returncode=0,
                stdout='',
                stderr='',
            ),
        ]

        response = self._post_screenshot(device)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertTrue(response.data['data']['content'].startswith('data:image/png;base64,'))
        encoded = response.data['data']['content'].split(',', 1)[1]
        self.assertEqual(base64.b64decode(encoded), PNG_BYTES)

        command_sequence = [call.args[0] for call in mock_run.call_args_list]
        self.assertEqual(command_sequence[3][:4], ['adb', '-s', device.device_id, 'pull'])
        self.assertEqual(command_sequence[-1][:5], ['adb', '-s', device.device_id, 'shell', 'rm'])
        mock_close.assert_called_once_with(123)
        mock_open_file.assert_called_once_with(local_path, 'rb')
        mock_remove.assert_called_once_with(local_path)
        self.assertEqual(mock_run.call_count, 5)
