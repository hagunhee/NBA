"""
수정된 작업 편집 다이얼로그
주요 수정사항:
1. 파라미터 설정 로직 개선
2. 검증 로직 강화
3. 디버깅 로그 추가
4. 에러 처리 개선
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional
import json

from tasks.base_task import BaseTask, TaskType


class TaskEditDialog:
    """작업 편집 다이얼로그 (수정된 버전)"""

    def __init__(self, parent, task: BaseTask):
        self.task = task
        self.result = False  # 명시적 초기화
        self.param_widgets = {}

        # 디버깅을 위한 로깅
        print(f"TaskEditDialog 초기화: {task.name}")
        print(f"초기 파라미터: {task.parameters}")

        # 다이얼로그 생성
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"{task.name} 설정")
        self.dialog.geometry("600x700")
        self.dialog.resizable(True, True)

        # 중앙 배치
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 다이얼로그 닫기 이벤트 처리 추가
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        self._setup_ui()
        self._load_current_values()

        # 포커스 설정
        self.dialog.focus_set()

    def _setup_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 작업 정보
        self._create_info_section(main_frame)

        # 파라미터 편집
        self._create_parameters_section(main_frame)

        # 버튼들
        self._create_buttons(main_frame)

    def _create_info_section(self, parent):
        """작업 정보 섹션"""
        info_frame = ttk.LabelFrame(parent, text="작업 정보", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 20))

        # 작업 이름
        name_frame = ttk.Frame(info_frame)
        name_frame.pack(fill=tk.X, pady=5)

        ttk.Label(name_frame, text="작업 이름:").pack(side=tk.LEFT)
        self.name_var = tk.StringVar(value=self.task.name)
        ttk.Entry(name_frame, textvariable=self.name_var, width=40).pack(
            side=tk.LEFT, padx=(10, 0)
        )

        # 작업 정보 표시
        info_text = f"유형: {self.task.type.value}\n"
        info_text += f"설명: {self.task.description}"

        ttk.Label(info_frame, text=info_text, foreground="gray").pack(
            anchor=tk.W, pady=(10, 0)
        )

    def _create_parameters_section(self, parent):
        """파라미터 섹션"""
        param_frame = ttk.LabelFrame(parent, text="파라미터", padding="10")
        param_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # 스크롤 가능한 영역
        canvas = tk.Canvas(param_frame)
        scrollbar = ttk.Scrollbar(param_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 파라미터 위젯 생성
        if hasattr(self.task, "get_required_parameters"):
            param_info = self.task.get_required_parameters()
            print(f"필수 파라미터 정보: {param_info}")
            self._create_parameter_widgets(scrollable_frame, param_info)
        else:
            # 기본 파라미터 표시
            self._create_default_parameter_widgets(scrollable_frame)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _create_parameter_widgets(self, parent, param_info: Dict[str, Dict[str, Any]]):
        """파라미터 위젯 생성 (개선된 버전)"""

        # 파라미터 그룹핑 (주제별 블로그 작업의 경우)
        if isinstance(self.task, TopicBasedBlogTask):
            self._create_grouped_parameters(parent, param_info)
        else:
            # 기존 방식
            for param_name, info in param_info.items():
                self._create_single_parameter_widget(parent, param_name, info)

    def _create_grouped_parameters(self, parent, param_info: Dict[str, Dict[str, Any]]):
        """그룹화된 파라미터 위젯 생성"""

        # 탭 위젯 생성
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        # 기본 설정 탭
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="기본 설정")

        basic_params = [
            "topic",
            "post_days",
            "execution_order",
            "target_type",
            "target_count",
        ]
        for param in basic_params:
            if param in param_info:
                self._create_single_parameter_widget(
                    basic_frame, param, param_info[param]
                )

        # 필터 설정 탭
        filter_frame = ttk.Frame(notebook)
        notebook.add(filter_frame, text="필터 설정")

        filter_params = [
            "min_likes",
            "max_likes",
            "min_comments",
            "max_comments",
            "min_posts",
            "max_posts",
            "recent_post_days",
            "min_neighbors",
            "max_neighbors",
            "min_total_visitors",
            "min_today_visitors",
            "exclude_my_neighbors",
            "exclude_official_bloggers",
            "exclude_no_profile_image",
        ]

        # 스크롤 가능한 프레임
        canvas = tk.Canvas(filter_frame)
        scrollbar = ttk.Scrollbar(filter_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for param in filter_params:
            if param in param_info:
                self._create_single_parameter_widget(
                    scrollable_frame, param, param_info[param]
                )

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 서로이웃 설정 탭
        neighbor_frame = ttk.Frame(notebook)
        notebook.add(neighbor_frame, text="서로이웃 설정")

        neighbor_params = [
            "neighbor_enabled",
            "neighbor_max_count",
            "neighbor_delay_min",
            "neighbor_delay_max",
            "neighbor_probability",
        ]
        for param in neighbor_params:
            if param in param_info:
                self._create_single_parameter_widget(
                    neighbor_frame, param, param_info[param]
                )

        # 댓글 설정 탭
        comment_frame = ttk.Frame(notebook)
        notebook.add(comment_frame, text="댓글 설정")

        comment_params = [
            "comment_enabled",
            "comment_max_count",
            "comment_delay_min",
            "comment_delay_max",
            "comment_probability",
            "comment_style",
            "comment_use_ai",
        ]
        for param in comment_params:
            if param in param_info:
                self._create_single_parameter_widget(
                    comment_frame, param, param_info[param]
                )

        # 공감 설정 탭
        like_frame = ttk.Frame(notebook)
        notebook.add(like_frame, text="공감 설정")

        like_params = [
            "like_enabled",
            "like_max_count",
            "like_delay_min",
            "like_delay_max",
            "like_probability",
        ]
        for param in like_params:
            if param in param_info:
                self._create_single_parameter_widget(
                    like_frame, param, param_info[param]
                )

    def _create_single_parameter_widget(
        self, parent, param_name: str, info: Dict[str, Any]
    ):
        """단일 파라미터 위젯 생성"""
        # 기존 _create_parameter_widgets의 내부 로직을 여기로 이동
        p_frame = ttk.Frame(parent)
        p_frame.pack(fill=tk.X, pady=5)

    def _create_input_widget(
        self, parent, param_name: str, info: Dict[str, Any], current_value: Any
    ):
        """입력 위젯 생성 (개선된 버전)"""
        param_type = info.get("type", "string")
        print(f"    위젯 타입: {param_type}, 값: {current_value}")

        widget_frame = ttk.Frame(parent)
        widget_frame.pack(fill=tk.X, pady=2)

        if param_type == "string":
            widget = ttk.Entry(widget_frame, width=50)
            value_str = str(current_value) if current_value is not None else ""
            widget.insert(0, value_str)
            widget.pack(side=tk.LEFT)
            return widget

        elif param_type == "password":
            widget = ttk.Entry(widget_frame, width=50, show="*")
            value_str = str(current_value) if current_value is not None else ""
            widget.insert(0, value_str)
            widget.pack(side=tk.LEFT)

            # 표시/숨기기 버튼
            show_var = tk.BooleanVar(value=False)

            def toggle_show():
                widget.config(show="" if show_var.get() else "*")

            ttk.Checkbutton(
                widget_frame, text="표시", variable=show_var, command=toggle_show
            ).pack(side=tk.LEFT, padx=(10, 0))

            return widget

        elif param_type == "integer":
            min_val = info.get("min", 0)
            max_val = info.get("max", 9999)

            widget = ttk.Spinbox(widget_frame, from_=min_val, to=max_val, width=20)

            # 값 설정 개선
            if current_value is not None:
                try:
                    int_value = int(float(current_value))
                    widget.set(str(int_value))
                except (ValueError, TypeError):
                    widget.set(str(info.get("default", 0)))
            else:
                widget.set(str(info.get("default", 0)))

            widget.pack(side=tk.LEFT)
            return widget

        elif param_type == "float":
            min_val = info.get("min", 0.0)
            max_val = info.get("max", 999.9)
            increment = 0.1 if max_val <= 1.0 else 0.5

            widget = ttk.Spinbox(
                widget_frame,
                from_=min_val,
                to=max_val,
                increment=increment,
                width=20,
                format="%.2f",
            )

            # 값 설정 개선
            if current_value is not None:
                try:
                    float_value = float(current_value)
                    widget.set(f"{float_value:.2f}")
                except (ValueError, TypeError):
                    widget.set(f"{info.get('default', 0.0):.2f}")
            else:
                widget.set(f"{info.get('default', 0.0):.2f}")

            widget.pack(side=tk.LEFT)
            return widget

        elif param_type == "boolean":
            var = tk.BooleanVar()

            # 값 설정 개선
            if current_value is not None:
                var.set(bool(current_value))
            else:
                var.set(bool(info.get("default", False)))

            widget = ttk.Checkbutton(widget_frame, variable=var)
            widget.var = var  # 변수 참조 저장
            widget.pack(side=tk.LEFT)
            return widget

        elif param_type == "choice":
            choices = info.get("choices", [])
            widget = ttk.Combobox(
                widget_frame, values=choices, state="readonly", width=30
            )

            # 값 설정 개선
            if current_value is not None and str(current_value) in choices:
                widget.set(str(current_value))
            else:
                default_value = info.get("default", "")
                if default_value in choices:
                    widget.set(default_value)
                elif choices:
                    widget.set(choices[0])

            widget.pack(side=tk.LEFT)
            return widget

        elif param_type == "list":
            # 리스트 편집 위젯
            list_frame = ttk.Frame(widget_frame)
            list_frame.pack(fill=tk.BOTH, expand=True)

            # 텍스트 영역
            widget = tk.Text(list_frame, width=50, height=4)
            widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # 현재 값 표시 개선
            if current_value and isinstance(current_value, list):
                widget.insert(1.0, "\n".join(str(item) for item in current_value))
            elif current_value:
                # 문자열인 경우
                widget.insert(1.0, str(current_value))

            # 스크롤바
            scrollbar = ttk.Scrollbar(list_frame, command=widget.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            widget.config(yscrollcommand=scrollbar.set)

            # 도움말
            ttk.Label(
                parent,
                text="(한 줄에 하나씩 입력)",
                font=("Arial", 8),
                foreground="gray",
            ).pack(anchor=tk.W)

            return widget

        return None

    def _create_default_parameter_widgets(self, parent):
        """기본 파라미터 위젯"""
        if not self.task.parameters:
            ttk.Label(
                parent, text="설정 가능한 파라미터가 없습니다.", foreground="gray"
            ).pack(pady=20)
            return

        # JSON 편집기
        ttk.Label(parent, text="파라미터 (JSON):").pack(anchor=tk.W)

        self.json_text = tk.Text(parent, height=10, width=60)
        self.json_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # 현재 파라미터를 JSON으로 표시
        json_str = json.dumps(self.task.parameters, indent=2, ensure_ascii=False)
        self.json_text.insert(1.0, json_str)

    def _create_buttons(self, parent):
        """버튼 생성 (개선된 버전)"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X)

        # 왼쪽: 리셋 버튼
        ttk.Button(
            button_frame, text="기본값으로 리셋", command=self._reset_to_defaults
        ).pack(side=tk.LEFT)

        # 오른쪽: 저장/취소
        ttk.Button(button_frame, text="저장", command=self._save).pack(
            side=tk.RIGHT, padx=(5, 0)
        )

        ttk.Button(button_frame, text="취소", command=self._on_close).pack(
            side=tk.RIGHT
        )

        # Enter 키 바인딩
        self.dialog.bind("<Return>", lambda e: self._save())
        self.dialog.bind("<Escape>", lambda e: self._on_close())

    def _on_close(self):
        """다이얼로그 닫기 처리"""
        print("다이얼로그 닫기 - 취소")
        self.result = False
        self.dialog.destroy()

    def _load_current_values(self):
        """현재 값 로드 (이미 위젯 생성 시 처리됨)"""
        print(f"현재 값 로드 완료: {self.task.parameters}")

    def _reset_to_defaults(self):
        """기본값으로 리셋"""
        result = messagebox.askyesno(
            "확인", "모든 파라미터를 기본값으로 리셋하시겠습니까?"
        )

        if not result:
            return

        if hasattr(self.task, "get_required_parameters"):
            param_info = self.task.get_required_parameters()

            for param_name, widget in self.param_widgets.items():
                if param_name in param_info:
                    default = param_info[param_name].get("default", "")
                    self._set_widget_value(widget, default)

    def _set_widget_value(self, widget, value):
        """위젯 값 설정"""
        if isinstance(widget, ttk.Entry):
            widget.delete(0, tk.END)
            widget.insert(0, str(value) if value is not None else "")
        elif isinstance(widget, ttk.Spinbox):
            widget.set(str(value) if value is not None else "0")
        elif isinstance(widget, ttk.Checkbutton):
            widget.var.set(bool(value))
        elif isinstance(widget, ttk.Combobox):
            widget.set(str(value) if value is not None else "")
        elif isinstance(widget, tk.Text):
            widget.delete(1.0, tk.END)
            if isinstance(value, list):
                widget.insert(1.0, "\n".join(str(item) for item in value))
            else:
                widget.insert(1.0, str(value) if value else "")

    def _save(self):
        """설정 저장 (개선된 버전)"""
        try:
            print("=== 저장 시작 ===")

            # 작업 이름 업데이트
            new_name = self.name_var.get().strip()
            if new_name:
                self.task.name = new_name
                print(f"작업 이름 변경: {new_name}")

            print(f"저장 전 파라미터: {self.task.parameters}")

            # 파라미터 수집
            if self.param_widgets:
                success = self._save_structured_parameters()
                if not success:
                    print("구조화된 파라미터 저장 실패")
                    return  # 저장 실패시 리턴
            elif hasattr(self, "json_text"):
                success = self._save_json_parameters()
                if not success:
                    print("JSON 파라미터 저장 실패")
                    return

            print(f"저장 후 파라미터: {self.task.parameters}")

            # 파라미터 검증
            if hasattr(self.task, "validate_parameters"):
                is_valid = self.task.validate_parameters()
                print(f"파라미터 검증 결과: {is_valid}")

                if not is_valid:
                    print("파라미터 검증 실패")
                    self._show_validation_error()
                    return

            # 성공 처리
            print("=== 저장 성공 ===")
            self.result = True  # 중요: 결과 설정
            self.dialog.destroy()

        except Exception as e:
            print(f"저장 중 오류: {e}")
            import traceback

            traceback.print_exc()
            messagebox.showerror("오류", f"설정 저장 실패: {str(e)}")
            self.result = False

    def _save_structured_parameters(self) -> bool:
        """구조화된 파라미터 저장 (개선된 버전)"""
        try:
            # 필수 파라미터 정보 가져오기
            param_info = {}
            if hasattr(self.task, "get_required_parameters"):
                param_info = self.task.get_required_parameters()

            # 수집된 파라미터
            collected_params = {}

            for param_name, widget in self.param_widgets.items():
                try:
                    # 위젯에서 값 가져오기
                    raw_value = self._get_widget_value(widget)
                    print(f"파라미터 '{param_name}' 원시값: {raw_value}")

                    # 타입 변환
                    if param_name in param_info:
                        param_type = param_info[param_name].get("type", "string")
                        converted_value = self._convert_parameter_value(
                            raw_value, param_type, param_info[param_name]
                        )
                        print(f"파라미터 '{param_name}' 변환값: {converted_value}")
                        collected_params[param_name] = converted_value
                    else:
                        collected_params[param_name] = raw_value

                except Exception as e:
                    print(f"파라미터 '{param_name}' 처리 중 오류: {e}")
                    messagebox.showerror(
                        "오류", f"파라미터 '{param_name}' 처리 중 오류: {str(e)}"
                    )
                    return False

            # 모든 파라미터를 한 번에 설정
            print(f"설정할 파라미터: {collected_params}")

            # 기존 파라미터 백업
            original_params = self.task.parameters.copy()

            # 새 파라미터 설정
            self.task.set_parameters(**collected_params)
            print(f"설정 후 task.parameters: {self.task.parameters}")

            # 설정이 제대로 되었는지 확인
            for param_name, expected_value in collected_params.items():
                actual_value = self.task.get_parameter(param_name)
                if actual_value != expected_value:
                    print(
                        f"경고: {param_name} 설정 불일치 - 예상: {expected_value}, 실제: {actual_value}"
                    )

            return True

        except Exception as e:
            print(f"구조화된 파라미터 저장 실패: {e}")
            messagebox.showerror("오류", f"파라미터 저장 실패: {str(e)}")
            return False

    def _convert_parameter_value(
        self, raw_value: Any, param_type: str, param_info: Dict[str, Any]
    ) -> Any:
        """파라미터 값 타입 변환"""
        try:
            if param_type == "integer":
                if isinstance(raw_value, str) and not raw_value.strip():
                    return param_info.get("default", 0)
                return int(float(raw_value))

            elif param_type == "float":
                if isinstance(raw_value, str) and not raw_value.strip():
                    return param_info.get("default", 0.0)
                return float(raw_value)

            elif param_type == "boolean":
                return bool(raw_value)

            elif param_type == "list":
                if isinstance(raw_value, list):
                    return raw_value
                elif isinstance(raw_value, str):
                    # 빈 문자열인 경우 빈 리스트 반환
                    if not raw_value.strip():
                        return []
                    # 줄바꿈으로 분할
                    return [
                        line.strip() for line in raw_value.split("\n") if line.strip()
                    ]
                else:
                    return param_info.get("default", [])

            elif param_type == "choice":
                return str(raw_value) if raw_value else param_info.get("default", "")

            else:  # string
                return str(raw_value) if raw_value is not None else ""

        except (ValueError, TypeError) as e:
            print(f"타입 변환 실패: {raw_value} -> {param_type}, 오류: {e}")
            # 기본값 반환
            return param_info.get("default", "")

    def _get_widget_value(self, widget):
        """위젯 값 가져오기 (개선된 버전)"""
        try:
            if isinstance(widget, ttk.Entry):
                return widget.get().strip()
            elif isinstance(widget, ttk.Spinbox):
                value = widget.get().strip()
                return value if value else "0"
            elif isinstance(widget, ttk.Checkbutton):
                return widget.var.get()
            elif isinstance(widget, ttk.Combobox):
                return widget.get()
            elif isinstance(widget, tk.Text):
                text = widget.get(1.0, tk.END).strip()
                # 리스트로 변환
                if not text:
                    return []
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                return lines
            else:
                return ""
        except Exception as e:
            print(f"위젯 값 가져오기 실패: {e}")
            return ""

    def _save_json_parameters(self) -> bool:
        """JSON 파라미터 저장"""
        try:
            json_str = self.json_text.get(1.0, tk.END).strip()
            params = json.loads(json_str)

            if isinstance(params, dict):
                self.task.parameters = params
                return True
            else:
                messagebox.showerror("오류", "파라미터는 딕셔너리 형식이어야 합니다.")
                return False

        except json.JSONDecodeError as e:
            messagebox.showerror("오류", f"잘못된 JSON 형식: {str(e)}")
            return False

    def _show_validation_error(self):
        """검증 오류 메시지 표시"""
        error_msg = "잘못된 파라미터 값입니다.\n\n"

        # 작업 타입별 구체적인 가이드
        if self.task.type == TaskType.LOGIN:
            error_msg += "- 네이버 아이디와 비밀번호를 입력해주세요."
        elif self.task.type == TaskType.WAIT:
            error_msg += "- 대기 시간은 1초 이상이어야 합니다.\n"
            error_msg += "- 랜덤 변동폭은 0~1 사이여야 합니다."
        elif self.task.type == TaskType.GOTO_URL:
            error_msg += "- 올바른 URL 형식을 입력해주세요.\n"
            error_msg += "  예: https://www.example.com"
        elif self.task.type == TaskType.CHECK_POSTS:
            error_msg += "- 최대 포스트 개수는 1 이상이어야 합니다."
        elif self.task.type == TaskType.WRITE_COMMENT:
            error_msg += "- 읽기 시간 설정을 확인해주세요.\n"
            error_msg += "- 댓글 스타일을 선택해주세요."

        messagebox.showerror("파라미터 오류", error_msg)
