import discord
from discord.ui import View, Button, Select
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class GameReadyView(View):
    """
    게임 준비 완료 상태의 영구 View
    - timeout=None으로 영구 유지
    - 결과 기록 버튼 제공
    """
    
    def __init__(self, session_id: str):
        super().__init__(timeout=None)  # 영구 유지
        self.session_id = session_id
        
        # 결과 기록 버튼 추가
        record_button = Button(
            label="결과 기록하기",
            style=discord.ButtonStyle.success,
            emoji="🎯",
            custom_id=f"record_result_{session_id}"
        )
        record_button.callback = self.record_result_callback
        self.add_item(record_button)
        
        # 세션 취소 버튼 추가
        cancel_button = Button(
            label="세션 취소",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            custom_id=f"cancel_session_{session_id}"
        )
        cancel_button.callback = self.cancel_session_callback
        self.add_item(cancel_button)
    
    async def record_result_callback(self, interaction: discord.Interaction):
        """결과 기록 버튼 클릭 시 - 승리팀 선택 모달"""
        from utils.balancing_session_manager import session_manager
        
        # 세션 조회
        session = session_manager.get_session(self.session_id)
        
        if not session:
            await interaction.response.send_message(
                "❌ 세션이 만료되었거나 존재하지 않습니다.\n"
                "세션 유효 시간: 2시간",
                ephemeral=True
            )
            return
        
        if not session.is_valid():
            await interaction.response.send_message(
                f"❌ 이 세션은 더 이상 유효하지 않습니다.\n"
                f"현재 상태: {session.status}",
                ephemeral=True
            )
            return
        
        # 승리팀 선택 View로 전환
        winner_view = WinnerSelectionView(self.session_id, session)
        
        embed = discord.Embed(
            title="🏆 승리팀 선택",
            description="게임 결과를 입력해주세요.",
            color=0x00ff88
        )
        
        # 팀 구성 표시
        team_a_text = "\n".join([
            f"{i+1}. {p['username']} ({session.team_a_positions.get(p['user_id'], '미설정')})"
            for i, p in enumerate(session.team_a)
        ])
        team_b_text = "\n".join([
            f"{i+1}. {p['username']} ({session.team_b_positions.get(p['user_id'], '미설정')})"
            for i, p in enumerate(session.team_b)
        ])
        
        embed.add_field(
            name="🔵 A팀",
            value=team_a_text,
            inline=True
        )
        embed.add_field(
            name="🔴 B팀",
            value=team_b_text,
            inline=True
        )
        
        embed.set_footer(
            text=f"세션 ID: {self.session_id[:8]}... | 요청자: {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.send_message(
            embed=embed,
            view=winner_view,
            ephemeral=True
        )
    
    async def cancel_session_callback(self, interaction: discord.Interaction):
        """세션 취소"""
        from utils.balancing_session_manager import session_manager
        
        session = session_manager.get_session(self.session_id)
        
        if not session:
            await interaction.response.send_message(
                "❌ 세션을 찾을 수 없습니다.",
                ephemeral=True
            )
            return
        
        # 권한 확인 (세션 생성자 또는 관리자)
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        is_creator = session.created_by == user_id
        is_admin = interaction.user.guild_permissions.manage_guild
        
        if not (is_creator or is_admin):
            await interaction.response.send_message(
                "❌ 세션을 취소할 권한이 없습니다.\n"
                "세션 생성자 또는 관리자만 취소할 수 있습니다.",
                ephemeral=True
            )
            return
        
        # 세션 취소
        session_manager.cancel_session(self.session_id)
        
        # 원본 메시지 비활성화
        try:
            # 버튼 비활성화
            for item in self.children:
                item.disabled = True
            
            # 임베드 수정
            if interaction.message:
                embed = interaction.message.embeds[0] if interaction.message.embeds else None
                if embed:
                    embed.color = 0x888888
                    embed.title = embed.title + " [취소됨]"
                    await interaction.message.edit(embed=embed, view=self)
        except:
            pass
        
        await interaction.response.send_message(
            "✅ 세션이 취소되었습니다.",
            ephemeral=True
        )


class WinnerSelectionView(View):
    """승리팀 선택 View"""
    
    def __init__(self, session_id: str, session):
        super().__init__(timeout=300)  # 5분
        self.session_id = session_id
        self.session = session
        self.winner = None
        
        # 승리팀 선택 Select
        winner_select = Select(
            placeholder="승리팀을 선택하세요",
            options=[
                discord.SelectOption(
                    label="🔵 A팀 승리",
                    value="team_a",
                    emoji="🔵",
                    description="A팀이 승리했습니다"
                ),
                discord.SelectOption(
                    label="🔴 B팀 승리",
                    value="team_b",
                    emoji="🔴",
                    description="B팀이 승리했습니다"
                )
            ]
        )
        winner_select.callback = self.winner_select_callback
        self.add_item(winner_select)
    
    async def winner_select_callback(self, interaction: discord.Interaction):
        """승리팀 선택 처리"""
        self.winner = interaction.data['values'][0]
        
        # 맵 선택으로 이동
        map_view = MapSelectionView(self.session_id, self.session, self.winner)
        
        winner_text = "🔵 A팀" if self.winner == "team_a" else "🔴 B팀"
        
        embed = discord.Embed(
            title="🗺️ 맵 선택 (선택사항)",
            description=f"**{winner_text}** 승리로 선택되었습니다.\n\n"
                       "플레이한 맵을 선택하시거나 건너뛰기를 눌러주세요.",
            color=0x0099ff if self.winner == "team_a" else 0xff4444
        )
        
        embed.add_field(
            name="💡 안내",
            value="• 맵 정보는 선택사항입니다\n"
                  "• 건너뛰기를 선택하면 바로 저장됩니다",
            inline=False
        )
        
        await interaction.response.edit_message(
            embed=embed,
            view=map_view
        )


class MapSelectionView(View):
    """맵 선택 View (기존 scrim_result_recording.py의 로직 참고)"""
    
    def __init__(self, session_id: str, session, winner: str):
        super().__init__(timeout=300)
        self.session_id = session_id
        self.session = session
        self.winner = winner
        self.selected_map_type = None
        self.selected_map_name = None
        
        # 맵 타입 선택
        map_type_select = Select(
            placeholder="맵 타입을 선택하세요",
            options=[
                discord.SelectOption(label="호위", value="호위", emoji="🚚"),
                discord.SelectOption(label="밀기", value="밀기", emoji="⬆️"),
                discord.SelectOption(label="혼합", value="혼합", emoji="🔄"),
                discord.SelectOption(label="쟁탈", value="쟁탈", emoji="⭕"),
                discord.SelectOption(label="플래시포인트", value="플래시포인트", emoji="⚡"),
                discord.SelectOption(label="격돌", value="격돌", emoji="⚔️"),
                discord.SelectOption(label="점령", value="점령", emoji="🏴"),
            ]
        )
        map_type_select.callback = self.map_type_callback
        self.add_item(map_type_select)
        
        # 건너뛰기 버튼
        skip_button = Button(
            label="맵 선택 건너뛰기",
            style=discord.ButtonStyle.secondary,
            emoji="⏭️"
        )
        skip_button.callback = self.skip_map_callback
        self.add_item(skip_button)
    
    async def map_type_callback(self, interaction: discord.Interaction):
        """맵 타입 선택 시"""
        from commands.scrim_result_recording import OVERWATCH_MAPS
        
        self.selected_map_type = interaction.data['values'][0]
        maps = OVERWATCH_MAPS.get(self.selected_map_type, [])
        
        # 맵 이름 선택 View로 전환
        self.clear_items()
        
        map_name_select = Select(
            placeholder=f"{self.selected_map_type} 맵을 선택하세요",
            options=[
                discord.SelectOption(label=map_name, value=map_name)
                for map_name in maps[:25]  # Discord 제한
            ]
        )
        map_name_select.callback = self.map_name_callback
        self.add_item(map_name_select)
        
        # 뒤로가기
        back_button = Button(label="뒤로가기", style=discord.ButtonStyle.secondary)
        back_button.callback = self.back_callback
        self.add_item(back_button)
        
        await interaction.response.edit_message(view=self)
    
    async def map_name_callback(self, interaction: discord.Interaction):
        """맵 이름 선택 시 - 최종 저장"""
        self.selected_map_name = interaction.data['values'][0]
        await self.save_result(interaction)
    
    async def skip_map_callback(self, interaction: discord.Interaction):
        """맵 선택 건너뛰기 - 최종 저장"""
        await self.save_result(interaction)
    
    async def back_callback(self, interaction: discord.Interaction):
        """뒤로가기"""
        self.__init__(self.session_id, self.session, self.winner)
        await interaction.response.edit_message(view=self)
    
    async def save_result(self, interaction: discord.Interaction):
        """결과 저장 및 DB 반영"""
        from utils.balancing_session_manager import session_manager
        
        await interaction.response.defer()
        
        try:
            bot = interaction.client
            guild_id = str(interaction.guild_id)
            
            # 매치 데이터 구성
            match_data = {
                'guild_id': guild_id,
                'team_a': self.session.team_a,
                'team_b': self.session.team_b,
                'team_a_positions': self.session.team_a_positions,
                'team_b_positions': self.session.team_b_positions,
                'winner': self.winner,
                'map_type': self.selected_map_type,
                'map_name': self.selected_map_name,
                'balancing_mode': self.session.balancing_mode,
                'session_id': self.session_id
            }
            
            # DB에 저장
            await self.save_to_database(bot, match_data)
            
            # 세션을 완료가 아닌 재경기 대기 상태로 변경
            session_manager.mark_waiting_rematch(self.session_id)

            # 완료 메시지
            winner_text = "🔵 A팀" if self.winner == "team_a" else "🔴 B팀"
            map_text = f" ({self.selected_map_type}: {self.selected_map_name})" if self.selected_map_name else ""
            
            embed = discord.Embed(
                title="✅ 경기 결과 저장 완료!",
                description=f"**{winner_text}** 승리{map_text}",
                color=0x00ff88
            )
            
            embed.add_field(
                name="📊 업데이트 내용",
                value="✅ 개인 승률 업데이트\n"
                      "✅ 포지션별 통계 업데이트\n"
                      "✅ 매치업 기록 저장\n"
                      "✅ 서버 랭킹 갱신",
                inline=False
            )
            
            embed.add_field(
                name="🔍 확인 방법",
                value="`/내정보` - 개인 통계 확인\n"
                      "`/순위표` - 서버 랭킹 확인",
                inline=False
            )
            
            embed.set_footer(
                text=f"세션 ID: {self.session_id[:8]}...",
                icon_url=interaction.user.display_avatar.url
            )
            
            continue_view = ContinueMatchView(
                self.session_id,
                self.session,
                guild_id
            )
            
            await interaction.followup.send(
                embed=embed,
                view=continue_view
            )
            
        except Exception as e:
            logger.error(f"결과 저장 중 오류: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ 결과 저장 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    async def save_to_database(self, bot, match_data: dict):
        """DB에 경기 결과 저장 (scrim_result_recording 로직 재사용)"""
        guild_id = match_data['guild_id']
        
        # 승리팀과 패배팀 구분
        if match_data['winner'] == 'team_a':
            winning_team = match_data['team_a']
            losing_team = match_data['team_b']
            winning_positions = match_data['team_a_positions']
            losing_positions = match_data['team_b_positions']
        else:
            winning_team = match_data['team_b']
            losing_team = match_data['team_a']
            winning_positions = match_data['team_b_positions']
            losing_positions = match_data['team_a_positions']
        
        # 각 플레이어의 결과 저장
        for player in winning_team:
            user_id = player['user_id']
            position = winning_positions.get(user_id, '미설정')
            
            await bot.db_manager.record_scrim_result(
                guild_id=guild_id,
                user_id=user_id,
                position=position,
                result='win',
                map_type=match_data.get('map_type'),
                map_name=match_data.get('map_name')
            )
        
        for player in losing_team:
            user_id = player['user_id']
            position = losing_positions.get(user_id, '미설정')
            
            await bot.db_manager.record_scrim_result(
                guild_id=guild_id,
                user_id=user_id,
                position=position,
                result='loss',
                map_type=match_data.get('map_type'),
                map_name=match_data.get('map_name')
            )
        
        logger.info(f"경기 결과 저장 완료 (세션: {match_data['session_id'][:8]})")

# game_ready_view.py 파일 맨 끝에 추가

class ContinueMatchView(View):
    """경기 결과 저장 완료 후 연속 경기를 위한 View"""
    
    def __init__(self, session_id: str, session, guild_id: str):
        super().__init__(timeout=None)  # 영구 유지
        self.session_id = session_id
        self.session = session
        self.guild_id = guild_id
        
        # 동일 멤버로 재밸런싱 버튼
        same_members_button = Button(
            label="동일 멤버로 재밸런싱",
            style=discord.ButtonStyle.primary,
            emoji="🔄",
            custom_id=f"rematch_same_{session_id}"
        )
        same_members_button.callback = self.rematch_same_members
        self.add_item(same_members_button)
        
        # 멤버 변경 후 재밸런싱 버튼
        change_members_button = Button(
            label="멤버 변경 후 재밸런싱",
            style=discord.ButtonStyle.secondary,
            emoji="👥",
            custom_id=f"rematch_change_{session_id}"
        )
        change_members_button.callback = self.rematch_change_members
        self.add_item(change_members_button)
    
    async def rematch_same_members(self, interaction: discord.Interaction):
        """동일 멤버로 재밸런싱"""
        from utils.balancing_session_manager import session_manager
        from utils.balance_algorithm import TeamBalancer, BalancingMode
        
        await interaction.response.defer()
        
        try:
            bot = interaction.client
            
            # 현재 세션의 모든 참가자
            all_participants = self.session.get_all_participants()
            
            # 최신 통계를 가져와서 재밸런싱
            updated_participants = []
            for player in all_participants:
                user_id = player['user_id']
                
                # DB에서 최신 통계 조회
                stats = await bot.db_manager.get_user_statistics(
                    self.guild_id, user_id
                )
                
                # 통계가 있으면 업데이트, 없으면 기존 데이터 유지
                if stats:
                    player_data = {
                        'user_id': user_id,
                        'username': player['username'],
                        'total_games': stats['total_games'],
                        'total_wins': stats['total_wins'],
                        'tank_games': stats['tank_games'],
                        'tank_wins': stats['tank_wins'],
                        'dps_games': stats['dps_games'],
                        'dps_wins': stats['dps_wins'],
                        'support_games': stats['support_games'],
                        'support_wins': stats['support_wins'],
                        'main_position': player.get('main_position', '딜러')
                    }
                else:
                    player_data = {
                        'user_id': user_id,
                        'username': player['username'],
                        'total_games': 0,
                        'total_wins': 0,
                        'tank_games': 0,
                        'tank_wins': 0,
                        'dps_games': 0,
                        'dps_wins': 0,
                        'support_games': 0,
                        'support_wins': 0,
                        'main_position': player.get('main_position', '딜러')
                    }
                
                updated_participants.append(player_data)
            
            # TeamBalancer 사용
            balancer = TeamBalancer(mode=BalancingMode.PRECISE)
            balance_results = balancer.find_optimal_balance(updated_participants)
            
            if not balance_results:
                await interaction.followup.send(
                    "❌ 팀 밸런싱 실패: 적절한 팀 구성을 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 최적의 결과 선택 (첫 번째)
            best_result = balance_results[0]
            
            # TeamComposition을 Dict 리스트로 변환
            team_a_list = [
                best_result.team_a.tank.to_dict(),
                best_result.team_a.dps1.to_dict(),
                best_result.team_a.dps2.to_dict(),
                best_result.team_a.support1.to_dict(),
                best_result.team_a.support2.to_dict()
            ]
            
            team_b_list = [
                best_result.team_b.tank.to_dict(),
                best_result.team_b.dps1.to_dict(),
                best_result.team_b.dps2.to_dict(),
                best_result.team_b.support1.to_dict(),
                best_result.team_b.support2.to_dict()
            ]
            
            # 포지션 매핑 (자동 할당됨)
            team_a_positions = {
                best_result.team_a.tank.user_id: "탱커",
                best_result.team_a.dps1.user_id: "딜러",
                best_result.team_a.dps2.user_id: "딜러",
                best_result.team_a.support1.user_id: "힐러",
                best_result.team_a.support2.user_id: "힐러"
            }
            
            team_b_positions = {
                best_result.team_b.tank.user_id: "탱커",
                best_result.team_b.dps1.user_id: "딜러",
                best_result.team_b.dps2.user_id: "딜러",
                best_result.team_b.support1.user_id: "힐러",
                best_result.team_b.support2.user_id: "힐러"
            }
            
            # ✅ 세션 정보 업데이트
            self.session.update_teams(
                new_team_a=team_a_list,
                new_team_b=team_b_list,
                new_team_a_positions=team_a_positions,
                new_team_b_positions=team_b_positions
            )
            
            # ✅ 바로 GameReadyView 생성
            game_view = GameReadyView(self.session_id)
            
            # 팀 구성 표시
            embed = discord.Embed(
                title="🔄 재밸런싱 완료!",
                description=f"업데이트된 통계로 새로운 팀을 구성했습니다.\n"
                        f"**밸런스 점수**: {best_result.balance_score:.1%}\n"
                        f"**예상 승률**: A팀 {best_result.predicted_winrate_a:.1%} vs B팀 {1-best_result.predicted_winrate_a:.1%}",
                color=0x00ff88
            )
            
            # A팀 구성 (포지션 포함)
            team_a_text = "\n".join([
                f"🛡️ {best_result.team_a.tank.username}",
                f"⚔️ {best_result.team_a.dps1.username}",
                f"⚔️ {best_result.team_a.dps2.username}",
                f"💚 {best_result.team_a.support1.username}",
                f"💚 {best_result.team_a.support2.username}"
            ])
            
            # B팀 구성 (포지션 포함)
            team_b_text = "\n".join([
                f"🛡️ {best_result.team_b.tank.username}",
                f"⚔️ {best_result.team_b.dps1.username}",
                f"⚔️ {best_result.team_b.dps2.username}",
                f"💚 {best_result.team_b.support1.username}",
                f"💚 {best_result.team_b.support2.username}"
            ])
            
            embed.add_field(
                name="🔵 A팀",
                value=team_a_text,
                inline=True
            )
            embed.add_field(
                name="🔴 B팀",
                value=team_b_text,
                inline=True
            )
            
            embed.add_field(
                name="📋 다음 단계",
                value="아래 버튼으로 경기 결과를 기록하거나 세션을 취소할 수 있습니다.",
                inline=False
            )
            
            embed.set_footer(text=f"세션 ID: {self.session_id[:8]}...")
            
            await interaction.followup.send(
                embed=embed,
                view=game_view
            )
            
            logger.info(f"동일 멤버 재밸런싱 완료: {self.session_id[:8]}")
            
        except Exception as e:
            logger.error(f"재밸런싱 중 오류: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ 재밸런싱 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    async def rematch_change_members(self, interaction: discord.Interaction):
        """멤버 변경 후 재밸런싱"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            bot = interaction.client
            
            # 현재 참가자 목록
            current_participants = self.session.get_all_participants()
            
            # 서버의 전체 등록 유저 목록 가져오기
            all_users = await bot.db_manager.get_registered_users_list(
                self.guild_id, limit=100
            )
            
            # 멤버 관리 View 표시
            member_mgmt_view = MemberManagementView(
                self.session_id,
                self.session,
                current_participants,
                all_users,
                self.guild_id
            )
            
            embed = discord.Embed(
                title="👥 멤버 변경",
                description=f"현재 참가자: **{len(current_participants)}명**\n\n"
                           "멤버를 추가하거나 제거한 후,\n"
                           "**10명이 되면** 재밸런싱 버튼이 활성화됩니다.",
                color=0x5865F2
            )
            
            # 현재 멤버 리스트
            members_text = "\n".join([
                f"{i+1}. {p['username']}"
                for i, p in enumerate(current_participants)
            ])
            
            embed.add_field(
                name="📋 현재 참가 멤버",
                value=members_text if members_text else "없음",
                inline=False
            )
            
            await interaction.followup.send(
                embed=embed,
                view=member_mgmt_view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"멤버 변경 UI 생성 중 오류: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )


class MemberManagementView(View):
    """멤버 추가/제거 관리 View"""
    
    def __init__(
        self,
        session_id: str,
        session,
        current_participants: List[Dict],
        all_users: List[Dict],
        guild_id: str
    ):
        super().__init__(timeout=300)  # 5분
        self.session_id = session_id
        self.session = session
        self.current_participants = current_participants.copy()
        self.all_users = all_users
        self.guild_id = guild_id
        
        # 멤버 추가 버튼
        add_button = Button(
            label="멤버 추가",
            style=discord.ButtonStyle.success,
            emoji="➕"
        )
        add_button.callback = self.add_member_callback
        self.add_item(add_button)
        
        # 멤버 제거 버튼
        remove_button = Button(
            label="멤버 제거",
            style=discord.ButtonStyle.danger,
            emoji="➖"
        )
        remove_button.callback = self.remove_member_callback
        self.add_item(remove_button)
        
        # 현재 멤버 보기 버튼
        view_button = Button(
            label="현재 멤버 보기",
            style=discord.ButtonStyle.secondary,
            emoji="📋"
        )
        view_button.callback = self.view_members_callback
        self.add_item(view_button)
        
        # 재밸런싱 버튼 (10명일 때만 활성화)
        rebalance_button = Button(
            label=f"재밸런싱 ({len(self.current_participants)}/10)",
            style=discord.ButtonStyle.primary,
            emoji="✅",
            disabled=len(self.current_participants) != 10
        )
        rebalance_button.callback = self.rebalance_callback
        self.add_item(rebalance_button)
    
    async def add_member_callback(self, interaction: discord.Interaction):
        """멤버 추가"""
        # 현재 참가자가 아닌 유저만 필터링
        current_ids = {p['user_id'] for p in self.current_participants}
        available_users = [
            user for user in self.all_users
            if user['user_id'] not in current_ids
        ]
        
        if not available_users:
            await interaction.response.send_message(
                "❌ 추가할 수 있는 멤버가 없습니다.",
                ephemeral=True
            )
            return
        
        # 멤버 선택 Select 생성
        select = Select(
            placeholder="추가할 멤버를 선택하세요 (최대 10명)",
            min_values=1,
            max_values=min(10, len(available_users)),
            options=[
                discord.SelectOption(
                    label=f"{user['username']}",
                    value=user['user_id'],
                    description=f"{user['main_position']} | {user['current_season_tier']}"
                )
                for user in available_users[:25]  # Discord 제한
            ]
        )
        
        async def select_callback(select_interaction: discord.Interaction):
            selected_ids = select_interaction.data['values']
            
            # 선택된 유저 추가
            for user_id in selected_ids:
                user_data = next(
                    (u for u in available_users if u['user_id'] == user_id),
                    None
                )
                if user_data and len(self.current_participants) < 20:
                    self.current_participants.append({
                        'user_id': user_data['user_id'],
                        'username': user_data['username']
                    })
            
            await self.update_view(select_interaction)
        
        select.callback = select_callback
        
        view = View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message(
            "➕ 추가할 멤버를 선택하세요:",
            view=view,
            ephemeral=True
        )
    
    async def remove_member_callback(self, interaction: discord.Interaction):
        """멤버 제거"""
        if not self.current_participants:
            await interaction.response.send_message(
                "❌ 제거할 멤버가 없습니다.",
                ephemeral=True
            )
            return
        
        # 멤버 선택 Select 생성
        select = Select(
            placeholder="제거할 멤버를 선택하세요",
            min_values=1,
            max_values=min(10, len(self.current_participants)),
            options=[
                discord.SelectOption(
                    label=f"{i+1}. {p['username']}",
                    value=p['user_id']
                )
                for i, p in enumerate(self.current_participants[:25])
            ]
        )
        
        async def select_callback(select_interaction: discord.Interaction):
            selected_ids = select_interaction.data['values']
            
            # 선택된 유저 제거
            self.current_participants = [
                p for p in self.current_participants
                if p['user_id'] not in selected_ids
            ]
            
            await self.update_view(select_interaction)
        
        select.callback = select_callback
        
        view = View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message(
            "➖ 제거할 멤버를 선택하세요:",
            view=view,
            ephemeral=True
        )
    
    async def view_members_callback(self, interaction: discord.Interaction):
        """현재 멤버 보기"""
        embed = discord.Embed(
            title="📋 현재 참가 멤버",
            description=f"총 **{len(self.current_participants)}명**",
            color=0x5865F2
        )
        
        members_text = "\n".join([
            f"{i+1}. {p['username']}"
            for i, p in enumerate(self.current_participants)
        ])
        
        embed.add_field(
            name="멤버 목록",
            value=members_text if members_text else "없음",
            inline=False
        )
        
        status = "✅ 재밸런싱 가능" if len(self.current_participants) == 10 else f"⚠️ {10 - len(self.current_participants)}명 {'부족' if len(self.current_participants) < 10 else '초과'}"
        embed.add_field(
            name="상태",
            value=status,
            inline=False
        )
        
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )
    
    async def rebalance_callback(self, interaction: discord.Interaction):
        """재밸런싱 실행"""
        if len(self.current_participants) != 10:
            await interaction.response.send_message(
                f"❌ 정확히 10명이 필요합니다. (현재: {len(self.current_participants)}명)",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            from utils.balance_algorithm import TeamBalancer, BalancingMode
            bot = interaction.client
            
            # 참가자들의 최신 통계 가져오기
            updated_participants = []
            for player in self.current_participants:
                user_id = player['user_id']
                
                stats = await bot.db_manager.get_user_statistics(
                    self.guild_id, user_id
                )
                
                if stats:
                    player_data = {
                        'user_id': user_id,
                        'username': player['username'],
                        'total_games': stats['total_games'],
                        'total_wins': stats['total_wins'],
                        'tank_games': stats['tank_games'],
                        'tank_wins': stats['tank_wins'],
                        'dps_games': stats['dps_games'],
                        'dps_wins': stats['dps_wins'],
                        'support_games': stats['support_games'],
                        'support_wins': stats['support_wins'],
                        'main_position': player.get('main_position', '딜러')
                    }
                else:
                    player_data = {
                        'user_id': user_id,
                        'username': player['username'],
                        'total_games': 0,
                        'total_wins': 0,
                        'tank_games': 0,
                        'tank_wins': 0,
                        'dps_games': 0,
                        'dps_wins': 0,
                        'support_games': 0,
                        'support_wins': 0,
                        'main_position': player.get('main_position', '딜러')
                    }
                
                updated_participants.append(player_data)
            
            # TeamBalancer 사용
            balancer = TeamBalancer(mode=BalancingMode.PRECISE)
            balance_results = balancer.find_optimal_balance(updated_participants)
            
            if not balance_results:
                await interaction.followup.send(
                    "❌ 팀 밸런싱 실패: 적절한 팀 구성을 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 최적의 결과 선택
            best_result = balance_results[0]
            
            # TeamComposition을 Dict 리스트로 변환
            team_a_list = [
                best_result.team_a.tank.to_dict(),
                best_result.team_a.dps1.to_dict(),
                best_result.team_a.dps2.to_dict(),
                best_result.team_a.support1.to_dict(),
                best_result.team_a.support2.to_dict()
            ]
            
            team_b_list = [
                best_result.team_b.tank.to_dict(),
                best_result.team_b.dps1.to_dict(),
                best_result.team_b.dps2.to_dict(),
                best_result.team_b.support1.to_dict(),
                best_result.team_b.support2.to_dict()
            ]
            
            # 포지션 매핑
            team_a_positions = {
                best_result.team_a.tank.user_id: "탱커",
                best_result.team_a.dps1.user_id: "딜러",
                best_result.team_a.dps2.user_id: "딜러",
                best_result.team_a.support1.user_id: "힐러",
                best_result.team_a.support2.user_id: "힐러"
            }
            
            team_b_positions = {
                best_result.team_b.tank.user_id: "탱커",
                best_result.team_b.dps1.user_id: "딜러",
                best_result.team_b.dps2.user_id: "딜러",
                best_result.team_b.support1.user_id: "힐러",
                best_result.team_b.support2.user_id: "힐러"
            }
            
            # ✅ 세션 정보 업데이트
            self.session.update_teams(
                new_team_a=team_a_list,
                new_team_b=team_b_list,
                new_team_a_positions=team_a_positions,
                new_team_b_positions=team_b_positions
            )
            
            # ✅ 바로 GameReadyView 생성
            game_view = GameReadyView(self.session_id)
            
            embed = discord.Embed(
                title="🔄 재밸런싱 완료!",
                description=f"변경된 멤버로 새로운 팀을 구성했습니다.\n"
                        f"**밸런스 점수**: {best_result.balance_score:.1%}\n"
                        f"**예상 승률**: A팀 {best_result.predicted_winrate_a:.1%} vs B팀 {1-best_result.predicted_winrate_a:.1%}",
                color=0x00ff88
            )
            
            # 팀 구성 표시
            team_a_text = "\n".join([
                f"🛡️ {best_result.team_a.tank.username}",
                f"⚔️ {best_result.team_a.dps1.username}",
                f"⚔️ {best_result.team_a.dps2.username}",
                f"💚 {best_result.team_a.support1.username}",
                f"💚 {best_result.team_a.support2.username}"
            ])
            
            team_b_text = "\n".join([
                f"🛡️ {best_result.team_b.tank.username}",
                f"⚔️ {best_result.team_b.dps1.username}",
                f"⚔️ {best_result.team_b.dps2.username}",
                f"💚 {best_result.team_b.support1.username}",
                f"💚 {best_result.team_b.support2.username}"
            ])
            
            embed.add_field(
                name="🔵 A팀",
                value=team_a_text,
                inline=True
            )
            embed.add_field(
                name="🔴 B팀",
                value=team_b_text,
                inline=True
            )
            
            embed.add_field(
                name="📋 다음 단계",
                value="아래 버튼으로 경기 결과를 기록하거나 세션을 취소할 수 있습니다.",
                inline=False
            )
            
            embed.set_footer(text=f"세션 ID: {self.session_id[:8]}...")
            
            await interaction.followup.send(
                embed=embed,
                view=game_view
            )
            
            logger.info(f"멤버 변경 후 재밸런싱 완료: {self.session_id[:8]}")
            
        except Exception as e:
            logger.error(f"재밸런싱 중 오류: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ 재밸런싱 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    async def update_view(self, interaction: discord.Interaction):
        """View 업데이트"""
        # 버튼 상태 업데이트
        self.clear_items()
        
        # 멤버 추가 버튼
        add_button = Button(
            label="멤버 추가",
            style=discord.ButtonStyle.success,
            emoji="➕"
        )
        add_button.callback = self.add_member_callback
        self.add_item(add_button)
        
        # 멤버 제거 버튼
        remove_button = Button(
            label="멤버 제거",
            style=discord.ButtonStyle.danger,
            emoji="➖",
            disabled=len(self.current_participants) == 0
        )
        remove_button.callback = self.remove_member_callback
        self.add_item(remove_button)
        
        # 현재 멤버 보기 버튼
        view_button = Button(
            label="현재 멤버 보기",
            style=discord.ButtonStyle.secondary,
            emoji="📋"
        )
        view_button.callback = self.view_members_callback
        self.add_item(view_button)
        
        # 재밸런싱 버튼 (10명일 때만 활성화)
        rebalance_button = Button(
            label=f"재밸런싱 ({len(self.current_participants)}/10)",
            style=discord.ButtonStyle.primary,
            emoji="✅",
            disabled=len(self.current_participants) != 10
        )
        rebalance_button.callback = self.rebalance_callback
        self.add_item(rebalance_button)
        
        # Embed 업데이트
        embed = discord.Embed(
            title="👥 멤버 변경",
            description=f"현재 참가자: **{len(self.current_participants)}명**\n\n"
                       "멤버를 추가하거나 제거한 후,\n"
                       "**10명이 되면** 재밸런싱 버튼이 활성화됩니다.",
            color=0x5865F2
        )
        
        # 현재 멤버 리스트
        members_text = "\n".join([
            f"{i+1}. {p['username']}"
            for i, p in enumerate(self.current_participants)
        ])
        
        embed.add_field(
            name="📋 현재 참가 멤버",
            value=members_text if members_text else "없음",
            inline=False
        )
        
        await interaction.response.edit_message(
            embed=embed,
            view=self
        )