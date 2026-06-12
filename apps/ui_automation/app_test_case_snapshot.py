from copy import deepcopy
from typing import Any, Dict, Iterable, List


STEP_ALLOWED_FIELDS = {
    'type',
    'name',
    'package_name',
    'wait_after',
    'text',
    'match_mode',
    'timeout',
    'interval',
    'index',
    'region',
    'value',
    'send_enter',
    'direction',
    'max_swipes',
    'keycode',
    'coordinate',
    'coordinates',
    'selector',
    'selector_type',
    'ocr_selector',
    'ocr_selector_type',
    'post_wait_text',
    'post_wait_match_mode',
    'post_wait_timeout',
    'post_wait_interval',
    'post_absent_text',
    'post_absent_timeout',
    'post_absent_interval',
    'condition',
    'then_steps',
    'else_steps',
}

CONDITION_ALLOWED_FIELDS = {
    'kind',
    'target',
    'text',
    'match_mode',
    'timeout',
    'interval',
    'index',
    'region',
    'selector',
    'selector_type',
    'ocr_selector',
    'ocr_selector_type',
}


def sanitize_ui_flow_snapshot(ui_flow: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a persistable AppTestCase ui_flow copied from an AI execution snapshot.

    The snapshot can contain runtime-only details. This function keeps only the
    executable DSL fields and recursively cleans conditional branches.
    """
    if not isinstance(ui_flow, list):
        raise ValueError('ui_flow_snapshot must be a list')

    cleaned_steps = []
    for step in ui_flow:
        if not isinstance(step, dict):
            continue
        cleaned_steps.append(_sanitize_step(step))
    return cleaned_steps


def _sanitize_step(step: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in step.items():
        if key not in STEP_ALLOWED_FIELDS:
            continue
        if key == 'condition':
            cleaned[key] = _sanitize_condition(value)
        elif key in {'then_steps', 'else_steps'}:
            cleaned[key] = sanitize_ui_flow_snapshot(value if isinstance(value, list) else [])
        else:
            cleaned[key] = deepcopy(value)
    return cleaned


def _sanitize_condition(condition: Any) -> Any:
    if not isinstance(condition, dict):
        return deepcopy(condition)

    return {
        key: deepcopy(value)
        for key, value in condition.items()
        if key in CONDITION_ALLOWED_FIELDS
    }
