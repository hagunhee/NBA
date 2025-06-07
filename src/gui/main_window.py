"""
GUI 메인 윈도우 - 프로필 기능 통합 버전
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import os
import json
from datetime import datetime
import time
import random

from core.updater import AutoUpdater, UpdateDialog
from core.config import Config
from core.license_manager import LicenseManager
from core.security import SecurityManager
from automation.naver_automation import NaverBlogAutomation
from utils.logger import Logger
from utils.statistics import Statistics
from gui.profile_manager import ProfileManagerDialog


class ScrollableFrame(ttk.Frame):
    """스크롤 가능한 프레임"""

    def __init__(self, parent):
        super().__init__(parent)

        # 캔버스와 스크롤바 생성
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.canvas)

        # 스크롤 가능한 프레임 설정
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        # 캔버스에 프레임 추가
        self.canvas_frame = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 레이아웃
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 마우스 휠 바인딩
        self.bind_mousewheel()

        # 캔버스 크기 조정 이벤트
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def bind_mousewheel(self):
        """마우스 휠 이벤트 바인딩"""

        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_to_mousewheel(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_from_mousewheel(event):
            self.canvas.unbind_all("<MouseWheel>")

        self.canvas.bind("<Enter>", _bind_to_mousewheel)
        self.canvas.bind("<Leave>", _unbind_from_mousewheel)

    def _on_canvas_configure(self, event):
        """캔버스 크기 조정 시 스크롤 가능한 프레임 폭 조정"""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_frame, width=canvas_width)


class BlogManagerApp:
    """메인 GUI 애플리케이션"""

    def __init__(self):
        """메인 GUI 애플리케이션 초기화"""
        self.root = tk.Tk()
        self.root.title("네이버 블로그 자동 이웃관리 v1.0.0")
        self.root.geometry("1000x800")
        self.root.resizable(True, True)
        self.root.minsize(900, 700)

        # 시스템 초기화
        self.config = Config()
        self.logger = Logger()
        self.stats = Statistics()
        self.license_manager = LicenseManager()
        self.security_manager = SecurityManager()
        self.updater = AutoUpdater(
            current_version="1.0.0",
            repo_owner="hagunhee",
            repo_name="NBA",
        )

        # 상태 변수
        self.is_licensed = False
        self.is_running = False
        self.automation = None
        self.automation_thread = None
        self.processed_posts = set()
        self.today_count = 0
        self.manual_browser = None

        # === 위젯 참조 변수들 미리 초기화 ===
        self.naver_id_entry = None
        self.naver_pw_entry = None
        self.license_entry = None
        self.save_id = None
        self.save_pw = None
        self.profile_dropdown = None
        self.current_profile_label = None

        # GUI 구성
        self.setup_gui()

        # GUI가 완전히 렌더링될 때까지 대기
        self.root.update()
        self.root.update_idletasks()

        # 초기화 완료 후 설정 불러오기
        self.root.after(1000, self.initial_load_settings)

    def initial_load_settings(self):
        """초기 설정 불러오기 - 프로필 기능 포함"""
        try:
            print("\n" + "=" * 60)
            print("초기 설정 불러오기 시작")
            print("=" * 60)

            # GUI가 완전히 로드될 때까지 대기
            self.root.update_idletasks()

            # 1. 현재 프로필 확인
            current_profile = self.config.get_current_profile_name()
            print(f"현재 프로필: {current_profile}")

            if current_profile:
                # 프로필이 설정되어 있으면 프로필에서 계정 정보 로드
                self.load_profile_account(current_profile)
            else:
                # 프로필이 없으면 기존 방식으로 시도 (하위 호환성)
                self.load_legacy_account()

            # 2. 다른 설정들 불러오기
            self.load_other_settings()

            # 3. 라이선스 확인
            self.check_saved_license()

            # 시작 메시지
            hardware_id = self.security_manager.get_hardware_id()
            self.log_message("프로그램이 시작되었습니다.")
            self.log_message(f"하드웨어 ID: {hardware_id[:16]}...")

            print("\n" + "=" * 60)
            print("초기 설정 불러오기 완료")
            print("=" * 60 + "\n")

        except Exception as e:
            print(f"\n초기 설정 불러오기 오류: {e}")
            import traceback

            traceback.print_exc()
            self.log_message(f"설정 불러오기 오류: {e}")

    def load_profile_account(self, profile_name: str):
        """프로필에서 계정 정보 로드"""
        try:
            print(f"\n프로필 '{profile_name}'에서 계정 정보 로드 중...")

            profile_data = self.config.get_profile(profile_name)
            if not profile_data:
                print(f"프로필 '{profile_name}'을 찾을 수 없습니다.")
                return

            # 아이디 설정
            naver_id = profile_data.get("naver_id", "")
            if naver_id and self.naver_id_entry:
                self.naver_id_entry.delete(0, tk.END)
                self.naver_id_entry.insert(0, naver_id)
                self.save_id.set(True)
                print(f"✓ 아이디 설정: {naver_id}")

            # 비밀번호 설정
            encrypted_pw = profile_data.get("naver_pw", "")
            save_pw = profile_data.get("save_pw", False)

            if encrypted_pw and save_pw and self.naver_pw_entry:
                try:
                    decrypted_pw = self.security_manager.decrypt_password(encrypted_pw)
                    if decrypted_pw:
                        self.naver_pw_entry.delete(0, tk.END)
                        self.naver_pw_entry.insert(0, decrypted_pw)
                        self.save_pw.set(True)
                        print("✓ 비밀번호 설정 완료")
                except Exception as e:
                    print(f"비밀번호 복호화 실패: {e}")

            # 프로필 드롭다운 업데이트
            self.update_profile_dropdown()

            # 현재 프로필 표시 업데이트
            if self.current_profile_label:
                self.current_profile_label.config(
                    text=f"현재 프로필: {profile_name}", foreground="#0066cc"
                )

            self.log_message(f"프로필 '{profile_name}'을 불러왔습니다.")

        except Exception as e:
            print(f"프로필 계정 정보 로드 오류: {e}")

    def load_legacy_account(self):
        """기존 방식으로 계정 정보 로드 (하위 호환성)"""
        try:
            print("\n기존 방식으로 계정 정보 로드 시도...")

            saved_id = self.config.get("account", "naver_id", "")
            save_id_flag = self.config.get("account", "save_id", False)
            encrypted_pw = self.config.get("account", "naver_pw", "")
            save_pw_flag = self.config.get("account", "save_pw", False)

            if saved_id and save_id_flag and self.naver_id_entry:
                self.naver_id_entry.delete(0, tk.END)
                self.naver_id_entry.insert(0, saved_id)
                self.save_id.set(True)
                self.log_message(f"저장된 네이버 아이디를 불러왔습니다: {saved_id}")

            if encrypted_pw and save_pw_flag and self.naver_pw_entry:
                try:
                    decrypted_pw = self.security_manager.decrypt_password(encrypted_pw)
                    if decrypted_pw:
                        self.naver_pw_entry.delete(0, tk.END)
                        self.naver_pw_entry.insert(0, decrypted_pw)
                        self.save_pw.set(True)
                        self.log_message("저장된 네이버 비밀번호를 불러왔습니다.")
                except Exception as e:
                    print(f"비밀번호 복호화 실패: {e}")

        except Exception as e:
            print(f"기존 계정 정보 로드 오류: {e}")

    def update_profile_dropdown(self):
        """프로필 드롭다운 업데이트"""
        if not self.profile_dropdown:
            return

        try:
            profiles = self.config.get_profile_names()
            current_profile = self.config.get_current_profile_name()

            # 프로필 목록 업데이트
            self.profile_dropdown["values"] = profiles

            # 현재 프로필 선택
            if current_profile and current_profile in profiles:
                self.profile_dropdown.set(current_profile)
            elif profiles:
                self.profile_dropdown.set("프로필 선택...")
            else:
                self.profile_dropdown.set("프로필 없음")

        except Exception as e:
            print(f"프로필 드롭다운 업데이트 오류: {e}")

    def on_profile_selected(self, event=None):
        """프로필 선택 이벤트 처리"""
        try:
            selected_profile = self.profile_dropdown.get()

            if selected_profile and selected_profile not in [
                "프로필 선택...",
                "프로필 없음",
            ]:
                # 프로필 변경
                self.config.set_current_profile(selected_profile)

                # 계정 정보 로드
                self.load_profile_account(selected_profile)

                self.log_message(f"프로필 '{selected_profile}'로 전환했습니다.")

        except Exception as e:
            print(f"프로필 선택 오류: {e}")
            messagebox.showerror("오류", f"프로필 전환 실패: {e}")

    def open_profile_manager(self):
        """프로필 관리자 열기"""
        dialog = ProfileManagerDialog(
            self.root,
            self.config,
            self.security_manager,
            on_profile_change=self.on_profile_changed_from_manager,
        )

    def on_profile_changed_from_manager(self, profile_name: str):
        """프로필 관리자에서 프로필이 변경되었을 때"""
        try:
            # 계정 정보 로드
            self.load_profile_account(profile_name)

            # 드롭다운 업데이트
            self.update_profile_dropdown()

        except Exception as e:
            print(f"프로필 변경 처리 오류: {e}")

    def save_account_info(self):
        """계정 정보 저장 - 프로필 기능 통합"""
        try:
            print("\n" + "=" * 60)
            print("계정 정보 저장 시작")
            print("=" * 60)

            # 현재 입력된 값 가져오기
            user_id = self.naver_id_entry.get().strip()
            password = self.naver_pw_entry.get().strip()
            save_id_checked = self.save_id.get()
            save_pw_checked = self.save_pw.get()

            if not user_id:
                messagebox.showerror("오류", "네이버 아이디를 입력해주세요.")
                return

            # 현재 프로필 확인
            current_profile = self.config.get_current_profile_name()

            if not current_profile:
                # 프로필이 없으면 새로 생성
                result = messagebox.askyesno(
                    "프로필 생성",
                    "저장된 프로필이 없습니다.\n새 프로필을 생성하시겠습니까?",
                )

                if result:
                    # 프로필 이름 입력
                    profile_name = tk.simpledialog.askstring(
                        "프로필 이름", "프로필 이름을 입력하세요:", initialvalue=user_id
                    )

                    if profile_name:
                        current_profile = profile_name
                    else:
                        return
                else:
                    return

            # 비밀번호 암호화
            encrypted_pw = ""
            if save_pw_checked and password:
                encrypted_pw = self.security_manager.encrypt_password(password)

            # 프로필에 저장
            self.config.save_profile(
                current_profile, user_id, encrypted_pw, save_pw_checked
            )

            # 드롭다운 업데이트
            self.update_profile_dropdown()

            messagebox.showinfo(
                "저장 완료", f"프로필 '{current_profile}'에 계정 정보가 저장되었습니다."
            )
            self.log_message(
                f"프로필 '{current_profile}'에 계정 정보가 저장되었습니다."
            )

            print("=" * 60)
            print("계정 정보 저장 완료")
            print("=" * 60 + "\n")

        except Exception as e:
            error_msg = f"계정 정보 저장 실패: {e}"
            print(f"✗ {error_msg}")
            import traceback

            traceback.print_exc()
            messagebox.showerror("저장 실패", error_msg)

    def load_other_settings(self):
        """다른 설정들 불러오기"""
        try:
            # 자동화 설정
            if hasattr(self, "delay_min"):
                automation_settings = {
                    "delay_min": (self.delay_min, 30),
                    "delay_max": (self.delay_max, 60),
                    "daily_limit": (self.daily_limit, 20),
                    "min_stay_time": (self.min_stay, 60),
                    "max_stay_time": (self.max_stay, 180),
                    "retry_count": (self.retry_count, 3),
                }

                for key, (widget, default) in automation_settings.items():
                    value = self.config.get("automation", key, default)
                    try:
                        widget.set(str(value))
                    except:
                        widget.set(str(default))

            # 콤보박스 설정
            if hasattr(self, "comment_style"):
                self.comment_style.set(
                    self.config.get("automation", "comment_style", "친근함")
                )
            if hasattr(self, "scroll_speed"):
                self.scroll_speed.set(
                    self.config.get("automation", "scroll_speed", "보통")
                )
            if hasattr(self, "log_level"):
                self.log_level.set(self.config.get("logging", "level", "기본"))

            # 체크박스 설정
            if hasattr(self, "auto_like"):
                self.auto_like.set(self.config.get("automation", "auto_like", True))
            if hasattr(self, "auto_comment"):
                self.auto_comment.set(
                    self.config.get("automation", "auto_comment", True)
                )
            if hasattr(self, "headless_mode"):
                self.headless_mode.set(self.config.get("browser", "headless", False))
            if hasattr(self, "continue_on_error"):
                self.continue_on_error.set(
                    self.config.get("automation", "continue_on_error", True)
                )
            if hasattr(self, "auto_restart"):
                self.auto_restart.set(
                    self.config.get("automation", "auto_restart", False)
                )

        except Exception as e:
            print(f"다른 설정 불러오기 오류: {e}")

    def setup_gui(self):
        """GUI 구성"""
        # 메뉴바 생성
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 도움말 메뉴
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="도움말", menu=help_menu)
        help_menu.add_command(label="업데이트 확인", command=self.check_update)
        help_menu.add_separator()
        help_menu.add_command(label="정보", command=self.show_about)

        # 디버그 메뉴 추가
        debug_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="디버그", menu=debug_menu)
        debug_menu.add_command(
            label="설정 다시 불러오기", command=self.initial_load_settings
        )
        debug_menu.add_command(label="설정 파일 확인", command=self.debug_config_file)

        # 스타일 설정
        style = ttk.Style()
        style.theme_use("clam")

        # 스크롤바를 위한 캔버스와 프레임 생성
        main_canvas = tk.Canvas(self.root)
        main_scrollbar = ttk.Scrollbar(
            self.root, orient="vertical", command=main_canvas.yview
        )
        scrollable_frame = ttk.Frame(main_canvas)

        # 스크롤 가능한 프레임 설정
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")),
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=main_scrollbar.set)

        # 캔버스와 스크롤바 배치
        main_canvas.pack(side="left", fill="both", expand=True)
        main_scrollbar.pack(side="right", fill="y")

        # 마우스 휠 바인딩
        def _on_mousewheel(event):
            main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 메인 프레임 (스크롤 가능한 프레임 안에)
        main_frame = ttk.Frame(scrollable_frame, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 제목
        title_label = ttk.Label(
            main_frame, text="네이버 블로그 자동 이웃관리", font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        # 각 섹션 구성
        self._setup_license_section(main_frame)
        self._setup_account_section(main_frame)
        self._setup_control_section(main_frame)
        self._setup_automation_section(main_frame)
        self._setup_log_section(main_frame)

        # 초기 상태 설정
        self.set_gui_state(False)

    def debug_config_file(self):
        """설정 파일 디버그"""
        try:
            config_path = os.path.abspath(self.config.config_file)
            print(f"\n디버그: Config 파일 경로 = {config_path}")

            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)

                debug_info = f"Config 파일 내용:\n{json.dumps(config_data, indent=2, ensure_ascii=False)}"
                print(debug_info)

                # 디버그 창 표시
                debug_window = tk.Toplevel(self.root)
                debug_window.title("Config 파일 디버그")
                debug_window.geometry("600x400")

                text_widget = scrolledtext.ScrolledText(debug_window, wrap=tk.WORD)
                text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                text_widget.insert(tk.END, debug_info)
                text_widget.config(state=tk.DISABLED)

            else:
                messagebox.showwarning(
                    "디버그", f"Config 파일이 존재하지 않습니다:\n{config_path}"
                )

        except Exception as e:
            messagebox.showerror("디버그 오류", str(e))

    def check_update(self):
        """업데이트 확인"""
        self.log_message("업데이트 확인 중...")
        update_dialog = UpdateDialog(self.root, self.updater)
        update_dialog.check_and_prompt()

    def show_about(self):
        """프로그램 정보"""
        messagebox.showinfo(
            "정보",
            "네이버 블로그 자동 이웃관리\n"
            f"버전: {self.updater.current_version}\n\n"
            "Copyright © 2024",
        )

    def _setup_license_section(self, parent):
        """라이선스 섹션 구성"""
        license_frame = ttk.LabelFrame(parent, text="라이선스 인증", padding="15")
        license_frame.pack(fill=tk.X, pady=(0, 15))

        # 라이선스 입력
        input_frame = ttk.Frame(license_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(input_frame, text="라이선스 키:").pack(anchor=tk.W)

        entry_frame = ttk.Frame(input_frame)
        entry_frame.pack(fill=tk.X, pady=(5, 0))

        # 라이선스 입력창 생성 및 참조 저장
        self.license_entry = ttk.Entry(entry_frame, font=("Consolas", 10))
        self.license_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.verify_btn = ttk.Button(
            entry_frame, text="인증", command=self.verify_license
        )
        self.verify_btn.pack(side=tk.RIGHT)

        # 상태 표시
        self.license_status = ttk.Label(
            license_frame, text="라이선스를 입력하고 인증해주세요.", foreground="gray"
        )
        self.license_status.pack(anchor=tk.W, pady=(10, 0))

    def _setup_account_section(self, parent):
        """계정 섹션 구성 - 프로필 기능 추가"""
        account_frame = ttk.LabelFrame(parent, text="네이버 계정", padding="15")
        account_frame.pack(fill=tk.X, pady=(0, 15))

        # 프로필 관리 영역
        profile_frame = ttk.Frame(account_frame)
        profile_frame.pack(fill=tk.X, pady=(0, 15))

        # 프로필 선택 드롭다운
        ttk.Label(profile_frame, text="프로필:").pack(side=tk.LEFT, padx=(0, 10))

        self.profile_dropdown = ttk.Combobox(profile_frame, state="readonly", width=20)
        self.profile_dropdown.pack(side=tk.LEFT, padx=(0, 10))
        self.profile_dropdown.bind("<<ComboboxSelected>>", self.on_profile_selected)

        # 프로필 관리 버튼
        ttk.Button(
            profile_frame, text="프로필 관리", command=self.open_profile_manager
        ).pack(side=tk.LEFT)

        # 현재 프로필 표시
        self.current_profile_label = ttk.Label(
            account_frame,
            text="프로필을 선택하세요",
            font=("Arial", 9),
            foreground="gray",
        )
        self.current_profile_label.pack(anchor=tk.W, pady=(0, 10))

        # 구분선
        ttk.Separator(account_frame, orient="horizontal").pack(fill=tk.X, pady=10)

        # 계정 정보 입력 영역
        grid_frame = ttk.Frame(account_frame)
        grid_frame.pack(fill=tk.X)

        # 아이디
        ttk.Label(grid_frame, text="아이디:").grid(row=0, column=0, sticky=tk.W, pady=5)

        id_frame = ttk.Frame(grid_frame)
        id_frame.grid(row=0, column=1, padx=(10, 20), pady=5, sticky=tk.W + tk.E)
        id_frame.columnconfigure(0, weight=1)

        # 아이디 입력창 생성
        self.naver_id_entry = ttk.Entry(id_frame, width=25)
        self.naver_id_entry.grid(row=0, column=0, sticky=tk.W + tk.E, padx=(0, 5))

        # 아이디 저장 체크박스
        self.save_id = tk.BooleanVar(value=True)
        ttk.Checkbutton(id_frame, text="저장", variable=self.save_id).grid(
            row=0, column=1
        )

        # 비밀번호
        ttk.Label(grid_frame, text="비밀번호:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )

        pw_frame = ttk.Frame(grid_frame)
        pw_frame.grid(row=1, column=1, padx=(10, 20), pady=5, sticky=tk.W + tk.E)
        pw_frame.columnconfigure(0, weight=1)

        # 비밀번호 입력창 생성
        self.naver_pw_entry = ttk.Entry(pw_frame, width=25, show="*")
        self.naver_pw_entry.grid(row=0, column=0, sticky=tk.W + tk.E, padx=(0, 5))

        # 비밀번호 저장 체크박스
        self.save_pw = tk.BooleanVar(value=False)
        ttk.Checkbutton(pw_frame, text="저장", variable=self.save_pw).grid(
            row=0, column=1
        )

        # 버튼들
        button_frame = ttk.Frame(grid_frame)
        button_frame.grid(row=0, column=2, rowspan=2, padx=(20, 0), pady=5)

        # 로그인 테스트 버튼
        self.login_btn = ttk.Button(
            button_frame, text="로그인 테스트", command=self.test_naver_login
        )
        self.login_btn.pack(pady=(0, 5))

        # 계정 저장 버튼
        self.save_account_btn = ttk.Button(
            button_frame,
            text="계정 저장",
            command=self.save_account_info,
        )
        self.save_account_btn.pack()

        # 로그인 상태
        self.login_status = ttk.Label(account_frame, text="", font=("Arial", 9))
        self.login_status.pack(anchor=tk.W, pady=(10, 0))

        # 계정 정보 안내
        info_label = ttk.Label(
            account_frame,
            text="※ 비밀번호는 암호화되어 저장됩니다. 보안을 위해 저장하지 않는 것을 권장합니다.",
            font=("Arial", 8),
            foreground="gray",
        )
        info_label.pack(anchor=tk.W, pady=(5, 0))

    def _setup_control_section(self, parent):
        """실행 컨트롤 섹션"""
        control_frame = ttk.LabelFrame(parent, text="🎯 실행 컨트롤", padding="20")
        control_frame.pack(fill=tk.X, pady=(0, 15))

        # 메인 버튼 영역
        main_button_frame = ttk.Frame(control_frame)
        main_button_frame.pack(fill=tk.X, pady=(0, 15))

        # 이모지 텍스트
        emoji_texts = self._get_button_texts()

        # 시작/중지 버튼 프레임
        start_stop_frame = ttk.Frame(main_button_frame)
        start_stop_frame.pack(side=tk.LEFT)

        # 자동화 시작 버튼
        self.start_btn = ttk.Button(
            start_stop_frame,
            text=emoji_texts["start"],
            command=self.start_automation,
            width=20,
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 중지 버튼
        self.stop_btn = ttk.Button(
            start_stop_frame,
            text=emoji_texts["stop"],
            command=self.stop_automation,
            width=10,
            state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT)

        # 통계 표시
        stats_frame = ttk.Frame(main_button_frame)
        stats_frame.pack(side=tk.RIGHT, padx=(20, 0))

        self.stats_label = ttk.Label(
            stats_frame,
            text="오늘 처리: 0 / 0",
            font=("Arial", 14, "bold"),
            foreground="#0066cc",
        )
        self.stats_label.pack()

        # 상태 표시
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(status_frame, text="상태:", font=("Arial", 10, "bold")).pack(
            side=tk.LEFT
        )
        self.status_label = ttk.Label(
            status_frame, text="대기 중...", font=("Arial", 10), foreground="green"
        )
        self.status_label.pack(side=tk.LEFT, padx=(5, 0))

        # 진행률 바
        self.progress = ttk.Progressbar(control_frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(0, 15))

        # 테스트 버튼들
        test_frame = ttk.LabelFrame(control_frame, text="테스트 및 도구", padding="10")
        test_frame.pack(fill=tk.X)

        test_buttons = ttk.Frame(test_frame)
        test_buttons.pack(fill=tk.X)

        # 수동 로그인 버튼
        self.manual_login_btn = ttk.Button(
            test_buttons,
            text=emoji_texts["manual"],
            command=self.manual_login_mode,
            width=18,
        )
        self.manual_login_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 이웃글 확인 버튼
        self.test_btn = ttk.Button(
            test_buttons,
            text=emoji_texts["test"],
            command=self.test_neighbor_posts,
            width=18,
        )
        self.test_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 설정 저장 버튼
        self.save_settings_btn = ttk.Button(
            test_buttons,
            text=emoji_texts["save"],
            command=self.save_all_settings,
            width=15,
        )
        self.save_settings_btn.pack(side=tk.LEFT)

    def _setup_automation_section(self, parent):
        """자동화 설정 섹션"""
        auto_frame = ttk.LabelFrame(parent, text="자동화 설정", padding="15")
        auto_frame.pack(fill=tk.X, pady=(0, 15))

        # 탭 구성
        notebook = ttk.Notebook(auto_frame)
        notebook.pack(fill=tk.X)

        # 기본 설정 탭
        basic_tab = ttk.Frame(notebook)
        notebook.add(basic_tab, text="기본 설정")

        # 고급 설정 탭
        advanced_tab = ScrollableFrame(notebook)
        notebook.add(advanced_tab, text="고급 설정")

        # === 기본 설정 탭 ===
        basic_frame = ttk.Frame(basic_tab, padding="10")
        basic_frame.pack(fill=tk.X)

        # 브라우저 모드 설정
        browser_mode_frame = ttk.LabelFrame(
            basic_frame, text="브라우저 설정", padding="10"
        )
        browser_mode_frame.pack(fill=tk.X, pady=(0, 15))

        self.headless_mode = tk.BooleanVar(value=False)
        headless_check = ttk.Checkbutton(
            browser_mode_frame,
            text="헤드리스 모드 (백그라운드 실행 - 불안정할 수 있음)",
            variable=self.headless_mode,
            command=self._on_headless_mode_change,
        )
        headless_check.pack(anchor=tk.W)

        # 기본 설정들
        settings_grid = ttk.Frame(basic_frame)
        settings_grid.pack(fill=tk.X, pady=(0, 15))

        # 댓글 스타일
        ttk.Label(settings_grid, text="댓글 스타일:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10), pady=5
        )
        self.comment_style = ttk.Combobox(
            settings_grid,
            values=["친근함", "전문적", "캐주얼", "응원"],
            state="readonly",
            width=15,
        )
        self.comment_style.grid(row=0, column=1, sticky=tk.W, pady=5)
        self.comment_style.set("친근함")

        # 일일 한도
        ttk.Label(settings_grid, text="일일 댓글 한도:").grid(
            row=1, column=0, sticky=tk.W, padx=(0, 10), pady=5
        )
        limit_frame = ttk.Frame(settings_grid)
        limit_frame.grid(row=1, column=1, sticky=tk.W, pady=5)

        self.daily_limit = ttk.Spinbox(limit_frame, from_=1, to=50, width=10, value=20)
        self.daily_limit.pack(side=tk.LEFT)
        ttk.Label(limit_frame, text="개").pack(side=tk.LEFT, padx=(5, 0))

        # 자동 기능 체크박스
        check_frame = ttk.Frame(basic_frame)
        check_frame.pack(fill=tk.X, pady=(15, 0))

        self.auto_like = tk.BooleanVar(value=True)
        ttk.Checkbutton(check_frame, text="자동 좋아요", variable=self.auto_like).pack(
            side=tk.LEFT, padx=(0, 20)
        )

        self.auto_comment = tk.BooleanVar(value=True)
        ttk.Checkbutton(check_frame, text="자동 댓글", variable=self.auto_comment).pack(
            side=tk.LEFT
        )

        # === 고급 설정 탭 ===
        advanced_content = advanced_tab.scrollable_frame

        # 체류 시간 설정
        stay_frame = ttk.LabelFrame(
            advanced_content, text="체류 시간 설정", padding="10"
        )
        stay_frame.pack(fill=tk.X, pady=(10, 15))

        stay_grid = ttk.Frame(stay_frame)
        stay_grid.pack(fill=tk.X)

        ttk.Label(stay_grid, text="최소:").grid(row=0, column=0, sticky=tk.W)
        self.min_stay = ttk.Spinbox(stay_grid, from_=30, to=300, width=10, value=60)
        self.min_stay.grid(row=0, column=1, padx=(5, 5))
        ttk.Label(stay_grid, text="초").grid(row=0, column=2, sticky=tk.W)

        ttk.Label(stay_grid, text="최대:").grid(
            row=1, column=0, sticky=tk.W, pady=(5, 0)
        )
        self.max_stay = ttk.Spinbox(stay_grid, from_=60, to=600, width=10, value=180)
        self.max_stay.grid(row=1, column=1, padx=(5, 5), pady=(5, 0))
        ttk.Label(stay_grid, text="초").grid(row=1, column=2, sticky=tk.W, pady=(5, 0))

        # 스크롤 설정
        scroll_frame = ttk.LabelFrame(
            advanced_content, text="스크롤 설정", padding="10"
        )
        scroll_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(scroll_frame, text="스크롤 속도:").pack(side=tk.LEFT)
        self.scroll_speed = ttk.Combobox(
            scroll_frame,
            values=["느리게", "보통", "빠르게"],
            state="readonly",
            width=15,
        )
        self.scroll_speed.pack(side=tk.LEFT, padx=(10, 0))
        self.scroll_speed.set("보통")

        # 대기 시간 설정
        delay_frame = ttk.LabelFrame(
            advanced_content, text="포스트 간 대기 시간", padding="10"
        )
        delay_frame.pack(fill=tk.X, pady=(0, 15))

        delay_grid = ttk.Frame(delay_frame)
        delay_grid.pack(fill=tk.X)

        ttk.Label(delay_grid, text="최소:").grid(row=0, column=0, sticky=tk.W)
        self.delay_min = ttk.Spinbox(delay_grid, from_=10, to=300, width=10, value=30)
        self.delay_min.grid(row=0, column=1, padx=(5, 5))
        ttk.Label(delay_grid, text="초").grid(row=0, column=2, sticky=tk.W)

        ttk.Label(delay_grid, text="최대:").grid(
            row=1, column=0, sticky=tk.W, pady=(5, 0)
        )
        self.delay_max = ttk.Spinbox(delay_grid, from_=30, to=600, width=10, value=60)
        self.delay_max.grid(row=1, column=1, padx=(5, 5), pady=(5, 0))
        ttk.Label(delay_grid, text="초").grid(row=1, column=2, sticky=tk.W, pady=(5, 0))

        # 고급 옵션들
        advanced_options_frame = ttk.LabelFrame(
            advanced_content, text="고급 옵션", padding="10"
        )
        advanced_options_frame.pack(fill=tk.X, pady=(0, 15))

        # 재시도 설정
        retry_frame = ttk.Frame(advanced_options_frame)
        retry_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(retry_frame, text="로그인 재시도 횟수:").pack(side=tk.LEFT)
        self.retry_count = ttk.Spinbox(retry_frame, from_=1, to=5, width=10, value=3)
        self.retry_count.pack(side=tk.LEFT, padx=(10, 0))

        # 에러 처리 설정
        error_frame = ttk.Frame(advanced_options_frame)
        error_frame.pack(fill=tk.X, pady=(10, 0))

        self.continue_on_error = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            error_frame, text="에러 발생 시 계속 진행", variable=self.continue_on_error
        ).pack(anchor=tk.W)

        self.auto_restart = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            error_frame,
            text="자동 재시작 (브라우저 크래시 시)",
            variable=self.auto_restart,
        ).pack(anchor=tk.W, pady=(5, 0))

        # 로그 레벨 설정
        log_frame = ttk.LabelFrame(advanced_content, text="로그 설정", padding="10")
        log_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(log_frame, text="로그 레벨:").pack(side=tk.LEFT)
        self.log_level = ttk.Combobox(
            log_frame,
            values=["기본", "상세", "디버그"],
            state="readonly",
            width=15,
        )
        self.log_level.pack(side=tk.LEFT, padx=(10, 0))
        self.log_level.set("기본")

    def _setup_log_section(self, parent):
        """로그 섹션 구성"""
        log_frame = ttk.LabelFrame(parent, text="실행 로그", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=12, font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _get_button_texts(self):
        """이모지 지원 여부에 따른 버튼 텍스트 반환"""
        try:
            import sys

            if sys.platform == "win32":
                emoji_support = True
            else:
                emoji_support = True
        except:
            emoji_support = False

        if emoji_support:
            return {
                "start": "🚀 자동 이웃관리 시작",
                "stop": "⏹ 중지",
                "manual": "🔑 수동 로그인",
                "test": "🔍 이웃글 확인",
                "login_test": "✅ 로그인 테스트",
                "save": "💾 설정 저장",
            }
        else:
            return {
                "start": "▶ 자동 이웃관리 시작",
                "stop": "■ 중지",
                "manual": "※ 수동 로그인",
                "test": "※ 이웃글 확인",
                "login_test": "※ 로그인 테스트",
                "save": "※ 설정 저장",
            }

    def check_saved_license(self):
        """저장된 라이선스 확인"""
        try:
            license_key = self.config.get("license", "key", "")

            if license_key and license_key.strip():
                self.license_entry.delete(0, tk.END)
                self.license_entry.insert(0, license_key)
                self.log_message("저장된 라이선스를 불러왔습니다.")

                # 자동 인증
                self.root.after(1000, self.verify_license)

        except Exception as e:
            print(f"라이선스 확인 오류: {e}")

    def save_all_settings(self):
        """모든 설정 저장"""
        try:
            # 자동화 설정
            self.config.set("automation", "delay_min", int(self.delay_min.get()))
            self.config.set("automation", "delay_max", int(self.delay_max.get()))
            self.config.set("automation", "daily_limit", int(self.daily_limit.get()))
            self.config.set("automation", "comment_style", self.comment_style.get())
            self.config.set("automation", "min_stay_time", int(self.min_stay.get()))
            self.config.set("automation", "max_stay_time", int(self.max_stay.get()))
            self.config.set("automation", "scroll_speed", self.scroll_speed.get())
            self.config.set("automation", "auto_like", self.auto_like.get())
            self.config.set("automation", "auto_comment", self.auto_comment.get())
            self.config.set("automation", "retry_count", int(self.retry_count.get()))
            self.config.set(
                "automation", "continue_on_error", self.continue_on_error.get()
            )
            self.config.set("automation", "auto_restart", self.auto_restart.get())

            # 브라우저 설정
            self.config.set("browser", "headless", self.headless_mode.get())

            # 로그 설정
            self.config.set("logging", "level", self.log_level.get())

            self.config.save()
            self.log_message("💾 설정이 저장되었습니다.")
            messagebox.showinfo("저장 완료", "모든 설정이 저장되었습니다!")

        except Exception as e:
            error_msg = f"설정 저장 실패: {e}"
            self.log_message(error_msg)
            messagebox.showerror("저장 실패", error_msg)

    def _on_headless_mode_change(self):
        """헤드리스 모드 변경 시 처리"""
        if self.headless_mode.get():
            result = messagebox.askyesno(
                "헤드리스 모드 경고",
                "헤드리스 모드는 브라우저 창 없이 백그라운드에서 실행됩니다.\n"
                "네이버 보안 정책으로 인해 불안정할 수 있습니다.\n\n"
                "문제 발생 시 헤드리스 모드를 해제하고 다시 시도하세요.\n\n"
                "계속하시겠습니까?",
            )
            if not result:
                self.headless_mode.set(False)

        self.config.set("browser", "headless", self.headless_mode.get())
        self.config.save()

    def get_automation_settings(self) -> dict:
        """현재 자동화 설정 가져오기"""
        try:

            def safe_int(widget, default):
                try:
                    value = widget.get()
                    if value and value.strip():
                        return int(value)
                    return default
                except (ValueError, AttributeError):
                    return default

            settings = {
                "comment_style": self.comment_style.get() or "친근함",
                "delay_min": safe_int(self.delay_min, 30),
                "delay_max": safe_int(self.delay_max, 60),
                "daily_limit": safe_int(self.daily_limit, 20),
                "min_stay_time": safe_int(self.min_stay, 60),
                "max_stay_time": safe_int(self.max_stay, 180),
                "scroll_speed": self.scroll_speed.get() or "보통",
                "auto_like": (
                    self.auto_like.get() if hasattr(self, "auto_like") else True
                ),
                "auto_comment": (
                    self.auto_comment.get() if hasattr(self, "auto_comment") else True
                ),
                "headless": (
                    self.headless_mode.get()
                    if hasattr(self, "headless_mode")
                    else False
                ),
                "retry_count": safe_int(self.retry_count, 3),
                "continue_on_error": (
                    self.continue_on_error.get()
                    if hasattr(self, "continue_on_error")
                    else True
                ),
                "auto_restart": (
                    self.auto_restart.get() if hasattr(self, "auto_restart") else False
                ),
                "log_level": (
                    self.log_level.get() if hasattr(self, "log_level") else "기본"
                ),
            }

            return settings

        except Exception as e:
            print(f"설정 가져오기 오류: {e}")
            return {
                "comment_style": "친근함",
                "delay_min": 30,
                "delay_max": 60,
                "daily_limit": 20,
                "min_stay_time": 60,
                "max_stay_time": 180,
                "scroll_speed": "보통",
                "auto_like": True,
                "auto_comment": True,
                "headless": False,
                "retry_count": 3,
                "continue_on_error": True,
                "auto_restart": False,
                "log_level": "기본",
            }

    def log_message(self, message):
        """로그 메시지 출력"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()
        self.logger.info(message)

    def update_status(self, message):
        """상태 메시지 업데이트"""
        if hasattr(self, "status_label"):
            self.status_label.config(text=message)
        self.log_message(message)

    def update_stats(self):
        """통계 업데이트"""
        try:
            daily_limit = int(self.daily_limit.get())
            self.stats_label.config(
                text=f"오늘 처리: {self.today_count} / {daily_limit}"
            )
        except:
            self.stats_label.config(text=f"오늘 처리: {self.today_count} / 0")

    def set_gui_state(self, enabled):
        """GUI 활성화/비활성화"""
        state = tk.NORMAL if enabled else tk.DISABLED

        basic_widgets = [
            self.naver_id_entry,
            self.naver_pw_entry,
            self.login_btn,
            self.save_account_btn,
            self.comment_style,
            self.delay_min,
            self.delay_max,
            self.daily_limit,
            self.start_btn,
        ]

        for widget in basic_widgets:
            try:
                widget.config(state=state)
            except:
                pass

        test_buttons = [
            self.manual_login_btn,
            self.test_btn,
        ]

        test_state = tk.NORMAL if self.is_licensed else tk.DISABLED
        for button in test_buttons:
            try:
                button.config(state=test_state)
            except:
                pass

        try:
            self.save_settings_btn.config(state=tk.NORMAL)
        except:
            pass

    def verify_license(self):
        """라이선스 검증"""
        license_key = self.license_entry.get().strip()
        if not license_key:
            self.license_status.config(
                text="라이선스 키를 입력해주세요.", foreground="red"
            )
            return

        self.log_message("라이선스 검증 중...")
        self.verify_btn.config(state=tk.DISABLED, text="검증 중...")
        threading.Thread(
            target=self._verify_license_thread, args=(license_key,), daemon=True
        ).start()

    def _verify_license_thread(self, license_key):
        """라이선스 검증 스레드"""
        try:
            hardware_id = self.security_manager.get_hardware_id()
            success, result = self.license_manager.verify_license(
                license_key, hardware_id
            )
            self.root.after(
                0, self._handle_license_result, success, result, license_key
            )
        except Exception as e:
            self.root.after(
                0,
                self._handle_license_result,
                False,
                {"message": f"검증 중 오류: {e}"},
                license_key,
            )

    def _handle_license_result(self, success, result, license_key):
        """라이선스 검증 결과 처리"""
        self.verify_btn.config(state=tk.NORMAL, text="인증")

        if success:
            self.is_licensed = True
            expires_at = result.get("expires_at")
            if expires_at:
                days_left = (expires_at - datetime.now()).days
                expire_text = f"({days_left}일 남음)" if days_left > 0 else "(만료됨)"
            else:
                expire_text = "(무제한)"

            customer = result.get("customer_email", "Unknown")
            self.license_status.config(
                text=f"✓ 라이선스 인증 완료 {expire_text} - {customer}",
                foreground="green",
            )
            self.set_gui_state(True)
            self.log_message(f"라이선스 인증 성공: {customer}")
            self.config.set("license", "key", license_key)
            self.config.save()
        else:
            self.is_licensed = False
            message = result.get("message", "알 수 없는 오류")
            self.license_status.config(text=f"✗ {message}", foreground="red")
            self.set_gui_state(False)
            self.log_message(f"라이선스 인증 실패: {message}")

    def test_naver_login(self):
        """네이버 로그인 테스트"""
        if not self.is_licensed:
            messagebox.showerror("오류", "먼저 라이선스를 인증해주세요.")
            return

        user_id = self.naver_id_entry.get().strip()
        password = self.naver_pw_entry.get().strip()

        if not user_id or not password:
            messagebox.showerror("오류", "아이디와 비밀번호를 입력해주세요.")
            return

        self.login_status.config(text="로그인 테스트 중...", foreground="orange")
        self.update_status("로그인 테스트 중...")
        self.log_message("✅ 네이버 로그인 테스트 시작...")
        threading.Thread(
            target=self._test_login_thread, args=(user_id, password), daemon=True
        ).start()

    def _test_login_thread(self, user_id, password):
        """로그인 테스트 스레드"""
        try:
            test_automation = NaverBlogAutomation(headless=self.headless_mode.get())
            if test_automation.init_browser():
                success, message = test_automation.login_naver(user_id, password)
                test_automation.close()
                self.root.after(0, self._handle_login_result, success, message)
            else:
                self.root.after(
                    0, self._handle_login_result, False, "드라이버 설정 실패"
                )
        except Exception as e:
            self.root.after(
                0, self._handle_login_result, False, f"테스트 실패: {str(e)}"
            )

    def _handle_login_result(self, success, message):
        """로그인 결과 처리"""
        if success:
            self.login_status.config(text="✓ 로그인 테스트 성공", foreground="green")
            self.log_message("네이버 로그인 테스트 성공")
        else:
            self.login_status.config(text=f"✗ {message}", foreground="red")
            self.log_message(f"로그인 테스트 실패: {message}")

    def manual_login_mode(self):
        """수동 로그인 모드"""
        if not self.is_licensed:
            messagebox.showerror("오류", "먼저 라이선스를 인증해주세요.")
            return

        self.update_status("수동 로그인 모드 시작 중...")
        self.log_message("🔑 수동 로그인 모드를 시작합니다...")
        threading.Thread(target=self._manual_login_thread, daemon=True).start()

    def _manual_login_thread(self):
        """수동 로그인 스레드"""
        try:
            temp_automation = NaverBlogAutomation(headless=False)

            if temp_automation.init_browser():
                success, message = temp_automation.manual_login_wait()

                if success:
                    self.root.after(
                        0,
                        self.log_message,
                        "수동 로그인 성공! 이제 자동화를 시작할 수 있습니다.",
                    )
                    self.root.after(
                        0,
                        lambda: self.login_status.config(
                            text="✓ 수동 로그인 완료", foreground="green"
                        ),
                    )
                    self.manual_browser = temp_automation
                else:
                    self.root.after(0, self.log_message, f"수동 로그인 실패: {message}")
                    temp_automation.close()
            else:
                self.root.after(0, self.log_message, "브라우저 초기화 실패")

        except Exception as e:
            self.root.after(0, self.log_message, f"수동 로그인 중 오류: {str(e)}")

    def test_neighbor_posts(self):
        """이웃 새글 확인 테스트"""
        if not self.is_licensed:
            messagebox.showerror("오류", "먼저 라이선스를 인증해주세요.")
            return

        user_id = self.naver_id_entry.get().strip()
        password = self.naver_pw_entry.get().strip()

        if not user_id or not password:
            messagebox.showerror("오류", "네이버 계정 정보를 입력해주세요.")
            return

        self.update_status("이웃 새글 확인 중...")
        self.log_message("🔍 이웃 새글 확인 테스트 시작...")
        threading.Thread(
            target=self._test_neighbor_posts_thread,
            args=(user_id, password),
            daemon=True,
        ).start()

    def _test_neighbor_posts_thread(self, user_id, password):
        """이웃 새글 확인 테스트 스레드"""
        try:
            test_automation = NaverBlogAutomation(headless=self.headless_mode.get())

            if test_automation.init_browser():
                self.root.after(0, self.log_message, "네이버 로그인 중...")
                success, message = test_automation.login_naver(user_id, password)

                if success:
                    self.root.after(
                        0, self.log_message, "로그인 성공! 이웃 새글 확인 중..."
                    )
                    posts = test_automation.get_neighbor_new_posts()

                    self.root.after(
                        0, self.log_message, f"발견된 이웃 새글: {len(posts)}개"
                    )

                    for i, post in enumerate(posts[:5]):  # 처음 5개만 표시
                        self.root.after(
                            0,
                            self.log_message,
                            f"{i+1}. [{post['blogger']}] {post['title'][:50]}...",
                        )

                    if len(posts) > 5:
                        self.root.after(
                            0, self.log_message, f"... 외 {len(posts)-5}개 더"
                        )

                else:
                    self.root.after(0, self.log_message, f"로그인 실패: {message}")

                test_automation.close()
            else:
                self.root.after(0, self.log_message, "브라우저 초기화 실패")

        except Exception as e:
            self.root.after(0, self.log_message, f"이웃글 확인 테스트 실패: {str(e)}")

    def start_automation(self):
        """자동화 시작"""
        if not self.is_licensed:
            messagebox.showerror("오류", "먼저 라이선스를 인증해주세요.")
            return

        user_id = self.naver_id_entry.get().strip()
        password = self.naver_pw_entry.get().strip()

        if not user_id or not password:
            messagebox.showerror("오류", "네이버 계정 정보를 입력해주세요.")
            return

        # 설정값 검증
        try:
            min_delay = int(self.delay_min.get())
            max_delay = int(self.delay_max.get())
            if min_delay > max_delay:
                messagebox.showerror(
                    "오류", "최소 대기시간이 최대 대기시간보다 큽니다."
                )
                return
        except ValueError:
            messagebox.showerror("오류", "올바른 숫자를 입력해주세요.")
            return

        # 헤드리스 모드 확인
        if self.headless_mode.get():
            result = messagebox.askyesno(
                "헤드리스 모드 확인",
                "헤드리스 모드로 실행됩니다.\n"
                "브라우저 창이 보이지 않으며, 문제 발생 시 디버깅이 어려울 수 있습니다.\n\n"
                "계속하시겠습니까?",
            )
            if not result:
                return

        # UI 상태 변경
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress.start()
        self.today_count = 0
        self.update_stats()
        self.update_status("자동화 시작 중...")

        self.log_message(
            f"🚀 자동 이웃관리를 시작합니다... (헤드리스: {'ON' if self.headless_mode.get() else 'OFF'})"
        )

        self.automation_thread = threading.Thread(
            target=self._automation_thread, args=(user_id, password), daemon=True
        )
        self.automation_thread.start()

    def stop_automation(self):
        """자동화 중지"""
        self.is_running = False
        self.update_status("자동화 중지 요청 중...")
        self.log_message("⏹ 자동화 중지 요청...")

    def _reset_automation_ui(self):
        """자동화 UI 리셋"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress.stop()
        self.is_running = False
        self.update_status("대기 중...")
        self.log_message("자동화가 중지되었습니다.")

    def _automation_thread(self, user_id, password):
        """자동화 실행 스레드"""
        try:
            # 설정값 가져오기
            settings = self.get_automation_settings()

            # NaverBlogAutomation 인스턴스 생성
            self.automation = NaverBlogAutomation(
                headless=settings.get("headless", False)
            )

            # 브라우저 초기화
            if not self.automation.init_browser():
                self.root.after(0, self.log_message, "브라우저 초기화 실패")
                return

            # 로그인 재시도 로직
            retry_count = settings.get("retry_count", 3)
            login_success = False

            for attempt in range(retry_count):
                self.root.after(
                    0,
                    self.log_message,
                    f"네이버 로그인 시도 {attempt + 1}/{retry_count}...",
                )
                success, message = self.automation.login_naver(user_id, password)

                if success:
                    login_success = True
                    self.root.after(0, self.log_message, "로그인 성공!")
                    break
                else:
                    self.root.after(0, self.log_message, f"로그인 실패: {message}")
                    if attempt < retry_count - 1:
                        self.root.after(0, self.log_message, "5초 후 재시도...")
                        time.sleep(5)

            if not login_success:
                self.root.after(0, self.log_message, "모든 로그인 시도 실패")
                return

            consecutive_errors = 0
            max_consecutive_errors = 5

            # 메인 루프
            while self.is_running and self.today_count < settings["daily_limit"]:
                try:
                    self.root.after(0, self.log_message, "이웃 새글 확인 중...")
                    posts = self.automation.get_neighbor_new_posts()

                    if not posts:
                        self.root.after(
                            0,
                            self.log_message,
                            "새 글이 없습니다. 5분 후 다시 확인합니다.",
                        )
                        for _ in range(300):  # 5분
                            if not self.is_running:
                                break
                            time.sleep(1)
                        continue

                    self.root.after(
                        0, self.log_message, f"{len(posts)}개의 새 글을 발견했습니다."
                    )

                    # 포스트 처리
                    for post in posts:
                        if (
                            not self.is_running
                            or self.today_count >= settings["daily_limit"]
                        ):
                            break

                        # 중복 확인
                        if post["url"] in self.processed_posts:
                            continue

                        self.root.after(
                            0,
                            self.log_message,
                            f"포스트 처리 중: [{post['blogger']}] {post['title'][:30]}...",
                        )

                        # 포스트 처리
                        success, result = self.automation.process_post(post, settings)

                        if success:
                            self.processed_posts.add(post["url"])
                            self.today_count += 1
                            self.root.after(0, self.update_stats)
                            self.root.after(
                                0,
                                self.log_message,
                                f"✓ 댓글 작성 완료: {result[:50]}...",
                            )
                            self.stats.add_comment()
                            consecutive_errors = 0
                        else:
                            self.root.after(
                                0, self.log_message, f"✗ 댓글 작성 실패: {result}"
                            )
                            consecutive_errors += 1

                            # 연속 에러 체크
                            if consecutive_errors >= max_consecutive_errors:
                                if settings["auto_restart"]:
                                    self.root.after(
                                        0,
                                        self.log_message,
                                        f"연속 {max_consecutive_errors}회 에러 발생. 브라우저 재시작...",
                                    )
                                    self.automation.close()
                                    time.sleep(10)

                                    # 브라우저 재시작
                                    self.automation = NaverBlogAutomation(
                                        headless=settings["headless"]
                                    )
                                    if self.automation.init_browser():
                                        success, _ = self.automation.login_naver(
                                            user_id, password
                                        )
                                        if success:
                                            consecutive_errors = 0
                                            continue

                                if not settings["continue_on_error"]:
                                    self.root.after(
                                        0,
                                        self.log_message,
                                        f"연속 {max_consecutive_errors}회 에러로 자동화 중지",
                                    )
                                    break

                        # 대기
                        delay = random.uniform(
                            settings["delay_min"], settings["delay_max"]
                        )
                        self.root.after(
                            0,
                            self.log_message,
                            f"다음 포스트까지 {int(delay)}초 대기...",
                        )

                        for _ in range(int(delay)):
                            if not self.is_running:
                                break
                            time.sleep(1)

                    # 다음 확인까지 대기
                    if self.is_running and self.today_count < settings["daily_limit"]:
                        self.root.after(
                            0, self.log_message, "10분 후 새 글을 확인합니다."
                        )
                        for _ in range(600):  # 10분
                            if not self.is_running:
                                break
                            time.sleep(1)

                except Exception as e:
                    error_msg = f"오류 발생: {str(e)}"
                    self.root.after(0, self.log_message, error_msg)
                    consecutive_errors += 1

                    if settings["log_level"] == "디버그":
                        import traceback

                        self.root.after(
                            0,
                            self.log_message,
                            f"디버그 정보: {traceback.format_exc()}",
                        )

                    if (
                        consecutive_errors >= max_consecutive_errors
                        and not settings["continue_on_error"]
                    ):
                        break

                    time.sleep(60)

            if self.today_count >= settings["daily_limit"]:
                self.root.after(
                    0, self.log_message, f"일일 한도 {settings['daily_limit']}개 도달!"
                )

        except Exception as e:
            self.root.after(0, self.log_message, f"자동화 오류: {str(e)}")
            import traceback

            print(f"자동화 스레드 오류 상세:\n{traceback.format_exc()}")

        finally:
            if self.automation:
                self.automation.close()
            self.root.after(0, self._reset_automation_ui)

    def on_closing(self):
        """프로그램 종료 시 처리"""
        self.save_all_settings()
        self.is_running = False

        if self.automation:
            self.automation.close()
        if self.manual_browser:
            self.manual_browser.close()

        self.root.destroy()

    def run(self):
        """프로그램 실행"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


# 메인 실행
if __name__ == "__main__":
    # simpledialog import 추가 (save_account_info에서 사용)
    import tkinter.simpledialog as simpledialog

    tk.simpledialog = simpledialog

    app = BlogManagerApp()
    app.run()
