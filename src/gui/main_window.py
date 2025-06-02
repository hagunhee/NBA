import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
from datetime import datetime
import sys
import time
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Config
from core.license_manager import LicenseManager
from core.security import SecurityManager
from automation.naver_blog import NaverBlogAutomation
from automation.comment_generator_cached import CachedCommentGenerator
from utils.logger import Logger
from utils.statistics import Statistics


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("네이버 블로그 자동 이웃관리 v1.0")
        self.root.geometry("900x700")

        # 시스템 초기화
        self.config = Config()
        self.logger = Logger()
        self.stats = Statistics()
        self.license_manager = LicenseManager()
        self.security_manager = SecurityManager()

        self.automation = None
        self.automation_thread = None
        self.is_running = False

        # GUI 설정
        self.setup_ui()
        self.load_saved_settings()

        # 라이선스 확인
        self.check_license_on_startup()

    def setup_ui(self):
        """UI 구성"""
        # 메인 노트북 (탭)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # 각 탭 설정
        self.setup_license_tab()
        self.setup_account_tab()
        self.setup_automation_tab()
        self.setup_stats_tab()
        self.setup_log_tab()

        # 상태 바
        self.status_bar = ttk.Label(self.root, text="준비", relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_license_tab(self):
        """라이선스 탭"""
        license_frame = ttk.Frame(self.notebook)
        self.notebook.add(license_frame, text="라이선스")

        # 라이선스 입력
        ttk.Label(license_frame, text="라이선스 키:", font=("Arial", 10)).grid(
            row=0, column=0, padx=20, pady=20, sticky="e"
        )

        self.license_entry = ttk.Entry(license_frame, width=40)
        self.license_entry.grid(row=0, column=1, padx=10, pady=20)

        ttk.Button(license_frame, text="인증", command=self.verify_license).grid(
            row=0, column=2, padx=10, pady=20
        )

        # 라이선스 상태
        self.license_status_frame = ttk.LabelFrame(license_frame, text="라이선스 정보")
        self.license_status_frame.grid(
            row=1, column=0, columnspan=3, padx=20, pady=20, sticky="ew"
        )

        self.license_status_label = ttk.Label(
            self.license_status_frame,
            text="라이선스 상태: 미인증",
            font=("Arial", 12, "bold"),
            foreground="red",
        )
        self.license_status_label.pack(pady=10)

        self.license_expiry_label = ttk.Label(self.license_status_frame, text="")
        self.license_expiry_label.pack(pady=5)

    def setup_account_tab(self):
        """계정 설정 탭"""
        account_frame = ttk.Frame(self.notebook)
        self.notebook.add(account_frame, text="계정 설정")

        # 네이버 계정
        naver_frame = ttk.LabelFrame(account_frame, text="네이버 계정")
        naver_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

        ttk.Label(naver_frame, text="아이디:").grid(
            row=0, column=0, padx=10, pady=10, sticky="e"
        )
        self.naver_id_entry = ttk.Entry(naver_frame, width=30)
        self.naver_id_entry.grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(naver_frame, text="비밀번호:").grid(
            row=1, column=0, padx=10, pady=10, sticky="e"
        )
        self.naver_pw_entry = ttk.Entry(naver_frame, width=30, show="*")
        self.naver_pw_entry.grid(row=1, column=1, padx=10, pady=10)

        # Claude API
        api_frame = ttk.LabelFrame(account_frame, text="Claude API")
        api_frame.grid(row=1, column=0, padx=20, pady=20, sticky="ew")

        ttk.Label(api_frame, text="API 키:").grid(
            row=0, column=0, padx=10, pady=10, sticky="e"
        )
        self.claude_key_entry = ttk.Entry(api_frame, width=40, show="*")
        self.claude_key_entry.grid(row=0, column=1, padx=10, pady=10)

        # 저장 버튼
        ttk.Button(
            account_frame, text="계정 정보 저장", command=self.save_credentials
        ).grid(row=2, column=0, pady=20)

    def setup_automation_tab(self):
        """자동화 설정 탭"""
        automation_frame = ttk.Frame(self.notebook)
        self.notebook.add(automation_frame, text="자동화 설정")

        # 스크롤 가능한 프레임
        canvas = tk.Canvas(automation_frame)
        scrollbar = ttk.Scrollbar(
            automation_frame, orient="vertical", command=canvas.yview
        )
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 기본 설정
        basic_frame = ttk.LabelFrame(scrollable_frame, text="기본 설정")
        basic_frame.grid(row=0, column=0, padx=20, pady=10, sticky="ew")

        self.auto_comment_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            basic_frame, text="자동 댓글 작성", variable=self.auto_comment_var
        ).grid(row=0, column=0, padx=10, pady=5, sticky="w")

        ttk.Label(basic_frame, text="일일 최대 댓글 수:").grid(
            row=1, column=0, padx=10, pady=5, sticky="e"
        )
        self.daily_limit_spinbox = ttk.Spinbox(basic_frame, from_=1, to=50, width=10)
        self.daily_limit_spinbox.set(20)
        self.daily_limit_spinbox.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        # 체류시간 설정
        stay_frame = ttk.LabelFrame(scrollable_frame, text="체류시간 설정")
        stay_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        ttk.Label(stay_frame, text="최소 체류시간 (초):").grid(
            row=0, column=0, padx=10, pady=5, sticky="e"
        )
        self.min_stay_spinbox = ttk.Spinbox(stay_frame, from_=30, to=300, width=10)
        self.min_stay_spinbox.set(60)
        self.min_stay_spinbox.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        ttk.Label(stay_frame, text="최대 체류시간 (초):").grid(
            row=1, column=0, padx=10, pady=5, sticky="e"
        )
        self.max_stay_spinbox = ttk.Spinbox(stay_frame, from_=60, to=600, width=10)
        self.max_stay_spinbox.set(180)
        self.max_stay_spinbox.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        # 스크롤 설정
        scroll_frame = ttk.LabelFrame(scrollable_frame, text="스크롤 설정")
        scroll_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        ttk.Label(scroll_frame, text="스크롤 속도:").grid(
            row=0, column=0, padx=10, pady=5, sticky="e"
        )
        self.scroll_speed_var = tk.StringVar(value="보통")
        scroll_speed_combo = ttk.Combobox(
            scroll_frame,
            textvariable=self.scroll_speed_var,
            values=["느리게", "보통", "빠르게"],
            width=10,
            state="readonly",
        )
        scroll_speed_combo.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        self.natural_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            scroll_frame,
            text="자연스러운 스크롤 패턴",
            variable=self.natural_scroll_var,
        ).grid(row=1, column=0, columnspan=2, padx=10, pady=5)

        # 딜레이 설정
        delay_frame = ttk.LabelFrame(scrollable_frame, text="페이지 전환 딜레이")
        delay_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        ttk.Label(delay_frame, text="최소 딜레이 (초):").grid(
            row=0, column=0, padx=10, pady=5, sticky="e"
        )
        self.min_delay_spinbox = ttk.Spinbox(delay_frame, from_=5, to=30, width=10)
        self.min_delay_spinbox.set(10)
        self.min_delay_spinbox.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        ttk.Label(delay_frame, text="최대 딜레이 (초):").grid(
            row=1, column=0, padx=10, pady=5, sticky="e"
        )
        self.max_delay_spinbox = ttk.Spinbox(delay_frame, from_=10, to=60, width=10)
        self.max_delay_spinbox.set(30)
        self.max_delay_spinbox.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        # 시작/중지 버튼
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.grid(row=4, column=0, pady=20)

        self.start_button = ttk.Button(
            button_frame, text="자동화 시작", command=self.start_automation
        )
        self.start_button.pack(side=tk.LEFT, padx=10)

        self.stop_button = ttk.Button(
            button_frame, text="중지", command=self.stop_automation, state="disabled"
        )
        self.stop_button.pack(side=tk.LEFT, padx=10)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def setup_stats_tab(self):
        """통계 탭"""
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="통계")

        # 오늘 통계
        today_frame = ttk.LabelFrame(stats_frame, text="오늘 활동")
        today_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

        self.today_visits_label = ttk.Label(today_frame, text="방문: 0")
        self.today_visits_label.grid(row=0, column=0, padx=20, pady=10)

        self.today_comments_label = ttk.Label(today_frame, text="댓글: 0")
        self.today_comments_label.grid(row=0, column=1, padx=20, pady=10)

        # 전체 통계
        total_frame = ttk.LabelFrame(stats_frame, text="전체 통계")
        total_frame.grid(row=1, column=0, padx=20, pady=20, sticky="ew")

        self.total_visits_label = ttk.Label(total_frame, text="총 방문: 0")
        self.total_visits_label.grid(row=0, column=0, padx=20, pady=10)

        self.total_comments_label = ttk.Label(total_frame, text="총 댓글: 0")
        self.total_comments_label.grid(row=0, column=1, padx=20, pady=10)

        # 캐시 통계
        cache_frame = ttk.LabelFrame(stats_frame, text="캐시 통계")
        cache_frame.grid(row=2, column=0, padx=20, pady=20, sticky="ew")

        self.cache_hit_label = ttk.Label(cache_frame, text="캐시 히트율: 0%")
        self.cache_hit_label.grid(row=0, column=0, padx=20, pady=10)

        self.tokens_saved_label = ttk.Label(cache_frame, text="절약된 토큰: 0")
        self.tokens_saved_label.grid(row=0, column=1, padx=20, pady=10)

        # 새로고침 버튼
        ttk.Button(stats_frame, text="통계 새로고침", command=self.refresh_stats).grid(
            row=3, column=0, pady=20
        )

    def setup_log_tab(self):
        """로그 탭"""
        log_frame = ttk.Frame(self.notebook)
        self.notebook.add(log_frame, text="활동 로그")

        # 로그 텍스트 영역
        self.log_text = tk.Text(log_frame, height=20, width=80)
        self.log_text.pack(side=tk.LEFT, fill="both", expand=True, padx=10, pady=10)

        # 스크롤바
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

    def verify_license(self):
        """라이선스 검증"""
        license_key = self.license_entry.get().strip()
        if not license_key:
            messagebox.showerror("오류", "라이선스 키를 입력해주세요.")
            return

        hardware_id = self.security_manager.get_hardware_id()
        valid, result = self.license_manager.verify_license(license_key, hardware_id)

        if valid:
            self.license_status_label.config(
                text="라이선스 상태: 인증됨", foreground="green"
            )
            expiry_date = result.get("expires_at", datetime.now())
            self.license_expiry_label.config(
                text=f"만료일: {expiry_date.strftime('%Y-%m-%d')}"
            )

            # 라이선스 키 저장
            self.config.set("license", "key", license_key)
            self.config.save()

            messagebox.showinfo("성공", "라이선스가 인증되었습니다.")
            self.log_message("라이선스 인증 성공", "INFO")
        else:
            self.license_status_label.config(
                text="라이선스 상태: 미인증", foreground="red"
            )
            messagebox.showerror("오류", f"라이선스 인증 실패: {result}")
            self.log_message(f"라이선스 인증 실패: {result}", "ERROR")

    def save_credentials(self):
        """계정 정보 저장"""
        naver_id = self.naver_id_entry.get().strip()
        naver_pw = self.naver_pw_entry.get().strip()
        claude_key = self.claude_key_entry.get().strip()

        if not all([naver_id, naver_pw, claude_key]):
            messagebox.showerror("오류", "모든 필드를 입력해주세요.")
            return

        # 안전하게 저장
        self.security_manager.store_credentials(naver_id, naver_pw, claude_key)

        # 설정에도 저장 (ID만)
        self.config.set("account", "naver_id", naver_id)
        self.config.save()

        messagebox.showinfo("성공", "계정 정보가 안전하게 저장되었습니다.")
        self.log_message("계정 정보 저장 완료", "INFO")

    def start_automation(self):
        """자동화 시작"""
        # 라이선스 확인
        if not self.check_license():
            return

        # 설정값 검증
        if not self.validate_settings():
            return

        self.is_running = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_bar.config(text="자동화 실행 중...")

        # 별도 스레드에서 실행
        self.automation_thread = threading.Thread(target=self.run_automation)
        self.automation_thread.daemon = True
        self.automation_thread.start()

        self.log_message("자동화 시작", "INFO")

    def stop_automation(self):
        """자동화 중지"""
        self.is_running = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_bar.config(text="중지됨")

        self.log_message("자동화 중지", "INFO")

    def run_automation(self):
        """자동화 실행 (별도 스레드)"""
        try:
            # 자동화 객체 생성
            automation = NaverBlogAutomation()

            # 브라우저 초기화
            if not automation.init_browser():
                self.log_message("브라우저 초기화 실패", "ERROR")
                return

            # 설정 수집
            settings = {
                "auto_comment": self.auto_comment_var.get(),
                "daily_limit": int(self.daily_limit_spinbox.get()),
                "min_stay": int(self.min_stay_spinbox.get()),
                "max_stay": int(self.max_stay_spinbox.get()),
                "scroll_speed": self.scroll_speed_var.get(),
                "natural_scroll": self.natural_scroll_var.get(),
                "min_delay": int(self.min_delay_spinbox.get()),
                "max_delay": int(self.max_delay_spinbox.get()),
            }

            # 계정 정보 가져오기
            naver_id = self.config.get("account", "naver_id")
            naver_pw, claude_key = self.security_manager.get_credentials(naver_id)

            if not all([naver_id, naver_pw]):
                self.log_message("계정 정보가 없습니다", "ERROR")
                return

            # 로그인
            self.log_message("네이버 로그인 중...", "INFO")
            if not automation.login_naver(naver_id, naver_pw):
                self.log_message("로그인 실패", "ERROR")
                return

            self.log_message("로그인 성공", "INFO")

            # 메인 루프
            daily_count = 0
            while self.is_running and daily_count < settings["daily_limit"]:
                try:
                    # 이웃 포스트 가져오기
                    posts = automation.get_neighbor_posts()

                    if not posts:
                        self.log_message("새 포스트가 없습니다. 대기 중...", "INFO")
                        time.sleep(300)  # 5분 대기
                        continue

                    for post in posts:
                        if (
                            not self.is_running
                            or daily_count >= settings["daily_limit"]
                        ):
                            break

                        # 포스트 처리
                        success = automation.process_post(post["url"], settings)

                        if success:
                            daily_count += 1
                            self.stats.add_comment()
                            self.log_message(
                                f"댓글 작성 완료 ({daily_count}/{settings['daily_limit']})",
                                "INFO",
                            )

                        # 딜레이
                        delay = random.uniform(
                            settings["min_delay"], settings["max_delay"]
                        )
                        self.log_message(f"{int(delay)}초 대기 중...", "DEBUG")
                        time.sleep(delay)

                except Exception as e:
                    self.log_message(f"오류 발생: {str(e)}", "ERROR")
                    time.sleep(60)

            self.log_message("일일 한도 도달 또는 중지됨", "INFO")

        except Exception as e:
            self.log_message(f"자동화 오류: {str(e)}", "ERROR")
        finally:
            if automation:
                automation.close_browser()
            self.stop_automation()

    def validate_settings(self):
        """설정값 검증"""
        try:
            min_stay = int(self.min_stay_spinbox.get())
            max_stay = int(self.max_stay_spinbox.get())
            min_delay = int(self.min_delay_spinbox.get())
            max_delay = int(self.max_delay_spinbox.get())

            if min_stay > max_stay:
                messagebox.showerror(
                    "오류", "최소 체류시간이 최대 체류시간보다 큽니다."
                )
                return False

            if min_delay > max_delay:
                messagebox.showerror("오류", "최소 딜레이가 최대 딜레이보다 큽니다.")
                return False

            return True

        except ValueError:
            messagebox.showerror("오류", "올바른 숫자를 입력해주세요.")
            return False

    def check_license(self):
        """라이선스 유효성 확인"""
        license_key = self.config.get("license", "key")
        if not license_key:
            messagebox.showerror("오류", "라이선스를 먼저 인증해주세요.")
            return False

        hardware_id = self.security_manager.get_hardware_id()
        valid, _ = self.license_manager.verify_license(license_key, hardware_id)

        if not valid:
            messagebox.showerror("오류", "라이선스가 유효하지 않습니다.")
            return False

        return True

    def check_license_on_startup(self):
        """시작 시 라이선스 확인"""
        license_key = self.config.get("license", "key")
        if license_key:
            self.license_entry.insert(0, license_key)
            self.verify_license()

    def load_saved_settings(self):
        """저장된 설정 불러오기"""
        # 자동화 설정
        automation_config = self.config.get_section("automation")
        if automation_config:
            self.min_stay_spinbox.set(automation_config.get("min_stay_time", 60))
            self.max_stay_spinbox.set(automation_config.get("max_stay_time", 180))
            self.min_delay_spinbox.set(automation_config.get("min_delay", 10))
            self.max_delay_spinbox.set(automation_config.get("max_delay", 30))
            self.daily_limit_spinbox.set(automation_config.get("daily_limit", 20))
            self.scroll_speed_var.set(automation_config.get("scroll_speed", "보통"))

        # 계정 정보
        naver_id = self.config.get("account", "naver_id")
        if naver_id:
            self.naver_id_entry.insert(0, naver_id)

    def refresh_stats(self):
        """통계 새로고침"""
        stats_data = self.stats.get_stats()

        # 오늘 통계
        today_stats = stats_data.get("today", {})
        self.today_visits_label.config(text=f"방문: {today_stats.get('visits', 0)}")
        self.today_comments_label.config(text=f"댓글: {today_stats.get('comments', 0)}")

        # 전체 통계
        self.total_visits_label.config(
            text=f"총 방문: {stats_data.get('total_visits', 0)}"
        )
        self.total_comments_label.config(
            text=f"총 댓글: {stats_data.get('total_comments', 0)}"
        )

        # 캐시 통계 (comment generator에서 가져오기)
        if hasattr(self, "comment_generator") and self.comment_generator:
            cache_stats = self.comment_generator.get_stats()
            self.cache_hit_label.config(
                text=f"캐시 히트율: {cache_stats.get('cache_hit_rate', '0%')}"
            )
            self.tokens_saved_label.config(
                text=f"절약된 토큰: {cache_stats.get('estimated_tokens_saved', 0)}"
            )

    def log_message(self, message, level="INFO"):
        """로그 메시지 추가"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"

        # 로그 텍스트에 추가
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)

        # 파일 로깅
        self.logger.log(message, level)

    def run(self):
        """GUI 실행"""
        self.root.mainloop()
