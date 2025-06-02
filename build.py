import PyInstaller.__main__
import os
import shutil


def build():
    PyInstaller.__main__.run(
        [
            "src/main.py",
            "--name=NaverBlogManager",
            "--onefile",
            "--windowed",
            "--icon=resources/icons/app.ico",
            "--add-data=resources;resources",
            "--hidden-import=anthropic",
            "--hidden-import=firebase_admin",
            "--hidden-import=keyring.backends.Windows",
            "--collect-all=undetected_chromedriver",
            "--noconfirm",
            "--clean",
        ]
    )


if __name__ == "__main__":
    build()
