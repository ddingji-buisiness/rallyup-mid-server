import discord
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from utils.wordle_logic import WordleGame as WordleLogic

class WordleUI:
    """워들 게임 UI 헬퍼 클래스"""
    
    # 색상 테마
    COLORS = {
        'primary': 0x0099ff,      # 파란색 (기본)
        'success': 0x00ff88,      # 초록색 (성공)
        'warning': 0xffa500,      # 주황색 (경고)
        'danger': 0xff6b6b,       # 빨간색 (위험)
        'info': 0x95a5a6,         # 회색 (정보)
        'gold': 0xffd700,         # 금색 (보상)
        'purple': 0x9b59b6        # 보라색 (특별)
    }
    
    # 이모지 세트
    EMOJIS = {
        'wordle': '🎯',
        'points': '💰',
        'hint': '💡',
        'time': '⏰',
        'creator': '👨‍💻',
        'player': '🎮',
        'winner': '🏆',
        'fire': '🔥',
        'star': '⭐',
        'gem': '💎',
        'trophy': '🏆',
        'thinking': '🤔',
        'celebration': '🎉',
        'sad': '😢',
        'muscle': '💪',
        'brain': '🧠',
        'target': '🎯',
        'gift': '🎁',
        'chart': '📊',
        'rank': '🏅',
        'crown': '👑'
    }
    
    @staticmethod
    def create_game_board(guesses: List[Dict], max_display: int = 6) -> str:
        """시각적으로 개선된 게임 보드 생성"""
        board_lines = []
        
        # 헤더
        board_lines.append("```")
        board_lines.append("┌─────────────────────────┐")
        board_lines.append("│     🎯 띵지워들 보드      │")
        board_lines.append("├─────────────────────────┤")
        
        # 추측 기록들
        for i, guess_data in enumerate(guesses[:max_display]):
            pattern = guess_data['result_pattern']
            guess_word = guess_data['guess_word']
            
            # 각 글자를 이모지로 변환
            emoji_chars = []
            for j, char in enumerate(guess_word):
                result = int(pattern[j])
                if result == WordleLogic.CORRECT:
                    emoji_chars.append(f"🟩")
                elif result == WordleLogic.WRONG_POSITION:
                    emoji_chars.append(f"🟨")
                else:
                    emoji_chars.append(f"⬜")
            
            emoji_line = " ".join(emoji_chars)
            word_line = " ".join(list(guess_word))
            
            board_lines.append(f"│ {i+1:2d}. {word_line}     │")
            board_lines.append(f"│     {emoji_line}    │")
            
            if i < len(guesses) - 1:
                board_lines.append("├─────────────────────────┤")
        
        # 빈 줄들 (남은 시도 횟수 표시)
        remaining_attempts = max_display - len(guesses)
        for i in range(remaining_attempts):
            attempt_num = len(guesses) + i + 1
            board_lines.append(f"│ {attempt_num:2d}. ⬜ ⬜ ⬜ ⬜ ⬜     │")
            if i < remaining_attempts - 1:
                board_lines.append("├─────────────────────────┤")
        
        board_lines.append("└─────────────────────────┘")
        board_lines.append("```")
        
        return "\n".join(board_lines)
    
    @staticmethod
    def create_progress_bar(current: int, maximum: int, length: int = 10) -> str:
        """진행률 바 생성"""
        if maximum == 0:
            return "▱" * length
        
        filled = int((current / maximum) * length)
        return "▰" * filled + "▱" * (length - filled)
    
    @staticmethod
    def format_points(points: int) -> str:
        """포인트를 보기 좋게 포맷팅"""
        if points >= 1000000:
            return f"{points//1000000:.1f}M"
        elif points >= 1000:
            return f"{points//1000:.1f}K"
        else:
            return str(points)
    
    @staticmethod
    def get_difficulty_emoji(rating: str) -> str:
        """난이도 이모지 반환"""
        difficulty_map = {
            "쉬움": "😅",
            "적절함": "👍", 
            "어려움": "😰"
        }
        return difficulty_map.get(rating, "❓")
    
    @staticmethod
    def get_rank_emoji(rank: int) -> str:
        """순위 이모지 반환"""
        if rank == 1:
            return "🥇"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        elif rank <= 10:
            return "🏅"
        else:
            return "📍"
    
    @staticmethod
    def create_game_info_embed(game: Dict, attempt: Optional[Dict] = None) -> discord.Embed:
        """게임 정보 임베드 생성"""
        embed = discord.Embed(
            title=f"🎯 띵지워들 게임 #{game['id']}",
            color=WordleUI.COLORS['primary'],
            timestamp=datetime.now()
        )
        
        # 썸네일 추가
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1234567890123456789.png")  # 워들 관련 이미지
        
        # 출제자 정보
        embed.add_field(
            name=f"{WordleUI.EMOJIS['creator']} 출제자",
            value=f"**{game['creator_username']}**",
            inline=True
        )
        
        # 힌트 정보
        hint_text = game['hint'] if game['hint'] else "없음"
        embed.add_field(
            name=f"{WordleUI.EMOJIS['hint']} 힌트",
            value=f"*{hint_text}*",
            inline=True
        )
        
        # 포인트 풀
        embed.add_field(
            name=f"{WordleUI.EMOJIS['gem']} 포인트 풀",
            value=f"**{game['total_pool']:,}**점",
            inline=True
        )
        
        # 게임 시간 정보
        created_time = datetime.fromisoformat(game['created_at'])
        expires_time = datetime.fromisoformat(game['expires_at'])
        
        embed.add_field(
            name=f"{WordleUI.EMOJIS['time']} 게임 정보",
            value=f"**등록**: <t:{int(created_time.timestamp())}:R>\n"
                  f"**만료**: <t:{int(expires_time.timestamp())}:R>",
            inline=False
        )
        
        # 참여자 정보 (있다면)
        if attempt:
            progress_bar = WordleUI.create_progress_bar(
                attempt['bet_amount'] - attempt['remaining_points'], 
                attempt['bet_amount']
            )
            
            embed.add_field(
                name=f"{WordleUI.EMOJIS['player']} 내 도전 현황",
                value=f"**베팅**: {attempt['bet_amount']:,}점\n"
                      f"**남은 포인트**: {attempt['remaining_points']:,}점\n"
                      f"**시도**: {attempt['attempts_used']}회\n"
                      f"**진행률**: {progress_bar}",
                inline=False
            )
        
        embed.set_footer(
            text="🎯 띵지워들 • 한글 단어 맞추기 게임",
            icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png"
        )
        
        return embed
    
    @staticmethod
    def create_game_list_embed(games: List[Dict], title: str = "🎯 띵지워들 게임 목록") -> discord.Embed:
        """게임 목록 임베드 생성"""
        embed = discord.Embed(
            title=title,
            color=WordleUI.COLORS['primary'],
            timestamp=datetime.now()
        )
        
        if not games:
            embed.description = "현재 활성 상태인 게임이 없습니다.\n`/띵지워들 등록`으로 새 게임을 만들어보세요!"
            embed.color = WordleUI.COLORS['info']
            return embed
        
        embed.description = f"현재 **{len(games)}개**의 게임이 진행 중입니다!"
        
        for i, game in enumerate(games[:6]):  # 최대 6개까지 표시
            created_time = datetime.fromisoformat(game['created_at'])
            expires_time = datetime.fromisoformat(game['expires_at'])
            
            # 시간 남은 정도에 따른 이모지
            time_left = expires_time - datetime.now()
            if time_left.total_seconds() < 3600:  # 1시간 미만
                time_emoji = "⚠️"
            elif time_left.total_seconds() < 6 * 3600:  # 6시간 미만
                time_emoji = "⏳"
            else:
                time_emoji = "⏰"
            
            embed.add_field(
                name=f"🎮 #{game['id']} - {game['creator_username']}",
                value=f"{WordleUI.EMOJIS['hint']} **힌트**: {game['hint'][:30] + '...' if game['hint'] and len(game['hint']) > 30 else game['hint'] or '없음'}\n"
                      f"{WordleUI.EMOJIS['points']} **베팅**: {game['bet_points']:,}점\n"
                      f"{WordleUI.EMOJIS['gem']} **풀**: {game['total_pool']:,}점\n"
                      f"{time_emoji} **만료**: <t:{int(expires_time.timestamp())}:R>",
                inline=True
            )
        
        if len(games) > 6:
            embed.add_field(
                name="📋 더 많은 게임",
                value=f"총 {len(games)}개 게임 중 6개만 표시됩니다.\n"
                      "`/띵지워들 도전`에서 전체 목록을 확인하세요!",
                inline=False
            )
        
        return embed
    
    @staticmethod
    def create_stats_embed(user_stats: Dict, username: str, rank_info: Optional[Dict] = None) -> discord.Embed:
        """통계 임베드 생성"""
        embed = discord.Embed(
            title=f"{WordleUI.EMOJIS['chart']} {username}님의 띵지워들 통계",
            color=WordleUI.COLORS['purple'],
            timestamp=datetime.now()
        )
        
        # 포인트 정보
        embed.add_field(
            name=f"{WordleUI.EMOJIS['points']} 포인트",
            value=f"**{user_stats['points']:,}**점",
            inline=True
        )
        
        # 순위 정보 (있다면)
        if rank_info:
            rank_emoji = WordleUI.get_rank_emoji(rank_info['rank'])
            embed.add_field(
                name=f"{WordleUI.EMOJIS['rank']} 순위",
                value=f"{rank_emoji} **#{rank_info['rank']}**위",
                inline=True
            )
        
        # 승률
        embed.add_field(
            name=f"{WordleUI.EMOJIS['trophy']} 승률",
            value=f"**{user_stats['win_rate']:.1f}%**",
            inline=True
        )
        
        # 출제자 통계
        creator_success_rate = 0
        if user_stats['games_created'] > 0:
            creator_success_rate = (user_stats['games_solved'] / user_stats['games_created']) * 100
        
        embed.add_field(
            name=f"{WordleUI.EMOJIS['brain']} 출제자 활동",
            value=f"**등록**: {user_stats['games_created']}게임\n"
                  f"**해결**: {user_stats['games_solved']}게임\n"
                  f"**성공률**: {creator_success_rate:.1f}%",
            inline=True
        )
        
        # 도전자 통계
        embed.add_field(
            name=f"{WordleUI.EMOJIS['target']} 도전자 활동",
            value=f"**도전**: {user_stats['games_attempted']}게임\n"
                  f"**승리**: {user_stats['games_won']}게임\n"
                  f"**평균 시도**: {user_stats['avg_attempts']:.1f}회",
            inline=True
        )
        
        # 진행률 바
        if user_stats['games_attempted'] > 0:
            win_progress = WordleUI.create_progress_bar(
                user_stats['games_won'], 
                user_stats['games_attempted']
            )
            embed.add_field(
                name=f"{WordleUI.EMOJIS['muscle']} 승리 진행률",
                value=f"`{win_progress}` {user_stats['win_rate']:.1f}%",
                inline=False
            )
        
        embed.set_footer(text="🎯 띵지워들 통계")
        
        return embed
    
    @staticmethod
    def create_ranking_embed(rankings: List[Dict], title: str = "🏆 띵지워들 명예의 전당") -> discord.Embed:
        """랭킹 임베드 생성"""
        embed = discord.Embed(
            title=title,
            color=WordleUI.COLORS['gold'],
            timestamp=datetime.now()
        )
        
        if not rankings:
            embed.description = "아직 랭킹 데이터가 없습니다."
            embed.color = WordleUI.COLORS['info']
            return embed
        
        # 통합된 랭킹 표시 (최대 15명)
        ranking_text = ""
        for i, player in enumerate(rankings[:15]):
            rank_emoji = WordleUI.get_rank_emoji(i + 1)
            points_formatted = WordleUI.format_points(player['points'])
            ranking_text += f"{rank_emoji} **{player['username']}** - {points_formatted}점\n"
        
        if ranking_text:
            embed.add_field(
                name=f"{WordleUI.EMOJIS['crown']} 서버 랭킹",
                value=ranking_text.strip(),
                inline=False
            )
        
        embed.set_footer(text=f"총 {len(rankings)}명의 플레이어 • 🎯 띵지워들")
        
        return embed
    
    @staticmethod
    def create_help_embed() -> discord.Embed:
        """도움말 임베드 생성"""
        embed = discord.Embed(
            title="🎯 띵지워들 게임 가이드",
            description="한글 5글자 단어 맞추기 게임에 오신 것을 환영합니다!",
            color=WordleUI.COLORS['info'],
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🎮 게임 방법",
            value="1️⃣ 출제자가 5글자 한글 단어를 등록\n"
                  "2️⃣ 도전자가 포인트를 걸고 게임 참여\n"
                  "3️⃣ 5글자 단어를 추측하여 힌트 확인\n"
                  "4️⃣ 정답을 맞추면 전체 포인트 획득!",
            inline=False
        )
        
        embed.add_field(
            name="🎨 힌트 이해하기",
            value="🟩 **초록색**: 정확한 위치의 올바른 글자\n"
                  "🟨 **노란색**: 다른 위치의 올바른 글자\n"
                  "⬜ **회색**: 단어에 없는 글자",
            inline=False
        )
        
        embed.add_field(
            name="💰 포인트 시스템",
            value="• **일일 보너스**: 매일 1,000점 무료 지급\n"
                  "• **베팅 시스템**: 실패할 때마다 베팅액의 10% 차감\n"
                  "• **승리 보상**: 전체 포인트 풀 획득\n"
                  "• **출제자 보상**: 난이도 평가에 따라 50-200점",
            inline=False
        )
        
        embed.add_field(
            name="📋 주요 명령어",
            value="`/띵지워들 등록` - 새 게임 등록\n"
                  "`/띵지워들 도전` - 게임에 도전\n"
                  "`/띵지워들 포인트` - 포인트 확인\n"
                  "`/띵지워들 목록` - 활성 게임 목록\n"
                  "`/띵지워들 삭제` - 본인 게임 삭제",
            inline=False
        )
        
        embed.set_footer(text="🎯 띵지워들 • 즐거운 한글 게임!")
        
        return embed