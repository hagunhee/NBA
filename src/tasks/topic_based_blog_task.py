"""
주제별 블로그 작업 - 복합 작업
"""

import asyncio
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from tasks.base_task import BaseTask, TaskType, TaskResult
from automation.naver_actions import NaverActions


class TopicBasedBlogTask(BaseTask):
    """주제별 블로그 작업"""

    def __init__(self, name: str = "주제별 블로그 작업"):
        super().__init__(name)
        self.parameters = {
            # 기본 설정
            "topic": "문학/책",
            "post_days": 50,  # 최근 며칠 이내 포스트
            "execution_order": ["서로이웃", "댓글", "공감"],
            "target_type": "서로이웃",  # 종료 기준 타입
            "target_count": 10,  # 종료 기준 수
            # 작업 조건 (필터)
            "min_likes": 0,
            "max_likes": 1000,
            "min_comments": 0,
            "max_comments": 100,
            "min_posts": 10,
            "max_posts": 1000,
            "recent_post_days": 30,  # 최근 포스트 필터
            "min_neighbors": 10,
            "max_neighbors": 1000,
            "min_total_visitors": 100,
            "min_today_visitors": 0,
            "exclude_my_neighbors": True,
            "exclude_official_bloggers": False,
            "exclude_no_profile_image": False,
            # 서로이웃 설정
            "neighbor_enabled": True,
            "neighbor_max_count": 100,
            "neighbor_delay_min": 20,
            "neighbor_delay_max": 60,
            "neighbor_probability": 100,
            # 댓글 설정
            "comment_enabled": True,
            "comment_max_count": 100,
            "comment_delay_min": 30,
            "comment_delay_max": 90,
            "comment_probability": 50,
            # 공감 설정
            "like_enabled": True,
            "like_max_count": 100,
            "like_delay_min": 10,
            "like_delay_max": 20,
            "like_probability": 100,
        }

        # 내부 카운터
        self.neighbor_count = 0
        self.comment_count = 0
        self.like_count = 0

    def _get_task_type(self) -> TaskType:
        return TaskType.CUSTOM

    @property
    def description(self) -> str:
        return "주제별로 블로그를 검색하여 서로이웃, 댓글, 공감 작업을 수행합니다."

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "topic": {
                "type": "choice",
                "description": "검색할 주제",
                "required": True,
                "default": "문학/책",
                "choices": [
                    "문학/책",
                    "영화",
                    "미술/디자인",
                    "공연/전시",
                    "음악",
                    "드라마",
                    "스타/연예인",
                    "만화/애니",
                    "방송",
                    "일상/생각",
                    "육아/결혼",
                    "애완/반려동물",
                    "좋은글/이미지",
                    "패션/미용",
                    "인테리어/DIY",
                    "요리/레시피",
                    "상품리뷰",
                    "원예/재배",
                ],
            },
            "post_days": {
                "type": "integer",
                "description": "최근 며칠 이내 작성된 포스트",
                "required": False,
                "default": 50,
                "min": 1,
                "max": 365,
            },
            "target_type": {
                "type": "choice",
                "description": "종료 기준",
                "required": False,
                "default": "서로이웃",
                "choices": ["서로이웃", "댓글", "공감"],
            },
            "target_count": {
                "type": "integer",
                "description": "목표 작업 수",
                "required": False,
                "default": 10,
                "min": 1,
                "max": 1000,
            },
            # ... 나머지 파라미터들도 동일한 방식으로 정의
        }

    def validate_parameters(self) -> bool:
        # 기본 검증
        try:
            # 숫자 파라미터 검증
            numeric_params = [
                "post_days",
                "target_count",
                "min_likes",
                "max_likes",
                "min_comments",
                "max_comments",
                "min_posts",
                "max_posts",
                "min_neighbors",
                "max_neighbors",
                "min_total_visitors",
            ]

            for param in numeric_params:
                value = self.get_parameter(param)
                if value is not None:
                    int(value)

            # 확률 검증 (0-100)
            prob_params = [
                "neighbor_probability",
                "comment_probability",
                "like_probability",
            ]
            for param in prob_params:
                prob = int(self.get_parameter(param, 100))
                if prob < 0 or prob > 100:
                    return False

            return True

        except (ValueError, TypeError):
            return False

    def get_estimated_duration(self) -> float:
        # 대략적인 예상 시간 계산
        target_count = int(self.get_parameter("target_count", 10))
        avg_delay = 30  # 평균 딜레이

        return target_count * avg_delay * 3  # 3가지 작업

    async def execute(
        self, browser_manager: Any, context: Dict[str, Any]
    ) -> TaskResult:
        """주제별 블로그 작업 실행"""
        try:
            # 로그인 확인
            if not context.get("user_info", {}).get("logged_in", False):
                return TaskResult(success=False, message="로그인이 필요합니다.")

            # 초기화
            self.neighbor_count = 0
            self.comment_count = 0
            self.like_count = 0

            # 파라미터 로드
            topic = self.get_parameter("topic", "문학/책")
            target_type = self.get_parameter("target_type", "서로이웃")
            target_count = int(self.get_parameter("target_count", 10))

            # 주제별 블로그 검색
            blogs = await self._search_blogs_by_topic(browser_manager, topic)

            if not blogs:
                return TaskResult(
                    success=False,
                    message=f"'{topic}' 주제의 블로그를 찾을 수 없습니다.",
                )

            # 필터링
            filtered_blogs = await self._filter_blogs(browser_manager, blogs, context)

            if not filtered_blogs:
                return TaskResult(
                    success=False, message="조건에 맞는 블로그가 없습니다."
                )

            # 작업 실행
            processed_blogs = []

            for blog in filtered_blogs:
                # 목표 달성 확인
                if self._is_target_reached(target_type, target_count):
                    break

                # 블로그 작업 수행
                result = await self._process_blog(browser_manager, blog, context)

                if result["processed"]:
                    processed_blogs.append(result)

                # 작업 간 딜레이
                await asyncio.sleep(random.uniform(5, 10))

            # 결과 생성
            return TaskResult(
                success=True,
                message=self._create_result_message(),
                data={
                    "topic": topic,
                    "processed_blogs": len(processed_blogs),
                    "neighbor_count": self.neighbor_count,
                    "comment_count": self.comment_count,
                    "like_count": self.like_count,
                    "filtered_blogs": len(filtered_blogs),
                    "details": processed_blogs,
                },
            )

        except Exception as e:
            return TaskResult(
                success=False, message=f"주제별 블로그 작업 중 오류: {str(e)}", error=e
            )

    async def _search_blogs_by_topic(
        self, browser_manager: Any, topic: str
    ) -> List[Dict[str, Any]]:
        """주제별 블로그 검색"""
        blogs = []

        # 네이버 블로그 주제별 검색 URL
        search_url = f"https://section.blog.naver.com/BlogHome.naver?directoryNo={self._get_topic_directory_no(topic)}"

        # 페이지 이동
        if hasattr(browser_manager, "navigate_async"):
            await browser_manager.navigate_async(search_url, wait_time=3)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, browser_manager.navigate, search_url, 3)

        # 블로그 목록 수집
        blog_elements = browser_manager.find_elements(".blog_list_item")

        for elem in blog_elements:
            try:
                blog_info = {
                    "url": elem.find_element_by_css_selector("a").get_attribute("href"),
                    "title": elem.find_element_by_css_selector(".title").text,
                    "author": elem.find_element_by_css_selector(".author").text,
                    "date": self._parse_post_date(
                        elem.find_element_by_css_selector(".date").text
                    ),
                    "element": elem,
                }
                blogs.append(blog_info)
            except:
                continue

        return blogs

    async def _filter_blogs(
        self, browser_manager: Any, blogs: List[Dict[str, Any]], context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """블로그 필터링"""
        filtered = []

        # 날짜 필터
        post_days = int(self.get_parameter("post_days", 50))
        cutoff_date = datetime.now() - timedelta(days=post_days)

        # 내 이웃 목록 (필요한 경우)
        my_neighbors = []
        if self.get_parameter("exclude_my_neighbors", True):
            my_neighbors = await self._get_my_neighbors(browser_manager)

        for blog in blogs:
            # 날짜 체크
            if blog.get("date") and blog["date"] < cutoff_date:
                continue

            # 내 이웃 제외
            if self.get_parameter("exclude_my_neighbors", True):
                if blog["author"] in my_neighbors:
                    continue

            # 상세 정보 가져오기 (필요한 경우)
            if self._needs_detailed_filtering():
                blog_details = await self._get_blog_details(
                    browser_manager, blog["url"]
                )

                # 상세 필터링
                if not self._pass_detailed_filter(blog_details):
                    continue

                blog.update(blog_details)

            filtered.append(blog)

        return filtered

    async def _process_blog(
        self, browser_manager: Any, blog: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """개별 블로그 작업 수행"""
        result = {
            "blog_url": blog["url"],
            "blog_author": blog["author"],
            "processed": False,
            "neighbor": False,
            "comment": False,
            "like": False,
        }

        # 블로그로 이동
        if hasattr(browser_manager, "navigate_async"):
            await browser_manager.navigate_async(blog["url"], wait_time=2)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, browser_manager.navigate, blog["url"], 2)

        # 실행 순서에 따라 작업 수행
        execution_order = self.get_parameter(
            "execution_order", ["서로이웃", "댓글", "공감"]
        )

        for task_type in execution_order:
            if task_type == "서로이웃" and self._should_do_neighbor():
                if await self._send_neighbor_request(browser_manager):
                    result["neighbor"] = True
                    self.neighbor_count += 1
                    await self._apply_delay("neighbor")

            elif task_type == "댓글" and self._should_do_comment():
                if await self._write_comment(browser_manager, context):
                    result["comment"] = True
                    self.comment_count += 1
                    await self._apply_delay("comment")

            elif task_type == "공감" and self._should_do_like():
                if await self._click_like(browser_manager):
                    result["like"] = True
                    self.like_count += 1
                    await self._apply_delay("like")

        result["processed"] = result["neighbor"] or result["comment"] or result["like"]

        return result

    def _should_do_neighbor(self) -> bool:
        """서로이웃 작업 수행 여부"""
        if not self.get_parameter("neighbor_enabled", True):
            return False

        max_count = int(self.get_parameter("neighbor_max_count", 100))
        if self.neighbor_count >= max_count:
            return False

        probability = int(self.get_parameter("neighbor_probability", 100))
        return random.randint(1, 100) <= probability

    def _should_do_comment(self) -> bool:
        """댓글 작업 수행 여부"""
        if not self.get_parameter("comment_enabled", True):
            return False

        max_count = int(self.get_parameter("comment_max_count", 100))
        if self.comment_count >= max_count:
            return False

        probability = int(self.get_parameter("comment_probability", 50))
        return random.randint(1, 100) <= probability

    def _should_do_like(self) -> bool:
        """공감 작업 수행 여부"""
        if not self.get_parameter("like_enabled", True):
            return False

        max_count = int(self.get_parameter("like_max_count", 100))
        if self.like_count >= max_count:
            return False

        probability = int(self.get_parameter("like_probability", 100))
        return random.randint(1, 100) <= probability

    async def _send_neighbor_request(self, browser_manager: Any) -> bool:
        """서로이웃 신청"""
        try:
            # 서로이웃 신청 버튼 찾기
            neighbor_btn = browser_manager.find_element(".btn_neighbor_add", timeout=3)

            if neighbor_btn and neighbor_btn.is_displayed():
                neighbor_btn.click()
                await asyncio.sleep(1)

                # 신청 메시지 입력 (필요한 경우)
                msg_input = browser_manager.find_element(
                    ".neighbor_msg_input", timeout=2
                )
                if msg_input:
                    msg_input.send_keys("안녕하세요! 좋은 글 잘 보고 갑니다 :)")
                    await asyncio.sleep(0.5)

                # 확인 버튼
                confirm_btn = browser_manager.find_element(".btn_confirm", timeout=2)
                if confirm_btn:
                    confirm_btn.click()
                    await asyncio.sleep(1)

                return True

        except Exception as e:
            self.logger.debug(f"서로이웃 신청 실패: {e}")

        return False

    async def _write_comment(
        self, browser_manager: Any, context: Dict[str, Any]
    ) -> bool:
        """댓글 작성"""
        # WriteCommentTask를 활용하거나 직접 구현
        try:
            # 간단한 템플릿 댓글
            comments = [
                "좋은 글 잘 읽었습니다!",
                "유익한 정보 감사합니다 :)",
                "공감하고 갑니다!",
                "좋은 하루 되세요~",
            ]

            comment_text = random.choice(comments)

            # NaverActions 사용
            naver = NaverActions(browser_manager)
            return naver.write_comment(comment_text)

        except Exception as e:
            self.logger.debug(f"댓글 작성 실패: {e}")
            return False

    async def _click_like(self, browser_manager: Any) -> bool:
        """좋아요 클릭"""
        try:
            naver = NaverActions(browser_manager)
            if hasattr(browser_manager, "_run_in_executor"):
                return await browser_manager._run_in_executor(naver.click_like)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, naver.click_like)

        except Exception as e:
            self.logger.debug(f"좋아요 클릭 실패: {e}")
            return False

    async def _apply_delay(self, task_type: str):
        """작업별 딜레이 적용"""
        delay_min = int(self.get_parameter(f"{task_type}_delay_min", 10))
        delay_max = int(self.get_parameter(f"{task_type}_delay_max", 20))

        delay = random.uniform(delay_min, delay_max)
        await asyncio.sleep(delay)

    def _is_target_reached(self, target_type: str, target_count: int) -> bool:
        """목표 달성 여부 확인"""
        if target_type == "서로이웃":
            return self.neighbor_count >= target_count
        elif target_type == "댓글":
            return self.comment_count >= target_count
        elif target_type == "공감":
            return self.like_count >= target_count

        return False

    def _create_result_message(self) -> str:
        """결과 메시지 생성"""
        parts = []

        if self.neighbor_count > 0:
            parts.append(f"서로이웃 {self.neighbor_count}건")
        if self.comment_count > 0:
            parts.append(f"댓글 {self.comment_count}건")
        if self.like_count > 0:
            parts.append(f"공감 {self.like_count}건")

        if parts:
            return f"작업 완료: {', '.join(parts)}"
        else:
            return "작업을 수행하지 않았습니다."

    def _get_topic_directory_no(self, topic: str) -> int:
        """주제별 디렉토리 번호 매핑"""
        topic_map = {
            "문학/책": 6,
            "영화": 7,
            "미술/디자인": 8,
            "공연/전시": 11,
            "음악": 12,
            "드라마": 13,
            "스타/연예인": 14,
            "만화/애니": 15,
            "방송": 16,
            "일상/생각": 28,
            "육아/결혼": 29,
            "애완/반려동물": 30,
            "좋은글/이미지": 31,
            "패션/미용": 32,
            "인테리어/DIY": 33,
            "요리/레시피": 34,
            "상품리뷰": 35,
            "원예/재배": 36,
        }

        return topic_map.get(topic, 6)

    def _parse_post_date(self, date_text: str) -> Optional[datetime]:
        """포스트 날짜 파싱"""
        try:
            # "3시간 전", "어제", "2024.01.15" 등의 형식 처리
            if "시간 전" in date_text:
                hours = int(date_text.split("시간")[0])
                return datetime.now() - timedelta(hours=hours)
            elif "분 전" in date_text:
                minutes = int(date_text.split("분")[0])
                return datetime.now() - timedelta(minutes=minutes)
            elif "어제" in date_text:
                return datetime.now() - timedelta(days=1)
            else:
                return datetime.strptime(date_text, "%Y.%m.%d")
        except:
            return None

    def _needs_detailed_filtering(self) -> bool:
        """상세 필터링이 필요한지 확인"""
        # 좋아요, 댓글, 방문자 수 등의 필터가 설정되어 있으면 True
        return (
            self.get_parameter("min_likes", 0) > 0
            or self.get_parameter("max_likes", 1000) < 1000
            or self.get_parameter("min_comments", 0) > 0
            or self.get_parameter("max_comments", 100) < 100
            or self.get_parameter("min_neighbors", 10) > 10
            or self.get_parameter("min_total_visitors", 100) > 100
        )

    async def _get_blog_details(
        self, browser_manager: Any, blog_url: str
    ) -> Dict[str, Any]:
        """블로그 상세 정보 가져오기"""
        details = {}

        # 블로그 방문
        if hasattr(browser_manager, "navigate_async"):
            await browser_manager.navigate_async(blog_url, wait_time=2)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, browser_manager.navigate, blog_url, 2)

        try:
            # 이웃 수
            neighbor_elem = browser_manager.find_element(".neighbor_count", timeout=2)
            if neighbor_elem:
                details["neighbor_count"] = int(neighbor_elem.text.replace(",", ""))

            # 방문자 수
            visitor_elem = browser_manager.find_element(".visitor_count", timeout=2)
            if visitor_elem:
                details["total_visitors"] = int(visitor_elem.text.replace(",", ""))

            # 오늘 방문자
            today_elem = browser_manager.find_element(".today_visitor", timeout=2)
            if today_elem:
                details["today_visitors"] = int(today_elem.text.replace(",", ""))

            # 프로필 이미지 여부
            profile_img = browser_manager.find_element(".profile_image", timeout=1)
            details["has_profile_image"] = profile_img is not None

            # 공식 블로거 여부
            official_badge = browser_manager.find_element(".official_badge", timeout=1)
            details["is_official"] = official_badge is not None

        except Exception as e:
            self.logger.debug(f"블로그 상세 정보 가져오기 실패: {e}")

        return details

    def _pass_detailed_filter(self, blog_details: Dict[str, Any]) -> bool:
        """상세 필터 통과 여부"""
        # 이웃 수 필터
        neighbor_count = blog_details.get("neighbor_count", 0)
        min_neighbors = int(self.get_parameter("min_neighbors", 10))
        max_neighbors = int(self.get_parameter("max_neighbors", 1000))

        if neighbor_count < min_neighbors or neighbor_count > max_neighbors:
            return False

        # 방문자 수 필터
        total_visitors = blog_details.get("total_visitors", 0)
        min_total_visitors = int(self.get_parameter("min_total_visitors", 100))

        if total_visitors < min_total_visitors:
            return False

        # 오늘 방문자 필터
        today_visitors = blog_details.get("today_visitors", 0)
        min_today_visitors = int(self.get_parameter("min_today_visitors", 0))

        if today_visitors < min_today_visitors:
            return False

        # 공식 블로거 제외
        if self.get_parameter("exclude_official_bloggers", False):
            if blog_details.get("is_official", False):
                return False

        # 프로필 이미지 없는 블로그 제외
        if self.get_parameter("exclude_no_profile_image", False):
            if not blog_details.get("has_profile_image", True):
                return False

        return True

    async def _get_my_neighbors(self, browser_manager: Any) -> List[str]:
        """내 이웃 목록 가져오기"""
        neighbors = []

        try:
            # 이웃 목록 페이지로 이동
            neighbor_url = "https://m.blog.naver.com/BuddyList.naver"

            if hasattr(browser_manager, "navigate_async"):
                await browser_manager.navigate_async(neighbor_url, wait_time=2)
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, browser_manager.navigate, neighbor_url, 2
                )

            # 이웃 목록 수집
            neighbor_elements = browser_manager.find_elements(".buddy_nickname")

            for elem in neighbor_elements:
                neighbors.append(elem.text)

        except Exception as e:
            self.logger.debug(f"이웃 목록 가져오기 실패: {e}")

        return neighbors
