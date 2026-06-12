from unittest import mock

from django.test import SimpleTestCase

from apps.app_automation.utils.airtest_base import AirtestBase


class AirtestBaseTests(SimpleTestCase):
    @mock.patch('apps.app_automation.utils.airtest_base.AndroidUiHierarchyHelper.get_adb_path', return_value='adb')
    @mock.patch('apps.app_automation.utils.airtest_base.init_device')
    def test_init_device_with_timeout_passes_configured_adb_path(self, mock_init_device, _mock_get_adb_path):
        airtest = AirtestBase(device_id='device-1', username='tester')

        success = airtest._init_device_with_timeout(platform='Android', uuid='device-1', timeout=1)

        self.assertTrue(success)
        mock_init_device.assert_called_once_with(platform='Android', uuid='device-1', adb_path='adb')

    @mock.patch('apps.app_automation.utils.airtest_base.time.sleep', return_value=None)
    @mock.patch('apps.app_automation.utils.airtest_base.AndroidUiHierarchyHelper.get_adb_path', return_value='adb')
    def test_ensure_device_ready_wakes_and_unlocks_when_needed(self, _mock_get_adb_path, _mock_sleep):
        with mock.patch.object(AirtestBase, '_get_device_state', create=True) as mock_get_state, \
             mock.patch.object(AirtestBase, '_wake_device', create=True) as mock_wake, \
             mock.patch.object(AirtestBase, '_unlock_device', create=True) as mock_unlock:
            mock_get_state.side_effect = [
                {'is_awake': False, 'is_locked': True, 'focused_package': 'com.android.systemui'},
                {'is_awake': True, 'is_locked': True, 'focused_package': 'com.android.systemui'},
                {'is_awake': True, 'is_locked': False, 'focused_package': 'com.example.demo'},
            ]
            airtest = AirtestBase(device_id='device-1', username='tester')
            airtest.is_connected = True

            self.assertTrue(airtest.ensure_device_ready())
            mock_wake.assert_called_once_with()
            mock_unlock.assert_called_once_with()
            self.assertEqual(mock_get_state.call_count, 3)

    @mock.patch('apps.app_automation.utils.airtest_base.AndroidUiHierarchyHelper.get_adb_path', return_value='adb')
    def test_extract_focused_package_treats_status_bar_as_systemui(self, _mock_get_adb_path):
        airtest = AirtestBase(device_id='device-1', username='tester')

        focused_package = airtest._extract_focused_package(
            'mCurrentFocus=Window{31d3eb1 u0 StatusBar}\n'
            'mFocusedApp=AppWindowToken{2fddec6 token=Token{3380b71 ActivityRecord{2fdde87 u0 com.tdx.AndroidNewXN/tdx.com.tdxsdkdemomode2.HomeActivity t456}}}'
        )

        self.assertEqual(focused_package, 'com.android.systemui')

    @mock.patch('apps.app_automation.utils.airtest_base.time.sleep', return_value=None)
    @mock.patch('apps.app_automation.utils.airtest_base.AndroidUiHierarchyHelper.get_adb_path', return_value='adb')
    def test_ensure_device_ready_returns_false_when_unlock_fails(self, _mock_get_adb_path, _mock_sleep):
        with mock.patch.object(AirtestBase, '_get_device_state', create=True) as mock_get_state, \
             mock.patch.object(AirtestBase, '_wake_device', create=True) as mock_wake, \
             mock.patch.object(AirtestBase, '_unlock_device', create=True) as mock_unlock:
            mock_get_state.side_effect = [
                {'is_awake': True, 'is_locked': True, 'focused_package': 'com.android.systemui'},
                {'is_awake': True, 'is_locked': True, 'focused_package': 'com.android.systemui'},
            ]
            airtest = AirtestBase(device_id='device-1', username='tester')
            airtest.is_connected = True

            self.assertFalse(airtest.ensure_device_ready(max_unlock_attempts=1))
            mock_wake.assert_not_called()
            mock_unlock.assert_called_once_with()
            self.assertEqual(mock_get_state.call_count, 2)
