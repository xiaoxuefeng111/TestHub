import re
from typing import Any, Dict, List, Optional


class MobileSemanticParser:
    """将移动端自然语言任务解析为受限 DSL。"""

    _NUMBERED_LINE_PATTERN = re.compile(r'^\s*(\d+(?:\.\d+)*)[\.\s、:：-]+(.*)$')
    _VALUE_PATTERN = re.compile(r'([A-Za-z0-9@#._\-]{2,})\s*$')
    _ACTION_KEYWORDS = ('点击', '点开', '输入', '切换到', '切到', '聚焦', '定位到', '等待', '打开', '启动', '进入', '返回')

    def should_parse(self, task_description: str) -> bool:
        text = self._normalize_text(task_description)
        if not text:
            return False

        if ('没有' in text and '有的话' in text) or ('如果' in text and '否则' in text):
            return True

        if re.search(r'输入[^\n，。,；;]{0,20}[A-Za-z0-9@#._\-]{2,}', text):
            return True

        if any(keyword in text for keyword in ('点击', '点开', '切换到', '切到', '聚焦', '定位到', '等待', '返回')):
            return True

        structured_steps = self._extract_structured_steps(text)
        return len(structured_steps) > 1 and any(keyword in text for keyword in self._ACTION_KEYWORDS)

    def parse(self, task_description: str, package_name: str) -> Dict[str, Any]:
        steps: List[Dict[str, Any]] = [
            {
                'type': 'start_app',
                'name': '启动应用',
                'package_name': package_name,
                'wait_after': 2,
            }
        ]
        unsupported_steps: List[str] = []

        for raw_step in self._extract_structured_steps(task_description):
            step_text = self._normalize_text(raw_step)
            parsed_steps = self._parse_step(step_text)
            if parsed_steps:
                steps.extend(parsed_steps)
                continue

            if self._is_open_app_step(step_text):
                continue

            unsupported_steps.append(step_text)

        return {
            'version': '1.0',
            'mode': 'unsafe' if unsupported_steps else 'safe',
            'unsafe_reason': '存在未支持的结构化步骤' if unsupported_steps else None,
            'unsupported_steps': unsupported_steps,
            'steps': steps,
        }

    def _parse_step(self, raw_step: str) -> List[Dict[str, Any]]:
        step_text = self._normalize_text(raw_step)
        if not step_text:
            return []

        conditional = self._parse_conditional_step(step_text)
        if conditional:
            return [conditional]

        if self._is_open_app_step(step_text):
            return []

        parsed_steps: List[Dict[str, Any]] = []
        for tap_target in self._extract_tap_targets(step_text):
            parsed_steps.append({
                'type': 'tap_text',
                'name': f'点击{tap_target}',
                'target': tap_target,
            })

        expected_page_step = self._parse_expected_page_step(step_text)
        if expected_page_step:
            parsed_steps.append(expected_page_step)

        input_step = self._parse_input_step(step_text)
        if input_step:
            parsed_steps.append(input_step)
        else:
            focus_step = self._parse_focus_step(step_text)
            if focus_step:
                parsed_steps.append(focus_step)

        return parsed_steps

    def _parse_conditional_step(self, step_text: str) -> Optional[Dict[str, Any]]:
        if '没有' not in step_text or '输入' not in step_text:
            return None

        branch_marker = None
        for marker in ('有的话', '否则', '不然'):
            if marker in step_text:
                branch_marker = marker
                break
        if not branch_marker:
            return None

        condition_target_match = re.search(r'没有(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16}?)(?:的情况下|时|的话|，|,)', step_text)
        if not condition_target_match:
            return None

        condition_target = self._normalize_field_name(condition_target_match.group('target'))
        if not condition_target:
            return None

        before_branch, after_branch = step_text.split(branch_marker, 1)
        true_input = self._parse_input_step(before_branch)
        false_focus = self._parse_focus_step(after_branch)
        if not true_input or not false_focus:
            return None

        return {
            'type': 'conditional',
            'name': f'判断{condition_target}是否为空',
            'condition': {
                'kind': 'field_empty',
                'target': condition_target,
            },
            'if_true': [
                {
                    'type': 'focus_field',
                    'name': f'聚焦{true_input["target"]}',
                    'target': true_input['target'],
                },
                true_input,
            ],
            'if_false': [
                false_focus,
            ],
        }

    def _parse_input_step(self, step_text: str) -> Optional[Dict[str, Any]]:
        if '输入' not in step_text:
            return None

        clause = step_text.split('输入', 1)[1]
        clause = re.split(r'[，,。；;]', clause, maxsplit=1)[0]
        clause = clause.strip()
        if not clause:
            return None

        value_match = self._VALUE_PATTERN.search(clause)
        if not value_match:
            return None

        value = value_match.group(1)
        target_text = clause[:value_match.start()].strip()
        target = self._normalize_field_name(target_text)
        if not target:
            return None

        return {
            'type': 'input',
            'name': f'输入{target}',
            'target': target,
            'value': value,
            'clear_first': True,
        }

    def _parse_focus_step(self, step_text: str) -> Optional[Dict[str, Any]]:
        normalized_step = re.sub(r'^(?:有的话就|有的话|然后|并且|并|就|再)+', '', step_text).strip()
        patterns = [
            r'^(?:切换到|切到|进入|聚焦|定位到)(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16})(?:输入框|输入栏|文本框|框|栏)?$',
            r'^点击(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16})(?:输入框|输入栏|文本框|框|栏)$',
            r'^(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16})(?:输入框|输入栏|文本框)$',
        ]

        match = None
        for pattern in patterns:
            match = re.fullmatch(pattern, normalized_step)
            if match:
                break
        if not match:
            return None

        target = self._normalize_field_name(match.group('target'))
        if not target:
            return None

        return {
            'type': 'focus_field',
            'name': f'聚焦{target}',
            'target': target,
        }

    def _parse_expected_page_step(self, step_text: str) -> Optional[Dict[str, Any]]:
        patterns = [
            r'(?:会)?弹出(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16})(?:页面|界面)',
            r'(?:进入|跳转到|来到)(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16})(?:页面|界面)',
        ]

        for pattern in patterns:
            match = re.search(pattern, step_text)
            if not match:
                continue
            target = self._clean_target_text(match.group('target'))
            if not target:
                continue
            return {
                'type': 'wait_text',
                'name': f'等待{target}出现',
                'target': target,
            }
        return None

    def _extract_tap_targets(self, step_text: str) -> List[str]:
        patterns = [
            r'点击(?:底部栏|底部)?(?:tab)?(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16})(?:按钮|tab|标签|入口)',
            r'点击(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16})(?:按钮|tab|标签|入口)',
            r'点击(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16}?)(?:$|，|,|。)',
            r'点开(?P<target>[\u4e00-\u9fa5A-Za-z0-9_-]{1,16})(?:按钮|tab|标签|入口)?',
        ]
        targets: List[str] = []

        for pattern in patterns:
            for match in re.finditer(pattern, step_text):
                target = self._clean_target_text(match.group('target'))
                if target and target not in targets:
                    targets.append(target)

        return targets

    def _extract_structured_steps(self, text: str) -> List[str]:
        if not text:
            return []

        normalized_text = str(text).replace('\r\n', '\n').replace('\r', '\n').strip()
        if not normalized_text:
            return []

        extracted_steps: List[str] = []
        plain_lines: List[str] = []

        for raw_line in normalized_text.split('\n'):
            line = raw_line.strip()
            if not line:
                continue
            match = self._NUMBERED_LINE_PATTERN.match(line)
            if match:
                desc = match.group(2).strip()
                if desc:
                    extracted_steps.append(desc)
            else:
                plain_lines.append(line)

        if extracted_steps:
            return extracted_steps

        split_inline_text = re.sub(
            r'\s+(?=\d+(?:\.\d+)*[\.\s、:：-]+)',
            '\n',
            normalized_text,
        )
        if split_inline_text != normalized_text:
            inline_steps = self._extract_structured_steps(split_inline_text)
            if inline_steps:
                return inline_steps

        return plain_lines or [normalized_text]

    def _is_open_app_step(self, step_text: str) -> bool:
        return any(keyword in step_text for keyword in ('打开', '启动')) and '应用' in step_text

    def _normalize_field_name(self, text: str) -> str:
        cleaned = self._clean_target_text(text)
        cleaned = cleaned.replace('帐户', '账户').replace('帐号', '账号')
        cleaned = cleaned.replace('账户号', '账号').replace('帐户号', '账号')
        cleaned = re.sub(r'(输入框|输入栏|文本框|框|栏)$', '', cleaned)
        cleaned = cleaned.strip()

        if '资金' in cleaned and '账号' in cleaned:
            return '资金账号'
        if '密码' in cleaned:
            return '密码'
        return cleaned

    def _clean_target_text(self, text: str) -> str:
        cleaned = str(text or '').strip()
        cleaned = cleaned.replace('登陆', '登录')
        cleaned = re.sub(r'^(并|再|然后|底部栏|底部|顶部|页面|界面|应用|按钮|tab|标签)+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'(按钮|tab|标签|页面|界面|入口)+$', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip('，。,.、:：;； ')
        generic_values = {'', '底部', '顶部', '按钮', 'tab', '标签', '页面', '界面', '应用'}
        if cleaned.lower() in {value.lower() for value in generic_values}:
            return ''
        return cleaned

    @staticmethod
    def _normalize_text(text: Any) -> str:
        return str(text or '').replace('\u3000', ' ').strip()
