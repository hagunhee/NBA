from cryptography.fernet import Fernet
import keyring
import platform
import hashlib
import uuid


class SecurityManager:
    def __init__(self):
        self.service_name = "NaverBlogManager"

    def get_hardware_id(self):
        """하드웨어 ID 생성"""
        if platform.system() == "Windows":
            import wmi

            c = wmi.WMI()
            for item in c.Win32_ComputerSystemProduct():
                return hashlib.sha256(item.UUID.encode()).hexdigest()
        else:
            # macOS/Linux
            mac = uuid.getnode()
            return hashlib.sha256(str(mac).encode()).hexdigest()

    def store_credentials(self, username, password, api_key):
        """자격 증명 안전하게 저장"""
        # 각 항목을 시스템 키체인에 저장
        keyring.set_password(self.service_name, f"{username}_password", password)
        keyring.set_password(self.service_name, "claude_api_key", api_key)

    def get_credentials(self, username):
        """저장된 자격 증명 가져오기"""
        try:
            password = keyring.get_password(self.service_name, f"{username}_password")
            api_key = keyring.get_password(self.service_name, "claude_api_key")
            return password, api_key
        except:
            return None, None
