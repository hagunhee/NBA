import anthropic
import random
import json
import os
from datetime import datetime
from typing import Optional, List


class CommentGenerator:
    """Claude API를 사용한 자연스러운 댓글 생성"""

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Anthropic API 키
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.comment_history = self.load_comment_history()

        # 댓글 스타일 템플릿
        self.comment_styles = [
            "친근하고 따뜻한",
            "전문적이고 정중한",
            "유머러스하고 재미있는",
            "공감하고 격려하는",
            "호기심 많고 질문하는",
        ]

    def load_comment_history(self) -> List[dict]:
        """이전 댓글 기록 불러오기"""
        history_file = "comment_history.json"
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_comment_history(self, post_url: str, comment: str):
        """댓글 기록 저장"""
        self.comment_history.append(
            {
                "post_url": post_url,
                "comment": comment,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # 최근 1000개만 유지
        if len(self.comment_history) > 1000:
            self.comment_history = self.comment_history[-1000:]

        with open("comment_history.json", "w", encoding="utf-8") as f:
            json.dump(self.comment_history, f, ensure_ascii=False, indent=2)

    def generate_comment(
        self, post_title: str, post_content: str, post_url: str = None
    ) -> Optional[str]:
        """
        블로그 포스트에 대한 자연스러운 댓글 생성

        Args:
            post_title: 포스트 제목
            post_content: 포스트 본문 내용
            post_url: 포스트 URL (선택사항)

        Returns:
            생성된 댓글 텍스트 또는 None
        """
        try:
            # 본문이 너무 길면 요약
            content_preview = (
                post_content[:1500] if len(post_content) > 1500 else post_content
            )

            # 랜덤 스타일 선택
            style = random.choice(self.comment_styles)

            # 최근 댓글 몇 개를 컨텍스트로 제공 (중복 방지)
            recent_comments = self.comment_history[-5:] if self.comment_history else []
            recent_comments_text = "\n".join(
                [f"- {comment['comment']}" for comment in recent_comments]
            )

            # Claude에게 보낼 프롬프트
            prompt = f"""
            당신은 네이버 블로그를 즐겨 읽는 일반 독자입니다. 다음 블로그 포스트를 읽고 "{style}" 스타일로 자연스러운 댓글을 작성해주세요.

            블로그 포스트 정보:
            제목: {post_title}
            
            내용:
            {content_preview}
            
            댓글 작성 규칙:
            1. 1-3문장으로 짧고 자연스럽게 작성
            2. 포스트 내용과 관련된 구체적인 부분을 언급
            3. 과도한 칭찬이나 홍보성 멘트 금지
            4. 이모티콘은 최대 1개만 사용 (선택사항)
            5. 존댓말 사용
            6. 블로그 주인과 자연스러운 대화하듯이
            7. 질문을 포함해도 좋음
            8. 개인적인 경험이나 생각을 짧게 공유해도 좋음
            
            최근에 작성한 댓글들 (중복 방지용):
            {recent_comments_text if recent_comments_text else "없음"}
            
            위 댓글들과는 다른 스타일과 내용으로 작성해주세요.
            
            댓글:
            """

            # Claude API 호출
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",  # 또는 "claude-3-opus-20240229"
                max_tokens=150,
                temperature=0.8,  # 창의성을 위해 약간 높게 설정
                messages=[{"role": "user", "content": prompt}],
            )

            # 응답에서 댓글 추출
            comment = response.content[0].text.strip()

            # 댓글 후처리
            comment = self.post_process_comment(comment)

            # 댓글 기록 저장
            if post_url:
                self.save_comment_history(post_url, comment)

            return comment

        except Exception as e:
            print(f"댓글 생성 실패: {str(e)}")
            return None

    def post_process_comment(self, comment: str) -> str:
        """댓글 후처리"""
        # 너무 긴 댓글 자르기
        if len(comment) > 200:
            # 마지막 문장 끝에서 자르기
            sentences = comment.split(".")
            if len(sentences) > 2:
                comment = ".".join(sentences[:2]) + "."

        # 불필요한 줄바꿈 제거
        comment = " ".join(comment.split())

        # 금지된 단어 체크 (필요시 추가)
        forbidden_words = ["광고", "홍보", "판매", "구매", "할인"]
        for word in forbidden_words:
            if word in comment:
                # 다시 생성하거나 기본 댓글 반환
                return "좋은 글 잘 읽었습니다. 감사합니다!"

        return comment

    def generate_reply_comment(
        self, original_comment: str, reply_to: str
    ) -> Optional[str]:
        """
        다른 댓글에 대한 대댓글 생성

        Args:
            original_comment: 원본 댓글
            reply_to: 답글을 달 댓글

        Returns:
            생성된 대댓글
        """
        try:
            prompt = f"""
            네이버 블로그 댓글에 답글을 달아주세요.
            
            원본 댓글: {original_comment}
            답글 대상 댓글: {reply_to}
            
            답글 작성 규칙:
            1. 1-2문장으로 짧게
            2. 친근하고 공감하는 톤
            3. 자연스러운 대화체
            4. 존댓말 사용
            
            답글:
            """

            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=100,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text.strip()

        except Exception as e:
            print(f"대댓글 생성 실패: {str(e)}")
            return None
