from pathlib import Path

from django.conf import settings

from apps.app_automation.executors.test_executor import AppTestExecutor


def test_app_executor_targets_only_app_flow_test():
    executor = AppTestExecutor(base_path=Path(settings.BASE_DIR))

    pytest_args = executor._build_pytest_args("allure-results")

    assert "apps/app_automation/tests/test_app_flow.py::TestAppFlow::test_execute_ui_flow" in pytest_args
    assert "apps/app_automation/tests/" not in pytest_args
