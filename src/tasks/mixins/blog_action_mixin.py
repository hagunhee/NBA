"""
블로그 액션 Mixin
서로이웃, 댓글, 공감 작업을 처리하는 공통 기능
"""

import asyncio
import random
from typing import Dict, Any, Optional
from tasks.ai_comment_generator import AICommentGenerator, CommentStyle
from automation.naver_actions import NaverActions


class BlogActionMixin:
    """블로그 액션 (서이추/댓글/공감) Mixin"""

    def get_action_parameters(self) -> Dict[str, Dict[str, Any]]:
        """액션 관련 파라미터 정의"""
        return {
            # 서로이웃 설정
            "neighbor_enabled": {
                "type": "boolean",
                "description": "서로이웃 사용",
                "required": False,
                "default": True,
            },
            "neighbor_max_count": {
                "type": "integer",
                "description": "서로이웃 최대 작업 수",
                "required": False,
                "default": 100,
                "min": 0,
                "max": 1000,
            },
            "neighbor_delay_min": {
                "type": "integer",
                "description": "서로이웃 최소 딜레이 (초)",
                "required": False,
                "default": 20,
                "min": 5,
                "max": 300,
            },
            "neighbor_delay_max": {
                "type": "integer",
                "description": "서로이웃 최대 딜레이 (초)",
                "required": False,
                "default": 60,
                "min": 10,
                "max": 600,
            },
            "neighbor_probability": {
                "type": "integer",
                "description": "서로이웃 작업 확률 (%)",
                "required": False,
                "default": 100,
                "min": 0,
                "max": 100,
            },
            # 댓글 설정
            "comment_enabled": {
                "type": "boolean",
                "description": "댓글 사용",
                "required": False,
                "default": True,
            },
            "comment_max_count": {
                "type": "integer",
                "description": "댓글 최대 작업 수",
                "required": False,
                "default": 100,
                "min": 0,
                "max": 1000,
            },
            "comment_delay_min": {
                "type": "integer",
                "description": "댓글 최소 딜레이 (초)",
                "required": False,
                "default": 30,
                "min": 10,
                "max": 300,
            },
            "comment_delay_max": {
                "type": "integer",
                "description": "댓글 최대 딜레이 (초)",
                "required": False,
                "default": 90,
                "min": 20,
                "max": 600,
            },
            "comment_probability": {
                "type": "integer",
                "description": "댓글 작업 확률 (%)",
                "required": False,
                "default": 50,
                "min": 0,
                "max": 100,
            },
            "comment_style": {
                "type": "choice",
                "description": "댓글 스타일",
                "required": False,
                "default": "친근함",
                "choices": ["친근함", "전문적", "캐주얼", "응원", "분석적", "질문형"],
            },
            "comment_use_ai": {
                "type": "boolean",
                "description": "AI 댓글 생성 사용",
                "required": False,
                "default": True,
            },
            # 공감 설정
            "like_enabled": {
                "type": "boolean",
                "description": "공감 사용",
                "required": False,
                "default": True,
            },
            "like_max_count": {
                "type": "integer",
                "description": "공감 최대 작업 수",
                "required": False,
                "default": 100,
                "min": 0,
                "max": 1000,
            },
            "like_delay_min": {
                "type": "integer",
                "description": "공감 최소 딜레이 (초)",
                "required": False,
                "default": 10,
                "min": 2,
                "max": 300,
            },
            "like_delay_max": {
                "type": "integer",
                "description": "공감 최대 딜레이 (초)",
                "required": False,
                "default": 20,
                "min": 5,
                "max": 600,
            },
            "like_probability": {
                "type": "integer",
                "description": "공감 작업 확률 (%)",
                "required": False,
                "default": 100,
                "min": 0,
                "max": 100,
            },
        }

    def init_action_counters(self):
        """액션 카운터 초기화"""
        self.neighbor_count = 0
        self.comment_count = 0
        self.like_count = 0

        # AI 댓글 생성기 초기화
        if self.get_parameter("comment_use_ai", True):
            try:
                self.ai_generator = AICommentGenerator()
            except:
                self.ai_generator = None

    async def perform_blog_actions(
        self,
        browser_manager: Any,
        blog: Dict[str, Any],
        context: Dict[str, Any],
        execution_order: List[str] = None,
    ) -> Dict[str, Any]:
        """블로그 액션 수행"""
        result = {
            "blog_url": blog.get("url"),
            "blog_author": blog.get("author"),
            "neighbor": False,
            "comment": False,
            "like": False,
            "actions_performed": [],
        }

        # 기본 실행 순서
        if execution_order is None:
            execution_order = ["서로이웃", "댓글", "공감"]

        # 각 액션 수행
        for action in execution_order:
            if action == "서로이웃" and await self._should_do_neighbor():
                if await self._perform_neighbor_action(browser_manager, blog):
                    result["neighbor"] = True
                    result["actions_performed"].append("서로이웃")
                    self.neighbor_count += 1
                    await self._apply_action_delay("neighbor")

            elif action == "댓글" and await self._should_do_comment():
                if await self._perform_comment_action(browser_manager, blog, context):
                    result["comment"] = True
                    result["actions_performed"].append("댓글")
                    self.comment_count += 1
                    await self._apply_action_delay("comment")

            elif action == "공감" and await self._should_do_like():
                if await self._perform_like_action(browser_manager, blog):
                    result["like"] = True
                    result["actions_performed"].append("공감")
                    self.like_count += 1
                    await self._apply_action_delay("like")

        return result

    async def _should_do_neighbor(self) -> bool:
        """서로이웃 작업 수행 여부"""
        if not self.get_parameter("neighbor_enabled", True):
            return False

        max_count = self.get_parameter("neighbor_max_count", 100)
        if self.neighbor_count >= max_count:
            return False

        probability = self.get_parameter("neighbor_probability", 100)
        return random.randint(1, 100) <= probability

    async def _should_do_comment(self) -> bool:
        """댓글 작업 수행 여부"""
        if not self.get_parameter("comment_enabled", True):
            return False

        max_count = self.get_parameter("comment_max_count", 100)
        if self.comment_count >= max_count:
            return False

        probability = self.get_parameter("comment_probability", 50)
        return random.randint(1, 100) <= probability

    async def _should_do_like(self) -> bool:
        """공감 작업 수행 여부"""
        if not self.get_parameter("like_enabled", True):
            return False

        max_count = self.get_parameter("like_max_count", 100)
        if self.like_count >= max_count:
            return False

        probability = self.get_parameter("like_probability", 100)
        return random.randint(1, 100) <= probability

    async def _perform_neighbor_action(
        self, browser_manager: Any, blog: Dict[str, Any]
    ) -> bool:
        """서로이웃 신청"""
        try:
            # 블로그 메인 페이지로 이동 (포스트가 아닌 경우)
            blog_main_url = self._get_blog_main_url(blog["url"])
            if blog_main_url != browser_manager.current_url:
                await browser_manager.navigate_async(blog_main_url, wait_time=2)

            # 서로이웃 신청 버튼 찾기
            neighbor_btn = browser_manager.find_element(
                ".btn_buddy_add, .add_buddy_btn, #addBuddyBtn", timeout=3
            )

            if neighbor_btn and neighbor_btn.is_displayed():
                # 이미 이웃인지 확인
                btn_text = neighbor_btn.text.lower()
                if "이웃" in btn_text and ("추가" in btn_text or "신청" in btn_text):
                    neighbor_btn.click()
                    await asyncio.sleep(1)

                    # 신청 메시지 입력
                    msg_input = browser_manager.find_element(
                        ".buddy_msg_textarea, #buddyMessageInput", timeout=2
                    )
                    if msg_input:
                        messages = [
                            "안녕하세요! 좋은 글 잘 보고 갑니다 :)",
                            "반갑습니다! 서로이웃 하면서 소통해요~",
                            "좋은 포스팅 감사합니다. 서로이웃 신청드려요!",
                            "자주 방문하겠습니다. 서로이웃 해요 :)",
                        ]
                        msg_input.clear()
                        msg_input.send_keys(random.choice(messages))
                        await asyncio.sleep(0.5)

                    # 확인 버튼
                    confirm_btn = browser_manager.find_element(
                        ".btn_confirm, .btn_ok, button[type='submit']", timeout=2
                    )
                    if confirm_btn:
                        confirm_btn.click()
                        await asyncio.sleep(1)
                        return True

        except Exception as e:
            logging.debug(f"서로이웃 신청 실패: {e}")

        return False

    async def _perform_comment_action(
        self, browser_manager: Any, blog: Dict[str, Any], context: Dict[str, Any]
    ) -> bool:
        """댓글 작성"""
        try:
            # 포스트 페이지인지 확인, 아니면 최신 포스트로 이동
            if "/PostView" not in browser_manager.current_url:
                latest_post = await self._navigate_to_latest_post(browser_manager)
                if not latest_post:
                    return False

            # 포스트 내용 수집
            post_content = await self._collect_post_content(browser_manager)
            if not post_content:
                return False

            # 스크롤하며 읽기 시뮬레이션
            await self._simulate_reading(
                browser_manager, duration=random.uniform(20, 40)
            )

            # 댓글 생성
            comment_text = await self._generate_comment(post_content, context)
            if not comment_text:
                return False

            # 댓글 작성
            naver = NaverActions(browser_manager)
            success = naver.write_comment(comment_text)

            if success:
                # 컨텍스트에 댓글 기록
                if "written_comments" not in context:
                    context["written_comments"] = []
                context["written_comments"].append(
                    {
                        "blog_url": blog["url"],
                        "comment": comment_text,
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                )

            return success

        except Exception as e:
            logging.debug(f"댓글 작성 실패: {e}")
            return False

    async def _perform_like_action(
        self, browser_manager: Any, blog: Dict[str, Any]
    ) -> bool:
        """공감 클릭"""
        try:
            # 포스트 페이지인지 확인
            if "/PostView" not in browser_manager.current_url:
                latest_post = await self._navigate_to_latest_post(browser_manager)
                if not latest_post:
                    return False

            # 약간의 스크롤
            await self._simulate_reading(
                browser_manager, duration=random.uniform(5, 10)
            )

            # 공감 클릭
            naver = NaverActions(browser_manager)
            return naver.click_like()

        except Exception as e:
            logging.debug(f"공감 클릭 실패: {e}")
            return False

    async def _apply_action_delay(self, action_type: str):
        """액션별 딜레이 적용"""
        delay_min = self.get_parameter(f"{action_type}_delay_min", 10)
        delay_max = self.get_parameter(f"{action_type}_delay_max", 20)

        delay = random.uniform(delay_min, delay_max)
        await asyncio.sleep(delay)

    async def _generate_comment(
        self, post_content: Dict[str, Any], context: Dict[str, Any]
    ) -> Optional[str]:
        """댓글 생성"""
        # AI 사용
        if (
            self.get_parameter("comment_use_ai", True)
            and hasattr(self, "ai_generator")
            and self.ai_generator
        ):
            try:
                style_str = self.get_parameter("comment_style", "친근함")
                style_map = {
                    "친근함": CommentStyle.FRIENDLY,
                    "전문적": CommentStyle.PROFESSIONAL,
                    "캐주얼": CommentStyle.CASUAL,
                    "응원": CommentStyle.SUPPORTIVE,
                    "분석적": CommentStyle.ANALYTICAL,
                    "질문형": CommentStyle.QUESTION,
                }
                style = style_map.get(style_str, CommentStyle.FRIENDLY)

                comment = await self.ai_generator.generate_comment_async(
                    title=post_content.get("title", ""),
                    content=post_content.get("content", ""),
                    style=style,
                    max_length=150,
                    use_emoji=True,
                    personalized=True,
                )

                if comment:
                    return comment

            except Exception as e:
                logging.debug(f"AI 댓글 생성 실패: {e}")

        # 템플릿 댓글
        return self._generate_template_comment(post_content)

    def _generate_template_comment(self, post_content: Dict[str, Any]) -> str:
        """템플릿 기반 댓글"""
        style = self.get_parameter("comment_style", "친근함")

        templates = {
            "친근함": [
                "좋은 글 잘 읽었습니다! 😊",
                "유익한 정보 감사합니다!",
                "오늘도 좋은 글 감사해요~",
                "공감하고 갑니다! 좋은 하루 되세요 :)",
            ],
            "전문적": [
                "좋은 정보 감사합니다.",
                "유익한 내용이네요. 참고하겠습니다.",
                "잘 정리된 내용 감사합니다.",
            ],
            "캐주얼": [
                "오 이거 진짜 유용하네요!",
                "와 감사합니다!!",
                "대박 꿀팁이네요 ㅎㅎ",
            ],
            "응원": [
                "항상 응원합니다! 화이팅!",
                "좋은 글 감사합니다! 앞으로도 기대할게요!",
                "블로그 자주 들를게요! 화이팅!",
            ],
        }

        style_templates = templates.get(style, templates["친근함"])
        return random.choice(style_templates)

    async def _navigate_to_latest_post(self, browser_manager: Any) -> Optional[str]:
        """최신 포스트로 이동"""
        try:
            # 포스트 목록에서 첫 번째 포스트 찾기
            post_link = browser_manager.find_element(
                "a[href*='/PostView'], .post_title a, .tit_h3 a", timeout=3
            )

            if post_link:
                post_url = post_link.get_attribute("href")
                await browser_manager.navigate_async(post_url, wait_time=2)
                return post_url

        except Exception as e:
            logging.debug(f"최신 포스트 이동 실패: {e}")

        return None

    async def _collect_post_content(
        self, browser_manager: Any
    ) -> Optional[Dict[str, Any]]:
        """포스트 내용 수집"""
        try:
            # NaverActions 활용
            naver = NaverActions(browser_manager)
            content_dict = naver.collect_post_content()

            if content_dict:
                return {
                    "title": content_dict.get("title", ""),
                    "content": content_dict.get("content", ""),
                }

        except Exception as e:
            logging.debug(f"포스트 내용 수집 실패: {e}")

        return None

    async def _simulate_reading(self, browser_manager: Any, duration: float = 30):
        """읽기 시뮬레이션"""
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration

        while asyncio.get_event_loop().time() < end_time:
            # 자연스러운 스크롤
            scroll_distance = random.randint(100, 300)
            browser_manager.scroll_by(0, scroll_distance)

            # 대기
            await asyncio.sleep(random.uniform(0.5, 2))

            # 가끔 위로 스크롤
            if random.random() < 0.2:
                browser_manager.scroll_by(0, -scroll_distance // 2)
                await asyncio.sleep(random.uniform(1, 3))

    def _get_blog_main_url(self, url: str) -> str:
        """블로그 메인 URL 추출"""
        # https://blog.naver.com/blogId/postNumber -> https://blog.naver.com/blogId
        if "blog.naver.com" in url:
            parts = url.split("/")
            if len(parts) >= 4:
                return f"https://blog.naver.com/{parts[3]}"
        return url

    def get_action_summary(self) -> Dict[str, int]:
        """액션 수행 요약"""
        return {
            "neighbor_count": self.neighbor_count,
            "comment_count": self.comment_count,
            "like_count": self.like_count,
            "total_actions": self.neighbor_count + self.comment_count + self.like_count,
        }
