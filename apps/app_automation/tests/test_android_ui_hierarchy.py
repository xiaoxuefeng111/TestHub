from unittest import mock

from django.test import SimpleTestCase

from apps.app_automation.utils.android_ui_hierarchy import AndroidUiHierarchyHelper


SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="com.example:id/tab_holder" class="android.widget.LinearLayout" clickable="false" enabled="true" bounds="[0,1953][1080,2037]">
    <node index="1" text="" resource-id="com.example:id/id_tab_quote" class="android.widget.LinearLayout" clickable="true" enabled="true" bounds="[360,1959][720,2037]">
      <node index="0" text="" resource-id="com.example:id/id_tab_quote_img" class="android.widget.ImageButton" clickable="false" enabled="true" bounds="[495,1966][585,2037]" />
      <node index="1" text="行情" resource-id="" class="android.widget.TextView" clickable="false" enabled="true" bounds="[0,0][0,0]" />
    </node>
  </node>
</hierarchy>
"""

EMPTY_FIELD_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="root" class="android.widget.LinearLayout" clickable="false" enabled="true" bounds="[0,0][1080,2400]">
    <node index="0" text="资金账号" resource-id="" class="android.widget.TextView" clickable="false" enabled="true" bounds="[48,240][240,312]" />
    <node index="1" text="" hint-text="资金账号" resource-id="com.example:id/account_input" class="android.widget.EditText" clickable="true" enabled="true" focused="false" bounds="[260,220][980,330]" />
  </node>
</hierarchy>
"""

FILLED_FIELD_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="root" class="android.widget.LinearLayout" clickable="false" enabled="true" bounds="[0,0][1080,2400]">
    <node index="0" text="资金账号" resource-id="" class="android.widget.TextView" clickable="false" enabled="true" bounds="[48,240][240,312]" />
    <node index="1" text="100000120" hint-text="资金账号" resource-id="com.example:id/account_input" class="android.widget.EditText" clickable="true" enabled="true" focused="true" bounds="[260,220][980,330]" />
  </node>
</hierarchy>
"""

DUPLICATE_LOGIN_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="root" class="android.widget.FrameLayout" clickable="false" enabled="true" bounds="[0,0][1080,2400]">
    <node index="0" text="交易登录" resource-id="com.example:id/login_title" class="android.widget.TextView" clickable="false" enabled="true" bounds="[360,360][720,430]" />
    <node index="1" text="" resource-id="com.example:id/login_button" class="android.widget.Button" clickable="true" enabled="true" bounds="[140,1760][940,1880]">
      <node index="0" text="交易登录" resource-id="" class="android.widget.TextView" clickable="false" enabled="true" bounds="[0,0][0,0]" />
    </node>
  </node>
</hierarchy>
"""


class AndroidUiHierarchyHelperTests(SimpleTestCase):
    @mock.patch('apps.app_automation.utils.android_ui_hierarchy.subprocess.run')
    def test_run_adb_command_uses_utf8_when_text_mode_enabled(self, mock_run):
        helper = AndroidUiHierarchyHelper(device_id='device-1', adb_path='adb')

        helper._run_adb_command(['shell', 'echo', 'ok'], text=True)

        _, kwargs = mock_run.call_args
        self.assertTrue(kwargs['text'])
        self.assertEqual(kwargs['encoding'], 'utf-8')
        self.assertEqual(kwargs['errors'], 'ignore')

    def test_find_text_uses_clickable_ancestor_bounds_for_zero_sized_text_node(self):
        helper = AndroidUiHierarchyHelper(device_id='device-1', adb_path='adb')

        with mock.patch.object(helper, 'dump_hierarchy_xml', return_value=SAMPLE_XML):
            match = helper.find_text('行情', match_mode='exact')

        self.assertIsNotNone(match)
        self.assertEqual(match['center'], (540, 1998))
        self.assertEqual(match['bbox'], [(360, 1959), (720, 1959), (720, 2037), (360, 2037)])
        self.assertEqual(match['resource_id'], 'com.example:id/id_tab_quote')
        self.assertEqual(match['source'], 'ui_hierarchy')

    def test_is_field_empty_returns_true_for_empty_edit_text(self):
        helper = AndroidUiHierarchyHelper(device_id='device-1', adb_path='adb')

        with mock.patch.object(helper, 'dump_hierarchy_xml', return_value=EMPTY_FIELD_XML):
            result = helper.is_field_empty('资金账号')

        self.assertTrue(result)

    def test_is_field_empty_returns_false_for_filled_edit_text(self):
        helper = AndroidUiHierarchyHelper(device_id='device-1', adb_path='adb')

        with mock.patch.object(helper, 'dump_hierarchy_xml', return_value=FILLED_FIELD_XML):
            result = helper.is_field_empty('资金账号')

        self.assertFalse(result)

    def test_find_text_supports_negative_index_for_last_duplicate_candidate(self):
        helper = AndroidUiHierarchyHelper(device_id='device-1', adb_path='adb')

        with mock.patch.object(helper, 'dump_hierarchy_xml', return_value=DUPLICATE_LOGIN_XML):
            match = helper.find_text('交易登录', match_mode='contains', index=-1)

        self.assertIsNotNone(match)
        self.assertEqual(match['center'], (540, 1820))
        self.assertEqual(match['resource_id'], 'com.example:id/login_button')
        self.assertEqual(match['source'], 'ui_hierarchy')
