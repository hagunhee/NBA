import os
import json
import logging
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
import concurrent.futures
import time


class LicenseStatus(Enum):
    """라이선스 상태"""

    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    TRIAL = "trial"


class LicenseType(Enum):
    """라이선스 타입"""

    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    TRIAL = "trial"


@dataclass
class License:
    """라이선스 데이터 모델"""

    license_key: str
    customer_email: str
    customer_id: str
    license_type: LicenseType
    status: LicenseStatus
    created_at: datetime
    expires_at: Optional[datetime]
    hardware_id: Optional[str]
    max_devices: int = 1
    features: Dict[str, bool] = None
    usage_count: int = 0
    last_used: Optional[datetime] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.features is None:
            self.features = self._get_default_features()
        if self.metadata is None:
            self.metadata = {}

    def _get_default_features(self) -> Dict[str, bool]:
        """라이선스 타입별 기본 기능"""
        features_map = {
            LicenseType.BASIC: {
                "blog_management": True,
                "auto_comment": True,
                "auto_like": True,
                "ai_comment": False,
                "scheduling": False,
                "multi_profile": False,
                "analytics": False,
            },
            LicenseType.PROFESSIONAL: {
                "blog_management": True,
                "auto_comment": True,
                "auto_like": True,
                "ai_comment": True,
                "scheduling": True,
                "multi_profile": True,
                "analytics": False,
            },
            LicenseType.ENTERPRISE: {
                "blog_management": True,
                "auto_comment": True,
                "auto_like": True,
                "ai_comment": True,
                "scheduling": True,
                "multi_profile": True,
                "analytics": True,
                "priority_support": True,
                "custom_features": True,
            },
            LicenseType.TRIAL: {
                "blog_management": True,
                "auto_comment": True,
                "auto_like": True,
                "ai_comment": True,
                "scheduling": False,
                "multi_profile": False,
                "analytics": False,
            },
        }
        return features_map.get(self.license_type, features_map[LicenseType.BASIC])

    def is_valid(self) -> bool:
        """라이선스 유효성 확인"""
        if self.status != LicenseStatus.ACTIVE and self.status != LicenseStatus.TRIAL:
            return False

        if self.expires_at and datetime.now() > self.expires_at:
            return False

        return True


class LicenseManager:
    """개선된 라이선스 관리 클래스 - 타임아웃 처리"""

    def __init__(
        self, service_account_path: Optional[str] = None, timeout: int = 5
    ):  # 10 -> 5초로 줄임
        self.logger = logging.getLogger(__name__)
        self.db = None
        self.timeout = timeout  # 타임아웃 줄임
        self._cache: Dict[str, License] = {}
        self._offline_mode = False

        # Firebase 초기화 (타임아웃 적용)
        self._init_firebase_with_timeout(service_account_path)

    def _init_firebase_with_timeout(self, service_account_path: Optional[str] = None):
        """Firebase 초기화 (타임아웃 적용)"""

        def init_worker():
            try:
                return self._init_firebase_internal(service_account_path)
            except Exception as e:
                self.logger.error(f"Firebase 초기화 실패: {str(e)}")
                return False

        try:
            # 타임아웃 적용하여 Firebase 초기화
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(init_worker)
                success = future.result(timeout=self.timeout)

                if not success:
                    self._offline_mode = True
                    self.logger.warning("Firebase 초기화 실패, 오프라인 모드로 전환")

        except concurrent.futures.TimeoutError:
            self._offline_mode = True
            self.logger.warning(
                f"Firebase 초기화 타임아웃 ({self.timeout}초), 오프라인 모드로 전환"
            )
        except Exception as e:
            self._offline_mode = True
            self.logger.error(
                f"Firebase 초기화 중 오류: {str(e)}, 오프라인 모드로 전환"
            )

    def _init_firebase_internal(
        self, service_account_path: Optional[str] = None
    ) -> bool:
        """내부 Firebase 초기화"""
        try:
            # Firebase 모듈 임포트 (선택적)
            try:
                import firebase_admin
                from firebase_admin import credentials, firestore
            except ImportError:
                self.logger.warning("firebase_admin 모듈이 설치되지 않았습니다.")
                return False

            # 서비스 계정 키 파일 경로
            if not service_account_path:
                service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")

                if not service_account_path:
                    default_paths = [
                        "serviceAccountKey.json",
                        os.path.join(
                            os.path.dirname(__file__),
                            "..",
                            "..",
                            "serviceAccountKey.json",
                        ),
                        os.path.join(
                            os.path.expanduser("~"),
                            ".naver_blog_automation",
                            "serviceAccountKey.json",
                        ),
                    ]

                    for path in default_paths:
                        if os.path.exists(path):
                            service_account_path = path
                            break

            if not service_account_path or not os.path.exists(service_account_path):
                self.logger.warning("Firebase 서비스 계정 키 파일을 찾을 수 없습니다.")
                return False

            # Firebase 앱이 이미 초기화되었는지 확인
            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)

            self.db = firestore.client()
            self.logger.info("Firebase/Firestore 연결 성공")
            return True

        except Exception as e:
            self.logger.error(f"Firebase 초기화 실패: {str(e)}")
            return False

    def verify_license(
        self, license_key: str, hardware_id: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """라이선스 검증 (타임아웃 적용)"""
        # 오프라인 모드
        if self._offline_mode:
            return self._verify_offline(license_key, hardware_id)

        # 캐시 확인
        if license_key in self._cache:
            cached_license = self._cache[license_key]
            if cached_license.is_valid():
                return self._validate_hardware(cached_license, hardware_id)

        def verify_worker():
            try:
                # Firestore에서 라이선스 조회
                doc_ref = self.db.collection("licenses").document(license_key)
                doc = doc_ref.get()

                if not doc.exists:
                    return False, {"message": "존재하지 않는 라이선스입니다."}

                license_data = doc.to_dict()

                # License 객체로 변환 시도
                try:
                    license_obj = (
                        License.from_dict(license_data)
                        if hasattr(License, "from_dict")
                        else None
                    )
                    if not license_obj:
                        # 간단한 검증으로 폴백
                        if license_data.get("active", False):
                            return True, {"valid": True, "message": "라이선스 유효"}
                        else:
                            return False, {"message": "비활성화된 라이선스"}
                except Exception as e:
                    self.logger.error(f"라이선스 데이터 파싱 실패: {e}")
                    # 기본적인 검증으로 폴백
                    if license_data.get("active", False):
                        return True, {
                            "valid": True,
                            "message": "라이선스 유효 (기본 검증)",
                        }
                    else:
                        return False, {"message": "라이선스 검증 실패"}

                # 캐시에 저장
                self._cache[license_key] = license_obj

                # 유효성 확인
                if not license_obj.is_valid():
                    if license_obj.status == LicenseStatus.EXPIRED:
                        return False, {"message": "만료된 라이선스입니다."}
                    elif license_obj.status == LicenseStatus.SUSPENDED:
                        return False, {"message": "일시 정지된 라이선스입니다."}
                    elif license_obj.status == LicenseStatus.REVOKED:
                        return False, {"message": "취소된 라이선스입니다."}
                    else:
                        return False, {"message": "비활성화된 라이선스입니다."}

                # 하드웨어 검증 및 등록
                return self._validate_hardware(license_obj, hardware_id)

            except Exception as e:
                self.logger.error(f"라이선스 검증 오류: {str(e)}")
                return False, {"message": f"라이선스 검증 중 오류: {str(e)}"}

        try:
            # 타임아웃 적용하여 검증
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(verify_worker)
                return future.result(timeout=self.timeout)

        except concurrent.futures.TimeoutError:
            self.logger.warning("라이선스 검증 타임아웃")
            return False, {"message": "라이선스 검증 타임아웃"}
        except Exception as e:
            self.logger.error(f"라이선스 검증 중 오류: {str(e)}")
            return False, {"message": f"라이선스 검증 중 오류: {str(e)}"}

    def _validate_hardware(
        self, license_obj: License, hardware_id: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """하드웨어 검증 (간소화)"""
        try:
            # 간단한 하드웨어 검증
            if not license_obj.hardware_id:
                # 첫 사용 - 하드웨어 ID 등록 시도
                try:
                    self._register_hardware(license_obj.license_key, hardware_id)
                    license_obj.hardware_id = hardware_id
                except:
                    # 등록 실패해도 진행
                    pass

            elif license_obj.hardware_id != hardware_id:
                # 다른 하드웨어인 경우 경고하지만 허용 (개발 중)
                self.logger.warning("다른 하드웨어에서 접속")

            # 성공 응답
            response = {
                "valid": True,
                "license_type": (
                    license_obj.license_type.value
                    if hasattr(license_obj.license_type, "value")
                    else "professional"
                ),
                "features": license_obj.features,
                "expires_at": (
                    license_obj.expires_at.isoformat()
                    if license_obj.expires_at
                    else None
                ),
                "customer_email": license_obj.customer_email,
                "customer_id": license_obj.customer_id,
            }

            return True, response

        except Exception as e:
            self.logger.error(f"하드웨어 검증 오류: {str(e)}")
            # 오류 발생해도 허용 (개발 모드)
            return True, {
                "valid": True,
                "license_type": "professional",
                "features": {
                    "blog_management": True,
                    "auto_comment": True,
                    "auto_like": True,
                },
                "message": "검증 오류, 기본 권한으로 진행",
            }

    def _register_hardware(self, license_key: str, hardware_id: str):
        """하드웨어 ID 등록 (타임아웃 적용)"""
        if self._offline_mode or not self.db:
            return

        def register_worker():
            try:
                doc_ref = self.db.collection("licenses").document(license_key)
                doc_ref.update(
                    {
                        "hardware_id": hardware_id,
                        "first_used": datetime.now().isoformat(),
                        "last_used": datetime.now().isoformat(),
                    }
                )
            except Exception as e:
                self.logger.error(f"하드웨어 등록 실패: {e}")

        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(register_worker)
                future.result(timeout=5)  # 5초 타임아웃
        except:
            # 등록 실패해도 무시
            pass

    def _verify_offline(
        self, license_key: str, hardware_id: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """오프라인 검증 (개발 모드)"""
        # 개발용 키들
        dev_keys = ["OFFLINE-DEV-LICENSE", "DEV-MODE", "DEVELOPMENT", "TEST-LICENSE"]

        if license_key in dev_keys or len(license_key) > 10:
            return True, {
                "valid": True,
                "offline_mode": True,
                "message": "개발자 오프라인 모드",
                "features": {
                    "blog_management": True,
                    "auto_comment": True,
                    "auto_like": True,
                    "ai_comment": True,
                    "scheduling": True,
                    "multi_profile": True,
                },
                "license_type": "professional",
            }

        # 오프라인 캐시 확인
        cache_file = os.path.join(
            os.path.expanduser("~"), ".naver_blog_automation", ".license_cache"
        )

        try:
            if os.path.exists(cache_file):
                with open(cache_file, "r") as f:
                    cache_data = json.load(f)

                if license_key in cache_data:
                    cached_license = cache_data[license_key]
                    return True, {
                        "valid": True,
                        "offline_mode": True,
                        "message": "오프라인 캐시",
                        "features": cached_license.get("features", {}),
                        "license_type": cached_license.get("license_type", "basic"),
                    }
        except Exception as e:
            self.logger.error(f"오프라인 캐시 읽기 실패: {e}")

        return False, {"message": "오프라인 모드에서는 인증할 수 없습니다."}

    def generate_license(self, customer_email: str, days: int = 365) -> Optional[str]:
        """라이선스 생성 (관리자용) - 간소화"""
        if self._offline_mode:
            self.logger.error("오프라인 모드에서는 라이선스를 생성할 수 없습니다.")
            return None

        try:
            # 간단한 라이선스 키 생성
            license_key = self._generate_license_key()

            # Firestore에 저장 (타임아웃 적용)
            def create_worker():
                doc_ref = self.db.collection("licenses").document(license_key)
                doc_ref.set(
                    {
                        "customer_email": customer_email,
                        "active": True,
                        "created_at": datetime.now().isoformat(),
                        "expires_at": (
                            (datetime.now() + timedelta(days=days)).isoformat()
                            if days > 0
                            else None
                        ),
                    }
                )
                return license_key

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(create_worker)
                return future.result(timeout=self.timeout)

        except Exception as e:
            self.logger.error(f"라이선스 생성 실패: {str(e)}")
            return None

    def _generate_license_key(self) -> str:
        """라이선스 키 생성"""
        import string
        import random

        chars = string.ascii_uppercase + string.digits
        segments = []

        for _ in range(4):
            segment = "".join(random.choices(chars, k=4))
            segments.append(segment)

        return "-".join(segments)
