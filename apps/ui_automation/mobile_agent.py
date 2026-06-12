import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv
from django.db import DatabaseError, connection
from django.utils import timezone
from langchain_openai import ChatOpenAI

from apps.app_automation.runners.ui_flow_runner import StopExecution, UiFlowRunner
from apps.app_automation.utils.airtest_base import AirtestBase
from apps.requirement_analysis.models import AIModelConfig
from apps.ui_automation.mobile_plan_validator import MobilePlanValidator
from apps.ui_automation.mobile_semantic_parser import MobileSemanticParser
from apps.ui_automation.models import AIExecutionRecord

load_dotenv()

logger = logging.getLogger('django')


class MobileFlowPlanner:
    """将自然语言任务规划为 OCR 驱动的移动端 UI Flow。"""

    ALLOWED_ACTIONS = {
        'start_app',
        'wait_text',
        'tap_text',
        'input',
        'swipe_until_text',
        'keyevent',
        'screenshot',
        'assert_text_visible',
        'if',
    }

    def __init__(self):
        config = (
            AIModelConfig.objects.filter(role='browser_use_vision', is_active=True).first()
            or AIModelConfig.objects.filter(role='browser_use_text', is_active=True).first()
            or AIModelConfig.objects.filter(is_active=True).first()
        )
        if not config:
            raise ValueError('未找到可用的 AI 模型配置')

        api_key = config.api_key or os.getenv('AUTH_TOKEN')
        base_url = config.base_url or os.getenv('BASE_URL')
        model_name = config.model_name or os.getenv('MODEL_NAME')
        if not api_key or not base_url or not model_name:
            raise ValueError('移动端 AI 执行缺少模型配置')

        self.llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0,
        )
        self.semantic_parser = MobileSemanticParser()
        self.plan_validator = MobilePlanValidator()

    def generate_ui_flow(self, task_description: str, package_name: str) -> List[Dict[str, Any]]:
        semantic_plan = self._try_generate_semantic_plan(task_description, package_name)
        if semantic_plan:
            logger.info('MobileFlowPlanner using rule-based semantic plan for task: %s', task_description)
            return self._compile_semantic_plan(semantic_plan, package_name)

        prompt = f"""
你是 Android 真机自动化规划器。请把用户任务转换成 JSON 数组，供 OCR + Airtest 执行。

只允许以下动作类型：
1. {{"type":"start_app","name":"启动应用","package_name":"{package_name}","wait_after":2}}
2. {{"type":"wait_text","name":"等待文字出现","text":"登录","match_mode":"contains","timeout":8,"interval":0.5}}
3. {{"type":"tap_text","name":"点击文字","text":"登录","match_mode":"contains","index":0}}
4. {{"type":"input","name":"输入文本","value":"OpenAI","send_enter":false}}
5. {{"type":"swipe_until_text","name":"滑动查找文字","text":"设置","direction":"up","max_swipes":5,"interval":0.5}}
6. {{"type":"keyevent","name":"返回上一页","keycode":"KEYCODE_BACK"}}
7. {{"type":"assert_text_visible","name":"断言结果可见","text":"成功","match_mode":"contains","timeout":8}}
8. {{"type":"screenshot","name":"结果截图"}}

规则：
- 第一条必须是 start_app，并使用给定 package_name。
- 只能输出 JSON 数组，不要 Markdown，不要解释。
- 只能使用上面的动作类型，不要输出坐标、图片模板、selector、element_id。
- 每一步都要有清晰中文 name。
- 尽量使用文字点击/等待；如果是搜索场景，input 可以配合 send_enter=true。
- 如果任务没有明确结果校验，也请在最后补一条 screenshot。

应用包名: {package_name}
用户任务: {task_description}
""".strip()

        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            ui_flow = self._extract_ui_flow(content)
            if not ui_flow:
                raise ValueError('empty ui flow from llm')
        except Exception as exc:
            logger.warning('MobileFlowPlanner fallback triggered: %s', exc)
            ui_flow = self._build_heuristic_ui_flow(task_description)
        return self._normalize_ui_flow(ui_flow, package_name)

    def _try_generate_semantic_plan(self, task_description: str, package_name: str) -> Optional[Dict[str, Any]]:
        if not self.semantic_parser.should_parse(task_description):
            return None

        plan = self.semantic_parser.parse(task_description, package_name)
        errors = self.plan_validator.validate(task_description, plan)
        if errors:
            raise ValueError('; '.join(errors))

        return plan

    def _compile_semantic_plan(self, plan: Dict[str, Any], package_name: str) -> List[Dict[str, Any]]:
        compiled_steps: List[Dict[str, Any]] = []
        for step in plan.get('steps') or []:
            compiled_steps.extend(self._compile_semantic_step(step, package_name))
        return self._normalize_ui_flow(compiled_steps, package_name)

    def _compile_semantic_step(self, step: Dict[str, Any], package_name: str) -> List[Dict[str, Any]]:
        step_type = str(step.get('type', '')).strip()
        if not step_type:
            return []

        if step_type == 'start_app':
            return [{
                'type': 'start_app',
                'name': step.get('name', '启动应用'),
                'package_name': package_name,
                'wait_after': step.get('wait_after', 2),
            }]

        if step_type in {'tap_text', 'focus_field'}:
            target = step.get('target') or step.get('text')
            return self._build_wait_and_tap_steps(str(target or ''), step.get('name'))

        if step_type == 'wait_text':
            target = step.get('target') or step.get('text')
            if not target:
                return []
            return [{
                'type': 'wait_text',
                'name': step.get('name', f'等待{target}出现'),
                'text': str(target),
                'match_mode': 'contains',
                'timeout': step.get('timeout', 8),
                'interval': step.get('interval', 0.5),
            }]

        if step_type == 'input':
            value = step.get('value')
            target = step.get('target') or step.get('text')
            compiled: List[Dict[str, Any]] = []
            if target:
                compiled.extend(self._build_wait_and_tap_steps(str(target), f'聚焦{target}'))
            compiled.append({
                'type': 'input',
                'name': step.get('name', f'输入{target or "文本"}'),
                'value': value,
                'text': value,
                'send_enter': bool(step.get('send_enter', False)),
            })
            return compiled

        if step_type == 'conditional':
            condition = dict(step.get('condition') or {})
            kind = str(condition.get('kind') or 'conditional')
            if kind != 'field_empty':
                raise ValueError(f'Unsupported mobile conditional kind: {kind}')

            then_steps: List[Dict[str, Any]] = []
            for branch_step in step.get('if_true') or []:
                then_steps.extend(self._compile_semantic_step(branch_step, package_name))

            else_steps: List[Dict[str, Any]] = []
            for branch_step in step.get('if_false') or []:
                else_steps.extend(self._compile_semantic_step(branch_step, package_name))

            return [{
                'type': 'if',
                'name': step.get('name', f'判断{condition.get("target") or ""}是否为空'),
                'condition': condition,
                'then_steps': then_steps,
                'else_steps': else_steps,
            }]

        return []

    def _build_wait_and_tap_steps(self, target: str, name: Optional[str] = None) -> List[Dict[str, Any]]:
        if not target:
            return []
        readable_name = name or f'点击{target}'
        tap_index = -1 if self._should_prefer_last_tap_candidate(target) else 0
        tap_step = {
            'type': 'tap_text',
            'name': readable_name,
            'text': target,
            'match_mode': 'contains',
            'index': tap_index,
        }
        preferred_region = self._preferred_tap_region(target)
        if preferred_region:
            tap_step['region'] = preferred_region
        return [
            {
                'type': 'wait_text',
                'name': f'等待{target}出现',
                'text': target,
                'match_mode': 'contains',
                'timeout': 8,
                'interval': 0.5,
            },
            tap_step,
        ]

    @staticmethod
    def _should_prefer_last_tap_candidate(target: str) -> bool:
        normalized_target = str(target or '').strip()
        return any(keyword in normalized_target for keyword in ('登录', '提交', '确认', '完成', '下一步'))

    @staticmethod
    def _should_skip_auto_absent_validation(target: str) -> bool:
        normalized_target = str(target or '').strip()
        return '登录' in normalized_target

    @staticmethod
    def _preferred_tap_region(target: str) -> Optional[str]:
        normalized_target = str(target or '').strip()
        if '登录' in normalized_target:
            return '0,600,3000,4000'
        return None

    def _extract_ui_flow(self, content: str) -> List[Dict[str, Any]]:
        cleaned = content.strip()
        if '```' in cleaned:
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            cleaned = cleaned.strip()

        parsed: Any = None
        try:
            parsed = json.loads(cleaned)
        except Exception:
            match = re.search(r'(\[.*\]|\{.*\})', cleaned, re.S)
            if match:
                parsed = json.loads(match.group(1))

        if isinstance(parsed, dict):
            parsed = parsed.get('ui_flow') or parsed.get('steps') or []
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, dict)]

    def _normalize_ui_flow(self, ui_flow: List[Dict[str, Any]], package_name: str) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for index, step in enumerate(ui_flow, 1):
            action_type = str(step.get('type', '')).strip()
            if action_type not in self.ALLOWED_ACTIONS:
                continue
            new_step = dict(step)
            if action_type == 'input' and 'value' not in new_step and 'text' in new_step:
                new_step['value'] = new_step.get('text', '')
            new_step.setdefault('name', f'移动步骤 {index}')
            if action_type == 'start_app':
                new_step['package_name'] = package_name
                new_step.setdefault('wait_after', 2)
            normalized.append(new_step)

        if not normalized or normalized[0].get('type') != 'start_app':
            normalized.insert(0, {
                'type': 'start_app',
                'name': '启动应用',
                'package_name': package_name,
                'wait_after': 2,
            })

        normalized = self._annotate_post_tap_validations(normalized)

        if not normalized or normalized[-1].get('type') != 'screenshot':
            normalized.append({
                'type': 'screenshot',
                'name': '结果截图',
            })

        return normalized

    def _annotate_post_tap_validations(self, ui_flow: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        annotated: List[Dict[str, Any]] = []
        visible_targets: List[str] = []

        for index, step in enumerate(ui_flow):
            new_step = dict(step)
            step_type = str(new_step.get('type', '')).strip()
            target = self._normalize_step_target(new_step)

            if step_type in {'wait_text', 'assert_text_visible'} and target:
                visible_targets.append(target)
            elif step_type == 'tap_text' and target:
                next_step = ui_flow[index + 1] if index + 1 < len(ui_flow) else {}
                next_step_type = str(next_step.get('type', '')).strip()
                next_target = self._normalize_step_target(next_step)

                if next_step_type in {'wait_text', 'assert_text_visible'} and next_target and next_target != target:
                    new_step.setdefault('post_wait_text', str(next_step.get('text') or next_step.get('target') or next_target))
                    new_step.setdefault('post_wait_match_mode', next_step.get('match_mode', 'contains'))
                    new_step.setdefault('post_wait_timeout', next_step.get('timeout', 8))
                    new_step.setdefault('post_wait_interval', next_step.get('interval', 0.5))

                if (
                    self._should_prefer_last_tap_candidate(target)
                    and not self._should_skip_auto_absent_validation(target)
                    and target in visible_targets
                    and next_target != target
                ):
                    new_step.setdefault('post_absent_text', str(new_step.get('text') or new_step.get('target') or target))
                    new_step.setdefault('post_absent_timeout', 5)
                    new_step.setdefault('post_absent_interval', 0.5)

            annotated.append(new_step)

        return annotated

    def _normalize_step_target(self, step: Dict[str, Any]) -> str:
        value = step.get('target') or step.get('text') or ''
        return str(value).strip().replace('登陆', '登录')

    def _build_heuristic_ui_flow(self, task_description: str) -> List[Dict[str, Any]]:
        compact_task = re.sub(r'\s+', '', task_description or '')
        tap_targets = self._infer_tap_targets(compact_task)
        ui_flow: List[Dict[str, Any]] = []

        for target in tap_targets:
            ui_flow.append({
                'type': 'wait_text',
                'name': f'等待{target}出现',
                'text': target,
                'match_mode': 'contains',
                'timeout': 8,
                'interval': 0.5,
            })
            tap_step = {
                'type': 'tap_text',
                'name': f'点击{target}',
                'text': target,
                'match_mode': 'contains',
                'index': -1 if self._should_prefer_last_tap_candidate(target) else 0,
            }
            preferred_region = self._preferred_tap_region(target)
            if preferred_region:
                tap_step['region'] = preferred_region
            ui_flow.append(tap_step)

        return ui_flow

    def _infer_tap_targets(self, task_description: str) -> List[str]:
        patterns = [
            r'点击(?:底部)?(?:tab)?(?:的)?(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,12})(?:按钮|tab|标签|入口)?',
            r'打开(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,12})(?:页面|按钮|tab|标签|入口)?',
            r'进入(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,12})(?:页面|按钮|tab|标签|入口)?',
        ]
        targets: List[str] = []

        for pattern in patterns:
            for match in re.finditer(pattern, task_description):
                target = self._clean_target_text(match.group('target'))
                if target and target not in targets:
                    targets.append(target)

        if targets:
            return targets

        generic_tokens = {
            '启动', '打开', '进入', '应用', '页面', '界面', '底部', '顶部', '按钮', '点击', '任务', '执行', 'tab', '标签',
            '看看', '看下', '看一下', '查看', '随便', '这个', '那个', '帮我', '一下',
        }
        conversational_markers = ('帮我', '看看', '看下', '看一下', '随便', '这个', '那个', '一下')
        for token in re.findall(r'[\u4e00-\u9fa5A-Za-z0-9_-]{2,12}', task_description):
            cleaned = self._clean_target_text(token)
            if not cleaned or cleaned in generic_tokens:
                continue
            if any(marker in cleaned for marker in conversational_markers):
                continue
            if cleaned.isascii() and len(cleaned) > 6 and not re.search(r'[\u4e00-\u9fa5]', cleaned):
                continue
            return [cleaned]
        return []

    def _clean_target_text(self, text: str) -> str:
        cleaned = re.sub(r'^(底部|顶部|页面|界面|应用|按钮|tab|标签)+', '', text or '', flags=re.IGNORECASE)
        cleaned = re.sub(r'(按钮|tab|标签|页面|界面|入口)+$', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip('，。,.、:：;； ')
        generic_values = {'', '底部', '顶部', '按钮', 'tab', '标签', '页面', '界面', '应用'}
        if cleaned.lower() in {value.lower() for value in generic_values}:
            return ''
        return cleaned


def _safe_save(record: AIExecutionRecord, update_fields: Optional[List[str]] = None, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            record.save(update_fields=update_fields)
            return
        except (DatabaseError, Exception) as e:
            if attempt >= max_retries - 1:
                raise
            logger.warning(f'保存移动端 AI 执行记录失败，准备重试: {e}')
            try:
                connection.close()
            except Exception:
                pass
            time.sleep(0.2)


def run_mobile_execution(execution_record_id: int, should_stop: Optional[Callable[[], bool]] = None):
    """执行移动端 AI 临时任务。"""
    execution_record = None
    device = None
    airtest = None

    try:
        try:
            connection.close()
        except Exception:
            pass
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'

        execution_record = AIExecutionRecord.objects.select_related(
            'app_device', 'app_package', 'executed_by'
        ).get(id=execution_record_id)
        device = execution_record.app_device
        app_package = execution_record.app_package
        username = execution_record.executed_by.username if execution_record.executed_by else 'unknown'

        if not device:
            raise ValueError('移动端执行缺少目标设备')
        if not app_package:
            raise ValueError('移动端执行缺少目标应用包')
        if device.status == 'locked' and device.locked_by != execution_record.executed_by:
            raise RuntimeError(f'设备 {device.device_id} 已被其他用户锁定')
        if device.status == 'offline':
            raise RuntimeError(f'设备 {device.device_id} 当前离线，无法执行任务')

        if device.status != 'locked':
            device.lock(execution_record.executed_by)

        planner = MobileFlowPlanner()
        ui_flow = planner.generate_ui_flow(execution_record.task_description, app_package.package_name)
        execution_record.planned_tasks = [
            {
                'id': index,
                'description': step.get('name') or step.get('type', f'步骤{index}'),
                'status': 'pending',
            }
            for index, step in enumerate(ui_flow, 1)
        ]
        execution_record.logs += f"已生成 {len(ui_flow)} 个移动端执行步骤。\n"
        _safe_save(execution_record, update_fields=['planned_tasks', 'logs'])

        if should_stop and should_stop():
            raise StopExecution('任务已停止')

        airtest = AirtestBase(device_id=device.device_id, username=username)
        if not airtest.setup_airtest():
            raise RuntimeError(f'连接设备失败: {device.device_id}')

        execution_record.logs += f"设备已连接: {device.device_id}\n"
        _safe_save(execution_record, update_fields=['logs'])

        device_ready = airtest.ensure_device_ready()
        if device_ready:
            execution_record.logs += '设备准备检查通过，继续执行移动端步骤。\n'
        else:
            execution_record.logs += (
                '设备准备检查未完全通过，继续执行移动端步骤；'
                '如当前仍在锁屏或系统界面，后续步骤可能失败。\n'
            )
        _safe_save(execution_record, update_fields=['logs'])

        runner = UiFlowRunner(username=username, device_id=device.device_id)

        def progress_callback(current_step, total_steps, step_name, status):
            status_map = {
                'running': 'in_progress',
                'passed': 'completed',
                'failed': 'failed',
            }
            if execution_record.planned_tasks and 0 < current_step <= len(execution_record.planned_tasks):
                execution_record.planned_tasks[current_step - 1]['status'] = status_map.get(status, status)
                if status == 'passed':
                    execution_record.steps_completed.append(step_name)
            execution_record.logs += f"[{current_step}/{total_steps}] {step_name} - {status}\n"
            _safe_save(execution_record, update_fields=['planned_tasks', 'steps_completed', 'logs'])

        result = runner.run(
            ui_flow=ui_flow,
            runtime={'stop_on_error': True},
            progress_callback=progress_callback,
            should_stop=should_stop,
        )

        execution_record.status = 'passed' if result.get('failed', 0) == 0 else 'failed'
        execution_record.logs += (
            f"移动端执行完成：总步骤 {result.get('total', 0)}，"
            f"成功 {result.get('passed', 0)}，失败 {result.get('failed', 0)}。\n"
        )
    except StopExecution:
        if execution_record:
            execution_record.status = 'stopped'
            execution_record.logs += '[System] 任务已由用户停止。\n'
    except Exception as e:
        logger.error(f'移动端 AI 执行失败: {e}', exc_info=True)
        if execution_record:
            execution_record.status = 'failed'
            execution_record.logs += f'[System] 移动端执行失败: {e}\n'
    finally:
        if airtest:
            try:
                airtest.teardown_airtest()
            except Exception:
                logger.exception('清理 Airtest 环境失败')

        if execution_record:
            execution_record.end_time = timezone.now()
            if execution_record.start_time:
                execution_record.duration = (execution_record.end_time - execution_record.start_time).total_seconds()
            _safe_save(execution_record, update_fields=['status', 'logs', 'end_time', 'duration', 'planned_tasks', 'steps_completed'])

        try:
            if device and execution_record and device.locked_by == execution_record.executed_by:
                device.unlock()
        except Exception:
            logger.exception('释放移动端设备失败')
