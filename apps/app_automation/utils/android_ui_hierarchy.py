# -*- coding: utf-8 -*-
"""Android 视图树文本定位工具。"""

import logging
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AndroidUiHierarchyHelper:
    """基于 adb + uiautomator dump 的 Android 文本定位辅助类。"""

    _BOUNDS_PATTERN = re.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')

    def __init__(self, device_id: str, adb_path: Optional[str] = None, cache_ttl: float = 0.5):
        self.device_id = device_id
        self.adb_path = adb_path or self.get_adb_path()
        self.cache_ttl = cache_ttl
        self._cached_xml: Optional[str] = None
        self._cached_at = 0.0

    @staticmethod
    def get_adb_path() -> str:
        try:
            from apps.app_automation.models import AppTestConfig

            config = AppTestConfig.objects.first()
            if config and config.adb_path:
                return config.adb_path
        except Exception as exc:
            logger.warning(f"获取 ADB 配置失败，改用默认 adb: {exc}")
        return 'adb'

    @staticmethod
    def _get_subprocess_kwargs() -> Dict[str, Any]:
        create_no_window = getattr(subprocess, 'CREATE_NO_WINDOW', None)
        return {'creationflags': create_no_window} if create_no_window is not None else {}

    def _run_adb_command(self, args: List[str], *, timeout: int = 20, text: bool = True) -> subprocess.CompletedProcess:
        kwargs: Dict[str, Any] = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'timeout': timeout,
            'text': text,
            **self._get_subprocess_kwargs(),
        }
        if text:
            kwargs['encoding'] = 'utf-8'
            kwargs['errors'] = 'ignore'
        return subprocess.run(
            [self.adb_path, '-s', self.device_id, *args],
            **kwargs,
        )

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return re.sub(r'\s+', '', str(value or '')).lower()

    @classmethod
    def _parse_bounds(cls, bounds_value: str) -> Optional[Tuple[int, int, int, int]]:
        match = cls._BOUNDS_PATTERN.fullmatch(str(bounds_value or '').strip())
        if not match:
            return None
        x1, y1, x2, y2 = (int(part) for part in match.groups())
        return x1, y1, x2, y2

    @staticmethod
    def _has_visible_bounds(bounds: Optional[Tuple[int, int, int, int]]) -> bool:
        return bool(bounds and bounds[2] > bounds[0] and bounds[3] > bounds[1])

    @staticmethod
    def _center_from_bounds(bounds: Tuple[int, int, int, int]) -> Tuple[int, int]:
        x1, y1, x2, y2 = bounds
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @staticmethod
    def _bbox_from_bounds(bounds: Tuple[int, int, int, int]) -> List[Tuple[int, int]]:
        x1, y1, x2, y2 = bounds
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    @staticmethod
    def _point_in_region(point: Tuple[int, int], region: Tuple[int, int, int, int]) -> bool:
        x, y = point
        x1, y1, x2, y2 = region
        return x1 <= x <= x2 and y1 <= y <= y2

    def dump_hierarchy_xml(self, force_refresh: bool = False) -> Optional[str]:
        if (
            not force_refresh
            and self._cached_xml
            and (time.time() - self._cached_at) <= self.cache_ttl
        ):
            return self._cached_xml

        remote_path = f"/data/local/tmp/testhub_window_dump_{int(time.time() * 1000)}.xml"
        try:
            dump_result = self._run_adb_command(
                ['shell', 'uiautomator', 'dump', remote_path],
                timeout=20,
                text=True,
            )
            if dump_result.returncode != 0:
                error_text = (dump_result.stderr or dump_result.stdout or '').strip()
                logger.warning(f"uiautomator dump 执行失败: {error_text}")
                return None

            cat_result = self._run_adb_command(
                ['shell', 'cat', remote_path],
                timeout=20,
                text=True,
            )
            if cat_result.returncode != 0:
                error_text = (cat_result.stderr or cat_result.stdout or '').strip()
                logger.warning(f"读取 uiautomator dump 失败: {error_text}")
                return None

            output = (cat_result.stdout or '').replace('\x00', '')
            xml_start = output.find('<?xml')
            if xml_start < 0:
                logger.warning('uiautomator dump 输出中未找到 XML 内容')
                return None

            xml_content = output[xml_start:].strip()
            self._cached_xml = xml_content
            self._cached_at = time.time()
            return xml_content
        except Exception as exc:
            logger.warning(f"获取 Android 视图树失败: {exc}")
            return None
        finally:
            try:
                self._run_adb_command(['shell', 'rm', '-f', remote_path], timeout=5, text=True)
            except Exception as cleanup_error:
                logger.debug(f"清理临时视图树文件失败: {cleanup_error}")

    def _build_node_info(self, node: ET.Element) -> Dict[str, Any]:
        attrs = node.attrib
        return {
            'text': attrs.get('text', '') or '',
            'content_desc': attrs.get('content-desc', '') or '',
            'hint_text': attrs.get('hint-text', '') or '',
            'resource_id': attrs.get('resource-id', '') or '',
            'class_name': attrs.get('class', '') or '',
            'clickable': str(attrs.get('clickable', 'false')).lower() == 'true',
            'enabled': str(attrs.get('enabled', 'true')).lower() == 'true',
            'focused': str(attrs.get('focused', 'false')).lower() == 'true',
            'bounds': self._parse_bounds(attrs.get('bounds', '')),
        }

    def _resolve_click_target(
        self,
        current_node: Dict[str, Any],
        ancestors: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if self._has_visible_bounds(current_node.get('bounds')):
            return current_node

        for ancestor in reversed(ancestors):
            if ancestor.get('clickable') and self._has_visible_bounds(ancestor.get('bounds')):
                return ancestor

        for ancestor in reversed(ancestors):
            if self._has_visible_bounds(ancestor.get('bounds')):
                return ancestor

        return None

    def _matches_target(self, candidate_text: str, target_text: str, match_mode: str) -> bool:
        normalized_candidate = self._normalize_text(candidate_text)
        normalized_target = self._normalize_text(target_text)
        if not normalized_candidate or not normalized_target:
            return False
        if match_mode == 'exact':
            return normalized_candidate == normalized_target
        if match_mode == 'regex':
            return re.search(target_text, candidate_text) is not None
        return normalized_target in normalized_candidate

    def _collect_matches(
        self,
        node: ET.Element,
        ancestors: List[Dict[str, Any]],
        target_text: str,
        match_mode: str,
        region: Optional[Tuple[int, int, int, int]],
        candidates: List[Dict[str, Any]],
    ) -> None:
        current_info = self._build_node_info(node)

        matched_value = None
        matched_field = None
        for field_name in ('text', 'content_desc'):
            field_value = current_info.get(field_name) or ''
            if self._matches_target(field_value, target_text, match_mode):
                matched_value = field_value
                matched_field = field_name
                break

        if matched_value and current_info.get('enabled', True):
            click_target = self._resolve_click_target(current_info, ancestors)
            if click_target and click_target.get('bounds'):
                center = self._center_from_bounds(click_target['bounds'])
                if region is None or self._point_in_region(center, region):
                    candidates.append(
                        {
                            'text': matched_value,
                            'matched_field': matched_field,
                            'center': center,
                            'bbox': self._bbox_from_bounds(click_target['bounds']),
                            'resource_id': click_target.get('resource_id') or current_info.get('resource_id', ''),
                            'class_name': click_target.get('class_name') or current_info.get('class_name', ''),
                            'source': 'ui_hierarchy',
                        }
                    )

        next_ancestors = [*ancestors, current_info]
        for child in list(node):
            self._collect_matches(child, next_ancestors, target_text, match_mode, region, candidates)

    def find_text(
        self,
        target_text: str,
        match_mode: str = 'contains',
        region: Optional[Tuple[int, int, int, int]] = None,
        index: int = 0,
    ) -> Optional[Dict[str, Any]]:
        if not target_text:
            return None

        xml_content = self.dump_hierarchy_xml()
        if not xml_content:
            return None

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as exc:
            logger.warning(f"解析 Android 视图树失败: {exc}")
            return None

        candidates: List[Dict[str, Any]] = []
        self._collect_matches(root, [], target_text, match_mode, region, candidates)
        candidates.sort(key=lambda item: (item['bbox'][0][1], item['bbox'][0][0]))

        if not candidates:
            return None
        if -len(candidates) <= index < len(candidates):
            return candidates[index]
        return None

    def _collect_nodes(self, node: ET.Element, nodes: List[Dict[str, Any]]) -> None:
        nodes.append(self._build_node_info(node))
        for child in list(node):
            self._collect_nodes(child, nodes)

    @staticmethod
    def _vertical_gap(left: Tuple[int, int, int, int], right: Tuple[int, int, int, int]) -> int:
        if right[1] > left[3]:
            return right[1] - left[3]
        if left[1] > right[3]:
            return left[1] - right[3]
        return 0

    @staticmethod
    def _horizontal_gap(left: Tuple[int, int, int, int], right: Tuple[int, int, int, int]) -> int:
        if right[0] > left[2]:
            return right[0] - left[2]
        if left[0] > right[2]:
            return left[0] - right[2]
        return 0

    def _is_input_like(self, node_info: Dict[str, Any]) -> bool:
        class_name = str(node_info.get('class_name') or '').lower()
        resource_id = str(node_info.get('resource_id') or '').lower()
        return any(token in class_name for token in ('edittext', 'textfield', 'autocomplete', 'input')) or any(
            token in resource_id for token in ('edit', 'input', 'account', 'password', 'pwd')
        )

    def _find_nearest_value_node(
        self,
        label: Dict[str, Any],
        nodes: List[Dict[str, Any]],
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        label_bounds = label.get('bounds')
        if not self._has_visible_bounds(label_bounds):
            return None

        label_center = self._center_from_bounds(label_bounds)
        label_x1, _label_y1, label_x2, _label_y2 = label_bounds
        ranked_candidates: List[Tuple[int, Dict[str, Any]]] = []

        for node in nodes:
            if node is label:
                continue

            bounds = node.get('bounds')
            if not self._has_visible_bounds(bounds):
                continue

            center = self._center_from_bounds(bounds)
            if region is not None and not self._point_in_region(center, region):
                continue

            text_value = (node.get('text') or node.get('content_desc') or node.get('hint_text') or '').strip()
            is_input_like = self._is_input_like(node)
            if not text_value and not is_input_like:
                continue

            vertical_gap = self._vertical_gap(label_bounds, bounds)
            if vertical_gap > 120:
                continue

            if bounds[0] < label_x1 - 80 and bounds[2] < label_x2:
                continue

            horizontal_gap = self._horizontal_gap(label_bounds, bounds)
            score = vertical_gap * 1000 + max(horizontal_gap, 0) * 10 + abs(center[1] - label_center[1])
            if not is_input_like:
                score += 5000
            ranked_candidates.append((score, node))

        ranked_candidates.sort(key=lambda item: item[0])
        return ranked_candidates[0][1] if ranked_candidates else None

    def _is_candidate_empty(self, node_info: Dict[str, Any], normalized_target: str) -> Optional[bool]:
        text_value = self._normalize_text(node_info.get('text'))
        content_desc = self._normalize_text(node_info.get('content_desc'))
        hint_text = self._normalize_text(node_info.get('hint_text'))
        visible_values = [value for value in (text_value, content_desc) if value]

        if any(value != normalized_target for value in visible_values):
            return False
        if any(value == normalized_target for value in visible_values):
            return True
        if hint_text == normalized_target:
            return True
        if self._is_input_like(node_info):
            return True
        return None

    def is_field_empty(
        self,
        target_text: str,
        region: Optional[Tuple[int, int, int, int]] = None,
        force_refresh: bool = False,
    ) -> Optional[bool]:
        if not target_text:
            return None

        xml_content = self.dump_hierarchy_xml(force_refresh=force_refresh)
        if not xml_content:
            return None

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as exc:
            logger.warning(f"解析 Android 视图树失败: {exc}")
            return None

        nodes: List[Dict[str, Any]] = []
        self._collect_nodes(root, nodes)
        normalized_target = self._normalize_text(target_text)
        matching_labels: List[Dict[str, Any]] = []

        for node_info in nodes:
            if not node_info.get('enabled', True):
                continue

            bounds = node_info.get('bounds')
            if region is not None:
                if not self._has_visible_bounds(bounds):
                    continue
                center = self._center_from_bounds(bounds)
                if not self._point_in_region(center, region):
                    continue

            for field_name in ('text', 'content_desc', 'hint_text'):
                field_value = node_info.get(field_name) or ''
                if self._matches_target(field_value, target_text, 'contains'):
                    matching_labels.append(node_info)
                    break

        for label in matching_labels:
            if self._is_input_like(label):
                result = self._is_candidate_empty(label, normalized_target)
                if result is not None:
                    return result

            nearby = self._find_nearest_value_node(label, nodes, region)
            if nearby is None:
                continue

            result = self._is_candidate_empty(nearby, normalized_target)
            if result is not None:
                return result

        return None
