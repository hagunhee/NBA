"""
작업 목록 위젯 - 사용 가능한 작업들을 표시 (드래그 앤 드롭 지원)
"""

import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Any, Callable, Optional
import json

from tasks.base_task import TaskType
from tasks.login_task import LoginTask
from tasks.check_posts_task import CheckNewPostsTask
from tasks.comment_task import WriteCommentTask
from tasks.utility_task import LikeTask, WaitTask, ScrollReadTask, GoToUrlTask
from tasks.accept_neighbor_requests_task import AcceptNeighborRequestsTask
from tasks.cancel_pending_neighbor_requests_task import (
    CancelPendingNeighborRequestsTask,
)
from tasks.topic_based_blog_task import TopicBasedBlogTask


class TaskListWidget(ttk.Frame):
    """작업 목록 위젯"""

    def __init__(self, parent, on_task_double_click: Optional[Callable] = None):
        super().__init__(parent)

        self.on_task_double_click = on_task_double_click
        self.on_quick_add = None
        self.main_app = None

        self.available_tasks = self._get_available_tasks()
        self.filtered_tasks = self.available_tasks.copy()

        # 드래그 상태 (개선)
        self.drag_start = None
        self.drag_data = None
        self.drag_threshold = 5  # 드래그 임계값
        self.drag_active = False

        self._setup_ui()
        self._load_tasks()

    def _setup_ui(self):
        """UI 구성 (개선된 버전)"""
        # 제목
        title_label = ttk.Label(self, text="📋 작업 목록", font=("Arial", 11, "bold"))
        title_label.pack(anchor=tk.W, pady=(0, 10))

        # 검색 프레임
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="검색:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            search_frame, textvariable=self.search_var, width=25
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.search_var.trace("w", self._on_search_changed)

        # 카테고리 필터 (수정)
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text="카테고리:").pack(side=tk.LEFT)
        self.category_var = tk.StringVar(value="전체")
        self.category_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.category_var,
            values=[
                "전체",
                "기본",
                "포스트",
                "유틸리티",
                "이웃관리",
                "복합작업",
            ],  # 새 카테고리 추가
            state="readonly",
            width=15,
        )
        self.category_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.category_combo.bind("<<ComboboxSelected>>", self._on_category_changed)

        # 작업 목록 트리뷰
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # 트리뷰
        self.tree = ttk.Treeview(
            tree_frame, columns=("type", "description"), show="tree headings", height=12
        )

        # 컬럼 설정
        self.tree.heading("#0", text="작업명")
        self.tree.heading("type", text="유형")
        self.tree.heading("description", text="설명")

        self.tree.column("#0", width=150)
        self.tree.column("type", width=100)
        self.tree.column("description", width=250)

        # 스크롤바
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=self.tree.yview)

        # 이벤트 바인딩 (개선된 드래그 앤 드롭)
        self.tree.bind("<Double-Button-1>", self._on_double_click)
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<B1-Motion>", self._on_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_release)

        # 작업 설명 표시
        info_frame = ttk.LabelFrame(self, text="작업 정보", padding=5)
        info_frame.pack(fill=tk.X, pady=(10, 0))

        self.info_text = tk.Text(info_frame, height=3, wrap=tk.WORD, font=("Arial", 9))
        self.info_text.pack(fill=tk.X)
        self.info_text.config(state=tk.DISABLED)

        # 트리 선택 이벤트
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_changed)

        # 사용 안내 (개선)
        help_label = ttk.Label(
            self,
            text="💡 더블클릭으로 편집 추가 | 드래그하여 빠른 추가",
            font=("Arial", 8),
            foreground="gray",
        )
        help_label.pack(anchor=tk.W, pady=(5, 0))

    def _get_available_tasks(self) -> List[Dict[str, Any]]:
        """사용 가능한 작업 목록"""
        return [
            # 기본 작업
            {
                "name": "네이버 로그인",
                "type": TaskType.LOGIN,
                "class": LoginTask,
                "category": "기본",
                "description": "네이버 계정으로 로그인합니다.",
                "icon": "🔐",
            },
            {
                "name": "대기",
                "type": TaskType.WAIT,
                "class": WaitTask,
                "category": "유틸리티",
                "description": "지정된 시간만큼 대기합니다.",
                "icon": "⏱️",
            },
            # 포스트 관련
            {
                "name": "이웃 새글 확인",
                "type": TaskType.CHECK_POSTS,
                "class": CheckNewPostsTask,
                "category": "포스트",
                "description": "이웃들의 새 글을 확인합니다.",
                "icon": "📋",
            },
            {
                "name": "댓글 작성",
                "type": TaskType.WRITE_COMMENT,
                "class": WriteCommentTask,
                "category": "포스트",
                "description": "포스트에 댓글을 작성합니다.",
                "icon": "💬",
            },
            {
                "name": "좋아요 클릭",
                "type": TaskType.CLICK_LIKE,
                "class": LikeTask,
                "category": "포스트",
                "description": "포스트에 좋아요를 클릭합니다.",
                "icon": "👍",
            },
            {
                "name": "스크롤 읽기",
                "type": TaskType.SCROLL_READ,
                "class": ScrollReadTask,
                "category": "포스트",
                "description": "포스트를 스크롤하며 읽습니다.",
                "icon": "📖",
            },
            # 유틸리티
            {
                "name": "URL 이동",
                "type": TaskType.GOTO_URL,
                "class": GoToUrlTask,
                "category": "유틸리티",
                "description": "지정된 URL로 이동합니다.",
                "icon": "🌐",
            },
            # 이웃 관리 (새로 추가)
            {
                "name": "받은 이웃신청 수락",
                "type": TaskType.CUSTOM,
                "class": AcceptNeighborRequestsTask,
                "category": "이웃관리",
                "description": "받은 이웃신청을 자동으로 수락합니다.",
                "icon": "✅",
            },
            {
                "name": "무응답 이웃신청 취소",
                "type": TaskType.CUSTOM,
                "class": CancelPendingNeighborRequestsTask,
                "category": "이웃관리",
                "description": "일정 기간 응답이 없는 이웃신청을 취소합니다.",
                "icon": "❌",
            },
            # 복합 작업 (새로 추가)
            {
                "name": "주제별 블로그 작업",
                "type": TaskType.CUSTOM,
                "class": TopicBasedBlogTask,
                "category": "복합작업",
                "description": "주제별로 블로그를 검색하여 서로이웃, 댓글, 공감 작업을 수행합니다.",
                "icon": "🎯",
            },
            # 마지막 URL 이동 작업 뒤에 추가
            {
                "name": "받은 이웃신청 수락",
                "type": TaskType.CUSTOM,
                "class": AcceptNeighborRequestsTask,
                "category": "이웃관리",
                "description": "받은 이웃신청을 자동으로 수락합니다.",
                "icon": "✅",
            },
            {
                "name": "무응답 이웃신청 취소",
                "type": TaskType.CUSTOM,
                "class": CancelPendingNeighborRequestsTask,
                "category": "이웃관리",
                "description": "일정 기간 응답이 없는 이웃신청을 취소합니다.",
                "icon": "❌",
            },
            {
                "name": "주제별 블로그 작업",
                "type": TaskType.CUSTOM,
                "class": TopicBasedBlogTask,
                "category": "복합작업",
                "description": "주제별로 블로그를 검색하여 서로이웃, 댓글, 공감 작업을 수행합니다.",
                "icon": "🎯",
            },
        ]

    def _load_tasks(self):
        """작업 목록 로드"""
        # 기존 항목 제거
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 작업 추가
        for task_info in self.filtered_tasks:
            icon = task_info.get("icon", "")
            name = f"{icon} {task_info['name']}" if icon else task_info["name"]

            self.tree.insert(
                "",
                "end",
                text=name,
                values=(task_info["type"].value, task_info["description"]),
                tags=(task_info["category"],),
            )

        # 태그별 색상 설정
        self.tree.tag_configure("기본", foreground="#0066cc")
        self.tree.tag_configure("포스트", foreground="#009900")
        self.tree.tag_configure("유틸리티", foreground="#cc6600")
        self.tree.tag_configure("이웃관리", foreground="#9900cc")
        self.tree.tag_configure("복합작업", foreground="#cc0066")

    def _on_search_changed(self, *args):
        """검색어 변경 이벤트"""
        self._filter_tasks()

    def _on_category_changed(self, event):
        """카테고리 변경 이벤트"""
        self._filter_tasks()

    def _filter_tasks(self):
        """작업 필터링"""
        search_text = self.search_var.get().lower()
        category = self.category_var.get()

        self.filtered_tasks = []

        for task in self.available_tasks:
            # 카테고리 필터
            if category != "전체" and task["category"] != category:
                continue

            # 검색어 필터
            if search_text:
                if not any(
                    search_text in str(value).lower()
                    for value in [task["name"], task["description"]]
                ):
                    continue

            self.filtered_tasks.append(task)

        self._load_tasks()

    def _on_selection_changed(self, event):
        """선택 변경 이벤트"""
        selection = self.tree.selection()
        if not selection:
            self._show_info("")
            return

        item = self.tree.item(selection[0])
        task_name = item["text"].lstrip("🔐⏱️📋💬👍📖🌐 ")  # 아이콘 제거

        # 작업 정보 찾기
        task_info = next(
            (t for t in self.available_tasks if t["name"] == task_name), None
        )

        if task_info:
            info_text = f"작업: {task_info['name']}\n"
            info_text += f"카테고리: {task_info['category']}\n"
            info_text += f"설명: {task_info['description']}"
            self._show_info(info_text)

    def _show_info(self, text: str):
        """정보 표시"""
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, text)
        self.info_text.config(state=tk.DISABLED)

    def _on_double_click(self, event):
        """더블클릭 이벤트"""
        if self.on_task_double_click:
            task_info = self.get_selected_task()
            if task_info:
                self.on_task_double_click(task_info)

    def get_selected_task(self) -> Optional[Dict[str, Any]]:
        """선택된 작업 정보 반환"""
        selection = self.tree.selection()
        if not selection:
            return None

        item = self.tree.item(selection[0])
        task_name = item["text"].lstrip("🔐⏱️📋💬👍📖🌐 ")  # 아이콘 제거

        return next((t for t in self.available_tasks if t["name"] == task_name), None)

    def _on_click(self, event):
        """클릭 이벤트 (드래그 시작점 기록)"""
        item = self.tree.identify("item", event.x, event.y)
        if item:
            self.tree.selection_set(item)
            self.drag_start = (event.x, event.y)
            self.drag_data = self.get_selected_task()
            self.drag_active = False
            print(f"클릭: {self.drag_data['name'] if self.drag_data else 'None'}")

    def _on_drag_motion(self, event):
        """드래그 모션 이벤트"""
        if not self.drag_start or not self.drag_data:
            return

        # 드래그 거리 계산
        dx = abs(event.x - self.drag_start[0])
        dy = abs(event.y - self.drag_start[1])
        distance = (dx * dx + dy * dy) ** 0.5

        # 임계값 확인
        if distance > self.drag_threshold and not self.drag_active:
            self._start_drag()

        # 드래그 중인 경우 위치 업데이트
        if self.drag_active:
            self._update_drag_position(event)

    def _start_drag(self):
        """드래그 시작"""
        if not self.drag_data:
            return

        self.drag_active = True
        print(f"드래그 시작: {self.drag_data['name']}")

        # 메인 앱에 드래그 데이터 설정
        if self.main_app:
            self.main_app._dragging_task_info = self.drag_data
            print(f"메인 앱에 드래그 데이터 설정: {self.drag_data['name']}")

        # 드래그 커서 설정
        self.tree.config(cursor="hand2")

        # 선택된 아이템 하이라이트
        selection = self.tree.selection()
        if selection:
            self.tree.item(selection[0], tags=("dragging",))
            self.tree.tag_configure("dragging", background="#e8f4f8")

        # 드래그 라벨 생성
        self._create_drag_label()

    def _create_drag_label(self):
        """드래그 라벨 생성"""
        if not hasattr(self, "_drag_label") and self.drag_data:
            self._drag_label = tk.Label(
                self.winfo_toplevel(),
                text=f"📦 {self.drag_data['name']}",
                relief=tk.SOLID,
                borderwidth=1,
                background="#ffffcc",
                foreground="#333333",
                padx=10,
                pady=5,
                font=("Arial", 9),
            )

    def _update_drag_position(self, event):
        """드래그 위치 업데이트"""
        if hasattr(self, "_drag_label") and self._drag_label:
            # 마우스 근처에 라벨 표시
            x = event.x_root + 10
            y = event.y_root + 10
            self._drag_label.place(x=x, y=y)
            self._drag_label.lift()

    def _on_release(self, event):
        """마우스 릴리즈 이벤트"""
        try:
            if self.drag_active and self.drag_data:
                print(f"드래그 릴리즈: {self.drag_data['name']}")

                # 드롭 대상 확인
                x, y = event.x_root, event.y_root
                target_widget = self.winfo_containing(x, y)

                print(f"드롭 대상: {target_widget}")

                if target_widget:
                    # 스케줄러 위젯 확인
                    if self._is_scheduler_target(target_widget):
                        print("스케줄러 위젯에 드롭")
                        self._perform_drop()
                    else:
                        print("스케줄러가 아닌 위젯에 드롭")

        except Exception as e:
            print(f"릴리즈 처리 중 오류: {e}")
        finally:
            # 드래그 상태 정리
            self._cleanup_drag()

    def _is_scheduler_target(self, widget):
        """드롭 대상이 스케줄러 위젯인지 확인"""
        try:
            if not widget:
                return False

            # 위젯 클래스 이름 확인
            widget_class = widget.__class__.__name__
            if "Listbox" in widget_class:
                # 리스트박스의 마스터 확인
                master = widget.master
                while master:
                    master_class = master.__class__.__name__
                    if "SchedulerWidget" in master_class:
                        return True
                    master = getattr(master, "master", None)

            return False

        except Exception as e:
            print(f"스케줄러 대상 확인 중 오류: {e}")
            return False

    def _perform_drop(self):
        """드롭 수행"""
        try:
            if self.drag_data and self.on_quick_add:
                print(f"빠른 추가 콜백 호출: {self.drag_data['name']}")
                self.on_quick_add(self.drag_data)
            elif self.drag_data and self.main_app:
                print(f"메인 앱 빠른 추가 호출: {self.drag_data['name']}")
                self.main_app._on_quick_add_task(self.drag_data)
            else:
                print("드롭 콜백을 찾을 수 없음")

        except Exception as e:
            print(f"드롭 수행 중 오류: {e}")

    def _cleanup_drag(self):
        """드래그 정리"""
        try:
            # 드래그 라벨 제거
            if hasattr(self, "_drag_label") and self._drag_label:
                self._drag_label.place_forget()
                self._drag_label.destroy()
                delattr(self, "_drag_label")

            # 드래그 하이라이트 제거
            for item in self.tree.get_children():
                tags = list(self.tree.item(item, "tags"))
                if "dragging" in tags:
                    tags.remove("dragging")
                    self.tree.item(item, tags=tags)

            # 커서 복원
            self.tree.config(cursor="")

            # 상태 초기화
            self.drag_start = None
            self.drag_data = None
            self.drag_active = False

            # 메인 앱 드래그 데이터 정리
            if self.main_app and hasattr(self.main_app, "_dragging_task_info"):
                self.main_app._dragging_task_info = None

            print("드래그 정리 완료")

        except Exception as e:
            print(f"드래그 정리 중 오류: {e}")

    def get_drag_data(self) -> Optional[Dict[str, Any]]:
        """현재 드래그 중인 데이터 반환"""
        return self.drag_data if self.drag_active else None

    # 기존 메서드들은 그대로 유지...
    def _get_available_tasks(self) -> List[Dict[str, Any]]:
        """사용 가능한 작업 목록"""
        return [
            # 기본 작업
            {
                "name": "네이버 로그인",
                "type": TaskType.LOGIN,
                "class": LoginTask,
                "category": "기본",
                "description": "네이버 계정으로 로그인합니다.",
                "icon": "🔐",
            },
            {
                "name": "대기",
                "type": TaskType.WAIT,
                "class": WaitTask,
                "category": "유틸리티",
                "description": "지정된 시간만큼 대기합니다.",
                "icon": "⏱️",
            },
            # 포스트 관련
            {
                "name": "이웃 새글 확인",
                "type": TaskType.CHECK_POSTS,
                "class": CheckNewPostsTask,
                "category": "포스트",
                "description": "이웃들의 새 글을 확인합니다.",
                "icon": "📋",
            },
            {
                "name": "댓글 작성",
                "type": TaskType.WRITE_COMMENT,
                "class": WriteCommentTask,
                "category": "포스트",
                "description": "포스트에 댓글을 작성합니다.",
                "icon": "💬",
            },
            {
                "name": "좋아요 클릭",
                "type": TaskType.CLICK_LIKE,
                "class": LikeTask,
                "category": "포스트",
                "description": "포스트에 좋아요를 클릭합니다.",
                "icon": "👍",
            },
            {
                "name": "스크롤 읽기",
                "type": TaskType.SCROLL_READ,
                "class": ScrollReadTask,
                "category": "포스트",
                "description": "포스트를 스크롤하며 읽습니다.",
                "icon": "📖",
            },
            # 유틸리티
            {
                "name": "URL 이동",
                "type": TaskType.GOTO_URL,
                "class": GoToUrlTask,
                "category": "유틸리티",
                "description": "지정된 URL로 이동합니다.",
                "icon": "🌐",
            },
            {
                "name": "받은 이웃신청 수락",
                "type": TaskType.CUSTOM,
                "class": AcceptNeighborRequestsTask,
                "category": "이웃관리",
                "description": "받은 이웃신청을 자동으로 수락합니다.",
                "icon": "✅",
            },
            {
                "name": "무응답 이웃신청 취소",
                "type": TaskType.CUSTOM,
                "class": CancelPendingNeighborRequestsTask,
                "category": "이웃관리",
                "description": "일정 기간 응답이 없는 이웃신청을 취소합니다.",
                "icon": "❌",
            },
            {
                "name": "주제별 블로그 작업",
                "type": TaskType.CUSTOM,
                "class": TopicBasedBlogTask,
                "category": "복합작업",
                "description": "주제별로 블로그를 검색하여 서로이웃, 댓글, 공감 작업을 수행합니다.",
                "icon": "🎯",
            },
        ]

    def _create_tooltip(self, widget, text):
        """툴팁 생성"""

        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

            label = tk.Label(
                tooltip,
                text=text,
                background="#ffffe0",
                relief=tk.SOLID,
                borderwidth=1,
                font=("Arial", 9),
            )
            label.pack()

            widget.tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, "tooltip"):
                widget.tooltip.destroy()
                del widget.tooltip

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def refresh(self):
        """목록 새로고침"""
        self._filter_tasks()
