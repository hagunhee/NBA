import PyInstaller.__main__
import os
import shutil


def build():
    # 불필요한 파일 제외
    exclude_patterns = [
        "*.pyc",
        "__pycache__",
        ".git",
        ".env",
        "tests",
        "docs",
        "vscode",
        "*.log",
    ]

    # 이전 빌드 정리
    for dir in ["build", "dist"]:
        if os.path.exists(dir):
            shutil.rmtree(dir)

    # PyInstaller 실행
    PyInstaller.__main__.run(
        [
            "src/main.py",
            "--name=NaverBlogManager",
            "--onefile",
            "--windowed",
            "--add-data=resources;resources",
            "--hidden-import=anthropic",
            "--hidden-import=firebase_admin",
            "--hidden-import=selenium",
            "--hidden-import=undetected_chromedriver",
            "--collect-all=undetected_chromedriver",
            "--noconfirm",
            "--clean",
        ]
    )

    print("빌드 완료! dist 폴더에서 실행 파일을 찾을 수 있습니다.")


if __name__ == "__main__":
    build()
