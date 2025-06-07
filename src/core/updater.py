"""
자동 업데이트 모듈
GitHub 릴리즈에서 최신 버전을 확인하고 업데이트
"""

import requests
import os
import sys
import json
import zipfile
import tempfile
import shutil
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from packaging import version


class AutoUpdater:
    """자동 업데이트 관리자"""

    def __init__(self, current_version: str, repo_owner: str, repo_name: str):
        self.current_version = current_version
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_api_url = (
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        )

        # 업데이트 체크 캐시 파일
        self.cache_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "update_cache.json",
        )

    def check_for_update(self, force: bool = False) -> Dict:
        """
        업데이트 확인

        Args:
            force: 강제로 확인 (캐시 무시)

        Returns:
            {
                'available': bool,
                'version': str,
                'download_url': str,
                'changelog': str,
                'published_at': str
            }
        """
        # 캐시 확인 (1일에 한 번만 체크)
        if not force:
            cached_data = self._load_cache()
            if cached_data:
                last_check = datetime.fromisoformat(cached_data.get("last_check", ""))
                if datetime.now() - last_check < timedelta(days=1):
                    return cached_data.get("result", {"available": False})

        try:
            # GitHub API 호출
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "NaverBlogAutomation",
            }

            response = requests.get(self.github_api_url, headers=headers, timeout=10)

            if response.status_code == 200:
                release_data = response.json()
                latest_version = release_data["tag_name"].lstrip("v")

                # 버전 비교
                if self._is_newer_version(latest_version, self.current_version):
                    # 다운로드 URL 찾기
                    download_url = None
                    for asset in release_data.get("assets", []):
                        if asset["name"].endswith(".exe") or asset["name"].endswith(
                            ".zip"
                        ):
                            download_url = asset["browser_download_url"]
                            break

                    result = {
                        "available": True,
                        "version": latest_version,
                        "download_url": download_url,
                        "changelog": release_data.get("body", ""),
                        "published_at": release_data.get("published_at", ""),
                    }
                else:
                    result = {"available": False}

                # 캐시 저장
                self._save_cache(result)
                return result
            else:
                print(f"GitHub API 응답 오류: {response.status_code}")
                return {"available": False}

        except Exception as e:
            print(f"업데이트 확인 실패: {e}")
            return {"available": False}

    def download_update(
        self, download_url: str, progress_callback=None
    ) -> Optional[str]:
        """
        업데이트 다운로드

        Args:
            download_url: 다운로드 URL
            progress_callback: 진행률 콜백 함수 (percent, status)

        Returns:
            다운로드된 파일 경로
        """
        try:
            # 임시 디렉토리 생성
            temp_dir = tempfile.mkdtemp()
            filename = os.path.basename(download_url)
            filepath = os.path.join(temp_dir, filename)

            # 다운로드
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            percent = (downloaded / total_size) * 100
                            progress_callback(
                                percent,
                                f"다운로드 중... {downloaded}/{total_size} bytes",
                            )

            return filepath

        except Exception as e:
            print(f"다운로드 실패: {e}")
            if "temp_dir" in locals():
                shutil.rmtree(temp_dir, ignore_errors=True)
            return None

    def install_update(self, update_file: str) -> bool:
        """
        업데이트 설치

        Args:
            update_file: 업데이트 파일 경로

        Returns:
            성공 여부
        """
        try:
            # 업데이트 스크립트 생성
            update_script = self._create_update_script(update_file)

            if sys.platform == "win32":
                # Windows: 배치 파일 실행
                subprocess.Popen(update_script, shell=True)
            else:
                # macOS/Linux: 쉘 스크립트 실행
                os.chmod(update_script, 0o755)
                subprocess.Popen(update_script, shell=True)

            return True

        except Exception as e:
            print(f"업데이트 설치 실패: {e}")
            return False

    def _create_update_script(self, update_file: str) -> str:
        """업데이트 스크립트 생성"""
        current_exe = sys.executable
        current_dir = os.path.dirname(current_exe)

        if sys.platform == "win32":
            # Windows 배치 스크립트
            script_content = f"""@echo off
echo 업데이트를 설치하는 중...
timeout /t 3 /nobreak > nul
taskkill /f /im "{os.path.basename(current_exe)}" > nul 2>&1
timeout /t 2 /nobreak > nul
"""

            if update_file.endswith(".zip"):
                # ZIP 파일인 경우
                script_content += f"""
powershell -Command "Expand-Archive -Path '{update_file}' -DestinationPath '{current_dir}' -Force"
"""
            else:
                # EXE 파일인 경우
                script_content += f"""
copy /y "{update_file}" "{current_exe}"
"""

            script_content += f"""
del "{update_file}"
start "" "{current_exe}"
del "%~f0"
"""

            script_path = os.path.join(tempfile.gettempdir(), "update.bat")

        else:
            # macOS/Linux 쉘 스크립트
            script_content = f"""#!/bin/bash
echo "업데이트를 설치하는 중..."
sleep 3
pkill -f "{os.path.basename(current_exe)}"
sleep 2
"""

            if update_file.endswith(".zip"):
                script_content += f"""
unzip -o "{update_file}" -d "{current_dir}"
"""
            else:
                script_content += f"""
cp -f "{update_file}" "{current_exe}"
chmod +x "{current_exe}"
"""

            script_content += f"""
rm -f "{update_file}"
"{current_exe}" &
rm -f "$0"
"""

            script_path = os.path.join(tempfile.gettempdir(), "update.sh")

        # 스크립트 파일 생성
        with open(script_path, "w") as f:
            f.write(script_content)

        return script_path

    def _is_newer_version(self, v1: str, v2: str) -> bool:
        """버전 비교"""
        try:
            return version.parse(v1) > version.parse(v2)
        except:
            # 버전 파싱 실패 시 문자열 비교
            return v1 > v2

    def _load_cache(self) -> Optional[Dict]:
        """캐시 로드"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    return json.load(f)
        except:
            pass
        return None

    def _save_cache(self, result: Dict):
        """캐시 저장"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            cache_data = {"last_check": datetime.now().isoformat(), "result": result}
            with open(self.cache_file, "w") as f:
                json.dump(cache_data, f)
        except:
            pass


class UpdateDialog:
    """업데이트 다이얼로그 (GUI용)"""

    def __init__(self, parent, updater: AutoUpdater):
        self.parent = parent
        self.updater = updater

    def check_and_prompt(self):
        """업데이트 확인 및 프롬프트"""
        import tkinter as tk
        from tkinter import messagebox

        # 업데이트 확인
        update_info = self.updater.check_for_update()

        if update_info.get("available"):
            version = update_info["version"]
            changelog = update_info.get("changelog", "변경 사항 없음")

            # 변경 사항을 보여주는 커스텀 다이얼로그
            result = self._show_update_dialog(version, changelog)

            if result:
                # 업데이트 진행
                self._perform_update(update_info["download_url"])
        else:
            messagebox.showinfo("업데이트", "현재 최신 버전을 사용하고 있습니다.")

    def _show_update_dialog(self, version: str, changelog: str) -> bool:
        """업데이트 다이얼로그 표시"""
        import tkinter as tk
        from tkinter import ttk, scrolledtext

        dialog = tk.Toplevel(self.parent)
        dialog.title("업데이트 알림")
        dialog.geometry("500x400")
        dialog.resizable(False, False)

        # 중앙 배치
        dialog.transient(self.parent)
        dialog.grab_set()

        # 아이콘 및 제목
        title_frame = ttk.Frame(dialog, padding="20")
        title_frame.pack(fill=tk.X)

        ttk.Label(
            title_frame, text=f"새 버전 {version} 사용 가능", font=("Arial", 14, "bold")
        ).pack()

        ttk.Label(
            title_frame,
            text=f"현재 버전: {self.updater.current_version}",
            font=("Arial", 10),
        ).pack(pady=(5, 0))

        # 변경 사항
        changelog_frame = ttk.LabelFrame(dialog, text="변경 사항", padding="10")
        changelog_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        changelog_text = scrolledtext.ScrolledText(
            changelog_frame, height=10, wrap=tk.WORD, font=("Arial", 9)
        )
        changelog_text.pack(fill=tk.BOTH, expand=True)
        changelog_text.insert("1.0", changelog)
        changelog_text.config(state=tk.DISABLED)

        # 버튼
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        result = [False]

        def on_update():
            result[0] = True
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ttk.Button(button_frame, text="업데이트", command=on_update).pack(
            side=tk.RIGHT, padx=(5, 0)
        )

        ttk.Button(button_frame, text="나중에", command=on_cancel).pack(side=tk.RIGHT)

        # 다이얼로그 표시
        dialog.wait_window()

        return result[0]

    def _perform_update(self, download_url: str):
        """업데이트 수행"""
        import tkinter as tk
        from tkinter import ttk, messagebox

        # 진행률 다이얼로그
        progress_dialog = tk.Toplevel(self.parent)
        progress_dialog.title("업데이트 진행 중")
        progress_dialog.geometry("400x150")
        progress_dialog.resizable(False, False)
        progress_dialog.transient(self.parent)
        progress_dialog.grab_set()

        # 진행률 표시
        ttk.Label(
            progress_dialog, text="업데이트를 다운로드하는 중...", font=("Arial", 10)
        ).pack(pady=20)

        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(
            progress_dialog, variable=progress_var, maximum=100, length=300
        )
        progress_bar.pack(pady=10)

        status_label = ttk.Label(progress_dialog, text="")
        status_label.pack()

        def update_progress(percent, status):
            progress_var.set(percent)
            status_label.config(text=status)
            progress_dialog.update()

        # 다운로드 시작
        update_file = self.updater.download_update(download_url, update_progress)

        progress_dialog.destroy()

        if update_file:
            # 설치 확인
            result = messagebox.askyesno(
                "업데이트 설치",
                "업데이트를 다운로드했습니다.\n"
                "지금 설치하시겠습니까?\n\n"
                "프로그램이 재시작됩니다.",
            )

            if result:
                # 업데이트 설치
                if self.updater.install_update(update_file):
                    messagebox.showinfo(
                        "업데이트",
                        "업데이트가 설치됩니다.\n" "프로그램이 자동으로 재시작됩니다.",
                    )
                    # 프로그램 종료
                    self.parent.quit()
                else:
                    messagebox.showerror(
                        "오류", "업데이트 설치 중 오류가 발생했습니다."
                    )
        else:
            messagebox.showerror("오류", "업데이트 다운로드 중 오류가 발생했습니다.")
