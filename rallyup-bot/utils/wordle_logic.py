import re
from typing import Tuple, List

class WordleGame:
    """워들 게임 로직 처리 클래스"""
    
    # 결과 상수
    CORRECT = 1      # 🟩 정확한 위치의 정확한 글자
    WRONG_POSITION = 2   # 🟨 다른 위치의 정확한 글자  
    NOT_IN_WORD = 0  # ⬜ 단어에 없는 글자
    
    # 이모지 매핑
    EMOJI_MAP = {
        CORRECT: "🟩",
        WRONG_POSITION: "🟨", 
        NOT_IN_WORD: "⬜"
    }
    
    @staticmethod
    def validate_korean_word(word: str) -> bool:
        """한글 5글자 단어 검증"""
        if not word or len(word) != 5:
            return False
        
        # 한글만 허용 (완성형 한글)
        korean_pattern = re.compile(r'^[가-힣]{5}$')
        return bool(korean_pattern.match(word))
    
    @staticmethod
    def compare_words(guess: str, answer: str) -> str:
        """
        추측과 정답을 비교하여 결과 패턴 반환
        
        Args:
            guess: 사용자의 추측 (5글자)
            answer: 정답 단어 (5글자)
            
        Returns:
            결과 패턴 문자열 (예: "10201" - 각 자리는 0,1,2 중 하나)
        """
        if len(guess) != 5 or len(answer) != 5:
            return "00000"
        
        result = [0] * 5
        answer_chars = list(answer)
        guess_chars = list(guess)
        
        # 1단계: 정확한 위치 찾기 (🟩)
        for i in range(5):
            if guess_chars[i] == answer_chars[i]:
                result[i] = WordleGame.CORRECT
                answer_chars[i] = None  # 사용된 글자 표시
                guess_chars[i] = None
        
        # 2단계: 다른 위치의 올바른 글자 찾기 (🟨)
        for i in range(5):
            if guess_chars[i] is not None:  # 아직 처리되지 않은 글자
                for j in range(5):
                    if answer_chars[j] == guess_chars[i]:
                        result[i] = WordleGame.WRONG_POSITION
                        answer_chars[j] = None  # 사용된 글자 표시
                        break
        
        return ''.join(map(str, result))
    
    @staticmethod
    def pattern_to_emoji(pattern: str) -> str:
        """패턴 문자열을 이모지로 변환"""
        return ''.join(WordleGame.EMOJI_MAP.get(int(char), "⬜") for char in pattern)
    
    @staticmethod
    def is_winner(pattern: str) -> bool:
        """승리 조건 확인 (모든 글자가 정확한 위치)"""
        return pattern == "11111"
    
    @staticmethod
    def format_guess_result(guess: str, pattern: str) -> str:
        """추측 결과를 보기 좋게 포맷팅"""
        emoji_pattern = WordleGame.pattern_to_emoji(pattern)
        
        # 각 글자에 이모지 붙이기
        formatted_chars = []
        for i, char in enumerate(guess):
            emoji = WordleGame.EMOJI_MAP.get(int(pattern[i]), "⬜")
            formatted_chars.append(f"{char}{emoji}")
        
        return " ".join(formatted_chars) + f"\n{emoji_pattern}"
    
    @staticmethod
    def calculate_remaining_points(bet_amount: int, attempts_used: int, points_per_failure: int) -> int:
        """남은 포인트 계산"""
        return max(0, bet_amount - (attempts_used * points_per_failure))
    
    @staticmethod
    def can_continue_game(remaining_points: int, points_per_failure: int) -> bool:
        """게임을 계속할 수 있는지 확인"""
        return remaining_points >= points_per_failure
    
    @staticmethod
    def generate_game_board(guesses: List[Tuple[str, str]], max_attempts: int = 10) -> str:
        """게임 보드 생성 (지금까지의 모든 추측 표시)"""
        board_lines = []
        
        for i, (guess, pattern) in enumerate(guesses):
            emoji_line = WordleGame.pattern_to_emoji(pattern)
            board_lines.append(f"{i+1}. {guess} {emoji_line}")
        
        # 남은 빈 줄들
        for i in range(len(guesses), max_attempts):
            board_lines.append(f"{i+1}. ⬜⬜⬜⬜⬜")
        
        return "\n".join(board_lines)

# 테스트용 함수들
def test_wordle_logic():
    """워들 로직 테스트"""
    print("=== 워들 로직 테스트 ===")
    
    # 테스트 케이스들
    test_cases = [
        ("사과나무딸기", "사과나무딸기", "11111"),  # 완전 일치
        ("사과나무딸기", "사과나무스기", "11110"),  # 마지막 글자만 틀림
        ("사과나무딸기", "나무사과딸기", "22221"),  # 위치 바뀜
        ("사과나무딸기", "바나나무딸기", "01111"),  # 첫 글자만 틀림
        ("사과나무딸기", "완전다른단어", "00000"),  # 완전 다름
    ]
    
    for guess, answer, expected in test_cases:
        result = WordleGame.compare_words(guess, answer)
        emoji = WordleGame.pattern_to_emoji(result)
        status = "✅" if result == expected else "❌"
        
        print(f"{status} {guess} vs {answer}")
        print(f"   예상: {expected} | 결과: {result}")
        print(f"   이모지: {emoji}")
        print()

if __name__ == "__main__":
    test_wordle_logic()