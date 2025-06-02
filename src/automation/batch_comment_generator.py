from typing import List, Dict, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor
from .comment_generator_cached import CachedCommentGenerator


class BatchCommentGenerator:
    """대량 댓글 생성을 위한 배치 처리기"""

    def __init__(self, api_key: str):
        self.generator = CachedCommentGenerator(api_key)
        self.batch_cache = {}

    async def generate_batch_comments(self, posts: List[Dict]) -> List[Tuple[str, str]]:
        """
        여러 포스트에 대한 댓글을 배치로 생성

        Args:
            posts: [{'title': '', 'content': '', 'url': ''}, ...]

        Returns:
            [(url, comment), ...]
        """
        # 유사한 포스트 그룹화
        grouped_posts = self.group_similar_posts(posts)

        results = []

        for group_key, group_posts in grouped_posts.items():
            if len(group_posts) > 1:
                # 그룹 대표로 한 번만 API 호출
                representative = group_posts[0]
                base_comment = self.generator.generate_comment(
                    representative["title"],
                    representative["content"],
                    representative["url"],
                )

                # 나머지는 변형해서 사용
                for i, post in enumerate(group_posts):
                    if i == 0:
                        comment = base_comment
                    else:
                        comment = self.vary_comment(base_comment)

                    results.append((post["url"], comment))
            else:
                # 개별 생성
                post = group_posts[0]
                comment = self.generator.generate_comment(
                    post["title"], post["content"], post["url"]
                )
                results.append((post["url"], comment))

        return results

    def group_similar_posts(self, posts: List[Dict]) -> Dict[str, List[Dict]]:
        """유사한 포스트 그룹화 (토큰 절약)"""
        groups = {}

        for post in posts:
            # 카테고리로 그룹화
            category = self.generator.categorize_post(post["title"], post["content"])

            if category not in groups:
                groups[category] = []

            groups[category].append(post)

        return groups

    def vary_comment(self, base_comment: str) -> str:
        """기본 댓글을 약간 변형"""
        variations = [
            lambda x: x.replace("네요", "어요"),
            lambda x: x.replace("!", "~"),
            lambda x: x.replace("정말", "너무"),
            lambda x: x.replace("😊", "^^"),
            lambda x: x + " 좋은 글 감사합니다!",
        ]

        import random

        variation = random.choice(variations)
        return variation(base_comment)
