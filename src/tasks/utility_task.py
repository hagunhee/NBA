"""
유틸리티 작업들
"""

import asyncio
import random
from typing import Any, Dict, List
from tasks.base_task import BaseTask, TaskType, TaskResult
from automation.browser_manager import BrowserManager, ScrollSpeed
from automation.naver_actions import NaverActions


class WaitTask(BaseTask):
    """대기 작업 (개선된 버전)"""

    def __init__(self, name: str = "대기"):
        super().__init__(name)
        # 기본 파라미터 명시적 설정
        self.parameters = {"duration": 10, "random_variance": 0.2}

    def _get_task_type(self) -> TaskType:
        return TaskType.WAIT

    @property
    def description(self) -> str:
        return "지정된 시간만큼 대기합니다."

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "duration": {
                "type": "integer",
                "description": "대기 시간 (초)",
                "required": True,
                "default": 10,
                "min": 1,
                "max": 600,
            },
            "random_variance": {
                "type": "float",
                "description": "랜덤 변동폭 (0~1)",
                "required": False,
                "default": 0.2,
                "min": 0.0,
                "max": 1.0,
            },
        }

    def validate_parameters(self) -> bool:
        """파라미터 검증 (개선된 버전)"""
        try:
            print(f"WaitTask 파라미터 검증 시작: {self.parameters}")

            # duration 검증
            duration = self.get_parameter("duration", 10)
            print(f"  duration 원본값: {duration} (타입: {type(duration)})")

            # 문자열인 경우 변환 시도
            if isinstance(duration, str):
                duration = duration.strip()
                if not duration:
                    print("  duration이 빈 문자열, 기본값 사용")
                    self.set_parameters(duration=10)
                    duration = 10
                else:
                    try:
                        duration = float(duration)
                        print(f"  duration 변환 성공: {duration}")
                    except ValueError:
                        print(f"  duration 변환 실패: {duration}")
                        return False

            # 숫자 타입 검증
            if not isinstance(duration, (int, float)):
                print(f"  duration이 숫자가 아님: {type(duration)}")
                return False

            # 범위 검증
            if duration <= 0:
                print(f"  duration이 0 이하: {duration}")
                return False

            # random_variance 검증
            variance = self.get_parameter("random_variance", 0.2)
            print(f"  random_variance 원본값: {variance} (타입: {type(variance)})")

            # 문자열인 경우 변환 시도
            if isinstance(variance, str):
                variance = variance.strip()
                if not variance:
                    print("  random_variance가 빈 문자열, 기본값 사용")
                    self.set_parameters(random_variance=0.2)
                    variance = 0.2
                else:
                    try:
                        variance = float(variance)
                        print(f"  random_variance 변환 성공: {variance}")
                    except ValueError:
                        print(f"  random_variance 변환 실패: {variance}")
                        return False

            # 숫자 타입 검증
            if not isinstance(variance, (int, float)):
                print(f"  random_variance가 숫자가 아님: {type(variance)}")
                return False

            # 범위 검증
            if variance < 0 or variance > 1:
                print(f"  random_variance가 0~1 범위 벗어남: {variance}")
                return False

            print("  WaitTask 파라미터 검증 성공")
            return True

        except Exception as e:
            print(f"  WaitTask 파라미터 검증 중 예외: {e}")
            if self.logger:
                self.logger.error(f"파라미터 검증 중 오류: {e}")
            return False

    def get_estimated_duration(self) -> float:
        duration = self.get_parameter("duration", 10)
        try:
            return float(duration)
        except (ValueError, TypeError):
            return 10.0

    async def execute(
        self, browser_manager: Any, context: Dict[str, Any]
    ) -> TaskResult:
        """대기 실행"""
        try:
            duration = self.get_parameter("duration", 10)
            variance = self.get_parameter("random_variance", 0.2)

            # 안전한 타입 변환
            try:
                duration = float(duration)
                variance = float(variance)
            except (ValueError, TypeError):
                return TaskResult(
                    success=False,
                    message="파라미터 타입 오류",
                    error=ValueError("Invalid parameter types"),
                )

            # 랜덤 변동 적용
            if variance > 0:
                min_duration = duration * (1 - variance)
                max_duration = duration * (1 + variance)
                actual_duration = random.uniform(min_duration, max_duration)
            else:
                actual_duration = duration

            print(f"대기 시작: {actual_duration:.1f}초")

            # 대기
            await asyncio.sleep(actual_duration)

            return TaskResult(
                success=True,
                message=f"{actual_duration:.1f}초 대기 완료",
                data={"actual_duration": actual_duration},
            )

        except asyncio.CancelledError:
            print("대기 작업이 취소되었습니다.")
            raise

        except Exception as e:
            print(f"대기 중 오류: {e}")
            return TaskResult(success=False, message=f"대기 중 오류: {str(e)}", error=e)


class LikeTask(BaseTask):
    """좋아요 클릭 작업"""

    def __init__(self, name: str = "좋아요 클릭"):
        super().__init__(name)

    def _get_task_type(self) -> TaskType:
        return TaskType.CLICK_LIKE

    @property
    def description(self) -> str:
        return "현재 포스트에 좋아요를 클릭합니다."

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "skip_if_already_liked": {
                "type": "boolean",
                "description": "이미 좋아요를 누른 경우 건너뛰기",
                "required": False,
                "default": True,
            },
        }

    def get_estimated_duration(self) -> float:
        return 5.0

    def validate_parameters(self) -> bool:
        return True  # 모든 파라미터가 선택적이므로 항상 유효

    async def execute(
        self, browser_manager: BrowserManager, context: Dict[str, Any]
    ) -> TaskResult:
        """좋아요 클릭 실행"""
        try:
            # NaverActions 인스턴스 생성 (동기 메서드이므로 executor 사용)
            naver = NaverActions(browser_manager)

            # 좋아요 클릭 (비동기 실행)
            if hasattr(browser_manager, "_run_in_executor"):
                success = await browser_manager._run_in_executor(naver.click_like)
            else:
                # 폴백: 동기 실행
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(None, naver.click_like)

            if success:
                # 통계 업데이트
                self._update_like_statistics(context)

                return TaskResult(
                    success=True, message="좋아요 클릭 완료", data={"liked": True}
                )
            else:
                skip_if_liked = self.get_parameter("skip_if_already_liked", True)

                return TaskResult(
                    success=skip_if_liked,  # 이미 좋아요인 경우 성공으로 처리 가능
                    message="좋아요 클릭 실패 또는 이미 좋아요를 누른 포스트",
                    data={"liked": False},
                )

        except Exception as e:
            return TaskResult(
                success=False, message=f"좋아요 클릭 중 오류: {str(e)}", error=e
            )

    def _update_like_statistics(self, context: Dict[str, Any]) -> None:
        """좋아요 통계 업데이트"""
        if "like_statistics" not in context:
            context["like_statistics"] = {"total_likes": 0}

        context["like_statistics"]["total_likes"] += 1


class ScrollReadTask(BaseTask):
    """스크롤 읽기 작업"""

    def __init__(self, name: str = "스크롤 읽기"):
        super().__init__(name)
        # 기본 파라미터 설정
        self.parameters = {
            "duration": 60,
            "scroll_speed": "MEDIUM",
            "pause_probability": 0.3,
        }

    def _get_task_type(self) -> TaskType:
        return TaskType.SCROLL_READ

    @property
    def description(self) -> str:
        return "포스트를 자연스럽게 스크롤하며 읽습니다."

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "duration": {
                "type": "integer",
                "description": "읽기 시간 (초)",
                "required": False,
                "default": 60,
                "min": 10,
                "max": 300,
            },
            "scroll_speed": {
                "type": "choice",
                "description": "스크롤 속도",
                "required": False,
                "default": "MEDIUM",
                "choices": ["SLOW", "MEDIUM", "FAST"],
            },
            "pause_probability": {
                "type": "float",
                "description": "일시정지 확률",
                "required": False,
                "default": 0.3,
                "min": 0.0,
                "max": 1.0,
            },
        }

    def get_estimated_duration(self) -> float:
        return float(self.get_parameter("duration", 60))

    def validate_parameters(self) -> bool:
        """파라미터 검증"""
        duration = self.get_parameter("duration", 60)
        try:
            duration = float(duration)
            if duration < 10:
                return False
        except (ValueError, TypeError):
            return False

        speed = self.get_parameter("scroll_speed", "MEDIUM")
        if not speed:  # 빈 문자열 체크
            self.set_parameters(scroll_speed="MEDIUM")
            speed = "MEDIUM"

        if speed not in ["SLOW", "MEDIUM", "FAST"]:
            return False

        pause_prob = self.get_parameter("pause_probability", 0.3)
        try:
            pause_prob = float(pause_prob)
            if pause_prob < 0 or pause_prob > 1:
                return False
        except (ValueError, TypeError):
            return False

        return True

    async def execute(
        self, browser_manager: BrowserManager, context: Dict[str, Any]
    ) -> TaskResult:
        """스크롤 읽기 실행"""
        try:
            duration = self.get_parameter("duration", 60)
            speed_str = self.get_parameter("scroll_speed", "MEDIUM")
            pause_prob = self.get_parameter("pause_probability", 0.3)

            # ScrollSpeed enum 변환
            speed = ScrollSpeed[speed_str]

            # 시작 시간
            start_time = asyncio.get_event_loop().time()
            end_time = start_time + duration

            # 스크롤 설정
            config = speed.value
            total_scrolled = 0

            while asyncio.get_event_loop().time() < end_time:
                # 스크롤 거리 계산
                distance = random.randint(
                    int(config["step"] * 0.8), int(config["step"] * 1.2)
                )

                # 스크롤 (비동기 메서드 사용)
                if hasattr(browser_manager, "scroll_by_async"):
                    await browser_manager.scroll_by_async(0, distance)
                else:
                    # 폴백: 동기 메서드를 비동기로 실행
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None, browser_manager.scroll_by, 0, distance
                    )

                total_scrolled += distance

                # 대기
                await asyncio.sleep(config["delay"])

                # 일시정지 (확률적)
                if random.random() < pause_prob:
                    pause_duration = random.uniform(1, 3)
                    await asyncio.sleep(pause_duration)

                # 가끔 위로 스크롤
                if random.random() < 0.2:
                    back_distance = distance // 2
                    if hasattr(browser_manager, "scroll_by_async"):
                        await browser_manager.scroll_by_async(0, -back_distance)
                    else:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            None, browser_manager.scroll_by, 0, -back_distance
                        )

                    total_scrolled -= back_distance
                    await asyncio.sleep(config["delay"] * 2)

                # 페이지 끝 확인
                try:
                    if hasattr(browser_manager, "execute_script_async"):
                        at_bottom = await browser_manager.execute_script_async(
                            "return (window.innerHeight + window.scrollY) >= document.body.offsetHeight - 100"
                        )
                    else:
                        loop = asyncio.get_event_loop()
                        at_bottom = await loop.run_in_executor(
                            None,
                            browser_manager.execute_script,
                            "return (window.innerHeight + window.scrollY) >= document.body.offsetHeight - 100",
                        )

                    if at_bottom:
                        # 페이지 끝에 도달하면 위로 스크롤
                        if hasattr(browser_manager, "scroll_by_async"):
                            await browser_manager.scroll_by_async(0, -300)
                        else:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                None, browser_manager.scroll_by, 0, -300
                            )
                        await asyncio.sleep(1)
                except:
                    # 스크립트 실행 실패시 무시
                    pass

            # 실제 소요 시간
            actual_duration = asyncio.get_event_loop().time() - start_time

            return TaskResult(
                success=True,
                message=f"{actual_duration:.1f}초 동안 읽기 완료",
                data={
                    "duration": actual_duration,
                    "total_scrolled": total_scrolled,
                    "scroll_speed": speed_str,
                },
            )

        except asyncio.CancelledError:
            raise

        except Exception as e:
            return TaskResult(
                success=False, message=f"스크롤 읽기 중 오류: {str(e)}", error=e
            )


class GoToUrlTask(BaseTask):
    """URL 이동 작업"""

    def __init__(self, name: str = "URL 이동"):
        super().__init__(name)

    def _get_task_type(self) -> TaskType:
        return TaskType.GOTO_URL

    @property
    def description(self) -> str:
        return "지정된 URL로 이동합니다."

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "type": "string",
                "description": "이동할 URL",
                "required": True,
                "default": "",
            },
            "wait_time": {
                "type": "integer",
                "description": "페이지 로드 대기 시간 (초)",
                "required": False,
                "default": 3,
                "min": 1,
                "max": 30,
            },
            "check_login": {
                "type": "boolean",
                "description": "이동 후 로그인 상태 확인",
                "required": False,
                "default": False,
            },
        }

    def get_estimated_duration(self) -> float:
        wait_time = self.get_parameter("wait_time", 3)
        return float(wait_time + 2)  # 이동 시간 + 대기 시간

    def validate_parameters(self) -> bool:
        """파라미터 검증"""
        url = self.get_parameter("url", "")

        # URL이 문자열인지만 확인 (빈 문자열도 허용)
        if not isinstance(url, str):
            return False

        # URL이 입력된 경우에만 형식 검증
        if url and not self._validate_url(url):
            return False

        wait_time = self.get_parameter("wait_time", 3)
        if not isinstance(wait_time, (int, float)) or wait_time < 1:
            return False

        return True

    async def execute(
        self, browser_manager: BrowserManager, context: Dict[str, Any]
    ) -> TaskResult:
        """URL 이동 실행"""
        try:
            url = self.get_parameter("url", "")
            if not url:
                return TaskResult(
                    success=False, message="이동할 URL이 지정되지 않았습니다."
                )

            # URL 검증
            if not self._validate_url(url):
                return TaskResult(success=False, message="잘못된 URL 형식입니다.")

            wait_time = self.get_parameter("wait_time", 3)
            check_login = self.get_parameter("check_login", False)

            # URL로 이동
            if hasattr(browser_manager, "navigate_async"):
                await browser_manager.navigate_async(url, wait_time=wait_time)
            else:
                # 폴백: 동기 메서드를 비동기로 실행
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, browser_manager.navigate, url, wait_time
                )

            # 로그인 상태 확인 (선택적)
            if check_login:
                naver = NaverActions(browser_manager)

                if hasattr(browser_manager, "_run_in_executor"):
                    logged_in = await browser_manager._run_in_executor(
                        naver.check_login_status
                    )
                else:
                    loop = asyncio.get_event_loop()
                    logged_in = await loop.run_in_executor(
                        None, naver.check_login_status
                    )

                if not logged_in:
                    return TaskResult(
                        success=False,
                        message="로그인이 필요한 페이지입니다.",
                        data={"url": url, "logged_in": False},
                    )

            # 현재 URL 확인
            if hasattr(browser_manager, "get_current_url_async"):
                current_url = await browser_manager.get_current_url_async()
            else:
                current_url = browser_manager.current_url

            # 포스트 URL인 경우 컨텍스트 업데이트
            if "blog.naver.com" in current_url and "/PostView" in current_url:
                context["current_post_url"] = current_url

            return TaskResult(
                success=True,
                message=f"이동 완료: {url}",
                data={"current_url": current_url},
            )

        except asyncio.CancelledError:
            raise

        except Exception as e:
            return TaskResult(
                success=False, message=f"URL 이동 중 오류: {str(e)}", error=e
            )

    def _validate_url(self, url: str) -> bool:
        """URL 검증"""
        import re

        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        return url_pattern.match(url) is not None


class LoopTask(BaseTask):
    """반복 작업 - 하위 작업들을 반복 실행"""

    def __init__(self, name: str = "반복 작업"):
        super().__init__(name)
        self.sub_tasks: List[BaseTask] = []

    def _get_task_type(self) -> TaskType:
        # 커스텀 타입으로 처리하거나 별도 타입 추가 가능
        return TaskType.CUSTOM

    @property
    def description(self) -> str:
        return "하위 작업들을 지정된 횟수만큼 반복 실행합니다."

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "repeat_count": {
                "type": "integer",
                "description": "반복 횟수",
                "required": False,
                "default": 1,
                "min": 1,
                "max": 100,
            },
            "delay_between": {
                "type": "float",
                "description": "반복 간 대기 시간 (초)",
                "required": False,
                "default": 2.0,
                "min": 0,
                "max": 60,
            },
            "continue_on_error": {
                "type": "boolean",
                "description": "에러 발생 시 계속 진행",
                "required": False,
                "default": True,
            },
        }

    def add_sub_task(self, task: BaseTask) -> None:
        """하위 작업 추가"""
        self.sub_tasks.append(task)

    def get_estimated_duration(self) -> float:
        """예상 실행 시간"""
        if not self.sub_tasks:
            return 0.0

        repeat_count = self.get_parameter("repeat_count", 1)
        delay_between = self.get_parameter("delay_between", 2.0)

        # 하위 작업들의 예상 시간 합계
        sub_duration = sum(task.get_estimated_duration() for task in self.sub_tasks)

        # 전체 시간 = (하위 작업 시간 * 반복 횟수) + (대기 시간 * (반복 횟수 - 1))
        total_duration = sub_duration * repeat_count
        if repeat_count > 1:
            total_duration += delay_between * (repeat_count - 1)

        return total_duration

    def validate_parameters(self) -> bool:
        """파라미터 검증"""
        repeat_count = self.get_parameter("repeat_count", 1)
        if not isinstance(repeat_count, int) or repeat_count < 1:
            return False

        delay_between = self.get_parameter("delay_between", 2.0)
        if not isinstance(delay_between, (int, float)) or delay_between < 0:
            return False

        return True

    async def execute(
        self, browser_manager: Any, context: Dict[str, Any]
    ) -> TaskResult:
        """반복 실행"""
        try:
            if not self.sub_tasks:
                return TaskResult(success=False, message="실행할 하위 작업이 없습니다.")

            repeat_count = self.get_parameter("repeat_count", 1)
            delay_between = self.get_parameter("delay_between", 2.0)
            continue_on_error = self.get_parameter("continue_on_error", True)

            total_executed = 0
            success_count = 0
            failed_tasks = []

            for i in range(repeat_count):
                # 반복 시작 로그
                context["current_loop"] = i + 1

                for task in self.sub_tasks:
                    try:
                        # 하위 작업 실행
                        result = await task.run(browser_manager, context)
                        total_executed += 1

                        if result.success:
                            success_count += 1
                        else:
                            failed_tasks.append(
                                {
                                    "task": task.name,
                                    "loop": i + 1,
                                    "error": result.message,
                                }
                            )

                            if not continue_on_error:
                                return TaskResult(
                                    success=False,
                                    message=f"반복 {i+1}에서 실패: {task.name}",
                                    data={
                                        "total_executed": total_executed,
                                        "success_count": success_count,
                                        "failed_tasks": failed_tasks,
                                        "completed_loops": i,
                                    },
                                )

                    except asyncio.CancelledError:
                        raise

                    except Exception as e:
                        total_executed += 1
                        failed_tasks.append(
                            {"task": task.name, "loop": i + 1, "error": str(e)}
                        )

                        if not continue_on_error:
                            raise

                # 다음 반복 전 대기
                if i < repeat_count - 1 and delay_between > 0:
                    await asyncio.sleep(delay_between)

            # 결과 생성
            all_success = len(failed_tasks) == 0

            return TaskResult(
                success=all_success,
                message=f"{repeat_count}회 반복 완료 - 성공: {success_count}/{total_executed}",
                data={
                    "total_executed": total_executed,
                    "success_count": success_count,
                    "failed_count": len(failed_tasks),
                    "failed_tasks": failed_tasks,
                    "loops_completed": repeat_count,
                },
            )

        except asyncio.CancelledError:
            raise

        except Exception as e:
            return TaskResult(
                success=False, message=f"반복 실행 중 오류: {str(e)}", error=e
            )
