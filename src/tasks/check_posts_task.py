"""
이웃 새글 확인 작업
"""

from typing import Dict, Any, List
from tasks.base_task import BaseTask, TaskType, TaskResult
from automation.naver_actions import NaverActions


class CheckNewPostsTask(BaseTask):
    """이웃 새글 확인 작업"""

    def __init__(self, name: str = "이웃 새글 확인"):
        super().__init__(name)

        # 기본 파라미터 - 모든 파라미터에 유효한 기본값 설정
        self.parameters = {
            "max_posts": 20,
            "filter_keywords": [],
            "exclude_keywords": [],
            "blogger_whitelist": [],
            "blogger_blacklist": [],
        }

    def _get_task_type(self) -> TaskType:
        """작업 타입 반환"""
        return TaskType.CHECK_POSTS

    @property
    def description(self) -> str:
        """작업 설명"""
        return "이웃들의 새 글을 확인합니다."

    async def execute(
        self, browser_manager: Any, context: Dict[str, Any]
    ) -> TaskResult:
        """
        이웃 새글 확인 실행

        Args:
            browser_manager: BrowserManager 인스턴스
            context: 실행 컨텍스트

        Returns:
            TaskResult: 실행 결과
        """
        try:
            # 로그인 확인
            if not context.get("user_info", {}).get("logged_in", False):
                return TaskResult(
                    success=False,
                    message="로그인이 필요합니다. 로그인 작업을 먼저 실행하세요.",
                )

            # NaverActions 인스턴스 생성
            naver = NaverActions(browser_manager)

            # 이웃 새글 가져오기
            posts = naver.get_neighbor_new_posts()

            if not posts:
                return TaskResult(
                    success=True,
                    message="새 글이 없습니다.",
                    data={"posts": [], "count": 0},
                )

            # 필터링 적용
            filtered_posts = self._apply_filters(posts)

            # 최대 개수 제한
            max_posts = self.get_parameter("max_posts", 20)
            filtered_posts = filtered_posts[:max_posts]

            # 결과 저장
            result_data = {
                "posts": filtered_posts,
                "count": len(filtered_posts),
                "total_found": len(posts),
                "filtered_out": len(posts) - len(filtered_posts),
            }

            # 컨텍스트에 포스트 목록 저장 (다음 작업에서 사용)
            context["available_posts"] = filtered_posts
            context["current_post_index"] = 0

            return TaskResult(
                success=True,
                message=f"{len(filtered_posts)}개의 새 글을 발견했습니다.",
                data=result_data,
            )

        except Exception as e:
            return TaskResult(
                success=False, message=f"이웃 새글 확인 중 오류 발생: {str(e)}"
            )

    def _apply_filters(self, posts: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """필터링 적용"""
        filtered = posts.copy()

        # 키워드 필터링
        filter_keywords = self.get_parameter("filter_keywords", [])
        if filter_keywords:
            filtered = [
                post
                for post in filtered
                if any(
                    keyword.lower() in post["title"].lower()
                    for keyword in filter_keywords
                )
            ]

        # 제외 키워드
        exclude_keywords = self.get_parameter("exclude_keywords", [])
        if exclude_keywords:
            filtered = [
                post
                for post in filtered
                if not any(
                    keyword.lower() in post["title"].lower()
                    for keyword in exclude_keywords
                )
            ]

        # 블로거 화이트리스트
        blogger_whitelist = self.get_parameter("blogger_whitelist", [])
        if blogger_whitelist:
            filtered = [
                post for post in filtered if post["blogger"] in blogger_whitelist
            ]

        # 블로거 블랙리스트
        blogger_blacklist = self.get_parameter("blogger_blacklist", [])
        if blogger_blacklist:
            filtered = [
                post for post in filtered if post["blogger"] not in blogger_blacklist
            ]

        return filtered

    def validate_parameters(self) -> bool:
        """파라미터 검증"""
        max_posts = self.get_parameter("max_posts", 20)

        # 숫자로 변환 시도
        try:
            max_posts = int(float(max_posts))  # float을 거쳐서 int로 변환
            if max_posts <= 0:
                return False
        except (ValueError, TypeError):
            return False

        # 리스트 파라미터 검증
        list_params = [
            "filter_keywords",
            "exclude_keywords",
            "blogger_whitelist",
            "blogger_blacklist",
        ]

        for param in list_params:
            value = self.get_parameter(param, [])
            if not isinstance(value, list):
                # 문자열인 경우 리스트로 변환 시도
                if isinstance(value, str):
                    self.set_parameters(**{param: [value] if value else []})
                else:
                    return False

        return True

    def get_estimated_duration(self) -> int:
        """예상 소요 시간 (초)"""
        return 5  # 페이지 로드 및 파싱

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        """필수 파라미터 정보"""
        return {
            "max_posts": {
                "type": "integer",
                "description": "최대 수집할 포스트 개수",
                "required": False,
                "default": 20,
                "min": 1,
                "max": 100,
            },
            "filter_keywords": {
                "type": "list",
                "description": "포함할 키워드 목록",
                "required": False,
                "default": [],
            },
            "exclude_keywords": {
                "type": "list",
                "description": "제외할 키워드 목록",
                "required": False,
                "default": [],
            },
            "blogger_whitelist": {
                "type": "list",
                "description": "포함할 블로거 목록",
                "required": False,
                "default": [],
            },
            "blogger_blacklist": {
                "type": "list",
                "description": "제외할 블로거 목록",
                "required": False,
                "default": [],
            },
        }
