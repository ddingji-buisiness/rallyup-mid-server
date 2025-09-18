import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import asyncio

from database.models import WordleGame, WordleAttempt, WordleGuess, WordleRating
from utils.wordle_logic import WordleGame as WordleLogic
from utils.wordle_ui import WordleUI

class WordleGameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}
    
    @app_commands.command(name="띵지워들", description="띵지워들 게임 시스템")
    @app_commands.describe(
        행동="수행할 행동을 선택하세요",
        단어="등록할 5글자 한글 단어 (행동이 '등록'인 경우)",
        힌트="단어에 대한 힌트 (행동이 '등록'인 경우, 선택사항)",
        베팅포인트="베팅할 포인트 (100-5000, 행동이 '등록'인 경우)"
    )
    @app_commands.choices(행동=[
        app_commands.Choice(name="🎮 등록", value="등록"),
        app_commands.Choice(name="⚔️ 도전", value="도전"),
        app_commands.Choice(name="🗑️ 삭제", value="삭제"),
        app_commands.Choice(name="💰 포인트", value="포인트"),
        app_commands.Choice(name="🏆 랭킹", value="랭킹"),
        app_commands.Choice(name="📊 통계", value="통계"),
        app_commands.Choice(name="❓ 도움말", value="도움말")
    ])
    async def 띵지워들(
        self, 
        interaction: discord.Interaction, 
        행동: app_commands.Choice[str],
        단어: str = None,
        힌트: str = None,
        베팅포인트: int = None
    ):
        """띵지워들 메인 명령어"""
        action = 행동.value
        
        if action == "등록":
            await self._handle_register(interaction, 단어, 힌트, 베팅포인트)
        elif action == "도전":
            await self._handle_challenge(interaction)
        elif action == "삭제":
            await self._handle_delete(interaction)
        elif action == "포인트":
            await self._handle_points(interaction)
        elif action == "랭킹":
            await self._handle_ranking(interaction)
        elif action == "통계":
            await self._handle_stats(interaction)
        elif action == "도움말":
            await self._handle_help(interaction)
    
    async def _handle_register(self, interaction: discord.Interaction, 단어: str, 힌트: str, 베팅포인트: int):
        """게임 등록 처리"""
        user_id = str(interaction.user.id)
        username = interaction.user.display_name
        guild_id = str(interaction.guild_id)

        # 🔒 등록된 사용자인지 먼저 확인
        is_registered = await self.bot.db_manager.is_user_registered(guild_id, user_id)
        if not is_registered:
            await interaction.response.send_message(
                "❌ 등록된 사용자만 띵지워들 게임을 이용할 수 있습니다.\n"
                "서버 관리자에게 사용자 등록을 요청해주세요.",
                ephemeral=True
            )
            return
        
        # 입력 검증
        if not 단어:
            await interaction.response.send_message(
                "❌ 등록할 단어를 입력해주세요.\n"
                "사용법: `/띵지워들 등록 [5글자 한글단어] [힌트] [베팅포인트]`",
                ephemeral=True
            )
            return
        
        if not WordleLogic.validate_korean_word(단어):
            await interaction.response.send_message(
                "❌ 올바른 5글자 한글 단어를 입력해주세요.\n"
                f"입력된 단어: `{단어}` (길이: {len(단어)}글자)",
                ephemeral=True
            )
            return
        
        if 베팅포인트 is None or 베팅포인트 < 100 or 베팅포인트 > 5000:
            await interaction.response.send_message(
                "❌ 베팅 포인트는 100~5000 사이로 입력해주세요.",
                ephemeral=True
            )
            return
        
        # 사용자 포인트 확인
        user_points = await self.bot.db_manager.get_user_points(guild_id, user_id)
        if user_points is None:
            await interaction.response.send_message(
                "❌ 등록된 사용자 정보를 찾을 수 없습니다.",
                ephemeral=True
            )
            return
        
        if user_points < 베팅포인트:
            await interaction.response.send_message(
                f"❌ 포인트가 부족합니다.\n"
                f"현재 포인트: {user_points:,}점\n"
                f"필요 포인트: {베팅포인트:,}점",
                ephemeral=True
            )
            return
        
        # 일일 포인트 지급 체크
        daily_claimed = await self.bot.db_manager.claim_daily_points(user_id, username)

        # 게임 생성
        expires_at = datetime.now() + timedelta(hours=24)
        game = WordleGame(
            guild_id=guild_id,
            word=단어,
            hint=힌트,
            creator_id=user_id,
            creator_username=username,
            bet_points=베팅포인트,
            expires_at=expires_at
        )

        game_id = await self.bot.db_manager.create_game(game)
        if not game_id:
            await interaction.response.send_message(
                "❌ 게임 등록 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                ephemeral=True
            )
            return
        
        # 포인트 차감
        await self.bot.db_manager.add_user_points(guild_id, user_id, -베팅포인트)

        # 성공 메시지 - 새로운 UI 적용
        embed = discord.Embed(
            title="🎉 띵지워들 게임 등록 완료!",
            description=f"**게임 #{game_id}**가 성공적으로 등록되었습니다!",
            color=WordleUI.COLORS['success'],
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name=f"{WordleUI.EMOJIS['creator']} 출제자 정보",
            value=f"**이름**: {username}\n"
                  f"**단어**: `5글자 한글 단어 등록 완료`\n"
                  f"**힌트**: {힌트 or '없음'}",
            inline=True
        )
        
        embed.add_field(
            name=f"{WordleUI.EMOJIS['points']} 베팅 정보",
            value=f"**베팅 포인트**: {베팅포인트:,}점\n"
                  f"**현재 풀**: {베팅포인트:,}점\n"
                  f"**남은 포인트**: {user_points - 베팅포인트:,}점",
            inline=True
        )
        
        embed.add_field(
            name=f"{WordleUI.EMOJIS['time']} 게임 일정",
            value=f"**만료 시간**: <t:{int(expires_at.timestamp())}:R>\n"
                  f"**만료 일시**: <t:{int(expires_at.timestamp())}:F>",
            inline=False
        )
        
        if daily_claimed:
            embed.add_field(
                name=f"{WordleUI.EMOJIS['gift']} 일일 보너스",
                value="🎁 오늘의 무료 포인트 1,000점을 받았습니다!",
                inline=False
            )
        
        embed.add_field(
            name=f"{WordleUI.EMOJIS['target']} 다음 단계",
            value="다른 사용자들이 `/띵지워들 도전`으로 게임에 참여할 수 있습니다!\n"
                  "24시간 내에 아무도 정답을 맞추지 못하면 전체 포인트를 획득합니다.",
            inline=False
        )
        
        embed.set_footer(text="🎯 띵지워들 • 새로운 도전이 시작되었습니다!")
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_challenge(self, interaction: discord.Interaction):
        """게임 도전 처리"""
        guild_id = str(interaction.guild_id)
        
        # 활성 게임 목록 조회
        active_games = await self.bot.db_manager.get_active_games(guild_id)

        if not active_games:
            await interaction.response.send_message(
                "🤷‍♂️ 현재 도전할 수 있는 게임이 없습니다.\n"
                "`/띵지워들 등록`으로 새 게임을 만들어보세요!",
                ephemeral=True
            )
            return
        
        # 게임 선택 드롭다운 생성 - 개선된 UI
        view = GameSelectionView(active_games, self.bot)

        embed = WordleUI.create_game_list_embed(active_games, "⚔️ 도전할 게임을 선택하세요!")
        embed.description = f"현재 **{len(active_games)}개**의 게임이 여러분의 도전을 기다리고 있습니다!\n"
        embed.description += "아래에서 도전하고 싶은 게임을 선택해주세요."
        
        if len(active_games) > 25:
            embed.add_field(
                name="ℹ️ 안내",
                value=f"드롭다운에는 최신 25개 게임만 표시됩니다.\n"
                      f"(총 {len(active_games)}개 게임 중)",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _handle_delete(self, interaction: discord.Interaction):
        """게임 삭제 처리"""
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        
        # 사용자의 활성 게임 조회
        active_games = await self.bot.db_manager.get_active_games(guild_id)
        user_games = [game for game in active_games if game['creator_id'] == user_id]
        
        if not user_games:
            await interaction.response.send_message(
                "❌ 삭제할 수 있는 게임이 없습니다.\n"
                "본인이 등록한 활성 게임만 삭제할 수 있습니다.",
                ephemeral=True
            )
            return
        
        # 게임 삭제 드롭다운 생성
        view = GameDeleteView(user_games, self.bot)
        
        embed = discord.Embed(
            title="🗑️ 게임 삭제",
            description="삭제할 게임을 선택해주세요. 베팅한 포인트가 반환됩니다.",
            color=0xff6b6b
        )
        
        for game in user_games:
            created_time = datetime.fromisoformat(game['created_at'])
            embed.add_field(
                name=f"🎮 게임 #{game['id']}",
                value=f"**힌트**: {game['hint'] or '없음'}\n"
                      f"**베팅 포인트**: {game['bet_points']:,}점\n"
                      f"**등록 시간**: <t:{int(created_time.timestamp())}:R>",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _handle_points(self, interaction: discord.Interaction):
        """포인트 확인 처리"""
        user_id = str(interaction.user.id)
        username = interaction.user.display_name
        guild_id = str(interaction.guild_id)
        
        # 일일 포인트 지급 체크
        daily_claimed = await self.bot.db_manager.claim_daily_points(user_id, username)
        
        # 포인트 조회
        points = await self.bot.db_manager.get_user_points(guild_id, user_id)

        embed = discord.Embed(
            title="💰 포인트 현황",
            color=0x00ff88,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🎯 현재 포인트",
            value=f"**{points:,}점**",
            inline=False
        )
        
        if daily_claimed:
            embed.add_field(
                name="🎁 일일 보너스 지급!",
                value="오늘의 무료 포인트 1,000점을 받았습니다!",
                inline=False
            )
        else:
            embed.add_field(
                name="ℹ️ 일일 보너스",
                value="오늘은 이미 일일 포인트를 받으셨습니다.\n내일 다시 받을 수 있어요!",
                inline=False
            )
        
        embed.add_field(
            name="📋 포인트 사용법",
            value="• 게임 등록: 100~5,000점 베팅\n"
                  "• 게임 도전: 자유롭게 베팅\n"
                  "• 매일 1,000점 무료 지급",
            inline=False
        )
        
        embed.set_footer(text=f"{username}님의 포인트 현황")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _handle_list(self, interaction: discord.Interaction):
        """게임 목록 확인 처리 - 개선된 UI"""
        guild_id = str(interaction.guild_id)

        active_games = await self.bot.db_manager.get_active_games(guild_id)
        embed = WordleUI.create_game_list_embed(active_games)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _handle_ranking(self, interaction: discord.Interaction):
        """랭킹 확인 처리"""
        top_players = await self.bot.db_manager.get_top_players(30)
        embed = WordleUI.create_ranking_embed(top_players)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _handle_stats(self, interaction: discord.Interaction):
        """개인 통계 확인 처리"""
        user_id = str(interaction.user.id)
        username = interaction.user.display_name
        guild_id = str(interaction.guild_id)

        # 일일 포인트 지급 체크
        await self.bot.db_manager.claim_daily_points(user_id, username)

        # 통계 조회
        user_stats = await self.bot.db_manager.get_user_stats(guild_id, user_id)

        # 랭킹 정보도 함께 조회
        top_players = await self.bot.db_manager.get_top_players(100)
        user_rank = None
        for i, player in enumerate(top_players):
            if player['user_id'] == user_id:
                user_rank = {'rank': i + 1}
                break
        
        embed = WordleUI.create_stats_embed(user_stats, username, user_rank)
        
        # 추가 버튼들
        view = StatsView(user_id, self.bot)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _handle_help(self, interaction: discord.Interaction):
        """도움말 표시"""
        embed = WordleUI.create_help_embed()
        
        # 도움말 버튼들 추가
        view = HelpView(self.bot)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ===========================================
# 새로운 UI 컴포넌트들
# ===========================================

class StatsView(discord.ui.View):
    def __init__(self, user_id: str, bot):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bot = bot

    @discord.ui.button(label="🎁 일일 포인트", style=discord.ButtonStyle.green, emoji="🎁")
    async def daily_points(self, interaction: discord.Interaction, button: discord.ui.Button):
        username = interaction.user.display_name
        claimed = await self.bot.db_manager.claim_daily_points(self.user_id, username)

        if claimed:
            embed = discord.Embed(
                title="🎁 일일 포인트 지급!",
                description="1,000점을 받았습니다!",
                color=WordleUI.COLORS['success']
            )
        else:
            embed = discord.Embed(
                title="ℹ️ 이미 받으셨습니다",
                description="오늘은 이미 일일 포인트를 받으셨습니다.\n내일 다시 받을 수 있어요!",
                color=WordleUI.COLORS['info']
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🔄 새로고침", style=discord.ButtonStyle.secondary)
    async def refresh_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild_id)

        # 통계 다시 조회
        user_stats = await self.bot.db_manager.get_user_stats(guild_id, self.user_id)
        username = interaction.user.display_name

        top_players = await self.bot.db_manager.get_top_players(100)
        user_rank = None
        for i, player in enumerate(top_players):
            if player['user_id'] == self.user_id:
                user_rank = {'rank': i + 1}
                break
        
        embed = WordleUI.create_stats_embed(user_stats, username, user_rank)
        
        await interaction.response.edit_message(embed=embed, view=self)

class HelpView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label="🎮 게임 시작하기", style=discord.ButtonStyle.primary)
    async def start_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎮 게임 시작 가이드",
            description="띵지워들을 시작하는 방법을 안내드립니다!",
            color=WordleUI.COLORS['primary']
        )
        
        embed.add_field(
            name="1️⃣ 게임 등록하기",
            value="`/띵지워들 등록 [단어] [힌트] [포인트]`\n"
                  "예시: `/띵지워들 등록 사과나무 \"빨간 과일\" 1000`",
            inline=False
        )
        
        embed.add_field(
            name="2️⃣ 게임 도전하기",
            value="`/띵지워들 도전`\n"
                  "활성 게임 목록에서 선택하여 도전하세요!",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="🏆 랭킹 보기", style=discord.ButtonStyle.success)
    async def show_ranking(self, interaction: discord.Interaction, button: discord.ui.Button):
        top_players = await self.bot.db_manager.get_top_players(30)
        embed = WordleUI.create_ranking_embed(top_players)
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="💡 팁과 전략", style=discord.ButtonStyle.secondary)
    async def show_tips(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💡 띵지워들 팁과 전략",
            color=WordleUI.COLORS['info']
        )
        
        embed.add_field(
            name="🎯 출제자 팁",
            value="• 너무 쉽거나 어려운 단어는 피하세요\n"
                  "• 힌트는 간단하고 명확하게 작성하세요\n"
                  "• 일반적인 5글자 한글 단어를 사용하세요\n"
                  "• 적절한 난이도로 평가받으면 200점 보상!",
            inline=False
        )
        
        embed.add_field(
            name="⚔️ 도전자 팁",
            value="• 첫 추측은 자음과 모음이 다양한 단어로\n"
                  "• 🟨 노란색 힌트를 활용해 위치를 좁혀가세요\n"
                  "• 포인트 관리에 신경쓰세요 (10%씩 차감)\n"
                  "• 힌트를 꼼꼼히 읽어보세요",
            inline=False
        )
        
        embed.add_field(
            name="💰 포인트 관리 팁",
            value="• 매일 일일 포인트 1,000점을 받으세요\n"
                  "• 베팅은 신중하게 (100-5000점)\n"
                  "• 초보자는 작은 금액부터 시작하세요\n"
                  "• 정답을 맞추면 전체 풀을 획득합니다!",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

class GamePlayView(discord.ui.View):
    def __init__(self, game_id: int, attempt_id: int, bot):
        super().__init__(timeout=600)  # 10분 타임아웃
        self.game_id = game_id
        self.attempt_id = attempt_id
        self.bot = bot

    async def show_game_status(self, interaction: discord.Interaction):
        """현재 게임 상태 표시 - 개선된 UI"""
        # 게임 정보 조회
        game = await self.bot.db_manager.get_game_by_id(self.game_id)
        attempt = await self.bot.db_manager.get_user_attempt(self.game_id, str(interaction.user.id))
        guesses = await self.bot.db_manager.get_attempt_guesses(self.attempt_id)

        if not game or not attempt:
            await interaction.response.send_message("❌ 게임 정보를 찾을 수 없습니다.", ephemeral=True)
            return
        
        # 기본 게임 정보 임베드
        embed = WordleUI.create_game_info_embed(game, attempt)
        embed.title = f"🎯 진행 중인 게임 #{self.game_id}"
        
        # 게임 보드 추가
        if guesses:
            game_board = WordleUI.create_game_board(guesses)
            embed.add_field(
                name="🎮 게임 보드",
                value=game_board,
                inline=False
            )
            
            # 최근 추측 결과 하이라이트
            last_guess = guesses[-1]
            last_pattern = last_guess['result_pattern']
            last_word = last_guess['guess_word']
            
            if WordleLogic.is_winner(last_pattern):
                embed.add_field(
                    name="🎉 정답입니다!",
                    value=f"축하합니다! **{last_word}**가 정답입니다!",
                    inline=False
                )
            else:
                # 힌트 분석 제공
                correct_count = last_pattern.count('1')
                wrong_pos_count = last_pattern.count('2')
                
                hint_text = f"🔍 **{last_word}** 분석 결과:\n"
                if correct_count > 0:
                    hint_text += f"🟩 정확한 위치: {correct_count}개\n"
                if wrong_pos_count > 0:
                    hint_text += f"🟨 다른 위치: {wrong_pos_count}개\n"
                if correct_count == 0 and wrong_pos_count == 0:
                    hint_text += "⬜ 일치하는 글자가 없습니다"
                
                embed.add_field(
                    name="💭 최근 추측 분석",
                    value=hint_text,
                    inline=False
                )
        else:
            embed.add_field(
                name="🎮 게임 보드",
                value="```\n┌─────────────────────────┐\n"
                      "│     🎯 띵지워들 보드      │\n"
                      "├─────────────────────────┤\n"
                      "│  1. ⬜ ⬜ ⬜ ⬜ ⬜     │\n"
                      "│  2. ⬜ ⬜ ⬜ ⬜ ⬜     │\n"
                      "│  3. ⬜ ⬜ ⬜ ⬜ ⬜     │\n"
                      "│  4. ⬜ ⬜ ⬜ ⬜ ⬜     │\n"
                      "│  5. ⬜ ⬜ ⬜ ⬜ ⬜     │\n"
                      "│  6. ⬜ ⬜ ⬜ ⬜ ⬜     │\n"
                      "└─────────────────────────┘\n```",
                inline=False
            )
        
        # 게임 상태에 따른 버튼 및 메시지
        if not attempt['is_completed']:
            can_continue = WordleLogic.can_continue_game(
                attempt['remaining_points'], 
                attempt['points_per_failure']
            )
            
            if can_continue:
                embed.add_field(
                    name=f"{WordleUI.EMOJIS['fire']} 다음 도전",
                    value=f"아래 버튼을 눌러 단어를 추측해보세요!\n"
                          f"💸 실패시 **{attempt['points_per_failure']}점** 차감\n"
                          f"🏆 성공시 **{game['total_pool']:,}점** 전체 획득",
                    inline=False
                )
                
                # 진행률 바 추가
                progress = WordleUI.create_progress_bar(
                    attempt['bet_amount'] - attempt['remaining_points'],
                    attempt['bet_amount']
                )
                embed.add_field(
                    name="📊 포인트 사용 현황",
                    value=f"`{progress}` {((attempt['bet_amount'] - attempt['remaining_points']) / attempt['bet_amount'] * 100):.1f}%",
                    inline=False
                )
            else:
                # 포인트 부족으로 게임 종료
                await self._end_game_points_exhausted(interaction.user.id)
                embed.color = WordleUI.COLORS['danger']
                embed.add_field(
                    name="💸 게임 종료",
                    value="포인트가 부족하여 게임이 자동으로 종료되었습니다.\n"
                          "다음에는 더 신중하게 도전해보세요!",
                    inline=False
                )
        else:
            # 이미 완료된 게임
            if attempt['is_winner']:
                embed.color = WordleUI.COLORS['success']
                embed.add_field(
                    name="🎉 게임 완료 - 승리!",
                    value=f"축하합니다! 정답을 맞추셨습니다!\n"
                          f"🏆 획득한 포인트: **{game['total_pool']:,}점**",
                    inline=False
                )
            else:
                embed.color = WordleUI.COLORS['danger']
                embed.add_field(
                    name="😢 게임 완료 - 패배",
                    value="아쉽게도 정답을 맞추지 못했습니다.\n"
                          "다음 기회에 더 좋은 결과를 얻으시길!",
                    inline=False
                )
        
        # 버튼 추가
        if not attempt['is_completed'] and WordleLogic.can_continue_game(attempt['remaining_points'], attempt['points_per_failure']):
            self.clear_items()
            self.add_item(EnhancedGuessButton())
            self.add_item(EnhancedGiveUpButton())
        else:
            self.clear_items()
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _end_game_points_exhausted(self, user_id: str):
        """포인트 부족으로 게임 종료"""
        await self.bot.db_manager.complete_attempt(self.attempt_id, is_winner=False)
        
        # 게임 풀에 추가할 포인트가 있다면 추가
        attempt = await self.bot.db_manager.get_user_attempt(self.game_id, user_id)
        if attempt and attempt['remaining_points'] > 0:
            failed_points = attempt['bet_amount'] - attempt['remaining_points']
            await self.bot.db_manager.add_to_pool(self.game_id, failed_points)

class EnhancedGuessButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="단어 추측하기", 
            style=discord.ButtonStyle.primary, 
            emoji="🎯",
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        modal = EnhancedGuessModal(self.view.game_id, self.view.attempt_id, self.view.bot)
        await interaction.response.send_modal(modal)

class EnhancedGiveUpButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="게임 포기", 
            style=discord.ButtonStyle.danger, 
            emoji="🏳️",
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        # 포기 확인 임베드
        embed = discord.Embed(
            title="🏳️ 게임 포기 확인",
            description="정말로 이 게임을 포기하시겠습니까?",
            color=WordleUI.COLORS['warning']
        )
        
        embed.add_field(
            name="⚠️ 포기 시 결과",
            value="• 남은 포인트가 게임 풀에 추가됩니다\n"
                  "• 다른 도전자들이 더 큰 보상을 받을 수 있습니다\n"
                  "• 이 결정은 되돌릴 수 없습니다",
            inline=False
        )
        
        view = EnhancedGiveUpConfirmView(self.view.game_id, self.view.attempt_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class EnhancedGiveUpConfirmView(discord.ui.View):
    def __init__(self, game_id: int, attempt_id: int):
        super().__init__(timeout=60)
        self.game_id = game_id
        self.attempt_id = attempt_id
    
    @discord.ui.button(label="네, 포기합니다", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_give_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        
        # 도전 완료 처리
        await self.bot.db_manager.complete_attempt(self.attempt_id, is_winner=False)

        # 남은 포인트를 게임 풀에 추가
        attempt = await self.bot.db_manager.get_user_attempt(self.game_id, user_id)
        if attempt:
            failed_points = attempt['bet_amount'] - attempt['remaining_points']
            await self.bot.db_manager.add_to_pool(self.game_id, failed_points)

        embed = discord.Embed(
            title="🏳️ 게임 포기 완료",
            description="게임을 포기하였습니다.",
            color=WordleUI.COLORS['info']
        )
        
        embed.add_field(
            name="💰 포인트 처리",
            value=f"사용된 포인트: {failed_points:,}점\n"
                  f"게임 풀에 추가되었습니다.",
            inline=False
        )
        
        embed.add_field(
            name="🎯 다음 도전",
            value="`/띵지워들 도전`으로 다른 게임에 도전해보세요!",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="아니요, 계속합니다", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_give_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💪 도전 계속!",
            description="포기를 취소했습니다. 계속 도전해보세요!",
            color=WordleUI.COLORS['success']
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

class EnhancedGuessModal(discord.ui.Modal):
    def __init__(self, game_id: int, attempt_id: int, bot):
        super().__init__(title="🎯 단어 추측하기")
        self.game_id = game_id
        self.attempt_id = attempt_id
        self.bot = bot

        self.guess_input = discord.ui.TextInput(
            label="5글자 한글 단어를 입력하세요",
            placeholder="예: 사과나무딸기",
            min_length=5,
            max_length=5,
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.guess_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        guess_word = self.guess_input.value.strip()
        user_id = str(interaction.user.id)
        
        # 단어 검증
        if not WordleLogic.validate_korean_word(guess_word):
            embed = discord.Embed(
                title="❌ 잘못된 입력",
                description="올바른 5글자 한글 단어를 입력해주세요.",
                color=WordleUI.COLORS['danger']
            )
            
            embed.add_field(
                name="입력된 내용",
                value=f"**{guess_word}** (길이: {len(guess_word)}글자)",
                inline=False
            )
            
            embed.add_field(
                name="올바른 예시",
                value="사과나무, 컴퓨터게임, 따뜻한물 등",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 게임 및 도전 정보 조회
        game = await self.bot.db_manager.get_game_by_id(self.game_id)
        attempt = await self.bot.db_manager.get_user_attempt(self.game_id, user_id)

        if not game or not attempt or attempt['is_completed']:
            await interaction.response.send_message(
                "❌ 게임 정보를 찾을 수 없거나 이미 완료된 게임입니다.",
                ephemeral=True
            )
            return
        
        # 포인트 부족 확인
        if not WordleLogic.can_continue_game(attempt['remaining_points'], attempt['points_per_failure']):
            await interaction.response.send_message(
                "❌ 포인트가 부족하여 더 이상 추측할 수 없습니다.",
                ephemeral=True
            )
            return
        
        # 단어 비교
        answer = game['word']
        pattern = WordleLogic.compare_words(guess_word, answer)
        is_winner = WordleLogic.is_winner(pattern)
        
        # 추측 기록 저장
        attempts_used = attempt['attempts_used'] + 1
        guess = WordleGuess(
            attempt_id=self.attempt_id,
            guess_word=guess_word,
            result_pattern=pattern,
            guess_number=attempts_used
        )
        await self.bot.db_manager.add_guess(guess)
        
        # 포인트 차감 (정답이 아닌 경우)
        if not is_winner:
            new_remaining = attempt['remaining_points'] - attempt['points_per_failure']
            await self.bot.db_manager.update_attempt_progress(
                self.attempt_id, 
                max(0, new_remaining), 
                attempts_used
            )
        else:
            # 정답인 경우
            await self.bot.db_manager.update_attempt_progress(
                self.attempt_id,
                attempt['remaining_points'],  # 포인트 차감 없음
                attempts_used
            )
        
        # 게임 결과 처리
        if is_winner:
            await self._handle_winner(interaction, user_id, game, attempt)
        else:
            await self._handle_guess_result(interaction, guess_word, pattern, attempt)
    
    async def _handle_winner(self, interaction: discord.Interaction, user_id: str, game: Dict, attempt: Dict):
        """정답자 처리 (향상된 UI)"""
        username = interaction.user.display_name
        
        # 게임 완료 처리
        await self.bot.db_manager.complete_game(self.game_id, user_id, username)
        await self.bot.db_manager.complete_attempt(self.attempt_id, is_winner=True)

        # 안전한 포인트 지급 (전체 풀)
        total_reward = game['total_pool']
        success = await self.bot.db_manager.safe_reward_winner(self.game_id, user_id, total_reward)

        if not success:
            # 안전한 지급 실패시 일반 지급 시도
            guild_id = str(interaction.guild_id)
            await self.bot.db_manager.add_user_points(guild_id, user_id, total_reward)

        # 승리 메시지
        embed = discord.Embed(
            title="🎉 정답입니다! 축하합니다!",
            description=f"**{game['word']}**가 정답입니다!\n"
                       f"🏆 {attempt['attempts_used'] + 1}번 만에 맞추셨네요!",
            color=WordleUI.COLORS['success'],
            timestamp=datetime.now()
        )
        
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        # 보상 정보
        bonus_points = total_reward - attempt['remaining_points']
        embed.add_field(
            name=f"{WordleUI.EMOJIS['gem']} 획득 보상",
            value=f"💰 **총 {total_reward:,}점** 획득!\n"
                  f"🔄 베팅 반환: {attempt['remaining_points']:,}점\n"
                  f"🎁 보너스: {bonus_points:,}점",
            inline=True
        )
        
        # 성과 분석
        efficiency = (attempt['bet_amount'] - (attempt['attempts_used'] * attempt['points_per_failure'])) / attempt['bet_amount'] * 100
        embed.add_field(
            name=f"{WordleUI.EMOJIS['chart']} 성과 분석",
            value=f"🎯 시도 횟수: {attempt['attempts_used'] + 1}회\n"
                  f"💪 효율성: {efficiency:.1f}%\n"
                  f"🏅 수익률: {(bonus_points / attempt['bet_amount'] * 100):.1f}%",
            inline=True
        )
        
        embed.set_footer(text="🎯 띵지워들 • 훌륭한 성과입니다!")
        
        # 난이도 평가 버튼 추가
        view = EnhancedDifficultyRatingView(self.game_id, self.attempt_id, self.bot)

        await interaction.response.send_message(embed=embed, view=view)
    
    async def _handle_guess_result(self, interaction: discord.Interaction, guess_word: str, pattern: str, attempt: Dict):
        """일반 추측 결과 처리 (향상된 UI)"""
        emoji_result = WordleLogic.pattern_to_emoji(pattern)
        new_remaining = max(0, attempt['remaining_points'] - attempt['points_per_failure'])
        
        # 결과 분석
        correct_count = pattern.count('1')
        wrong_pos_count = pattern.count('2')
        wrong_count = pattern.count('0')
        
        embed = discord.Embed(
            title="🎯 추측 결과",
            color=WordleUI.COLORS['warning'],
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="💭 추측한 단어",
            value=f"**{guess_word}**\n{emoji_result}",
            inline=False
        )
        
        # 상세 분석
        analysis_text = ""
        if correct_count > 0:
            analysis_text += f"🟩 정확한 위치: **{correct_count}개**\n"
        if wrong_pos_count > 0:
            analysis_text += f"🟨 다른 위치에 있음: **{wrong_pos_count}개**\n"
        if wrong_count > 0:
            analysis_text += f"⬜ 단어에 없음: **{wrong_count}개**\n"
        
        if correct_count + wrong_pos_count == 0:
            analysis_text += "😅 완전히 다른 단어네요!"
        elif correct_count >= 3:
            analysis_text += "🔥 거의 다 맞췄어요!"
        elif correct_count + wrong_pos_count >= 3:
            analysis_text += "💪 잘하고 있어요!"
        
        embed.add_field(
            name="📊 결과 분석",
            value=analysis_text,
            inline=False
        )
        
        embed.add_field(
            name="💰 포인트 현황",
            value=f"💸 차감: **{attempt['points_per_failure']:,}점**\n"
                  f"💰 남은 포인트: **{new_remaining:,}점**",
            inline=True
        )
        
        # 진행률 표시
        progress = WordleUI.create_progress_bar(
            attempt['bet_amount'] - new_remaining,
            attempt['bet_amount']
        )
        used_percentage = ((attempt['bet_amount'] - new_remaining) / attempt['bet_amount']) * 100
        
        embed.add_field(
            name="📊 진행 상황",
            value=f"`{progress}` {used_percentage:.1f}%",
            inline=True
        )
        
        # 게임 계속 가능 여부
        can_continue = WordleLogic.can_continue_game(new_remaining, attempt['points_per_failure'])
        
        if can_continue:
            embed.add_field(
                name="🔥 계속하기",
                value="아직 기회가 있습니다! 계속 도전해보세요.\n"
                      f"다음 실패시 **{attempt['points_per_failure']:,}점** 추가 차감",
                inline=False
            )
        else:
            embed.color = WordleUI.COLORS['danger']
            embed.add_field(
                name="💸 게임 종료",
                value="포인트가 부족하여 게임이 종료됩니다.\n"
                      "아쉽지만 다음 기회에 더 좋은 결과를!",
                inline=False
            )
            
            # 게임 종료 처리
            await self.bot.db_manager.complete_attempt(self.attempt_id, is_winner=False)
            failed_points = attempt['bet_amount'] - new_remaining
            await self.bot.db_manager.add_to_pool(self.game_id, failed_points)

        await interaction.response.send_message(embed=embed, ephemeral=True)

class EnhancedDifficultyRatingView(discord.ui.View):
    def __init__(self, game_id: int, attempt_id: int, bot):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.attempt_id = attempt_id
        self.bot = bot
    
    @discord.ui.button(label="쉬움", style=discord.ButtonStyle.green, emoji="😅")
    async def rate_easy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._submit_rating(interaction, "쉬움")
    
    @discord.ui.button(label="적절함", style=discord.ButtonStyle.primary, emoji="👍") 
    async def rate_appropriate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._submit_rating(interaction, "적절함")
    
    @discord.ui.button(label="어려움", style=discord.ButtonStyle.red, emoji="😰")
    async def rate_hard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._submit_rating(interaction, "어려움")
    
    async def _submit_rating(self, interaction: discord.Interaction, rating_value: str):
        user_id = str(interaction.user.id)
        username = interaction.user.display_name
        
        rating = WordleRating(
            game_id=self.game_id,
            user_id=user_id,
            username=username,
            rating=rating_value
        )
        
        success = await self.bot.db_manager.add_rating(rating)
        
        if success:
            embed = discord.Embed(
                title="✅ 난이도 평가 완료",
                description=f"이 게임의 난이도를 **{rating_value}**으로 평가해주셨습니다.",
                color=WordleUI.COLORS['success']
            )
            
            embed.add_field(
                name="🎁 출제자 보상",
                value="여러분의 평가는 출제자의 보상 결정에 영향을 줍니다!\n"
                      "• '적절함' 50% 이상 → 200점 보상\n"
                      "• 그 외 → 50점 기본 보상",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="ℹ️ 이미 평가 완료",
                description="이미 이 게임의 난이도를 평가하셨습니다.",
                color=WordleUI.COLORS['info']
            )
        
        await interaction.response.edit_message(embed=embed, view=None)

class GameSelectionView(discord.ui.View):
    def __init__(self, games: List[Dict], bot):
        super().__init__(timeout=300)
        self.add_item(GameSelectionDropdown(games, bot))

class GameSelectionDropdown(discord.ui.Select):
    def __init__(self, games: List[Dict], bot):
        options = []
        for game in games[:25]:  # 드롭다운 최대 25개
            created_time = datetime.fromisoformat(game['created_at'])
            option = discord.SelectOption(
                label=f"#{game['id']} - {game['creator_username']}",
                description=f"베팅: {game['bet_points']:,}점 | 풀: {game['total_pool']:,}점 | {game['hint'][:50] if game['hint'] else '힌트 없음'}",
                value=str(game['id'])
            )
            options.append(option)
        
        super().__init__(placeholder="도전할 게임을 선택하세요...", options=options)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        game_id = int(self.values[0])
        
        # 베팅 금액 선택 뷰로 전환
        view = BetSelectionView(game_id, self.bot)
        
        embed = discord.Embed(
            title="💰 베팅 금액 선택",
            description=f"게임 #{game_id}에 도전합니다!\n베팅할 포인트를 선택해주세요.",
            color=0xffa500
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

class BetSelectionView(discord.ui.View):
    def __init__(self, game_id: int, bot):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.bot = bot
        
    @discord.ui.button(label="100점", style=discord.ButtonStyle.green, emoji="💰")
    async def bet_100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._start_game(interaction, 100)
    
    @discord.ui.button(label="500점", style=discord.ButtonStyle.primary, emoji="💎")
    async def bet_500(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._start_game(interaction, 500)
    
    @discord.ui.button(label="1000점", style=discord.ButtonStyle.red, emoji="🔥")
    async def bet_1000(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._start_game(interaction, 1000)
    
    async def _start_game(self, interaction: discord.Interaction, bet_amount: int):
        user_id = str(interaction.user.id)
        username = interaction.user.display_name
        guild_id = str(interaction.guild_id)

        # 포인트 확인
        user_points = await self.bot.db_manager.get_user_points(guild_id, user_id)

        if user_points < bet_amount:
            await interaction.response.send_message(
                f"❌ 포인트가 부족합니다!\n"
                f"현재 포인트: {user_points:,}점\n"
                f"필요 포인트: {bet_amount:,}점",
                ephemeral=True
            )
            return
        
        # 이미 도전 중인지 확인
        existing_attempt = await self.bot.db_manager.get_user_attempt(self.game_id, user_id)
        if existing_attempt and not existing_attempt['is_completed']:
            # 기존 게임 재개
            view = GamePlayView(self.game_id, existing_attempt['id'], self.bot)
            await view.show_game_status(interaction)
            return
        
        # 새 도전 시작
        points_per_failure = max(1, bet_amount // 10)  # 베팅액의 10%씩 차감
        
        attempt = WordleAttempt(
            game_id=self.game_id,
            user_id=user_id,
            username=username,
            bet_amount=bet_amount,
            remaining_points=bet_amount,
            points_per_failure=points_per_failure
        )

        attempt_id = await self.bot.db_manager.create_attempt(attempt)
        if not attempt_id:
            await interaction.response.send_message(
                "❌ 게임 시작 중 오류가 발생했습니다.",
                ephemeral=True
            )
            return
        
        # 초기 베팅 포인트 차감
        guild_id = str(interaction.guild_id)
        await self.bot.db_manager.add_user_points(guild_id, user_id, -bet_amount)

        # 게임 플레이 뷰 시작
        view = GamePlayView(self.game_id, attempt_id, self.bot)
        await view.show_game_status(interaction)

class GameDeleteView(discord.ui.View):
    def __init__(self, games: List[Dict], bot):
        super().__init__(timeout=300)
        self.bot = bot
        self.add_item(GameDeleteDropdown(games, bot))

class GameDeleteDropdown(discord.ui.Select):
    def __init__(self, games: List[Dict], bot):
        options = []
        for game in games:
            option = discord.SelectOption(
                label=f"게임 #{game['id']} 삭제",
                description=f"베팅: {game['bet_points']:,}점 반환 | 힌트: {game['hint'][:50] if game['hint'] else '없음'}",
                value=str(game['id'])
            )
            options.append(option)
        
        super().__init__(placeholder="삭제할 게임을 선택하세요...", options=options)
        self.bot = bot
    
    async def callback(self, interaction: discord.Interaction):
        game_id = int(self.values[0])
        user_id = str(interaction.user.id)
        
        # 게임 정보 조회
        game = await self.bot.db_manager.get_game_by_id(game_id)
        if not game:
            await interaction.response.send_message("❌ 게임을 찾을 수 없습니다.", ephemeral=True)
            return
        
        # 게임 삭제
        success = await self.bot.db_manager.delete_game(game_id, user_id)
        if not success:
            await interaction.response.send_message("❌ 게임 삭제에 실패했습니다.", ephemeral=True)
            return
        
        # 포인트 반환
        guild_id = str(interaction.guild_id)
        await self.bot.db_manager.add_user_points(guild_id, user_id, game['bet_points'])

        embed = discord.Embed(
            title="✅ 게임 삭제 완료",
            description=f"게임 #{game_id}가 삭제되었습니다.",
            color=0x00ff88
        )
        
        embed.add_field(
            name="💰 포인트 반환",
            value=f"{game['bet_points']:,}점이 반환되었습니다.",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


async def setup(bot):
    await bot.add_cog(WordleGameCommands(bot))