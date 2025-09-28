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
                description=f"선택된 모드: {self.selected_mode.value}\n잠시만 기다려주세요.",
                color=0xffaa00
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            # 밸런싱 실행
            balancer = TeamBalancer(mode=self.selected_mode)
            results = await asyncio.get_event_loop().run_in_executor(
                None, balancer.find_optimal_balance, self.selected_players
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
        embed = discord.Embed(
            title="🎯 팀 밸런싱 결과",
            color=0x00ff00 if result.balance_score >= 0.8 else 0xffaa00 if result.balance_score >= 0.6 else 0xff4444
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
        
        # 밸런싱 분석
        balance_emoji = "🟢" if result.balance_score >= 0.8 else "🟡" if result.balance_score >= 0.6 else "🔴"
        analysis_text = (
            f"{balance_emoji} **밸런스 점수**: {result.balance_score:.2f}/1.00\n"
            f"📊 **스킬 차이**: {result.skill_difference:.3f}\n"
            f"💡 **평가**: {result.reasoning.get('balance', '분석 중')}"
        )
        
        embed.add_field(
            name="📈 밸런싱 분석",
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