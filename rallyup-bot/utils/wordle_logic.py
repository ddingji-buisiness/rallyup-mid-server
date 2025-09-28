import re
from typing import Tuple, List, Optional, Dict, Any
from enum import Enum

class GameMode(Enum):
    """게임 모드"""
    CLASSIC = "classic"        # 기존 5글자 워들
    HYBRID = "hybrid"         # 하이브리드 (유사도 + 글자힌트)
    SIMILARITY_ONLY = "similarity_only"  # 유사도만

class WordleGame:
    """워들 게임 로직 처리 클래스 (확장됨)"""
    
    # 기존 결과 상수들
    CORRECT = 1          # 🟩 정확한 위치의 정확한 글자
    WRONG_POSITION = 2   # 🟨 다른 위치의 정확한 글자  
    NOT_IN_WORD = 0      # ⬜ 단어에 없는 글자
    
    # 이모지 매핑
    EMOJI_MAP = {
        CORRECT: "🟩",
        WRONG_POSITION: "🟨", 
        NOT_IN_WORD: "⬜"
    }
    
    def __init__(self):
        """초기화"""
        pass
    
    @staticmethod
    def validate_korean_word(word: str, require_5_chars: bool = True) -> bool:
        """한글 단어 검증 (확장됨)"""
        if not word:
            return False
        
        # 길이 검증
        if require_5_chars:
            if len(word) != 5:  # 기존 5글자 제한
                return False
        else:
            if not (2 <= len(word) <= 8):  # 하이브리드 모드용 확장
                return False
        
        # 한글만 허용 (완성형 한글)
        korean_pattern = re.compile(r'^[가-힣]+$')
        return bool(korean_pattern.match(word))
    
    @staticmethod
    def compare_words(guess: str, answer: str) -> str:
        """
        추측과 정답을 비교하여 결과 패턴 반환 (기존 로직 유지)
        
        Args:
            guess: 사용자의 추측
            answer: 정답 단어
            
        Returns:
            결과 패턴 문자열 (예: "10201" - 각 자리는 0,1,2 중 하나)
        """
        if len(guess) != len(answer):
            return "0" * len(guess)
        
        result = [0] * len(guess)
        answer_chars = list(answer)
        guess_chars = list(guess)
        
        # 1단계: 정확한 위치 찾기 (🟩)
        for i in range(len(guess)):
            if guess_chars[i] == answer_chars[i]:
                result[i] = WordleGame.CORRECT
                answer_chars[i] = None  # 사용된 글자 표시
                guess_chars[i] = None
        
        # 2단계: 다른 위치의 올바른 글자 찾기 (🟨)
        for i in range(len(guess)):
            if guess_chars[i] is not None:  # 아직 처리되지 않은 글자
                for j in range(len(answer)):
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
        return pattern == "1" * len(pattern)

    @staticmethod
    def validate_hybrid_word(word: str) -> bool:
        """하이브리드 모드용 단어 검증"""
        return WordleGame.validate_korean_word(word, require_5_chars=False)
    
    @staticmethod
    def compare_words_flexible(guess: str, answer: str) -> str:
        """길이가 다른 단어도 비교 가능한 확장 버전"""
        if len(guess) != len(answer):
            # 길이가 다르면 모든 글자를 틀린 것으로 처리
            return "0" * len(guess)
        
        return WordleGame.compare_words(guess, answer)
    
    @staticmethod
    def format_guess_result(guess: str, pattern: str, similarity_score: Optional[float] = None) -> str:
        """추측 결과를 보기 좋게 포맷팅 (확장됨)"""
        emoji_pattern = WordleGame.pattern_to_emoji(pattern)
        
        # 기본 포맷
        result_lines = []
        result_lines.append(f"**{guess}**")
        result_lines.append(emoji_pattern)
        
        # 유사도 점수 추가 (하이브리드 모드)
        if similarity_score is not None:
            similarity_emoji = WordleGame._get_similarity_emoji(similarity_score)
            result_lines.append(f"{similarity_emoji} {similarity_score:+.1f}점")
        
        return "\n".join(result_lines)
    
    @staticmethod
    def _get_similarity_emoji(score: float) -> str:
        """유사도 점수에 따른 이모지"""
        if score >= 80:
            return "🔥🔥🔥"
        elif score >= 60:
            return "🔥🔥"
        elif score >= 40:
            return "🔥"
        elif score >= 20:
            return "❄️"
        else:
            return "🧊"
    
    @staticmethod
    def calculate_remaining_points(bet_amount: int, attempts_used: int, points_per_failure: int) -> int:
        """남은 포인트 계산 (기존 로직 유지)"""
        return max(0, bet_amount - (attempts_used * points_per_failure))
    
    @staticmethod
    def can_continue_game(remaining_points: int, points_per_failure: int) -> bool:
        """게임을 계속할 수 있는지 확인 (기존 로직 유지)"""
        return remaining_points >= points_per_failure
    
    @staticmethod
    def generate_game_board(guesses: List[Tuple[str, str]], max_attempts: int = 10,
                          similarities: Optional[List[float]] = None) -> str:
        """게임 보드 생성 (하이브리드 모드 지원)"""
        board_lines = []
        
        # 헤더
        board_lines.append("```")
        board_lines.append("┌─────────────────────────────────────┐")
        board_lines.append("│           🎯 띵지워들 보드           │")
        board_lines.append("├─────────────────────────────────────┤")
        
        # 추측 기록들
        for i, (guess, pattern) in enumerate(guesses):
            emoji_line = WordleGame.pattern_to_emoji(pattern)
            word_line = " ".join(list(guess))
            
            board_lines.append(f"│ {i+1:2d}. {word_line:<15} │")
            board_lines.append(f"│     {emoji_line:<15} │")
            
            # 유사도 점수 추가 (있는 경우)
            if similarities and i < len(similarities):
                sim_score = similarities[i]
                sim_emoji = WordleGame._get_similarity_emoji(sim_score)
                board_lines.append(f"│     {sim_emoji} {sim_score:+6.1f}점     │")
            
            if i < len(guesses) - 1:
                board_lines.append("├─────────────────────────────────────┤")
        
        # 남은 빈 줄들
        for i in range(len(guesses), max_attempts):
            attempt_num = i + 1
            board_lines.append(f"│ {attempt_num:2d}. {'⬜ ' * 5:<15} │")
            
            if i < max_attempts - 1:
                board_lines.append("├─────────────────────────────────────┤")
        
        board_lines.append("└─────────────────────────────────────┘")
        board_lines.append("```")
        
        return "\n".join(board_lines)
    
    # =============================================================================
    # 게임 모드별 로직 분기
    # =============================================================================
    
    @staticmethod
    def create_game_session(mode: GameMode, answer_word: str, 
                          initial_points: int = 1000, **kwargs) -> Dict[str, Any]:
        """게임 세션 생성"""
        
        base_session = {
            "mode": mode.value,
            "answer_word": answer_word,
            "attempts": [],
            "current_attempt": 0,
            "max_attempts": kwargs.get("max_attempts", 10),
            "is_finished": False,
            "is_won": False,
            "created_at": WordleGame._get_current_timestamp()
        }
        
        if mode == GameMode.CLASSIC:
            # 기존 워들 방식
            base_session.update({
                "bet_amount": initial_points,
                "remaining_points": initial_points,
                "points_per_failure": kwargs.get("points_per_failure", 100)
            })
            
        elif mode == GameMode.HYBRID:
            # 하이브리드 방식
            base_session.update({
                "initial_points": initial_points,
                "remaining_points": initial_points,
                "difficulty": kwargs.get("difficulty", "중급"),
                "similarities": []
            })
            
        return base_session
    
    @staticmethod
    def process_guess(session: Dict[str, Any], guess_word: str, 
                     similarity_score: Optional[float] = None) -> Tuple[str, bool]:
        """추측 처리 (모드별 분기)"""
        
        mode = GameMode(session["mode"])
        answer_word = session["answer_word"]
        
        # 공통 검증
        if session["is_finished"]:
            raise ValueError("이미 종료된 게임입니다.")
        
        # 글자 패턴 생성
        if mode == GameMode.CLASSIC:
            pattern = WordleGame.compare_words(guess_word, answer_word)
        else:
            pattern = WordleGame.compare_words_flexible(guess_word, answer_word)
        
        # 시도 기록 추가
        attempt_data = {
            "guess": guess_word,
            "pattern": pattern,
            "timestamp": WordleGame._get_current_timestamp()
        }
        
        # 유사도 점수 추가 (하이브리드 모드)
        if similarity_score is not None:
            attempt_data["similarity"] = similarity_score
            session.setdefault("similarities", []).append(similarity_score)
        
        session["attempts"].append(attempt_data)
        session["current_attempt"] += 1
        
        # 승리 조건 확인
        is_correct = WordleGame.is_winner(pattern)
        
        if is_correct:
            session["is_finished"] = True
            session["is_won"] = True
        elif session["current_attempt"] >= session["max_attempts"]:
            session["is_finished"] = True
            session["is_won"] = False
        
        # 점수 처리 (모드별)
        if mode == GameMode.CLASSIC and not is_correct:
            session["remaining_points"] = WordleGame.calculate_remaining_points(
                session["bet_amount"], 
                session["current_attempt"], 
                session["points_per_failure"]
            )
        
        return pattern, is_correct
    
    @staticmethod
    def _get_current_timestamp() -> int:
        """현재 타임스탬프 반환"""
        import time
        return int(time.time())
    
    @staticmethod
    def analyze_game_session(session: Dict[str, Any]) -> Dict[str, Any]:
        """게임 세션 분석"""
        if not session["attempts"]:
            return {}
        
        analysis = {
            "total_attempts": len(session["attempts"]),
            "is_completed": session["is_finished"],
            "is_won": session["is_won"],
            "mode": session["mode"]
        }
        
        # 글자 정확도 분석
        patterns = [attempt["pattern"] for attempt in session["attempts"]]
        total_chars = sum(len(pattern) for pattern in patterns)
        correct_chars = sum(pattern.count('1') for pattern in patterns)
        
        analysis["letter_accuracy"] = (correct_chars / total_chars * 100) if total_chars > 0 else 0
        
        # 유사도 분석 (하이브리드 모드)
        if "similarities" in session and session["similarities"]:
            similarities = session["similarities"]
            analysis.update({
                "max_similarity": max(similarities),
                "min_similarity": min(similarities),
                "avg_similarity": sum(similarities) / len(similarities),
                "similarity_trend": WordleGame._analyze_similarity_trend(similarities)
            })
        
        return analysis
    
    @staticmethod
    def _analyze_similarity_trend(similarities: List[float]) -> str:
        """유사도 변화 추세 분석"""
        if len(similarities) < 2:
            return "insufficient_data"
        
        # 마지막 3개 시도의 평균과 처음 3개 시도의 평균 비교
        recent_avg = sum(similarities[-3:]) / len(similarities[-3:])
        early_avg = sum(similarities[:3]) / len(similarities[:3])
        
        if recent_avg > early_avg + 10:
            return "improving"  # 개선 중
        elif recent_avg < early_avg - 10:
            return "declining"  # 악화 중
        else:
            return "stable"     # 안정적

def test_wordle_logic():
    """워들 로직 테스트 (기존 함수 유지)"""
    print("=== 워들 로직 테스트 ===")
    
    # 기존 테스트 케이스들
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