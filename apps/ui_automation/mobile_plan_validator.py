import json
import re
from typing import Any, Dict, Iterable, List


class MobilePlanValidator:
    """校验移动端受限 DSL 的完整性与关键字面值保真。"""

    def validate(self, task_description: str, plan: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        steps = plan.get('steps') if isinstance(plan, dict) else None
        if not isinstance(steps, list):
            return ['plan.steps 必须是列表']

        unsupported_steps = plan.get('unsupported_steps') or []
        if unsupported_steps:
            errors.append(f"未支持的结构化步骤: {'；'.join(str(step) for step in unsupported_steps)}")

        self._validate_steps(steps, errors)
        serialized_plan = json.dumps(plan, ensure_ascii=False, sort_keys=True)

        for literal in self._extract_key_literals(task_description):
            if literal not in serialized_plan:
                errors.append(f'计划缺少用户原文中的关键字面值: {literal}')

        for tap_target in self._extract_key_tap_targets(task_description):
            if not self._plan_has_tap_target(steps, tap_target):
                errors.append(f'计划缺少用户原文中的关键点击动作: {tap_target}')

        return errors

    def _validate_steps(self, steps: Iterable[Dict[str, Any]], errors: List[str]) -> None:
        for step in steps:
            if not isinstance(step, dict):
                errors.append('step 必须是字典')
                continue

            step_type = str(step.get('type', '')).strip()
            if step_type in {'tap_text', 'focus_field', 'wait_text', 'assert_text_visible'}:
                if not (step.get('target') or step.get('text')):
                    errors.append(f'{step_type} 动作缺少 target/text')
            elif step_type == 'input':
                if not step.get('target'):
                    errors.append('input 动作缺少 target')
                if step.get('value') in (None, ''):
                    errors.append('input 动作缺少 value')
            elif step_type == 'conditional':
                condition = step.get('condition') or {}
                if not condition.get('kind'):
                    errors.append('conditional 缺少 condition.kind')
                if not condition.get('target'):
                    errors.append('conditional 缺少 condition.target')
                if_true = step.get('if_true')
                if_false = step.get('if_false')
                if not isinstance(if_true, list) or not if_true:
                    errors.append('conditional 缺少 if_true 分支')
                else:
                    self._validate_steps(if_true, errors)
                if not isinstance(if_false, list) or not if_false:
                    errors.append('conditional 缺少 if_false 分支')
                else:
                    self._validate_steps(if_false, errors)

    def _extract_key_literals(self, task_description: str) -> List[str]:
        if not task_description:
            return []

        text = str(task_description)
        candidates: List[str] = []
        candidates.extend(re.findall(r'"([^"\n]+)"', text))
        candidates.extend(re.findall(r"'([^'\n]+)'", text))
        candidates.extend(re.findall(r'\d{4,}', text))
        candidates.extend(re.findall(r'https?://[^\s]+', text))

        deduped: List[str] = []
        for candidate in candidates:
            item = str(candidate).strip()
            if item and item not in deduped:
                deduped.append(item)
        return deduped

    def _extract_key_tap_targets(self, task_description: str) -> List[str]:
        if not task_description:
            return []

        patterns = [
            r'点击(?:底部栏|底部)?(?:tab)?(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16})(?:按钮|tab|标签|入口)',
            r'点击(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16})(?:按钮|tab|标签|入口)',
            r'点击(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16}?)(?:$|，|,|。)',
        ]
        targets: List[str] = []

        for pattern in patterns:
            for match in re.finditer(pattern, str(task_description)):
                target = self._normalize_target(match.group('target'))
                if target and target not in targets:
                    targets.append(target)
        return targets

    def _plan_has_tap_target(self, steps: Iterable[Dict[str, Any]], target: str) -> bool:
        normalized_target = self._normalize_target(target)
        for step in steps:
            if not isinstance(step, dict):
                continue

            step_type = str(step.get('type', '')).strip()
            if step_type == 'tap_text' and self._normalize_target(step.get('target') or step.get('text')) == normalized_target:
                return True
            if step_type == 'conditional':
                if self._plan_has_tap_target(step.get('if_true') or [], target):
                    return True
                if self._plan_has_tap_target(step.get('if_false') or [], target):
                    return True
        return False

    def _normalize_target(self, value: Any) -> str:
        cleaned = str(value or '').strip()
        cleaned = cleaned.replace('登陆', '登录')
        cleaned = cleaned.replace('帐户', '账户').replace('帐号', '账号')
        cleaned = cleaned.replace('账户号', '账号').replace('帐户号', '账号')
        cleaned = re.sub(r'^(并|再|然后|底部栏|底部|顶部|页面|界面|应用|按钮|tab|标签)+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'(按钮|tab|标签|页面|界面|入口)+$', '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip('，。,.、:：;； ')
