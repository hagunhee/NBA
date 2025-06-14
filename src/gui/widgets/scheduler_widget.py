"""
스케줄러 위젯 - 작업 스케줄을 관리하고 표시
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime

from tasks.base_task import BaseTask, TaskStatus
from tasks.task_scheduler import TaskScheduler


class SchedulerWidget(ttk.Frame):
    def __init__(self, parent, scheduler: TaskScheduler):
        print("SchedulerWidget.__init__ 시작...")

        super().__init__(parent)
        print("  - Frame 초기화 완료")

        self.scheduler = scheduler
        self.selected_index = None
        self.task_factory = None  # TaskFactory 저장용
        print("  - 속성 설정 완료")

        # 콜백 함수들
        self.on_task_edit: Optional[Callable] = None
        self.on_schedule_changed: Optional[Callable] = None
        print("  - 콜백 설정 완료")

        # 드래그 앤 드롭 상태
        self._drag_active = False
        self._drop_highlight = False

        print("  - UI 설정 시작...")
        self._setup_ui()
        print("  - UI 설정 완료")

        print("  - 스케줄러 콜백 설정...")
        self._setup_scheduler_callbacks()
        print("  - 스케줄러 콜백 완료")

        print("  - 뷰 업데이트...")
        self.update_view()
        print("SchedulerWidget.__init__ 완료")

    def _setup_ui(self):
        """UI 구성 (드롭 영역 개선)"""
        # 제목과 정보
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text="📅 작업 스케줄", font=("Arial", 11, "bold")).pack(
            side=tk.LEFT
        )

        self.info_label = ttk.Label(
            header_frame, text="총 0개 작업 | 예상 시간: 0분", font=("Arial", 9)
        )
        self.info_label.pack(side=tk.RIGHT)

        # 진행률 바
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))

        # 작업 목록 프레임 (드롭 영역으로 설정)
        list_frame = ttk.LabelFrame(
            self, text="📋 작업 목록 (여기에 드래그하세요)", padding="5"
        )
        list_frame.pack(fill=tk.BOTH, expand=True)

        # 드롭 이벤트 바인딩 (프레임 전체에)
        self._setup_drop_events(list_frame)

        # 리스트박스와 스크롤바
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.task_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("Consolas", 10),
            activestyle="none",
            selectmode=tk.SINGLE,
        )
        self.task_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.configure(command=self.task_listbox.yview)

        # 리스트박스 이벤트
        self.task_listbox.bind("<<ListboxSelect>>", self._on_selection_changed)
        self.task_listbox.bind("<Double-Button-1>", self._on_double_click)
        self.task_listbox.bind("<Button-3>", self._show_context_menu)  # 우클릭

        # 드롭 이벤트 바인딩 (리스트박스에도)
        self._setup_drop_events(self.task_listbox)

        # 컨텍스트 메뉴
        self._create_context_menu()

        # 하단 버튼들
        self._create_button_panel()

        # 작업 정보 표시
        info_frame = ttk.LabelFrame(self, text="작업 정보", padding=5)
        info_frame.pack(fill=tk.X, pady=(10, 0))

        self.task_info_text = tk.Text(
            info_frame, height=4, wrap=tk.WORD, font=("Arial", 9)
        )
        self.task_info_text.pack(fill=tk.X)
        self.task_info_text.config(state=tk.DISABLED)

    def _setup_drop_events(self, widget):
        """드롭 이벤트 설정"""
        # 모든 마우스 이벤트를 바인딩하여 드롭 감지
        widget.bind("<Button-1>", self._on_potential_drop)
        widget.bind("<ButtonRelease-1>", self._on_potential_drop)
        widget.bind("<Motion>", self._on_mouse_motion)
        widget.bind("<Enter>", self._on_drop_enter)
        widget.bind("<Leave>", self._on_drop_leave)

        # 키보드 이벤트도 바인딩 (전역 드롭 처리)
        widget.bind("<Key>", self._on_key_event)

    def _on_mouse_motion(self, event):
        """마우스 이동 이벤트"""
        # 드래그 중인지 확인하고 시각적 피드백 제공
        main_app = self._find_main_app()
        if (
            main_app
            and hasattr(main_app, "_dragging_task_info")
            and main_app._dragging_task_info
        ):
            if not self._drop_highlight:
                self._show_drop_highlight()

    def _on_drop_enter(self, event):
        """드롭 영역 진입"""
        main_app = self._find_main_app()
        if (
            main_app
            and hasattr(main_app, "_dragging_task_info")
            and main_app._dragging_task_info
        ):
            self._show_drop_highlight()

    def _on_drop_leave(self, event):
        """드롭 영역 이탈"""
        self._hide_drop_highlight()

    def _on_potential_drop(self, event):
        """잠재적 드롭 이벤트 처리"""
        try:
            print(f"잠재적 드롭 이벤트: {event.type} at {event.x}, {event.y}")

            # 메인 애플리케이션에서 드래그 데이터 확인
            main_app = self._find_main_app()
            if main_app and hasattr(main_app, "_dragging_task_info"):
                drag_data = main_app._dragging_task_info
                if drag_data:
                    print(f"드래그 데이터 발견: {drag_data}")
                    self._handle_task_drop(drag_data)
                    # 드래그 데이터 초기화
                    main_app._dragging_task_info = None

        except Exception as e:
            print(f"드롭 처리 중 오류: {e}")

    def _on_key_event(self, event):
        """키 이벤트 처리 (전역 드롭 감지)"""
        # 특정 키 조합으로 드롭 트리거 (디버깅용)
        if event.keysym == "space":
            main_app = self._find_main_app()
            if (
                main_app
                and hasattr(main_app, "_dragging_task_info")
                and main_app._dragging_task_info
            ):
                self._handle_task_drop(main_app._dragging_task_info)
                main_app._dragging_task_info = None

    def _handle_task_drop(self, task_info):
        """작업 드롭 처리 (개선된 버전)"""
        try:
            print(f"작업 드롭 처리: {task_info}")

            # TaskFactory 확인
            if not self.task_factory:
                from tasks.task_factory import TaskFactory
                from core.config import Config
                from core.security import SecurityManager

                print("TaskFactory 생성")
                self.task_factory = TaskFactory(
                    config=Config(), security_manager=SecurityManager()
                )

            # 작업 생성
            print(f"작업 생성 중: {task_info['type']}")
            task = self.task_factory.create_task(
                task_info["type"], task_info.get("name")
            )

            # 작업 추가
            print(f"스케줄러에 작업 추가: {task.name}")
            task_id = self.add_task(task)
            print(f"작업 추가 완료: {task_id}")

            # 시각적 피드백
            self._hide_drop_highlight()

            # 성공 메시지
            print(f"✅ 작업 '{task.name}'이(가) 성공적으로 추가되었습니다.")

            return True
        except Exception as e:
            print(f"❌ 작업 드롭 처리 실패: {e}")
            import traceback

            traceback.print_exc()

            # 에러 시 하이라이트 제거
            self._hide_drop_highlight()
            return False

    def enable_drop(self):
        """드롭 활성화"""
        # Windows에서 드래그 앤 드롭 활성화
        try:
            from tkinterdnd2 import TkinterDnD

            # tkinterdnd2가 설치되어 있으면 사용
            self.task_listbox.drop_target_register("DND_Text")
            self.task_listbox.dnd_bind("<<Drop>>", self._on_dnd_drop)
        except ImportError:
            pass

    def _show_drop_highlight(self):
        """드롭 하이라이트 표시"""
        if not self._drop_highlight:
            self.task_listbox.config(bg="#e8f4f8", relief=tk.RIDGE, borderwidth=2)
            self._drop_highlight = True

    def _hide_drop_highlight(self):
        """드롭 하이라이트 숨기기"""
        if self._drop_highlight:
            self.task_listbox.config(bg="white", relief=tk.SUNKEN, borderwidth=1)
            self._drop_highlight = False

    def _find_main_app(self):
        """메인 애플리케이션 인스턴스 찾기"""
        try:
            # 위젯 트리를 거슬러 올라가며 메인 애플리케이션 찾기
            widget = self
            while widget:
                if hasattr(widget, "main_app"):
                    return widget.main_app
                if hasattr(widget, "master"):
                    widget = widget.master
                    if hasattr(widget, "_dragging_task_info"):
                        return widget
                else:
                    break
            return None
        except Exception as e:
            print(f"메인 앱 찾기 실패: {e}")
            return None

    def _on_drop(self, event):
        """드롭 이벤트 처리 (개선된 버전)"""
        try:
            # 드롭 대상이 자신의 리스트박스인지 확인
            if event.widget != self.task_listbox and event.widget != self:
                return

            # 드래그 데이터 찾기
            drag_data = None

            # TaskListWidget 찾기
            for widget in self.winfo_toplevel().winfo_children():
                if self._check_for_task_list_widget(widget):
                    task_list_widget = self._get_task_list_widget(widget)
                    if task_list_widget and hasattr(task_list_widget, "get_drag_data"):
                        drag_data = task_list_widget.get_drag_data()
                        if drag_data:
                            break

            if not drag_data:
                print("드래그 데이터를 찾을 수 없습니다.")
                return

            print(f"드래그 데이터 받음: {drag_data}")

            # TaskFactory 확인
            if not self.task_factory:
                from tasks.task_factory import TaskFactory
                from core.config import Config
                from core.security import SecurityManager

                print("TaskFactory 임시 생성")
                self.task_factory = TaskFactory(
                    config=Config(), security_manager=SecurityManager()
                )

            # 작업 생성
            task = self.task_factory.create_task(
                drag_data["type"], drag_data.get("name")
            )

            # 작업 추가
            self.add_task(task)

            # 시각적 피드백
            self.task_listbox.config(relief=tk.RAISED)

            print(f"작업 '{task.name}'이(가) 추가되었습니다.")

        except Exception as e:
            print(f"드롭 처리 중 오류: {e}")
            import traceback

            traceback.print_exc()

    def _check_for_task_list_widget(self, widget):
        """위젯이 TaskListWidget를 포함하는지 확인"""
        if hasattr(widget, "get_drag_data"):
            return True
        for child in widget.winfo_children():
            if self._check_for_task_list_widget(child):
                return True
        return False

    def _get_task_list_widget(self, widget):
        """TaskListWidget 찾기"""
        if hasattr(widget, "get_drag_data"):
            return widget
        for child in widget.winfo_children():
            result = self._get_task_list_widget(child)
            if result:
                return result
        return None

    def _find_task_list_widget(self, parent):
        """TaskListWidget 재귀적으로 찾기"""
        for child in parent.winfo_children():
            if hasattr(child, "get_drag_data"):
                return child
            # Frame이나 다른 컨테이너인 경우 재귀 탐색
            result = self._find_task_list_widget(child)
            if result:
                return result
        return None

    def _on_drag_enter(self, event):
        """드래그 오버 시작"""
        self.task_listbox.config(relief=tk.SUNKEN, highlightthickness=2)

    def _on_drag_leave(self, event):
        """드래그 오버 종료"""
        self.task_listbox.config(relief=tk.RAISED, highlightthickness=1)

    def _create_button_panel(self):
        """버튼 패널 생성"""
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # 왼쪽 버튼들 (작업 조작)
        left_frame = ttk.Frame(button_frame)
        left_frame.pack(side=tk.LEFT)

        ttk.Button(left_frame, text="↑", command=self.move_up, width=3).pack(
            side=tk.LEFT, padx=2
        )

        ttk.Button(left_frame, text="↓", command=self.move_down, width=3).pack(
            side=tk.LEFT, padx=2
        )

        ttk.Separator(left_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=5
        )

        ttk.Button(left_frame, text="⚙️ 설정", command=self.edit_task, width=8).pack(
            side=tk.LEFT, padx=2
        )

        ttk.Button(left_frame, text="🗑️ 삭제", command=self.remove_task, width=8).pack(
            side=tk.LEFT, padx=2
        )

        ttk.Button(left_frame, text="🔄 초기화", command=self.reset_task, width=8).pack(
            side=tk.LEFT, padx=2
        )

        # 오른쪽 버튼들 (스케줄 관리)
        right_frame = ttk.Frame(button_frame)
        right_frame.pack(side=tk.RIGHT)

        ttk.Button(
            right_frame, text="💾 저장", command=self.save_schedule, width=8
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            right_frame, text="📂 불러오기", command=self.load_schedule, width=10
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            right_frame, text="🗑️ 전체삭제", command=self.clear_all, width=10
        ).pack(side=tk.LEFT, padx=2)

    def _create_context_menu(self):
        """컨텍스트 메뉴 생성"""
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="설정", command=self.edit_task)
        self.context_menu.add_command(label="삭제", command=self.remove_task)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="위로 이동", command=self.move_up)
        self.context_menu.add_command(label="아래로 이동", command=self.move_down)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="초기화", command=self.reset_task)
        self.context_menu.add_command(label="복제", command=self.duplicate_task)

    def _setup_scheduler_callbacks(self):
        """스케줄러 콜백 설정"""
        self.scheduler.on_task_start = self._on_task_start
        self.scheduler.on_task_complete = self._on_task_complete
        self.scheduler.on_task_failed = self._on_task_failed

    def add_task(self, task: BaseTask):
        """작업 추가 (개선된 버전)"""
        try:
            print(f"add_task 호출: {task.name}")
            task_id = self.scheduler.add_task(task)
            print(f"스케줄러에 추가 완료: {task_id}")

            # 즉시 뷰 업데이트
            self.update_view()
            print("뷰 업데이트 완료")

            # 콜백 호출
            if self.on_schedule_changed:
                self.on_schedule_changed()

            return task_id

        except Exception as e:
            print(f"작업 추가 실패: {e}")
            raise

    def update_view(self):
        """뷰 업데이트 (개선된 버전)"""
        print("update_view() 시작...")

        try:
            # 현재 선택 위치 저장
            current_selection = self.task_listbox.curselection()
            print(f"  - 현재 선택: {current_selection}")

            # 리스트박스 초기화
            self.task_listbox.delete(0, tk.END)
            print("  - 리스트박스 초기화 완료")

            # 작업 목록 표시
            print("  - 스케줄러에서 작업 가져오기...")
            if self.scheduler is None:
                print("  - 경고: 스케줄러가 None입니다!")
                return

            tasks = self.scheduler.get_all_tasks()
            print(f"  - 작업 개수: {len(tasks)}")

            total_duration = 0

            for i, task in enumerate(tasks):
                print(f"  - 작업 {i}: {task.name} (상태: {task.status.value})")

                # 상태 아이콘
                status_icon = self._get_status_icon(task.status)

                # 표시 텍스트
                display_text = f"{i+1}. {status_icon} {task.name}"

                # 추가 정보
                if hasattr(task, "get_estimated_duration"):
                    try:
                        duration = task.get_estimated_duration()
                        total_duration += duration

                        # 파라미터 정보 추가
                        if task.parameters:
                            param_info = []
                            for key, value in task.parameters.items():
                                if key != "password":  # 비밀번호 숨김
                                    param_info.append(f"{key}={value}")

                            if param_info:
                                param_str = ", ".join(param_info[:2])  # 최대 2개만
                                if len(param_info) > 2:
                                    param_str += "..."
                                display_text += f" ({param_str})"

                    except Exception as e:
                        print(f"    - 작업 정보 처리 오류: {e}")

                # 리스트박스에 추가
                self.task_listbox.insert(tk.END, display_text)

                # 상태별 색상 설정
                color = self._get_status_color(task.status)
                if color != "black":
                    try:
                        self.task_listbox.itemconfig(i, foreground=color)
                    except:
                        pass

            # 정보 라벨 업데이트
            total_min = int(total_duration / 60)
            self.info_label.config(
                text=f"총 {len(tasks)}개 작업 | 예상 시간: {total_min}분"
            )

            # 선택 복원
            if current_selection and current_selection[0] < len(tasks):
                self.task_listbox.selection_set(current_selection[0])
                self.selected_index = current_selection[0]
                self._show_task_info()

            print("update_view() 완료")

        except Exception as e:
            print(f"update_view() 오류: {e}")
            import traceback

            traceback.print_exc()

    def _get_status_icon(self, status: TaskStatus) -> str:
        """상태별 아이콘"""
        icons = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.RUNNING: "▶️",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.CANCELLED: "🚫",
            TaskStatus.SKIPPED: "⏭️",
        }
        return icons.get(status, "❓")

    def _get_status_color(self, status: TaskStatus) -> str:
        """상태별 색상"""
        colors = {
            TaskStatus.PENDING: "black",
            TaskStatus.RUNNING: "blue",
            TaskStatus.COMPLETED: "green",
            TaskStatus.FAILED: "red",
            TaskStatus.CANCELLED: "orange",
            TaskStatus.SKIPPED: "gray",
        }
        return colors.get(status, "black")

    def _on_selection_changed(self, event):
        """선택 변경 이벤트"""
        selection = self.task_listbox.curselection()
        if selection:
            self.selected_index = selection[0]
            self._show_task_info()
        else:
            self.selected_index = None
            self._clear_task_info()

    def _show_task_info(self):
        """작업 정보 표시"""
        if self.selected_index is None:
            return

        tasks = self.scheduler.get_all_tasks()
        if self.selected_index >= len(tasks):
            return

        task = tasks[self.selected_index]

        # 정보 텍스트 생성
        info_lines = [
            f"작업: {task.name}",
            f"유형: {task.type.value}",
            f"상태: {task.status.value}",
            f"설명: {task.description}",
        ]

        # 파라미터 표시
        if task.parameters:
            info_lines.append("\n파라미터:")
            for key, value in task.parameters.items():
                if key != "password":  # 비밀번호는 숨김
                    info_lines.append(f"  {key}: {value}")

        # 실행 정보
        if task.started_at:
            info_lines.append(f"\n시작: {task.started_at.strftime('%H:%M:%S')}")
        if task.completed_at:
            info_lines.append(f"완료: {task.completed_at.strftime('%H:%M:%S')}")
        if task.result:
            info_lines.append(f"결과: {task.result.message}")

        # 텍스트 표시
        self.task_info_text.config(state=tk.NORMAL)
        self.task_info_text.delete(1.0, tk.END)
        self.task_info_text.insert(1.0, "\n".join(info_lines))
        self.task_info_text.config(state=tk.DISABLED)

    def _clear_task_info(self):
        """작업 정보 지우기"""
        self.task_info_text.config(state=tk.NORMAL)
        self.task_info_text.delete(1.0, tk.END)
        self.task_info_text.config(state=tk.DISABLED)

    def _on_double_click(self, event):
        """더블클릭 이벤트"""
        self.edit_task()

    def _show_context_menu(self, event):
        """컨텍스트 메뉴 표시"""
        # 클릭 위치의 항목 선택
        index = self.task_listbox.nearest(event.y)
        self.task_listbox.selection_clear(0, tk.END)
        self.task_listbox.selection_set(index)
        self.selected_index = index

        # 메뉴 표시
        self.context_menu.post(event.x_root, event.y_root)

    def move_up(self):
        """선택한 작업을 위로 이동"""
        if self.selected_index is None or self.selected_index == 0:
            return

        tasks = self.scheduler.get_all_tasks()
        if self.selected_index >= len(tasks):
            return

        task = tasks[self.selected_index]
        if self.scheduler.move_task_up(task.id):
            self.selected_index -= 1
            self.update_view()
            self.task_listbox.selection_set(self.selected_index)

            if self.on_schedule_changed:
                self.on_schedule_changed()

    def move_down(self):
        """선택한 작업을 아래로 이동"""
        if self.selected_index is None:
            return

        tasks = self.scheduler.get_all_tasks()
        if self.selected_index >= len(tasks) - 1:
            return

        task = tasks[self.selected_index]
        if self.scheduler.move_task_down(task.id):
            self.selected_index += 1
            self.update_view()
            self.task_listbox.selection_set(self.selected_index)

            if self.on_schedule_changed:
                self.on_schedule_changed()

    def edit_task(self):
        """선택한 작업 편집"""
        if self.selected_index is None:
            return

        tasks = self.scheduler.get_all_tasks()
        if self.selected_index >= len(tasks):
            return

        task = tasks[self.selected_index]

        if self.on_task_edit:
            self.on_task_edit(task)

    def remove_task(self):
        """선택한 작업 삭제"""
        if self.selected_index is None:
            return

        tasks = self.scheduler.get_all_tasks()
        if self.selected_index >= len(tasks):
            return

        task = tasks[self.selected_index]

        # 확인 대화상자
        result = messagebox.askyesno(
            "삭제 확인", f"'{task.name}' 작업을 삭제하시겠습니까?"
        )

        if result:
            self.scheduler.remove_task(task.id)
            self.update_view()

            if self.on_schedule_changed:
                self.on_schedule_changed()

    def reset_task(self):
        """선택한 작업 초기화"""
        if self.selected_index is None:
            return

        tasks = self.scheduler.get_all_tasks()
        if self.selected_index >= len(tasks):
            return

        task = tasks[self.selected_index]
        task.reset()
        self.update_view()

    def duplicate_task(self):
        """선택한 작업 복제"""
        if self.selected_index is None:
            return

        tasks = self.scheduler.get_all_tasks()
        if self.selected_index >= len(tasks):
            return

        original_task = tasks[self.selected_index]

        # 새 작업 생성 (같은 타입과 파라미터)
        new_task = original_task.__class__(f"{original_task.name} (복사)")
        new_task.parameters = original_task.parameters.copy()

        self.scheduler.add_task(new_task)
        self.update_view()

        if self.on_schedule_changed:
            self.on_schedule_changed()

    def clear_all(self):
        """모든 작업 삭제"""
        if not self.scheduler.get_all_tasks():
            return

        result = messagebox.askyesno("전체 삭제", "모든 작업을 삭제하시겠습니까?")

        if result:
            self.scheduler.clear_tasks()
            self.update_view()

            if self.on_schedule_changed:
                self.on_schedule_changed()

    def save_schedule(self):
        """스케줄 저장"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )

        if not filename:
            return

        try:
            # 작업들을 직렬화 가능한 형태로 변환
            schedule_data = {"created_at": datetime.now().isoformat(), "tasks": []}

            for task in self.scheduler.get_all_tasks():
                task_data = {
                    "class": task.__class__.__name__,
                    "name": task.name,
                    "type": task.type.value,
                    "parameters": task.parameters.copy(),
                }
                schedule_data["tasks"].append(task_data)

            # 파일로 저장
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(schedule_data, f, ensure_ascii=False, indent=2)

            messagebox.showinfo("저장 완료", "스케줄이 저장되었습니다.")

        except Exception as e:
            messagebox.showerror("저장 실패", f"스케줄 저장 중 오류: {str(e)}")

    def load_schedule(self):
        """스케줄 불러오기"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if not filename:
            return

        try:
            # 파일 읽기
            with open(filename, "r", encoding="utf-8") as f:
                schedule_data = json.load(f)

            # 현재 작업 확인
            if self.scheduler.get_all_tasks():
                result = messagebox.askyesno(
                    "불러오기 확인", "현재 작업들을 모두 삭제하고 불러오시겠습니까?"
                )
                if not result:
                    return

            # 기존 작업 삭제
            self.scheduler.clear_tasks()

            # 작업 클래스 매핑
            from tasks.login_task import LoginTask
            from tasks.check_posts_task import CheckNewPostsTask
            from tasks.comment_task import WriteCommentTask
            from tasks.utility_task import (
                LikeTask,
                WaitTask,
                ScrollReadTask,
                GoToUrlTask,
            )
            from tasks.accept_neighbor_requests_task import AcceptNeighborRequestsTask
            from tasks.cancel_pending_neighbor_requests_task import (
                CancelPendingNeighborRequestsTask,
            )
            from tasks.topic_based_blog_task import TopicBasedBlogTask

            class_map = {
                "LoginTask": LoginTask,
                "CheckNewPostsTask": CheckNewPostsTask,
                "WriteCommentTask": WriteCommentTask,
                "LikeTask": LikeTask,
                "WaitTask": WaitTask,
                "ScrollReadTask": ScrollReadTask,
                "GoToUrlTask": GoToUrlTask,
                # 새로 추가
                "AcceptNeighborRequestsTask": AcceptNeighborRequestsTask,
                "CancelPendingNeighborRequestsTask": CancelPendingNeighborRequestsTask,
                "TopicBasedBlogTask": TopicBasedBlogTask,
            }

            # 작업 생성 및 추가
            for task_data in schedule_data.get("tasks", []):
                class_name = task_data.get("class")
                if class_name in class_map:
                    task_class = class_map[class_name]
                    task = task_class(task_data.get("name", ""))
                    task.parameters = task_data.get("parameters", {})
                    self.scheduler.add_task(task)

            self.update_view()
            messagebox.showinfo("불러오기 완료", "스케줄을 불러왔습니다.")

            if self.on_schedule_changed:
                self.on_schedule_changed()

        except Exception as e:
            messagebox.showerror("불러오기 실패", f"스케줄 불러오기 중 오류: {str(e)}")

    def _on_task_start(self, task: BaseTask):
        """작업 시작 콜백"""
        self.update_view()

    def _on_task_complete(self, task: BaseTask, result):
        """작업 완료 콜백"""
        self.update_view()

    def _on_task_failed(self, task: BaseTask, result):
        """작업 실패 콜백"""
        self.update_view()
