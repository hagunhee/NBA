import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os
import time
from typing import Optional


class BrowserManager:
    """브라우저 관리 클래스"""

    def __init__(self, config: dict = None):
        self.driver: Optional[webdriver.Chrome] = None
        self.config = config or {}

    def init_driver(self) -> bool:
        """Chrome 드라이버 초기화"""
        try:
            # Chrome 옵션 설정
            chrome_options = uc.ChromeOptions()

            # 기본 옵션
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            chrome_options.add_argument("--disable-setuid-sandbox")

            # 윈도우 크기
            window_size = self.config.get("window_size", "1280x800")
            chrome_options.add_argument(f"--window-size={window_size}")

            # 헤드리스 모드
            if self.config.get("headless", False):
                chrome_options.add_argument("--headless")

            # User-Agent
            user_agent = self.config.get(
                "user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            chrome_options.add_argument(f"user-agent={user_agent}")

            # 자동화 탐지 우회
            chrome_options.add_experimental_option(
                "excludeSwitches", ["enable-automation"]
            )
            chrome_options.add_experimental_option("useAutomationExtension", False)

            # 프록시 설정 (선택사항)
            if "proxy" in self.config:
                chrome_options.add_argument(f'--proxy-server={self.config["proxy"]}')

            # 드라이버 생성
            self.driver = uc.Chrome(options=chrome_options)

            # JavaScript 실행으로 추가 속성 제거
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ko-KR', 'ko', 'en-US', 'en']
                    });
                    
                    window.chrome = {
                        runtime: {}
                    };
                    
                    Object.defineProperty(navigator, 'permissions', {
                        get: () => ({
                            query: () => Promise.resolve({ state: 'granted' })
                        })
                    });
                """
                },
            )

            return True

        except Exception as e:
            print(f"브라우저 초기화 실패: {e}")
            return False

    def close(self):
        """브라우저 종료"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
