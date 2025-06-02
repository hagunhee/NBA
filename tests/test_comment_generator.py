import os
from dotenv import load_dotenv
from src.automation.comment_generator import CommentGenerator

load_dotenv()


def test_comment_generation():
    # API 키 확인
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY를 .env 파일에 설정해주세요!")
        return

    # 댓글 생성기 초기화
    generator = CommentGenerator(api_key)

    # 테스트 포스트
    test_post_title = "맛있는 파스타 만들기 레시피"
    test_post_content = """
    오늘은 집에서 쉽게 만들 수 있는 토마토 파스타 레시피를 공유해드리려고 해요.
    
    재료:
    - 파스타면 200g
    - 토마토 소스 300g
    - 마늘 3쪽
    - 올리브오일
    - 바질
    
    만드는 방법:
    1. 물을 끓여서 파스타를 삶아주세요
    2. 팬에 올리브오일을 두르고 마늘을 볶아주세요
    3. 토마토 소스를 넣고 끓여주세요
    4. 삶은 파스타를 넣고 섞어주세요
    
    정말 간단하죠? 20분이면 완성됩니다!
    """

    # 댓글 생성 테스트
    print("댓글 생성 중...")
    comment = generator.generate_comment(test_post_title, test_post_content)

    if comment:
        print(f"\n생성된 댓글:\n{comment}")
    else:
        print("댓글 생성 실패!")


if __name__ == "__main__":
    test_comment_generation()
