"""
블로그 필터링 조건 Mixin
여러 작업에서 공통으로 사용되는 블로그 필터링 기능
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging


class BlogFilterMixin:
    """블로그 필터링 조건 Mixin"""

    def get_filter_parameters(self) -> Dict[str, Dict[str, Any]]:
        """필터링 관련 파라미터 정의"""
        return {
            # 기본 필터
            "min_likes": {
                "type": "integer",
                "description": "최소 좋아요 수",
                "required": False,
                "default": 0,
                "min": 0,
                "max": 99999,
            },
            "max_likes": {
                "type": "integer",
                "description": "최대 좋아요 수",
                "required": False,
                "default": 1000,
                "min": 0,
                "max": 99999,
            },
            "min_comments": {
                "type": "integer",
                "description": "최소 댓글 수",
                "required": False,
                "default": 0,
                "min": 0,
                "max": 9999,
            },
            "max_comments": {
                "type": "integer",
                "description": "최대 댓글 수",
                "required": False,
                "default": 100,
                "min": 0,
                "max": 9999,
            },
            "min_posts": {
                "type": "integer",
                "description": "최소 포스팅 수",
                "required": False,
                "default": 10,
                "min": 0,
                "max": 99999,
            },
            "max_posts": {
                "type": "integer",
                "description": "최대 포스팅 수",
                "required": False,
                "default": 1000,
                "min": 0,
                "max": 99999,
            },
            "recent_post_days": {
                "type": "integer",
                "description": "최근 새글 X일 이내",
                "required": False,
                "default": 30,
                "min": 1,
                "max": 365,
            },
            "min_neighbors": {
                "type": "integer",
                "description": "최소 이웃 수",
                "required": False,
                "default": 10,
                "min": 0,
                "max": 99999,
            },
            "max_neighbors": {
                "type": "integer",
                "description": "최대 이웃 수",
                "required": False,
                "default": 1000,
                "min": 0,
                "max": 99999,
            },
            "min_total_visitors": {
                "type": "integer",
                "description": "최소 누적 방문자 수",
                "required": False,
                "default": 100,
                "min": 0,
                "max": 9999999,
            },
            "min_today_visitors": {
                "type": "integer",
                "description": "최소 오늘 방문자 수",
                "required": False,
                "default": 0,
                "min": 0,
                "max": 99999,
            },
            "exclude_my_neighbors": {
                "type": "boolean",
                "description": "내 이웃 작업 제외",
                "required": False,
                "default": True,
            },
            "exclude_official_bloggers": {
                "type": "boolean",
                "description": "공식 블로거 작업 제외",
                "required": False,
                "default": False,
            },
            "exclude_no_profile_image": {
                "type": "boolean",
                "description": "프로필 이미지 없는 대상 제외",
                "required": False,
                "default": False,
            },
        }

    async def filter_blogs(
        self, browser_manager: Any, blogs: List[Dict[str, Any]], context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """블로그 목록 필터링"""
        filtered = []

        # 내 이웃 목록 (필요한 경우)
        my_neighbors = []
        if self.get_parameter("exclude_my_neighbors", True):
            my_neighbors = await self._get_my_neighbors(browser_manager)
            context["my_neighbors"] = my_neighbors  # 캐시

        for blog in blogs:
            # 필터 통과 여부 확인
            if await self._pass_filters(browser_manager, blog, my_neighbors):
                filtered.append(blog)

        return filtered

    async def _pass_filters(
        self, browser_manager: Any, blog: Dict[str, Any], my_neighbors: List[str]
    ) -> bool:
        """개별 블로그 필터 통과 여부"""
        try:
            # 내 이웃 제외
            if self.get_parameter("exclude_my_neighbors", True):
                if (
                    blog.get("author") in my_neighbors
                    or blog.get("blog_id") in my_neighbors
                ):
                    return False

            # 상세 정보가 필요한 경우
            if self._needs_detailed_info(blog):
                blog_details = await self._get_blog_details(
                    browser_manager, blog["url"]
                )
                blog.update(blog_details)

            # 각 필터 확인
            if not self._check_post_filter(blog):
                return False

            if not self._check_engagement_filter(blog):
                return False

            if not self._check_neighbor_filter(blog):
                return False

            if not self._check_visitor_filter(blog):
                return False

            if not self._check_profile_filter(blog):
                return False

            return True

        except Exception as e:
            logging.debug(f"필터 확인 중 오류: {e}")
            return False

    def _needs_detailed_info(self, blog: Dict[str, Any]) -> bool:
        """상세 정보 필요 여부"""
        # 이미 상세 정보가 있으면 스킵
        if "neighbor_count" in blog and "total_visitors" in blog:
            return False

        # 필터 설정값 확인
        return (
            self.get_parameter("min_neighbors", 10) > 10
            or self.get_parameter("max_neighbors", 1000) < 1000
            or self.get_parameter("min_total_visitors", 100) > 100
            or self.get_parameter("min_today_visitors", 0) > 0
            or self.get_parameter("exclude_official_bloggers", False)
            or self.get_parameter("exclude_no_profile_image", False)
        )

    def _check_post_filter(self, blog: Dict[str, Any]) -> bool:
        """포스트 관련 필터"""
        # 최근 포스트 날짜
        if "last_post_date" in blog:
            recent_days = self.get_parameter("recent_post_days", 30)
            cutoff_date = datetime.now() - timedelta(days=recent_days)
            if blog["last_post_date"] < cutoff_date:
                return False

        # 포스트 수
        if "post_count" in blog:
            min_posts = self.get_parameter("min_posts", 10)
            max_posts = self.get_parameter("max_posts", 1000)
            if blog["post_count"] < min_posts or blog["post_count"] > max_posts:
                return False

        return True

    def _check_engagement_filter(self, blog: Dict[str, Any]) -> bool:
        """참여도 관련 필터"""
        # 좋아요 수
        if "like_count" in blog:
            min_likes = self.get_parameter("min_likes", 0)
            max_likes = self.get_parameter("max_likes", 1000)
            if blog["like_count"] < min_likes or blog["like_count"] > max_likes:
                return False

        # 댓글 수
        if "comment_count" in blog:
            min_comments = self.get_parameter("min_comments", 0)
            max_comments = self.get_parameter("max_comments", 100)
            if (
                blog["comment_count"] < min_comments
                or blog["comment_count"] > max_comments
            ):
                return False

        return True

    def _check_neighbor_filter(self, blog: Dict[str, Any]) -> bool:
        """이웃 관련 필터"""
        if "neighbor_count" in blog:
            min_neighbors = self.get_parameter("min_neighbors", 10)
            max_neighbors = self.get_parameter("max_neighbors", 1000)
            if (
                blog["neighbor_count"] < min_neighbors
                or blog["neighbor_count"] > max_neighbors
            ):
                return False

        return True

    def _check_visitor_filter(self, blog: Dict[str, Any]) -> bool:
        """방문자 관련 필터"""
        # 누적 방문자
        if "total_visitors" in blog:
            min_total = self.get_parameter("min_total_visitors", 100)
            if blog["total_visitors"] < min_total:
                return False

        # 오늘 방문자
        if "today_visitors" in blog:
            min_today = self.get_parameter("min_today_visitors", 0)
            if blog["today_visitors"] < min_today:
                return False

        return True

    def _check_profile_filter(self, blog: Dict[str, Any]) -> bool:
        """프로필 관련 필터"""
        # 공식 블로거 제외
        if self.get_parameter("exclude_official_bloggers", False):
            if blog.get("is_official", False):
                return False

        # 프로필 이미지 없는 블로거 제외
        if self.get_parameter("exclude_no_profile_image", False):
            if not blog.get("has_profile_image", True):
                return False

        return True

    async def _get_blog_details(
        self, browser_manager: Any, blog_url: str
    ) -> Dict[str, Any]:
        """블로그 상세 정보 가져오기"""
        details = {}

        try:
            # 블로그 메인 페이지로 이동
            await browser_manager.navigate_async(blog_url, wait_time=2)

            # 이웃 수
            neighbor_elem = browser_manager.find_element(".neighbor_cnt", timeout=2)
            if neighbor_elem:
                details["neighbor_count"] = self._parse_number(neighbor_elem.text)

            # 방문자 수
            visitor_elem = browser_manager.find_element(".visitor_cnt", timeout=2)
            if visitor_elem:
                details["total_visitors"] = self._parse_number(visitor_elem.text)

            # 오늘 방문자
            today_elem = browser_manager.find_element(".today_visitor", timeout=2)
            if today_elem:
                details["today_visitors"] = self._parse_number(today_elem.text)

            # 포스트 수
            post_cnt_elem = browser_manager.find_element(".post_cnt", timeout=2)
            if post_cnt_elem:
                details["post_count"] = self._parse_number(post_cnt_elem.text)

            # 프로필 이미지
            profile_img = browser_manager.find_element(".profile_img", timeout=1)
            details["has_profile_image"] = profile_img is not None

            # 공식 블로거 여부
            official_badge = browser_manager.find_element(".official_badge", timeout=1)
            details["is_official"] = official_badge is not None

        except Exception as e:
            logging.debug(f"블로그 상세 정보 가져오기 실패: {e}")

        return details

    async def _get_my_neighbors(self, browser_manager: Any) -> List[str]:
        """내 이웃 목록 가져오기"""
        # 캐시 확인
        if hasattr(self, "_my_neighbors_cache"):
            return self._my_neighbors_cache

        neighbors = []

        try:
            # 이웃 목록 페이지로 이동
            neighbor_url = "https://m.blog.naver.com/BuddyListManage.naver"
            await browser_manager.navigate_async(neighbor_url, wait_time=2)

            # 이웃 목록 수집
            neighbor_elements = browser_manager.find_elements(".buddy_list .nickname")

            for elem in neighbor_elements:
                neighbors.append(elem.text.strip())

            # 캐시 저장
            self._my_neighbors_cache = neighbors

        except Exception as e:
            logging.debug(f"이웃 목록 가져오기 실패: {e}")

        return neighbors

    def _parse_number(self, text: str) -> int:
        """숫자 파싱 (1,234 -> 1234)"""
        try:
            return int(text.replace(",", "").replace("명", "").strip())
        except:
            return 0
