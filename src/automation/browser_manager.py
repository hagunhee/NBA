"""
리팩터링된 브라우저 관리자 v2
- 비동기 지원 추가
- 타입 힌팅 개선
- 기존 동기 메서드 유지 (하위 호환성)
"""

import time
import random
import logging
import asyncio
from typing import (
    Any,
    List,
    Optional,
    Dict,
    Tuple,
    Union,
    TypeVar,
    Generic,
    Callable,
    Awaitable,
)
from contextlib import contextmanager, asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
    ElementNotInteractableException,
    ElementClickInterceptedException,
    InvalidSessionIdException,
)
import undetected_chromedriver as uc

# 타입 정의
T = TypeVar("T")
WebDriverType = TypeVar("WebDriverType", bound=webdriver.Chrome)


# 커스텀 예외 클래스 (기존 유지)
class BrowserManagerError(Exception):
    """브라우저 관리자 기본 예외"""

    pass


class BrowserInitializationError(BrowserManagerError):
    """브라우저 초기화 실패"""

    pass


class ElementInteractionError(BrowserManagerError):
    """요소 상호작용 실패"""

    pass


class NavigationError(BrowserManagerError):
    """페이지 이동 실패"""

    pass


# 설정 데이터 클래스 (기존 유지)
@dataclass
class BrowserConfig:
    """브라우저 설정"""

    headless: bool = False
    timeout: int = 15
    window_size: Tuple[int, int] = (1920, 1080)
    user_agent: Optional[str] = None
    download_dir: Optional[str] = None
    disable_images: bool = False
    disable_javascript: bool = False
    proxy: Optional[str] = None
    max_retries: int = 3
    retry_delay: float = 1.0


class ScrollSpeed(Enum):
    """스크롤 속도"""

    SLOW = {"step": 100, "delay": 0.5}
    MEDIUM = {"step": 200, "delay": 0.3}
    FAST = {"step": 300, "delay": 0.1}


class BrowserManager:
    """리팩터링된 브라우저 관리자 v2 - 비동기 지원"""

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self.driver: Optional[ChromeDriver] = None
        self.wait: Optional[WebDriverWait] = None
        self.logger = logging.getLogger(__name__)
        self._is_initialized = False
        self._session_id: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # === 기존 동기 메서드들 (하위 호환성) ===

    @property
    def is_initialized(self) -> bool:
        """초기화 상태 확인"""
        return self._is_initialized and self._is_driver_alive()

    def _is_driver_alive(self) -> bool:
        """드라이버 생존 확인"""
        if not self.driver:
            return False

        try:
            _ = self.driver.current_url
            return True
        except (InvalidSessionIdException, WebDriverException):
            return False

    def initialize(self) -> None:
        """브라우저 초기화"""
        if self._is_initialized:
            self.logger.warning("브라우저가 이미 초기화되었습니다.")
            return

        for attempt in range(self.config.max_retries):
            try:
                self._initialize_driver()
                self._verify_initialization()
                self._is_initialized = True
                self.logger.info("브라우저 초기화 성공")
                return

            except WebDriverException as e:
                self.logger.error(
                    f"초기화 실패 (시도 {attempt + 1}/{self.config.max_retries}): {e}"
                )
                self._cleanup()

                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay)
                else:
                    raise BrowserInitializationError(f"브라우저 초기화 실패: {e}")

            except Exception as e:
                self._cleanup()
                raise BrowserInitializationError(f"예상치 못한 오류: {e}")

    # === 새로운 비동기 메서드들 ===

    async def initialize_async(self) -> None:
        """비동기 브라우저 초기화"""
        if self._is_initialized:
            self.logger.warning("브라우저가 이미 초기화되었습니다.")
            return

        self._loop = asyncio.get_event_loop()

        for attempt in range(self.config.max_retries):
            try:
                await self._run_in_executor(self._initialize_driver)
                await self._run_in_executor(self._verify_initialization)
                self._is_initialized = True
                self.logger.info("브라우저 초기화 성공")
                return

            except WebDriverException as e:
                self.logger.error(
                    f"초기화 실패 (시도 {attempt + 1}/{self.config.max_retries}): {e}"
                )
                await self._run_in_executor(self._cleanup)

                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    raise BrowserInitializationError(f"브라우저 초기화 실패: {e}")

            except Exception as e:
                await self._run_in_executor(self._cleanup)
                raise BrowserInitializationError(f"예상치 못한 오류: {e}")

    async def _run_in_executor(self, func: Callable[..., T], *args, **kwargs) -> T:
        """동기 함수를 비동기로 실행"""
        loop = self._loop or asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    @asynccontextmanager
    async def ensure_initialized_async(self):
        """비동기 초기화 보장 컨텍스트 매니저"""
        if not self.is_initialized:
            raise BrowserManagerError("브라우저가 초기화되지 않았습니다.")

        try:
            yield
        except InvalidSessionIdException:
            self._is_initialized = False
            raise BrowserManagerError("브라우저 세션이 만료되었습니다.")

    # === 페이지 네비게이션 (동기 + 비동기) ===

    def navigate(self, url: str, wait_time: float = 2.0) -> None:
        """URL로 이동 (동기)"""
        with self.ensure_initialized():
            with self._error_handler(f"페이지 이동: {url}"):
                self.driver.get(url)
                time.sleep(wait_time)

                self.wait.until(
                    lambda driver: driver.execute_script("return document.readyState")
                    == "complete"
                )

    async def navigate_async(self, url: str, wait_time: float = 2.0) -> None:
        """URL로 이동 (비동기)"""
        async with self.ensure_initialized_async():
            await self._run_in_executor(self.driver.get, url)
            await asyncio.sleep(wait_time)

            await self._run_in_executor(
                self.wait.until,
                lambda driver: driver.execute_script("return document.readyState")
                == "complete",
            )

    # === 요소 찾기 (타입 힌팅 개선) ===

    def find_element(
        self, selector: str, by: By = By.CSS_SELECTOR, timeout: Optional[float] = None
    ) -> Optional[WebElement]:
        """요소 찾기 (동기)"""
        with self.ensure_initialized():
            timeout = timeout or self.config.timeout

            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, selector))
                )
                return element
            except TimeoutException:
                return None

    async def find_element_async(
        self, selector: str, by: By = By.CSS_SELECTOR, timeout: Optional[float] = None
    ) -> Optional[WebElement]:
        """요소 찾기 (비동기)"""
        async with self.ensure_initialized_async():
            timeout = timeout or self.config.timeout

            try:
                element = await self._run_in_executor(
                    WebDriverWait(self.driver, timeout).until,
                    EC.presence_of_element_located((by, selector)),
                )
                return element
            except TimeoutException:
                return None

    def find_elements(
        self, selector: str, by: By = By.CSS_SELECTOR
    ) -> List[WebElement]:
        """여러 요소 찾기 (동기)"""
        with self.ensure_initialized():
            with self._error_handler(f"요소들 찾기: {selector}"):
                return self.driver.find_elements(by, selector)

    async def find_elements_async(
        self, selector: str, by: By = By.CSS_SELECTOR
    ) -> List[WebElement]:
        """여러 요소 찾기 (비동기)"""
        async with self.ensure_initialized_async():
            return await self._run_in_executor(self.driver.find_elements, by, selector)

    # === 요소 상호작용 (타입 힌팅 개선) ===

    def click(
        self,
        selector: str,
        by: By = By.CSS_SELECTOR,
        wait_clickable: bool = True,
        scroll_into_view: bool = True,
        retry: bool = True,
    ) -> None:
        """요소 클릭 (동기)"""
        with self.ensure_initialized():
            element = self.find_element(selector, by)
            if not element:
                raise ElementInteractionError(f"클릭할 요소를 찾을 수 없음: {selector}")

            if wait_clickable:
                self.wait_for_element(selector, by, "clickable")

            if scroll_into_view:
                self.scroll_to_element(element)

            self._perform_click(element, selector)

    async def click_async(
        self,
        selector: str,
        by: By = By.CSS_SELECTOR,
        wait_clickable: bool = True,
        scroll_into_view: bool = True,
        retry: bool = True,
    ) -> None:
        """요소 클릭 (비동기)"""
        async with self.ensure_initialized_async():
            element = await self.find_element_async(selector, by)
            if not element:
                raise ElementInteractionError(f"클릭할 요소를 찾을 수 없음: {selector}")

            if wait_clickable:
                await self.wait_for_element_async(selector, by, "clickable")

            if scroll_into_view:
                await self.scroll_to_element_async(element)

            await self._run_in_executor(self._perform_click, element, selector)

    def _perform_click(self, element: WebElement, selector: str) -> None:
        """실제 클릭 수행"""
        click_methods = [
            lambda: element.click(),
            lambda: self.driver.execute_script("arguments[0].click();", element),
            lambda: ActionChains(self.driver)
            .move_to_element(element)
            .click()
            .perform(),
        ]

        for method in click_methods:
            try:
                with self._error_handler(f"클릭: {selector}"):
                    method()
                    return
            except ElementInteractionError:
                if method == click_methods[-1]:
                    raise

    def type_text(
        self,
        selector: str,
        text: str,
        by: By = By.CSS_SELECTOR,
        clear_first: bool = True,
        human_typing: bool = True,
    ) -> None:
        """텍스트 입력 (동기)"""
        with self.ensure_initialized():
            element = self.find_element(selector, by)
            if not element:
                raise ElementInteractionError(f"입력할 요소를 찾을 수 없음: {selector}")

            self._perform_typing(element, text, clear_first, human_typing)

    async def type_text_async(
        self,
        selector: str,
        text: str,
        by: By = By.CSS_SELECTOR,
        clear_first: bool = True,
        human_typing: bool = True,
    ) -> None:
        """텍스트 입력 (비동기)"""
        async with self.ensure_initialized_async():
            element = await self.find_element_async(selector, by)
            if not element:
                raise ElementInteractionError(f"입력할 요소를 찾을 수 없음: {selector}")

            await self._perform_typing_async(element, text, clear_first, human_typing)

    def _perform_typing(
        self, element: WebElement, text: str, clear_first: bool, human_typing: bool
    ) -> None:
        """실제 타이핑 수행 (동기)"""
        with self._error_handler("텍스트 입력"):
            element.click()
            time.sleep(0.3)

            if clear_first:
                element.clear()
                element.send_keys(Keys.CONTROL + "a")
                element.send_keys(Keys.DELETE)
                time.sleep(0.2)

            if human_typing:
                for char in text:
                    element.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
            else:
                element.send_keys(text)

    async def _perform_typing_async(
        self, element: WebElement, text: str, clear_first: bool, human_typing: bool
    ) -> None:
        """실제 타이핑 수행 (비동기)"""
        await self._run_in_executor(element.click)
        await asyncio.sleep(0.3)

        if clear_first:
            await self._run_in_executor(element.clear)
            await self._run_in_executor(element.send_keys, Keys.CONTROL + "a")
            await self._run_in_executor(element.send_keys, Keys.DELETE)
            await asyncio.sleep(0.2)

        if human_typing:
            for char in text:
                await self._run_in_executor(element.send_keys, char)
                await asyncio.sleep(random.uniform(0.05, 0.15))
        else:
            await self._run_in_executor(element.send_keys, text)

    # === 요소 정보 가져오기 (타입 힌팅 개선) ===

    def get_text(self, selector: str, by: By = By.CSS_SELECTOR) -> str:
        """요소 텍스트 가져오기 (동기)"""
        with self.ensure_initialized():
            element = self.find_element(selector, by)
            return element.text.strip() if element else ""

    async def get_text_async(self, selector: str, by: By = By.CSS_SELECTOR) -> str:
        """요소 텍스트 가져오기 (비동기)"""
        async with self.ensure_initialized_async():
            element = await self.find_element_async(selector, by)
            if element:
                text = await self._run_in_executor(lambda: element.text)
                return text.strip()
            return ""

    def get_attribute(
        self, selector: str, attribute: str, by: By = By.CSS_SELECTOR
    ) -> str:
        """요소 속성 가져오기 (동기)"""
        with self.ensure_initialized():
            element = self.find_element(selector, by)
            return element.get_attribute(attribute) if element else ""

    async def get_attribute_async(
        self, selector: str, attribute: str, by: By = By.CSS_SELECTOR
    ) -> str:
        """요소 속성 가져오기 (비동기)"""
        async with self.ensure_initialized_async():
            element = await self.find_element_async(selector, by)
            if element:
                return await self._run_in_executor(element.get_attribute, attribute)
            return ""

    # === 대기 메서드들 (비동기 추가) ===

    def wait_for_element(
        self,
        selector: str,
        by: By = By.CSS_SELECTOR,
        condition: str = "presence",
        timeout: Optional[float] = None,
    ) -> bool:
        """요소 대기 (동기)"""
        with self.ensure_initialized():
            timeout = timeout or self.config.timeout

            conditions = {
                "presence": EC.presence_of_element_located,
                "visible": EC.visibility_of_element_located,
                "clickable": EC.element_to_be_clickable,
                "invisible": EC.invisibility_of_element_located,
            }

            condition_func = conditions.get(condition, EC.presence_of_element_located)

            try:
                WebDriverWait(self.driver, timeout).until(
                    condition_func((by, selector))
                )
                return True
            except TimeoutException:
                return False

    async def wait_for_element_async(
        self,
        selector: str,
        by: By = By.CSS_SELECTOR,
        condition: str = "presence",
        timeout: Optional[float] = None,
    ) -> bool:
        """요소 대기 (비동기)"""
        async with self.ensure_initialized_async():
            timeout = timeout or self.config.timeout

            conditions = {
                "presence": EC.presence_of_element_located,
                "visible": EC.visibility_of_element_located,
                "clickable": EC.element_to_be_clickable,
                "invisible": EC.invisibility_of_element_located,
            }

            condition_func = conditions.get(condition, EC.presence_of_element_located)

            try:
                await self._run_in_executor(
                    WebDriverWait(self.driver, timeout).until,
                    condition_func((by, selector)),
                )
                return True
            except TimeoutException:
                return False

    # === 스크롤 메서드들 (비동기 추가) ===

    def scroll_to_element(self, element: WebElement) -> None:
        """요소로 스크롤 (동기)"""
        with self.ensure_initialized():
            with self._error_handler("요소로 스크롤"):
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                    element,
                )
                time.sleep(0.5)

    async def scroll_to_element_async(self, element: WebElement) -> None:
        """요소로 스크롤 (비동기)"""
        async with self.ensure_initialized_async():
            await self._run_in_executor(
                self.driver.execute_script,
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                element,
            )
            await asyncio.sleep(0.5)

    def natural_scroll(
        self, duration: float, speed: Union[str, ScrollSpeed] = ScrollSpeed.MEDIUM
    ) -> None:
        """자연스러운 스크롤 (동기)"""
        with self.ensure_initialized():
            if isinstance(speed, str):
                speed = ScrollSpeed[speed.upper()]

            config = speed.value
            start_time = time.time()

            while time.time() - start_time < duration:
                distance = random.randint(
                    int(config["step"] * 0.8), int(config["step"] * 1.2)
                )

                self.scroll_by(0, distance)
                time.sleep(config["delay"])

                if random.random() < 0.2:
                    self.scroll_by(0, -distance // 2)
                    time.sleep(config["delay"] * 2)

    async def natural_scroll_async(
        self, duration: float, speed: Union[str, ScrollSpeed] = ScrollSpeed.MEDIUM
    ) -> None:
        """자연스러운 스크롤 (비동기)"""
        async with self.ensure_initialized_async():
            if isinstance(speed, str):
                speed = ScrollSpeed[speed.upper()]

            config = speed.value
            start_time = time.time()

            while time.time() - start_time < duration:
                distance = random.randint(
                    int(config["step"] * 0.8), int(config["step"] * 1.2)
                )

                await self.scroll_by_async(0, distance)
                await asyncio.sleep(config["delay"])

                if random.random() < 0.2:
                    await self.scroll_by_async(0, -distance // 2)
                    await asyncio.sleep(config["delay"] * 2)

    def scroll_by(self, x: int, y: int) -> None:
        """지정된 픽셀만큼 스크롤 (동기)"""
        with self.ensure_initialized():
            with self._error_handler("스크롤"):
                self.driver.execute_script(f"window.scrollBy({x}, {y});")

    async def scroll_by_async(self, x: int, y: int) -> None:
        """지정된 픽셀만큼 스크롤 (비동기)"""
        async with self.ensure_initialized_async():
            await self._run_in_executor(
                self.driver.execute_script, f"window.scrollBy({x}, {y});"
            )

    # === JavaScript 실행 (타입 개선) ===

    def execute_script(self, script: str, *args: Any) -> Any:
        """JavaScript 실행 (동기)"""
        with self.ensure_initialized():
            with self._error_handler("스크립트 실행"):
                return self.driver.execute_script(script, *args)

    async def execute_script_async(self, script: str, *args: Any) -> Any:
        """JavaScript 실행 (비동기)"""
        async with self.ensure_initialized_async():
            return await self._run_in_executor(
                self.driver.execute_script, script, *args
            )

    # === 프레임 처리 (비동기 추가) ===

    def switch_to_frame(self, frame_reference: Union[str, int, WebElement]) -> None:
        """프레임으로 전환 (동기)"""
        with self.ensure_initialized():
            with self._error_handler(f"프레임 전환: {frame_reference}"):
                if isinstance(frame_reference, str):
                    frame = self.find_element(frame_reference)
                    if frame:
                        self.driver.switch_to.frame(frame)
                    else:
                        self.driver.switch_to.frame(frame_reference)
                else:
                    self.driver.switch_to.frame(frame_reference)

    async def switch_to_frame_async(
        self, frame_reference: Union[str, int, WebElement]
    ) -> None:
        """프레임으로 전환 (비동기)"""
        async with self.ensure_initialized_async():
            if isinstance(frame_reference, str):
                frame = await self.find_element_async(frame_reference)
                if frame:
                    await self._run_in_executor(self.driver.switch_to.frame, frame)
                else:
                    await self._run_in_executor(
                        self.driver.switch_to.frame, frame_reference
                    )
            else:
                await self._run_in_executor(
                    self.driver.switch_to.frame, frame_reference
                )

    def switch_to_default_content(self) -> None:
        """기본 컨텐츠로 복귀 (동기)"""
        with self.ensure_initialized():
            with self._error_handler("기본 컨텐츠로 복귀"):
                self.driver.switch_to.default_content()

    async def switch_to_default_content_async(self) -> None:
        """기본 컨텐츠로 복귀 (비동기)"""
        async with self.ensure_initialized_async():
            await self._run_in_executor(self.driver.switch_to.default_content)

    # === 페이지 정보 (타입 개선) ===

    @property
    def current_url(self) -> str:
        """현재 URL"""
        with self.ensure_initialized():
            return self.driver.current_url

    @property
    def title(self) -> str:
        """페이지 제목"""
        with self.ensure_initialized():
            return self.driver.title

    @property
    def page_source(self) -> str:
        """페이지 소스"""
        with self.ensure_initialized():
            return self.driver.page_source

    async def get_current_url_async(self) -> str:
        """현재 URL (비동기)"""
        async with self.ensure_initialized_async():
            return await self._run_in_executor(lambda: self.driver.current_url)

    async def get_title_async(self) -> str:
        """페이지 제목 (비동기)"""
        async with self.ensure_initialized_async():
            return await self._run_in_executor(lambda: self.driver.title)

    async def get_page_source_async(self) -> str:
        """페이지 소스 (비동기)"""
        async with self.ensure_initialized_async():
            return await self._run_in_executor(lambda: self.driver.page_source)

    # === 리소스 관리 ===

    async def close_async(self) -> None:
        """브라우저 종료 (비동기)"""
        if self._is_initialized:
            self.logger.info("브라우저 종료 중...")
            await self._run_in_executor(self._cleanup)
            self.logger.info("브라우저가 정상적으로 종료되었습니다.")

    # ... 기존 메서드들은 그대로 유지 ...

    def _initialize_driver(self) -> None:
        """드라이버 초기화"""
        options = self._create_chrome_options()

        self.driver = uc.Chrome(options=options, version_main=None)
        self.wait = WebDriverWait(self.driver, self.config.timeout)
        self._session_id = self.driver.session_id

        self._apply_stealth_settings()

    def _create_chrome_options(self) -> uc.ChromeOptions:
        """Chrome 옵션 생성"""
        options = uc.ChromeOptions()

        # 기본 옵션
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-translate")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-device-discovery-notifications")
        options.add_argument(
            f"--window-size={self.config.window_size[0]},{self.config.window_size[1]}"
        )

        # 헤드리스 모드
        if self.config.headless:
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

        # User-Agent
        if self.config.user_agent:
            options.add_argument(f"--user-agent={self.config.user_agent}")
        else:
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            ]
            options.add_argument(f"--user-agent={random.choice(user_agents)}")

        # 프록시 설정
        if self.config.proxy:
            options.add_argument(f"--proxy-server={self.config.proxy}")

        # 다운로드 디렉토리
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "popups": 2,
            },
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        }

        if self.config.download_dir:
            prefs["download.default_directory"] = self.config.download_dir
            prefs["download.prompt_for_download"] = False

        if self.config.disable_images:
            prefs["profile.managed_default_content_settings"] = {"images": 2}

        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # JavaScript 비활성화
        if self.config.disable_javascript:
            prefs["profile.managed_default_content_settings"]["javascript"] = 2

        return options

    def _apply_stealth_settings(self) -> None:
        """스텔스 설정 적용"""
        stealth_js = """
        // WebDriver 속성 숨기기
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        
        // Chrome 자동화 감지 제거
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        // 언어 설정
        Object.defineProperty(navigator, 'languages', {
            get: () => ['ko-KR', 'ko', 'en-US', 'en']
        });
        
        // 권한 쿼리 오버라이드
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """

        try:
            self.driver.execute_script(stealth_js)
        except WebDriverException as e:
            self.logger.warning(f"스텔스 설정 적용 실패: {e}")

    def _verify_initialization(self) -> None:
        """초기화 검증"""
        try:
            self.driver.get("about:blank")
            if self.driver.title is None:
                raise BrowserInitializationError("브라우저 초기화 검증 실패")
        except WebDriverException as e:
            raise BrowserInitializationError(f"초기화 검증 중 오류: {e}")

    def _cleanup(self) -> None:
        """리소스 정리"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.error(f"드라이버 정리 중 오류: {e}")
            finally:
                self.driver = None
                self.wait = None
                self._is_initialized = False
                self._session_id = None

    @contextmanager
    def _error_handler(self, operation: str):
        """에러 처리 컨텍스트 매니저"""
        try:
            yield
        except TimeoutException as e:
            self.logger.error(f"{operation} - 시간 초과: {e}")
            raise ElementInteractionError(f"{operation} 시간 초과")
        except NoSuchElementException as e:
            self.logger.error(f"{operation} - 요소 없음: {e}")
            raise ElementInteractionError(f"{operation} 요소를 찾을 수 없음")
        except ElementNotInteractableException as e:
            self.logger.error(f"{operation} - 상호작용 불가: {e}")
            raise ElementInteractionError(f"{operation} 요소와 상호작용할 수 없음")
        except StaleElementReferenceException as e:
            self.logger.error(f"{operation} - 오래된 참조: {e}")
            raise ElementInteractionError(f"{operation} 요소가 더 이상 유효하지 않음")
        except InvalidSessionIdException as e:
            self.logger.error(f"{operation} - 세션 만료: {e}")
            self._is_initialized = False
            raise BrowserManagerError(f"{operation} 브라우저 세션이 만료됨")
        except WebDriverException as e:
            self.logger.error(f"{operation} - WebDriver 오류: {e}")
            raise BrowserManagerError(f"{operation} WebDriver 오류: {e}")

    @contextmanager
    def ensure_initialized(self):
        """초기화 보장 컨텍스트 매니저"""
        if not self.is_initialized:
            raise BrowserManagerError("브라우저가 초기화되지 않았습니다.")

        try:
            yield
        except InvalidSessionIdException:
            self._is_initialized = False
            raise BrowserManagerError("브라우저 세션이 만료되었습니다.")

    def refresh(self) -> None:
        """페이지 새로고침"""
        with self.ensure_initialized():
            with self._error_handler("페이지 새로고침"):
                self.driver.refresh()
                self.wait.until(
                    lambda driver: driver.execute_script("return document.readyState")
                    == "complete"
                )

    def back(self) -> None:
        """뒤로 가기"""
        with self.ensure_initialized():
            with self._error_handler("뒤로 가기"):
                self.driver.back()

    def forward(self) -> None:
        """앞으로 가기"""
        with self.ensure_initialized():
            with self._error_handler("앞으로 가기"):
                self.driver.forward()

    def is_visible(self, selector: str, by: By = By.CSS_SELECTOR) -> bool:
        """요소 표시 여부 확인"""
        with self.ensure_initialized():
            element = self.find_element(selector, by, timeout=1)
            return element.is_displayed() if element else False

    def scroll_to_bottom(self) -> None:
        """페이지 하단으로 스크롤"""
        with self.ensure_initialized():
            with self._error_handler("하단 스크롤"):
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                time.sleep(1)

    def take_screenshot(self, filename: str) -> None:
        """스크린샷 저장"""
        with self.ensure_initialized():
            with self._error_handler("스크린샷"):
                self.driver.save_screenshot(filename)

    def get_screenshot_as_base64(self) -> str:
        """스크린샷을 Base64로 반환"""
        with self.ensure_initialized():
            with self._error_handler("스크린샷 Base64"):
                return self.driver.get_screenshot_as_base64()

    def get_cookies(self) -> List[Dict[str, Any]]:
        """모든 쿠키 가져오기"""
        with self.ensure_initialized():
            with self._error_handler("쿠키 가져오기"):
                return self.driver.get_cookies()

    def add_cookie(self, cookie: Dict[str, Any]) -> None:
        """쿠키 추가"""
        with self.ensure_initialized():
            with self._error_handler("쿠키 추가"):
                self.driver.add_cookie(cookie)

    def delete_all_cookies(self) -> None:
        """모든 쿠키 삭제"""
        with self.ensure_initialized():
            with self._error_handler("쿠키 삭제"):
                self.driver.delete_all_cookies()

    def execute_async_script(self, script: str, *args: Any) -> Any:
        """비동기 JavaScript 실행"""
        with self.ensure_initialized():
            with self._error_handler("비동기 스크립트 실행"):
                return self.driver.execute_async_script(script, *args)

    def close(self) -> None:
        """브라우저 종료"""
        if self._is_initialized:
            self.logger.info("브라우저 종료 중...")
            self._cleanup()
            self.logger.info("브라우저가 정상적으로 종료되었습니다.")

    def __enter__(self):
        """컨텍스트 매니저 진입"""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.close()

    def __del__(self):
        """소멸자"""
        if self._is_initialized:
            self.close()


# === BrowserPool도 비동기 지원 추가 ===


class AsyncBrowserPool:
    """비동기 브라우저 풀 관리자"""

    def __init__(self, size: int = 3, config: Optional[BrowserConfig] = None):
        self.size = size
        self.config = config or BrowserConfig()
        self.pool: List[BrowserManager] = []
        self.available: List[BrowserManager] = []
        self.logger = logging.getLogger(__name__)
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """풀 초기화 (비동기)"""
        tasks = []
        for i in range(self.size):
            tasks.append(self._create_browser(i))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"브라우저 {i+1} 초기화 실패: {result}")
            else:
                self.logger.info(f"브라우저 {i+1}/{self.size} 초기화 완료")

    async def _create_browser(self, index: int) -> BrowserManager:
        """브라우저 생성 (비동기)"""
        browser = BrowserManager(self.config)
        await browser.initialize_async()
        self.pool.append(browser)
        self.available.append(browser)
        return browser

    @asynccontextmanager
    async def acquire(self):
        """브라우저 획득 (비동기)"""
        browser = None
        async with self._lock:
            if not self.available:
                raise BrowserManagerError("사용 가능한 브라우저가 없습니다.")

            browser = self.available.pop(0)

        try:
            yield browser
        finally:
            if browser:
                async with self._lock:
                    self.available.append(browser)

    async def close_all(self) -> None:
        """모든 브라우저 종료 (비동기)"""
        tasks = []
        for browser in self.pool:
            tasks.append(browser.close_async())

        await asyncio.gather(*tasks, return_exceptions=True)

        self.pool.clear()
        self.available.clear()


# 기존 BrowserPool 클래스는 그대로 유지
class BrowserPool:
    """브라우저 풀 관리자"""

    def __init__(self, size: int = 3, config: Optional[BrowserConfig] = None):
        self.size = size
        self.config = config or BrowserConfig()
        self.pool: List[BrowserManager] = []
        self.available: List[BrowserManager] = []
        self.logger = logging.getLogger(__name__)

    def initialize(self) -> None:
        """풀 초기화"""
        for i in range(self.size):
            try:
                browser = BrowserManager(self.config)
                browser.initialize()
                self.pool.append(browser)
                self.available.append(browser)
                self.logger.info(f"브라우저 {i+1}/{self.size} 초기화 완료")
            except Exception as e:
                self.logger.error(f"브라우저 {i+1} 초기화 실패: {e}")

    @contextmanager
    def acquire(self):
        """브라우저 획득"""
        browser = None
        try:
            if not self.available:
                raise BrowserManagerError("사용 가능한 브라우저가 없습니다.")

            browser = self.available.pop(0)
            yield browser

        finally:
            if browser:
                self.available.append(browser)

    def close_all(self) -> None:
        """모든 브라우저 종료"""
        for browser in self.pool:
            try:
                browser.close()
            except Exception as e:
                self.logger.error(f"브라우저 종료 실패: {e}")

        self.pool.clear()
        self.available.clear()
