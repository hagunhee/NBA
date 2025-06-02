import json
import os
from typing import Any, Dict, Optional


class Config:
    """프로그램 설정 관리"""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self) -> Dict:
        """설정 파일 로드"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"설정 파일 로드 실패: {e}")
                return self.get_default_config()
        else:
            return self.get_default_config()

    def get_default_config(self) -> Dict:
        """기본 설정"""
        return {
            "license": {"key": ""},
            "account": {"naver_id": ""},
            "automation": {
                "min_stay_time": 60,
                "max_stay_time": 180,
                "min_delay": 10,
                "max_delay": 30,
                "daily_limit": 20,
                "scroll_speed": "보통",
                "natural_scroll": True,
                "auto_comment": True,
            },
            "browser": {
                "headless": False,
                "window_size": "1280x800",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            "cache": {"enabled": True, "ttl_days": 7, "max_entries": 1000},
            "update": {"auto_check": True, "check_interval": 86400, "last_check": ""},
        }

    def save(self):
        """설정 저장"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"설정 저장 실패: {e}")

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """설정값 가져오기"""
        try:
            return self.config[section][key]
        except KeyError:
            return default

    def set(self, section: str, key: str, value: Any):
        """설정값 저장"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value

    def get_section(self, section: str) -> Optional[Dict]:
        """섹션 전체 가져오기"""
        return self.config.get(section)
