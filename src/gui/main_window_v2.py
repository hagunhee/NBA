"""
리팩터링된 작업 기반 스케줄러 GUI 메인 윈도우
- 책임 분리
- 의존성 주입
- 에러 처리 개선
- 코드 구조 개선
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import asyncio
import threading
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json
import os

# 내부 모듈
from core.config import Config
from core.license_manager import LicenseManager
from core.security import SecurityManager
from automation.browser_manager import BrowserManager, BrowserConfig
from tasks.task_scheduler import TaskScheduler
from tasks.base_task import BaseTask, TaskStatus, TaskType
from tasks.task_factory import TaskFactory
from utils.logger import Logger
from gui.widgets.task_list_widget import TaskListWidget
from gui.widgets.scheduler_widget import SchedulerWidget
from gui.profile_manager import ProfileManagerDialog


# === 상태 및 이벤트 관리 ===


class AppState(Enum):
    """애플리케이션 상태"""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"


@dataclass
class AppContext:
    """애플리케이션 컨텍스트"""

    config: Config
    security_manager: SecurityManager
    logger: Logger
    license_manager: Optional[object] = None  # 선택적으로 로드
    browser_manager: Optional[BrowserManager] = None
    task_factory: Optional[TaskFactory] = None
    scheduler: Optional[TaskScheduler] = None
    state: AppState = AppState.IDLE
    is_licensed: bool = False


class EventBus:
    """이벤트 버스 - 컴포넌트 간 통신"""

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self.logger = logging.getLogger(__name__)

    def subscribe(self, event: str, handler: Callable) -> None:
        """이벤트 구독"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def emit(self, event: str, data: Any = None) -> None:
        """이벤트 발생"""
        if event in self._handlers:
            for handler in self._handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    self.logger.error(f"Event handler error: {e}")


# === UI 컴포넌트 분리 ===


class ToolbarComponent:
    """툴바 컴포넌트"""

    def __init__(self, parent: tk.Widget, context: AppContext, event_bus: EventBus):
        self.parent = parent
        self.context = context
        self.event_bus = event_bus
        self._setup_ui()
        self._subscribe_events()

    def _setup_ui(self):
        """UI 구성"""
        self.toolbar = ttk.Frame(self.parent)
        self.toolbar.pack(fill=tk.X)

        # 라이선스 상태
        self._create_license_section()

        # 프로필 선택
        self._create_profile_section()

        # 실행 컨트롤
        self._create_control_section()

    def _create_license_section(self):
        """라이선스 섹션"""
        license_frame = ttk.LabelFrame(self.toolbar, text="라이선스", padding=5)
        license_frame.pack(side=tk.LEFT, padx=(0, 10))

        self.license_status = ttk.Label(
            license_frame, text="인증 필요", foreground="red"
        )
        self.license_status.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            license_frame,
            text="라이선스 관리",
            command=lambda: self.event_bus.emit("license:manage"),
        ).pack(side=tk.LEFT)

    def _create_profile_section(self):
        """프로필 섹션"""
        profile_frame = ttk.LabelFrame(self.toolbar, text="프로필", padding=5)
        profile_frame.pack(side=tk.LEFT, padx=(0, 10))

        self.profile_var = tk.StringVar()
        self.profile_combo = ttk.Combobox(
            profile_frame, textvariable=self.profile_var, state="readonly", width=20
        )
        self.profile_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.profile_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.event_bus.emit("profile:changed", self.profile_var.get()),
        )

        ttk.Button(
            profile_frame,
            text="프로필 관리",
            command=lambda: self.event_bus.emit("profile:manage"),
        ).pack(side=tk.LEFT)

    def _create_control_section(self):
        """컨트롤 섹션"""
        control_frame = ttk.Frame(self.toolbar)
        control_frame.pack(side=tk.RIGHT)

        self.start_btn = ttk.Button(
            control_frame,
            text="▶ 실행",
            command=lambda: self.event_bus.emit("scheduler:start"),
            state=tk.DISABLED,
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.pause_btn = ttk.Button(
            control_frame,
            text="⏸ 일시정지",
            command=lambda: self.event_bus.emit("scheduler:pause"),
            state=tk.DISABLED,
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(
            control_frame,
            text="⏹ 중지",
            command=lambda: self.event_bus.emit("scheduler:stop"),
            state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # 헤드리스 모드
        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            control_frame, text="헤드리스", variable=self.headless_var
        ).pack(side=tk.LEFT, padx=(20, 5))

    def _subscribe_events(self):
        """이벤트 구독"""
        self.event_bus.subscribe("app:state_changed", self._on_state_changed)
        self.event_bus.subscribe("license:status_changed", self._on_license_changed)
        self.event_bus.subscribe("profiles:loaded", self._on_profiles_loaded)

    def _on_state_changed(self, state: AppState):
        """상태 변경 처리"""
        if state == AppState.IDLE:
            self.start_btn.config(
                state=tk.NORMAL if self.context.is_licensed else tk.DISABLED
            )
            self.pause_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.DISABLED)
            self.profile_combo.config(state="readonly")
        elif state == AppState.RUNNING:
            self.start_btn.config(state=tk.DISABLED)
            self.pause_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.NORMAL)
            self.profile_combo.config(state=tk.DISABLED)
        elif state == AppState.PAUSED:
            self.pause_btn.config(text="▶ 재개")

    def _on_license_changed(self, is_licensed: bool):
        """라이선스 상태 변경"""
        if is_licensed:
            self.license_status.config(text="인증됨", foreground="green")
            if self.context.state == AppState.IDLE:
                self.start_btn.config(state=tk.NORMAL)
        else:
            self.license_status.config(text="인증 필요", foreground="red")
            self.start_btn.config(state=tk.DISABLED)

    def _on_profiles_loaded(self, profiles: List[str]):
        """프로필 목록 로드"""
        self.profile_combo["values"] = profiles

        current_profile = self.context.config.get_current_profile_name()
        if current_profile and current_profile in profiles:
            self.profile_var.set(current_profile)


class LogComponent:
    """로그 컴포넌트"""

    def __init__(self, parent: tk.Widget, context: AppContext, event_bus: EventBus):
        self.parent = parent
        self.context = context
        self.event_bus = event_bus
        self._setup_ui()
        self._subscribe_events()

    def _setup_ui(self):
        """UI 구성"""
        log_frame = ttk.LabelFrame(self.parent, text="📝 실행 로그", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # 로그 텍스트
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=8, font=("Consolas", 9), wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 로그 컨트롤
        self._create_log_controls(log_frame)

        # 태그 설정
        self._setup_log_tags()

    def _create_log_controls(self, parent):
        """로그 컨트롤 생성"""
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(control_frame, text="로그 레벨:").pack(side=tk.LEFT)

        self.log_level = ttk.Combobox(
            control_frame, values=["기본", "상세", "디버그"], state="readonly", width=10
        )
        self.log_level.set("기본")
        self.log_level.pack(side=tk.LEFT, padx=5)
        self.log_level.bind(
            "<<ComboboxSelected>>",
            lambda e: self.event_bus.emit("log:level_changed", self.log_level.get()),
        )

        ttk.Button(control_frame, text="로그 지우기", command=self.clear_log).pack(
            side=tk.RIGHT
        )

        ttk.Button(
            control_frame,
            text="로그 저장",
            command=lambda: self.event_bus.emit("log:save"),
        ).pack(side=tk.RIGHT, padx=5)

    def _setup_log_tags(self):
        """로그 태그 설정"""
        self.log_text.tag_config("INFO", foreground="black")
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("WARNING", foreground="orange")
        self.log_text.tag_config("DEBUG", foreground="gray")
        self.log_text.tag_config("SUCCESS", foreground="green")

    def _subscribe_events(self):
        """이벤트 구독"""
        self.event_bus.subscribe("log:message", self.add_log)

    def add_log(self, data: Dict[str, Any]):
        """로그 추가"""
        message = data.get("message", "")
        level = data.get("level", "INFO")
        timestamp = data.get("timestamp", datetime.now())

        # 포맷팅
        formatted_time = timestamp.strftime("%H:%M:%S")
        tag_prefix = {
            "ERROR": "[오류] ",
            "WARNING": "[경고] ",
            "DEBUG": "[디버그] ",
            "SUCCESS": "[성공] ",
        }.get(level, "")

        # 텍스트 삽입
        log_line = f"[{formatted_time}] {tag_prefix}{message}\n"
        self.log_text.insert(tk.END, log_line)

        # 태그 적용
        if level != "INFO":
            line_start = self.log_text.index("end-2c linestart")
            line_end = self.log_text.index("end-2c lineend")
            self.log_text.tag_add(level, line_start, line_end)

        # 자동 스크롤
        self.log_text.see(tk.END)

        # 로거에도 기록
        self.context.logger.log(getattr(logging, level, logging.INFO), message)

    def clear_log(self):
        """로그 지우기"""
        self.log_text.delete(1.0, tk.END)


# === 비즈니스 로직 분리 ===


class SchedulerService:
    """스케줄러 서비스"""

    def __init__(self, context: AppContext, event_bus: EventBus):
        self.context = context
        self.event_bus = event_bus
        self.scheduler_thread: Optional[threading.Thread] = None

    async def start(self) -> None:
        """스케줄러 시작"""
        try:
            # 브라우저 초기화
            await self._initialize_browser()

            # TaskFactory 생성
            self.context.task_factory = TaskFactory(
                browser_manager=self.context.browser_manager,
                config=self.context.config,
                security_manager=self.context.security_manager,
            )

            # 스케줄러 설정
            self.context.scheduler.browser_manager = self.context.browser_manager
            self._setup_scheduler_callbacks()

            # 상태 변경
            self.context.state = AppState.RUNNING
            self.event_bus.emit("app:state_changed", AppState.RUNNING)

            # 비동기 실행
            result = await self.context.scheduler.execute()

            # 완료 처리
            self._on_complete(result)

        except Exception as e:
            self.event_bus.emit(
                "log:message",
                {"message": f"스케줄러 실행 중 오류: {str(e)}", "level": "ERROR"},
            )
            self.stop()

    async def _initialize_browser(self) -> None:
        """브라우저 초기화"""
        headless = self.event_bus.emit("browser:get_headless_mode")
        browser_config = BrowserConfig(
            headless=headless, timeout=self.context.config.get("browser", "timeout", 15)
        )

        self.context.browser_manager = BrowserManager(browser_config)
        self.context.browser_manager.initialize()

    def _setup_scheduler_callbacks(self):
        """스케줄러 콜백 설정"""
        scheduler = self.context.scheduler

        scheduler.on_task_start = lambda t: self.event_bus.emit("task:started", t)
        scheduler.on_task_complete = lambda t, r: self.event_bus.emit(
            "task:completed", {"task": t, "result": r}
        )
        scheduler.on_task_failed = lambda t, r: self.event_bus.emit(
            "task:failed", {"task": t, "result": r}
        )

    def pause(self) -> None:
        """일시정지"""
        if self.context.scheduler:
            if self.context.scheduler.is_paused:
                self.context.scheduler.resume()
                self.context.state = AppState.RUNNING
            else:
                self.context.scheduler.pause()
                self.context.state = AppState.PAUSED

            self.event_bus.emit("app:state_changed", self.context.state)

    def stop(self) -> None:
        """중지"""
        if self.context.scheduler:
            self.context.scheduler.stop()

        self.context.state = AppState.STOPPING
        self.event_bus.emit("app:state_changed", AppState.STOPPING)

        # 리소스 정리
        self._cleanup()

    def _cleanup(self):
        """리소스 정리"""
        if self.context.browser_manager:
            self.context.browser_manager.close()
            self.context.browser_manager = None

        self.context.state = AppState.IDLE
        self.event_bus.emit("app:state_changed", AppState.IDLE)

    def _on_complete(self, result: Dict[str, Any]):
        """완료 처리"""
        self.event_bus.emit("scheduler:completed", result)
        self.stop()


class LicenseService:
    """라이선스 서비스"""

    def __init__(self, context: AppContext, event_bus: EventBus):
        self.context = context
        self.event_bus = event_bus

    def check_license(self) -> bool:
        """라이선스 확인"""
        saved_key = self.context.config.get("license", "key", "")
        if not saved_key:
            return False

        hardware_id = self.context.security_manager.get_hardware_id()
        success, result = self.context.license_manager.verify_license(
            saved_key, hardware_id
        )

        self.context.is_licensed = success
        self.event_bus.emit("license:status_changed", success)

        if success:
            self.event_bus.emit(
                "log:message", {"message": "라이선스 인증 완료", "level": "SUCCESS"}
            )
        else:
            self.event_bus.emit(
                "log:message",
                {
                    "message": f"라이선스 인증 실패: {result.get('message', '')}",
                    "level": "WARNING",
                },
            )

        return success


# === 메인 애플리케이션 ===


class MainApplication:
    """리팩터링된 메인 애플리케이션"""

    def __init__(self):
        print("MainApplication.__init__ 시작...")

        # 컨텍스트 초기화
        print("1. 컨텍스트 초기화...")

        self.context = AppContext(
            config=Config(),
            license_manager=LicenseManager(),
            security_manager=SecurityManager(),
            logger=Logger(),
            scheduler=TaskScheduler(),
        )
        print("2. 컨텍스트 초기화 완료")

        # 이벤트 버스
        print("3. 이벤트 버스 생성...")

        self.event_bus = EventBus()

        ## 서비스
        print("4. 서비스 생성...")
        self.scheduler_service = SchedulerService(self.context, self.event_bus)
        self.license_service = LicenseService(self.context, self.event_bus)

        # UI 컴포넌트
        print("5. tkinter 초기화...")
        self.root = tk.Tk()
        self.root.title("네이버 블로그 자동화 v2.0")
        self.root.geometry("1400x900")
        print("6. UI 설정...")
        self._setup_ui()
        print("7. 이벤트 핸들러 설정...")

        self._setup_event_handlers()
        print("8. 초기화...")

        self._initialize()
        print("MainApplication.__init__ 완료")

    def _setup_ui(self):
        """UI 설정"""
        print("_setup_ui 시작...")

        # 스타일
        print("  - 스타일 설정...")
        style = ttk.Style()
        style.theme_use("clam")

        # 메뉴바
        print("  - 메뉴바 생성...")
        self._create_menubar()

        # 메인 컨테이너
        print("  - 메인 컨테이너 생성...")
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 툴바
        print("  - 툴바 생성...")
        self.toolbar = ToolbarComponent(main_container, self.context, self.event_bus)

        # 메인 영역
        print("  - 메인 영역 생성...")
        main_paned = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # 왼쪽: 작업 목록
        print("  - 작업 목록 위젯 생성...")
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)

        self.task_list_widget = TaskListWidget(
            left_frame, on_task_double_click=self._on_task_double_click
        )
        self.task_list_widget.pack(fill=tk.BOTH, expand=True)

        # ⭐ 추가: 빠른 추가를 위한 콜백 설정
        self.task_list_widget.on_quick_add = self._on_quick_add_task

        # 오른쪽: 스케줄러
        print("  - 스케줄러 위젯 생성...")
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)

        self.scheduler_widget = SchedulerWidget(right_frame, self.context.scheduler)
        self.scheduler_widget.pack(fill=tk.BOTH, expand=True)
        self.scheduler_widget.on_task_edit = self._on_task_edit

        # ⭐ 추가: TaskFactory를 생성하여 전달
        if not self.context.task_factory:
            self.context.task_factory = TaskFactory(
                config=self.context.config,
                security_manager=self.context.security_manager,
            )
        self.scheduler_widget.task_factory = self.context.task_factory

        # TaskFactory를 scheduler_widget에 전달
        self.scheduler_widget.task_factory = self.context.task_factory

        # 로그 영역
        print("  - 로그 컴포넌트 생성...")
        self.log_component = LogComponent(main_container, self.context, self.event_bus)

        print("_setup_ui 완료")

    def _create_menubar(self):
        """메뉴바 생성"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 파일 메뉴
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="파일", menu=file_menu)
        file_menu.add_command(
            label="스케줄 불러오기",
            command=lambda: self.event_bus.emit("schedule:load"),
        )
        file_menu.add_command(
            label="스케줄 저장", command=lambda: self.event_bus.emit("schedule:save")
        )
        file_menu.add_separator()
        file_menu.add_command(label="종료", command=self._on_closing)

        # 편집 메뉴
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="편집", menu=edit_menu)
        edit_menu.add_command(
            label="전체 작업 삭제",
            command=lambda: self.event_bus.emit("tasks:clear_all"),
        )

        # 도구 메뉴
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="도구", menu=tools_menu)
        tools_menu.add_command(
            label="프로필 관리", command=lambda: self.event_bus.emit("profile:manage")
        )
        tools_menu.add_command(
            label="설정", command=lambda: self.event_bus.emit("settings:show")
        )

        # 도움말 메뉴
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="도움말", menu=help_menu)
        help_menu.add_command(
            label="사용법", command=lambda: self.event_bus.emit("help:show")
        )
        help_menu.add_separator()
        help_menu.add_command(
            label="정보", command=lambda: self.event_bus.emit("about:show")
        )

    def _setup_event_handlers(self):
        """이벤트 핸들러 설정"""
        # 스케줄러 이벤트
        self.event_bus.subscribe("scheduler:start", self._start_scheduler)
        self.event_bus.subscribe("scheduler:pause", self._pause_scheduler)
        self.event_bus.subscribe("scheduler:stop", self._stop_scheduler)
        self.event_bus.subscribe("scheduler:completed", self._on_scheduler_completed)

        # 작업 이벤트
        self.event_bus.subscribe("task:started", self._on_task_started)
        self.event_bus.subscribe("task:completed", self._on_task_completed)
        self.event_bus.subscribe("task:failed", self._on_task_failed)

        # 프로필 이벤트
        self.event_bus.subscribe("profile:manage", self._manage_profiles)
        self.event_bus.subscribe("profile:changed", self._on_profile_changed)

        # 라이선스 이벤트
        self.event_bus.subscribe("license:manage", self._manage_license)

        # 스케줄 이벤트
        self.event_bus.subscribe("schedule:load", self._load_schedule)
        self.event_bus.subscribe("schedule:save", self._save_schedule)
        self.event_bus.subscribe("tasks:clear_all", self._clear_all_tasks)

        # 로그 이벤트
        self.event_bus.subscribe("log:save", self._save_logs)

        # 기타 이벤트
        self.event_bus.subscribe("settings:show", self._show_settings)
        self.event_bus.subscribe("help:show", self._show_help)
        self.event_bus.subscribe("about:show", self._show_about)

        # 브라우저 이벤트
        self.event_bus.subscribe(
            "browser:get_headless_mode", lambda: self.toolbar.headless_var.get()
        )
        # ⭐ 추가: 드래그 앤 드롭 이벤트
        self.root.bind_all("<<TaskDragStart>>", self._on_task_drag_start)
        self.root.bind_all("<<TaskDrop>>", self._on_task_drop)

    def _initialize(self):
        """초기화"""
        # ⭐ 추가: 작업 목록 위젯에 메인 앱 참조 제공
        self.task_list_widget.main_app = self

        self.root.after(100, self._load_initial_data)

    def _load_initial_data(self):
        """초기 데이터 로드"""
        # 라이선스 확인
        self.license_service.check_license()

        # 프로필 로드
        self._load_profiles()

        # 설정 로드
        self._load_settings()

        self.event_bus.emit(
            "log:message", {"message": "프로그램이 시작되었습니다.", "level": "INFO"}
        )

    def _load_profiles(self):
        """프로필 로드"""
        profiles = self.context.config.get_profile_names()
        self.event_bus.emit("profiles:loaded", profiles)

    def _load_settings(self):
        """설정 로드"""
        # 로그 레벨
        log_level = self.context.config.get("logging", "level", "기본")
        self.log_component.log_level.set(log_level)

        # 브라우저 설정
        headless = self.context.config.get("browser", "headless", False)
        self.toolbar.headless_var.set(headless)

    # === 스케줄러 관련 ===
    def _start_scheduler(self, _):
        """스케줄러 시작"""
        if not self.context.is_licensed:
            messagebox.showerror("오류", "라이선스 인증이 필요합니다.")
            return

        if not self.context.scheduler.get_all_tasks():
            messagebox.showwarning("경고", "실행할 작업이 없습니다.")
            return

        # 비동기 실행
        self.scheduler_thread = threading.Thread(
            target=self._run_scheduler_async, daemon=True
        )
        self.scheduler_thread.start()

        self.event_bus.emit(
            "log:message", {"message": "스케줄러가 시작되었습니다.", "level": "INFO"}
        )

    def _run_scheduler_async(self):
        """비동기 스케줄러 실행"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.scheduler_service.start())
        finally:
            loop.close()

    def _pause_scheduler(self, _):
        """스케줄러 일시정지"""
        self.scheduler_service.pause()

    def _stop_scheduler(self, _):
        """스케줄러 중지"""
        self.scheduler_service.stop()
        self.event_bus.emit(
            "log:message", {"message": "스케줄러가 중지되었습니다.", "level": "INFO"}
        )

    def _on_scheduler_completed(self, result: Dict[str, Any]):
        """스케줄러 완료"""
        message = (
            f"스케줄러 완료 - "
            f"총 {result['total_tasks']}개, "
            f"성공 {result['success_count']}개, "
            f"실패 {result['failed_count']}개, "
            f"소요시간 {result['duration']:.1f}초"
        )

        self.event_bus.emit("log:message", {"message": message, "level": "SUCCESS"})

    # === 작업 관련 ===
    def _on_task_double_click(self, task_info: Dict[str, Any]):
        """작업 더블클릭 (수정된 버전)"""
        if not task_info:
            return

        try:
            print(f"더블클릭된 작업: {task_info}")

            # TaskFactory 확인
            if not self.context.task_factory:
                print("TaskFactory가 없어서 생성합니다.")
                self.context.task_factory = TaskFactory(
                    config=self.context.config,
                    security_manager=self.context.security_manager,
                )

            # 작업 생성
            task = self.context.task_factory.create_task(
                task_info["type"], task_info.get("name")
            )

            print(f"생성된 작업: {task}")
            print(f"작업 파라미터: {task.parameters}")

            # 작업 편집 다이얼로그
            from gui.dialogs.task_edit_dialog import TaskEditDialog

            dialog = TaskEditDialog(self.root, task)

            # 다이얼로그가 닫힐 때까지 대기
            dialog.dialog.wait_window()

            # 결과 확인 (수정된 부분)
            print(f"다이얼로그 결과: {dialog.result}")

            if dialog.result:
                # 스케줄러에 작업 추가
                print("스케줄러에 작업 추가 중...")
                task_id = self.scheduler_widget.add_task(task)
                print(f"작업 추가 완료: {task_id}")

                # 뷰 업데이트 강제 실행
                self.scheduler_widget.update_view()

                self.event_bus.emit(
                    "log:message",
                    {"message": f"작업 추가: {task.name}", "level": "INFO"},
                )
            else:
                print("다이얼로그가 취소되었습니다.")

        except Exception as e:
            print(f"작업 생성 중 오류: {e}")
            import traceback

            traceback.print_exc()

            # 에러 메시지 표시
            from tkinter import messagebox

            messagebox.showerror("오류", f"작업 추가 중 오류가 발생했습니다:\n{str(e)}")

    def _on_quick_add_task(self, task_info: Dict[str, Any]):
        """작업 빠른 추가 (편집 없이) - 수정된 버전"""
        if not task_info:
            return

        try:
            print(f"빠른 추가 요청: {task_info}")

            # TaskFactory 확인
            if not self.context.task_factory:
                self.context.task_factory = TaskFactory(
                    config=self.context.config,
                    security_manager=self.context.security_manager,
                )

            # 작업 생성
            task = self.context.task_factory.create_task(
                task_info["type"], task_info.get("name")
            )

            print(f"빠른 추가용 작업 생성: {task}")

            # 스케줄러에 바로 추가
            task_id = self.scheduler_widget.add_task(task)
            print(f"빠른 추가 완료: {task_id}")

            # 뷰 업데이트
            self.scheduler_widget.update_view()

            self.event_bus.emit(
                "log:message",
                {"message": f"작업 추가: {task.name}", "level": "INFO"},
            )

        except Exception as e:
            print(f"빠른 추가 중 오류: {e}")
            import traceback

            traceback.print_exc()

            from tkinter import messagebox

            messagebox.showerror("오류", f"작업 추가 중 오류가 발생했습니다:\n{str(e)}")

    def _on_task_edit(self, task: BaseTask):
        """작업 편집"""
        from gui.dialogs.task_edit_dialog import TaskEditDialog

        dialog = TaskEditDialog(self.root, task)
        self.root.wait_window(dialog.dialog)

        if dialog.result:
            self.scheduler_widget.update_view()
            self.event_bus.emit(
                "log:message", {"message": f"작업 수정: {task.name}", "level": "INFO"}
            )

    def _on_task_started(self, task: BaseTask):
        """작업 시작"""
        self.root.after(
            0,
            lambda: self.event_bus.emit(
                "log:message", {"message": f"[시작] {task.name}", "level": "INFO"}
            ),
        )
        self.scheduler_widget.update_view()

    def _on_task_completed(self, data: Dict[str, Any]):
        """작업 완료"""
        task = data["task"]
        result = data["result"]

        self.root.after(
            0,
            lambda: self.event_bus.emit(
                "log:message",
                {
                    "message": f"[완료] {task.name}: {result.message}",
                    "level": "SUCCESS",
                },
            ),
        )
        self.scheduler_widget.update_view()

    def _on_task_failed(self, data: Dict[str, Any]):
        """작업 실패"""
        task = data["task"]
        result = data["result"]

        self.root.after(
            0,
            lambda: self.event_bus.emit(
                "log:message",
                {"message": f"[실패] {task.name}: {result.message}", "level": "ERROR"},
            ),
        )
        self.scheduler_widget.update_view()

    def _on_task_drag_start(self, event):
        """작업 드래그 시작"""
        self._dragging_task_info = getattr(event, "data", None)

    def _on_task_drop(self, event):
        """작업 드롭 (수정된 버전)"""
        try:
            print(f"드롭 이벤트 발생: {event}")

            # 드래그 데이터 확인
            if hasattr(self, "_dragging_task_info") and self._dragging_task_info:
                print(f"드래그 데이터 확인: {self._dragging_task_info}")

                # 드롭 대상이 스케줄러 위젯인지 확인
                widget = self.root.winfo_containing(event.x_root, event.y_root)
                print(f"드롭 대상 위젯: {widget}")

                # 스케줄러 위젯이나 그 하위 위젯인지 확인
                if self._is_scheduler_widget_or_child(widget):
                    print("스케줄러 위젯에 드롭됨")
                    self._on_quick_add_task(self._dragging_task_info)
                else:
                    print("스케줄러 위젯이 아닌 곳에 드롭됨")

                # 드래그 데이터 초기화
                self._dragging_task_info = None
            else:
                print("드래그 데이터가 없습니다.")

        except Exception as e:
            print(f"드롭 처리 중 오류: {e}")
            import traceback

            traceback.print_exc()

    def _is_scheduler_widget_or_child(self, widget):
        """위젯이 스케줄러 위젯이거나 그 하위 위젯인지 확인"""
        try:
            if not widget:
                return False

            # 스케줄러 위젯 찾기
            current = widget
            while current:
                if hasattr(current, "master") and hasattr(current.master, "__class__"):
                    if "SchedulerWidget" in str(current.master.__class__):
                        return True
                    if hasattr(current.master, "scheduler_widget"):
                        return True

                # 상위 위젯으로 이동
                current = getattr(current, "master", None)

            return False

        except Exception as e:
            print(f"위젯 확인 중 오류: {e}")
            return False

    # === 프로필 관련 ===
    def _manage_profiles(self, _):
        """프로필 관리"""
        dialog = ProfileManagerDialog(
            self.root,
            self.context.config,
            self.context.security_manager,
            on_profile_change=self._on_profile_manager_change,
        )

    def _on_profile_manager_change(self, profile_name: str):
        """프로필 매니저에서 변경"""
        self._load_profiles()
        self.toolbar.profile_var.set(profile_name)

    def _on_profile_changed(self, profile_name: str):
        """프로필 변경"""
        if profile_name:
            self.context.config.set_current_profile(profile_name)
            self.event_bus.emit(
                "log:message",
                {"message": f"프로필 변경: {profile_name}", "level": "INFO"},
            )

    # === 라이선스 관련 ===
    def _manage_license(self, _):
        """라이선스 관리"""
        from gui.dialogs.license_dialog import LicenseDialog

        dialog = LicenseDialog(self.root, self.context, self.license_service)

    # === 스케줄 관련 ===
    def _load_schedule(self, _):
        """스케줄 불러오기"""
        self.scheduler_widget.load_schedule()

    def _save_schedule(self, _):
        """스케줄 저장"""
        self.scheduler_widget.save_schedule()

    def _clear_all_tasks(self, _):
        """모든 작업 삭제"""
        self.scheduler_widget.clear_all()

    # === 로그 관련 ===
    def _save_logs(self, _):
        """로그 저장"""
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )

        if filename:
            try:
                content = self.log_component.log_text.get(1.0, tk.END)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)

                self.event_bus.emit(
                    "log:message",
                    {"message": "로그가 저장되었습니다.", "level": "SUCCESS"},
                )
            except Exception as e:
                messagebox.showerror("저장 실패", f"로그 저장 중 오류: {str(e)}")

    # === 기타 ===
    def _show_settings(self, _):
        """설정 표시"""
        messagebox.showinfo("설정", "설정 기능은 준비 중입니다.")

    def _show_help(self, _):
        """도움말 표시"""
        from gui.dialogs.help_dialog import HelpDialog

        HelpDialog(self.root)

    def _show_about(self, _):
        """정보 표시"""
        messagebox.showinfo(
            "정보",
            "네이버 블로그 자동화 v2.0\n"
            "작업 기반 스케줄러 시스템\n\n"
            "Copyright © 2024",
        )

    def run(self):
        """애플리케이션 실행"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.mainloop()

    def _on_closing(self):
        """종료 처리"""
        if self.context.state == AppState.RUNNING:
            result = messagebox.askokcancel(
                "종료", "작업이 실행 중입니다. 종료하시겠습니까?"
            )

            if result:
                self.scheduler_service.stop()
            else:
                return

        # 설정 저장
        self._save_settings()
        self.root.destroy()

    def _save_settings(self):
        """설정 저장"""
        # 브라우저 설정
        self.context.config.set("browser", "headless", self.toolbar.headless_var.get())

        # 로그 설정
        self.context.config.set("logging", "level", self.log_component.log_level.get())

        # 저장
        self.context.config.save()


if __name__ == "__main__":
    app = MainApplication()
    app.run()
