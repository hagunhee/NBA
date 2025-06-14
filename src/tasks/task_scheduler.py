"""
작업 스케줄러 - 작업들을 순차적/병렬적으로 실행
"""

import asyncio
import threading
from typing import List, Dict, Any, Optional, Callable, Set
from datetime import datetime
import logging
from collections import deque
from enum import Enum

from tasks.base_task import BaseTask, TaskStatus, TaskResult
from automation.browser_manager import BrowserManager


class SchedulerState(Enum):
    """스케줄러 상태"""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


class TaskScheduler:
    """개선된 작업 스케줄러"""

    def __init__(self, browser_manager: Optional[BrowserManager] = None):
        self.browser_manager = browser_manager
        self.task_queue: deque[BaseTask] = deque()
        self.completed_tasks: Dict[str, BaseTask] = {}
        self.running_tasks: Dict[str, BaseTask] = {}
        self.failed_tasks: Dict[str, BaseTask] = {}
        self.context: Dict[str, Any] = {}  # 작업 간 공유 컨텍스트

        self.state = SchedulerState.IDLE
        self._async_lock = asyncio.Lock()  # 비동기용 Lock
        self._sync_lock = threading.Lock()  # 동기용 Lock
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 초기에는 일시정지 해제 상태

        self.logger = logging.getLogger(__name__)
        self.task_factory = None  # 팩토리 추가

        # 통계
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None

        # 콜백 함수들
        self.on_task_start: Optional[Callable[[BaseTask], None]] = None
        self.on_task_complete: Optional[Callable[[BaseTask, TaskResult], None]] = None
        self.on_task_failed: Optional[Callable[[BaseTask, TaskResult], None]] = None
        self.on_scheduler_complete: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_scheduler_error: Optional[Callable[[Exception], None]] = None

    # === 작업 관리 ===

    def add_task(self, task: BaseTask) -> str:
        """작업 추가"""
        with self._sync_lock:
            self.task_queue.append(task)
            self.logger.info(f"작업 추가됨: {task.name} (ID: {task.id})")
            return task.id

    def add_tasks(self, tasks: List[BaseTask]) -> List[str]:
        """여러 작업 추가"""
        task_ids = []
        for task in tasks:
            task_ids.append(self.add_task(task))
        return task_ids

    def remove_task(self, task_id: str) -> bool:
        """작업 제거"""
        with self._sync_lock:
            # 대기 중인 작업에서만 제거 가능
            for i, task in enumerate(self.task_queue):
                if task.id == task_id:
                    self.task_queue.remove(task)
                    self.logger.info(f"작업 제거됨: {task.name} (ID: {task_id})")
                    return True
        return False

    def clear_tasks(self) -> None:
        """모든 작업 제거"""
        with self._sync_lock:
            self.task_queue.clear()
            self.completed_tasks.clear()
            self.running_tasks.clear()
            self.failed_tasks.clear()
            self.context.clear()
            self.logger.info("모든 작업이 제거되었습니다.")

    def get_task(self, task_id: str) -> Optional[BaseTask]:
        """작업 가져오기"""
        with self._sync_lock:
            # 큐에서 찾기
            for task in self.task_queue:
                if task.id == task_id:
                    return task

            # 실행 중인 작업에서 찾기
            if task_id in self.running_tasks:
                return self.running_tasks[task_id]

            # 완료된 작업에서 찾기
            if task_id in self.completed_tasks:
                return self.completed_tasks[task_id]

            # 실패한 작업에서 찾기
            if task_id in self.failed_tasks:
                return self.failed_tasks[task_id]

        return None

    def get_all_tasks(self) -> List[BaseTask]:
        """모든 작업 가져오기"""
        with self._sync_lock:
            all_tasks = list(self.task_queue)
            all_tasks.extend(self.running_tasks.values())
            all_tasks.extend(self.completed_tasks.values())
            all_tasks.extend(self.failed_tasks.values())
            return all_tasks

    def get_pending_tasks(self) -> List[BaseTask]:
        """대기 중인 작업 목록"""
        with self._sync_lock:
            return [
                task for task in self.task_queue if task.status == TaskStatus.PENDING
            ]

    def get_executable_tasks(self) -> List[BaseTask]:
        """실행 가능한 작업 목록"""
        with self._sync_lock:
            completed_ids = set(self.completed_tasks.keys())
            return [
                task
                for task in self.task_queue
                if task.status == TaskStatus.PENDING
                and self._can_execute(task, completed_ids)
            ]

    def _can_execute(self, task: BaseTask, completed_ids: Set[str]) -> bool:
        """작업 실행 가능 여부 확인"""
        # 의존성 확인
        if hasattr(task, "dependencies"):
            for dep_id in task.dependencies:
                if dep_id not in completed_ids:
                    return False
        return True

    # === 순서 관리 (동기 함수로 수정) ===

    def move_task_up(self, task_id: str) -> bool:
        """작업 순서 위로 이동"""
        with self._sync_lock:
            queue_list = list(self.task_queue)
            for i, task in enumerate(queue_list):
                if task.id == task_id and i > 0:
                    queue_list[i], queue_list[i - 1] = queue_list[i - 1], queue_list[i]
                    self.task_queue = deque(queue_list)
                    return True
        return False

    def move_task_down(self, task_id: str) -> bool:
        """작업 순서 아래로 이동"""
        with self._sync_lock:
            queue_list = list(self.task_queue)
            for i, task in enumerate(queue_list):
                if task.id == task_id and i < len(queue_list) - 1:
                    queue_list[i], queue_list[i + 1] = queue_list[i + 1], queue_list[i]
                    self.task_queue = deque(queue_list)
                    return True
        return False

    # === 실행 제어 ===

    async def execute(self) -> Dict[str, Any]:
        """스케줄러 실행 (개선된 버전)"""
        if self.state != SchedulerState.IDLE:
            raise RuntimeError(f"스케줄러가 이미 {self.state.value} 상태입니다.")

        self.state = SchedulerState.RUNNING
        self._start_time = datetime.now()

        with self._sync_lock:
            total_tasks = len(self.task_queue)

        self.logger.info(f"스케줄러 시작: 총 {total_tasks}개 작업")

        try:
            while self.task_queue and self.state == SchedulerState.RUNNING:
                # 일시정지 확인
                await self._pause_event.wait()

                # 중지 요청 확인
                if self.state == SchedulerState.STOPPING:
                    break

                # 실행 가능한 작업 찾기
                executable_tasks = self.get_executable_tasks()

                if not executable_tasks:
                    # 실행 가능한 작업이 없으면 잠시 대기
                    await asyncio.sleep(0.5)

                    # 데드락 확인
                    if self._check_deadlock():
                        self.logger.error(
                            "데드락 감지: 의존성 순환이 있을 수 있습니다."
                        )
                        break
                    continue

                # 첫 번째 실행 가능한 작업 가져오기
                task = executable_tasks[0]

                with self._sync_lock:
                    if task in self.task_queue:
                        self.task_queue.remove(task)
                    else:
                        continue  # 이미 제거된 작업

                # 작업 실행
                result = await self._execute_task(task)

                # 작업 간 대기
                await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            self.logger.warning("스케줄러가 취소되었습니다.")
            raise

        except Exception as e:
            self.logger.error(f"스케줄러 실행 중 오류: {e}")
            if self.on_scheduler_error:
                self.on_scheduler_error(e)
            raise

        finally:
            self.state = SchedulerState.STOPPED
            self._end_time = datetime.now()

            # 완료 요약
            summary = self._create_summary()

            self.logger.info(
                f"스케줄러 완료: 성공 {summary['success_count']}, "
                f"실패 {summary['failed_count']}, "
                f"소요시간 {summary['duration']:.1f}초"
            )

            if self.on_scheduler_complete:
                self.on_scheduler_complete(summary)

            return summary

    async def _execute_task(self, task: BaseTask) -> TaskResult:
        """개별 작업 실행 (개선된 버전)"""
        self.logger.info(f"작업 시작: {task.name}")

        # 작업 시작 콜백
        if self.on_task_start:
            self.on_task_start(task)

        # 실행 중인 작업에 추가
        async with self._async_lock:
            self.running_tasks[task.id] = task

        try:
            # 작업 실행
            result = await task.execute(self.browser_manager, self.context)

            # 실행 중인 작업에서 제거
            async with self._async_lock:
                if task.id in self.running_tasks:
                    del self.running_tasks[task.id]

                # 결과에 따라 적절한 딕셔너리에 추가
                if result.success:
                    self.completed_tasks[task.id] = task
                else:
                    self.failed_tasks[task.id] = task

            # 결과를 컨텍스트에 저장
            self.context[f"task_{task.id}_result"] = result.data

            # 작업 완료/실패 콜백
            if result.success and self.on_task_complete:
                self.on_task_complete(task, result)
            elif not result.success and self.on_task_failed:
                self.on_task_failed(task, result)

            self.logger.info(
                f"작업 완료: {task.name} - "
                f"{'성공' if result.success else '실패'} ({result.message})"
            )

            return result

        except asyncio.CancelledError:
            # 작업 취소
            task.status = TaskStatus.CANCELLED
            async with self._async_lock:
                if task.id in self.running_tasks:
                    del self.running_tasks[task.id]
                self.failed_tasks[task.id] = task
            raise

        except Exception as e:
            # 예상치 못한 오류
            error_msg = f"작업 실행 중 예상치 못한 오류: {str(e)}"
            self.logger.error(error_msg)

            result = TaskResult(success=False, message=error_msg)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.result = result

            async with self._async_lock:
                if task.id in self.running_tasks:
                    del self.running_tasks[task.id]
                self.failed_tasks[task.id] = task

            if self.on_task_failed:
                self.on_task_failed(task, result)

            return result

    def pause(self) -> None:
        """스케줄러 일시정지"""
        if self.state == SchedulerState.RUNNING:
            self.state = SchedulerState.PAUSED
            self._pause_event.clear()
            self.logger.info("스케줄러 일시정지")

    def resume(self) -> None:
        """스케줄러 재개"""
        if self.state == SchedulerState.PAUSED:
            self.state = SchedulerState.RUNNING
            self._pause_event.set()
            self.logger.info("스케줄러 재개")

    def stop(self) -> None:
        """스케줄러 중지"""
        if self.state in [SchedulerState.RUNNING, SchedulerState.PAUSED]:
            self.state = SchedulerState.STOPPING
            self._pause_event.set()  # 일시정지 해제하여 종료 가능하게
            self.logger.info("스케줄러 중지 요청")

    @property
    def is_running(self) -> bool:
        """실행 중 여부"""
        return self.state == SchedulerState.RUNNING

    @property
    def is_paused(self) -> bool:
        """일시정지 여부"""
        return self.state == SchedulerState.PAUSED

    # === 진행 상황 및 통계 ===

    def get_progress(self) -> Dict[str, Any]:
        """진행 상황 가져오기"""
        with self._sync_lock:
            total = len(self.get_all_tasks())
            completed = len(self.completed_tasks)
            failed = len(self.failed_tasks)
            running = len(self.running_tasks)
            pending = len(self.get_pending_tasks())

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": pending,
            "progress_percent": (completed + failed) / total * 100 if total > 0 else 0,
            "success_rate": (
                completed / (completed + failed) * 100
                if (completed + failed) > 0
                else 0
            ),
            "state": self.state.value,
            "elapsed_time": self._get_elapsed_time(),
        }

    def _create_summary(self) -> Dict[str, Any]:
        """실행 요약 생성"""
        with self._sync_lock:
            success_count = len(self.completed_tasks)
            failed_count = len(self.failed_tasks)
            total_tasks = success_count + failed_count

        summary = {
            "total_tasks": total_tasks,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": success_count / total_tasks * 100 if total_tasks > 0 else 0,
            "duration": self._get_elapsed_time(),
            "completed_tasks": list(self.completed_tasks.values()),
            "failed_tasks": list(self.failed_tasks.values()),
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "end_time": self._end_time.isoformat() if self._end_time else None,
        }

        # 실패한 작업들의 원인 분석
        if failed_count > 0:
            failure_reasons = {}
            for task in self.failed_tasks.values():
                if task.result:
                    reason = task.result.message
                    failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            summary["failure_reasons"] = failure_reasons

        return summary

    def _get_elapsed_time(self) -> float:
        """경과 시간 계산"""
        if not self._start_time:
            return 0.0

        end_time = self._end_time or datetime.now()
        return (end_time - self._start_time).total_seconds()

    def _check_deadlock(self) -> bool:
        """데드락 검사"""
        with self._sync_lock:
            # 대기 중인 작업이 있고, 실행 중인 작업이 없고,
            # 모든 대기 작업이 의존성 때문에 실행 불가능한 경우
            if (
                self.task_queue
                and not self.running_tasks
                and not self.get_executable_tasks()
            ):
                return True
        return False
