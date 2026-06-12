from django.test import SimpleTestCase

from apps.ui_automation.mobile_plan_validator import MobilePlanValidator
from apps.ui_automation.mobile_semantic_parser import MobileSemanticParser


class MobileSemanticParserTests(SimpleTestCase):
    def setUp(self):
        self.parser = MobileSemanticParser()
        self.validator = MobilePlanValidator()

    def test_parse_login_condition_task_to_safe_dsl(self):
        task = (
            '1.打开com.tdx.AndroidNewXN应用\n'
            '2.并点击底部栏tab交易按钮,\n'
            '3.点击买入按钮，会弹出交易登录界面\n'
            '4.没有资金账号的情况下，输入资金账号100000120，有的话就切换到密码输入框\n'
            '5.输入密码111111\n'
            '6.点击交易登录按钮'
        )

        plan = self.parser.parse(task, package_name='com.tdx.AndroidNewXN')

        self.assertEqual(plan['version'], '1.0')
        self.assertEqual(plan['mode'], 'safe')
        self.assertIsNone(plan.get('unsafe_reason'))
        self.assertEqual(plan.get('unsupported_steps'), [])

        steps = plan['steps']
        self.assertEqual(steps[0]['type'], 'start_app')
        self.assertEqual(steps[0]['package_name'], 'com.tdx.AndroidNewXN')
        self.assertTrue(any(step['type'] == 'tap_text' and step['target'] == '交易' for step in steps))
        self.assertTrue(any(step['type'] == 'tap_text' and step['target'] == '买入' for step in steps))
        self.assertTrue(any(step['type'] == 'wait_text' and step['target'] == '交易登录' for step in steps))
        self.assertFalse(any(step['type'] == 'focus_field' and step['target'] == '点击底部' for step in steps))

        conditional = next(step for step in steps if step['type'] == 'conditional')
        self.assertEqual(conditional['condition']['kind'], 'field_empty')
        self.assertEqual(conditional['condition']['target'], '资金账号')
        self.assertEqual(conditional['if_true'][1]['value'], '100000120')
        self.assertEqual(conditional['if_true'][1]['target'], '资金账号')
        self.assertEqual(conditional['if_false'][0]['type'], 'focus_field')
        self.assertEqual(conditional['if_false'][0]['target'], '密码')

        password_input = next(
            step for step in steps
            if step['type'] == 'input' and step['target'] == '密码'
        )
        self.assertEqual(password_input['value'], '111111')
        self.assertTrue(any(step['type'] == 'tap_text' and step['target'] == '交易登录' for step in steps))

    def test_parse_bottom_tab_tap_step_does_not_create_fake_focus_field(self):
        plan = self.parser.parse(
            '1.打开com.tdx.AndroidNewXN应用\n2.并点击底部栏tab交易按钮',
            package_name='com.tdx.AndroidNewXN',
        )

        steps = plan['steps']
        self.assertTrue(any(step['type'] == 'tap_text' and step['target'] == '交易' for step in steps))
        self.assertFalse(any(step['type'] == 'focus_field' and step['target'] == '点击底部' for step in steps))

    def test_parse_expected_page_text_to_wait_step(self):
        plan = self.parser.parse(
            '1.点击买入按钮，会弹出交易登录界面',
            package_name='com.tdx.AndroidNewXN',
        )

        steps = plan['steps']
        self.assertTrue(any(step['type'] == 'tap_text' and step['target'] == '买入' for step in steps))
        self.assertTrue(any(step['type'] == 'wait_text' and step['target'] == '交易登录' for step in steps))

    def test_parse_expected_page_text_normalizes_登陆_to_登录(self):
        plan = self.parser.parse(
            '1.点击买入按钮，会弹出交易登陆界面',
            package_name='com.tdx.AndroidNewXN',
        )

        steps = plan['steps']
        self.assertTrue(any(step['type'] == 'wait_text' and step['target'] == '交易登录' for step in steps))
        self.assertFalse(any(step['type'] == 'wait_text' and step['target'] == '交易登陆' for step in steps))

    def test_validator_rejects_missing_literal_and_key_action(self):
        task = (
            '1.点击买入按钮\n'
            '2.输入密码111111\n'
            '3.点击交易登录按钮'
        )
        invalid_plan = {
            'version': '1.0',
            'mode': 'safe',
            'steps': [
                {'type': 'tap_text', 'target': '买入'},
                {'type': 'input', 'target': '密码', 'value': '******', 'clear_first': True},
            ],
        }

        errors = self.validator.validate(task, invalid_plan)

        self.assertTrue(any('111111' in error for error in errors))
        self.assertTrue(any('交易登录' in error for error in errors))

    def test_validator_rejects_input_without_target(self):
        task = '1.输入密码111111'
        invalid_plan = {
            'version': '1.0',
            'mode': 'safe',
            'steps': [
                {'type': 'input', 'value': '111111', 'clear_first': True},
            ],
        }

        errors = self.validator.validate(task, invalid_plan)

        self.assertTrue(any('input 动作缺少 target' in error for error in errors))

    def test_validator_rejects_unsupported_structured_step(self):
        task = '1.打开com.tdx.AndroidNewXN应用\n2.自己判断该点哪个按钮'

        plan = self.parser.parse(task, package_name='com.tdx.AndroidNewXN')
        errors = self.validator.validate(task, plan)

        self.assertEqual(plan['mode'], 'unsafe')
        self.assertEqual(plan['unsupported_steps'], ['自己判断该点哪个按钮'])
        self.assertTrue(any('未支持的结构化步骤' in error for error in errors))
