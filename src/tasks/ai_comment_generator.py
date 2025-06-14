"""
AI 기반 댓글 생성기 (비동기 지원)
"""

import os
import json
import random
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

import anthropic
from anthropic import Anthropic, AsyncAnthropic, APIError


class CommentStyle(Enum):
    """댓글 스타일"""

    FRIENDLY = "친근함"
    PROFESSIONAL = "전문적"
    CASUAL = "캐주얼"
    SUPPORTIVE = "응원"
    ANALYTICAL = "분석적"
    QUESTION = "질문형"


@dataclass
class PostContent:
    """포스트 내용"""

    title: str
    content: str
    author: str = ""
    category: str = ""
    tags: List[str] = None
    url: str = ""

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def get_summary(self, max_length: int = 500) -> str:
        """요약 텍스트 반환"""
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."


class AICommentGenerator:
    """AI 기반 댓글 생성기 (동기/비동기 지원)"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Anthropic API 키 (None이면 환경변수에서 가져옴)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = None
        self.async_client = None
        self.logger = logging.getLogger(__name__)
        self.cache = {}  # 간단한 캐시
        self.template_fallback = self._load_fallback_templates()

        if self.api_key:
            try:
                self.client = Anthropic(api_key=self.api_key)
                self.async_client = AsyncAnthropic(api_key=self.api_key)
                self.logger.info("Anthropic API 클라이언트 초기화 성공")
            except Exception as e:
                self.logger.error(f"Anthropic API 초기화 실패: {e}")

    def _load_fallback_templates(self) -> Dict[CommentStyle, List[str]]:
        """폴백 템플릿 로드"""
        return {
            CommentStyle.FRIENDLY: [
                "좋은 글 잘 읽었습니다! 😊",
                "유익한 정보 감사합니다!",
                "오늘도 좋은 글 감사해요~",
                "항상 좋은 내용 공유해주셔서 감사합니다!",
                "도움이 많이 되었어요! 감사합니다 :)",
            ],
            CommentStyle.PROFESSIONAL: [
                "좋은 정보 감사합니다.",
                "유익한 내용이네요. 참고하겠습니다.",
                "도움이 되는 글입니다.",
                "잘 정리된 내용 감사합니다.",
                "좋은 인사이트를 얻었습니다.",
            ],
            CommentStyle.CASUAL: [
                "오 이거 진짜 유용하네요!",
                "와 감사합니다!!",
                "이런 정보 찾고 있었는데 감사해요!",
                "대박 꿀팁이네요 ㅎㅎ",
                "완전 도움됐어요!!",
            ],
            CommentStyle.SUPPORTIVE: [
                "항상 응원합니다! 화이팅!",
                "좋은 글 감사합니다! 앞으로도 기대할게요!",
                "오늘도 좋은 하루 되세요! 😊",
                "블로그 자주 들를게요! 화이팅!",
                "멋진 글이에요! 계속 응원할게요!",
            ],
        }

    async def generate_comment_async(
        self,
        title: str,
        content: str,
        style: CommentStyle = CommentStyle.FRIENDLY,
        max_length: int = 150,
        use_emoji: bool = True,
        personalized: bool = True,
    ) -> Optional[str]:
        """
        AI를 사용하여 댓글 생성 (비동기)

        Args:
            title: 포스트 제목
            content: 포스트 내용
            style: 댓글 스타일
            max_length: 최대 길이
            use_emoji: 이모지 사용 여부
            personalized: 개인화된 댓글 생성

        Returns:
            생성된 댓글 또는 None
        """
        post_content = PostContent(title=title, content=content)

        # API 키가 없으면 폴백 사용
        if not self.async_client:
            return await self._generate_fallback_comment_async(post_content, style)

        try:
            # 캐시 확인
            cache_key = f"{title}_{style.value}_{max_length}"
            if cache_key in self.cache:
                self.logger.debug("캐시된 댓글 사용")
                return self.cache[cache_key]

            # 프롬프트 생성
            prompt = self._create_prompt(
                post_content, style, max_length, use_emoji, personalized
            )

            # Claude API 호출 (비동기)
            response = await self.async_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=200,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}],
            )

            # 응답 추출
            comment = response.content[0].text.strip()

            # 후처리
            comment = self._post_process_comment(comment, max_length)

            # 캐시 저장
            self.cache[cache_key] = comment

            self.logger.info(f"AI 댓글 생성 성공: {len(comment)}자")
            return comment

        except APIError as e:
            self.logger.error(f"Anthropic API 오류: {e}")
            return await self._generate_fallback_comment_async(post_content, style)
        except Exception as e:
            self.logger.error(f"댓글 생성 중 오류: {e}")
            return await self._generate_fallback_comment_async(post_content, style)

    def generate_comment(
        self,
        post_content: PostContent,
        style: CommentStyle = CommentStyle.FRIENDLY,
        max_length: int = 150,
        use_emoji: bool = True,
        personalized: bool = True,
    ) -> Optional[str]:
        """
        AI를 사용하여 댓글 생성 (동기)

        Args:
            post_content: 포스트 내용
            style: 댓글 스타일
            max_length: 최대 길이
            use_emoji: 이모지 사용 여부
            personalized: 개인화된 댓글 생성

        Returns:
            생성된 댓글 또는 None
        """
        # API 키가 없으면 폴백 사용
        if not self.client:
            return self._generate_fallback_comment(post_content, style)

        try:
            # 캐시 확인
            cache_key = f"{post_content.title}_{style.value}_{max_length}"
            if cache_key in self.cache:
                self.logger.debug("캐시된 댓글 사용")
                return self.cache[cache_key]

            # 프롬프트 생성
            prompt = self._create_prompt(
                post_content, style, max_length, use_emoji, personalized
            )

            # Claude API 호출
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=200,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}],
            )

            # 응답 추출
            comment = response.content[0].text.strip()

            # 후처리
            comment = self._post_process_comment(comment, max_length)

            # 캐시 저장
            self.cache[cache_key] = comment

            self.logger.info(f"AI 댓글 생성 성공: {len(comment)}자")
            return comment

        except APIError as e:
            self.logger.error(f"Anthropic API 오류: {e}")
            return self._generate_fallback_comment(post_content, style)
        except Exception as e:
            self.logger.error(f"댓글 생성 중 오류: {e}")
            return self._generate_fallback_comment(post_content, style)

    def _create_prompt(
        self,
        post_content: PostContent,
        style: CommentStyle,
        max_length: int,
        use_emoji: bool,
        personalized: bool,
    ) -> str:
        """프롬프트 생성"""
        style_descriptions = {
            CommentStyle.FRIENDLY: "친근하고 따뜻한",
            CommentStyle.PROFESSIONAL: "전문적이고 정중한",
            CommentStyle.CASUAL: "캐주얼하고 편안한",
            CommentStyle.SUPPORTIVE: "응원하고 격려하는",
            CommentStyle.ANALYTICAL: "분석적이고 통찰력 있는",
            CommentStyle.QUESTION: "호기심 있고 질문하는",
        }

        style_desc = style_descriptions.get(style, "친근한")
        emoji_instruction = (
            "이모지를 적절히 사용하세요." if use_emoji else "이모지는 사용하지 마세요."
        )

        # 개인화 요소
        personalization = ""
        if personalized and post_content.title:
            personalization = (
                f"포스트 제목 '{post_content.title}'을 자연스럽게 언급하세요."
            )

        prompt = f"""다음 블로그 포스트에 대한 {style_desc} 댓글을 작성해주세요.

포스트 제목: {post_content.title}
포스트 내용 요약: {post_content.get_summary(300)}

요구사항:
- {style_desc} 톤으로 작성
- 최대 {max_length}자 이내
- 자연스럽고 진정성 있게
- {emoji_instruction}
- 블로그 주인을 격려하고 긍정적인 피드백 제공
- 구체적인 내용을 언급하여 실제로 읽은 것처럼 보이게
{personalization}

댓글만 작성하고 다른 설명은 하지 마세요."""

        return prompt

    def _post_process_comment(self, comment: str, max_length: int) -> str:
        """댓글 후처리"""
        # 앞뒤 공백 제거
        comment = comment.strip()

        # 따옴표 제거
        if comment.startswith('"') and comment.endswith('"'):
            comment = comment[1:-1]

        # 길이 제한
        if len(comment) > max_length:
            # 마지막 문장 단위로 자르기
            sentences = comment.split(".")
            result = ""
            for sentence in sentences:
                if len(result + sentence + ".") <= max_length:
                    result += sentence + "."
                else:
                    break
            comment = result.strip()

        # 마지막 문장부호 확인
        if comment and not comment[-1] in ".!?~":
            comment += "."

        return comment

    async def _generate_fallback_comment_async(
        self, post_content: PostContent, style: CommentStyle
    ) -> str:
        """폴백 템플릿 기반 댓글 생성 (비동기)"""
        # CPU 집약적인 작업이므로 별도 스레드에서 실행
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._generate_fallback_comment, post_content, style
        )

    def _generate_fallback_comment(
        self, post_content: PostContent, style: CommentStyle
    ) -> str:
        """폴백 템플릿 기반 댓글 생성"""
        self.logger.info("폴백 템플릿 사용")

        templates = self.template_fallback.get(
            style, self.template_fallback[CommentStyle.FRIENDLY]
        )
        base_comment = random.choice(templates)

        # 제목 기반 개인화
        if post_content.title:
            # 키워드 추출
            keywords = self._extract_keywords(post_content.title)

            # 키워드 기반 추가 문장
            keyword_comments = {
                "맛집": ["맛있어 보이네요!", "꼭 가보고 싶어요!"],
                "여행": ["멋진 곳이네요!", "여행 가고 싶어지네요~"],
                "요리": ["레시피 따라해볼게요!", "너무 맛있어 보여요!"],
                "리뷰": ["상세한 리뷰 감사합니다!", "구매에 도움이 되었어요!"],
                "일상": ["공감이 가네요~", "즐거운 일상이네요!"],
                "정보": ["유용한 정보 감사합니다!", "많이 배웠어요!"],
                "IT": ["좋은 기술 정보네요!", "개발에 도움이 될 것 같아요!"],
            }

            for keyword, comments in keyword_comments.items():
                if keyword in post_content.title.lower():
                    base_comment = f"{base_comment} {random.choice(comments)}"
                    break

        return base_comment

    def _extract_keywords(self, text: str) -> List[str]:
        """간단한 키워드 추출"""
        keywords = []
        keyword_patterns = [
            "맛집",
            "여행",
            "요리",
            "리뷰",
            "일상",
            "정보",
            "IT",
            "개발",
            "뷰티",
            "패션",
            "운동",
            "건강",
            "교육",
            "경제",
            "투자",
        ]

        text_lower = text.lower()
        for pattern in keyword_patterns:
            if pattern.lower() in text_lower:
                keywords.append(pattern)

        return keywords

    def analyze_comment_quality(
        self, comment: str, post_content: PostContent
    ) -> Dict[str, Any]:
        """댓글 품질 분석"""
        analysis = {
            "length": len(comment),
            "has_emoji": any(ord(char) > 127 for char in comment),
            "mentions_title": any(
                word in comment for word in post_content.title.split()
            ),
            "is_generic": self._is_generic_comment(comment),
            "sentiment": "positive",  # 간단한 감정 분석
            "quality_score": 0.0,
        }

        # 품질 점수 계산
        score = 50  # 기본 점수

        if analysis["length"] > 20:
            score += 10
        if analysis["length"] > 50:
            score += 10
        if analysis["has_emoji"]:
            score += 5
        if analysis["mentions_title"]:
            score += 20
        if not analysis["is_generic"]:
            score += 15

        analysis["quality_score"] = min(score, 100) / 100.0

        return analysis

    def _is_generic_comment(self, comment: str) -> bool:
        """일반적인 댓글인지 확인"""
        generic_phrases = [
            "좋은 글 감사합니다",
            "잘 보고 갑니다",
            "감사합니다",
            "좋은 정보 감사합니다",
            "잘 읽었습니다",
        ]

        comment_lower = comment.lower()
        return (
            any(phrase in comment_lower for phrase in generic_phrases)
            and len(comment) < 30
        )

    async def generate_batch_comments_async(
        self,
        post_contents: List[PostContent],
        style: CommentStyle = CommentStyle.FRIENDLY,
        variety: bool = True,
    ) -> List[str]:
        """여러 포스트에 대한 댓글 일괄 생성 (비동기)"""
        comments = []
        styles = [CommentStyle.FRIENDLY, CommentStyle.CASUAL, CommentStyle.SUPPORTIVE]
        style_index = 0

        # 동시 실행 제한
        semaphore = asyncio.Semaphore(3)  # 최대 3개 동시 실행

        async def generate_single(
            post: PostContent, current_style: CommentStyle
        ) -> str:
            async with semaphore:
                comment = await self.generate_comment_async(
                    post.title,
                    post.content,
                    style=current_style,
                    use_emoji=random.choice([True, False]) if variety else True,
                )

                # Rate limiting
                if self.async_client:
                    await asyncio.sleep(0.5)

                return comment or "좋은 글 감사합니다!"

        tasks = []
        for post in post_contents:
            if variety:
                current_style = styles[style_index % len(styles)]
                style_index += 1
            else:
                current_style = style

            task = generate_single(post, current_style)
            tasks.append(task)

        comments = await asyncio.gather(*tasks)
        return comments
