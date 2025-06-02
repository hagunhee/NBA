import os
import time
import random
from typing import Optional, Dict, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import undetected_chromedriver as uc
from dotenv import load_dotenv

from .comment_generator import CommentGenerator

load_dotenv()


class NaverBlogAutomation:
    """네이버 블로그 자동화 + Claude 댓글 생성"""

    def __init__(self):
        self.driver = None
        self.wait = None
        self.comment_generator = None
        self.is_running = False

    def init_browser(self) -> bool:
        """브라우저 초기화"""
        try:
            chrome_options = uc.ChromeOptions()
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--window-size=1280,800")

            self.driver = uc.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)

            # Claude API 초기화
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.comment_generator = CommentGenerator(api_key)
            else:
                print("경고: Claude API 키가 설정되지 않았습니다.")

            return True

        except Exception as e:
            print(f"브라우저 초기화 실패: {str(e)}")
            return False

    def process_post(self, post_url: str, settings: Dict) -> bool:
        """
        포스트 처리: 방문 -> 읽기 -> 스크롤 -> 댓글 생성 -> 댓글 작성

        Args:
            post_url: 포스트 URL
            settings: 자동화 설정

        Returns:
            성공 여부
        """
        try:
            # 1. 포스트 방문
            self.driver.get(post_url)
            time.sleep(random.uniform(2, 4))

            # 2. 포스트 정보 수집
            post_info = self.collect_post_info()
            if not post_info:
                return False

            print(f"포스트 방문: {post_info['title'][:30]}...")

            # 3. 체류시간 동안 스크롤하며 읽기
            stay_time = random.uniform(
                settings.get("min_stay", 60), settings.get("max_stay", 180)
            )

            self.read_with_scroll(stay_time, settings.get("scroll_speed", "보통"))

            # 4. Claude로 댓글 생성
            if self.comment_generator and settings.get("auto_comment", True):
                print("댓글 생성 중...")

                comment = self.comment_generator.generate_comment(
                    post_title=post_info["title"],
                    post_content=post_info["content"],
                    post_url=post_url,
                )

                if comment:
                    print(f"생성된 댓글: {comment[:50]}...")

                    # 5. 댓글 작성
                    success = self.write_comment(comment)

                    if success:
                        print("댓글 작성 완료!")
                        return True
                    else:
                        print("댓글 작성 실패")
                        return False
                else:
                    print("댓글 생성 실패")
                    return False

            return True

        except Exception as e:
            print(f"포스트 처리 실패: {str(e)}")
            return False

    def collect_post_info(self) -> Optional[Dict]:
        """포스트 정보 수집"""
        try:
            # iframe 처리
            try:
                iframe = self.driver.find_element(By.ID, "mainFrame")
                self.driver.switch_to.frame(iframe)
            except:
                pass

            # 제목 수집
            title = ""
            title_selectors = [
                ".se-fs-.se-ff-",  # 스마트에디터
                ".htitle",  # 구버전
                "h3.se-fs-",  # 신버전
            ]

            for selector in title_selectors:
                try:
                    title_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    title = title_elem.text
                    break
                except:
                    continue

            # 본문 수집
            content = ""
            content_selectors = [
                ".se-main-container",  # 스마트에디터
                ".se-text-paragraph",  # 문단
                "#postViewArea",  # 구버전
                ".post-view",  # 신버전
            ]

            for selector in content_selectors:
                try:
                    content_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    content = content_elem.text
                    break
                except:
                    continue

            # 메인 프레임으로 복귀
            self.driver.switch_to.default_content()

            if title and content:
                return {"title": title, "content": content}

            return None

        except Exception as e:
            print(f"포스트 정보 수집 실패: {str(e)}")
            self.driver.switch_to.default_content()
            return None

    def read_with_scroll(self, duration: float, scroll_speed: str):
        """자연스러운 스크롤로 읽기"""
        speeds = {
            "느리게": {"step": 100, "delay": 0.5},
            "보통": {"step": 200, "delay": 0.3},
            "빠르게": {"step": 300, "delay": 0.1},
        }

        speed_config = speeds.get(scroll_speed, speeds["보통"])
        start_time = time.time()

        while time.time() - start_time < duration:
            if not self.is_running:
                break

            # 스크롤 수행
            self.driver.execute_script(f"window.scrollBy(0, {speed_config['step']});")
            time.sleep(speed_config["delay"])

            # 가끔 위로 스크롤
            if random.random() < 0.2:
                self.driver.execute_script(
                    f"window.scrollBy(0, -{speed_config['step']//2});"
                )
                time.sleep(speed_config["delay"] * 2)

            # 가끔 멈춤
            if random.random() < 0.3:
                time.sleep(random.uniform(1, 3))

    def write_comment(self, comment_text: str) -> bool:
        """댓글 작성"""
        try:
            # iframe 전환
            try:
                iframe = self.driver.find_element(By.ID, "mainFrame")
                self.driver.switch_to.frame(iframe)
            except:
                pass

            # 댓글 입력창 찾기
            comment_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".u_cbox_text"))
            )

            # 댓글창 클릭
            comment_input.click()
            time.sleep(1)

            # 자연스러운 타이핑
            for char in comment_text:
                comment_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))

            time.sleep(1)

            # 등록 버튼 클릭
            submit_button = self.driver.find_element(
                By.CSS_SELECTOR, ".u_cbox_btn_upload"
            )
            submit_button.click()

            time.sleep(2)

            # 메인 프레임으로 복귀
            self.driver.switch_to.default_content()

            return True

        except Exception as e:
            print(f"댓글 작성 실패: {str(e)}")
            self.driver.switch_to.default_content()
            return False
