# print_tree_filtered.py
# 터미널에 python print_tree_filtered.py

import os


def print_tree(startpath, prefix="", exclude_dirs=None):
    """
    startpath: 트리를 출력할 최상위 경로
    prefix: 들여쓰기를 위한 문자열
    exclude_dirs: 제외할 폴더 이름 리스트 (ex: ["venv"])
    """
    if exclude_dirs is None:
        exclude_dirs = []

    # 최상위 폴더명 출력
    folder_name = os.path.basename(os.path.abspath(startpath))
    print(prefix + folder_name + os.sep)

    entries = sorted(os.listdir(startpath), key=lambda s: s.lower())
    for index, entry in enumerate(entries):
        path = os.path.join(startpath, entry)

        # 디렉터리이면서 제외 대상이면 건너뛰기
        if os.path.isdir(path) and entry in exclude_dirs:
            continue

        is_dir = os.path.isdir(path)
        connector = "├── " if index < len(entries) - 1 else "└── "

        if is_dir:
            print(prefix + connector + entry + os.sep)
            extension = "│   " if index < len(entries) - 1 else "    "
            print_tree(path, prefix + extension, exclude_dirs)
        else:
            print(prefix + connector + entry)


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.abspath(__file__))
    # “venv” 폴더만 제외하도록 설정
    print_tree(project_root, exclude_dirs=["venv"])
