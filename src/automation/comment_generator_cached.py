import anthropic
import random
import json
import os
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from collections import defaultdict


class CachedCommentGenerator:
    """토큰 사용량 최소화를 위한 캐싱이 적용된 댓글 생성기"""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

        # 캐시 설정
        self.cache_dir = "cache"
        os.makedirs(self.cache_dir, exist_ok=True)

        # 캐시 파일들
        self.template_cache_file = os.path.join(
            self.cache_dir, "comment_templates.json"
        )
        self.response_cache_file = os.path.join(self.cache_dir, "response_cache.json")
        self.category_cache_file = os.path.join(
            self.cache_dir, "category_patterns.json"
        )

        # 캐시 로드
        self.template_cache = self.load_cache(self.template_cache_file)
        self.response_cache = self.load_cache(self.response_cache_file)
        self.category_patterns = self.load_cache(self.category_cache_file)

        # 통계
        self.stats = {"api_calls": 0, "cache_hits": 0, "tokens_saved": 0}

        # 카테고리별 기본 템플릿
        self.initialize_templates()

    def load_cache(self, file_path: str) -> Dict:
        """캐시 파일 로드"""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_cache(self, data: Dict, file_path: str):
        """캐시 파일 저장"""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def initialize_templates(self):
        """카테고리별 기본 댓글 템플릿 초기화"""
        if not self.template_cache:
            self.template_cache = {
                "요리/레시피": [
                    "레시피 따라서 만들어봐야겠어요! {detail} 정말 맛있어 보이네요 😊",
                    "우와 {detail} 꿀팁이네요! 저도 이번 주말에 도전해볼게요~",
                    "{detail} 부분이 특히 인상적이에요. 자세한 레시피 공유 감사합니다!",
                ],
                "여행": [
                    "{detail} 정말 멋진 곳이네요! 저도 다음에 꼭 가보고 싶어요.",
                    "사진만 봐도 힐링되는 느낌이에요. {detail} 추천 감사합니다!",
                    "{detail} 정보 너무 유용해요! 여행 계획 세울 때 참고할게요~",
                ],
                "일상/에세이": [
                    "{detail} 부분에서 많은 공감이 되네요. 좋은 글 감사합니다.",
                    "글 읽으면서 {detail} 생각이 들었어요. 따뜻한 글이네요 :)",
                    "{detail} 저도 비슷한 경험이 있어서 더 와닿네요!",
                ],
                "IT/기술": [
                    "{detail} 설명이 정말 이해하기 쉽게 되어있네요! 좋은 정보 감사합니다.",
                    "오 {detail} 이런 방법도 있었군요! 바로 적용해봐야겠어요.",
                    "{detail} 팁 너무 유용해요! 개발하면서 막혔던 부분인데 도움이 됐어요.",
                ],
                "뷰티/패션": [
                    "{detail} 팁 너무 좋아요! 저도 한번 따라해봐야겠네요~",
                    "와 {detail} 정보 찾고 있었는데! 자세한 리뷰 감사해요 💕",
                    "{detail} 저도 궁금했던 부분이에요! 도움 많이 됐어요~",
                ],
            }
            self.save_cache(self.template_cache, self.template_cache_file)

    def get_content_hash(self, title: str, content: str) -> str:
        """콘텐츠 해시 생성 (캐시 키로 사용)"""
        # 제목과 내용의 주요 부분만 해시
        key_content = f"{title[:50]}{content[:200]}"
        return hashlib.md5(key_content.encode()).hexdigest()

    def categorize_post(self, title: str, content: str) -> str:
        """포스트 카테고리 분류"""
        text = f"{title} {content}".lower()

        # 카테고리 키워드
        categories = {
            "요리/레시피": ["요리", "레시피", "맛있", "재료", "조리", "음식", "만들기"],
            "여행": ["여행", "관광", "호텔", "비행기", "해외", "국내", "관광지"],
            "IT/기술": ["프로그래밍", "코딩", "개발", "it", "컴퓨터", "앱", "웹"],
            "뷰티/패션": ["화장품", "패션", "옷", "코디", "메이크업", "스킨케어"],
            "일상/에세이": ["일상", "하루", "생각", "느낌", "오늘", "일기"],
        }

        # 카테고리 점수 계산
        scores = defaultdict(int)
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in text:
                    scores[category] += 1

        # 가장 높은 점수의 카테고리 반환
        if scores:
            return max(scores, key=scores.get)
        return "일상/에세이"  # 기본값

    def extract_key_detail(self, content: str, category: str) -> str:
        """포스트에서 핵심 디테일 추출"""
        # 카테고리별 핵심 키워드 추출 로직
        sentences = content.split(".")

        if category == "요리/레시피":
            # 재료나 조리법 관련 문장 찾기
            for sent in sentences:
                if any(word in sent for word in ["재료", "넣고", "볶", "끓"]):
                    return sent.strip()[:30]

        elif category == "여행":
            # 장소나 추천 관련 문장 찾기
            for sent in sentences:
                if any(word in sent for word in ["곳", "추천", "가볼만한", "명소"]):
                    return sent.strip()[:30]

        # 기본: 첫 번째 의미있는 문장
        for sent in sentences:
            if len(sent.strip()) > 10:
                return sent.strip()[:30]

        return "이 내용"

    def check_cache(self, content_hash: str) -> Optional[str]:
        """캐시에서 댓글 확인"""
        if content_hash in self.response_cache:
            cache_entry = self.response_cache[content_hash]

            # 캐시 만료 확인 (7일)
            cached_time = datetime.fromisoformat(cache_entry["timestamp"])
            if datetime.now() - cached_time < timedelta(days=7):
                # 캐시된 댓글 중 랜덤 선택
                comments = cache_entry["comments"]
                if comments:
                    self.stats["cache_hits"] += 1
                    self.stats["tokens_saved"] += 150  # 평균 토큰 절약량
                    return random.choice(comments)

        return None

    def generate_from_template(self, category: str, detail: str) -> str:
        """템플릿 기반 댓글 생성"""
        if category in self.template_cache:
            template = random.choice(self.template_cache[category])
            return template.format(detail=detail)
        return None

    def generate_comment(
        self, post_title: str, post_content: str, post_url: str = None
    ) -> Optional[str]:
        """
        캐싱이 적용된 댓글 생성

        1. 콘텐츠 해시로 캐시 확인
        2. 카테고리 분류 후 템플릿 확인
        3. 필요시에만 API 호출
        """
        try:
            # 1. 콘텐츠 해시 생성
            content_hash = self.get_content_hash(post_title, post_content)

            # 2. 캐시 확인
            cached_comment = self.check_cache(content_hash)
            if cached_comment:
                print(f"캐시 히트! 토큰 절약: ~150")
                return cached_comment

            # 3. 카테고리 분류
            category = self.categorize_post(post_title, post_content)

            # 4. 핵심 디테일 추출
            detail = self.extract_key_detail(post_content, category)

            # 5. 템플릿 기반 생성 시도 (30% 확률)
            if random.random() < 0.3:
                template_comment = self.generate_from_template(category, detail)
                if template_comment:
                    print(f"템플릿 사용! 토큰 절약: ~200")
                    self.save_to_cache(content_hash, [template_comment])
                    return template_comment

            # 6. API 호출 (필요한 경우만)
            print("API 호출 중...")
            self.stats["api_calls"] += 1

            # 콘텐츠 요약 (토큰 절약)
            content_summary = self.summarize_content(post_content, 500)

            prompt = f"""
            카테고리: {category}
            제목: {post_title}
            핵심 내용: {content_summary}
            
            위 블로그에 대한 자연스러운 댓글 3개를 생성해주세요.
            각 댓글은 다른 스타일로, 1-2문장으로 작성하고, 줄바꿈으로 구분해주세요.
            
            규칙:
            - 구체적인 내용 언급
            - 자연스러운 한국어
            - 이모티콘 최대 1개
            - 각각 다른 관점
            """

            response = self.client.messages.create(
                model="claude-3-haiku-20240307",  # 더 저렴한 모델 사용
                max_tokens=200,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}],
            )

            # 여러 댓글 생성 및 캐싱
            comments = response.content[0].text.strip().split("\n")
            comments = [c.strip() for c in comments if c.strip()]

            if comments:
                self.save_to_cache(content_hash, comments)
                return random.choice(comments)

            return None

        except Exception as e:
            print(f"댓글 생성 실패: {str(e)}")
            return None

    def summarize_content(self, content: str, max_length: int) -> str:
        """콘텐츠 요약 (토큰 절약)"""
        if len(content) <= max_length:
            return content

        # 중요 문장 추출
        sentences = content.split(".")
        important_sentences = []

        # 숫자, 키워드가 포함된 문장 우선
        for sent in sentences:
            if any(char.isdigit() for char in sent) or len(sent.strip()) > 20:
                important_sentences.append(sent.strip())

        # 길이 제한에 맞춰 반환
        result = ""
        for sent in important_sentences:
            if len(result) + len(sent) < max_length:
                result += sent + ". "
            else:
                break

        return result or content[:max_length]

    def save_to_cache(self, content_hash: str, comments: List[str]):
        """캐시에 저장"""
        self.response_cache[content_hash] = {
            "comments": comments,
            "timestamp": datetime.now().isoformat(),
        }
        self.save_cache(self.response_cache, self.response_cache_file)

    def get_stats(self) -> Dict:
        """통계 반환"""
        total_calls = self.stats["api_calls"] + self.stats["cache_hits"]
        cache_rate = (
            (self.stats["cache_hits"] / total_calls * 100) if total_calls > 0 else 0
        )

        return {
            "total_requests": total_calls,
            "api_calls": self.stats["api_calls"],
            "cache_hits": self.stats["cache_hits"],
            "cache_hit_rate": f"{cache_rate:.1f}%",
            "estimated_tokens_saved": self.stats["tokens_saved"],
            "estimated_cost_saved": f"${self.stats['tokens_saved'] * 0.00002:.2f}",  # Haiku 가격 기준
        }

    def cleanup_old_cache(self, days: int = 7):
        """오래된 캐시 정리"""
        current_time = datetime.now()
        cleaned = 0

        # response_cache 정리
        for key in list(self.response_cache.keys()):
            cached_time = datetime.fromisoformat(self.response_cache[key]["timestamp"])
            if current_time - cached_time > timedelta(days=days):
                del self.response_cache[key]
                cleaned += 1

        if cleaned > 0:
            self.save_cache(self.response_cache, self.response_cache_file)
            print(f"오래된 캐시 {cleaned}개 정리됨")
