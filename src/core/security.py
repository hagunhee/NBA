"""
보안 관리 모듈
"""

import platform
import uuid
import psutil
from typing import Optional, Tuple
import json
import os
import base64
from cryptography.fernet import Fernet
import hashlib


class SecurityManager:
    """보안 관리 클래스"""

    def __init__(self):
        self.service_name = "NaverBlogAutomation"
        # 하드웨어 ID를 기반으로 암호화 키 생성
        hardware_id = self.get_hardware_id()
        key = hashlib.sha256(hardware_id.encode()).digest()
        self.cipher = Fernet(base64.urlsafe_b64encode(key))

    def get_hardware_id(self) -> str:
        """하드웨어 고유 ID 생성"""
        try:
            system_info = []

            # 플랫폼 정보
            system_info.append(platform.machine())
            system_info.append(platform.processor())
            system_info.append(platform.system())

            # MAC 주소
            try:
                mac = hex(uuid.getnode())
                system_info.append(mac)
            except:
                pass

            # 메모리 정보
            try:
                memory = psutil.virtual_memory()
                system_info.append(str(memory.total))
            except:
                pass

            # 디스크 정보
            try:
                if platform.system() == "Windows":
                    disk_usage = psutil.disk_usage("C:\\")
                else:
                    disk_usage = psutil.disk_usage("/")
                system_info.append(str(disk_usage.total))
            except:
                pass

            # Windows UUID
            if platform.system() == "Windows":
                try:
                    import subprocess

                    result = subprocess.run(
                        ["wmic", "csproduct", "get", "uuid"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        uuid_info = result.stdout.strip().split("\n")
                        if len(uuid_info) > 1:
                            system_info.append(uuid_info[1].strip())
                except:
                    pass

            # 해시 생성
            combined_info = "".join(system_info)
            return hashlib.sha256(combined_info.encode()).hexdigest()

        except Exception as e:
            print(f"하드웨어 ID 생성 중 오류: {e}")
            # Fallback
            fallback_info = (
                f"{platform.machine()}-{platform.system()}-{hex(uuid.getnode())}"
            )
            return hashlib.md5(fallback_info.encode()).hexdigest()

    def encrypt_password(self, password: str) -> str:
        """비밀번호 암호화"""
        try:
            if not password:
                return ""
            encrypted = self.cipher.encrypt(password.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            print(f"비밀번호 암호화 실패: {e}")
            return ""

    def decrypt_password(self, encrypted_password: str) -> str:
        """비밀번호 복호화"""
        try:
            if not encrypted_password:
                return ""
            encrypted_data = base64.b64decode(encrypted_password.encode())
            decrypted = self.cipher.decrypt(encrypted_data)
            return decrypted.decode()
        except Exception as e:
            print(f"비밀번호 복호화 실패: {e}")
            return ""

    def store_credentials(self, username: str, password: str, api_key: str = None):
        """자격 증명 안전하게 저장"""
        try:
            # keyring 사용 시도
            try:
                import keyring

                keyring.set_password(
                    self.service_name, f"{username}_password", password
                )
                if api_key:
                    keyring.set_password(self.service_name, "claude_api_key", api_key)
                print("keyring을 사용하여 자격 증명 저장 완료")
                return True
            except ImportError:
                print("keyring 모듈을 찾을 수 없습니다. 로컬 저장 방식 사용")
            except Exception as e:
                print(f"keyring 저장 실패: {e}. 로컬 저장 방식 사용")

            # Fallback: 로컬 파일에 암호화하여 저장
            self._store_local_credentials(username, password, api_key)
            return True

        except Exception as e:
            print(f"자격 증명 저장 실패: {e}")
            return False

    def get_credentials(self, username: str) -> Tuple[Optional[str], Optional[str]]:
        """저장된 자격 증명 가져오기"""
        try:
            # keyring 사용 시도
            try:
                import keyring

                password = keyring.get_password(
                    self.service_name, f"{username}_password"
                )
                api_key = keyring.get_password(self.service_name, "claude_api_key")
                if password:  # keyring에서 찾았으면 반환
                    return password, api_key
            except ImportError:
                pass
            except Exception as e:
                print(f"keyring 읽기 실패: {e}")

            # Fallback: 로컬 파일에서 읽기
            return self._get_local_credentials(username)

        except Exception as e:
            print(f"자격 증명 읽기 실패: {e}")
            return None, None

    def _store_local_credentials(
        self, username: str, password: str, api_key: str = None
    ):
        """로컬 파일에 자격 증명 저장 (Fallback)"""
        try:
            # 암호화하여 저장
            encrypted_data = {
                "username": username,
                "password": self.encrypt_password(password),
                "api_key": self.encrypt_password(api_key) if api_key else None,
            }

            # 데이터 디렉토리 생성
            data_dir = os.path.join(os.path.expanduser("~"), ".naver_blog_automation")
            os.makedirs(data_dir, exist_ok=True)

            cred_file = os.path.join(data_dir, ".credentials")
            with open(cred_file, "w") as f:
                json.dump(encrypted_data, f)

            print(f"로컬 파일에 자격 증명 저장 완료: {cred_file}")

        except Exception as e:
            print(f"로컬 자격 증명 저장 실패: {e}")

    def _get_local_credentials(
        self, username: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """로컬 파일에서 자격 증명 읽기 (Fallback)"""
        try:
            data_dir = os.path.join(os.path.expanduser("~"), ".naver_blog_automation")
            cred_file = os.path.join(data_dir, ".credentials")

            if not os.path.exists(cred_file):
                return None, None

            with open(cred_file, "r") as f:
                data = json.load(f)

            if data.get("username") != username:
                return None, None

            # 복호화
            password = self.decrypt_password(data.get("password", ""))
            api_key = (
                self.decrypt_password(data.get("api_key", ""))
                if data.get("api_key")
                else None
            )

            return password, api_key

        except Exception as e:
            print(f"로컬 자격 증명 읽기 실패: {e}")
            return None, None

    def clear_credentials(self, username: str = None):
        """저장된 자격 증명 삭제"""
        try:
            # keyring에서 삭제 시도
            try:
                import keyring

                if username:
                    keyring.delete_password(self.service_name, f"{username}_password")
                keyring.delete_password(self.service_name, "claude_api_key")
                print("keyring에서 자격 증명 삭제 완료")
            except:
                pass

            # 로컬 파일 삭제
            data_dir = os.path.join(os.path.expanduser("~"), ".naver_blog_automation")
            cred_file = os.path.join(data_dir, ".credentials")

            if os.path.exists(cred_file):
                os.remove(cred_file)
                print("로컬 자격 증명 파일 삭제 완료")

            return True

        except Exception as e:
            print(f"자격 증명 삭제 실패: {e}")
            return False

    def validate_hardware_id(self, stored_hardware_id: str) -> bool:
        """하드웨어 ID 검증"""
        try:
            current_hardware_id = self.get_hardware_id()
            return current_hardware_id == stored_hardware_id
        except Exception as e:
            print(f"하드웨어 ID 검증 실패: {e}")
            return False
