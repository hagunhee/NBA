"""
작업 팩토리 - 의존성 주입 패턴
"""

import logging
import os
from typing import Dict, Any, Optional, Type, List
from dataclasses import dataclass, field

from automation.browser_manager import BrowserManager, BrowserConfig
from core.config import Config
from core.security import SecurityManager

# 작업 임포트
from tasks.base_task import BaseTask, TaskType
from tasks.login_task import LoginTask
from tasks.check_posts_task import CheckNewPostsTask
from tasks.comment_task import WriteCommentTask
from tasks.utility_task import LikeTask, WaitTask, ScrollReadTask, GoToUrlTask, LoopTask
from tasks.accept_neighbor_requests_task import AcceptNeighborRequestsTask
from tasks.cancel_pending_neighbor_requests_task import (
    CancelPendingNeighborRequestsTask,
)
from tasks.topic_based_blog_task import TopicBasedBlogTask


@dataclass
class TaskDependencies:
    """작업 의존성 컨테이너"""

    browser_manager: Optional[BrowserManager] = None
    config: Optional[Config] = None
    security_manager: Optional[SecurityManager] = None
    logger: Optional[logging.Logger] = None
    context: Dict[str, Any] = field(default_factory=dict)


class TaskFactory:
    """
    작업 팩토리 - 의존성 주입을 통한 작업 생성

    이 클래스는 작업 생성을 중앙화하고 필요한 의존성을 주입합니다.
    """

    def __init__(
        self,
        browser_manager: Optional[BrowserManager] = None,
        config: Optional[Config] = None,
        security_manager: Optional[SecurityManager] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.browser_manager = browser_manager
        self.config = config or Config()
        self.security_manager = security_manager or SecurityManager()
        self.logger = logger or logging.getLogger(__name__)

        # 작업 타입별 클래스 매핑
        self._task_classes: Dict[TaskType, Type[BaseTask]] = {
            TaskType.LOGIN: LoginTask,
            TaskType.CHECK_POSTS: CheckNewPostsTask,
            TaskType.WRITE_COMMENT: WriteCommentTask,
            TaskType.CLICK_LIKE: LikeTask,
            TaskType.WAIT: WaitTask,
            TaskType.SCROLL_READ: ScrollReadTask,
            TaskType.GOTO_URL: GoToUrlTask,
        }
        # __init__ 메서드의 _custom_tasks에 추가
        self._custom_tasks: Dict[str, Type[BaseTask]] = {
            "LoopTask": LoopTask,
            "AcceptNeighborRequestsTask": AcceptNeighborRequestsTask,
            "CancelPendingNeighborRequestsTask": CancelPendingNeighborRequestsTask,
            "TopicBasedBlogTask": TopicBasedBlogTask,
        }

        # 커스텀 작업 레지스트리
        self._custom_tasks: Dict[str, Type[BaseTask]] = {"LoopTask": LoopTask}

        # 생성된 작업 캐시 (선택적)
        self._task_cache: Dict[str, BaseTask] = {}

    def create_task(
        self, task_type: TaskType, name: Optional[str] = None, **parameters
    ) -> BaseTask:
        """
        작업 생성 및 의존성 주입

        Args:
            task_type: 작업 타입
            name: 작업 이름 (선택적)
            **parameters: 작업 파라미터

        Returns:
            생성된 작업 인스턴스
        """
        # 작업 클래스 찾기
        task_class = self._task_classes.get(task_type)
        if not task_class:
            raise ValueError(f"지원하지 않는 작업 타입: {task_type}")

        # 작업 인스턴스 생성
        task = task_class(name) if name else task_class()

        # 의존성 주입
        self._inject_dependencies(task)

        # 파라미터 설정 (기존 파라미터를 덮어쓰지 않고 추가)
        if parameters:
            task.set_parameters(**parameters)

        # 작업별 추가 설정 (기본값 보장)
        self._configure_task(task)

        self.logger.info(f"작업 생성됨: {task.name} (타입: {task_type.value})")

        return task

    def create_custom_task(
        self, task_class_name: str, name: Optional[str] = None, **parameters
    ) -> BaseTask:
        """
        커스텀 작업 생성

        Args:
            task_class_name: 커스텀 작업 클래스 이름
            name: 작업 이름
            **parameters: 작업 파라미터

        Returns:
            생성된 작업 인스턴스
        """
        task_class = self._custom_tasks.get(task_class_name)
        if not task_class:
            raise ValueError(f"등록되지 않은 커스텀 작업: {task_class_name}")

        task = task_class(name) if name else task_class()

        self._inject_dependencies(task)

        if parameters:
            task.set_parameters(**parameters)

        self._configure_task(task)

        self.logger.info(f"커스텀 작업 생성됨: {task.name}")

        return task

    def register_custom_task(self, task_class_name: str, task_class: Type[BaseTask]):
        """커스텀 작업 클래스 등록"""
        if not issubclass(task_class, BaseTask):
            raise ValueError(f"{task_class}는 BaseTask의 서브클래스여야 합니다.")

        self._custom_tasks[task_class_name] = task_class
        self.logger.info(f"커스텀 작업 등록됨: {task_class_name}")

    def _inject_dependencies(self, task: BaseTask) -> None:
        """작업에 의존성 주입"""
        # 기본 의존성
        if hasattr(task, "browser_manager"):
            task.browser_manager = self.browser_manager

        if hasattr(task, "config"):
            task.config = self.config

        if hasattr(task, "security_manager"):
            task.security_manager = self.security_manager

        if hasattr(task, "logger"):
            task.logger = self.logger.getChild(task.__class__.__name__)

    def _configure_task(self, task: BaseTask) -> None:
        """작업별 추가 설정 (기본값 보장)"""

        # 1. 먼저 모든 작업에 대해 기본 파라미터 확인 (새로 추가)
        if hasattr(task, "get_required_parameters"):
            required_params = task.get_required_parameters()

            for param_name, param_info in required_params.items():
                # 파라미터가 설정되지 않았거나 None인 경우 기본값 설정
                current_value = task.get_parameter(param_name)
                if current_value is None or (
                    isinstance(current_value, str) and not current_value
                ):
                    default_value = param_info.get("default")
                    if default_value is not None:
                        task.set_parameters(**{param_name: default_value})

        # 2. 기존의 작업별 특수 설정들은 그대로 유지
        # 로그인 작업
        if isinstance(task, LoginTask):
            self._configure_login_task(task)

        # 댓글 작업
        elif isinstance(task, WriteCommentTask):
            self._configure_comment_task(task)

        # 이웃 새글 확인 작업
        elif isinstance(task, CheckNewPostsTask):
            self._configure_check_posts_task(task)

        # 대기 작업
        elif hasattr(task, "_get_task_type") and task._get_task_type() == TaskType.WAIT:
            # WaitTask의 기본값 확인
            if not task.get_parameter("duration"):
                task.set_parameters(duration=10)
            if task.get_parameter("random_variance") is None:
                task.set_parameters(random_variance=0.2)

        # URL 이동 작업
        elif (
            hasattr(task, "_get_task_type")
            and task._get_task_type() == TaskType.GOTO_URL
        ):
            # GoToUrlTask의 기본값 확인
            if not task.get_parameter("url"):
                task.set_parameters(url="")  # 빈 문자열이라도 설정
            if task.get_parameter("wait_time") is None:
                task.set_parameters(wait_time=3)
            if task.get_parameter("check_login") is None:
                task.set_parameters(check_login=False)

    def _configure_login_task(self, task: LoginTask) -> None:
        """로그인 작업 설정"""
        # 현재 프로필에서 계정 정보 가져오기
        current_profile = self.config.get_current_profile_name()
        if current_profile:
            profile_data = self.config.get_profile(current_profile)
            if profile_data:
                # 비밀번호 복호화
                encrypted_pw = profile_data.get("naver_pw", "")
                if encrypted_pw and self.security_manager:
                    try:
                        decrypted_pw = self.security_manager.decrypt_password(
                            encrypted_pw
                        )
                    except Exception as e:
                        self.logger.error(f"비밀번호 복호화 실패: {e}")
                        decrypted_pw = ""
                else:
                    decrypted_pw = ""

                # 파라미터 설정 (기존 파라미터를 덮어쓰지 않음)
                if not task.get_parameter("username"):
                    task.set_parameters(username=profile_data.get("naver_id", ""))
                if not task.get_parameter("password"):
                    task.set_parameters(password=decrypted_pw)

    def _configure_comment_task(self, task: WriteCommentTask) -> None:
        """댓글 작업 설정"""
        # 설정에서 기본 댓글 스타일 가져오기
        comment_style = self.config.get("automation", "comment_style", "친근함")
        if not task.get_parameter("comment_style"):
            task.set_parameters(comment_style=comment_style)

        # AI API 키 설정 (있는 경우)
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            if task.get_parameter("use_ai") is None:
                task.set_parameters(use_ai=True)
        else:
            self.logger.warning("AI API 키가 없습니다. 템플릿 기반 댓글을 사용합니다.")
            if task.get_parameter("use_ai") is None:
                task.set_parameters(use_ai=False)

    def _configure_check_posts_task(self, task: CheckNewPostsTask) -> None:
        """이웃 새글 확인 작업 설정"""
        # 설정에서 필터 정보 가져오기
        daily_limit = self.config.get("automation", "daily_limit", 20)
        if not task.get_parameter("max_posts"):
            task.set_parameters(max_posts=daily_limit)

    # === 편의 메서드들 ===

    def create_login_task(
        self, username: Optional[str] = None, password: Optional[str] = None, **kwargs
    ) -> LoginTask:
        """로그인 작업 생성 (편의 메서드)"""
        params = kwargs.copy()
        if username:
            params["username"] = username
        if password:
            params["password"] = password

        return self.create_task(TaskType.LOGIN, **params)

    def create_comment_task(
        self,
        comment_text: Optional[str] = None,
        use_ai: Optional[bool] = None,
        **kwargs,
    ) -> WriteCommentTask:
        """댓글 작업 생성 (편의 메서드)"""
        params = kwargs.copy()
        if comment_text:
            params["custom_comment"] = comment_text
        if use_ai is not None:
            params["use_ai"] = use_ai

        return self.create_task(TaskType.WRITE_COMMENT, **params)

    def create_wait_task(self, duration: float, **kwargs) -> WaitTask:
        """대기 작업 생성 (편의 메서드)"""
        params = kwargs.copy()
        params["duration"] = duration

        return self.create_task(TaskType.WAIT, **params)

    def create_like_task(self, **kwargs) -> LikeTask:
        """좋아요 작업 생성 (편의 메서드)"""
        return self.create_task(TaskType.CLICK_LIKE, **kwargs)

    def create_scroll_task(
        self, duration: int = 60, scroll_speed: str = "MEDIUM", **kwargs
    ) -> ScrollReadTask:
        """스크롤 읽기 작업 생성 (편의 메서드)"""
        params = kwargs.copy()
        params["duration"] = duration
        params["scroll_speed"] = scroll_speed

        return self.create_task(TaskType.SCROLL_READ, **params)

    def create_goto_url_task(self, url: str, **kwargs) -> GoToUrlTask:
        """URL 이동 작업 생성 (편의 메서드)"""
        params = kwargs.copy()
        params["url"] = url

        return self.create_task(TaskType.GOTO_URL, **params)

    def create_loop_task(
        self, sub_tasks: List[BaseTask], repeat_count: int = 1, **kwargs
    ) -> LoopTask:
        """반복 작업 생성 (편의 메서드)"""
        loop_task = self.create_custom_task("LoopTask", **kwargs)

        # 하위 작업 추가
        if isinstance(loop_task, LoopTask):
            for task in sub_tasks:
                loop_task.add_sub_task(task)

            # 반복 횟수 설정
            loop_task.set_parameters(repeat_count=repeat_count)

        return loop_task

    def create_task_chain(self, task_configs: List[Dict[str, Any]]) -> List[BaseTask]:
        """
        작업 체인 생성

        Args:
            task_configs: 작업 설정 리스트

        Returns:
            생성된 작업 리스트
        """
        tasks = []

        for config in task_configs:
            task_type = config.get("type")
            if not task_type:
                self.logger.warning(f"작업 타입이 없습니다: {config}")
                continue

            # TaskType enum으로 변환
            if isinstance(task_type, str):
                try:
                    task_type = TaskType(task_type)
                except ValueError:
                    # 커스텀 작업일 수 있음
                    if task_type in self._custom_tasks:
                        task = self.create_custom_task(
                            task_type,
                            config.get("name"),
                            **config.get("parameters", {}),
                        )
                        tasks.append(task)
                        continue
                    else:
                        self.logger.error(f"알 수 없는 작업 타입: {task_type}")
                        continue

            # 작업 생성
            name = config.get("name")
            params = config.get("parameters", {})

            task = self.create_task(task_type, name, **params)

            # 의존성 설정
            dependencies = config.get("dependencies", [])
            if dependencies and hasattr(task, "dependencies"):
                task.dependencies = dependencies

            tasks.append(task)

        return tasks

    def create_from_json(self, json_data: Dict[str, Any]) -> List[BaseTask]:
        """JSON 데이터로부터 작업 생성"""
        task_configs = json_data.get("tasks", [])
        return self.create_task_chain(task_configs)

    def get_available_task_types(self) -> Dict[str, Type[BaseTask]]:
        """사용 가능한 모든 작업 타입 반환"""
        all_tasks = {}

        # 기본 작업들
        for task_type, task_class in self._task_classes.items():
            all_tasks[task_type.value] = task_class

        # 커스텀 작업들
        for task_name, task_class in self._custom_tasks.items():
            all_tasks[task_name] = task_class

        return all_tasks

    def create_typical_workflow(self) -> List[BaseTask]:
        """일반적인 워크플로우 생성 (예시)"""
        tasks = []

        # 1. 로그인
        tasks.append(self.create_login_task(name="네이버 로그인"))

        # 2. 대기
        tasks.append(self.create_wait_task(3, name="로그인 후 대기"))

        # 3. 이웃 새글 확인
        tasks.append(
            self.create_task(TaskType.CHECK_POSTS, name="이웃 새글 확인", max_posts=10)
        )

        # 4. 포스트 처리 반복
        post_tasks = [
            self.create_scroll_task(duration=30, name="포스트 읽기"),
            self.create_like_task(name="좋아요 클릭"),
            self.create_comment_task(use_ai=True, name="댓글 작성"),
            self.create_wait_task(5, name="다음 포스트 전 대기"),
        ]

        loop_task = self.create_loop_task(
            post_tasks, repeat_count=5, name="포스트 처리 반복"
        )
        tasks.append(loop_task)

        return tasks
