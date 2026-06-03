"""
Zenith Async Scheduler - Asynchronous Task Scheduling and Execution Engine

Provides:
- Task prioritization (critical, high, normal, low)
- Dependency management (DAG execution)
- Concurrency control (semaphore-based)
- Task timeout and cancellation
- Progress tracking and metrics
- Error handling and retry logic

Usage:
    scheduler = AsyncScheduler(max_concurrent=5)
    await scheduler.start()
    
    # Add tasks with dependencies
    task1 = await scheduler.add_task(process_data, args=(data,), priority=TaskPriority.HIGH)
    task2 = await scheduler.add_task(analyze_results, deps=[task1], priority=TaskPriority.NORMAL)
    
    # Wait for completion
    await scheduler.wait_for(task2)
    await scheduler.shutdown()
"""
from __future__ import annotations
import asyncio
import logging
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set
from uuid import uuid4

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class TaskState(Enum):
    """Task execution states."""
    PENDING = "pending"
    WAITING = "waiting"  # waiting for dependencies
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskMetrics:
    """Metrics for a single task."""
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    
    @property
    def wait_time(self) -> float:
        if self.started_at is None:
            return time.time() - self.created_at
        return self.started_at - self.created_at
    
    @property
    def execution_time(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        return end - self.started_at


@dataclass
class Task:
    """Represents a scheduled task."""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    func: Callable[..., Coroutine] = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    state: TaskState = TaskState.PENDING
    deps: List[str] = field(default_factory=list)
    timeout: Optional[float] = None
    max_retries: int = 0
    result: Any = None
    error: Optional[Exception] = None
    metrics: TaskMetrics = field(default_factory=TaskMetrics)
    _event: asyncio.Event = field(default_factory=asyncio.Event)
    
    @property
    def is_terminal(self) -> bool:
        return self.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED)
    
    async def wait(self) -> Any:
        """Wait for task completion and return result."""
        await self._event.wait()
        if self.error:
            raise self.error
        return self.result


@dataclass
class SchedulerMetrics:
    """Global scheduler metrics."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    peak_concurrency: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.completed_tasks / self.total_tasks


class AsyncScheduler:
    """
    Asynchronous task scheduler with priority queues and dependency resolution.
    
    Features:
    - Priority-based scheduling (critical > high > normal > low)
    - DAG dependency resolution
    - Configurable concurrency limit
    - Task timeout and cancellation
    - Retry with exponential backoff
    - Comprehensive metrics collection
    """
    
    def __init__(self, max_concurrent: int = 5, default_timeout: float = 300.0):
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.tasks: Dict[str, Task] = {}
        self.metrics = SchedulerMetrics()
        self._running = False
        self._workers: List[asyncio.Task] = []
        self._dispatch_event = asyncio.Event()
    
    async def start(self):
        """Start the scheduler."""
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(), name=f"worker-{i}")
            for i in range(self.max_concurrent)
        ]
        logger.info(f"Scheduler started with {self.max_concurrent} workers")
    
    async def shutdown(self, wait: bool = True, timeout: float = 10.0):
        """Shutdown the scheduler gracefully."""
        self._running = False
        self._dispatch_event.set()
        
        if wait:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._workers, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                for w in self._workers:
                    w.cancel()
        
        logger.info(
            f"Scheduler shut down. "
            f"Metrics: {self.metrics.completed_tasks}/{self.metrics.total_tasks} completed, "
            f"success rate: {self.metrics.success_rate:.1%}"
        )
    
    async def add_task(
        self,
        func: Callable[..., Coroutine],
        args: tuple = (),
        kwargs: dict = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        deps: List[str] = None,
        timeout: Optional[float] = None,
        max_retries: int = 0,
    ) -> str:
        """Add a new task to the scheduler. Returns task ID."""
        task = Task(
            func=func,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            deps=deps or [],
            timeout=timeout or self.default_timeout,
            max_retries=max_retries,
        )
        
        self.tasks[task.id] = task
        self.metrics.total_tasks += 1
        
        # Check if dependencies are met
        if self._deps_satisfied(task):
            task.state = TaskState.READY
        
        self._dispatch_event.set()
        logger.debug(f"Task {task.id} added (priority={priority.name}, deps={len(task.deps)})")
        return task.id
    
    async def wait_for(self, task_id: str) -> Any:
        """Wait for a specific task to complete."""
        task = self.tasks.get(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        return await task.wait()
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        task = self.tasks.get(task_id)
        if task is None or task.is_terminal:
            return False
        
        if task.state == TaskState.RUNNING:
            # Can't cancel running task directly, mark for cancellation
            task.state = TaskState.CANCELLED
        else:
            task.state = TaskState.CANCELLED
            task._event.set()
        
        self.metrics.cancelled_tasks += 1
        logger.debug(f"Task {task_id} cancelled")
        return True
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def _deps_satisfied(self, task: Task) -> bool:
        """Check if all dependencies are completed."""
        return all(
            self.tasks.get(dep) and self.tasks[dep].state == TaskState.COMPLETED
            for dep in task.deps
        )
    
    def _get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to run, sorted by priority."""
        ready = []
        for task in self.tasks.values():
            if task.state == TaskState.PENDING and self._deps_satisfied(task):
                task.state = TaskState.READY
                ready.append(task)
            elif task.state == TaskState.READY:
                ready.append(task)
        
        # Sort by priority (lower enum value = higher priority)
        ready.sort(key=lambda t: t.priority.value)
        return ready
    
    async def _worker(self):
        """Worker coroutine that processes tasks."""
        while self._running:
            try:
                ready_tasks = self._get_ready_tasks()
                
                if not ready_tasks:
                    # Wait for new tasks or completions
                    self._dispatch_event.clear()
                    try:
                        await asyncio.wait_for(self._dispatch_event.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                
                for task in ready_tasks:
                    if not self._running or task.state == TaskState.CANCELLED:
                        continue
                    
                    async with self.semaphore:
                        if task.state == TaskState.CANCELLED:
                            continue
                        
                        task.state = TaskState.RUNNING
                        task.metrics.started_at = time.time()
                        
                        running_count = sum(
                            1 for t in self.tasks.values() if t.state == TaskState.RUNNING
                        )
                        self.metrics.peak_concurrency = max(
                            self.metrics.peak_concurrency, running_count
                        )
                        
                        await self._execute_task(task)
                        self._dispatch_event.set()
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(0.1)
    
    async def _execute_task(self, task: Task):
        """Execute a single task with timeout and retry logic."""
        retries = 0
        
        while retries <= task.max_retries:
            try:
                result = await asyncio.wait_for(
                    task.func(*task.args, **task.kwargs),
                    timeout=task.timeout
                )
                task.result = result
                task.state = TaskState.COMPLETED
                task.metrics.completed_at = time.time()
                self.metrics.completed_tasks += 1
                
                logger.debug(
                    f"Task {task.id} completed in {task.metrics.execution_time:.3f}s"
                )
                return
                
            except asyncio.TimeoutError:
                retries += 1
                task.metrics.retry_count = retries
                if retries > task.max_retries:
                    task.error = TimeoutError(
                        f"Task {task.id} timed out after {task.timeout}s"
                    )
                    task.state = TaskState.FAILED
                    task.metrics.completed_at = time.time()
                    self.metrics.failed_tasks += 1
                    logger.warning(f"Task {task.id} failed: timeout")
                    return
                logger.warning(f"Task {task.id} timeout, retrying ({retries}/{task.max_retries})")
                
            except Exception as e:
                retries += 1
                task.metrics.retry_count = retries
                if retries > task.max_retries:
                    task.error = e
                    task.state = TaskState.FAILED
                    task.metrics.completed_at = time.time()
                    self.metrics.failed_tasks += 1
                    logger.warning(f"Task {task.id} failed: {e}")
                    return
                logger.warning(f"Task {task.id} error, retrying ({retries}/{task.max_retries}): {e}")
                await asyncio.sleep(0.1 * (2 ** min(retries - 1, 4)))
        
        task._event.set()
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status summary."""
        state_counts = {}
        for state in TaskState:
            count = sum(1 for t in self.tasks.values() if t.state == state)
            if count > 0:
                state_counts[state.value] = count
        
        return {
            "running": self._running,
            "max_concurrent": self.max_concurrent,
            "total_tasks": self.metrics.total_tasks,
            "state_distribution": state_counts,
            "peak_concurrency": self.metrics.peak_concurrency,
            "success_rate": f"{self.metrics.success_rate:.1%}",
        }


# Convenience function for quick task submission
async def submit_task(
    func: Callable[..., Coroutine],
    *args,
    scheduler: Optional[AsyncScheduler] = None,
    **kwargs
) -> Any:
    """Submit a task to a scheduler and wait for result."""
    if scheduler is None:
        scheduler = AsyncScheduler()
        await scheduler.start()
        try:
            task_id = await scheduler.add_task(func, args=args, kwargs=kwargs)
            return await scheduler.wait_for(task_id)
        finally:
            await scheduler.shutdown(wait=False)
    else:
        task_id = await scheduler.add_task(func, args=args, kwargs=kwargs)
        return await scheduler.wait_for(task_id)
