"""
네이버 블로그 자동화 프로그램 설치 스크립트
"""

from setuptools import setup, find_packages
from pathlib import Path

# README 읽기
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# requirements.txt 읽기
requirements = []
with open("requirements.txt", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#"):
            requirements.append(line)

setup(
    name="naver-blog-automation",
    version="2.0.0",
    author="Alien Marketing",
    author_email="your.email@example.com",
    description="네이버 블로그 자동화 프로그램 - 작업 기반 스케줄러",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/naver-blog-automation",
    project_urls={
        "Bug Tracker": "https://github.com/yourusername/naver-blog-automation/issues",
        "Documentation": "https://github.com/yourusername/naver-blog-automation/wiki",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Natural Language :: Korean",
    ],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "black>=23.12.0",
            "flake8>=6.1.0",
            "mypy>=1.7.1",
            "pre-commit>=3.5.0",
        ],
        "docs": [
            "sphinx>=7.2.6",
            "sphinx-rtd-theme>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "naver-blog-automation=main:main",
            "nba=main:main",  # 짧은 별칭
            "nba-admin=main:run_admin_mode",  # 관리자 모드 직접 실행
        ],
        "gui_scripts": [
            "naver-blog-automation-gui=main:run_gui_mode",
        ],
    },
    include_package_data=True,
    package_data={
        "": [
            "*.json",
            "*.txt",
            "*.md",
            "*.yaml",
            "*.yml",
        ],
    },
    data_files=[
        ("", ["requirements.txt", "README.md", "LICENSE"]),
        ("config", ["config.json.example"]),
    ],
    zip_safe=False,
)
