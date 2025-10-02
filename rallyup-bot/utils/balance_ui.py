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
        super().__init__(timeout=900)  # 15분 타임아웃 (포지션 설정 시간 고려)
        self.bot = bot
        self.guild_id = guild_id
        self.all_users = all_users
        self.interaction_user = None
        
        # 팀 구성
        self.team_a_players = []
        self.team_b_players = []
        
        # 포지션 배치 (핵심 추가!)
        self.team_a_positions = {}  # {user_id: position}
        self.team_b_positions = {}  # {user_id: position}
        
        # 현재 단계 추적
        self.current_step = "select_team_a"  # select_team_a -> select_team_b -> set_positions_a -> set_positions_b -> analyze
        self.current_team = "A"  # A팀 선택 중
        self.current_position_player = 0  # 포지션 설정 중인 플레이어 인덱스
        
        # 초기 UI 설정
        self.update_ui()
    
    def update_ui(self):
        """현재 단계에 따른 UI 업데이트"""
        self.clear_items()
        
        if self.current_step in ["select_team_a", "select_team_b"]:
            # 팀 선택 단계
            self.add_team_selection_ui()
        elif self.current_step in ["set_positions_a", "set_positions_b"]:
            # 포지션 설정 단계 - 별도 메서드에서 처리
            pass
        elif self.current_step == "analyze":
            # 분석 단계 - 별도 메서드에서 처리
            pass
    
    def add_team_selection_ui(self):
        """팀 선택 UI 구성 (기존 로직 유지)"""
        # 현재 선택 중인 팀에 따라 드롭다운 추가
        if self.current_step == "select_team_a" and len(self.team_a_players) < 5:
            self.add_team_selection_dropdown("A")
        elif self.current_step == "select_team_b" and len(self.team_b_players) < 5:
            self.add_team_selection_dropdown("B")
        
        # 컨트롤 버튼들 추가
        self.add_control_buttons()
    
    def add_team_selection_dropdown(self, team: str):
        """팀 선택 드롭다운 추가 (기존 로직)"""
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
        # A팀/B팀 전환 버튼 (팀 선택 단계에서만)
        if self.current_step == "select_team_a":
            if len(self.team_a_players) >= 5:
                # A팀 완료 -> B팀으로 진행
                next_button = discord.ui.Button(
                    label="B팀 선택하기",
                    style=discord.ButtonStyle.primary,
                    emoji="🔴"
                )
                next_button.callback = self.proceed_to_team_b
                self.add_item(next_button)
        
        elif self.current_step == "select_team_b":
            if len(self.team_b_players) >= 5:
                # B팀 완료 -> 포지션 설정으로 진행
                next_button = discord.ui.Button(
                    label="포지션 설정하기",
                    style=discord.ButtonStyle.success,
                    emoji="⚔️"
                )
                next_button.callback = self.proceed_to_position_setting
                self.add_item(next_button)
                
                # B팀 -> A팀으로 돌아가기
                back_button = discord.ui.Button(
                    label="A팀으로 돌아가기",
                    style=discord.ButtonStyle.secondary,
                    emoji="🔵"
                )
                back_button.callback = self.back_to_team_a
                self.add_item(back_button)
        
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
    
    async def proceed_to_team_b(self, interaction: discord.Interaction):
        """A팀 선택 완료 -> B팀 선택으로 진행"""
        self.current_step = "select_team_b"
        self.current_team = "B"
        self.update_ui()
        
        embed = self.create_team_status_embed()
        embed.add_field(
            name="📋 다음 단계",
            value="이제 B팀 5명을 선택해주세요.",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def back_to_team_a(self, interaction: discord.Interaction):
        """B팀 -> A팀 선택으로 돌아가기"""
        self.current_step = "select_team_a"
        self.current_team = "A"
        self.update_ui()
        
        embed = self.create_team_status_embed()
        embed.add_field(
            name="📋 수정 모드",
            value="A팀 구성을 수정할 수 있습니다.",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def proceed_to_position_setting(self, interaction: discord.Interaction):
        """팀 선택 완료 -> A팀 포지션 설정으로 진행"""
        self.current_step = "set_positions_a"
        
        # A팀 첫 번째 플레이어의 포지션 설정 시작
        await self.start_position_setting("team_a", interaction)
    
    async def start_position_setting(self, team: str, interaction: discord.Interaction):
        """포지션 설정 시작"""
        self.current_position_player = 0
        await self.show_single_player_position(team, interaction)
    
    async def show_single_player_position(self, team: str, interaction: discord.Interaction):
        """개별 플레이어 포지션 선택"""
        team_players = self.team_a_players if team == "team_a" else self.team_b_players
        current_player = team_players[self.current_position_player]
        team_name = "A팀" if team == "team_a" else "B팀"
        team_color = 0x0099ff if team == "team_a" else 0xff4444
        
        embed = discord.Embed(
            title=f"⚔️ {team_name} 포지션 설정",
            description=f"**{current_player['username']}**님의 포지션을 선택해주세요\n"
                       f"({self.current_position_player + 1}/5)",
            color=team_color
        )
        
        # 현재까지 설정된 포지션 표시
        current_positions = self.team_a_positions if team == "team_a" else self.team_b_positions
        if current_positions:
            pos_text = []
            for i, player in enumerate(team_players[:self.current_position_player]):
                position = current_positions.get(player['user_id'], '미설정')
                emoji = "🛡️" if position == "탱커" else "⚔️" if position == "딜러" else "💚" if position == "힐러" else "❓"
                pos_text.append(f"{emoji} {player['username']} - {position}")
            
            if pos_text:
                embed.add_field(
                    name="✅ 설정 완료",
                    value="\n".join(pos_text),
                    inline=False
                )
        
        # 플레이어 정보 표시
        embed.add_field(
            name="🎮 플레이어 정보",
            value=f"주포지션: {current_player.get('main_position', '미설정')}\n"
                  f"티어: {current_player.get('current_season_tier', '배치안함')}",
            inline=True
        )
        
        # 포지션 선택 드롭다운
        self.clear_items()
        
        position_select = discord.ui.Select(
            placeholder="포지션을 선택하세요",
            options=[
                discord.SelectOption(label="🛡️ 탱커", value="탱커", emoji="🛡️"),
                discord.SelectOption(label="⚔️ 딜러", value="딜러", emoji="⚔️"),
                discord.SelectOption(label="💚 힐러", value="힐러", emoji="💚")
            ]
        )
        position_select.callback = lambda i: self.position_selected(team, i)
        self.add_item(position_select)
        
        # 이전 플레이어로 돌아가기 (첫 번째 플레이어가 아닌 경우)
        if self.current_position_player > 0:
            back_button = discord.ui.Button(
                label="이전 플레이어",
                style=discord.ButtonStyle.secondary,
                emoji="⬅️"
            )
            back_button.callback = lambda i: self.previous_player(team, i)
            self.add_item(back_button)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def position_selected(self, team: str, interaction: discord.Interaction):
        """포지션 선택 처리"""
        selected_position = interaction.data['values'][0]
        team_players = self.team_a_players if team == "team_a" else self.team_b_players
        current_player = team_players[self.current_position_player]
        
        # 포지션 저장
        if team == "team_a":
            self.team_a_positions[current_player['user_id']] = selected_position
        else:
            self.team_b_positions[current_player['user_id']] = selected_position
        
        # 다음 플레이어로 진행
        self.current_position_player += 1
        
        if self.current_position_player >= 5:
            # 현재 팀 포지션 설정 완료
            if team == "team_a":
                # A팀 완료 -> B팀 포지션 설정으로
                self.current_step = "set_positions_b"
                await self.start_position_setting("team_b", interaction)
            else:
                # B팀 완료 -> 포지션 검증 후 분석으로
                await self.validate_and_analyze(interaction)
        else:
            # 같은 팀의 다음 플레이어
            await self.show_single_player_position(team, interaction)
    
    async def previous_player(self, team: str, interaction: discord.Interaction):
        """이전 플레이어로 돌아가기"""
        self.current_position_player -= 1
        await self.show_single_player_position(team, interaction)
    
    async def validate_and_analyze(self, interaction: discord.Interaction):
        """포지션 구성 검증 후 분석 실행"""
        # 팀 구성 검증
        a_team_valid = self.validate_team_composition(self.team_a_positions)
        b_team_valid = self.validate_team_composition(self.team_b_positions)
        
        if not a_team_valid or not b_team_valid:
            # 검증 실패 - 재설정 요청
            await self.show_composition_error(interaction, a_team_valid, b_team_valid)
        else:
            # 검증 성공 - 분석 실행
            await self.execute_analysis(interaction)
    
    def validate_team_composition(self, team_positions: Dict) -> bool:
        """팀 구성 검증: 탱1딜2힐2인지 확인"""
        position_count = {"탱커": 0, "딜러": 0, "힐러": 0}
        
        for position in team_positions.values():
            position_count[position] += 1
        
        return (position_count["탱커"] == 1 and 
                position_count["딜러"] == 2 and 
                position_count["힐러"] == 2)
    
    async def show_composition_error(self, interaction: discord.Interaction, 
                                   a_team_valid: bool, b_team_valid: bool):
        """구성 오류 표시 및 재설정 옵션 제공"""
        embed = discord.Embed(
            title="❌ 팀 구성 오류",
            description="올바른 팀 구성이 아닙니다. 각 팀은 **탱커 1명, 딜러 2명, 힐러 2명**이어야 합니다.",
            color=0xff4444
        )
        
        # 현재 구성 표시
        for team_name, positions, valid in [("A팀", self.team_a_positions, a_team_valid), 
                                          ("B팀", self.team_b_positions, b_team_valid)]:
            position_count = {"탱커": 0, "딜러": 0, "힐러": 0}
            for position in positions.values():
                position_count[position] += 1
            
            status_emoji = "✅" if valid else "❌"
            composition_text = f"🛡️ 탱커: {position_count['탱커']}명\n⚔️ 딜러: {position_count['딜러']}명\n💚 힐러: {position_count['힐러']}명"
            
            embed.add_field(
                name=f"{status_emoji} {team_name}",
                value=composition_text,
                inline=True
            )
        
        # 재설정 버튼들
        self.clear_items()
        
        if not a_team_valid:
            retry_a_button = discord.ui.Button(
                label="A팀 포지션 재설정",
                style=discord.ButtonStyle.primary,
                emoji="🔵"
            )
            retry_a_button.callback = self.retry_a_team_positions
            self.add_item(retry_a_button)
        
        if not b_team_valid:
            retry_b_button = discord.ui.Button(
                label="B팀 포지션 재설정", 
                style=discord.ButtonStyle.danger,
                emoji="🔴"
            )
            retry_b_button.callback = self.retry_b_team_positions
            self.add_item(retry_b_button)
        
        # 전체 재시작
        restart_button = discord.ui.Button(
            label="처음부터 다시",
            style=discord.ButtonStyle.secondary,
            emoji="🔄"
        )
        restart_button.callback = self.restart_from_beginning
        self.add_item(restart_button)
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def retry_a_team_positions(self, interaction: discord.Interaction):
        """A팀 포지션 재설정"""
        self.team_a_positions.clear()
        self.current_step = "set_positions_a"
        await self.start_position_setting("team_a", interaction)
    
    async def retry_b_team_positions(self, interaction: discord.Interaction):
        """B팀 포지션 재설정"""
        self.team_b_positions.clear()
        self.current_step = "set_positions_b"
        await self.start_position_setting("team_b", interaction)
    
    async def restart_from_beginning(self, interaction: discord.Interaction):
        """처음부터 다시 시작"""
        self.team_a_players.clear()
        self.team_b_players.clear()
        self.team_a_positions.clear()
        self.team_b_positions.clear()
        self.current_step = "select_team_a"
        self.current_team = "A"
        self.update_ui()
        
        embed = self.create_team_status_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def execute_analysis(self, interaction: discord.Interaction):
        """밸런스 분석 실행"""
        await interaction.response.defer()
        
        try:
            from utils.balance_algorithm import TeamBalancer, BalancingMode
            
            # 로딩 메시지
            embed = discord.Embed(
                title="⏳ 팀 밸런스 분석 중...",
                description="지정된 포지션 기준으로 정밀 분석 진행 중입니다.",
                color=0xffaa00
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            # 밸런스 분석 실행 (포지션 고정)
            balancer = TeamBalancer(mode=BalancingMode.PRECISE)
            result = await asyncio.get_event_loop().run_in_executor(
                None, balancer.analyze_fixed_team_composition, 
                self.team_a_players, self.team_a_positions,
                self.team_b_players, self.team_b_positions
            )
            
            # 결과 표시
            result_view = BalanceCheckResultView(
                self.bot, result, self.team_a_players, self.team_b_players, 
                self.all_users, self.team_a_positions, self.team_b_positions
            )
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
        self.team_a_players.clear()
        self.team_b_players.clear()
        self.team_a_positions.clear()
        self.team_b_positions.clear()
        self.current_step = "select_team_a"
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
        if self.current_step.startswith("select"):
            title = "🔍 팀 밸런스 체크 - 팀 구성"
        elif self.current_step.startswith("set_positions"):
            title = "⚔️ 팀 밸런스 체크 - 포지션 설정"
        else:
            title = "📊 팀 밸런스 체크"
            
        embed = discord.Embed(title=title, color=0x9966ff)
        
        # A팀 정보
        if self.team_a_players:
            team_a_text = []
            for player in self.team_a_players:
                position = self.team_a_positions.get(player['user_id'])
                if position:
                    emoji = "🛡️" if position == "탱커" else "⚔️" if position == "딜러" else "💚"
                    team_a_text.append(f"{emoji} {player['username']} ({position})")
                else:
                    team_a_text.append(f"• {player['username']} ({player.get('main_position', '미설정')})")
            team_a_display = "\n".join(team_a_text)
        else:
            team_a_display = "아직 선택된 플레이어가 없습니다."
        
        embed.add_field(
            name=f"🔵 A팀 ({len(self.team_a_players)}/5)",
            value=team_a_display,
            inline=True
        )
        
        # B팀 정보
        if self.team_b_players:
            team_b_text = []
            for player in self.team_b_players:
                position = self.team_b_positions.get(player['user_id'])
                if position:
                    emoji = "🛡️" if position == "탱커" else "⚔️" if position == "딜러" else "💚"
                    team_b_text.append(f"{emoji} {player['username']} ({position})")
                else:
                    team_b_text.append(f"• {player['username']} ({player.get('main_position', '미설정')})")
            team_b_display = "\n".join(team_b_text)
        else:
            team_b_display = "아직 선택된 플레이어가 없습니다."
        
        embed.add_field(
            name=f"🔴 B팀 ({len(self.team_b_players)}/5)",
            value=team_b_display,
            inline=True
        )
        
        # 진행 상태
        step_descriptions = {
            "select_team_a": "🔵 A팀 5명을 선택해주세요.",
            "select_team_b": "🔴 B팀 5명을 선택해주세요.",
            "set_positions_a": "⚔️ A팀 포지션을 설정 중입니다.",
            "set_positions_b": "⚔️ B팀 포지션을 설정 중입니다.",
            "analyze": "📊 밸런스 분석을 실행합니다."
        }
        
        embed.add_field(
            name="📋 진행 상태",
            value=step_descriptions.get(self.current_step, "진행 중..."),
            inline=False
        )
        
        # 분석 정보
        embed.add_field(
            name="🎯 분석 방식",
            value="• 지정된 포지션 기준 분석\n• 내전 데이터 + 티어 정보 활용\n• 실제 팀 구성의 정확한 밸런스 측정",
            inline=False
        )
        
        return embed

class TeamPlayerSelectDropdown(discord.ui.Select):    
    def __init__(self, team: str, **kwargs):
        super().__init__(**kwargs)
        self.team = team
        self.parent_view = None
    
    async def callback(self, interaction: discord.Interaction):
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
        
        self.parent_view.update_ui()
        
        embed = self.parent_view.create_team_status_embed()
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
        
class BalanceCheckResultView(discord.ui.View):
    """밸런스 체크 결과 표시 View (포지션 정보 포함)"""
    
    def __init__(self, bot, result, team_a_players, team_b_players, all_users, 
                 team_a_positions=None, team_b_positions=None):
        super().__init__(timeout=600)
        self.bot = bot
        self.result = result
        self.original_team_a = team_a_players
        self.original_team_b = team_b_players
        self.all_users = all_users
        self.team_a_positions = team_a_positions or {}
        self.team_b_positions = team_b_positions or {}
        
        # 버튼 추가
        self.add_result_buttons()
    
    def add_result_buttons(self):
        """결과 화면 버튼들 추가"""
        # 팀 구성 수정 버튼
        edit_button = discord.ui.Button(
            label="팀 구성 수정",
            style=discord.ButtonStyle.secondary,
            emoji="✏️"
        )
        edit_button.callback = self.edit_teams
        self.add_item(edit_button)
        
        # 새로운 분석 버튼
        new_analysis_button = discord.ui.Button(
            label="새로운 분석",
            style=discord.ButtonStyle.primary,
            emoji="🔄"
        )
        new_analysis_button.callback = self.new_analysis
        self.add_item(new_analysis_button)
        
        # 개선 제안 버튼 (밸런스 점수가 낮은 경우)
        if self.result.balance_score < 0.8:
            suggestion_button = discord.ui.Button(
                label="개선 제안 보기",
                style=discord.ButtonStyle.success,
                emoji="💡"
            )
            suggestion_button.callback = self.show_suggestions
            self.add_item(suggestion_button)
    
    def create_balance_check_embed(self, result) -> discord.Embed:
        """밸런스 체크 결과 임베드 생성 (포지션 정보 포함)"""
        # 밸런스 점수에 따른 색상 결정
        if result.balance_score >= 0.8:
            color = 0x00ff00  # 초록 (좋음)
        elif result.balance_score >= 0.6:
            color = 0xffaa00  # 주황 (보통)
        else:
            color = 0xff4444  # 빨강 (나쁨)
        
        embed = discord.Embed(
            title="📊 팀 밸런스 분석 결과",
            color=color
        )
        
        # A팀 구성 (포지션 포함)
        team_a_text = self.format_team_with_positions(
            self.original_team_a, self.team_a_positions, result.team_a
        )
        embed.add_field(
            name="🔵 A팀",
            value=team_a_text,
            inline=True
        )
        
        # B팀 구성 (포지션 포함)
        team_b_text = self.format_team_with_positions(
            self.original_team_b, self.team_b_positions, result.team_b
        )
        embed.add_field(
            name="🔴 B팀",
            value=team_b_text,
            inline=True
        )
        
        # 빈 필드 (레이아웃 조정)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        # 밸런스 점수
        balance_emoji = "🟢" if result.balance_score >= 0.8 else "🟡" if result.balance_score >= 0.6 else "🔴"
        winrate_text = f"A팀 {result.predicted_winrate_a:.1%} vs B팀 {1-result.predicted_winrate_a:.1%}"
        
        embed.add_field(
            name="⚖️ 밸런스 점수",
            value=f"{balance_emoji} **{result.balance_score:.1%}** (최대 100%)\n"
                  f"📈 예상 승률: {winrate_text}",
            inline=False
        )
        
        # 포지션별 분석
        if result.reasoning:
            reasoning_text = ""
            if 'tank' in result.reasoning:
                reasoning_text += f"🛡️ **탱커**: {result.reasoning['tank']}\n"
            if 'dps' in result.reasoning:
                reasoning_text += f"⚔️ **딜러**: {result.reasoning['dps']}\n"
            if 'support' in result.reasoning:
                reasoning_text += f"💚 **힐러**: {result.reasoning['support']}\n"
            
            if reasoning_text:
                embed.add_field(
                    name="🔍 포지션별 분석",
                    value=reasoning_text,
                    inline=False
                )
        
        # 포지션 적합도
        if 'position_fit' in result.reasoning:
            embed.add_field(
                name="🎯 포지션 적합도",
                value=result.reasoning['position_fit'],
                inline=False
            )
        
        # 종합 평가
        if 'overall' in result.reasoning:
            embed.add_field(
                name="📝 종합 평가",
                value=result.reasoning['overall'],
                inline=False
            )
        
        # 분석 정보
        embed.add_field(
            name="📋 분석 방식",
            value="• 지정된 포지션 기준 정밀 분석\n"
                  "• 경험 많은 유저: 실제 내전 데이터 기반\n"
                  "• 신규 유저: 오버워치 티어 + 부분 데이터 활용\n"
                  "• 포지션 적합도 및 숙련도 종합 평가",
            inline=False
        )
        
        # 개선 여지가 있는 경우 힌트 제공
        if result.balance_score < 0.8:
            embed.add_field(
                name="💡 개선 힌트",
                value="'개선 제안 보기' 버튼을 클릭하면 더 균형잡힌 팀 구성 방법을 확인할 수 있습니다.",
                inline=False
            )
        
        embed.set_footer(
            text="🤖 RallyUp Bot 팀 밸런스 분석 시스템"
        )
        
        return embed
    
    def format_team_with_positions(self, team_players, team_positions, team_composition) -> str:
        """팀 구성을 포지션과 함께 포맷팅"""
        if not team_positions:
            # 포지션 정보가 없는 경우 (기존 방식)
            return "\n".join([
                f"• {p['username']} ({p.get('main_position', '미설정')})"
                for p in team_players
            ])
        
        # 포지션별로 정렬하여 표시
        position_order = ["탱커", "딜러", "힐러"]
        formatted_text = []
        
        for position in position_order:
            players_in_position = []
            for player in team_players:
                if team_positions.get(player['user_id']) == position:
                    # 해당 포지션 스킬 점수 표시
                    skill_score = self.get_player_position_skill(player, position, team_composition)
                    emoji = "🛡️" if position == "탱커" else "⚔️" if position == "딜러" else "💚"
                    
                    # 주포지션 일치 여부 표시
                    main_pos_match = "★" if player.get('main_position') == position else ""
                    
                    players_in_position.append(
                        f"{emoji} {player['username']}{main_pos_match} ({skill_score:.2f})"
                    )
            
            formatted_text.extend(players_in_position)
        
        return "\n".join(formatted_text) if formatted_text else "팀 구성 정보를 찾을 수 없습니다."
    
    def get_player_position_skill(self, player_dict, position, team_composition) -> float:
        """플레이어의 특정 포지션 스킬 점수 조회"""
        # team_composition에서 해당 플레이어 찾기
        player_id = player_dict['user_id']
        
        # TeamComposition에서 해당 플레이어의 스킬 데이터 찾기
        all_players_in_comp = [
            team_composition.tank, team_composition.dps1, team_composition.dps2,
            team_composition.support1, team_composition.support2
        ]
        
        for player_skill_data in all_players_in_comp:
            if player_skill_data.user_id == player_id:
                if position == "탱커":
                    return player_skill_data.tank_skill
                elif position == "딜러":
                    return player_skill_data.dps_skill
                elif position == "힐러":
                    return player_skill_data.support_skill
        
        return 0.5  # 기본값
    
    async def edit_teams(self, interaction: discord.Interaction):
        """팀 구성 수정"""
        manual_view = ManualTeamSelectionView(self.bot, interaction.guild_id, self.all_users)
        manual_view.team_a_players = self.original_team_a.copy()
        manual_view.team_b_players = self.original_team_b.copy()
        manual_view.team_a_positions = self.team_a_positions.copy()
        manual_view.team_b_positions = self.team_b_positions.copy()
        manual_view.current_step = "select_team_a"
        manual_view.interaction_user = interaction.user
        manual_view.update_ui()
        
        embed = manual_view.create_team_status_embed()
        embed.add_field(
            name="🔄 수정 모드",
            value="기존 팀 구성을 불러왔습니다. 원하는 플레이어나 포지션을 변경해보세요.",
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
        """개선된 팀 구성 제안 (실제 대안 구성 제시)"""
        await interaction.response.defer()
        
        try:
            # AI가 더 나은 팀 구성을 찾기
            improved_compositions = await self.find_improved_compositions()
            
            if not improved_compositions:
                # 개선안을 찾지 못한 경우
                embed = discord.Embed(
                    title="✅ 이미 최적화된 구성",
                    description="현재 팀 구성이 이미 상당히 균형잡혀 있습니다!",
                    color=0x00aa44
                )
                embed.add_field(
                    name="🎯 현재 밸런스 점수",
                    value=f"**{self.result.balance_score:.1%}** - 양호한 수준",
                    inline=False
                )
                embed.add_field(
                    name="💡 추가 제안",
                    value="• 다른 플레이어 조합을 시도해보세요\n• 포지션 변경으로 미세 조정 가능\n• 현재 구성으로도 재미있는 경기 예상",
                    inline=False
                )
            else:
                # 개선안을 찾은 경우
                best_improvement = improved_compositions[0]
                embed = self.create_improvement_comparison_embed(best_improvement)
            
            # 뒤로가기 버튼 (수정된 버전)
            back_button = discord.ui.Button(
                label="분석 결과로 돌아가기",
                style=discord.ButtonStyle.secondary,
                emoji="⬅️"
            )
            back_button.callback = self.back_to_results_fixed
            
            view = discord.ui.View(timeout=600)
            view.add_item(back_button)
            
            # 개선안이 있으면 적용 버튼도 추가
            if improved_compositions:
                apply_button = discord.ui.Button(
                    label="이 구성 적용하기",
                    style=discord.ButtonStyle.success,
                    emoji="✅"
                )
                apply_button.callback = lambda i: self.apply_improved_composition(i, best_improvement)
                view.add_item(apply_button)
            
            await interaction.edit_original_response(embed=embed, view=view)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 개선안 생성 실패",
                description=f"개선된 팀 구성을 생성하는 중 오류가 발생했습니다:\n```{str(e)}```",
                color=0xff4444
            )
            await interaction.edit_original_response(embed=embed, view=None)

    async def find_improved_compositions(self) -> List[Dict]:
        """더 나은 팀 구성 찾기"""
        import itertools
        from utils.balance_algorithm import TeamBalancer, BalancingMode
        
        current_score = self.result.balance_score
        improvements = []
        
        # 현재 구성에서 가능한 개선안들 시도
        all_players = self.original_team_a + self.original_team_b
        balancer = TeamBalancer(mode=BalancingMode.PRECISE)
        
        # 1. 플레이어 교체 시나리오 (각 팀에서 1-2명씩 교체)
        improvement_attempts = 0
        max_attempts = 20  # 성능을 위해 시도 횟수 제한
        
        for swap_count in [1, 2]:  # 1명 또는 2명씩 교체
            if improvement_attempts >= max_attempts:
                break
                
            # A팀에서 swap_count명 선택
            for a_players_to_swap in itertools.combinations(range(5), swap_count):
                if improvement_attempts >= max_attempts:
                    break
                    
                # B팀에서 swap_count명 선택  
                for b_players_to_swap in itertools.combinations(range(5), swap_count):
                    improvement_attempts += 1
                    if improvement_attempts >= max_attempts:
                        break
                    
                    # 새로운 팀 구성 생성
                    new_team_a = self.original_team_a.copy()
                    new_team_b = self.original_team_b.copy()
                    new_a_positions = self.team_a_positions.copy()
                    new_b_positions = self.team_b_positions.copy()
                    
                    # 플레이어 교체
                    for i, j in zip(a_players_to_swap, b_players_to_swap):
                        # 플레이어 교체
                        a_player = new_team_a[i]
                        b_player = new_team_b[j]
                        
                        new_team_a[i] = b_player
                        new_team_b[j] = a_player
                        
                        # 포지션도 함께 교체
                        a_pos = new_a_positions.get(a_player['user_id'])
                        b_pos = new_b_positions.get(b_player['user_id'])
                        
                        if a_pos and b_pos:
                            new_a_positions[b_player['user_id']] = a_pos
                            new_b_positions[a_player['user_id']] = b_pos
                            del new_a_positions[a_player['user_id']]
                            del new_b_positions[b_player['user_id']]
                    
                    try:
                        # 새 구성 분석
                        new_result = await asyncio.get_event_loop().run_in_executor(
                            None, balancer.analyze_fixed_team_composition,
                            new_team_a, new_a_positions, new_team_b, new_b_positions
                        )
                        
                        # 개선되었는지 확인
                        if new_result.balance_score > current_score + 0.05:  # 최소 5% 개선
                            improvements.append({
                                'team_a': new_team_a,
                                'team_b': new_team_b,
                                'team_a_positions': new_a_positions,
                                'team_b_positions': new_b_positions,
                                'result': new_result,
                                'improvement': new_result.balance_score - current_score,
                                'swapped_players': [(self.original_team_a[i]['username'], self.original_team_b[j]['username']) 
                                                for i, j in zip(a_players_to_swap, b_players_to_swap)]
                            })
                    except:
                        continue  # 유효하지 않은 구성이면 스킵
        
        # 개선도가 높은 순으로 정렬
        improvements.sort(key=lambda x: x['improvement'], reverse=True)
        return improvements[:3]  # 상위 3개만 반환

    def create_improvement_comparison_embed(self, improvement: Dict) -> discord.Embed:
        """개선 구성 비교 임베드 생성"""
        embed = discord.Embed(
            title="🚀 개선된 팀 구성 제안",
            description="AI가 분석한 더 균형잡힌 팀 구성입니다.",
            color=0x00aa44
        )
        
        # 개선 요약
        improvement_score = improvement['improvement']
        new_score = improvement['result'].balance_score
        
        embed.add_field(
            name="📊 개선 효과",
            value=f"**현재**: {self.result.balance_score:.1%} → **개선**: {new_score:.1%}\n"
                f"**향상도**: +{improvement_score:.1%} ⬆️",
            inline=False
        )
        
        # 변경 사항
        swapped_players = improvement['swapped_players']
        change_text = "\n".join([f"🔄 {a_player} ↔ {b_player}" for a_player, b_player in swapped_players])
        
        embed.add_field(
            name="🔄 주요 변경사항",
            value=change_text,
            inline=False
        )
        
        # 현재 구성
        embed.add_field(
            name="📋 현재 구성",
            value=self.format_team_comparison(
                self.original_team_a, self.team_a_positions, "A팀",
                self.original_team_b, self.team_b_positions, "B팀"
            ),
            inline=False
        )
        
        # 제안 구성
        embed.add_field(
            name="✨ 제안 구성",
            value=self.format_team_comparison(
                improvement['team_a'], improvement['team_a_positions'], "A팀",
                improvement['team_b'], improvement['team_b_positions'], "B팀"
            ),
            inline=False
        )
        
        # 새로운 밸런스 분석
        new_result = improvement['result']
        winrate_text = f"A팀 {new_result.predicted_winrate_a:.1%} vs B팀 {1-new_result.predicted_winrate_a:.1%}"
        
        embed.add_field(
            name="⚖️ 새로운 밸런스",
            value=f"🎯 밸런스 점수: **{new_result.balance_score:.1%}**\n"
                f"📈 예상 승률: {winrate_text}",
            inline=False
        )
        
        embed.set_footer(text="'이 구성 적용하기' 버튼으로 바로 적용할 수 있습니다.")
        
        return embed

    def format_team_comparison(self, team_a, a_positions, a_name, team_b, b_positions, b_name) -> str:
        """팀 구성 비교용 포맷팅"""
        def format_single_team(team_players, positions, team_name):
            lines = [f"**{team_name}**:"]
            for player in team_players:
                position = positions.get(player['user_id'], '미설정')
                emoji = "🛡️" if position == "탱커" else "⚔️" if position == "딜러" else "💚" if position == "힐러" else "❓"
                lines.append(f"{emoji} {player['username']}")
            return "\n".join(lines)
        
        team_a_text = format_single_team(team_a, a_positions, a_name)
        team_b_text = format_single_team(team_b, b_positions, b_name)
        
        return f"{team_a_text}\n\n{team_b_text}"

    async def apply_improved_composition(self, interaction: discord.Interaction, improvement: Dict):
        """개선된 구성 적용"""
        # 새로운 구성으로 업데이트
        self.original_team_a = improvement['team_a']
        self.original_team_b = improvement['team_b'] 
        self.team_a_positions = improvement['team_a_positions']
        self.team_b_positions = improvement['team_b_positions']
        self.result = improvement['result']
        
        # 결과 화면으로 돌아가기
        embed = self.create_balance_check_embed(self.result)
        embed.add_field(
            name="✅ 구성 적용 완료",
            value="개선된 팀 구성이 적용되었습니다!",
            inline=False
        )
        
        # 원래 결과 버튼들로 되돌리기
        self.clear_items()
        self.add_result_buttons()
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_to_results_fixed(self, interaction: discord.Interaction):
        """분석 결과로 돌아가기 (수정된 버전)"""
        embed = self.create_balance_check_embed(self.result)
        
        # 원래 버튼들 복원
        self.clear_items()
        self.add_result_buttons()
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    def find_position_mismatches(self) -> List[str]:
        """포지션 미스매치 찾기"""
        mismatches = []
        
        # A팀과 B팀의 포지션 적합도 비교
        for team_name, team_players, team_positions in [
            ("A팀", self.original_team_a, self.team_a_positions),
            ("B팀", self.original_team_b, self.team_b_positions)
        ]:
            for player in team_players:
                assigned_pos = team_positions.get(player['user_id'])
                main_pos = player.get('main_position')
                
                if assigned_pos and main_pos and assigned_pos != main_pos:
                    mismatches.append(
                        f"🔄 {team_name} {player['username']}님은 {main_pos} 전문이지만 {assigned_pos}에 배치됨"
                    )
        
        return mismatches
    
    async def back_to_results(self, interaction: discord.Interaction):
        """분석 결과로 돌아가기"""
        embed = self.create_balance_check_embed(self.result)
        await interaction.response.edit_message(embed=embed, view=self)

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