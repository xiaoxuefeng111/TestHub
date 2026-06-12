from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.app_automation.models import AppDevice, AppPackage
from apps.requirement_analysis.models import AIModelConfig
from apps.ui_automation.mobile_agent import MobileFlowPlanner, run_mobile_execution
from apps.ui_automation.models import AIExecutionRecord


class MobileFlowPlannerFallbackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='planner_user',
            password='password123',
        )
        AIModelConfig.objects.create(
            name='Browser Use Text',
            model_type='other',
            role='browser_use_text',
            api_key='test-key',
            base_url='http://example.com/v1',
            model_name='gpt-5.4',
            is_active=True,
            created_by=self.user,
        )

    @mock.patch('apps.ui_automation.mobile_agent.ChatOpenAI')
    def test_generate_ui_flow_uses_semantic_plan_for_simple_tap_task(self, mock_chat_openai):
        planner = MobileFlowPlanner()
        flow = planner.generate_ui_flow('点击底部tab交易按钮', 'com.tdx.AndroidNewXN')

        self.assertEqual(
            [step['type'] for step in flow],
            ['start_app', 'wait_text', 'tap_text', 'screenshot'],
        )
        self.assertEqual(flow[0]['package_name'], 'com.tdx.AndroidNewXN')
        self.assertEqual(flow[1]['text'], '交易')
        self.assertEqual(flow[2]['text'], '交易')
        mock_chat_openai.return_value.invoke.assert_not_called()

    @mock.patch('apps.ui_automation.mobile_agent.ChatOpenAI')
    def test_generate_ui_flow_falls_back_to_heuristics_for_non_structured_task_when_llm_response_is_incompatible(self, mock_chat_openai):
        mock_chat_openai.return_value.invoke.side_effect = AttributeError("'str' object has no attribute 'model_dump'")

        planner = MobileFlowPlanner()
        flow = planner.generate_ui_flow('帮我随便看看这个应用', 'com.tdx.AndroidNewXN')

        self.assertEqual(
            [step['type'] for step in flow],
            ['start_app', 'screenshot'],
        )
        self.assertEqual(flow[0]['package_name'], 'com.tdx.AndroidNewXN')

    @mock.patch('apps.ui_automation.mobile_agent.ChatOpenAI')
    def test_normalize_ui_flow_copies_input_text_to_value(self, mock_chat_openai):
        planner = MobileFlowPlanner()

        flow = planner._normalize_ui_flow(
            [{'type': 'input', 'name': '输入登录密码', 'text': '111111'}],
            'com.example.demo',
        )

        input_step = next(step for step in flow if step['type'] == 'input')
        self.assertEqual(input_step['text'], '111111')
        self.assertEqual(input_step['value'], '111111')

    @mock.patch('apps.ui_automation.mobile_agent.ChatOpenAI')
    def test_generate_ui_flow_compiles_field_empty_condition_to_runtime_if(self, mock_chat_openai):
        planner = MobileFlowPlanner()
        task = (
            '1.打开com.tdx.AndroidNewXN应用\n'
            '2.并点击底部栏tab交易按钮,\n'
            '3.点击买入按钮，会弹出交易登陆界面\n'
            '4.没有资金账号的情况下，输入资金账号100000120，有的话就切换到密码输入框\n'
            '5.输入密码111111\n'
            '6.点击交易登录按钮'
        )

        flow = planner.generate_ui_flow(task, 'com.tdx.AndroidNewXN')

        self.assertEqual(flow[0]['type'], 'start_app')
        self.assertTrue(any(step['type'] == 'if' for step in flow))
        self.assertTrue(any(step['type'] == 'wait_text' and step.get('text') == '交易登录' for step in flow))

        conditional_step = next(step for step in flow if step['type'] == 'if')
        self.assertEqual(conditional_step['condition']['kind'], 'field_empty')
        self.assertEqual(conditional_step['condition']['target'], '资金账号')
        self.assertTrue(
            any(step['type'] == 'input' and step.get('value') == '100000120' for step in conditional_step['then_steps'])
        )
        self.assertTrue(
            any(step['type'] == 'tap_text' and step.get('text') == '密码' for step in conditional_step['else_steps'])
        )
        self.assertTrue(
            any(
                step['type'] == 'tap_text'
                and step.get('text') == '买入'
                and step.get('post_wait_text') == '交易登录'
                for step in flow
            )
        )
        self.assertTrue(
            any(
                step['type'] == 'tap_text'
                and step.get('text') == '交易登录'
                and step.get('index') == -1
                and step.get('post_absent_text') is None
                and step.get('region') == '0,600,3000,4000'
                for step in flow
            )
        )
        mock_chat_openai.return_value.invoke.assert_not_called()

    @mock.patch('apps.ui_automation.mobile_agent.ChatOpenAI')
    def test_generate_ui_flow_rejects_unsupported_structured_task_without_llm_fallback(self, mock_chat_openai):
        planner = MobileFlowPlanner()
        task = '1.打开com.tdx.AndroidNewXN应用\n2.自己判断该点哪个按钮'

        with self.assertRaises(ValueError) as raised:
            planner.generate_ui_flow(task, 'com.tdx.AndroidNewXN')

        self.assertIn('未支持的结构化步骤', str(raised.exception))
        mock_chat_openai.return_value.invoke.assert_not_called()


class RunMobileExecutionDeviceReadyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='mobile_agent_user',
            password='password123',
        )
        self.device = AppDevice.objects.create(
            device_id='emulator-5554',
            name='Pixel 8',
            status='online',
        )
        self.app_package = AppPackage.objects.create(
            name='Demo App',
            package_name='com.example.demo',
        )
        self.record = AIExecutionRecord.objects.create(
            case_name='Mobile flow case',
            task_description='Open app and capture screen',
            app_device=self.device,
            app_package=self.app_package,
            execution_mode='mobile',
            status='running',
            executed_by=self.user,
        )

    @mock.patch('apps.ui_automation.mobile_agent.UiFlowRunner')
    @mock.patch('apps.ui_automation.mobile_agent.MobileFlowPlanner')
    @mock.patch('apps.ui_automation.mobile_agent.AirtestBase')
    def test_run_mobile_execution_checks_device_ready_before_running_flow(self, mock_airtest_cls, mock_planner_cls, mock_runner_cls):
        mock_planner_cls.return_value.generate_ui_flow.return_value = [
            {'type': 'start_app', 'name': 'Open app', 'package_name': 'com.example.demo'}
        ]
        airtest = mock_airtest_cls.return_value
        airtest.setup_airtest.return_value = True
        airtest.ensure_device_ready.return_value = True
        mock_runner_cls.return_value.run.return_value = {'total': 1, 'passed': 1, 'failed': 0}

        run_mobile_execution(self.record.id)

        airtest.ensure_device_ready.assert_called_once_with()
        mock_runner_cls.return_value.run.assert_called_once()

    @mock.patch('apps.ui_automation.mobile_agent.UiFlowRunner')
    @mock.patch('apps.ui_automation.mobile_agent.MobileFlowPlanner')
    @mock.patch('apps.ui_automation.mobile_agent.AirtestBase')
    def test_run_mobile_execution_continues_when_device_ready_check_returns_false(self, mock_airtest_cls, mock_planner_cls, mock_runner_cls):
        mock_planner_cls.return_value.generate_ui_flow.return_value = [
            {'type': 'start_app', 'name': 'Open app', 'package_name': 'com.example.demo'}
        ]
        airtest = mock_airtest_cls.return_value
        airtest.setup_airtest.return_value = True
        airtest.ensure_device_ready.return_value = False
        mock_runner_cls.return_value.run.return_value = {'total': 1, 'passed': 1, 'failed': 0}

        run_mobile_execution(self.record.id)
        self.record.refresh_from_db()

        airtest.ensure_device_ready.assert_called_once_with()
        mock_runner_cls.return_value.run.assert_called_once()
        self.assertEqual(self.record.status, 'passed')
        self.assertTrue(self.record.logs)
