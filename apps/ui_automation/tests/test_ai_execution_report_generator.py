from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ui_automation.models import AIExecutionRecord
from apps.ui_automation.reports import AIExecutionReportGenerator


class AIExecutionReportGeneratorCompatibilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ai_report_compat_user",
            password="password123",
        )

    def _create_record(self, steps_completed):
        return AIExecutionRecord.objects.create(
            case_name="Mobile Report",
            task_description="Open app and enter trade page",
            execution_mode="mobile",
            status="passed",
            executed_by=self.user,
            duration=12.0,
            logs="[Step 1]\n执行: 点击[1]\n[Step 2]\n执行: 输入: '123456'\n",
            planned_tasks=[
                {"id": 1, "description": "启动应用", "status": "completed"},
                {"id": 2, "description": "输入口令", "status": "completed"},
            ],
            steps_completed=steps_completed,
        )

    def test_summary_report_supports_string_steps_completed(self):
        record = self._create_record(["启动同花顺应用", "点击交易入口"])

        report = AIExecutionReportGenerator(record).generate_summary_report()

        self.assertEqual(report["metrics"]["total_steps"], 2)
        self.assertEqual(report["gif_path"], None)

    def test_detailed_report_supports_string_steps_completed(self):
        record = self._create_record(["启动同花顺应用", "点击交易入口"])

        report = AIExecutionReportGenerator(record).generate_detailed_report()

        self.assertEqual(report["detailed_steps"][0]["step_number"], 1)
        self.assertEqual(report["detailed_steps"][0]["action"], "启动同花顺应用")
        self.assertEqual(report["detailed_steps"][1]["step_number"], 2)

    def test_detailed_report_supports_history_step_shape(self):
        record = self._create_record(
            [
                {"step": 0, "action": "启动同花顺应用"},
                {"step": 1, "action": "点击交易入口"},
            ]
        )

        report = AIExecutionReportGenerator(record).generate_detailed_report()

        self.assertEqual(
            [step["step_number"] for step in report["detailed_steps"]],
            [1, 2],
        )

    def test_performance_report_supports_string_steps_completed(self):
        record = self._create_record(["启动同花顺应用", "点击交易入口"])

        report = AIExecutionReportGenerator(record).generate_performance_report()

        self.assertEqual(report["metrics"]["total_steps"], 2)
        self.assertEqual(report["step_performance"][0]["action"], "启动同花顺应用")
