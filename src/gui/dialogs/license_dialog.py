"""
추가 다이얼로그들
"""

# === 라이선스 다이얼로그 ===
# 파일 위치: src/gui/dialogs/license_dialog.py

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional


class LicenseDialog:
    """라이선스 관리 다이얼로그"""

    def __init__(self, parent, context, license_service):
        self.context = context
        self.license_service = license_service

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("라이선스 관리")
        self.dialog.geometry("550x350")
        self.dialog.resizable(False, False)

        # 중앙 배치
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._setup_ui()
        self.dialog.focus_set()

    def _setup_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 현재 상태
        status_frame = ttk.LabelFrame(
            main_frame, text="현재 라이선스 상태", padding="15"
        )
        status_frame.pack(fill=tk.X, pady=(0, 20))

        if self.context.is_licensed:
            status_text = "✓ 라이선스가 인증되었습니다."
            status_color = "green"
        else:
            status_text = "✗ 라이선스 인증이 필요합니다."
            status_color = "red"

        ttk.Label(
            status_frame,
            text=status_text,
            font=("Arial", 11, "bold"),
            foreground=status_color,
        ).pack(anchor=tk.W)

        # 하드웨어 ID 표시
        hw_id = self.context.security_manager.get_hardware_id()
        ttk.Label(
            status_frame,
            text=f"하드웨어 ID: {hw_id[:16]}...",
            font=("Arial", 9),
            foreground="gray",
        ).pack(anchor=tk.W, pady=(10, 0))

        # 라이선스 키 입력
        key_frame = ttk.LabelFrame(main_frame, text="라이선스 키", padding="15")
        key_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(key_frame, text="라이선스 키를 입력하세요:").pack(
            anchor=tk.W, pady=(0, 10)
        )

        self.license_entry = ttk.Entry(key_frame, width=60, font=("Consolas", 10))
        self.license_entry.pack(fill=tk.X)

        # 저장된 키 불러오기
        saved_key = self.context.config.get("license", "key", "")
        if saved_key:
            self.license_entry.insert(0, saved_key)

        # 버튼들
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(
            button_frame, text="인증", command=self._verify_license, width=15
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            button_frame, text="취소", command=self.dialog.destroy, width=15
        ).pack(side=tk.LEFT)

        # 도움말
        help_text = (
            "※ 라이선스 키는 이메일로 전달받으신 키를 입력하세요.\n"
            "※ 한 번 인증된 라이선스는 해당 컴퓨터에서만 사용 가능합니다."
        )

        ttk.Label(
            main_frame, text=help_text, font=("Arial", 9), foreground="gray"
        ).pack(anchor=tk.W, pady=(20, 0))

    def _verify_license(self):
        """라이선스 인증"""
        key = self.license_entry.get().strip()

        if not key:
            messagebox.showerror("오류", "라이선스 키를 입력하세요.")
            self.license_entry.focus_set()
            return

        # 진행 표시
        progress = ttk.Progressbar(self.dialog, mode="indeterminate", length=200)
        progress.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        progress.start()

        self.dialog.update()

        try:
            # 라이선스 검증
            hardware_id = self.context.security_manager.get_hardware_id()
            success, result = self.context.license_manager.verify_license(
                key, hardware_id
            )

            progress.stop()
            progress.destroy()

            if success:
                self.context.is_licensed = True
                self.context.config.set("license", "key", key)
                self.context.config.save()

                messagebox.showinfo("성공", "라이선스 인증에 성공했습니다!")
                self.dialog.destroy()
            else:
                messagebox.showerror(
                    "인증 실패",
                    f"라이선스 인증에 실패했습니다.\n\n{result.get('message', '알 수 없는 오류')}",
                )

        except Exception as e:
            progress.stop()
            progress.destroy()
            messagebox.showerror("오류", f"인증 중 오류 발생: {str(e)}")


# === 도움말 다이얼로그 ===
# 파일 위치: src/gui/dialogs/help_dialog.py


class HelpDialog:
    """도움말 다이얼로그"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("도움말")
        self.dialog.geometry("700x600")

        # 중앙 배치
        self.dialog.transient(parent)

        self._setup_ui()

    def _setup_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 제목
        ttk.Label(
            main_frame, text="네이버 블로그 자동화 사용법", font=("Arial", 14, "bold")
        ).pack(anchor=tk.W, pady=(0, 20))

        # 내용 (탭)
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # 시작하기 탭
        self._create_getting_started_tab(notebook)

        # 작업 관리 탭
        self._create_task_management_tab(notebook)

        # 프로필 관리 탭
        self._create_profile_management_tab(notebook)

        # 팁과 트릭 탭
        self._create_tips_tab(notebook)

        # 닫기 버튼
        ttk.Button(main_frame, text="닫기", command=self.dialog.destroy).pack(
            pady=(20, 0)
        )

    def _create_getting_started_tab(self, notebook):
        """시작하기 탭"""
        frame = ttk.Frame(notebook, padding="20")
        notebook.add(frame, text="시작하기")

        content = """
1. 라이선스 인증
   • 프로그램을 처음 실행하면 라이선스 인증이 필요합니다.
   • 구매 시 받은 라이선스 키를 입력하세요.
   • 한 번 인증하면 해당 컴퓨터에서 계속 사용할 수 있습니다.

2. 프로필 설정
   • '프로필 관리'에서 네이버 계정을 등록하세요.
   • 여러 계정을 등록하고 전환하며 사용할 수 있습니다.
   • 비밀번호는 암호화되어 안전하게 저장됩니다.

3. 작업 구성
   • 왼쪽 작업 목록에서 원하는 작업을 더블클릭하여 추가합니다.
   • 추가된 작업은 오른쪽 스케줄러에 표시됩니다.
   • 작업 순서는 드래그 또는 화살표 버튼으로 조정할 수 있습니다.

4. 실행
   • 모든 작업을 구성한 후 '실행' 버튼을 클릭합니다.
   • 실행 중에는 일시정지/재개가 가능합니다.
   • 로그 창에서 실행 상태를 확인할 수 있습니다.
        """

        text = tk.Text(frame, wrap=tk.WORD, font=("Arial", 10))
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(1.0, content)
        text.config(state=tk.DISABLED)

    def _create_task_management_tab(self, notebook):
        """작업 관리 탭"""
        frame = ttk.Frame(notebook, padding="20")
        notebook.add(frame, text="작업 관리")

        content = """
사용 가능한 작업들:

• 네이버 로그인
  - 네이버 계정으로 자동 로그인합니다.
  - 프로필에 저장된 계정 정보를 사용합니다.

• 이웃 새글 확인
  - 이웃들의 새로운 포스트를 확인합니다.
  - 키워드 필터링, 블로거 필터링 등을 설정할 수 있습니다.

• 댓글 작성
  - 포스트에 자동으로 댓글을 작성합니다.
  - 댓글 스타일을 선택하거나 직접 입력할 수 있습니다.
  - 포스트를 읽는 시간을 시뮬레이션합니다.

• 좋아요 클릭
  - 포스트에 좋아요를 클릭합니다.
  - 이미 좋아요를 누른 포스트는 건너뜁니다.

• 스크롤 읽기
  - 자연스럽게 포스트를 스크롤하며 읽습니다.
  - 읽기 시간과 속도를 설정할 수 있습니다.

• 대기
  - 지정된 시간만큼 대기합니다.
  - 작업 사이에 간격을 두고 싶을 때 사용합니다.

• URL 이동
  - 특정 URL로 이동합니다.
  - 특정 포스트나 페이지로 직접 이동할 때 사용합니다.
        """

        text = tk.Text(frame, wrap=tk.WORD, font=("Arial", 10))
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(1.0, content)
        text.config(state=tk.DISABLED)

    def _create_profile_management_tab(self, notebook):
        """프로필 관리 탭"""
        frame = ttk.Frame(notebook, padding="20")
        notebook.add(frame, text="프로필 관리")

        content = """
프로필 시스템:

• 프로필이란?
  - 네이버 계정 정보를 저장한 설정입니다.
  - 여러 계정을 프로필로 관리할 수 있습니다.

• 프로필 추가
  1. '프로필 관리' 버튼을 클릭합니다.
  2. '새 프로필' 버튼을 클릭합니다.
  3. 프로필 이름과 네이버 계정 정보를 입력합니다.
  4. '비밀번호 저장'을 체크하면 비밀번호가 암호화되어 저장됩니다.

• 프로필 전환
  - 상단 툴바의 프로필 선택 상자에서 원하는 프로필을 선택합니다.
  - 선택된 프로필의 계정으로 작업이 실행됩니다.

• 보안
  - 모든 비밀번호는 암호화되어 저장됩니다.
  - 비밀번호를 저장하지 않으면 실행 시마다 입력해야 합니다.
  - 프로필 정보는 로컬 컴퓨터에만 저장됩니다.
        """

        text = tk.Text(frame, wrap=tk.WORD, font=("Arial", 10))
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(1.0, content)
        text.config(state=tk.DISABLED)

    def _create_tips_tab(self, notebook):
        """팁과 트릭 탭"""
        frame = ttk.Frame(notebook, padding="20")
        notebook.add(frame, text="팁과 트릭")

        content = """
유용한 팁:

• 자연스러운 활동 패턴
  - 작업 사이에 '대기' 작업을 추가하여 자연스러운 패턴을 만드세요.
  - '스크롤 읽기'를 사용하여 실제로 포스트를 읽는 것처럼 보이게 하세요.
  - 댓글 작성 시 '읽기 시간'을 충분히 설정하세요.

• 스케줄 저장/불러오기
  - 자주 사용하는 작업 조합을 스케줄로 저장할 수 있습니다.
  - 파일 메뉴에서 '스케줄 저장' 및 '스케줄 불러오기'를 사용하세요.

• 헤드리스 모드
  - 브라우저 창을 표시하지 않고 백그라운드에서 실행합니다.
  - 다른 작업을 하면서 자동화를 실행할 때 유용합니다.

• 로그 활용
  - 로그 레벨을 '상세' 또는 '디버그'로 설정하면 더 많은 정보를 볼 수 있습니다.
  - 문제가 발생했을 때 로그를 저장하여 분석하세요.

• 안전한 사용
  - 너무 빠른 속도로 많은 활동을 하지 마세요.
  - 하루 활동량을 적절히 제한하세요.
  - 실제 사용자처럼 자연스러운 패턴을 유지하세요.
        """

        text = tk.Text(frame, wrap=tk.WORD, font=("Arial", 10))
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(1.0, content)
        text.config(state=tk.DISABLED)
