import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import hashlib
import uuid


class LicenseManager:
    def __init__(self):
        # Firebase 초기화
        cred = credentials.Certificate("path/to/serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def generate_license(self, customer_email, days, features=None):
        """라이선스 생성"""
        license_data = {
            "license_key": str(uuid.uuid4()),
            "customer_email": customer_email,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=days),
            "features": features or ["basic"],
            "hardware_id": None,
            "is_active": True,
        }

        # Firestore에 저장
        self.db.collection("licenses").document(license_data["license_key"]).set(
            license_data
        )

        return license_data["license_key"]

    def verify_license(self, license_key, hardware_id):
        """라이선스 검증"""
        try:
            doc = self.db.collection("licenses").document(license_key).get()

            if not doc.exists:
                return False, "Invalid license key"

            license_data = doc.to_dict()

            # 만료일 확인
            if license_data["expires_at"] < datetime.now():
                return False, "License expired"

            # 활성화 상태 확인
            if not license_data["is_active"]:
                return False, "License deactivated"

            # 하드웨어 ID 확인 (첫 실행시 바인딩)
            if license_data["hardware_id"] is None:
                doc.reference.update({"hardware_id": hardware_id})
            elif license_data["hardware_id"] != hardware_id:
                return False, "License bound to different device"

            return True, license_data

        except Exception as e:
            return False, str(e)
