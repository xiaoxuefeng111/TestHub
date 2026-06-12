from unittest import mock

from django.test import SimpleTestCase

from apps.app_automation.runners.ui_flow_runner import UiFlowRunner
from apps.app_automation.utils.ocr_helper import OCRRuntimeError


class UiFlowRunnerMobileActionsTests(SimpleTestCase):
    @mock.patch('apps.app_automation.runners.ui_flow_runner.touch')
    def test_tap_text_clicks_center_of_ocr_match(self, mock_touch):
        runner = UiFlowRunner(username='tester')
        fake_ocr = mock.Mock()
        fake_ocr.find_text.return_value = {
            'text': '登录',
            'center': (120, 240),
            'bbox': [(100, 220), (140, 220), (140, 260), (100, 260)],
        }
        runner._ocr_helper = fake_ocr

        runner._action_tap_text({'text': '登录', 'match_mode': 'exact'})

        fake_ocr.find_text.assert_called_once_with(
            '登录',
            match_mode='exact',
            region=None,
            index=0,
            min_confidence=0.3,
        )
        mock_touch.assert_called_once_with((120, 240))

    @mock.patch('apps.app_automation.runners.ui_flow_runner.touch')
    def test_tap_text_falls_back_to_ui_hierarchy_when_ocr_misses(self, mock_touch):
        runner = UiFlowRunner(username='tester', device_id='device-1')
        fake_ocr = mock.Mock()
        fake_ocr.find_text.return_value = None
        fake_hierarchy = mock.Mock()
        fake_hierarchy.find_text.return_value = {
            'text': '行情',
            'center': (540, 1998),
            'bbox': [(360, 1959), (720, 1959), (720, 2037), (360, 2037)],
            'source': 'ui_hierarchy',
        }
        runner._ocr_helper = fake_ocr
        runner._ui_hierarchy_helper = fake_hierarchy

        runner._action_tap_text({'text': '行情', 'match_mode': 'exact'})

        fake_ocr.find_text.assert_not_called()
        fake_hierarchy.find_text.assert_called_once_with(
            '行情',
            match_mode='exact',
            region=None,
            index=0,
        )
        mock_touch.assert_called_once_with((540, 1998))

    @mock.patch('apps.app_automation.runners.ui_flow_runner.touch')
    def test_tap_text_passes_negative_index_to_ui_hierarchy(self, mock_touch):
        runner = UiFlowRunner(username='tester', device_id='device-1')
        fake_ocr = mock.Mock()
        fake_ocr.find_text.return_value = None
        fake_hierarchy = mock.Mock()
        fake_hierarchy.find_text.return_value = {
            'text': '交易登录',
            'center': (540, 1820),
            'bbox': [(140, 1760), (940, 1760), (940, 1880), (140, 1880)],
            'source': 'ui_hierarchy',
        }
        runner._ocr_helper = fake_ocr
        runner._ui_hierarchy_helper = fake_hierarchy

        runner._action_tap_text({'text': '交易登录', 'match_mode': 'contains', 'index': -1})

        fake_ocr.find_text.assert_not_called()
        fake_hierarchy.find_text.assert_called_once_with(
            '交易登录',
            match_mode='contains',
            region=None,
            index=-1,
        )
        mock_touch.assert_called_once_with((540, 1820))

    @mock.patch('apps.app_automation.runners.ui_flow_runner.time.sleep', return_value=None)
    @mock.patch('apps.app_automation.runners.ui_flow_runner.touch')
    def test_tap_text_waits_for_post_wait_text_after_touch(self, mock_touch, _mock_sleep):
        runner = UiFlowRunner(username='tester')
        tap_match = {
            'text': '买入',
            'center': (540, 1520),
            'bbox': [(420, 1480), (660, 1480), (660, 1560), (420, 1560)],
        }
        next_match = {
            'text': '交易登录',
            'center': (540, 620),
            'bbox': [(260, 560), (820, 560), (820, 680), (260, 680)],
        }
        runner._find_text_match = mock.Mock(side_effect=[tap_match, None, next_match])

        runner._action_tap_text({
            'text': '买入',
            'match_mode': 'contains',
            'post_wait_text': '交易登录',
            'post_wait_timeout': 0.1,
            'post_wait_interval': 0.01,
        })

        self.assertEqual(runner._find_text_match.call_count, 3)
        mock_touch.assert_called_once_with((540, 1520))

    @mock.patch('apps.app_automation.runners.ui_flow_runner.time.sleep', return_value=None)
    @mock.patch('apps.app_automation.runners.ui_flow_runner.touch')
    def test_tap_text_waits_for_post_absent_text_after_touch(self, mock_touch, _mock_sleep):
        runner = UiFlowRunner(username='tester')
        match = {
            'text': '交易登录',
            'center': (540, 1820),
            'bbox': [(140, 1760), (940, 1760), (940, 1880), (140, 1880)],
        }
        runner._find_text_match = mock.Mock(side_effect=[match, match, None])

        runner._action_tap_text({
            'text': '交易登录',
            'match_mode': 'contains',
            'post_absent_text': '交易登录',
            'post_absent_timeout': 0.1,
            'post_absent_interval': 0.01,
        })

        self.assertEqual(runner._find_text_match.call_count, 3)
        mock_touch.assert_called_once_with((540, 1820))

    @mock.patch('apps.app_automation.runners.ui_flow_runner.airtest_text')
    def test_input_uses_text_field_when_value_missing(self, mock_airtest_text):
        runner = UiFlowRunner(username='tester')

        with mock.patch('apps.core.variable_resolver.resolve_variables', side_effect=lambda value: value):
            runner._action_input({'text': '111111'})

        mock_airtest_text.assert_called_once_with('111111')

    @mock.patch('apps.app_automation.runners.ui_flow_runner.airtest_text')
    def test_input_raises_clear_error_when_value_and_text_missing(self, mock_airtest_text):
        runner = UiFlowRunner(username='tester')

        with self.assertRaisesRegex(ValueError, 'input 动作缺少 value/text 参数'):
            runner._action_input({})

        mock_airtest_text.assert_not_called()

    def test_wait_text_raises_when_text_not_found_before_timeout(self):
        runner = UiFlowRunner(username='tester')
        fake_ocr = mock.Mock()
        fake_ocr.find_text.return_value = None
        runner._ocr_helper = fake_ocr

        with self.assertRaisesRegex(ValueError, '未找到目标文字'):
            runner._action_wait_text({'text': '提交', 'timeout': 0.1, 'interval': 0.01})

    def test_wait_text_raises_ocr_failure_instead_of_not_found(self):
        runner = UiFlowRunner(username='tester')
        fake_ocr = mock.Mock()
        fake_ocr.find_text.side_effect = OCRRuntimeError('EasyOCR 初始化失败: connection refused')
        runner._ocr_helper = fake_ocr

        with self.assertRaisesRegex(RuntimeError, 'OCR 文本定位失败.*EasyOCR 初始化失败'):
            runner._action_wait_text({'text': '买入', 'timeout': 0.1, 'interval': 0.01})

    def test_if_field_empty_executes_then_branch_when_helper_reports_empty(self):
        runner = UiFlowRunner(username='tester', device_id='device-1')
        fake_hierarchy = mock.Mock()
        fake_hierarchy.is_field_empty.return_value = True
        runner._ui_hierarchy_helper = fake_hierarchy

        runner._action_if({
            'condition': {'kind': 'field_empty', 'target': '资金账号'},
            'then_steps': [{'type': 'set_variable', 'name': 'branch', 'value': 'then'}],
            'else_steps': [{'type': 'set_variable', 'name': 'branch', 'value': 'else'}],
        })

        fake_hierarchy.is_field_empty.assert_called_once_with('资金账号')
        self.assertEqual(runner.context['local']['branch'], 'then')

    def test_if_field_empty_executes_else_branch_when_helper_reports_not_empty(self):
        runner = UiFlowRunner(username='tester', device_id='device-1')
        fake_hierarchy = mock.Mock()
        fake_hierarchy.is_field_empty.return_value = False
        runner._ui_hierarchy_helper = fake_hierarchy

        runner._action_if({
            'condition': {'kind': 'field_empty', 'target': '资金账号'},
            'then_steps': [{'type': 'set_variable', 'name': 'branch', 'value': 'then'}],
            'else_steps': [{'type': 'set_variable', 'name': 'branch', 'value': 'else'}],
        })

        fake_hierarchy.is_field_empty.assert_called_once_with('资金账号')
        self.assertEqual(runner.context['local']['branch'], 'else')

    def test_if_field_empty_falls_back_to_visible_label_when_helper_cannot_decide(self):
        runner = UiFlowRunner(username='tester', device_id='device-1')
        fake_hierarchy = mock.Mock()
        fake_hierarchy.is_field_empty.return_value = None
        fake_hierarchy.find_text.return_value = {
            'text': '资金账号',
            'center': (320, 240),
            'bbox': [(200, 200), (440, 200), (440, 280), (200, 280)],
            'source': 'ui_hierarchy',
        }
        runner._ui_hierarchy_helper = fake_hierarchy

        runner._action_if({
            'condition': {'kind': 'field_empty', 'target': '资金账号'},
            'then_steps': [{'type': 'set_variable', 'name': 'branch', 'value': 'then'}],
            'else_steps': [{'type': 'set_variable', 'name': 'branch', 'value': 'else'}],
        })

        fake_hierarchy.is_field_empty.assert_called_once_with('资金账号')
        fake_hierarchy.find_text.assert_called_once_with(
            '资金账号',
            match_mode='contains',
            region=None,
            index=0,
        )
        self.assertEqual(runner.context['local']['branch'], 'then')
