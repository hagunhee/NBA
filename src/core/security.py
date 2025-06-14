"""
개선된 보안 관리 모듈 - pywin32/wmi 사용
"""

import platform
import uuid
import psutil
import logging
import sys
from typing import Optional, Tuple, Dict, Any
import json
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import hashlib
import secrets
import keyring
from keyring.errors import KeyringError

try:
    import cpuinfo

    HAS_CPUINFO = True
except ImportError:
    HAS_CPUINFO = False

# Windows 전용 모듈
if platform.system() == "Windows":
    try:
        import wmi
        import win32api
        import win32con

        HAS_WINDOWS_MODULES = True
    except ImportError:
        HAS_WINDOWS_MODULES = False
else:
    HAS_WINDOWS_MODULES = False


class SecurityManager:
    """개선된 보안 관리 클래스"""

    def __init__(self):
        self.service_name = "NaverBlogAutomation"
        self.logger = logging.getLogger(__name__)
        self._setup_encryption()
        self._hardware_id_cache = None

    def _setup_encryption(self):
        """암호화 설정"""
        # 암호화 키 파일 경로
        key_file = os.path.join(
            os.path.expanduser("~"), ".naver_blog_automation", ".encryption_key"
        )

        # 디렉토리 생성
        os.makedirs(os.path.dirname(key_file), exist_ok=True)

        # 키 파일이 있으면 로드, 없으면 생성
        if os.path.exists(key_file):
            try:
                with open(key_file, "rb") as f:
                    key = f.read()
            except Exception as e:
                self.logger.error(f"암호화 키 로드 실패: {e}")
                key = self._generate_encryption_key()
                self._save_encryption_key(key_file, key)
        else:
            key = self._generate_encryption_key()
            self._save_encryption_key(key_file, key)

        self.cipher = Fernet(key)

    def _generate_encryption_key(self) -> bytes:
        """안전한 암호화 키 생성"""
        # 마스터 패스워드 (환경 변수 또는 하드코딩)
        master_password = os.getenv(
            "MASTER_PASSWORD", "default_secure_password"
        ).encode()

        # 솔트 생성
        salt = b"naver_blog_automation_salt_v2"

        # PBKDF2를 사용한 키 유도
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password))

        return key

    def _save_encryption_key(self, key_file: str, key: bytes):
        """암호화 키 저장"""
        try:
            with open(key_file, "wb") as f:
                f.write(key)

            # Windows에서 파일 속성 설정
            if platform.system() == "Windows" and HAS_WINDOWS_MODULES:
                try:
                    win32api.SetFileAttributes(key_file, win32con.FILE_ATTRIBUTE_HIDDEN)
                except:
                    pass
            else:
                # Unix 계열에서 권한 설정
                os.chmod(key_file, 0o600)

        except Exception as e:
            self.logger.error(f"암호화 키 저장 실패: {e}")

    def get_hardware_id(self) -> str:
        """하드웨어 고유 ID 생성 (개선된 버전)"""
        # 캐시 확인
        if self._hardware_id_cache:
            return self._hardware_id_cache

        try:
            if platform.system() == "Windows" and HAS_WINDOWS_MODULES:
                hw_id = self._get_windows_hardware_id()
            elif platform.system() == "Darwin":  # macOS
                hw_id = self._get_macos_hardware_id()
            else:  # Linux 및 기타
                hw_id = self._get_linux_hardware_id()

            self._hardware_id_cache = hw_id
            return hw_id

        except Exception as e:
            self.logger.error(f"하드웨어 ID 생성 중 오류: {e}")
            # Fallback
            return self._get_fallback_hardware_id()

    def _get_windows_hardware_id(self) -> str:
        """Windows용 하드웨어 ID 생성 (WMI 사용)"""
        system_info = []

        try:
            c = wmi.WMI()

            # BIOS 정보
            for bios in c.Win32_BIOS():
                system_info.append(bios.SerialNumber or "")
                system_info.append(bios.Manufacturer or "")

            # 마더보드 정보
            for board in c.Win32_BaseBoard():
                system_info.append(board.SerialNumber or "")
                system_info.append(board.Product or "")

            # CPU 정보
            for cpu in c.Win32_Processor():
                system_info.append(cpu.ProcessorId or "")
                system_info.append(cpu.Name or "")

            # 디스크 정보
            for disk in c.Win32_DiskDrive():
                if disk.InterfaceType != "USB":  # USB 제외
                    system_info.append(disk.SerialNumber or "")
                    break

            # 네트워크 어댑터 (물리적인 것만)
            for net in c.Win32_NetworkAdapter(PhysicalAdapter=True):
                if net.MACAddress:
                    system_info.append(net.MACAddress)
                    break

            # Windows 제품 ID
            for os_info in c.Win32_OperatingSystem():
                system_info.append(os_info.SerialNumber or "")

        except Exception as e:
            self.logger.error(f"WMI를 통한 정보 수집 실패: {e}")
            # WMI 없이 기본 정보 수집
            system_info.extend(self._get_basic_windows_info())

        # 정보 결합 및 해시
        combined_info = "|".join(filter(None, system_info))
        return hashlib.sha256(combined_info.encode()).hexdigest()

    def _get_basic_windows_info(self) -> list:
        """WMI 없이 Windows 정보 수집"""
        info = []

        # 레지스트리에서 정보 읽기
        if HAS_WINDOWS_MODULES:
            try:
                import winreg

                # Machine GUID
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
                ) as key:
                    machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
                    info.append(machine_guid)

            except Exception:
                pass

        # 기본 정보
        info.extend(
            [
                platform.machine(),
                platform.processor(),
                hex(uuid.getnode()),  # MAC 주소
            ]
        )

        return info

    def _get_macos_hardware_id(self) -> str:
        """macOS용 하드웨어 ID 생성"""
        system_info = []

        try:
            import subprocess

            # 하드웨어 UUID
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Hardware UUID" in line:
                        hw_uuid = line.split(": ")[-1].strip()
                        system_info.append(hw_uuid)
                        break

            # 시리얼 번호
            result = subprocess.run(["ioreg", "-l"], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "IOPlatformSerialNumber" in line:
                        serial = line.split('"')[-2]
                        system_info.append(serial)
                        break

        except Exception as e:
            self.logger.error(f"macOS 정보 수집 실패: {e}")

        # 기본 정보 추가
        system_info.extend(
            [
                platform.machine(),
                platform.processor(),
                hex(uuid.getnode()),
            ]
        )

        combined_info = "|".join(filter(None, system_info))
        return hashlib.sha256(combined_info.encode()).hexdigest()

    def _get_linux_hardware_id(self) -> str:
        """Linux용 하드웨어 ID 생성"""
        system_info = []

        try:
            # DMI 정보 읽기
            dmi_files = [
                "/sys/class/dmi/id/product_uuid",
                "/sys/class/dmi/id/board_serial",
                "/sys/class/dmi/id/product_serial",
            ]

            for dmi_file in dmi_files:
                try:
                    with open(dmi_file, "r") as f:
                        system_info.append(f.read().strip())
                except:
                    pass

            # CPU 정보
            if HAS_CPUINFO:
                cpu_info = cpuinfo.get_cpu_info()
                system_info.append(cpu_info.get("brand_raw", ""))

        except Exception as e:
            self.logger.error(f"Linux 정보 수집 실패: {e}")

        # 기본 정보 추가
        system_info.extend(
            [
                platform.machine(),
                platform.processor(),
                hex(uuid.getnode()),
            ]
        )

        # 메모리 정보
        try:
            memory = psutil.virtual_memory()
            system_info.append(str(memory.total))
        except:
            pass

        combined_info = "|".join(filter(None, system_info))
        return hashlib.sha256(combined_info.encode()).hexdigest()

    def _get_fallback_hardware_id(self) -> str:
        """폴백 하드웨어 ID"""
        fallback_info = f"{platform.machine()}-{platform.system()}-{uuid.uuid4()}"
        return hashlib.sha256(fallback_info.encode()).hexdigest()

    def encrypt_password(self, password: str) -> str:
        """비밀번호 암호화 (개선된 버전)"""
        try:
            if not password:
                return ""

            # 추가 메타데이터와 함께 암호화
            data = {
                "password": password,
                "timestamp": os.path.getmtime(__file__),  # 파일 수정 시간
                "version": 2,  # 암호화 버전
            }

            json_data = json.dumps(data)
            encrypted = self.cipher.encrypt(json_data.encode())
            return base64.b64encode(encrypted).decode()

        except Exception as e:
            self.logger.error(f"비밀번호 암호화 실패: {e}")
            return ""

    def decrypt_password(self, encrypted_password: str) -> str:
        """비밀번호 복호화 (개선된 버전)"""
        try:
            if not encrypted_password:
                return ""

            encrypted_data = base64.b64decode(encrypted_password.encode())
            decrypted = self.cipher.decrypt(encrypted_data)

            data = json.loads(decrypted.decode())

            # 버전 확인
            version = data.get("version", 1)
            if version < 2:
                # 구버전 호환성
                return data.get("password", "")

            return data.get("password", "")

        except Exception as e:
            self.logger.error(f"비밀번호 복호화 실패: {e}")
            return ""

    def store_credentials(self, username: str, password: str, api_key: str = None):
        """자격 증명 안전하게 저장 (keyring 우선 사용)"""
        try:
            # keyring 사용 시도
            try:
                keyring.set_password(
                    self.service_name, f"{username}_password", password
                )
                if api_key:
                    keyring.set_password(
                        self.service_name, "anthropic_api_key", api_key
                    )
                self.logger.info("keyring을 사용하여 자격 증명 저장 완료")
                return True

            except KeyringError as e:
                self.logger.warning(f"keyring 저장 실패: {e}")
                # 로컬 저장으로 폴백

        except Exception as e:
            self.logger.error(f"자격 증명 저장 실패: {e}")

        # 폴백: 암호화하여 로컬 저장
        return self._store_local_credentials(username, password, api_key)

    def get_credentials(self, username: str) -> Tuple[Optional[str], Optional[str]]:
        """저장된 자격 증명 가져오기"""
        try:
            # keyring 시도
            try:
                password = keyring.get_password(
                    self.service_name, f"{username}_password"
                )
                api_key = keyring.get_password(self.service_name, "anthropic_api_key")

                if password:
                    return password, api_key

            except KeyringError:
                pass

        except Exception as e:
            self.logger.error(f"keyring 조회 실패: {e}")

        # 폴백: 로컬에서 읽기
        return self._get_local_credentials(username)

    def _store_local_credentials(
        self, username: str, password: str, api_key: str = None
    ) -> bool:
        """로컬 파일에 자격 증명 저장"""
        try:
            # 암호화
            encrypted_data = {
                "username": username,
                "password": self.encrypt_password(password),
                "api_key": self.encrypt_password(api_key) if api_key else None,
                "hardware_id": self.get_hardware_id(),  # 하드웨어 바인딩
            }

            # 저장 경로
            data_dir = os.path.join(os.path.expanduser("~"), ".naver_blog_automation")
            os.makedirs(data_dir, exist_ok=True)

            cred_file = os.path.join(data_dir, ".credentials")

            with open(cred_file, "w") as f:
                json.dump(encrypted_data, f)

            # 파일 권한 설정
            if platform.system() != "Windows":
                os.chmod(cred_file, 0o600)

            self.logger.info("로컬 파일에 자격 증명 저장 완료")
            return True

        except Exception as e:
            self.logger.error(f"로컬 저장 실패: {e}")
            return False

    def _get_local_credentials(
        self, username: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """로컬 파일에서 자격 증명 읽기"""
        try:
            data_dir = os.path.join(os.path.expanduser("~"), ".naver_blog_automation")
            cred_file = os.path.join(data_dir, ".credentials")

            if not os.path.exists(cred_file):
                return None, None

            with open(cred_file, "r") as f:
                data = json.load(f)

            # 사용자 확인
            if data.get("username") != username:
                return None, None

            # 하드웨어 확인 (선택적)
            stored_hw_id = data.get("hardware_id")
            if stored_hw_id and not self.validate_hardware_id(stored_hw_id):
                self.logger.warning("하드웨어 ID 불일치")
                # 경고만 하고 계속 진행 (유연한 정책)

            # 복호화
            password = self.decrypt_password(data.get("password", ""))
            api_key = (
                self.decrypt_password(data.get("api_key", ""))
                if data.get("api_key")
                else None
            )

            return password, api_key

        except Exception as e:
            self.logger.error(f"로컬 자격 증명 읽기 실패: {e}")
            return None, None

    def validate_hardware_id(self, stored_hardware_id: str) -> bool:
        """하드웨어 ID 검증 (유연한 버전)"""
        try:
            current_hardware_id = self.get_hardware_id()

            # 정확히 일치
            if current_hardware_id == stored_hardware_id:
                return True

            # 부분 일치 허용 (앞 32자)
            if len(current_hardware_id) >= 32 and len(stored_hardware_id) >= 32:
                if current_hardware_id[:32] == stored_hardware_id[:32]:
                    self.logger.info("하드웨어 ID 부분 일치")
                    return True

            return False

        except Exception as e:
            self.logger.error(f"하드웨어 ID 검증 실패: {e}")
            return False

    def generate_secure_token(self, length: int = 32) -> str:
        """안전한 토큰 생성"""
        return secrets.token_urlsafe(length)

    def hash_sensitive_data(self, data: str) -> str:
        """민감한 데이터 해싱"""
        return hashlib.sha256(data.encode()).hexdigest()

    def get_system_info(self) -> Dict[str, Any]:
        """시스템 정보 수집"""
        info = {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version,
            "hardware_id": self.get_hardware_id()[:16] + "...",  # 일부만 표시
        }

        # Windows 추가 정보
        if platform.system() == "Windows" and HAS_WINDOWS_MODULES:
            try:
                import win32api

                info["windows_version"] = win32api.GetVersionEx()
                info["computer_name"] = win32api.GetComputerName()
            except:
                pass

        return info
