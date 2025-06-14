"""
로그인 작업
"""

import asyncio
from typing import Dict, Any, List

from tasks.base_task import BaseTask, TaskType, TaskResult


class LoginTask(BaseTask):
    """네이버 로그인 작업"""

    def __init__(self, name: str = "네이버 로그인"):
        super().__init__(name)

        # 기본 파라미터
        self.parameters = {
            "username": "",  # user_id 대신 username 사용
            "password": "",
            "keep_login": True,
            "retry_on_captcha": False,
        }

    def _get_task_type(self) -> TaskType:
        return TaskType.LOGIN

    @property
    def description(self) -> str:
        return "네이버 계정으로 로그인합니다."

    def get_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "username": {
                "type": "string",
                "description": "네이버 아이디",
                "required": True,
                "default": "",
            },
            "password": {
                "type": "password",
                "description": "네이버 비밀번호",
                "required": True,
                "default": "",
                "sensitive": True,
            },
            "keep_login": {
                "type": "boolean",
                "description": "로그인 상태 유지",
                "required": False,
                "default": True,
            },
            "retry_on_captcha": {
                "type": "boolean",
                "description": "캡차 발생 시 재시도",
                "required": False,
                "default": False,
            },
        }

    def validate_parameters(self) -> bool:
        """파라미터 검증"""
        username = self.get_parameter("username")
        password = self.get_parameter("password")

        # username과 password가 문자열이고 None이 아닌지만 확인
        # 빈 문자열은 허용 (나중에 입력할 수 있도록)
        return isinstance(username, str) and isinstance(password, str)

    def get_estimated_duration(self) -> float:
        """예상 소요 시간"""
        return 10.0  # 10초

    async def execute(
        self, browser_manager: Any, context: Dict[str, Any]
    ) -> TaskResult:
        """로그인 실행"""
        try:
            # 파라미터 가져오기
            username = self.get_parameter("username")
            password = self.get_parameter("password")
            keep_login = self.get_parameter("keep_login", True)

            if not username or not password:
                return TaskResult(
                    success=False, message="아이디 또는 비밀번호가 설정되지 않았습니다."
                )

            # 네이버 로그인 페이지로 이동
            if hasattr(browser_manager, "navigate_async"):
                await browser_manager.navigate_async(
                    "https://nid.naver.com/nidlogin.login"
                )
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    browser_manager.navigate,
                    "https://nid.naver.com/nidlogin.login",
                )

            await asyncio.sleep(2)

            # 아이디 입력
            if hasattr(browser_manager, "type_text_async"):
                await browser_manager.type_text_async("#id", username)
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, browser_manager.type_text, "#id", username
                )

            await asyncio.sleep(0.5)

            # 비밀번호 입력
            if hasattr(browser_manager, "type_text_async"):
                await browser_manager.type_text_async("#pw", password)
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, browser_manager.type_text, "#pw", password
                )

            await asyncio.sleep(0.5)

            # 로그인 상태 유지 체크
            if keep_login:
                if hasattr(browser_manager, "click_async"):
                    await browser_manager.click_async(".keep_check")
                else:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None, browser_manager.click, ".keep_check"
                    )
                await asyncio.sleep(0.5)

            # 로그인 버튼 클릭
            if hasattr(browser_manager, "click_async"):
                await browser_manager.click_async("#log\\.login")
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, browser_manager.click, "#log\\.login")

            await asyncio.sleep(3)

            # 로그인 결과 확인
            if hasattr(browser_manager, "get_current_url_async"):
                current_url = await browser_manager.get_current_url_async()
            else:
                current_url = browser_manager.current_url

            if "naver.com" in current_url and "nid.naver.com" not in current_url:
                # 로그인 성공
                # 사용자 정보 가져오기
                user_info = await self._get_user_info(browser_manager)

                # 컨텍스트에 로그인 정보 저장
                context["user_info"] = user_info
                context["logged_in"] = True

                return TaskResult(
                    success=True, message="로그인 성공", data={"user_info": user_info}
                )
            elif "captcha" in current_url.lower():
                return TaskResult(
                    success=False,
                    message="캡차 인증이 필요합니다.",
                    data={"captcha_required": True},
                )
            else:
                return TaskResult(
                    success=False,
                    message="로그인 실패 - 아이디 또는 비밀번호를 확인하세요.",
                )

        except Exception as e:
            return TaskResult(success=False, message=f"로그인 중 오류 발생: {str(e)}")

    async def _get_user_info(self, browser_manager: Any) -> Dict[str, str]:
        """사용자 정보 가져오기"""
        try:
            # 네이버 메인으로 이동
            if hasattr(browser_manager, "navigate_async"):
                await browser_manager.navigate_async("https://www.naver.com")
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, browser_manager.navigate, "https://www.naver.com"
                )

            await asyncio.sleep(2)

            # 사용자 닉네임 가져오기
            if hasattr(browser_manager, "get_text_async"):
                nickname = await browser_manager.get_text_async(".user_name")
            else:
                nickname = browser_manager.get_text(".user_name")

            if not nickname:
                # 다른 선택자 시도
                selectors = [".MyView-module__my_menu___ehoqV", "#account", ".gnb_my"]
                for selector in selectors:
                    try:
                        if hasattr(browser_manager, "get_text_async"):
                            nickname = await browser_manager.get_text_async(selector)
                        else:
                            nickname = browser_manager.get_text(selector)
                        if nickname:
                            break
                    except:
                        continue

            return {"nickname": nickname or "사용자", "logged_in": True}

        except Exception as e:
            if self.logger:
                self.logger.warning(f"사용자 정보 가져오기 실패: {e}")
            return {"nickname": "사용자", "logged_in": True}


# CheckNewPostsTask는 별도 파일로 이동되었으므로 제거
