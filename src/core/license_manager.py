import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import hashlib
import uuid
from typing import Tuple, Dict, Optional
import os


class LicenseManager:
    """라이선스 관리 클래스"""

    def __init__(self):
        self.db = None
        self.init_firebase()

    def init_firebase(self):
        """Firebase 초기화"""
        try:
            # 서비스 계정 키 파일 경로
            cred_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "serviceAccountKey.json"
            )

            if not os.path.exists(cred_path):
                print("경고: serviceAccountKey.json 파일이 없습니다.")
                return

            # Firebase 앱이 이미 초기화되었는지 확인
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)

            self.db = firestore.client()
            print("Firebase 연결 성공")

        except Exception as e:
            print(f"Firebase 초기화 실패: {str(e)}")
            self.db = None

    def generate_license(
        self, customer_email: str, days: int, features: list = None
    ) -> str:
        """라이선스 생성 (관리자용)"""
        if not self.db:
            return None

        license_key = str(uuid.uuid4())
        license_data = {
            "license_key": license_key,
            "customer_email": customer_email,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=days),
            "features": features or ["basic"],
            "hardware_id": None,
            "is_active": True,
            "max_devices": 1,
        }

        try:
            self.db.collection("licenses").document(license_key).set(license_data)
            return license_key
        except Exception as e:
            print(f"라이선스 생성 실패: {str(e)}")
            return None

    def verify_license(self, license_key: str, hardware_id: str) -> Tuple[bool, Dict]:
        """라이선스 검증"""
        if not self.db:
            # 오프라인 모드 - 임시 허용
            return True, {
                "message": "오프라인 모드",
                "expires_at": datetime.now() + timedelta(days=30),
            }

        try:
            doc = self.db.collection("licenses").document(license_key).get()

            if not doc.exists:
                return False, {"message": "유효하지 않은 라이선스 키"}

            license_data = doc.to_dict()

            # 만료일 확인
            if license_data["expires_at"] < datetime.now():
                return False, {"message": "라이선스가 만료되었습니다"}

            # 활성화 상태 확인
            if not license_data.get("is_active", True):
                return False, {"message": "비활성화된 라이선스입니다"}

            # 하드웨어 ID 확인 및 바인딩
            stored_hw_id = license_data.get("hardware_id")
            if stored_hw_id is None:
                # 첫 실행 - 하드웨어 ID 바인딩
                doc.reference.update({"hardware_id": hardware_id})
                license_data["hardware_id"] = hardware_id
            elif stored_hw_id != hardware_id:
                return False, {"message": "다른 기기에 등록된 라이선스입니다"}

            return True, license_data

        except Exception as e:
            print(f"라이선스 검증 오류: {str(e)}")
            return False, {"message": "라이선스 검증 중 오류가 발생했습니다"}
