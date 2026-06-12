# Mobile Semantic Safety Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce random mobile execution by preferring strict semantic parsing, rejecting unsupported structured steps, and only falling back to LLM for clearly non-structured tasks.

**Architecture:** Keep the existing `mobile_semantic_parser -> mobile_plan_validator -> mobile_agent -> ui_flow_runner` chain, but make the parser produce explicit unsupported-step metadata and expected page text steps. The planner should fail closed for structured tasks when semantic validation fails instead of silently falling back to LLM/heuristics.

**Tech Stack:** Django, Python, unittest, existing mobile UI flow runner

---

### Task 1: Red tests for stricter semantic coverage

**Files:**
- Modify: `apps/ui_automation/tests/test_mobile_semantic_parser.py`
- Modify: `apps/ui_automation/tests/test_mobile_agent.py`

**Step 1: Write the failing tests**
- Add a parser test that expects `点击买入按钮，会弹出交易登录界面` to preserve the expected page text as a semantic wait step.
- Add a parser/validator test that expects unsupported structured steps to be recorded and rejected.
- Add a planner test that expects structured semantic failures to stop execution without calling LLM.

**Step 2: Run tests to verify they fail**
Run: `python manage.py test apps.ui_automation.tests.test_mobile_semantic_parser apps.ui_automation.tests.test_mobile_agent --verbosity 1`
Expected: FAIL on the new safety expectations.

**Step 3: Commit**
```bash
git add apps/ui_automation/tests/test_mobile_semantic_parser.py apps/ui_automation/tests/test_mobile_agent.py
git commit -m "test: cover strict mobile semantic safety"
```

### Task 2: Minimal parser and validator hardening

**Files:**
- Modify: `apps/ui_automation/mobile_semantic_parser.py`
- Modify: `apps/ui_automation/mobile_plan_validator.py`

**Step 1: Write minimal implementation**
- Extend `should_parse` so numbered/imperative mobile tasks enter the semantic path more often.
- Record unsupported structured steps in the semantic plan instead of silently dropping them.
- Parse simple expected page text (`弹出/进入...界面`) into a semantic wait step.
- Make validator reject any plan that contains unsupported structured steps.

**Step 2: Run focused tests**
Run: `python manage.py test apps.ui_automation.tests.test_mobile_semantic_parser --verbosity 1`
Expected: PASS

**Step 3: Commit**
```bash
git add apps/ui_automation/mobile_semantic_parser.py apps/ui_automation/mobile_plan_validator.py
 git commit -m "feat: harden mobile semantic parsing safety"
```

### Task 3: Planner fail-closed behavior

**Files:**
- Modify: `apps/ui_automation/mobile_agent.py`
- Test: `apps/ui_automation/tests/test_mobile_agent.py`

**Step 1: Write minimal implementation**
- If a task is considered structured enough for semantic parsing, and semantic validation fails, raise a safe planning error instead of falling back to LLM/heuristics.
- Keep current fallback only for clearly non-structured tasks.

**Step 2: Run targeted tests**
Run: `python manage.py test apps.ui_automation.tests.test_mobile_agent apps.ui_automation.tests.test_ai_run_adhoc_mobile apps.ui_automation.tests.test_ai_execution_record_mobile apps.app_automation.tests.test_ui_flow_runner_mobile_actions --verbosity 1`
Expected: PASS

**Step 3: Commit**
```bash
git add apps/ui_automation/mobile_agent.py apps/ui_automation/tests/test_mobile_agent.py
git commit -m "feat: fail closed for unsupported mobile semantic tasks"
```

### Task 4: Final regression check

**Files:**
- Test: `apps/ui_automation/tests/test_mobile_semantic_parser.py`
- Test: `apps/ui_automation/tests/test_mobile_agent.py`
- Test: `apps/ui_automation/tests/test_ai_run_adhoc_mobile.py`
- Test: `apps/ui_automation/tests/test_ai_execution_record_mobile.py`
- Test: `apps/app_automation/tests/test_ui_flow_runner_mobile_actions.py`

**Step 1: Run the regression suite**
Run: `python manage.py test apps.ui_automation.tests.test_mobile_semantic_parser apps.ui_automation.tests.test_mobile_agent apps.ui_automation.tests.test_ai_run_adhoc_mobile apps.ui_automation.tests.test_ai_execution_record_mobile apps.app_automation.tests.test_ui_flow_runner_mobile_actions --verbosity 1`
Expected: PASS

**Step 2: Commit**
```bash
git add docs/plans/2026-06-12-mobile-semantic-safety-implementation.md
git commit -m "docs: add mobile semantic safety implementation plan"
```