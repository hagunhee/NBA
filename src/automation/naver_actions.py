"""
네이버 특화 액션 - 네이버 블로그 관련 동작들
"""

import time
import random
from typing import Dict, List, Optional, Tuple, Any  # typing import 추가
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from .browser_manager import BrowserManager


class NaverActions:
    """네이버 블로그 특화 액션 클래스"""

    def __init__(self, browser_manager: BrowserManager):
        """
        Args:
            browser_manager: 브라우저 관리자 인스턴스
        """
        self.browser = browser_manager

    def login(
        self, user_id: str, password: str, keep_login: bool = True
    ) -> Tuple[bool, str]:
        """
        네이버 로그인

        Args:
            user_id: 네이버 아이디
            password: 네이버 비밀번호
            keep_login: 로그인 상태 유지 여부

        Returns:
            (성공여부, 메시지)
        """
        try:
            print("네이버 로그인 시작...")

            # 네이버 메인 페이지 접속
            self.browser.navigate("https://www.naver.com", wait_time=2)

            # 로그인 페이지로 이동
            self.browser.navigate("https://nid.naver.com/nidlogin.login", wait_time=3)

            # 로그인 폼 대기
            if not self.browser.wait_for_element("#id"):
                return False, "로그인 페이지 로드 실패"

            # 아이디 입력
            if not self.browser.type_text("#id", user_id, typing_delay=0.1):
                return False, "아이디 입력 실패"

            time.sleep(0.5)

            # 비밀번호 입력
            if not self.browser.type_text("#pw", password, typing_delay=0.1):
                return False, "비밀번호 입력 실패"

            time.sleep(0.5)

            # 로그인 상태 유지 체크
            if keep_login:
                self.browser.click(".keep_check")
                time.sleep(0.5)

            # 로그인 버튼 클릭
            login_button_clicked = False

            # 방법 1: Enter 키
            pw_input = self.browser.find_element("#pw")
            if pw_input:
                pw_input.send_keys(Keys.ENTER)
                login_button_clicked = True

            # 방법 2: 로그인 버튼 직접 클릭
            if not login_button_clicked:
                login_button_clicked = self.browser.click("#log\\.login")

            if not login_button_clicked:
                return False, "로그인 버튼 클릭 실패"

            # 로그인 결과 확인 (충분히 대기)
            time.sleep(5)

            return self._check_login_result()

        except Exception as e:
            return False, f"로그인 중 오류: {str(e)}"

    def _check_login_result(self) -> Tuple[bool, str]:
        """로그인 결과 확인"""
        current_url = self.browser.get_current_url()

        # 성공 조건
        if "naver.com" in current_url and "nid.naver.com" not in current_url:
            if self.check_login_status():
                return True, "로그인 성공"

        # 특수 상황 확인
        if "captcha" in current_url.lower():
            return False, "캡차 인증이 필요합니다. 수동 로그인을 사용하세요."

        if "protect" in current_url or "security" in current_url:
            return False, "보안 인증이 필요합니다. 수동 로그인을 사용하세요."

        if "changepassword" in current_url:
            return False, "비밀번호 변경이 필요합니다."

        # 에러 메시지 확인
        error_selectors = [".error_message", ".err_text", ".login_error"]
        for selector in error_selectors:
            error_text = self.browser.get_text(selector)
            if error_text:
                return False, f"로그인 실패: {error_text}"

        return False, "로그인 실패 - 아이디 또는 비밀번호를 확인하세요."

    def check_login_status(self) -> bool:
        """로그인 상태 확인"""
        # 네이버 메인으로 이동
        self.browser.navigate("https://www.naver.com", wait_time=2)

        # 로그인 상태 확인 요소들
        login_indicators = [
            ".MyView-module__my_menu___ehoqV",  # 마이메뉴
            ".MyView-module__link_logout___tBXTU",  # 로그아웃 버튼
            "#account",  # 계정 영역
            ".user_info",  # 사용자 정보
            ".gnb_my",  # 내 정보
        ]

        for selector in login_indicators:
            if self.browser.is_element_visible(selector):
                return True

        return False

    def get_neighbor_new_posts(self) -> List[Dict[str, str]]:
        """
        이웃 새글 목록 가져오기

        Returns:
            포스트 목록 [{"title": "", "url": "", "blogger": ""}, ...]
        """
        try:
            print("이웃 새글 페이지 접속 중...")

            # 이웃 새글 페이지로 이동
            self.browser.navigate(
                "https://section.blog.naver.com/BlogHome.naver", wait_time=3
            )

            posts = []

            # 방법 1: title_post 클래스 기반
            title_elements = self.browser.find_elements(".title_post")
            print(f"발견된 포스트: {len(title_elements)}개")

            for title_elem in title_elements:
                try:
                    # 제목 텍스트
                    title = title_elem.text.strip()
                    if not title or len(title) < 3:
                        continue

                    # 부모 링크 찾기
                    parent_link = self._find_parent_link(title_elem)
                    if not parent_link:
                        continue

                    url = parent_link.get_attribute("href")
                    if not url or "blog.naver.com" not in url:
                        continue

                    # 블로거 이름 찾기
                    blogger = self._find_blogger_name(title_elem)

                    # 중복 확인
                    if not any(p["url"] == url for p in posts):
                        posts.append({"title": title, "url": url, "blogger": blogger})

                except Exception as e:
                    print(f"포스트 처리 중 오류: {e}")
                    continue

            print(f"총 {len(posts)}개의 새글을 수집했습니다.")
            return posts

        except Exception as e:
            print(f"이웃 새글 가져오기 실패: {e}")
            return []

    def _find_parent_link(self, element) -> Optional[Any]:
        """부모 a 태그 찾기"""
        try:
            current = element
            for _ in range(5):
                current = current.find_element(By.XPATH, "..")
                if current.tag_name == "a":
                    href = current.get_attribute("href")
                    if href and "blog.naver.com" in href:
                        return current
        except:
            pass

        # 컨테이너에서 찾기
        try:
            container = element.find_element(By.XPATH, "../..")
            links = container.find_elements(
                By.CSS_SELECTOR, "a[href*='blog.naver.com']"
            )
            if links:
                return links[0]
        except:
            pass

        return None

    def _find_blogger_name(self, title_element) -> str:
        """블로거 이름 찾기"""
        try:
            container = title_element.find_element(By.XPATH, "../..")

            blogger_selectors = [
                ".nick",
                ".name",
                ".writer",
                ".author",
                "[class*='nick']",
                "[class*='name']",
                "[class*='writer']",
                ".blog_name",
                ".user_name",
            ]

            for selector in blogger_selectors:
                elements = container.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    text = elem.text.strip()
                    if text and len(text) >= 2 and len(text) <= 20:
                        return text

        except:
            pass

        return "Unknown"

    def collect_post_content(self) -> Optional[Dict[str, str]]:
        """
        현재 포스트의 내용 수집

        Returns:
            {"title": "", "content": ""} or None
        """
        try:
            print("포스트 정보 수집 중...")

            # iframe 전환 시도
            iframe_found = False
            if self.browser.switch_to_frame("mainFrame"):
                iframe_found = True
            else:
                # 다른 iframe 찾기
                iframes = self.browser.find_elements("iframe", By.TAG_NAME)
                for iframe in iframes:
                    size = iframe.size
                    if size["width"] > 500 and size["height"] > 500:
                        self.browser.driver.switch_to.frame(iframe)
                        iframe_found = True
                        break

            # 제목 찾기
            title = ""
            title_selectors = [
                ".se-title-text",
                ".se-fs-.se-ff-",
                ".htitle",
                "h3.se-fs-",
                ".pcol1",
                ".se-module-text h1",
                ".se-module-text h2",
                ".se-module-text h3",
            ]

            for selector in title_selectors:
                title = self.browser.get_text(selector)
                if title:
                    break

            # 본문 찾기
            content = ""
            content_selectors = [
                ".se-main-container",
                ".se-text-paragraph",
                "#postViewArea",
                ".post-view",
                ".post_ct",
                ".se-module-text",
            ]

            for selector in content_selectors:
                elements = self.browser.find_elements(selector)
                if elements:
                    content_parts = []
                    for elem in elements:
                        text = elem.text.strip()
                        if text:
                            content_parts.append(text)

                    content = "\n".join(content_parts)
                    if content:
                        break

            # 메인 프레임으로 복귀
            if iframe_found:
                self.browser.switch_to_default_content()

            if title and content:
                return {"title": title, "content": content[:2000]}  # 최대 2000자

            return None

        except Exception as e:
            print(f"포스트 정보 수집 실패: {e}")
            return None

    def click_like(self) -> bool:
        """좋아요 클릭"""
        try:
            # iframe 전환
            self.browser.switch_to_frame("mainFrame")

            like_selectors = [
                ".u_likeit_button",
                ".u_ico_like",
                ".btn_like",
                ".like_on",
                "#area_like_btn",
                "button[data-type='like']",
                ".btn_sympathy",
            ]

            for selector in like_selectors:
                elements = self.browser.find_elements(selector)
                for elem in elements:
                    if elem and elem.is_displayed():
                        # 이미 좋아요 눌렀는지 확인
                        class_name = elem.get_attribute("class") or ""
                        if "on" in class_name or "active" in class_name:
                            print("이미 좋아요를 누른 포스트입니다.")
                            self.browser.switch_to_default_content()
                            return True

                        # 좋아요 클릭
                        self.browser.scroll_to_element(elem)
                        elem.click()
                        time.sleep(1)

                        self.browser.switch_to_default_content()
                        return True

            self.browser.switch_to_default_content()
            return False

        except Exception as e:
            print(f"좋아요 클릭 실패: {e}")
            self.browser.switch_to_default_content()
            return False

    def write_comment(self, comment_text: str) -> bool:
        """
        댓글 작성

        Args:
            comment_text: 작성할 댓글 내용

        Returns:
            성공 여부
        """
        try:
            # 페이지 하단으로 스크롤
            self.browser.scroll_to_bottom()
            time.sleep(2)

            # 댓글 iframe 찾기
            comment_frame_found = False
            iframe_selectors = [
                "#naverComment",
                "#commentIframe",
                "iframe[title*='댓글']",
                "iframe[src*='comment']",
            ]

            for selector in iframe_selectors:
                if self.browser.switch_to_frame(selector):
                    comment_frame_found = True
                    break

            if not comment_frame_found:
                # 모든 iframe 순회
                iframes = self.browser.find_elements("iframe", By.TAG_NAME)
                for iframe in iframes:
                    self.browser.driver.switch_to.frame(iframe)
                    if self.browser.find_element(".u_cbox_text"):
                        comment_frame_found = True
                        break
                    else:
                        self.browser.switch_to_default_content()

            if not comment_frame_found:
                print("댓글 iframe을 찾을 수 없습니다.")
                return False

            # 댓글 입력창 찾기
            input_selectors = [
                ".u_cbox_text",
                ".comment_inbox_text",
                "textarea[placeholder*='댓글']",
            ]

            comment_input = None
            for selector in input_selectors:
                comment_input = self.browser.find_element(selector)
                if comment_input and comment_input.is_displayed():
                    break

            if not comment_input:
                print("댓글 입력창을 찾을 수 없습니다.")
                self.browser.switch_to_default_content()
                return False

            # 댓글 입력
            self.browser.scroll_to_element(comment_input)
            comment_input.click()
            time.sleep(1)

            comment_input.clear()
            time.sleep(0.5)

            # 자연스러운 타이핑
            for char in comment_text:
                comment_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))

            time.sleep(1)

            # 등록 버튼 클릭
            submit_selectors = [
                ".u_cbox_btn_upload",
                ".btn_register",
                "button[type='submit']",
                ".cmt_btn_register",
            ]

            submit_clicked = False
            for selector in submit_selectors:
                if self.browser.click(selector):
                    submit_clicked = True
                    break

            # Enter 키로 시도
            if not submit_clicked:
                comment_input.send_keys(Keys.ENTER)
                submit_clicked = True

            time.sleep(3)
            self.browser.switch_to_default_content()

            return submit_clicked

        except Exception as e:
            print(f"댓글 작성 실패: {e}")
            self.browser.switch_to_default_content()
            return False
