import time
import random
import logging
from typing import Dict, Any, Optional, List
from tasks.base_task import BaseTask, TaskType, TaskResult
from tasks.ai_comment_generator import AICommentGenerator, CommentStyle, PostContent
from automation.naver_actions import NaverActions
from bs4 import BeautifulSoup


class WriteCommentTask(BaseTask):
    """댓글 작성 작업 - AI 기능 통합"""

    def __init__(self, name: str = "댓글 작성"):
        super().__init__(name)

        # 기본 파라미터 - 모든 파라미터에 유효한 기본값 설정
        self.parameters = {
            "post_url": "",  # 특정 URL (없으면 컨텍스트에서)
            "comment_text": "",  # 댓글 내용 (없으면 자동 생성)
            "auto_generate": True,  # 자동 생성 여부
            "use_ai": True,  # AI 사용 여부
            "comment_style": "친근함",  # 댓글 스타일
            "use_emoji": True,  # 이모지 사용
            "personalized": True,  # 개인화된 댓글
            "max_comment_length": 150,  # 최대 댓글 길이
            "read_time_min": 30,  # 최소 읽기 시간 (초)
            "read_time_max": 90,  # 최대 읽기 시간 (초)
            "scroll_while_reading": True,  # 읽는 동안 스크롤
            "click_like_before_comment": True,  # 댓글 전 좋아요
            "analyze_content": True,  # 내용 분석 여부
            "avoid_duplicate": True,  # 중복 댓글 회피
        }

        # AI 댓글 생성기
        self.ai_generator = None
        self.logger = logging.getLogger(__name__)
        self.comment_history: List[str] = []

    def _get_task_type(self) -> TaskType:
        """작업 타입 반환"""
        return TaskType.WRITE_COMMENT

    @property
    def description(self) -> str:
        """작업 설명"""
        return "블로그 포스트에 댓글을 작성합니다."

    def initialize_ai_generator(self):
        """AI 생성기 초기화"""
        if not self.ai_generator and self.get_parameter("use_ai", True):
            try:
                self.ai_generator = AICommentGenerator()
                self.logger.info("AI 댓글 생성기 초기화 완료")
            except Exception as e:
                self.logger.error(f"AI 생성기 초기화 실패: {e}")
                self.ai_generator = None

    async def execute(
        self, browser_manager: Any, context: Dict[str, Any]
    ) -> TaskResult:
        """
        댓글 작성 실행

        Args:
            browser_manager: BrowserManager 인스턴스
            context: 실행 컨텍스트

        Returns:
            TaskResult: 실행 결과
        """
        try:
            # AI 생성기 초기화
            self.initialize_ai_generator()

            # 포스트 URL 결정
            post_url = self._get_post_url(context)
            if not post_url:
                return TaskResult(
                    success=False, message="댓글을 작성할 포스트가 없습니다."
                )

            # NaverActions 인스턴스 생성
            naver = NaverActions(browser_manager)

            # 포스트로 이동
            browser_manager.navigate(post_url, wait_time=3)

            # 포스트 내용 수집 (개선된 버전)
            post_content = self._collect_post_content(browser_manager, naver)
            if not post_content:
                return TaskResult(
                    success=False, message="포스트 내용을 읽을 수 없습니다."
                )

            # 포스트 읽기 시뮬레이션
            await self._simulate_reading(browser_manager, post_content)

            # 좋아요 클릭 (옵션)
            if self.get_parameter("click_like_before_comment", True):
                like_success = naver.click_like()
                if like_success:
                    time.sleep(random.uniform(1, 2))
                    self.logger.info("좋아요 클릭 완료")

            # 댓글 내용 준비
            comment_text = self._prepare_comment(post_content, context)
            if not comment_text:
                return TaskResult(
                    success=False, message="댓글 내용을 생성할 수 없습니다."
                )

            # 중복 확인
            if self.get_parameter("avoid_duplicate", True):
                if self._is_duplicate_comment(comment_text):
                    # 재생성 시도
                    self.logger.info("중복 댓글 감지, 재생성 시도")
                    comment_text = self._prepare_comment(
                        post_content, context, retry=True
                    )

            # 댓글 작성
            success = naver.write_comment(comment_text)

            if success:
                # 히스토리에 추가
                self.comment_history.append(comment_text)
                if len(self.comment_history) > 50:  # 최대 50개 유지
                    self.comment_history.pop(0)

                # 컨텍스트 업데이트
                self._update_context(context, post_url, comment_text)

                return TaskResult(
                    success=True,
                    message="댓글 작성 완료",
                    data={
                        "post_url": post_url,
                        "post_title": post_content.title,
                        "comment": comment_text,
                        "comment_length": len(comment_text),
                        "used_ai": bool(
                            self.ai_generator and self.get_parameter("use_ai", True)
                        ),
                    },
                )
            else:
                return TaskResult(success=False, message="댓글 작성에 실패했습니다.")

        except Exception as e:
            self.logger.error(f"댓글 작성 중 오류: {e}")
            return TaskResult(
                success=False, message=f"댓글 작성 중 오류 발생: {str(e)}"
            )

    def _collect_post_content(
        self, browser_manager: Any, naver: NaverActions
    ) -> Optional[PostContent]:
        """포스트 내용 수집 (개선된 버전)"""
        try:
            # BeautifulSoup 사용
            soup = browser_manager.get_page_soup()
            if not soup:
                # 기존 방식 폴백
                content_dict = naver.collect_post_content()
                if content_dict:
                    return PostContent(
                        title=content_dict.get("title", ""),
                        content=content_dict.get("content", ""),
                    )
                return None

            # iframe 내용 가져오기
            iframe_soup = None
            if browser_manager.switch_to_frame("mainFrame"):
                iframe_soup = browser_manager.get_page_soup()
                browser_manager.switch_to_default_content()

            # 제목 찾기
            title = ""
            title_selectors = [
                "h3.se-fs-",
                ".se-title-text",
                ".htitle",
                ".pcol1",
                ".se-module-text h1",
            ]

            for selector in title_selectors:
                if iframe_soup:
                    title_elem = iframe_soup.select_one(selector)
                else:
                    title_elem = soup.select_one(selector)

                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break

            # 본문 찾기
            content = ""
            content_selectors = [
                ".se-main-container",
                ".se-text-paragraph",
                "#postViewArea",
                ".post-view",
                ".post_ct",
            ]

            for selector in content_selectors:
                if iframe_soup:
                    content_elems = iframe_soup.select(selector)
                else:
                    content_elems = soup.select(selector)

                if content_elems:
                    content_parts = []
                    for elem in content_elems:
                        text = elem.get_text(strip=True)
                        if text:
                            content_parts.append(text)

                    content = "\n".join(content_parts)
                    if content:
                        break

            # 작성자 찾기
            author = ""
            author_selectors = [".writer", ".author", ".nick", ".blog_name"]

            for selector in author_selectors:
                author_elem = soup.select_one(selector)
                if author_elem:
                    author = author_elem.get_text(strip=True)
                    break

            # 카테고리 찾기
            category = ""
            category_elem = soup.select_one(".category, .blog_category")
            if category_elem:
                category = category_elem.get_text(strip=True)

            # 태그 찾기
            tags = []
            tag_elems = soup.select(".tag, .blog_tag, [rel='tag']")
            for tag_elem in tag_elems:
                tag = tag_elem.get_text(strip=True)
                if tag and tag not in tags:
                    tags.append(tag)

            # URL
            url = browser_manager.current_url

            if title and content:
                return PostContent(
                    title=title,
                    content=content[:3000],  # 최대 3000자
                    author=author,
                    category=category,
                    tags=tags,
                    url=url,
                )

            return None

        except Exception as e:
            self.logger.error(f"포스트 내용 수집 실패: {e}")
            return None

    async def _simulate_reading(self, browser_manager: Any, post_content: PostContent):
        """포스트 읽기 시뮬레이션 (개선된 버전)"""
        read_time_min = self.get_parameter("read_time_min", 30)
        read_time_max = self.get_parameter("read_time_max", 90)

        # 내용 길이에 따른 읽기 시간 조정
        content_length = len(post_content.content)
        if content_length > 2000:
            read_time_min = max(read_time_min, 45)
            read_time_max = max(read_time_max, 120)

        read_time = random.uniform(read_time_min, read_time_max)

        self.logger.info(f"포스트 읽기 시뮬레이션: {read_time:.1f}초")

        if self.get_parameter("scroll_while_reading", True):
            # 자연스러운 스크롤
            browser_manager.natural_scroll(duration=read_time, speed="medium")
        else:
            # 단순 대기
            time.sleep(read_time)

    def _prepare_comment(
        self, post_content: PostContent, context: Dict[str, Any], retry: bool = False
    ) -> str:
        """댓글 준비 (AI 통합)"""
        # 직접 지정된 댓글
        comment_text = self.get_parameter("comment_text")
        if comment_text and not retry:
            return comment_text

        # 자동 생성
        if self.get_parameter("auto_generate", True):
            # AI 사용
            if self.ai_generator and self.get_parameter("use_ai", True):
                return self._generate_ai_comment(post_content, retry)
            else:
                # 템플릿 기반
                return self._generate_template_comment(post_content, context)

        return ""

    def _generate_ai_comment(
        self, post_content: PostContent, retry: bool = False
    ) -> str:
        """AI 댓글 생성"""
        try:
            # 스타일 결정
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

            # retry 시 다른 스타일 시도
            if retry:
                styles = list(CommentStyle)
                styles.remove(style)
                style = random.choice(styles)

            # AI 댓글 생성
            comment = self.ai_generator.generate_comment(
                post_content,
                style=style,
                max_length=self.get_parameter("max_comment_length", 150),
                use_emoji=self.get_parameter("use_emoji", True),
                personalized=self.get_parameter("personalized", True),
            )

            if comment:
                # 품질 분석
                if self.get_parameter("analyze_content", True):
                    quality = self.ai_generator.analyze_comment_quality(
                        comment, post_content
                    )
                    self.logger.info(f"댓글 품질 점수: {quality['quality_score']:.2f}")

                    # 품질이 낮으면 재생성
                    if quality["quality_score"] < 0.5 and not retry:
                        self.logger.info("품질이 낮아 재생성 시도")
                        return self._generate_ai_comment(post_content, retry=True)

                return comment

        except Exception as e:
            self.logger.error(f"AI 댓글 생성 실패: {e}")

        # 폴백
        return self._generate_template_comment(post_content, {})

    def _generate_template_comment(
        self, post_content: PostContent, context: Dict[str, Any]
    ) -> str:
        """템플릿 기반 댓글 생성"""
        style = self.get_parameter("comment_style", "친근함")

        # 스타일별 템플릿
        templates = {
            "친근함": [
                "좋은 글 잘 읽었습니다! 😊",
                "유익한 정보 감사합니다!",
                f"{post_content.title} 정말 도움이 되었어요!",
                "오늘도 좋은 글 감사해요~",
                "항상 좋은 내용 공유해주셔서 감사합니다!",
            ],
            "전문적": [
                "좋은 정보 감사합니다.",
                "유익한 내용이네요. 참고하겠습니다.",
                "도움이 되는 글입니다.",
                "잘 정리된 내용 감사합니다.",
            ],
            "캐주얼": [
                "오 이거 진짜 유용하네요!",
                "와 감사합니다!!",
                "이런 정보 찾고 있었는데 감사해요!",
                "대박 꿀팁이네요 ㅎㅎ",
            ],
            "응원": [
                "항상 응원합니다! 화이팅!",
                "좋은 글 감사합니다! 앞으로도 기대할게요!",
                "오늘도 좋은 하루 되세요! 😊",
                "블로그 자주 들를게요! 화이팅!",
            ],
        }

        style_templates = templates.get(style, templates["친근함"])

        # 개인화
        if self.get_parameter("personalized", True):
            # 제목에 특정 키워드가 있으면 관련 댓글
            keyword_responses = self._get_keyword_responses(post_content)
            if keyword_responses:
                style_templates.extend(keyword_responses)

        # 랜덤 선택
        comment = random.choice(style_templates)

        # 이모지 제거 (옵션)
        if not self.get_parameter("use_emoji", True):
            comment = self._remove_emoji(comment)

        return comment

    def _get_keyword_responses(self, post_content: PostContent) -> List[str]:
        """키워드 기반 응답"""
        responses = []
        title_lower = post_content.title.lower()

        keyword_map = {
            "맛집": [
                "맛있어 보이네요! 꼭 가보고 싶어요!",
                "우와 너무 맛있어 보여요 😋",
            ],
            "여행": ["멋진 곳이네요! 저도 가보고 싶어요~", "여행 사진 너무 예뻐요!"],
            "요리": ["레시피 따라해볼게요!", "너무 맛있어 보여요! 레시피 감사합니다!"],
            "리뷰": ["상세한 리뷰 감사합니다!", "구매에 도움이 되었어요! 감사합니다."],
            "IT": ["좋은 기술 정보네요!", "개발에 도움이 될 것 같아요!"],
            "뷰티": ["좋은 제품 추천 감사해요!", "피부가 좋아질 것 같아요!"],
            "운동": ["운동 자극 받고 갑니다!", "오늘부터 저도 시작해볼게요!"],
        }

        for keyword, keyword_responses in keyword_map.items():
            if keyword in title_lower:
                responses.extend(keyword_responses)

        return responses

    def _remove_emoji(self, text: str) -> str:
        """이모지 제거"""
        import re

        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f1e0-\U0001f1ff"  # flags
            "\U00002702-\U000027b0"
            "\U000024c2-\U0001f251"
            "]+",
            flags=re.UNICODE,
        )

        return emoji_pattern.sub(r"", text).strip()

    def _is_duplicate_comment(self, comment: str) -> bool:
        """중복 댓글 확인"""
        # 정확히 같은 댓글
        if comment in self.comment_history:
            return True

        # 유사도 확인 (간단한 버전)
        comment_lower = comment.lower()
        for history_comment in self.comment_history[-10:]:  # 최근 10개만 확인
            if (
                len(set(comment_lower.split()) & set(history_comment.lower().split()))
                > 5
            ):
                return True

        return False

    def _get_post_url(self, context: Dict[str, Any]) -> Optional[str]:
        """포스트 URL 가져오기"""
        # 직접 지정된 URL 우선
        post_url = self.get_parameter("post_url")
        if post_url:
            return post_url

        # 컨텍스트에서 가져오기
        available_posts = context.get("available_posts", [])
        current_index = context.get("current_post_index", 0)

        if available_posts and current_index < len(available_posts):
            return available_posts[current_index]["url"]

        return None

    def _update_context(self, context: Dict[str, Any], post_url: str, comment: str):
        """컨텍스트 업데이트"""
        # 처리된 포스트 기록
        if "processed_posts" not in context:
            context["processed_posts"] = []

        context["processed_posts"].append(
            {"url": post_url, "comment": comment, "timestamp": time.time()}
        )

        # 다음 포스트로 인덱스 이동
        current_index = context.get("current_post_index", 0)
        context["current_post_index"] = current_index + 1

        # 댓글 통계
        if "comment_stats" not in context:
            context["comment_stats"] = {
                "total": 0,
                "ai_generated": 0,
                "template_based": 0,
            }

        context["comment_stats"]["total"] += 1

        if self.ai_generator and self.get_parameter("use_ai", True):
            context["comment_stats"]["ai_generated"] += 1
        else:
            context["comment_stats"]["template_based"] += 1

    def validate_parameters(self) -> bool:
        """파라미터 검증"""
        # 시간 파라미터 검증
        read_time_min = self.get_parameter("read_time_min", 30)
        read_time_max = self.get_parameter("read_time_max", 90)

        try:
            read_time_min = float(read_time_min)
            read_time_max = float(read_time_max)

            if read_time_min < 0 or read_time_max < read_time_min:
                return False
        except (ValueError, TypeError):
            return False

        # 댓글 스타일 검증
        valid_styles = ["친근함", "전문적", "캐주얼", "응원", "분석적", "질문형"]
        comment_style = self.get_parameter("comment_style", "친근함")

        # 빈 문자열인 경우 기본값으로 설정
        if not comment_style:
            self.set_parameters(comment_style="친근함")
            comment_style = "친근함"

        if comment_style not in valid_styles:
            return False

        # 댓글 길이 검증
        max_length = self.get_parameter("max_comment_length", 150)
        try:
            max_length = int(float(max_length))
            if max_length < 10 or max_length > 500:
                return False
        except (ValueError, TypeError):
            return False

        return True

    def get_estimated_duration(self) -> int:
        """예상 소요 시간 (초)"""
        read_time_min = self.get_parameter("read_time_min", 30)
        read_time_max = self.get_parameter("read_time_max", 90)
        avg_read_time = (read_time_min + read_time_max) / 2

        # 읽기 시간 + 댓글 작성 시간(약 10초) + AI 생성 시간(약 5초)
        ai_time = 5 if self.get_parameter("use_ai", True) else 0
        return int(avg_read_time + 10 + ai_time)

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        """필수 파라미터 정보"""
        return {
            "post_url": {
                "type": "string",
                "description": "댓글을 작성할 포스트 URL (비워두면 자동 선택)",
                "required": False,
                "default": "",
            },
            "comment_text": {
                "type": "string",
                "description": "댓글 내용 (비워두면 자동 생성)",
                "required": False,
                "default": "",
            },
            "auto_generate": {
                "type": "boolean",
                "description": "댓글 자동 생성 여부",
                "required": False,
                "default": True,
            },
            "use_ai": {
                "type": "boolean",
                "description": "AI 댓글 생성 사용",
                "required": False,
                "default": True,
            },
            "comment_style": {
                "type": "choice",
                "description": "댓글 스타일",
                "required": False,
                "default": "친근함",
                "choices": ["친근함", "전문적", "캐주얼", "응원", "분석적", "질문형"],
            },
            "use_emoji": {
                "type": "boolean",
                "description": "이모지 사용 여부",
                "required": False,
                "default": True,
            },
            "personalized": {
                "type": "boolean",
                "description": "개인화된 댓글 생성",
                "required": False,
                "default": True,
            },
            "max_comment_length": {
                "type": "integer",
                "description": "최대 댓글 길이",
                "required": False,
                "default": 150,
                "min": 10,
                "max": 500,
            },
            "read_time_min": {
                "type": "integer",
                "description": "최소 읽기 시간 (초)",
                "required": False,
                "default": 30,
                "min": 10,
            },
            "read_time_max": {
                "type": "integer",
                "description": "최대 읽기 시간 (초)",
                "required": False,
                "default": 90,
                "min": 10,
            },
            "scroll_while_reading": {
                "type": "boolean",
                "description": "읽는 동안 스크롤",
                "required": False,
                "default": True,
            },
            "click_like_before_comment": {
                "type": "boolean",
                "description": "댓글 작성 전 좋아요 클릭",
                "required": False,
                "default": True,
            },
            "analyze_content": {
                "type": "boolean",
                "description": "댓글 품질 분석",
                "required": False,
                "default": True,
            },
            "avoid_duplicate": {
                "type": "boolean",
                "description": "중복 댓글 회피",
                "required": False,
                "default": True,
            },
        }
