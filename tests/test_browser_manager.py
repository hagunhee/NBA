# tests/test_browser_manager.py
import pytest
from automation.browser_manager import BrowserManager


class TestBrowserManager:
    def test_initialize(self):
        browser = BrowserManager(headless=True)
        assert browser.initialize()
        browser.close()
