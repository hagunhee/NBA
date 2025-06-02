from setuptools import setup, find_packages

setup(
    name="naver-blog-automation",
    version="1.0.0",
    author="Your Name",
    description="네이버 블로그 자동 이웃관리 프로그램",
    packages=find_packages(),
    install_requires=[
        line.strip()
        for line in open("requirements.txt").readlines()
        if not line.startswith("#")
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "naver-blog-manager=src.main:main",
        ],
    },
)
