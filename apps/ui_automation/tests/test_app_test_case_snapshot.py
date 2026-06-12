from django.test import SimpleTestCase

from apps.ui_automation.app_test_case_snapshot import sanitize_ui_flow_snapshot


class SanitizeUiFlowSnapshotTests(SimpleTestCase):
    def test_keeps_only_executable_step_fields(self):
        cleaned = sanitize_ui_flow_snapshot([
            {
                'type': 'tap_text',
                'name': '点击登录',
                'text': '登录',
                'match_mode': 'contains',
                'timeout': 8,
                'debug_screenshot': '/tmp/screen.png',
                'actual_coordinate': [12, 34],
            }
        ])

        self.assertEqual(
            cleaned,
            [
                {
                    'type': 'tap_text',
                    'name': '点击登录',
                    'text': '登录',
                    'match_mode': 'contains',
                    'timeout': 8,
                }
            ],
        )

    def test_recursively_sanitizes_conditional_steps(self):
        cleaned = sanitize_ui_flow_snapshot([
            {
                'type': 'if',
                'name': '判断账号是否为空',
                'condition': {'kind': 'field_empty', 'target': '资金账号', 'runtime_hit': True},
                'then_steps': [
                    {'type': 'input', 'value': '100000120', 'ocr_result': 'noise'},
                ],
                'else_steps': [
                    {'type': 'tap_text', 'text': '密码', 'elapsed_ms': 120},
                ],
            }
        ])

        self.assertEqual(
            cleaned,
            [
                {
                    'type': 'if',
                    'name': '判断账号是否为空',
                    'condition': {'kind': 'field_empty', 'target': '资金账号'},
                    'then_steps': [{'type': 'input', 'value': '100000120'}],
                    'else_steps': [{'type': 'tap_text', 'text': '密码'}],
                }
            ],
        )

    def test_rejects_non_list_snapshot(self):
        with self.assertRaises(ValueError):
            sanitize_ui_flow_snapshot({'type': 'screenshot'})
