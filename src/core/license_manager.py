"""
라이선스 관리 모듈
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional
import os
import uuid


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
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "serviceAccountKey.json",
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

    def verify_license(self, license_key: str, hardware_id: str) -> Tuple[bool, Dict]:
        """라이선스 검증"""
        if not self.db:
            # 오프라인 모드
            return True, {
                "message": "오프라인 모드",
                "expires_at": datetime.now() + timedelta(days=30),
                "customer_email": "offline@user.com",
                "customer_id": "offline",
            }

        try:
            # Firestore에서 라이선스 조회
            doc_ref = self.db.collection("licenses").document(license_key)
            doc = doc_ref.get()

            if not doc.exists:
                return False, {"message": "존재하지 않는 라이선스입니다."}

            license_data = doc.to_dict()

            # 활성화 상태 확인 (active 필드 사용)
            if not license_data.get("active", False):
                return False, {"message": "비활성화된 라이선스입니다."}

            # 만료일 확인
            expire_date_str = license_data.get("expire_date")
            if expire_date_str:
                try:
                    # ISO 형식 문자열을 datetime으로 변환
                    expire_datetime = datetime.fromisoformat(
                        expire_date_str.replace("Z", "+00:00")
                    )

                    if datetime.now() > expire_datetime:
                        return False, {"message": "만료된 라이선스입니다."}

                    license_data["expires_at"] = expire_datetime
                except Exception as e:
                    print(f"날짜 파싱 오류: {e}")

            # 하드웨어 ID 확인 및 등록
            stored_hw_id = license_data.get("hardware_id")

            if not stored_hw_id:
                # 첫 사용 - 하드웨어 ID 등록
                doc_ref.update(
                    {
                        "hardware_id": hardware_id,
                        "first_used": datetime.now().isoformat(),
                        "last_used": datetime.now().isoformat(),
                    }
                )
                license_data["hardware_id"] = hardware_id

            elif stored_hw_id != hardware_id:
                return False, {
                    "message": "다른 컴퓨터에서는 사용할 수 없는 라이선스입니다."
                }
            else:
                # 마지막 사용 시간 업데이트
                doc_ref.update({"last_used": datetime.now().isoformat()})

            # customer_email 필드가 없으면 customer_id 사용
            if "customer_email" not in license_data:
                license_data["customer_email"] = license_data.get(
                    "customer_id", "Unknown"
                )

            return True, license_data

        except Exception as e:
            print(f"라이선스 검증 오류: {str(e)}")
            return False, {"message": f"라이선스 검증 중 오류: {str(e)}"}

    def generate_license(
        self, customer_id: str, days: int, features: list = None
    ) -> str:
        """라이선스 생성 (관리자용)"""
        if not self.db:
            return None

        license_key = str(uuid.uuid4())

        # 만료일 계산
        expire_date = None
        if days > 0:
            expire_date = (datetime.now() + timedelta(days=days)).isoformat()

        license_data = {
            "active": True,
            "created_date": datetime.now().isoformat(),
            "customer_id": customer_id,
            "expire_date": expire_date,
            "features": features or ["blog_management", "auto_comment"],
            "hardware_id": None,
            "max_devices": 1,
            "usage_count": 0,
        }

        try:
            self.db.collection("licenses").document(license_key).set(license_data)
            return license_key
        except Exception as e:
            print(f"라이선스 생성 실패: {str(e)}")
            return None
