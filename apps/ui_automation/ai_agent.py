import asyncio
import logging
import sys

from .ai_base import BaseBrowserAgent

logger = logging.getLogger('django')


class BrowserAgent(BaseBrowserAgent):
    """
    Standard Browser Agent for Text Mode.
    Inherits all base functionality without applying dangerous visual patches.
    """

    def __init__(self, execution_mode='text', enable_gif=True, case_name=None):
        self.enable_gif = enable_gif
        self.case_name = case_name or "Adhoc Task"
        super().__init__(execution_mode='text')


# ============================================================================
# EXPORTED FUNCTIONS (FACTORY)
# ============================================================================


def _run_coroutine_in_compatible_loop(coro):
    """Use a Windows Proactor loop so browser-use can spawn subprocesses in worker threads."""
    if sys.platform == 'win32' and hasattr(asyncio, 'ProactorEventLoop'):
        runner_cls = getattr(asyncio, 'Runner', None)
        if runner_cls is not None:
            logger.debug("Using Windows Proactor event loop for browser-use execution")
            with runner_cls(loop_factory=asyncio.ProactorEventLoop) as runner:
                return runner.run(coro)

        loop = asyncio.ProactorEventLoop()
        try:
            logger.debug("Using fallback Windows Proactor event loop for browser-use execution")
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            try:
                loop.run_until_complete(loop.shutdown_default_executor())
            except Exception:
                pass
            asyncio.set_event_loop(None)
            loop.close()

    return asyncio.run(coro)


def get_agent_class(execution_mode='text'):
    # 始终返回文本模式实现
    return BrowserAgent


def run_ai_task_sync(task_description: str, planned_tasks=None, callback=None, should_stop=None, execution_mode='text'):
    agent = BrowserAgent(execution_mode='text')
    return _run_coroutine_in_compatible_loop(agent.run_task(task_description, planned_tasks, callback, should_stop))


def analyze_task_sync(task_description: str, execution_mode='text'):
    agent = BrowserAgent(execution_mode='text')
    return _run_coroutine_in_compatible_loop(agent.analyze_task(task_description))


def run_full_process_sync(task_description: str, analysis_callback=None, step_callback=None, should_stop=None, execution_mode='text', enable_gif=True, case_name=None):
    logger.info(f"DEBUG: Entering run_full_process_sync with execution_mode=text, enable_gif={enable_gif}")

    agent = BrowserAgent(execution_mode='text', enable_gif=enable_gif, case_name=case_name)

    logger.info(f"DEBUG: Agent created successfully ({type(agent).__name__}), starting async runner")
    return _run_coroutine_in_compatible_loop(
        agent.run_full_process(task_description, analysis_callback, step_callback, should_stop)
    )
