"""
프로필 관리 다이얼로그
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional, Callable
from core.config import Config
from core.security import SecurityManager


class ProfileManagerDialog:
    """프로필 관리 다이얼로그"""

    def __init__(
        self,
        parent,
        config: Config,
        security_manager: SecurityManager,
        on_profile_change: Callable = None,
    ):
        self.parent = parent
        self.config = config
        self.security_manager = security_manager
        self.on_profile_change = on_profile_change

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("프로필 관리")
        self.dialog.geometry("600x500")
        self.dialog.resizable(False, False)

        # 중앙 배치
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 선택된 프로필
        self.selected_profile = None

        self.setup_ui()
        self.load_profiles()

        # 포커스 설정
        self.dialog.focus_set()

    def setup_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 상단 설명
        ttk.Label(
            main_frame,
            text="저장된 네이버 계정 프로필을 관리합니다.",
            font=("Arial", 10),
        ).pack(anchor=tk.W, pady=(0, 20))

        # 프로필 목록 프레임
        list_frame = ttk.LabelFrame(main_frame, text="프로필 목록", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # 프로필 리스트박스와 스크롤바
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.profile_listbox = tk.Listbox(
            list_container, yscrollcommand=scrollbar.set, font=("Arial", 10), height=10
        )
        self.profile_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.profile_listbox.yview)

        # 리스트박스 이벤트 바인딩
        self.profile_listbox.bind("<<ListboxSelect>>", self.on_profile_select)
        self.profile_listbox.bind("<Double-Button-1>", lambda e: self.load_profile())

        # 프로필 정보 표시
        info_frame = ttk.Frame(list_frame)
        info_frame.pack(fill=tk.X, pady=(10, 0))

        self.info_label = ttk.Label(
            info_frame, text="프로필을 선택하세요.", foreground="gray"
        )
        self.info_label.pack(anchor=tk.W)

        # 버튼 프레임
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        # 왼쪽 버튼들
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)

        ttk.Button(
            left_buttons, text="새 프로필", command=self.add_profile, width=12
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            left_buttons, text="프로필 편집", command=self.edit_profile, width=12
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            left_buttons, text="프로필 삭제", command=self.delete_profile, width=12
        ).pack(side=tk.LEFT)

        # 오른쪽 버튼들
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)

        ttk.Button(
            right_buttons, text="불러오기", command=self.load_profile, width=12
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            right_buttons, text="닫기", command=self.dialog.destroy, width=12
        ).pack(side=tk.LEFT)

        # 현재 프로필 표시
        current_frame = ttk.Frame(main_frame)
        current_frame.pack(fill=tk.X)

        current_profile = self.config.get_current_profile_name()
        if current_profile:
            self.current_label = ttk.Label(
                current_frame,
                text=f"현재 프로필: {current_profile}",
                font=("Arial", 9, "bold"),
                foreground="#0066cc",
            )
        else:
            self.current_label = ttk.Label(
                current_frame,
                text="현재 선택된 프로필이 없습니다.",
                font=("Arial", 9),
                foreground="gray",
            )
        self.current_label.pack(anchor=tk.W)

    def load_profiles(self):
        """프로필 목록 로드"""
        self.profile_listbox.delete(0, tk.END)

        profiles = self.config.get_profiles()
        current_profile = self.config.get_current_profile_name()

        for i, (profile_name, profile_data) in enumerate(profiles.items()):
            display_text = profile_name
            if profile_name == current_profile:
                display_text = f"▶ {profile_name}"

            self.profile_listbox.insert(tk.END, display_text)

            # 현재 프로필 선택
            if profile_name == current_profile:
                self.profile_listbox.selection_set(i)
                self.selected_profile = profile_name
                self.update_info_label(profile_name, profile_data)

    def on_profile_select(self, event):
        """프로필 선택 이벤트"""
        selection = self.profile_listbox.curselection()
        if selection:
            index = selection[0]
            profile_name = self.profile_listbox.get(index).replace("▶ ", "")
            self.selected_profile = profile_name

            profile_data = self.config.get_profile(profile_name)
            if profile_data:
                self.update_info_label(profile_name, profile_data)

    def update_info_label(self, profile_name: str, profile_data: dict):
        """프로필 정보 업데이트"""
        naver_id = profile_data.get("naver_id", "")
        save_pw = profile_data.get("save_pw", False)

        info_text = f"프로필: {profile_name}\n"
        info_text += f"아이디: {naver_id}\n"
        info_text += f"비밀번호: {'저장됨' if save_pw else '저장 안 됨'}"

        self.info_label.config(text=info_text, foreground="black")

    def add_profile(self):
        """새 프로필 추가"""
        dialog = ProfileEditDialog(self.dialog, self.config, self.security_manager)
        self.dialog.wait_window(dialog.dialog)

        if dialog.result:
            profile_name, naver_id, naver_pw, save_pw = dialog.result

            # 중복 확인
            if profile_name in self.config.get_profile_names():
                messagebox.showerror("오류", "이미 존재하는 프로필 이름입니다.")
                return

            # 비밀번호 암호화
            if save_pw and naver_pw:
                encrypted_pw = self.security_manager.encrypt_password(naver_pw)
            else:
                encrypted_pw = ""

            # 프로필 저장
            self.config.save_profile(profile_name, naver_id, encrypted_pw, save_pw)

            # 목록 새로고침
            self.load_profiles()

            messagebox.showinfo(
                "성공", f"프로필 '{profile_name}'이(가) 추가되었습니다."
            )

    def edit_profile(self):
        """프로필 편집"""
        if not self.selected_profile:
            messagebox.showwarning("경고", "편집할 프로필을 선택하세요.")
            return

        profile_data = self.config.get_profile(self.selected_profile)
        if not profile_data:
            return

        # 비밀번호 복호화
        encrypted_pw = profile_data.get("naver_pw", "")
        if encrypted_pw:
            try:
                decrypted_pw = self.security_manager.decrypt_password(encrypted_pw)
            except:
                decrypted_pw = ""
        else:
            decrypted_pw = ""

        dialog = ProfileEditDialog(
            self.dialog,
            self.config,
            self.security_manager,
            profile_name=self.selected_profile,
            naver_id=profile_data.get("naver_id", ""),
            naver_pw=decrypted_pw,
            save_pw=profile_data.get("save_pw", False),
        )

        self.dialog.wait_window(dialog.dialog)

        if dialog.result:
            new_name, naver_id, naver_pw, save_pw = dialog.result

            # 이름 변경 처리
            if new_name != self.selected_profile:
                if new_name in self.config.get_profile_names():
                    messagebox.showerror("오류", "이미 존재하는 프로필 이름입니다.")
                    return

                # 기존 프로필 삭제
                self.config.delete_profile(self.selected_profile)

            # 비밀번호 암호화
            if save_pw and naver_pw:
                encrypted_pw = self.security_manager.encrypt_password(naver_pw)
            else:
                encrypted_pw = ""

            # 프로필 저장
            self.config.save_profile(new_name, naver_id, encrypted_pw, save_pw)

            # 목록 새로고침
            self.load_profiles()

            messagebox.showinfo("성공", "프로필이 수정되었습니다.")

    def delete_profile(self):
        """프로필 삭제"""
        if not self.selected_profile:
            messagebox.showwarning("경고", "삭제할 프로필을 선택하세요.")
            return

        result = messagebox.askyesno(
            "확인", f"프로필 '{self.selected_profile}'을(를) 삭제하시겠습니까?"
        )

        if result:
            self.config.delete_profile(self.selected_profile)
            self.load_profiles()
            self.selected_profile = None
            self.info_label.config(text="프로필을 선택하세요.", foreground="gray")

            messagebox.showinfo("성공", "프로필이 삭제되었습니다.")

    def load_profile(self):
        """선택한 프로필 불러오기"""
        if not self.selected_profile:
            messagebox.showwarning("경고", "불러올 프로필을 선택하세요.")
            return

        # 현재 프로필로 설정
        self.config.set_current_profile(self.selected_profile)

        # 콜백 실행
        if self.on_profile_change:
            self.on_profile_change(self.selected_profile)

        messagebox.showinfo(
            "성공", f"프로필 '{self.selected_profile}'을(를) 불러왔습니다."
        )

        self.dialog.destroy()


class ProfileEditDialog:
    """프로필 편집 다이얼로그"""

    def __init__(
        self,
        parent,
        config: Config,
        security_manager: SecurityManager,
        profile_name: str = "",
        naver_id: str = "",
        naver_pw: str = "",
        save_pw: bool = True,
    ):
        self.config = config
        self.security_manager = security_manager
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("프로필 편집" if profile_name else "새 프로필")
        self.dialog.geometry("400x300")
        self.dialog.resizable(False, False)

        # 중앙 배치
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # UI 구성
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 입력 필드들
        fields_frame = ttk.Frame(main_frame)
        fields_frame.pack(fill=tk.X, pady=(0, 20))

        # 프로필 이름
        ttk.Label(fields_frame, text="프로필 이름:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.profile_name_entry = ttk.Entry(fields_frame, width=30)
        self.profile_name_entry.grid(row=0, column=1, padx=(10, 0), pady=5)
        self.profile_name_entry.insert(0, profile_name)

        # 구분선
        ttk.Separator(fields_frame, orient="horizontal").grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=10
        )

        # 네이버 아이디
        ttk.Label(fields_frame, text="네이버 아이디:").grid(
            row=2, column=0, sticky=tk.W, pady=5
        )
        self.naver_id_entry = ttk.Entry(fields_frame, width=30)
        self.naver_id_entry.grid(row=2, column=1, padx=(10, 0), pady=5)
        self.naver_id_entry.insert(0, naver_id)

        # 네이버 비밀번호
        ttk.Label(fields_frame, text="네이버 비밀번호:").grid(
            row=3, column=0, sticky=tk.W, pady=5
        )
        self.naver_pw_entry = ttk.Entry(fields_frame, width=30, show="*")
        self.naver_pw_entry.grid(row=3, column=1, padx=(10, 0), pady=5)
        self.naver_pw_entry.insert(0, naver_pw)

        # 비밀번호 저장 체크박스
        self.save_pw_var = tk.BooleanVar(value=save_pw)
        ttk.Checkbutton(
            fields_frame, text="비밀번호 저장", variable=self.save_pw_var
        ).grid(row=4, column=1, sticky=tk.W, padx=(10, 0), pady=10)

        # 안내 메시지
        info_label = ttk.Label(
            main_frame,
            text="※ 비밀번호는 암호화되어 저장됩니다.",
            font=("Arial", 8),
            foreground="gray",
        )
        info_label.pack(anchor=tk.W, pady=(0, 20))

        # 버튼들
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Button(button_frame, text="저장", command=self.save, width=12).pack(
            side=tk.RIGHT, padx=(5, 0)
        )

        ttk.Button(
            button_frame, text="취소", command=self.dialog.destroy, width=12
        ).pack(side=tk.RIGHT)

        # 포커스 설정
        self.profile_name_entry.focus_set()

        # Enter 키 바인딩
        self.dialog.bind("<Return>", lambda e: self.save())

    def save(self):
        """프로필 저장"""
        profile_name = self.profile_name_entry.get().strip()
        naver_id = self.naver_id_entry.get().strip()
        naver_pw = self.naver_pw_entry.get().strip()
        save_pw = self.save_pw_var.get()

        # 검증
        if not profile_name:
            messagebox.showerror("오류", "프로필 이름을 입력하세요.")
            self.profile_name_entry.focus_set()
            return

        if not naver_id:
            messagebox.showerror("오류", "네이버 아이디를 입력하세요.")
            self.naver_id_entry.focus_set()
            return

        if save_pw and not naver_pw:
            messagebox.showerror(
                "오류", "비밀번호를 입력하거나 '비밀번호 저장'을 해제하세요."
            )
            self.naver_pw_entry.focus_set()
            return

        self.result = (profile_name, naver_id, naver_pw, save_pw)
        self.dialog.destroy()
