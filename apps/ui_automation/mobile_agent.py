import copy
import logging
import os
from typing import Any, Callable, Dict, List, Optional

from django.db import DatabaseError, connection
from django.utils import timezone

from apps.app_automation.runners.ui_flow_runner import UiFlowRunner
from apps.ui_automation.models import AIExecutionRecord

logger = logging.getLogger(__name__)


class MobileFlowPlanner:
    """Build an executable mobile UI Flow from a natural-language task.

    This minimal planner keeps the execution path deterministic. More advanced
    semantic/LLM planning can replace this class without changing the persistence
    contract used by run_mobile_execution().
    """

    def generate_ui_flow(self, task_description: str, package_name: str) -> List[Dict[str, Any]]:
        return [
            {
                'type': 'start_app',
                'name': '启动应用',
                'package_name': package_name,
                'wait_after': 2,
            },
            {
                'type': 'screenshot',
                'name': '结果截图',
            },
        ]


def _safe_save(record: AIExecutionRecord, update_fields: Optional[List[str]] = None, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            record.save(update_fields=update_fields)
            return
        except (DatabaseError, Exception) as exc:
            if attempt >= max_retries - 1:
                raise
            logger.warning('保存移动端 AI 执行记录失败，准备重试: %s', exc)
            try:
                connection.close()
            except Exception:
                pass


def run_mobile_execution(execution_record_id: int, should_stop: Optional[Callable[[], bool]] = None):
    """Execute one mobile AI record and persist the exact UI Flow snapshot first."""
    execution_record = None
    try:
        try:
            connection.close()
        except Exception:
            pass
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'

        execution_record = AIExecutionRecord.objects.select_related(
            'app_package', 'executed_by'
        ).get(id=execution_record_id)

        if should_stop and should_stop():
            execution_record.status = 'stopped'
            execution_record.end_time = timezone.now()
            execution_record.logs += '\n[System] 任务已由用户停止。'
            _safe_save(execution_record, update_fields=['status', 'end_time', 'logs'])
            return

        if not execution_record.app_package:
            raise ValueError('移动端执行缺少目标应用包')

        planner = MobileFlowPlanner()
        ui_flow = planner.generate_ui_flow(
            execution_record.task_description,
            execution_record.app_package.package_name,
        )

        execution_record.ui_flow_snapshot = copy.deepcopy(ui_flow)
        execution_record.planned_tasks = [
            {
                'id': index,
                'description': step.get('name') or step.get('type', f'步骤{index}'),
                'status': 'pending',
            }
            for index, step in enumerate(ui_flow, 1)
        ]
        execution_record.logs += '移动端执行计划已生成，开始执行...\n'
        _safe_save(
            execution_record,
            update_fields=['ui_flow_snapshot', 'planned_tasks', 'logs'],
        )

        runner = UiFlowRunner()
        result = runner.run(ui_flow)

        if should_stop and should_stop():
            execution_record.status = 'stopped'
            execution_record.logs += '\n[System] 任务已由用户停止。'
        elif result.get('failed', 0):
            execution_record.status = 'failed'
            execution_record.logs += '\n移动端执行完成，但存在失败步骤。'
        else:
            execution_record.status = 'passed'
            execution_record.logs += '\n移动端执行完成。'

        execution_record.end_time = timezone.now()
        execution_record.duration = (
            execution_record.end_time - execution_record.start_time
        ).total_seconds()
        _safe_save(
            execution_record,
            update_fields=['status', 'logs', 'end_time', 'duration', 'ui_flow_snapshot'],
        )
    except Exception as exc:
        logger.error('移动端 AI 执行失败: %s', exc, exc_info=True)
        if execution_record is not None:
            execution_record.status = 'failed'
            execution_record.end_time = timezone.now()
            execution_record.duration = (
                execution_record.end_time - execution_record.start_time
            ).total_seconds()
            execution_record.logs += f'\n移动端执行出错: {exc}'
            _safe_save(
                execution_record,
                update_fields=['status', 'logs', 'end_time', 'duration', 'ui_flow_snapshot'],
            )
        else:
            raise
