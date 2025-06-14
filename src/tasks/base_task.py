"""
기본 작업 클래스 - 모든 작업의 베이스
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime
import uuid
import asyncio
import logging


class TaskStatus(Enum):
    """작업 상태"""

    PENDING = "대기중"
    RUNNING = "실행중"
    COMPLETED = "완료"
    FAILED = "실패"
    CANCELLED = "취소됨"
    SKIPPED = "건너뜀"


class TaskType(Enum):
    """작업 타입"""

    LOGIN = "로그인"
    CHECK_POSTS = "이웃 새글 확인"
    WRITE_COMMENT = "댓글 작성"
    CLICK_LIKE = "좋아요 클릭"
    SCROLL_READ = "스크롤 읽기"
    WAIT = "대기"
    GOTO_URL = "URL 이동"
    CUSTOM = "사용자 정의"


class TaskResult:
    """작업 결과"""

    def __init__(
        self,
        success: bool,
        message: str = "",
        data: Any = None,
        error: Exception = None,
    ):
        self.success = success
        self.message = message
        self.data = data
        self.error = error
        self.timestamp = datetime.now()


class BaseTask(ABC):
    """기본 작업 추상 클래스"""

    def __init__(self, name: str = None):
        self.id = str(uuid.uuid4())
        self.type = self._get_task_type()
        self.name = name or self.type.value
        # description은 property로 구현됨 - 초기화 필요 없음
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[TaskResult] = None
        self.parameters: Dict[str, Any] = {}
        self.retry_count = 0
        self.max_retries = 3
        self.dependencies: List[str] = []  # 의존하는 작업 ID 목록

        # 의존성 주입을 위한 속성
        self.browser_manager = None
        self.config = None
        self.security_manager = None
        self.logger = None

    @abstractmethod
    def _get_task_type(self) -> TaskType:
        """작업 타입 반환 (서브클래스에서 구현)"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """작업 설명 (서브클래스에서 구현)"""
        pass

    @abstractmethod
    async def execute(
        self, browser_manager: Any, context: Dict[str, Any]
    ) -> TaskResult:
        """
        작업 실행 (비동기)

        Args:
            browser_manager: 브라우저 관리자
            context: 실행 컨텍스트 (이전 작업 결과 등)

        Returns:
            TaskResult: 작업 결과
        """
        pass

    @abstractmethod
    def validate_parameters(self) -> bool:
        """파라미터 검증"""
        pass

    @abstractmethod
    def get_estimated_duration(self) -> float:
        """예상 소요 시간 (초)"""
        pass

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        """필수 파라미터 정보 (선택적 구현)"""
        return {}

    async def run(self, browser_manager: Any, context: Dict[str, Any]) -> TaskResult:
        """
        작업 실행 래퍼 (재시도 로직 포함)

        Args:
            browser_manager: 브라우저 관리자
            context: 실행 컨텍스트

        Returns:
            TaskResult: 작업 결과
        """
        self.start()

        for attempt in range(self.max_retries + 1):
            try:
                # 파라미터 검증
                if not self.validate_parameters():
                    result = TaskResult(
                        success=False,
                        message="파라미터 검증 실패",
                        error=ValueError("Invalid parameters"),
                    )
                    self.complete(result)
                    return result

                # 작업 실행
                result = await self.execute(browser_manager, context)

                # 완료 처리
                self.complete(result)

                if result.success:
                    return result

                # 실패한 경우 재시도 확인
                if attempt < self.max_retries:
                    self.retry_count += 1
                    (
                        self.logger.warning(
                            f"작업 실패, 재시도 {self.retry_count}/{self.max_retries}: {result.message}"
                        )
                        if self.logger
                        else None
                    )

                    # 재시도 전 대기
                    await asyncio.sleep(2**attempt)  # 지수 백오프
                    continue
                else:
                    return result

            except asyncio.CancelledError:
                # 취소된 경우
                self.cancel()
                raise

            except Exception as e:
                # 예상치 못한 오류
                error_msg = f"작업 실행 중 오류: {str(e)}"

                if self.logger:
                    self.logger.error(error_msg, exc_info=True)

                result = TaskResult(success=False, message=error_msg, error=e)

                if attempt < self.max_retries:
                    self.retry_count += 1
                    await asyncio.sleep(2**attempt)
                    continue
                else:
                    self.complete(result)
                    return result

        # 여기에 도달하면 안 되지만, 안전장치
        result = TaskResult(
            success=False,
            message="최대 재시도 횟수 초과",
            error=RuntimeError("Max retries exceeded"),
        )
        self.complete(result)
        return result

    def can_execute(self, completed_tasks: List[str]) -> bool:
        """
        작업 실행 가능 여부 확인

        Args:
            completed_tasks: 완료된 작업 ID 목록

        Returns:
            bool: 실행 가능 여부
        """
        # 모든 의존성이 완료되었는지 확인
        for dep_id in self.dependencies:
            if dep_id not in completed_tasks:
                return False
        return True

    def set_parameters(self, **kwargs):
        """파라미터 설정 (개선된 버전)"""
        # 디버깅용 로깅
        if hasattr(self, "logger") and self.logger:
            self.logger.debug(f"파라미터 설정 전: {self.parameters}")
            self.logger.debug(f"설정할 파라미터: {kwargs}")

        # 파라미터 하나씩 처리
        for key, value in kwargs.items():
            # None 값 처리
            if value is None:
                # 기본값이 있는지 확인
                if hasattr(self, "get_required_parameters"):
                    try:
                        required_params = self.get_required_parameters()
                        if key in required_params:
                            default_value = required_params[key].get("default")
                            if default_value is not None:
                                self.parameters[key] = default_value
                                continue
                    except:
                        pass

                # 기본값이 없으면 None으로 설정
                self.parameters[key] = None
                continue

            # 빈 문자열 처리
            if isinstance(value, str) and not value.strip():
                # 필수 파라미터인지 확인
                if hasattr(self, "get_required_parameters"):
                    try:
                        required_params = self.get_required_parameters()
                        if key in required_params and required_params[key].get(
                            "required", False
                        ):
                            # 필수 파라미터는 빈 문자열 허용하지 않음
                            default_value = required_params[key].get("default", "")
                            self.parameters[key] = default_value
                            continue
                    except:
                        pass

                # 빈 문자열 그대로 설정
                self.parameters[key] = value
                continue

            # 타입 검증 및 변환
            converted_value = self._convert_parameter_value(key, value)
            self.parameters[key] = converted_value

        # 디버깅용 로깅
        if hasattr(self, "logger") and self.logger:
            self.logger.debug(f"파라미터 설정 후: {self.parameters}")

    def _convert_parameter_value(self, param_name: str, value: Any) -> Any:
        """파라미터 값 타입 변환"""
        try:
            # 파라미터 정보 가져오기
            if hasattr(self, "get_required_parameters"):
                required_params = self.get_required_parameters()
                if param_name in required_params:
                    param_info = required_params[param_name]
                    param_type = param_info.get("type", "string")

                    # 타입별 변환
                    if param_type == "integer":
                        if isinstance(value, str):
                            value = value.strip()
                            if not value:
                                return param_info.get("default", 0)
                        return int(float(value))  # float을 거쳐 int로 변환

                    elif param_type == "float":
                        if isinstance(value, str):
                            value = value.strip()
                            if not value:
                                return param_info.get("default", 0.0)
                        return float(value)

                    elif param_type == "boolean":
                        if isinstance(value, str):
                            return value.lower() in ("true", "1", "yes", "on")
                        return bool(value)

                    elif param_type == "list":
                        if isinstance(value, list):
                            return value
                        elif isinstance(value, str):
                            if not value.strip():
                                return param_info.get("default", [])
                            # 줄바꿈으로 분할
                            return [
                                line.strip()
                                for line in value.split("\n")
                                if line.strip()
                            ]
                        else:
                            return param_info.get("default", [])

                    elif param_type == "choice":
                        str_value = str(value) if value is not None else ""
                        choices = param_info.get("choices", [])
                        if str_value in choices:
                            return str_value
                        else:
                            return param_info.get(
                                "default", choices[0] if choices else ""
                            )

            # 기본적으로 문자열로 변환
            return str(value) if value is not None else ""

        except Exception as e:
            # 변환 실패 시 기본값 또는 원본값 반환
            if hasattr(self, "logger") and self.logger:
                self.logger.warning(f"파라미터 '{param_name}' 변환 실패: {e}")

            # 기본값 찾기
            if hasattr(self, "get_required_parameters"):
                try:
                    required_params = self.get_required_parameters()
                    if param_name in required_params:
                        return required_params[param_name].get("default", value)
                except:
                    pass

            return value

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """파라미터 가져오기 (개선된 버전)"""
        value = self.parameters.get(key, default)

        # None인 경우 기본값 확인
        if value is None and hasattr(self, "get_required_parameters"):
            try:
                required_params = self.get_required_parameters()
                if key in required_params:
                    param_default = required_params[key].get("default")
                    if param_default is not None:
                        return param_default
            except:
                pass

        return value

    def get_parameter_info(self, param_name: str) -> Optional[Dict[str, Any]]:
        """파라미터 정보 가져오기"""
        if hasattr(self, "get_required_parameters"):
            try:
                required_params = self.get_required_parameters()
                return required_params.get(param_name)
            except:
                pass
        return None

    def validate_parameter(self, param_name: str, value: Any) -> bool:
        """개별 파라미터 검증"""
        try:
            param_info = self.get_parameter_info(param_name)
            if not param_info:
                return True  # 정보가 없으면 통과

            param_type = param_info.get("type", "string")
            required = param_info.get("required", False)

            # 필수 파라미터 확인
            if required and (
                value is None or (isinstance(value, str) and not value.strip())
            ):
                return False

            # 타입별 검증
            if param_type == "integer":
                try:
                    int_val = int(float(value))
                    min_val = param_info.get("min")
                    max_val = param_info.get("max")
                    if min_val is not None and int_val < min_val:
                        return False
                    if max_val is not None and int_val > max_val:
                        return False
                except (ValueError, TypeError):
                    return False

            elif param_type == "float":
                try:
                    float_val = float(value)
                    min_val = param_info.get("min")
                    max_val = param_info.get("max")
                    if min_val is not None and float_val < min_val:
                        return False
                    if max_val is not None and float_val > max_val:
                        return False
                except (ValueError, TypeError):
                    return False

            elif param_type == "choice":
                choices = param_info.get("choices", [])
                if choices and str(value) not in choices:
                    return False

            elif param_type == "list":
                if not isinstance(value, list):
                    return False

            return True

        except Exception as e:
            if hasattr(self, "logger") and self.logger:
                self.logger.error(f"파라미터 '{param_name}' 검증 중 오류: {e}")
            return False

    def get_missing_required_parameters(self) -> List[str]:
        """누락된 필수 파라미터 목록"""
        missing = []

        if hasattr(self, "get_required_parameters"):
            try:
                required_params = self.get_required_parameters()
                for param_name, param_info in required_params.items():
                    if param_info.get("required", False):
                        value = self.get_parameter(param_name)
                        if value is None or (
                            isinstance(value, str) and not value.strip()
                        ):
                            missing.append(param_name)
            except:
                pass

        return missing

    def has_valid_parameters(self) -> bool:
        """모든 파라미터가 유효한지 확인"""
        try:
            # 누락된 필수 파라미터 확인
            missing = self.get_missing_required_parameters()
            if missing:
                if hasattr(self, "logger") and self.logger:
                    self.logger.warning(f"누락된 필수 파라미터: {missing}")
                return False

            # 각 파라미터 검증
            for param_name, value in self.parameters.items():
                if not self.validate_parameter(param_name, value):
                    if hasattr(self, "logger") and self.logger:
                        self.logger.warning(f"잘못된 파라미터: {param_name}={value}")
                    return False

            return True

        except Exception as e:
            if hasattr(self, "logger") and self.logger:
                self.logger.error(f"파라미터 검증 중 오류: {e}")
            return False

    def start(self):
        """작업 시작"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

    def complete(self, result: TaskResult):
        """작업 완료"""
        self.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.result = result

    def cancel(self):
        """작업 취소"""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()

    def skip(self):
        """작업 건너뛰기"""
        self.status = TaskStatus.SKIPPED
        self.completed_at = datetime.now()

    def reset(self):
        """작업 리셋"""
        self.status = TaskStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.retry_count = 0

    def get_duration(self) -> Optional[float]:
        """실제 소요 시간 (초)"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "parameters": self.parameters,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration": self.get_duration(),
            "result": (
                {"success": self.result.success, "message": self.result.message}
                if self.result
                else None
            ),
            "dependencies": self.dependencies,
            "retry_count": self.retry_count,
        }

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id}, name={self.name}, status={self.status.value})>"
