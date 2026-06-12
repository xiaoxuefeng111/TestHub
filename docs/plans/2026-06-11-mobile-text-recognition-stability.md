# Mobile Text Recognition Stability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让移动端 AI 执行的文字定位链路在“元素树不可见、OCR 需要兜底”的场景下仍然稳定、可诊断、可复现，并避免把 OCR 环境异常误报成“未找到文字”。

**Architecture:** 保留 `UiFlowRunner` 作为执行中心，新增统一的 `_locate_text()` 入口，把 `wait_text`、`tap_text`、`swipe_until_text`、`assert_text_visible` 全部收口到同一条文字定位链路。定位链路固定为“UI hierarchy → 单次截图 → OCR 原图候选 → OCR 增强候选 → 候选打分 → 结构化结果/结构化错误”，同时在 `OCRHelper` 中补齐离线就绪检查、多变体识别与候选聚合能力。

**Tech Stack:** Django、Airtest、EasyOCR、OpenCV、Pillow、pytest、unittest.mock。

---

### Task 1: 为统一文字定位链路写失败测试基线

**Files:**
- Modify: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`
- Test: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`

**Step 1: Write the failing test**

在 `UiFlowRunnerMobileActionsTests` 中新增这些测试，先定义期望行为：

```python
@mock.patch('apps.app_automation.runners.ui_flow_runner.touch')
def test_locate_text_prefers_ui_hierarchy_before_ocr(self, mock_touch):
    runner = UiFlowRunner(username='tester', device_id='device-1')
    runner._ui_hierarchy_helper = mock.Mock()
    runner._ui_hierarchy_helper.find_text.return_value = {
        'text': '交易',
        'center': (900, 1998),
        'bbox': [(720, 1959), (1080, 1959), (1080, 2037), (720, 2037)],
        'source': 'ui_hierarchy',
    }
    runner._ocr_helper = mock.Mock()

    result = runner._locate_text({'text': '交易', 'match_mode': 'exact'})

    self.assertEqual(result['status'], 'found')
    self.assertEqual(result['source'], 'ui_hierarchy')
    runner._ocr_helper.find_text_candidates.assert_not_called()


def test_wait_text_raises_runtime_error_when_ocr_is_unavailable(self):
    runner = UiFlowRunner(username='tester')
    runner._locate_text = mock.Mock(return_value={
        'status': 'ocr_unavailable',
        'source': None,
        'matched_text': None,
        'confidence': 0.0,
        'center': None,
        'bbox': None,
        'candidates': [],
        'reason': 'OCR model missing',
        'screenshot_path': 'fake.png',
    })

    with self.assertRaisesRegex(RuntimeError, 'OCR'):
        runner._action_wait_text({'text': '买入', 'timeout': 0.1, 'interval': 0.01})
```

再补一个“增强 OCR 命中”的测试，约束后续实现必须支持 raw miss、enhanced hit：

```python
def test_locate_text_uses_enhanced_ocr_candidates_when_raw_misses(self):
    runner = UiFlowRunner(username='tester')
    runner._ui_hierarchy_helper = mock.Mock()
    runner._ui_hierarchy_helper.find_text.return_value = None
    runner._ocr_helper = mock.Mock()
    runner._ocr_helper.ensure_ready.return_value = {
        'ready': True,
        'error_code': None,
        'reason': ''
    }
    runner._ocr_helper.find_text_candidates.return_value = [
        {
            'text': '买入',
            'confidence': 0.91,
            'center': (120, 540),
            'bbox': [(80, 500), (160, 500), (160, 580), (80, 580)],
            'variant': 'scaled_2x',
            'source': 'ocr_enhanced',
        }
    ]

    result = runner._locate_text({'text': '买入', 'match_mode': 'exact'})

    self.assertEqual(result['status'], 'found')
    self.assertEqual(result['source'], 'ocr_enhanced')
    self.assertEqual(result['matched_text'], '买入')
```

**Step 2: Run test to verify it fails**

Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

Expected: FAIL，因为当前 `UiFlowRunner` 还没有 `_locate_text()`、结构化返回、`find_text_candidates()` 和 OCR 环境错误分流。

**Step 3: Write minimal implementation**

先只补出最小骨架，不做完整功能：

```python
def _empty_locate_result(self, status: str, reason: str = '') -> Dict[str, Any]:
    return {
        'status': status,
        'source': None,
        'matched_text': None,
        'confidence': 0.0,
        'center': None,
        'bbox': None,
        'candidates': [],
        'reason': reason,
        'screenshot_path': None,
    }
```

```python
def _locate_text(self, step: Dict[str, Any]) -> Dict[str, Any]:
    raise NotImplementedError
```

目标不是一次做完，而是把测试先挂到真实入口上。

**Step 4: Run test to verify it passes or fails in the new expected place**

Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

Expected: 失败点收敛到 `_locate_text()` 真实逻辑缺失，而不是旧的 `find_text()` 行为混在一起。

**Step 5: Commit**

```bash
git add apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py apps/app_automation/runners/ui_flow_runner.py
git commit -m "test: define mobile text locate stability baseline"
```

---

### Task 2: 为 OCRHelper 增加离线就绪检查和多变体候选聚合

**Files:**
- Modify: `apps/app_automation/utils/ocr_helper.py`
- Create: `apps/app_automation/tests/test_ocr_helper.py`
- Test: `apps/app_automation/tests/test_ocr_helper.py`

**Step 1: Write the failing test**

新建 `apps/app_automation/tests/test_ocr_helper.py`，先锁定两个能力：

1. 模型不存在时返回明确环境错误，而不是到了运行时才下载。
2. 同一张图能够生成 raw + enhanced 候选列表。

```python
from unittest import mock
from django.test import SimpleTestCase
from apps.app_automation.utils.ocr_helper import OCRHelper


class OCRHelperTests(SimpleTestCase):
    def test_ensure_ready_returns_model_missing_when_model_dir_is_empty(self):
        helper = OCRHelper(languages=['ch_sim', 'en'], use_gpu=False)

        with mock.patch.object(helper, '_model_files_present', return_value=False):
            result = helper.ensure_ready()

        self.assertFalse(result['ready'])
        self.assertEqual(result['error_code'], 'OCR_MODEL_MISSING')

    def test_find_text_candidates_merges_candidates_from_multiple_variants(self):
        helper = OCRHelper(languages=['ch_sim', 'en'], use_gpu=False)
        fake_image = mock.Mock()

        with mock.patch.object(helper, 'build_image_variants', return_value={
            'raw': fake_image,
            'scaled_2x': fake_image,
        }), mock.patch.object(helper, 'recognize_with_boxes', side_effect=[
            [],
            [
                {
                    'text': '买入',
                    'confidence': 0.91,
                    'bbox': [(80, 500), (160, 500), (160, 580), (80, 580)],
                    'center': (120, 540),
                }
            ],
        ]):
            candidates = helper.find_text_candidates('买入', match_mode='exact', image=fake_image)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['variant'], 'scaled_2x')
        self.assertEqual(candidates[0]['source'], 'ocr_enhanced')
```

**Step 2: Run test to verify it fails**

Run: `pytest apps/app_automation/tests/test_ocr_helper.py -v`

Expected: FAIL，因为当前 `OCRHelper` 没有 `ensure_ready()`、`_model_files_present()`、`build_image_variants()`、`find_text_candidates()`。

**Step 3: Write minimal implementation**

在 `ocr_helper.py` 中补齐最小实现：

```python
def _model_files_present(self) -> bool:
    model_dir = os.path.join(os.path.expanduser('~'), '.EasyOCR', 'model')
    return os.path.isdir(model_dir) and any(os.scandir(model_dir))
```

```python
def ensure_ready(self) -> Dict[str, Any]:
    if not self._model_files_present():
        return {
            'ready': False,
            'error_code': 'OCR_MODEL_MISSING',
            'reason': 'EasyOCR model directory is empty',
        }
    try:
        self.get_easyocr_reader(self.languages, self.use_gpu)
        return {'ready': True, 'error_code': None, 'reason': ''}
    except Exception as exc:
        return {
            'ready': False,
            'error_code': 'OCR_INIT_FAILED',
            'reason': str(exc),
        }
```

```python
def build_image_variants(self, image: Image.Image) -> Dict[str, Image.Image]:
    grayscale = image.convert('L')
    scaled_2x = image.resize((image.width * 2, image.height * 2))
    threshold = grayscale.point(lambda p: 255 if p > 160 else 0)
    return {
        'raw': image,
        'scaled_2x': scaled_2x,
        'grayscale': grayscale,
        'threshold': threshold,
    }
```

```python
def find_text_candidates(self, target_text: str, match_mode: str = 'contains', region=None, image=None, screenshot_path=None, min_confidence: float = 0.3) -> List[Dict[str, Any]]:
    # 读取一次图片，遍历 variants，聚合候选，补齐 variant/source/confidence
    ...
```

**Step 4: Run test to verify it passes**

Run: `pytest apps/app_automation/tests/test_ocr_helper.py -v`

Expected: PASS。

**Step 5: Commit**

```bash
git add apps/app_automation/utils/ocr_helper.py apps/app_automation/tests/test_ocr_helper.py
git commit -m "feat: add OCR readiness check and candidate variants"
```

---

### Task 3: 在 UiFlowRunner 中实现统一 `_locate_text()` 和结构化错误

**Files:**
- Modify: `apps/app_automation/runners/ui_flow_runner.py`
- Modify: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`
- Test: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`

**Step 1: Write the failing test**

围绕 `_locate_text()` 的完整行为再补三类测试：

```python
def test_locate_text_returns_not_found_with_candidates_when_no_match(self):
    runner = UiFlowRunner(username='tester')
    runner._ui_hierarchy_helper = mock.Mock()
    runner._ui_hierarchy_helper.find_text.return_value = None
    runner._ocr_helper = mock.Mock()
    runner._ocr_helper.ensure_ready.return_value = {'ready': True, 'error_code': None, 'reason': ''}
    runner._ocr_helper.find_text_candidates.return_value = []
    runner._capture_text_search_screenshot = mock.Mock(return_value='fake.png')

    result = runner._locate_text({'text': '买入'})

    self.assertEqual(result['status'], 'not_found')
    self.assertEqual(result['screenshot_path'], 'fake.png')
    self.assertEqual(result['candidates'], [])


def test_locate_text_returns_ocr_unavailable_when_helper_not_ready(self):
    runner = UiFlowRunner(username='tester')
    runner._ui_hierarchy_helper = mock.Mock()
    runner._ui_hierarchy_helper.find_text.return_value = None
    runner._ocr_helper = mock.Mock()
    runner._ocr_helper.ensure_ready.return_value = {
        'ready': False,
        'error_code': 'OCR_MODEL_MISSING',
        'reason': 'EasyOCR model directory is empty',
    }
    runner._capture_text_search_screenshot = mock.Mock(return_value='fake.png')

    result = runner._locate_text({'text': '买入'})

    self.assertEqual(result['status'], 'ocr_unavailable')
    self.assertIn('EasyOCR', result['reason'])
```

**Step 2: Run test to verify it fails**

Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

Expected: FAIL，因为 runner 还没有截图复用、候选打分和结构化错误分类。

**Step 3: Write minimal implementation**

在 `ui_flow_runner.py` 中补齐这些方法：

```python
def _capture_text_search_screenshot(self) -> Optional[str]:
    # 只截一次图，保存到临时路径，供 raw/enhanced OCR 共用
    ...
```

```python
def _score_text_candidate(self, candidate: Dict[str, Any], target_text: str, match_mode: str, region: Optional[tuple]) -> float:
    # 文本匹配度 + OCR 置信度 + 区域优先级
    ...
```

```python
def _locate_text(self, step: Dict[str, Any]) -> Dict[str, Any]:
    text_value = self._render_value(step.get('text') or step.get('target_text') or '')
    match_mode = str(step.get('match_mode', 'contains')).lower()
    region = self._parse_region_value(step.get('region'))
    index = int(step.get('index', 0) or 0)
    min_confidence = float(step.get('min_confidence', 0.3) or 0.3)

    hierarchy_match = self._find_text_match_with_ui_hierarchy(text_value, match_mode, region, index)
    if hierarchy_match:
        return {
            'status': 'found',
            'source': 'ui_hierarchy',
            'matched_text': hierarchy_match['text'],
            'confidence': 1.0,
            'center': hierarchy_match['center'],
            'bbox': hierarchy_match['bbox'],
            'candidates': [hierarchy_match],
            'reason': '',
            'screenshot_path': None,
        }

    screenshot_path = self._capture_text_search_screenshot()
    readiness = self._get_ocr_helper().ensure_ready()
    if not readiness['ready']:
        return {
            **self._empty_locate_result('ocr_unavailable', readiness['reason']),
            'screenshot_path': screenshot_path,
        }

    candidates = self._get_ocr_helper().find_text_candidates(
        text_value,
        match_mode=match_mode,
        region=region,
        screenshot_path=screenshot_path,
        min_confidence=min_confidence,
    )
    ...
```

保留旧的 `_find_text_match()`，但改成薄包装，避免一次性触碰太多调用点：

```python
def _find_text_match(self, step: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    result = self._locate_text(step)
    if result['status'] == 'found':
        return {
            'text': result['matched_text'],
            'center': result['center'],
            'bbox': result['bbox'],
            'source': result['source'],
        }
    return None
```

**Step 4: Run test to verify it passes**

Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

Expected: PASS。

**Step 5: Commit**

```bash
git add apps/app_automation/runners/ui_flow_runner.py apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py
git commit -m "feat: add structured mobile text locate pipeline"
```

---

### Task 4: 让所有文字动作消费结构化结果，并记录可回放诊断日志

**Files:**
- Modify: `apps/app_automation/runners/ui_flow_runner.py`
- Modify: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`
- Test: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`

**Step 1: Write the failing test**

补动作层测试，明确不同失败类型的行为：

```python
@mock.patch('apps.app_automation.runners.ui_flow_runner.touch')
def test_tap_text_uses_locate_result_center(self, mock_touch):
    runner = UiFlowRunner(username='tester')
    runner._locate_text = mock.Mock(return_value={
        'status': 'found',
        'source': 'ocr_enhanced',
        'matched_text': '买入',
        'confidence': 0.91,
        'center': (120, 540),
        'bbox': [(80, 500), (160, 500), (160, 580), (80, 580)],
        'candidates': [],
        'reason': '',
        'screenshot_path': 'fake.png',
    })

    runner._action_tap_text({'text': '买入'})

    mock_touch.assert_called_once_with((120, 540))


def test_wait_text_retries_on_not_found_until_timeout(self):
    runner = UiFlowRunner(username='tester')
    runner._locate_text = mock.Mock(side_effect=[
        {'status': 'not_found', 'reason': '', 'source': None, 'matched_text': None, 'confidence': 0.0, 'center': None, 'bbox': None, 'candidates': [], 'screenshot_path': '1.png'},
        {'status': 'found', 'reason': '', 'source': 'ocr_raw', 'matched_text': '买入', 'confidence': 0.8, 'center': (120, 540), 'bbox': [(80, 500), (160, 500), (160, 580), (80, 580)], 'candidates': [], 'screenshot_path': '2.png'},
    ])

    runner._action_wait_text({'text': '买入', 'timeout': 1, 'interval': 0.01})
    self.assertEqual(runner._locate_text.call_count, 2)
```

**Step 2: Run test to verify it fails**

Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

Expected: FAIL，因为动作层还没有按 `status` 分流。

**Step 3: Write minimal implementation**

在 `ui_flow_runner.py` 中新增统一错误出口：

```python
def _raise_locate_error(self, text_value: str, result: Dict[str, Any]) -> None:
    status = result.get('status')
    reason = result.get('reason') or ''
    if status == 'ocr_unavailable':
        raise RuntimeError(f'OCR 不可用，无法识别目标文字: {text_value}；{reason}')
    raise ValueError(f'未找到目标文字: {text_value}')
```

然后分别改造动作：

```python
def _action_tap_text(self, step: Dict[str, Any]):
    result = self._locate_text(step)
    if result['status'] != 'found':
        self._raise_locate_error(text_value, result)
    touch(result['center'])
```

```python
def _action_wait_text(self, step: Dict[str, Any]):
    while True:
        result = self._locate_text(step)
        if result['status'] == 'found':
            return
        if result['status'] == 'ocr_unavailable':
            self._raise_locate_error(text_value, result)
        if time.time() >= deadline:
            self._raise_locate_error(text_value, result)
        time.sleep(interval)
```

给日志补一条结构化摘要，便于之后排查：

```python
logger.info(
    'locate_text target=%s status=%s source=%s confidence=%s screenshot=%s reason=%s',
    text_value,
    result.get('status'),
    result.get('source'),
    result.get('confidence'),
    result.get('screenshot_path'),
    result.get('reason'),
)
```

**Step 4: Run test to verify it passes**

Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py -v`

Expected: PASS。

**Step 5: Commit**

```bash
git add apps/app_automation/runners/ui_flow_runner.py apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py
git commit -m "feat: route mobile text actions through structured locate results"
```

---

### Task 5: 加入轻量区域优先级并完成回归验证

**Files:**
- Modify: `apps/app_automation/runners/ui_flow_runner.py`
- Modify: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`
- Test: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`
- Test: `apps/app_automation/tests/test_ocr_helper.py`

**Step 1: Write the failing test**

为候选排序加一个稳定性测试：同分词候选中，优先选择符合页面区域先验的按钮。

```python
def test_locate_text_prefers_candidate_inside_preferred_region(self):
    runner = UiFlowRunner(username='tester')
    candidates = [
        {
            'text': '买入',
            'confidence': 0.88,
            'center': (120, 540),
            'bbox': [(80, 500), (160, 500), (160, 580), (80, 580)],
            'variant': 'raw',
            'source': 'ocr_raw',
        },
        {
            'text': '买入',
            'confidence': 0.89,
            'center': (120, 1750),
            'bbox': [(80, 1710), (160, 1710), (160, 1790), (80, 1790)],
            'variant': 'raw',
            'source': 'ocr_raw',
        },
    ]

    best = runner._select_best_text_candidate(
        candidates,
        target_text='买入',
        match_mode='exact',
        region=None,
        preferred_region=(0, 200, 1080, 1000),
    )

    self.assertEqual(best['center'], (120, 540))
```

**Step 2: Run test to verify it fails**

Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py apps/app_automation/tests/test_ocr_helper.py -v`

Expected: FAIL，因为当前还没有 `preferred_region` / `_select_best_text_candidate()`。

**Step 3: Write minimal implementation**

仅做轻量版，不做复杂页面分类系统：

```python
def _resolve_preferred_region(self, step: Dict[str, Any]) -> Optional[tuple]:
    region = step.get('preferred_region')
    if region:
        return self._parse_region_value(region)
    return None
```

```python
def _select_best_text_candidate(self, candidates, target_text, match_mode, region=None, preferred_region=None):
    scored = []
    for candidate in candidates:
        score = self._score_text_candidate(candidate, target_text, match_mode, region)
        if preferred_region and self._point_in_region(candidate['center'], preferred_region):
            score += 0.2
        scored.append((score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored else None
```

只支持动作级显式传入 `preferred_region`，不要这次就上页面模板注册系统，保持改动最小。

**Step 4: Run full targeted regression suite**

Run: `pytest apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py apps/app_automation/tests/test_ocr_helper.py apps/app_automation/tests/test_android_ui_hierarchy.py apps/app_automation/tests/test_app_executor.py -v`

Expected: PASS。

再补一次最贴近本问题的回归验证：

Run: `pytest apps/ui_automation/tests/test_ai_run_adhoc_mobile.py -v`

Expected: PASS，确认移动端 AI 入口没有被本次 runner 改造破坏。

**Step 5: Commit**

```bash
git add apps/app_automation/runners/ui_flow_runner.py apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py apps/app_automation/tests/test_ocr_helper.py
git commit -m "feat: prioritize stable OCR candidates for mobile text locate"
```
