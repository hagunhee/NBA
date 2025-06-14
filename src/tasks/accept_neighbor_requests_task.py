"""
받은 이웃신청 수락 작업
"""

import asyncio
import random
from typing import Dict, Any, List
from tasks.base_task import BaseTask, TaskType, TaskResult
from automation.naver_actions import NaverActions


class AcceptNeighborRequestsTask(BaseTask):
    """받은 이웃신청 수락 작업"""

    def __init__(self, name: str = "받은 이웃신청 수락"):
        super().__init__(name)
        self.parameters = {
            "max_accept": 20,  # 최대 수락 수
            "delay_min": 10,  # 최소 딜레이
            "delay_max": 20,  # 최대 딜레이
            "auto_save_posts": True,  # 게시글 저장 여부
        }

    def _get_task_type(self) -> TaskType:
        return TaskType.CUSTOM

    @property
    def description(self) -> str:
        return "받은 이웃신청을 자동으로 수락합니다."

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "max_accept": {
                "type": "integer",
                "description": "최대 수락할 이웃신청 수",
                "required": False,
                "default": 20,
                "min": 1,
                "max": 100,
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
            "auto_save_posts": {
                "type": "boolean",
                "description": "수락한 이웃의 게시글 자동 저장",
                "required": False,
                "default": True,
            },
        }

    def validate_parameters(self) -> bool:
        max_accept = self.get_parameter("max_accept", 20)
        delay_min = self.get_parameter("delay_min", 10)
        delay_max = self.get_parameter("delay_max", 20)

        try:
            max_accept = int(max_accept)
            delay_min = int(delay_min)
            delay_max = int(delay_max)

            if max_accept < 1:
                return False
            if delay_min < 5 or delay_max < delay_min:
                return False

            return True
        except (ValueError, TypeError):
            return False

    def get_estimated_duration(self) -> float:
        max_accept = self.get_parameter("max_accept", 20)
        avg_delay = (
            self.get_parameter("delay_min", 10) + self.get_parameter("delay_max", 20)
        ) / 2

        # 페이지 로딩 시간 + (평균 딜레이 * 수락 수)
        return 10 + (avg_delay * max_accept)

    async def execute(
        self, browser_manager: Any, context: Dict[str, Any]
    ) -> TaskResult:
        """이웃신청 수락 실행"""
        try:
            # 로그인 확인
            if not context.get("user_info", {}).get("logged_in", False):
                return TaskResult(success=False, message="로그인이 필요합니다.")

            # 파라미터 가져오기
            max_accept = int(self.get_parameter("max_accept", 20))
            delay_min = int(self.get_parameter("delay_min", 10))
            delay_max = int(self.get_parameter("delay_max", 20))
            auto_save = self.get_parameter("auto_save_posts", True)

            # 이웃 관리 페이지로 이동
            await self._navigate_to_neighbor_management(browser_manager)

            # 받은 신청 탭 클릭
            await self._click_received_requests_tab(browser_manager)

            # 대기 중인 신청 목록 가져오기
            pending_requests = await self._get_pending_requests(browser_manager)

            if not pending_requests:
                return TaskResult(
                    success=True,
                    message="대기 중인 이웃신청이 없습니다.",
                    data={"accepted_count": 0},
                )

            # 수락 처리
            accepted_count = 0
            accepted_neighbors = []

            for i, request in enumerate(pending_requests[:max_accept]):
                try:
                    # 수락 버튼 클릭
                    success = await self._accept_request(browser_manager, request)

                    if success:
                        accepted_count += 1
                        accepted_neighbors.append(
                            {
                                "blog_id": request.get("blog_id"),
                                "nickname": request.get("nickname"),
                                "accepted_at": asyncio.get_event_loop().time(),
                            }
                        )

                        # 게시글 저장 옵션
                        if auto_save and request.get("blog_url"):
                            await self._save_neighbor_post(
                                browser_manager, request["blog_url"]
                            )

                    # 다음 작업 전 딜레이
                    if i < len(pending_requests) - 1:
                        delay = random.uniform(delay_min, delay_max)
                        await asyncio.sleep(delay)

                except Exception as e:
                    self.logger.error(f"이웃신청 수락 중 오류: {e}")
                    continue

            # 컨텍스트 업데이트
            context["accepted_neighbors"] = accepted_neighbors

            return TaskResult(
                success=True,
                message=f"{accepted_count}개의 이웃신청을 수락했습니다.",
                data={
                    "accepted_count": accepted_count,
                    "accepted_neighbors": accepted_neighbors,
                    "total_pending": len(pending_requests),
                },
            )

        except Exception as e:
            return TaskResult(
                success=False, message=f"이웃신청 수락 중 오류: {str(e)}", error=e
            )

    async def _navigate_to_neighbor_management(self, browser_manager: Any):
        """이웃 관리 페이지로 이동"""
        # 네이버 블로그 이웃 관리 URL
        neighbor_url = "https://admin.blog.naver.com/BuddyListManage.nhn"

        if hasattr(browser_manager, "navigate_async"):
            await browser_manager.navigate_async(neighbor_url, wait_time=3)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, browser_manager.navigate, neighbor_url, 3)

    async def _click_received_requests_tab(self, browser_manager: Any):
        """받은 신청 탭 클릭"""
        # 탭 선택자 예시
        tab_selector = "a[href*='type=receive']"

        if hasattr(browser_manager, "click_async"):
            await browser_manager.click_async(tab_selector)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, browser_manager.click, tab_selector)

        await asyncio.sleep(2)

    async def _get_pending_requests(self, browser_manager: Any) -> List[Dict[str, Any]]:
        """대기 중인 이웃신청 목록 가져오기"""
        requests = []

        # 신청 목록 선택자
        request_selector = ".buddy_list_area .buddy_item"

        # 목록 가져오기
        if hasattr(browser_manager, "find_elements_async"):
            elements = await browser_manager.find_elements_async(request_selector)
        else:
            elements = browser_manager.find_elements(request_selector)

        for elem in elements:
            try:
                # 블로그 정보 추출
                blog_id = elem.get_attribute("data-blog-id")
                nickname = elem.find_element_by_css_selector(".nickname").text
                blog_url = elem.find_element_by_css_selector(
                    "a.blog_link"
                ).get_attribute("href")

                requests.append(
                    {
                        "element": elem,
                        "blog_id": blog_id,
                        "nickname": nickname,
                        "blog_url": blog_url,
                    }
                )
            except:
                continue

        return requests

    async def _accept_request(
        self, browser_manager: Any, request: Dict[str, Any]
    ) -> bool:
        """개별 이웃신청 수락"""
        try:
            # 수락 버튼 찾기
            accept_btn = request["element"].find_element_by_css_selector(".btn_accept")

            # 스크롤하여 보이게 하기
            browser_manager.scroll_to_element(accept_btn)
            await asyncio.sleep(0.5)

            # 클릭
            accept_btn.click()
            await asyncio.sleep(1)

            # 확인 팝업 처리 (있는 경우)
            try:
                confirm_btn = browser_manager.find_element(".btn_confirm", timeout=2)
                if confirm_btn:
                    confirm_btn.click()
                    await asyncio.sleep(1)
            except:
                pass

            return True

        except Exception as e:
            self.logger.error(f"수락 버튼 클릭 실패: {e}")
            return False

    async def _save_neighbor_post(self, browser_manager: Any, blog_url: str):
        """이웃 블로그 게시글 저장"""
        # 새 탭에서 블로그 열기
        original_window = browser_manager.driver.current_window_handle
        browser_manager.driver.execute_script(f"window.open('{blog_url}', '_blank');")

        # 새 탭으로 전환
        browser_manager.driver.switch_to.window(
            browser_manager.driver.window_handles[-1]
        )

        try:
            await asyncio.sleep(2)

            # 최신 게시글 찾기
            post_link = browser_manager.find_element(".post_link", timeout=3)
            if post_link:
                post_link.click()
                await asyncio.sleep(2)

                # 저장 버튼 클릭
                save_btn = browser_manager.find_element(".btn_save", timeout=2)
                if save_btn:
                    save_btn.click()
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.debug(f"게시글 저장 실패: {e}")
        finally:
            # 탭 닫고 원래 탭으로 돌아가기
            browser_manager.driver.close()
            browser_manager.driver.switch_to.window(original_window)
