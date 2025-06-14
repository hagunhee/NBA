"""
무응답 이웃신청 취소 작업
"""

import asyncio
import random
from typing import Dict, Any, List
from datetime import datetime, timedelta
from tasks.base_task import BaseTask, TaskType, TaskResult


class CancelPendingNeighborRequestsTask(BaseTask):
    """무응답 이웃신청 취소 작업"""

    def __init__(self, name: str = "무응답 이웃신청 취소"):
        super().__init__(name)
        self.parameters = {
            "pending_days": 7,  # 며칠 이상 응답없으면 취소할지
            "max_cancel": 10,  # 최대 취소 수
            "delay_min": 10,
            "delay_max": 20,
        }

    def _get_task_type(self) -> TaskType:
        return TaskType.CUSTOM

    @property
    def description(self) -> str:
        return "일정 기간 응답이 없는 이웃신청을 취소합니다."

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "pending_days": {
                "type": "integer",
                "description": "응답 대기 기간 (일)",
                "required": False,
                "default": 7,
                "min": 3,
                "max": 30,
            },
            "max_cancel": {
                "type": "integer",
                "description": "최대 취소할 신청 수",
                "required": False,
                "default": 10,
                "min": 1,
                "max": 50,
            },
            "delay_min": {
                "type": "integer",
                "description": "작업 간 최소 딜레이 (초)",
                "required": False,
                "default": 10,
                "min": 5,
                "max": 60,
            },
            "delay_max": {
                "type": "integer",
                "description": "작업 간 최대 딜레이 (초)",
                "required": False,
                "default": 20,
                "min": 10,
                "max": 120,
            },
        }

    def validate_parameters(self) -> bool:
        try:
            pending_days = int(self.get_parameter("pending_days", 7))
            max_cancel = int(self.get_parameter("max_cancel", 10))
            delay_min = int(self.get_parameter("delay_min", 10))
            delay_max = int(self.get_parameter("delay_max", 20))

            if pending_days < 3 or max_cancel < 1:
                return False
            if delay_min < 5 or delay_max < delay_min:
                return False

            return True
        except (ValueError, TypeError):
            return False

    def get_estimated_duration(self) -> float:
        max_cancel = self.get_parameter("max_cancel", 10)
        avg_delay = (
            self.get_parameter("delay_min", 10) + self.get_parameter("delay_max", 20)
        ) / 2

        return 10 + (avg_delay * max_cancel)

    async def execute(
        self, browser_manager: Any, context: Dict[str, Any]
    ) -> TaskResult:
        """무응답 이웃신청 취소 실행"""
        try:
            # 로그인 확인
            if not context.get("user_info", {}).get("logged_in", False):
                return TaskResult(success=False, message="로그인이 필요합니다.")

            # 파라미터
            pending_days = int(self.get_parameter("pending_days", 7))
            max_cancel = int(self.get_parameter("max_cancel", 10))
            delay_min = int(self.get_parameter("delay_min", 10))
            delay_max = int(self.get_parameter("delay_max", 20))

            # 이웃 관리 페이지로 이동
            await self._navigate_to_sent_requests(browser_manager)

            # 보낸 신청 목록 가져오기
            sent_requests = await self._get_sent_requests(browser_manager)

            if not sent_requests:
                return TaskResult(
                    success=True,
                    message="보낸 이웃신청이 없습니다.",
                    data={"cancelled_count": 0},
                )

            # 오래된 신청 필터링
            cutoff_date = datetime.now() - timedelta(days=pending_days)
            old_requests = [
                req
                for req in sent_requests
                if req.get("sent_date") and req["sent_date"] < cutoff_date
            ]

            if not old_requests:
                return TaskResult(
                    success=True,
                    message=f"{pending_days}일 이상 된 대기 중인 신청이 없습니다.",
                    data={"cancelled_count": 0},
                )

            # 취소 처리
            cancelled_count = 0
            cancelled_list = []

            for i, request in enumerate(old_requests[:max_cancel]):
                try:
                    success = await self._cancel_request(browser_manager, request)

                    if success:
                        cancelled_count += 1
                        cancelled_list.append(
                            {
                                "blog_id": request.get("blog_id"),
                                "nickname": request.get("nickname"),
                                "sent_date": request.get("sent_date"),
                                "cancelled_at": datetime.now(),
                            }
                        )

                    # 딜레이
                    if i < len(old_requests) - 1:
                        delay = random.uniform(delay_min, delay_max)
                        await asyncio.sleep(delay)

                except Exception as e:
                    self.logger.error(f"신청 취소 중 오류: {e}")
                    continue

            return TaskResult(
                success=True,
                message=f"{cancelled_count}개의 무응답 이웃신청을 취소했습니다.",
                data={
                    "cancelled_count": cancelled_count,
                    "cancelled_list": cancelled_list,
                    "total_old_requests": len(old_requests),
                },
            )

        except Exception as e:
            return TaskResult(
                success=False,
                message=f"무응답 이웃신청 취소 중 오류: {str(e)}",
                error=e,
            )

    async def _navigate_to_sent_requests(self, browser_manager: Any):
        """보낸 신청 페이지로 이동"""
        # 이웃 관리 페이지의 보낸 신청 탭
        sent_url = "https://admin.blog.naver.com/BuddyListManage.nhn?type=send"

        if hasattr(browser_manager, "navigate_async"):
            await browser_manager.navigate_async(sent_url, wait_time=3)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, browser_manager.navigate, sent_url, 3)

    async def _get_sent_requests(self, browser_manager: Any) -> List[Dict[str, Any]]:
        """보낸 신청 목록 가져오기"""
        requests = []

        # 신청 목록 요소들
        request_elements = browser_manager.find_elements(".sent_request_item")

        for elem in request_elements:
            try:
                # 정보 추출
                blog_id = elem.get_attribute("data-blog-id")
                nickname = elem.find_element_by_css_selector(".nickname").text

                # 신청 날짜 파싱
                date_text = elem.find_element_by_css_selector(".request_date").text
                sent_date = self._parse_date(date_text)

                requests.append(
                    {
                        "element": elem,
                        "blog_id": blog_id,
                        "nickname": nickname,
                        "sent_date": sent_date,
                    }
                )
            except:
                continue

        return requests

    async def _cancel_request(
        self, browser_manager: Any, request: Dict[str, Any]
    ) -> bool:
        """개별 신청 취소"""
        try:
            # 취소 버튼 찾기
            cancel_btn = request["element"].find_element_by_css_selector(".btn_cancel")

            # 스크롤
            browser_manager.scroll_to_element(cancel_btn)
            await asyncio.sleep(0.5)

            # 클릭
            cancel_btn.click()
            await asyncio.sleep(1)

            # 확인 팝업 처리
            try:
                confirm_btn = browser_manager.find_element(".btn_confirm", timeout=2)
                if confirm_btn:
                    confirm_btn.click()
                    await asyncio.sleep(1)
            except:
                pass

            return True

        except Exception as e:
            self.logger.error(f"취소 버튼 클릭 실패: {e}")
            return False

    def _parse_date(self, date_text: str) -> datetime:
        """날짜 텍스트 파싱"""
        # "2024.01.15" 형식 등을 datetime으로 변환
        try:
            return datetime.strptime(date_text, "%Y.%m.%d")
        except:
            # 파싱 실패시 현재 날짜 반환
            return datetime.now()
