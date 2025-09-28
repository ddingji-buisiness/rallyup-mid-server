import discord
from discord.ext import commands
from typing import List, Dict, Optional
import asyncio

from utils.balance_algorithm import TeamBalancer, BalancingMode, BalanceResult

class PlayerSelectionView(discord.ui.View):
    """10명의 참가자를 선택하는 View"""
    
    def __init__(self, bot, guild_id: str, eligible_players: List[Dict]):
        super().__init__(timeout=300)  # 5분 타임아웃
        self.bot = bot
        self.guild_id = guild_id
        self.eligible_players = eligible_players
        self.selected_players = []
        self.interaction_user = None
        
        # 드롭다운 메뉴 생성
        self.add_player_select()
        
        # 버튼들 초기 상태 설정
        self.update_button_states()
    
    def add_player_select(self):
        """플레이어 선택 드롭다운 추가"""
        if len(self.eligible_players) == 0:
            return
        
        # 10명이 이미 선택되었으면 드롭다운을 추가하지 않음
        if len(self.selected_players) >= 10:
            self.clear_items()
            self.add_buttons()
            return
        
        # 드롭다운 옵션 생성 (최대 25개까지)
        options = []
        for player in self.eligible_players[:25]:
            # 선택된 플레이어는 제외
            if player['user_id'] not in [p['user_id'] for p in self.selected_players]:
                description = f"{player.get('main_position', '미설정')} | {player.get('total_games', 0)}경기"
                if player.get('total_games', 0) > 0:
                    winrate = (player.get('total_wins', 0) / player['total_games']) * 100
                    description += f" | {winrate:.1f}% 승률"
                
                options.append(discord.SelectOption(
                    label=player['username'][:100],  # 라벨 길이 제한
                    value=player['user_id'],
                    description=description[:100]  # 설명 길이 제한
                ))
        
        # 옵션이 있고 아직 선택할 수 있는 경우에만 드롭다운 추가
        if options and len(self.selected_players) < 10:
            remaining_slots = 10 - len(self.selected_players)
            max_values = min(remaining_slots, len(options))
            
            # max_values가 최소 1 이상이 되도록 보장
            if max_values > 0:
                player_select = PlayerSelectDropdown(
                    options=options,
                    placeholder=f"참가자 선택 ({len(self.selected_players)}/10)",
                    min_values=1,
                    max_values=max_values
                )
                player_select.parent_view = self
                
                # 기존 드롭다운 제거 후 새로 추가
                self.clear_items()
                self.add_item(player_select)
                self.add_buttons()
            else:
                # 선택할 수 있는 옵션이 없으면 드롭다운 없이 버튼만
                self.clear_items()
                self.add_buttons()
        else:
            # 옵션이 없거나 이미 10명이 선택되었으면 드롭다운 없이 버튼만
            self.clear_items()
            self.add_buttons()
    
    def add_buttons(self):
        """확인 및 취소 버튼 추가"""
        # 선택 완료 버튼
        confirm_button = discord.ui.Button(
            label=f"선택 완료 ({len(self.selected_players)}/10)",
            style=discord.ButtonStyle.success,
            disabled=len(self.selected_players) != 10,
            emoji="✅"
        )
        confirm_button.callback = self.confirm_selection
        self.add_item(confirm_button)
        
        # 선택 초기화 버튼
        reset_button = discord.ui.Button(
            label="선택 초기화",
            style=discord.ButtonStyle.secondary,
            disabled=len(self.selected_players) == 0,
            emoji="🔄"
        )
        reset_button.callback = self.reset_selection
        self.add_item(reset_button)
        
        # 취소 버튼
        cancel_button = discord.ui.Button(
            label="취소",
            style=discord.ButtonStyle.danger,
            emoji="❌"
        )
        cancel_button.callback = self.cancel_selection
        self.add_item(cancel_button)
    
    def update_button_states(self):
        """버튼 상태 업데이트"""
        # View 재구성
        self.add_player_select()
    
    async def confirm_selection(self, interaction: discord.Interaction):
        """10명 선택 완료"""
        if len(self.selected_players) != 10:
            await interaction.response.send_message(
                "❌ 정확히 10명을 선택해야 합니다.", ephemeral=True
            )
            return
        
        # 다음 단계로 이동
        options_view = BalancingOptionsView(self.bot, self.guild_id, self.selected_players)
        
        embed = discord.Embed(
            title="⚙️ 밸런싱 옵션 설정",
            description="밸런싱 방식을 선택해주세요.",
            color=0x0099ff
        )
        
        # 선택된 플레이어 목록 표시
        player_list = "\n".join([f"• {p['username']}" for p in self.selected_players])
        embed.add_field(
            name="🎮 선택된 참가자 (10명)",
            value=player_list,
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=options_view)
    
    async def reset_selection(self, interaction: discord.Interaction):
        """선택 초기화"""
        self.selected_players = []
        self.update_button_states()
        
        embed = discord.Embed(
            title="👥 참가자 선택",
            description="내전에 참가할 10명을 선택해주세요.",
            color=0x0099ff
        )
        
        embed.add_field(
            name="📊 선택 가능한 플레이어",
            value=f"총 {len(self.eligible_players)}명 (최소 3경기 이상)",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def cancel_selection(self, interaction: discord.Interaction):
        """선택 취소"""
        embed = discord.Embed(
            title="❌ 팀 밸런싱 취소",
            description="팀 밸런싱이 취소되었습니다.",
            color=0xff4444
        )
        
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
class ManualTeamSelectionView(discord.ui.View):
    """수동 팀 선택 View (밸런스 체크 모드)"""
    
    def __init__(self, bot, guild_id: str, all_users: List[Dict]):
        super().__init__(timeout=600)  # 10분 타임아웃
        self.bot = bot
        self.guild_id = guild_id
        self.all_users = all_users
        self.team_a_players = []
        self.team_b_players = []
        self.interaction_user = None
        self.current_team = "A"  # 현재 선택 중인 팀
        
        # 초기 UI 설정
        self.update_ui()
    
    def update_ui(self):
        """UI 컴포넌트 업데이트"""
        self.clear_items()
        
        # 현재 선택 중인 팀에 따라 드롭다운 추가
        if self.current_team == "A" and len(self.team_a_players) < 5:
            self.add_team_selection_dropdown("A")
        elif self.current_team == "B" and len(self.team_b_players) < 5:
            self.add_team_selection_dropdown("B")
        
        # 버튼들 추가
        self.add_control_buttons()
    
    def add_team_selection_dropdown(self, team: str):
        """팀 선택 드롭다운 추가"""
        used_user_ids = set()
        used_user_ids.update([p['user_id'] for p in self.team_a_players])
        used_user_ids.update([p['user_id'] for p in self.team_b_players])
        
        # 아직 선택되지 않은 플레이어들만 표시
        available_players = [p for p in self.all_users if p['user_id'] not in used_user_ids]
        
        if not available_players:
            return
        
        # 드롭다운 옵션 생성 (최대 25개)
        options = []
        for player in available_players[:25]:
            description = f"{player.get('main_position', '미설정')}"
            if player.get('total_games', 0) > 0:
                winrate = (player.get('total_wins', 0) / player['total_games']) * 100
                description += f" | {player['total_games']}경기 {winrate:.1f}%"
            else:
                tier = player.get('current_season_tier', '배치안함')
                description += f" | {tier} (티어기반)"
            
            options.append(discord.SelectOption(
                label=player['username'][:100],
                value=player['user_id'],
                description=description[:100]
            ))
        
        if options:
            current_count = len(self.team_a_players) if team == "A" else len(self.team_b_players)
            remaining = 5 - current_count
            
            team_dropdown = TeamPlayerSelectDropdown(
                options=options,
                placeholder=f"{team}팀 선택 ({current_count}/5)",
                min_values=1,
                max_values=min(remaining, len(options), 5),
                team=team
            )
            team_dropdown.parent_view = self
            self.add_item(team_dropdown)
    
    def add_control_buttons(self):
        """컨트롤 버튼들 추가"""
        # A팀/B팀 전환 버튼
        if len(self.team_a_players) < 5:
            team_a_button = discord.ui.Button(
                label=f"A팀 선택 ({len(self.team_a_players)}/5)",
                style=discord.ButtonStyle.primary if self.current_team == "A" else discord.ButtonStyle.secondary,
                emoji="🔵",
                disabled=self.current_team == "A"
            )
            team_a_button.callback = lambda i: self.switch_team(i, "A")
            self.add_item(team_a_button)
        
        if len(self.team_b_players) < 5 and len(self.team_a_players) > 0:
            team_b_button = discord.ui.Button(
                label=f"B팀 선택 ({len(self.team_b_players)}/5)",
                style=discord.ButtonStyle.danger if self.current_team == "B" else discord.ButtonStyle.secondary,
                emoji="🔴",
                disabled=self.current_team == "B"
            )
            team_b_button.callback = lambda i: self.switch_team(i, "B")
            self.add_item(team_b_button)
        
        # 밸런스 분석 버튼 (양팀 모두 5명일 때)
        if len(self.team_a_players) == 5 and len(self.team_b_players) == 5:
            analyze_button = discord.ui.Button(
                label="밸런스 분석 시작",
                style=discord.ButtonStyle.success,
                emoji="🎯"
            )
            analyze_button.callback = self.analyze_balance
            self.add_item(analyze_button)
        
        # 초기화 버튼
        if self.team_a_players or self.team_b_players:
            reset_button = discord.ui.Button(
                label="팀 구성 초기화",
                style=discord.ButtonStyle.secondary,
                emoji="🔄"
            )
            reset_button.callback = self.reset_teams
            self.add_item(reset_button)
        
        # 취소 버튼
        cancel_button = discord.ui.Button(
            label="취소",
            style=discord.ButtonStyle.danger,
            emoji="❌"
        )
        cancel_button.callback = self.cancel
        self.add_item(cancel_button)
    
    async def switch_team(self, interaction: discord.Interaction, team: str):
        """팀 선택 전환"""
        self.current_team = team
        self.update_ui()
        
        embed = self.create_team_status_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def analyze_balance(self, interaction: discord.Interaction):
        """밸런스 분석 실행"""
        await interaction.response.defer()
        
        try:
            from utils.balance_algorithm import TeamBalancer, BalancingMode
            
            # 로딩 메시지
            embed = discord.Embed(
                title="⏳ 팀 밸런스 분석 중...",
                description="하이브리드 스코어링으로 정밀 분석 진행 중입니다.",
                color=0xffaa00
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            # 밸런스 분석 실행
            balancer = TeamBalancer(mode=BalancingMode.PRECISE)
            result = await asyncio.get_event_loop().run_in_executor(
                None, balancer.analyze_team_balance, self.team_a_players, self.team_b_players, True
            )
            
            # 결과 표시
            result_view = BalanceCheckResultView(self.bot, result, self.team_a_players, self.team_b_players, self.all_users)
            result_embed = result_view.create_balance_check_embed(result)
            
            await interaction.edit_original_response(embed=result_embed, view=result_view)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 분석 실패",
                description=f"밸런스 분석 중 오류가 발생했습니다:\n```{str(e)}```",
                color=0xff4444
            )
            await interaction.edit_original_response(embed=embed, view=None)
    
    async def reset_teams(self, interaction: discord.Interaction):
        """팀 구성 초기화"""
        self.team_a_players = []
        self.team_b_players = []
        self.current_team = "A"
        self.update_ui()
        
        embed = self.create_team_status_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def cancel(self, interaction: discord.Interaction):
        """취소"""
        embed = discord.Embed(
            title="❌ 밸런스 체크 취소",
            description="팀 밸런스 체크가 취소되었습니다.",
            color=0xff4444
        )
        
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    def create_team_status_embed(self) -> discord.Embed:
        """현재 팀 상태 임베드 생성"""
        embed = discord.Embed(
            title="🔍 팀 밸런스 체크 - 팀 구성",
            color=0x9966ff
        )
        
        # A팀 정보
        if self.team_a_players:
            team_a_text = "\n".join([
                f"• {p['username']} ({p.get('main_position', '미설정')})"
                for p in self.team_a_players
            ])
        else:
            team_a_text = "아직 선택된 플레이어가 없습니다."
        
        embed.add_field(
            name=f"🔵 A팀 ({len(self.team_a_players)}/5)",
            value=team_a_text,
            inline=True
        )
        
        # B팀 정보
        if self.team_b_players:
            team_b_text = "\n".join([
                f"• {p['username']} ({p.get('main_position', '미설정')})"
                for p in self.team_b_players
            ])
        else:
            team_b_text = "아직 선택된 플레이어가 없습니다."
        
        embed.add_field(
            name=f"🔴 B팀 ({len(self.team_b_players)}/5)",
            value=team_b_text,
            inline=True
        )
        
        # 진행 상태
        total_selected = len(self.team_a_players) + len(self.team_b_players)
        
        if total_selected == 0:
            status_text = "🔵 A팀부터 선택을 시작하세요."
        elif len(self.team_a_players) < 5:
            status_text = f"🔵 A팀 선택 중 ({5 - len(self.team_a_players)}명 더 필요)"
        elif len(self.team_b_players) < 5:
            status_text = f"🔴 B팀 선택 중 ({5 - len(self.team_b_players)}명 더 필요)"
        else:
            status_text = "✅ 팀 구성 완료! 밸런스 분석을 시작하세요."
        
        embed.add_field(
            name="📊 진행 상태",
            value=status_text,
            inline=False
        )
        
        # 분석 정보
        embed.add_field(
            name="🎯 분석 방식",
            value="• 내전 데이터가 있는 유저: 실제 승률 + 티어 보정\n"
                  "• 신규 유저: 오버워치 티어 기반 예측\n"
                  "• 하이브리드 스코어링으로 정확한 밸런스 분석",
            inline=False
        )
        
        return embed

class TeamPlayerSelectDropdown(discord.ui.Select):
    """팀별 플레이어 선택 드롭다운"""
    
    def __init__(self, team: str, **kwargs):
        super().__init__(**kwargs)
        self.team = team
        self.parent_view = None
    
    async def callback(self, interaction: discord.Interaction):
        # 선택된 플레이어들을 해당 팀에 추가
        for user_id in self.values:
            selected_player = next(
                (p for p in self.parent_view.all_users if p['user_id'] == user_id),
                None
            )
            if selected_player:
                if self.team == "A" and len(self.parent_view.team_a_players) < 5:
                    self.parent_view.team_a_players.append(selected_player)
                elif self.team == "B" and len(self.parent_view.team_b_players) < 5:
                    self.parent_view.team_b_players.append(selected_player)
        
        # A팀이 5명 완성되면 자동으로 B팀 선택으로 전환
        if self.team == "A" and len(self.parent_view.team_a_players) == 5:
            self.parent_view.current_team = "B"
        
        # UI 업데이트
        self.parent_view.update_ui()
        embed = self.parent_view.create_team_status_embed()
        
class BalanceCheckResultView(discord.ui.View):
    """밸런스 체크 결과 표시 View"""
    
    def __init__(self, bot, result: BalanceResult, team_a_players: List[Dict], team_b_players: List[Dict], all_users: List[Dict]):
        super().__init__(timeout=600)  # 10분 타임아웃
        self.bot = bot
        self.result = result
        self.original_team_a = team_a_players
        self.original_team_b = team_b_players
        self.all_users = all_users
        
        self.add_buttons()
    
    def add_buttons(self):
        """버튼들 추가"""
        # 팀 수정 버튼
        edit_teams_button = discord.ui.Button(
            label="팀 구성 수정",
            style=discord.ButtonStyle.secondary,
            emoji="✏️"
        )
        edit_teams_button.callback = self.edit_teams
        self.add_item(edit_teams_button)
        
        # 새로운 분석 버튼
        new_analysis_button = discord.ui.Button(
            label="새로운 분석",
            style=discord.ButtonStyle.secondary,
            emoji="🔄"
        )
        new_analysis_button.callback = self.new_analysis
        self.add_item(new_analysis_button)
        
        # 추천 개선사항이 있다면 표시
        if self.result.balance_score < 0.8:  # 밸런스가 완벽하지 않은 경우
            suggestion_button = discord.ui.Button(
                label="개선 제안 보기",
                style=discord.ButtonStyle.primary,
                emoji="💡"
            )
            suggestion_button.callback = self.show_suggestions
            self.add_item(suggestion_button)
        
        # 확정 버튼
        confirm_button = discord.ui.Button(
            label="이 구성으로 확정",
            style=discord.ButtonStyle.success,
            emoji="✅"
        )
        confirm_button.callback = self.confirm_teams
        self.add_item(confirm_button)
        
        # 취소 버튼
        cancel_button = discord.ui.Button(
            label="취소",
            style=discord.ButtonStyle.danger,
            emoji="❌"
        )
        cancel_button.callback = self.cancel
        self.add_item(cancel_button)
    
    def create_balance_check_embed(self, result: BalanceResult) -> discord.Embed:
        """밸런스 체크 결과 임베드 생성"""
        # 승률 편차에 따른 색상 및 평가
        winrate_deviation = abs(result.predicted_winrate_a - 0.5)
        if winrate_deviation <= 0.05:  # 45-55%
            color = 0x00ff00
            balance_emoji = "👑"
            balance_text = "황금 밸런스!"
        elif winrate_deviation <= 0.1:  # 40-60%
            color = 0x99ff99
            balance_emoji = "🟢"
            balance_text = "매우 좋은 밸런스"
        elif winrate_deviation <= 0.15:  # 35-65%
            color = 0xffaa00
            balance_emoji = "🟡"
            balance_text = "양호한 밸런스"
        elif winrate_deviation <= 0.2:  # 30-70%
            color = 0xff9900
            balance_emoji = "🟠"
            balance_text = "보통 밸런스"
        else:  # 30% 미만 또는 70% 초과
            color = 0xff4444
            balance_emoji = "🔴"
            balance_text = "재조정 권장"
        
        embed = discord.Embed(
            title="🔍 팀 밸런스 분석 결과",
            color=color
        )
        
        # A팀 구성
        team_a_text = (
            f"🛡️ {result.team_a.tank.username} (탱커 {result.team_a.tank.tank_skill:.1%})\n"
            f"⚔️ {result.team_a.dps1.username} (딜러 {result.team_a.dps1.dps_skill:.1%})\n"
            f"⚔️ {result.team_a.dps2.username} (딜러 {result.team_a.dps2.dps_skill:.1%})\n"
            f"💚 {result.team_a.support1.username} (힐러 {result.team_a.support1.support_skill:.1%})\n"
            f"💚 {result.team_a.support2.username} (힐러 {result.team_a.support2.support_skill:.1%})"
        )
        
        # B팀 구성
        team_b_text = (
            f"🛡️ {result.team_b.tank.username} (탱커 {result.team_b.tank.tank_skill:.1%})\n"
            f"⚔️ {result.team_b.dps1.username} (딜러 {result.team_b.dps1.dps_skill:.1%})\n"
            f"⚔️ {result.team_b.dps2.username} (딜러 {result.team_b.dps2.dps_skill:.1%})\n"
            f"💚 {result.team_b.support1.username} (힐러 {result.team_b.support1.support_skill:.1%})\n"
            f"💚 {result.team_b.support2.username} (힐러 {result.team_b.support2.support_skill:.1%})"
        )
        
        embed.add_field(
            name=f"🔵 A팀 (예상승률: {result.predicted_winrate_a:.1%})",
            value=team_a_text,
            inline=True
        )
        
        embed.add_field(
            name=f"🔴 B팀 (예상승률: {1-result.predicted_winrate_a:.1%})",
            value=team_b_text,
            inline=True
        )
        
        # 밸런스 분석
        analysis_text = (
            f"{balance_emoji} **밸런스 평가**: {balance_text}\n"
            f"📊 **스킬 차이**: {result.skill_difference:.3f}\n"
            f"💯 **밸런스 점수**: {result.balance_score:.3f}/1.000"
        )
        
        embed.add_field(
            name="📈 종합 분석",
            value=analysis_text,
            inline=False
        )
        
        # 포지션별 분석
        reasoning_text = (
            f"🛡️ {result.reasoning.get('tank', '')}\n"
            f"⚔️ {result.reasoning.get('dps', '')}\n"
            f"💚 {result.reasoning.get('support', '')}"
        )
        
        embed.add_field(
            name="🔍 포지션별 분석",
            value=reasoning_text,
            inline=False
        )
        
        # 하이브리드 스코어링 정보
        embed.add_field(
            name="🎯 분석 방식",
            value="• 경험 많은 유저: 실제 내전 데이터 기반\n"
                  "• 신규 유저: 오버워치 티어 + 부분 데이터 활용\n"
                  "• 하이브리드 스코어링으로 정확한 예측",
            inline=False
        )
        
        # 개선 여지가 있는 경우 힌트 제공
        if result.balance_score < 0.8:
            embed.add_field(
                name="💡 개선 힌트",
                value="'개선 제안 보기' 버튼을 클릭하면 더 균형잡힌 팀 구성 방법을 확인할 수 있습니다.",
                inline=False
            )
        
        return embed
    
    async def edit_teams(self, interaction: discord.Interaction):
        """팀 구성 수정"""
        manual_view = ManualTeamSelectionView(self.bot, interaction.guild_id, self.all_users)
        manual_view.team_a_players = self.original_team_a.copy()
        manual_view.team_b_players = self.original_team_b.copy()
        manual_view.current_team = "A"
        manual_view.interaction_user = interaction.user
        manual_view.update_ui()
        
        embed = manual_view.create_team_status_embed()
        embed.add_field(
            name="🔄 수정 모드",
            value="기존 팀 구성을 불러왔습니다. 원하는 플레이어를 변경해보세요.",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=manual_view)
    
    async def new_analysis(self, interaction: discord.Interaction):
        """새로운 분석 시작"""
        manual_view = ManualTeamSelectionView(self.bot, interaction.guild_id, self.all_users)
        manual_view.interaction_user = interaction.user
        
        embed = manual_view.create_team_status_embed()
        await interaction.response.edit_message(embed=embed, view=manual_view)
    
    async def show_suggestions(self, interaction: discord.Interaction):
        """개선 제안 표시"""
        embed = discord.Embed(
            title="💡 팀 밸런스 개선 제안",
            description="현재 팀 구성을 더욱 균형잡히게 만들 수 있는 방법들입니다.",
            color=0x0099ff
        )
        
        # 간단한 개선 제안 생성
        suggestions = []
        
        # 포지션별 스킬 차이 분석
        tank_diff = abs(self.result.team_a.tank.tank_skill - self.result.team_b.tank.tank_skill)
        dps_diff = abs(
            (self.result.team_a.dps1.dps_skill + self.result.team_a.dps2.dps_skill) / 2 -
            (self.result.team_b.dps1.dps_skill + self.result.team_b.dps2.dps_skill) / 2
        )
        support_diff = abs(
            (self.result.team_a.support1.support_skill + self.result.team_a.support2.support_skill) / 2 -
            (self.result.team_b.support1.support_skill + self.result.team_b.support2.support_skill) / 2
        )
        
        if tank_diff > 0.1:
            suggestions.append("🛡️ 탱커 교체를 고려해보세요")
        if dps_diff > 0.1:
            suggestions.append("⚔️ 딜러 1명 교체를 고려해보세요")
        if support_diff > 0.1:
            suggestions.append("💚 힐러 교체를 고려해보세요")
        
        if not suggestions:
            suggestions.append("✨ 현재 구성도 충분히 좋습니다!")
        
        embed.add_field(
            name="🎯 권장 개선사항",
            value="\n".join(suggestions),
            inline=False
        )
        
        embed.add_field(
            name="📊 현재 밸런스",
            value=f"A팀 {self.result.predicted_winrate_a:.1%} vs B팀 {1-self.result.predicted_winrate_a:.1%}",
            inline=True
        )
        
        embed.add_field(
            name="🎯 목표 범위",
            value="45% ~ 55% (황금 밸런스)",
            inline=True
        )
        
        # 뒤로가기 버튼
        back_button = discord.ui.Button(
            label="결과로 돌아가기",
            style=discord.ButtonStyle.secondary,
            emoji="⬅️"
        )
        
        async def back_callback(back_interaction):
            result_embed = self.create_balance_check_embed(self.result)
            await back_interaction.response.edit_message(embed=result_embed, view=self)
        
        back_button.callback = back_callback
        
        view = discord.ui.View(timeout=300)
        view.add_item(back_button)
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def confirm_teams(self, interaction: discord.Interaction):
        """팀 구성 확정"""
        embed = discord.Embed(
            title="✅ 팀 구성 확정 완료!",
            description="선택된 팀 구성이 확정되었습니다.",
            color=0x00ff00
        )
        
        # 최종 팀 구성 요약
        team_a_summary = f"{self.result.team_a.tank.username}, {self.result.team_a.dps1.username}, {self.result.team_a.dps2.username}, {self.result.team_a.support1.username}, {self.result.team_a.support2.username}"
        team_b_summary = f"{self.result.team_b.tank.username}, {self.result.team_b.dps1.username}, {self.result.team_b.dps2.username}, {self.result.team_b.support1.username}, {self.result.team_b.support2.username}"
        
        embed.add_field(
            name="🔵 A팀",
            value=team_a_summary,
            inline=False
        )
        
        embed.add_field(
            name="🔴 B팀", 
            value=team_b_summary,
            inline=False
        )
        
        # 밸런스 정보
        winrate_deviation = abs(self.result.predicted_winrate_a - 0.5)
        if winrate_deviation <= 0.05:
            balance_status = "👑 황금 밸런스"
        elif winrate_deviation <= 0.1:
            balance_status = "🟢 매우 좋은 밸런스"
        else:
            balance_status = "🟡 양호한 밸런스"
        
        embed.add_field(
            name="📊 최종 밸런스",
            value=f"{balance_status}\nA팀 예상 승률: {self.result.predicted_winrate_a:.1%}",
            inline=False
        )
        
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    async def cancel(self, interaction: discord.Interaction):
        """취소"""
        embed = discord.Embed(
            title="❌ 밸런스 체크 취소",
            description="팀 밸런스 체크가 취소되었습니다.",
            color=0xff4444
        )
        
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

class PlayerSelectDropdown(discord.ui.Select):
    """플레이어 선택 드롭다운"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.parent_view = None
    
    async def callback(self, interaction: discord.Interaction):
        # 선택된 플레이어들을 parent_view에 추가
        for user_id in self.values:
            # 이미 선택된 플레이어가 아닌 경우만 추가
            if user_id not in [p['user_id'] for p in self.parent_view.selected_players]:
                selected_player = next(
                    (p for p in self.parent_view.eligible_players if p['user_id'] == user_id),
                    None
                )
                if selected_player:
                    self.parent_view.selected_players.append(selected_player)
        
        # 10명이 선택되면 자동으로 제한
        if len(self.parent_view.selected_players) >= 10:
            self.parent_view.selected_players = self.parent_view.selected_players[:10]
        
        # View 업데이트
        self.parent_view.update_button_states()
        
        # 현재 선택 상태 표시
        embed = discord.Embed(
            title="👥 참가자 선택",
            description=f"선택된 참가자: {len(self.parent_view.selected_players)}/10명",
            color=0x0099ff
        )
        
        if self.parent_view.selected_players:
            selected_list = "\n".join([
                f"• {p['username']} ({p.get('main_position', '미설정')})"
                for p in self.parent_view.selected_players
            ])
            embed.add_field(
                name="✅ 선택된 플레이어",
                value=selected_list,
                inline=False
            )
        
        if len(self.parent_view.selected_players) < 10:
            embed.add_field(
                name="➕ 추가 선택 필요",
                value=f"{10 - len(self.parent_view.selected_players)}명 더 선택해주세요.",
                inline=False
            )
        else:
            embed.add_field(
                name="🎉 선택 완료!",
                value="'선택 완료' 버튼을 눌러 다음 단계로 진행하세요.",
                inline=False
            )
        
        # 10명이 선택되었을 때는 View에 드롭다운이 없을 수 있으므로 안전하게 처리
        try:
            await interaction.response.edit_message(embed=embed, view=self.parent_view)
        except discord.errors.HTTPException as e:
            # View 구성에 문제가 있는 경우 간단한 embed만 업데이트
            await interaction.response.edit_message(embed=embed, view=None)
            # 새로운 View를 다시 설정
            await interaction.edit_original_response(view=self.parent_view)

class BalancingOptionsView(discord.ui.View):
    """밸런싱 옵션 선택 View"""
    
    def __init__(self, bot, guild_id: str, selected_players: List[Dict]):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.selected_players = selected_players
        self.selected_mode = BalancingMode.PRECISE
        self.interaction_user = None
        
        # 모드 선택 드롭다운 추가
        self.add_mode_select()
        self.add_buttons()
    
    def add_mode_select(self):
        """밸런싱 모드 선택 드롭다운 추가"""
        mode_select = discord.ui.Select(
            placeholder="밸런싱 모드를 선택하세요",
            options=[
                discord.SelectOption(
                    label="⚡ 빠른 밸런싱",
                    value="quick",
                    description="기본 승률 기반 빠른 계산 (~1초)",
                    emoji="⚡"
                ),
                discord.SelectOption(
                    label="🎯 정밀 밸런싱",
                    value="precise",
                    description="모든 요소를 고려한 정밀 계산 (~5초)",
                    emoji="🎯",
                    default=True
                ),
                discord.SelectOption(
                    label="🔬 실험적 밸런싱",
                    value="experimental",
                    description="새로운 조합을 시도하는 실험적 계산 (~2초)",
                    emoji="🔬"
                )
            ]
        )
        mode_select.callback = self.mode_select_callback
        self.add_item(mode_select)
    
    def add_buttons(self):
        """실행 및 뒤로가기 버튼 추가"""
        # 밸런싱 시작 버튼
        start_button = discord.ui.Button(
            label="밸런싱 시작",
            style=discord.ButtonStyle.primary,
            emoji="🚀"
        )
        start_button.callback = self.start_balancing
        self.add_item(start_button)
        
        # 뒤로가기 버튼
        back_button = discord.ui.Button(
            label="뒤로가기",
            style=discord.ButtonStyle.secondary,
            emoji="⬅️"
        )
        back_button.callback = self.go_back
        self.add_item(back_button)
        
        # 취소 버튼
        cancel_button = discord.ui.Button(
            label="취소",
            style=discord.ButtonStyle.danger,
            emoji="❌"
        )
        cancel_button.callback = self.cancel
        self.add_item(cancel_button)
    
    async def mode_select_callback(self, interaction: discord.Interaction):
        """모드 선택 콜백"""
        selected_value = interaction.data['values'][0]
        
        if selected_value == "quick":
            self.selected_mode = BalancingMode.QUICK
            mode_name = "⚡ 빠른 밸런싱"
            mode_desc = "기본 승률을 중심으로 빠르게 계산합니다."
        elif selected_value == "experimental":
            self.selected_mode = BalancingMode.EXPERIMENTAL
            mode_name = "🔬 실험적 밸런싱"
            mode_desc = "다양한 조합을 시도하여 새로운 팀 구성을 제안합니다."
        else:
            self.selected_mode = BalancingMode.PRECISE
            mode_name = "🎯 정밀 밸런싱"
            mode_desc = "포지션 적합도, 팀 시너지 등을 종합적으로 고려합니다."
        
        embed = discord.Embed(
            title="⚙️ 밸런싱 옵션 설정",
            description=f"선택된 모드: **{mode_name}**\n{mode_desc}",
            color=0x0099ff
        )
        
        # 플레이어 목록 (간략하게)
        player_names = [p['username'] for p in self.selected_players]
        embed.add_field(
            name="👥 참가자 (10명)",
            value=", ".join(player_names),
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def start_balancing(self, interaction: discord.Interaction):
        """밸런싱 실행"""
        await interaction.response.defer()
        
        try:
            # 로딩 메시지 표시
            embed = discord.Embed(
                title="⏳ 팀 밸런싱 진행 중...",
                description=f"선택된 모드: {self.selected_mode.value}\n하이브리드 스코어링으로 분석 중입니다.",
                color=0xffaa00
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            # 밸런싱 실행 (하이브리드 스코어링 사용)
            balancer = TeamBalancer(mode=self.selected_mode)
            results = await asyncio.get_event_loop().run_in_executor(
                None, balancer.find_optimal_balance, self.selected_players, True  # use_hybrid=True
            )
            
            if not results:
                embed = discord.Embed(
                    title="❌ 밸런싱 실패",
                    description="적절한 팀 구성을 찾을 수 없습니다.\n다른 플레이어 조합을 시도해보세요.",
                    color=0xff4444
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # 결과 표시
            result_view = BalanceResultView(self.bot, results, self.selected_players)
            result_embed = result_view.create_result_embed(results[0])
            
            await interaction.edit_original_response(embed=result_embed, view=result_view)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 오류 발생",
                description=f"밸런싱 중 오류가 발생했습니다:\n```{str(e)}```",
                color=0xff4444
            )
            await interaction.edit_original_response(embed=embed, view=None)
    
    async def go_back(self, interaction: discord.Interaction):
        """플레이어 선택으로 돌아가기"""
        # 플레이어 선택 단계로 복귀
        eligible_players = await self.bot.db_manager.get_eligible_users_for_balancing(self.guild_id)
        selection_view = PlayerSelectionView(self.bot, self.guild_id, eligible_players)
        selection_view.selected_players = self.selected_players.copy()
        selection_view.update_button_states()
        
        embed = discord.Embed(
            title="👥 참가자 선택",
            description=f"선택된 참가자: {len(self.selected_players)}/10명",
            color=0x0099ff
        )
        
        if self.selected_players:
            selected_list = "\n".join([f"• {p['username']}" for p in self.selected_players])
            embed.add_field(name="✅ 현재 선택된 플레이어", value=selected_list, inline=False)
        
        await interaction.response.edit_message(embed=embed, view=selection_view)
    
    async def cancel(self, interaction: discord.Interaction):
        """취소"""
        embed = discord.Embed(
            title="❌ 팀 밸런싱 취소",
            description="팀 밸런싱이 취소되었습니다.",
            color=0xff4444
        )
        
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

class BalanceResultView(discord.ui.View):
    """밸런싱 결과 표시 View"""
    
    def __init__(self, bot, results: List[BalanceResult], original_players: List[Dict]):
        super().__init__(timeout=600)  # 10분 타임아웃
        self.bot = bot
        self.results = results
        self.original_players = original_players
        self.current_index = 0
        
        self.add_buttons()
    
    def add_buttons(self):
        """버튼들 추가"""
        # 다른 조합 보기 (결과가 2개 이상일 때만)
        if len(self.results) > 1:
            alternative_button = discord.ui.Button(
                label=f"다른 조합 보기 ({self.current_index + 1}/{len(self.results)})",
                style=discord.ButtonStyle.secondary,
                emoji="🔄"
            )
            alternative_button.callback = self.show_alternative
            self.add_item(alternative_button)
        
        # 새로운 밸런싱 버튼
        new_balance_button = discord.ui.Button(
            label="새로운 밸런싱",
            style=discord.ButtonStyle.secondary,
            emoji="🎲"
        )
        new_balance_button.callback = self.new_balancing
        self.add_item(new_balance_button)
        
        # 팀 확정 버튼
        confirm_button = discord.ui.Button(
            label="팀 구성 확정",
            style=discord.ButtonStyle.success,
            emoji="✅"
        )
        confirm_button.callback = self.confirm_teams
        self.add_item(confirm_button)
        
        # 취소 버튼
        cancel_button = discord.ui.Button(
            label="취소",
            style=discord.ButtonStyle.danger,
            emoji="❌"
        )
        cancel_button.callback = self.cancel
        self.add_item(cancel_button)
    
    def create_result_embed(self, result: BalanceResult) -> discord.Embed:
        """결과 임베드 생성"""
        # 승률 편차에 따른 색상 결정
        winrate_deviation = abs(result.predicted_winrate_a - 0.5)
        if winrate_deviation <= 0.05:  # 45-55%
            color = 0x00ff00  # 초록색 (황금 밸런스)
        elif winrate_deviation <= 0.1:  # 40-60%
            color = 0x99ff99  # 연한 초록색
        elif winrate_deviation <= 0.15:  # 35-65%
            color = 0xffaa00  # 주황색
        else:  # 35% 미만 또는 65% 초과
            color = 0xff4444  # 빨간색
        
        embed = discord.Embed(
            title="🎯 팀 밸런싱 결과",
            color=color
        )
        
        # A팀 구성
        team_a_text = (
            f"🛡️ **탱커**: {result.team_a.tank.username} ({result.team_a.tank.tank_skill:.1%})\n"
            f"⚔️ **딜러1**: {result.team_a.dps1.username} ({result.team_a.dps1.dps_skill:.1%})\n"
            f"⚔️ **딜러2**: {result.team_a.dps2.username} ({result.team_a.dps2.dps_skill:.1%})\n"
            f"💚 **힐러1**: {result.team_a.support1.username} ({result.team_a.support1.support_skill:.1%})\n"
            f"💚 **힐러2**: {result.team_a.support2.username} ({result.team_a.support2.support_skill:.1%})"
        )
        
        # B팀 구성
        team_b_text = (
            f"🛡️ **탱커**: {result.team_b.tank.username} ({result.team_b.tank.tank_skill:.1%})\n"
            f"⚔️ **딜러1**: {result.team_b.dps1.username} ({result.team_b.dps1.dps_skill:.1%})\n"
            f"⚔️ **딜러2**: {result.team_b.dps2.username} ({result.team_b.dps2.dps_skill:.1%})\n"
            f"💚 **힐러1**: {result.team_b.support1.username} ({result.team_b.support1.support_skill:.1%})\n"
            f"💚 **힐러2**: {result.team_b.support2.username} ({result.team_b.support2.support_skill:.1%})"
        )
        
        embed.add_field(
            name=f"🔵 A팀 (예상승률: {result.predicted_winrate_a:.1%})",
            value=team_a_text,
            inline=True
        )
        
        embed.add_field(
            name=f"🔴 B팀 (예상승률: {1-result.predicted_winrate_a:.1%})",
            value=team_b_text,
            inline=True
        )
        
        # 밸런싱 분석 - 50:50 기준으로 평가
        winrate_diff = abs(result.predicted_winrate_a - 0.5)
        
        if winrate_diff <= 0.05:
            balance_emoji = "👑"
            balance_text = "황금 밸런스!"
        elif winrate_diff <= 0.1:
            balance_emoji = "🟢"
            balance_text = "매우 좋음"
        elif winrate_diff <= 0.15:
            balance_emoji = "🟡"
            balance_text = "양호함"
        else:
            balance_emoji = "🔴"
            balance_text = "재조정 권장"
        
        analysis_text = (
            f"{balance_emoji} **밸런스 평가**: {balance_text}\n"
            f"📊 **스킬 차이**: {result.skill_difference:.3f}\n"
            f"💡 **종합 평가**: {result.reasoning.get('balance', '분석 중')}"
        )
        
        embed.add_field(
            name="📈 황금 밸런스 분석",
            value=analysis_text,
            inline=False
        )
        
        # 포지션별 분석
        reasoning_text = (
            f"🛡️ {result.reasoning.get('tank', '')}\n"
            f"⚔️ {result.reasoning.get('dps', '')}\n"
            f"💚 {result.reasoning.get('support', '')}"
        )
        
        embed.add_field(
            name="🔍 포지션별 분석",
            value=reasoning_text,
            inline=False
        )
        
        # 50:50 목표 표시
        ideal_range = "45-55%"
        current_range = f"{result.predicted_winrate_a:.1%} vs {1-result.predicted_winrate_a:.1%}"
        
        embed.add_field(
            name="🎯 밸런스 목표",
            value=f"**이상적 범위**: {ideal_range} vs {ideal_range}\n**현재 예상**: {current_range}",
            inline=False
        )
        
        return embed
    
    async def show_alternative(self, interaction: discord.Interaction):
        """다른 조합 보기"""
        self.current_index = (self.current_index + 1) % len(self.results)
        
        # 버튼 업데이트
        self.clear_items()
        self.add_buttons()
        
        # 새로운 결과 표시
        new_embed = self.create_result_embed(self.results[self.current_index])
        await interaction.response.edit_message(embed=new_embed, view=self)
    
    async def new_balancing(self, interaction: discord.Interaction):
        """새로운 밸런싱 시작"""
        options_view = BalancingOptionsView(self.bot, interaction.guild_id, self.original_players)
        
        embed = discord.Embed(
            title="⚙️ 새로운 밸런싱",
            description="다른 방식으로 밸런싱을 시도해보세요.",
            color=0x0099ff
        )
        
        await interaction.response.edit_message(embed=embed, view=options_view)
    
    async def confirm_teams(self, interaction: discord.Interaction):
        """팀 구성 확정"""
        result = self.results[self.current_index]
        
        embed = discord.Embed(
            title="✅ 팀 구성 확정 완료!",
            description="선택된 팀 구성이 확정되었습니다.",
            color=0x00ff00
        )
        
        # 최종 팀 구성 요약
        team_a_summary = f"{result.team_a.tank.username}, {result.team_a.dps1.username}, {result.team_a.dps2.username}, {result.team_a.support1.username}, {result.team_a.support2.username}"
        team_b_summary = f"{result.team_b.tank.username}, {result.team_b.dps1.username}, {result.team_b.dps2.username}, {result.team_b.support1.username}, {result.team_b.support2.username}"
        
        embed.add_field(
            name="🔵 A팀",
            value=team_a_summary,
            inline=False
        )
        
        embed.add_field(
            name="🔴 B팀", 
            value=team_b_summary,
            inline=False
        )
        
        embed.add_field(
            name="📊 밸런스 정보",
            value=f"밸런스 점수: {result.balance_score:.2f}/1.00\nA팀 예상 승률: {result.predicted_winrate_a:.1%}",
            inline=False
        )
        
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    async def cancel(self, interaction: discord.Interaction):
        """취소"""
        embed = discord.Embed(
            title="❌ 팀 밸런싱 취소",
            description="팀 밸런싱이 취소되었습니다.",
            color=0xff4444
        )
        
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()