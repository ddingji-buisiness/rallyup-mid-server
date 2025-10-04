import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import uuid

OVERWATCH_MAPS = {
    "호위": [
        "66번국도", "지브롤터", "도라도", "리알토", "샴발리수도원", 
        "서킷로얄", "쓰레기촌", "하바나"
    ],
    "밀기": [
        "뉴 퀸 스트리트", "이스페란사", "콜로세오", "루나사피"
    ],
    "혼합": [
        "눔바니", "미드타운", "블리자드 월드", "아이헨발데", 
        "왕의 길", "파라이수", "할리우드"
    ],
    "쟁탈": [
        "일리오스", "리장타워", "네팔", "오아시스", 
        "부산", "남극반도", "사모아"
    ],
    "플래시포인트": [
        "뉴 정크 시티", "수라바사", "아틀라스"
    ],
    "격돌": [
        "아누비스의 왕좌", "하나오카"
    ],
    "점령": [
        "불스카야 인더스트리", "아누비스 신전", "하나무라", 
        "파리", "호라이즌 달 기지"
    ]
}

class MapSelectionView(discord.ui.View):
    """맵 선택 View"""

    def __init__(self, bot, session: 'ScrimResultSession', match_number: int, dashboard: 'ScrimDashboardView'):
        super().__init__(timeout=300)
        self.bot = bot
        self.session = session
        self.match_number = match_number
        self.match_data = session.matches[match_number]
        self.dashboard = dashboard
        
        # 맵 타입 선택 드롭다운
        self.add_item(MapTypeSelect(self))
        
        # 건너뛰기 버튼
        skip_button = discord.ui.Button(
            label="맵 선택 건너뛰기",
            style=discord.ButtonStyle.secondary,
            emoji="⏭️"
        )
        skip_button.callback = self.skip_map_selection
        self.add_item(skip_button)
    
    async def skip_map_selection(self, interaction: discord.Interaction):
        """맵 선택 건너뛰기"""
        # 맵 정보 없이 최종 완료
        await self.complete_match_recording(interaction)
    
    async def complete_match_recording(self, interaction: discord.Interaction):
        """최종 경기 기록 완료"""
        try:
            # 매치 완료 표시
            self.match_data['completed'] = True
            self.match_data['guild_id'] = str(interaction.guild_id)

            # 데이터베이스에 저장
            await self.save_match_to_database(str(interaction.guild_id))
            
            await self.dashboard.update_dashboard()

            # 완료 메시지
            embed = discord.Embed(
                title=f"✅ {self.match_number}경기 기록 완료!",
                description="경기 결과가 성공적으로 저장되었습니다.",
                color=0x00ff88
            )
            
            # 경기 요약 표시
            winner_text = "🔵 A팀" if self.match_data['winner'] == "team_a" else "🔴 B팀"
            embed.add_field(name="🏆 승리팀", value=winner_text, inline=True)
            
            # 맵 정보가 있으면 표시
            if 'map_name' in self.match_data and self.match_data['map_name']:
                map_info = f"**{self.match_data['map_name']}**"
                if 'map_type' in self.match_data and self.match_data['map_type']:
                    map_info += f" ({self.match_data['map_type']})"
                embed.add_field(name="🗺️ 맵", value=map_info, inline=True)

            embed.add_field(
                name="📊 현재 진행",
                value=f"**완료된 경기**: {self.session.get_completed_count()}경기\n"
                      f"**다음 경기**: {self.session.get_next_match_number()}경기",
                inline=False
            )
            
            # 다음 단계 안내
            embed.add_field(
                name="🎯 다음 단계",
                value="대시보드의 **[➕ 경기 추가]** 버튼으로 다음 경기를 추가하거나\n"
                      "**[✅ 기록 완료]** 버튼으로 모든 기록을 저장할 수 있습니다.",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            await interaction.response.send_message(
                f"경기 기록 저장 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )
    
    async def save_match_to_database(self, guild_id: str):
        """매치 데이터를 데이터베이스에 저장 (맵 정보 포함)"""
        try:
            # 매치 데이터 준비
            match_data_for_db = {
                'recruitment_id': self.session.recruitment_id,
                'match_number': self.match_number,
                'winner': self.match_data['winner'],
                'created_by': self.session.created_by,
                'guild_id': guild_id,
                'team_a': self.match_data['team_a'],
                'team_b': self.match_data['team_b'],
                'team_a_positions': self.match_data['team_a_positions'],
                'team_b_positions': self.match_data['team_b_positions'],
                # 🆕 맵 정보 추가
                'map_name': self.match_data.get('map_name'),
                'map_type': self.match_data.get('map_type')
            }
            
            # 데이터베이스에 저장
            match_id = await self.bot.db_manager.save_match_result(match_data_for_db)
            return match_id
            
        except Exception as e:
            print(f"매치 저장 실패: {e}")
            raise

class MapTypeSelect(discord.ui.Select):
    """맵 타입 선택 드롭다운"""
    
    def __init__(self, parent_view):
        self.parent_view = parent_view
        
        options = []
        for map_type in OVERWATCH_MAPS.keys():
            map_count = len(OVERWATCH_MAPS[map_type])
            options.append(discord.SelectOption(
                label=map_type,
                description=f"{map_count}개 맵 포함",
                emoji="🗺️"
            ))
        
        super().__init__(
            placeholder="맵 타입을 선택하세요...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_map_type = self.values[0]
        
        # 선택된 맵 타입의 맵들로 새 View 생성
        view = MapSelectionView(
            self.parent_view.bot, 
            self.parent_view.session, 
            self.parent_view.match_number,
            self.parent_view.dashboard
        )
        view.clear_items()
        
        # 맵 선택 드롭다운 추가
        view.add_item(MapSelect(view, selected_map_type))
        
        # 뒤로가기 버튼
        back_button = discord.ui.Button(
            label="맵 타입 다시 선택",
            style=discord.ButtonStyle.secondary,
            emoji="🔙"
        )
        back_button.callback = self.go_back_to_type_selection
        view.add_item(back_button)
        
        # 건너뛰기 버튼
        skip_button = discord.ui.Button(
            label="맵 선택 건너뛰기",
            style=discord.ButtonStyle.secondary,
            emoji="⏭️"
        )
        skip_button.callback = view.skip_map_selection
        view.add_item(skip_button)
        
        embed = discord.Embed(
            title=f"🗺️ {selected_map_type} 맵 선택",
            description=f"**{selected_map_type}** 타입에서 플레이한 맵을 선택해주세요.",
            color=0x0099ff
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def go_back_to_type_selection(self, interaction: discord.Interaction):
        """맵 타입 선택으로 돌아가기"""
        # 원래 View 다시 생성
        view = MapSelectionView(
            self.parent_view.bot,
            self.parent_view.session,
            self.parent_view.match_number,
            self.parent_view.dashboard
        )
        
        embed = discord.Embed(
            title="🗺️ 맵 선택 (선택사항)",
            description="플레이한 맵을 기록하시겠습니까?\n맵별 통계를 위해 선택하시는 것을 권장합니다.",
            color=0x0099ff
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

class MapSelect(discord.ui.Select):
    """개별 맵 선택 드롭다운"""
    
    def __init__(self, parent_view, map_type: str):
        self.parent_view = parent_view
        self.map_type = map_type
        
        options = []
        for map_name in OVERWATCH_MAPS[map_type]:
            options.append(discord.SelectOption(
                label=map_name,
                description=f"{map_type} 맵",
                emoji="🎯"
            ))
        
        super().__init__(
            placeholder=f"{map_type} 맵을 선택하세요...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_map = self.values[0]
        
        # 매치 데이터에 맵 정보 저장
        match_data = self.parent_view.match_data
        match_data['map_name'] = selected_map
        match_data['map_type'] = self.map_type
        
        # 맵 선택 완료 후 최종 기록 완료
        await self.parent_view.complete_match_recording(interaction)

class ScrimResultSession:
    """내전 결과 기록 세션 관리 - 개선 버전"""
    def __init__(self, recruitment_id: str, participants: List[Dict], created_by: str, initial_match_number: int = 1):
        self.recruitment_id = recruitment_id
        self.participants = participants
        self.created_by = created_by
        self.matches = {}
        self.current_match = initial_match_number  # 🆕 자동으로 시작 번호 설정
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.now()
        self.dashboard_message = None  # 🆕 대시보드 메시지 추적
    
    def get_next_match_number(self) -> int:
        """🆕 다음 경기 번호 자동 반환"""
        completed_matches = [num for num, data in self.matches.items() if data.get('completed')]
        if completed_matches:
            return max(completed_matches) + 1
        return self.current_match
    
    def get_completed_count(self) -> int:
        """🆕 완료된 경기 수 반환"""
        return len([data for data in self.matches.values() if data.get('completed')])

active_sessions: Dict[str, ScrimResultSession] = {}

class ScrimDashboardView(discord.ui.View):
    """🆕 내전 결과 기록 메인 대시보드"""
    
    def __init__(self, bot, session: ScrimResultSession, guild_id: str, recruitment_info: Dict):
        super().__init__(timeout=None)  # 타임아웃 없음 (세션 종료 시까지 유지)
        self.bot = bot
        self.session = session
        self.guild_id = guild_id
        self.recruitment_info = recruitment_info
        
        self.setup_buttons()
    
    def setup_buttons(self):
        """대시보드 버튼 구성"""
        self.clear_items()
        
        # 경기 추가 버튼
        add_match_button = discord.ui.Button(
            label=f"경기 추가 (다음: {self.session.get_next_match_number()}경기)",
            style=discord.ButtonStyle.primary,
            emoji="➕",
            custom_id="add_match"
        )
        add_match_button.callback = self.add_match_callback
        self.add_item(add_match_button)
        
        # 진행 현황 버튼
        status_button = discord.ui.Button(
            label="진행 현황",
            style=discord.ButtonStyle.secondary,
            emoji="📊",
            custom_id="view_status"
        )
        status_button.callback = self.view_status_callback
        self.add_item(status_button)
        
        # 기록 완료 버튼 (경기가 1개 이상 있을 때만 활성화)
        complete_button = discord.ui.Button(
            label=f"기록 완료 ({self.session.get_completed_count()}경기)",
            style=discord.ButtonStyle.success,
            emoji="✅",
            custom_id="complete_recording",
            disabled=self.session.get_completed_count() == 0
        )
        complete_button.callback = self.complete_recording_callback
        self.add_item(complete_button)
        
        # 세션 취소 버튼
        cancel_button = discord.ui.Button(
            label="세션 취소",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            custom_id="cancel_session"
        )
        cancel_button.callback = self.cancel_session_callback
        self.add_item(cancel_button)
    
    async def add_match_callback(self, interaction: discord.Interaction):
        """경기 추가 - 자동으로 다음 경기 번호 할당"""
        next_match = self.session.get_next_match_number()
        
        # 팀 구성 단계로 이동
        await self.start_team_setup(interaction, next_match)
    
    async def start_team_setup(self, interaction: discord.Interaction, match_number: int):
        """팀 구성 시작"""
        view = TeamSetupView(self.bot, self.session, match_number, self)
        
        embed = discord.Embed(
            title=f"🔵🔴 {match_number}경기 팀 구성",
            description="A팀에 포함될 5명을 선택해주세요. (나머지 5명은 자동으로 B팀이 됩니다)",
            color=0x0099ff
        )
        
        embed.add_field(
            name="📊 세션 정보",
            value=f"**내전**: {self.recruitment_info['title']}\n"
                  f"**경기 번호**: {match_number}경기\n"
                  f"**완료된 경기**: {self.session.get_completed_count()}경기",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def view_status_callback(self, interaction: discord.Interaction):
        """진행 현황 보기"""
        embed = discord.Embed(
            title="📊 내전 결과 기록 진행 현황",
            color=0x0099ff
        )
        
        embed.add_field(
            name="🎮 내전 정보",
            value=f"**제목**: {self.recruitment_info['title']}\n"
                  f"**참가자**: {len(self.session.participants)}명\n"
                  f"**세션 시작**: <t:{int(self.session.created_at.timestamp())}:R>",
            inline=False
        )
        
        # 경기 진행 상황
        if self.session.matches:
            match_status = []
            for match_num in sorted(self.session.matches.keys()):
                match_data = self.session.matches[match_num]
                if match_data.get('completed'):
                    winner = "🔵 A팀" if match_data['winner'] == "team_a" else "🔴 B팀"
                    map_info = f" - {match_data.get('map_name', '')}" if match_data.get('map_name') else ""
                    match_status.append(f"✅ {match_num}경기: {winner} 승리{map_info}")
                else:
                    match_status.append(f"⏳ {match_num}경기: 진행 중")
            
            embed.add_field(
                name="🏆 경기 결과",
                value="\n".join(match_status),
                inline=False
            )
        else:
            embed.add_field(
                name="🏆 경기 결과",
                value="아직 기록된 경기가 없습니다.",
                inline=False
            )
        
        embed.add_field(
            name="📈 통계",
            value=f"**완료된 경기**: {self.session.get_completed_count()}경기\n"
                  f"**다음 경기 번호**: {self.session.get_next_match_number()}경기",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def complete_recording_callback(self, interaction: discord.Interaction):
        """기록 완료"""
        if self.session.get_completed_count() == 0:
            await interaction.response.send_message(
                "❌ 완료된 경기가 없습니다.", ephemeral=True
            )
            return
        
        # 확인 메시지
        confirm_view = ConfirmCompleteView(self.bot, self.session, self.guild_id, self)
        
        embed = discord.Embed(
            title="⚠️ 기록 완료 확인",
            description=f"총 **{self.session.get_completed_count()}경기**의 결과를 저장하고 통계를 업데이트하시겠습니까?",
            color=0xffaa00
        )
        
        embed.add_field(
            name="💾 저장될 내용",
            value="✅ 개인 승률 업데이트\n"
                  "✅ 포지션별 통계 업데이트\n"
                  "✅ 매치업 기록 저장\n"
                  "✅ 서버 랭킹 갱신",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
    
    async def cancel_session_callback(self, interaction: discord.Interaction):
        """세션 취소"""
        confirm_view = ConfirmCancelView(self.bot, self.session, self.guild_id)
        
        embed = discord.Embed(
            title="⚠️ 세션 취소 확인",
            description="정말로 이 세션을 취소하시겠습니까?\n**저장되지 않은 모든 데이터가 사라집니다.**",
            color=0xff4444
        )
        
        if self.session.get_completed_count() > 0:
            embed.add_field(
                name="⚠️ 주의",
                value=f"현재 **{self.session.get_completed_count()}경기**가 완료되었으나 저장되지 않았습니다.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
    
    async def update_dashboard(self, interaction: discord.Interaction = None):
        """🆕 대시보드 업데이트"""
        self.setup_buttons()
        embed = self.create_dashboard_embed()
        
        if self.session.dashboard_message:
            try:
                await self.session.dashboard_message.edit(embed=embed, view=self)
            except:
                pass
        
        if interaction and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)
    
    def create_dashboard_embed(self) -> discord.Embed:
        """🆕 대시보드 임베드 생성"""
        embed = discord.Embed(
            title="🎮 내전 결과 기록 대시보드",
            description=f"**{self.recruitment_info['title']}**",
            color=0x00ff88
        )
        
        # 현재 상태
        status_emoji = "🟢" if self.session.get_completed_count() > 0 else "⚪"
        embed.add_field(
            name=f"{status_emoji} 현재 상태",
            value=f"**완료된 경기**: {self.session.get_completed_count()}경기\n"
                  f"**다음 경기**: {self.session.get_next_match_number()}경기\n"
                  f"**참가자**: {len(self.session.participants)}명",
            inline=True
        )
        
        # 최근 경기 결과 (최대 3경기)
        recent_matches = []
        completed_nums = sorted([num for num, data in self.session.matches.items() if data.get('completed')], reverse=True)
        
        for match_num in completed_nums[:3]:
            match_data = self.session.matches[match_num]
            winner = "🔵 A팀" if match_data['winner'] == "team_a" else "🔴 B팀"
            recent_matches.append(f"{match_num}경기: {winner}")
        
        if recent_matches:
            embed.add_field(
                name="📋 최근 경기",
                value="\n".join(recent_matches),
                inline=True
            )
        
        embed.add_field(
            name="🎯 사용 방법",
            value="**➕ 경기 추가**: 새 경기 기록\n"
                  "**📊 진행 현황**: 상세 정보 확인\n"
                  "**✅ 기록 완료**: 통계 저장",
            inline=False
        )
        
        embed.set_footer(text=f"세션 ID: {self.session.session_id[:8]}... | 시작: {self.session.created_at.strftime('%H:%M')}")
        
        return embed

class ConfirmCompleteView(discord.ui.View):
    """🆕 기록 완료 확인 View"""
    
    def __init__(self, bot, session: ScrimResultSession, guild_id: str, dashboard: ScrimDashboardView):
        super().__init__(timeout=60)
        self.bot = bot
        self.session = session
        self.guild_id = guild_id
        self.dashboard = dashboard
    
    @discord.ui.button(label="네, 완료합니다", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        try:
            # 모든 완료된 매치 데이터 저장 및 통계 업데이트
            completed_matches = [
                num for num, data in self.session.matches.items() 
                if data.get('completed')
            ]
            
            completed_match_data = []
            for match_num in completed_matches:
                match_data = self.session.matches[match_num].copy()
                match_data['guild_id'] = self.guild_id
                match_data['recruitment_id'] = self.session.recruitment_id
                match_data['match_number'] = match_num
                match_data['created_by'] = self.session.created_by
                
                if not match_data.get('saved_to_db'):
                    await self.bot.db_manager.save_match_result(match_data)
                    self.session.matches[match_num]['saved_to_db'] = True
                
                completed_match_data.append(match_data)
            
            # 통계 업데이트
            await self.bot.db_manager.update_user_statistics(self.guild_id, completed_match_data)
            
            # 세션 종료
            if self.guild_id in active_sessions:
                del active_sessions[self.guild_id]
            
            # 대시보드 메시지 제거
            if self.dashboard.session.dashboard_message:
                try:
                    await self.dashboard.session.dashboard_message.delete()
                except:
                    pass
            
            # 완료 메시지
            embed = discord.Embed(
                title="🎉 내전 결과 기록 완료!",
                description=f"총 {len(completed_match_data)}경기의 결과가 성공적으로 저장되었습니다.",
                color=0x00ff88
            )
            
            embed.add_field(
                name="📊 업데이트 완료",
                value="✅ 개인 승률 업데이트\n"
                      "✅ 포지션별 통계 업데이트\n"
                      "✅ 매치업 기록 저장\n"
                      "✅ 서버 랭킹 갱신",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 완료 처리 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )
    
    @discord.ui.button(label="아니오, 취소", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="✅ 취소되었습니다. 계속 경기를 추가할 수 있습니다.",
            embed=None,
            view=None
        )

class ConfirmCancelView(discord.ui.View):
    """🆕 세션 취소 확인 View"""
    
    def __init__(self, bot, session: ScrimResultSession, guild_id: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.session = session
        self.guild_id = guild_id
    
    @discord.ui.button(label="네, 취소합니다", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 세션 삭제
        if self.guild_id in active_sessions:
            del active_sessions[self.guild_id]
        
        # 대시보드 메시지 제거
        if self.session.dashboard_message:
            try:
                await self.session.dashboard_message.delete()
            except:
                pass
        
        await interaction.response.edit_message(
            content="❌ 세션이 취소되었습니다. 저장되지 않은 데이터가 모두 삭제되었습니다.",
            embed=None,
            view=None
        )
    
    @discord.ui.button(label="아니오, 돌아가기", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="✅ 취소가 취소되었습니다. 세션이 계속 유지됩니다.",
            embed=None,
            view=None
        )

class RecruitmentSelectView(discord.ui.View):
    """마감된 내전 모집 선택 View"""
    
    def __init__(self, bot, completed_recruitments: List[Dict], guild_id: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id

        # 마감된 모집 리스트 드롭다운
        options = []
        for recruitment in completed_recruitments[:25]:  # Discord 제한
            scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
            participant_count = recruitment.get('participant_count', 0)
            
            options.append(discord.SelectOption(
                label=f"{recruitment['title']}",
                description=f"{scrim_date.strftime('%m/%d %H:%M')} | 참가자 {participant_count}명",
                value=recruitment['id'],
                emoji="🎮"
            ))
        
        if not options:
            options.append(discord.SelectOption(
                label="마감된 내전이 없습니다",
                description="먼저 내전 모집을 진행해주세요",
                value="none"
            ))
        
        self.recruitment_select = discord.ui.Select(
            placeholder="기록할 내전을 선택하세요",
            options=options
        )
        self.recruitment_select.callback = self.select_recruitment_callback
        self.add_item(self.recruitment_select)
    
    async def select_recruitment_callback(self, interaction: discord.Interaction):
        """내전 선택 처리"""
        if self.recruitment_select.values[0] == "none":
            await interaction.response.send_message(
                "마감된 내전이 없습니다.", ephemeral=True
            )
            return
        
        selected_recruitment_id = self.recruitment_select.values[0]
        
        try:
            # 선택된 모집의 참가자 목록 가져오기
            all_participants = await self.bot.db_manager.get_recruitment_participants(
                selected_recruitment_id
            )

            # 'joined' 상태만 필터링
            base_participants = [p for p in all_participants if p.get('status') == 'joined']
            
            # 기존 경기 기록 확인
            max_match_number = await self.bot.db_manager.get_max_match_number(selected_recruitment_id)
            
            # 모집 정보 가져오기
            recruitment = await self.bot.db_manager.get_recruitment_by_id(selected_recruitment_id)
            
            # 참가자 관리 화면으로 이동
            participant_view = ParticipantManagementView(
                bot=self.bot,
                guild_id=self.guild_id,
                recruitment_id=selected_recruitment_id,
                recruitment_info=recruitment,
                base_participants=base_participants,
                max_match_number=max_match_number
            )
            
            await participant_view.show_management_screen(interaction)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

class ParticipantManagementView(discord.ui.View):
    """참가자 관리 메인 화면"""
    
    def __init__(self, bot, guild_id: str, recruitment_id: str, recruitment_info: Dict, 
                 base_participants: List[Dict], max_match_number: int):
        super().__init__(timeout=600)  # 10분 제한
        self.bot = bot
        self.guild_id = guild_id
        self.recruitment_id = recruitment_id
        self.recruitment_info = recruitment_info
        self.base_participants = base_participants.copy()  # 원본 참가자 (참가 버튼 누른 사람들)
        self.current_participants = base_participants.copy()  # 현재 참가자 리스트 (수정 가능)
        self.max_match_number = max_match_number
        
        self.setup_buttons()
    
    def setup_buttons(self):
        """버튼 설정"""
        self.clear_items()
        
        # 참가자 추가 버튼
        add_button = discord.ui.Button(
            label="➕ 참가자 추가",
            style=discord.ButtonStyle.primary,
            emoji="👤"
        )
        add_button.callback = self.add_participant_callback
        self.add_item(add_button)
        
        # 참가자 제거 버튼 (참가자가 있을 때만)
        if self.current_participants:
            remove_button = discord.ui.Button(
                label="➖ 참가자 제거",
                style=discord.ButtonStyle.secondary,
                emoji="🗑️"
            )
            remove_button.callback = self.remove_participant_callback
            self.add_item(remove_button)
        
        # 참가자 리스트 초기화 버튼
        reset_button = discord.ui.Button(
            label="🔄 기본 리스트로 초기화",
            style=discord.ButtonStyle.secondary,
            emoji="🔄"
        )
        reset_button.callback = self.reset_participants_callback
        self.add_item(reset_button)
        
        # 최종 확정 버튼 (10명 이상일 때만 활성화)
        confirm_button = discord.ui.Button(
            label=f"✅ 참가자 확정 ({len(self.current_participants)}명)",
            style=discord.ButtonStyle.success if len(self.current_participants) >= 10 else discord.ButtonStyle.danger,
            disabled=len(self.current_participants) < 10,
            emoji="✅"
        )
        confirm_button.callback = self.confirm_participants_callback
        self.add_item(confirm_button)
    
    async def show_management_screen(self, interaction: discord.Interaction):
        """참가자 관리 화면 표시"""
        embed = self.create_management_embed()
        self.setup_buttons()
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
    
    def create_management_embed(self) -> discord.Embed:
        """참가자 관리 화면 임베드 생성"""
        embed = discord.Embed(
            title="👥 참가자 관리",
            description=f"**{self.recruitment_info['title']}** 내전 참가자를 관리합니다.",
            color=0x0099ff
        )
        
        # 기본 정보
        scrim_date = datetime.fromisoformat(self.recruitment_info['scrim_date'])
        embed.add_field(
            name="📅 내전 정보",
            value=f"**일시**: {scrim_date.strftime('%Y년 %m월 %d일 %H:%M')}\n"
                  f"**모집 ID**: `{self.recruitment_id}`",
            inline=False
        )
        
        # 참가자 현황
        embed.add_field(
            name="📊 참가자 현황",
            value=f"**현재 참가자**: {len(self.current_participants)}명\n"
                  f"**기본 참가자**: {len(self.base_participants)}명 (참가 버튼)\n"
                  f"**필요 인원**: 10명 이상",
            inline=True
        )
        
        # 상태 표시
        if len(self.current_participants) >= 10:
            status = "✅ 내전 진행 가능"
            status_color = "🟢"
        else:
            status = f"❌ {10 - len(self.current_participants)}명 부족"
            status_color = "🔴"
        
        embed.add_field(
            name="🚦 상태",
            value=f"{status_color} {status}",
            inline=True
        )
        
        # 현재 참가자 목록
        if self.current_participants:
            participant_list = []
            for i, participant in enumerate(self.current_participants[:20], 1):
                # 기본 참가자인지 추가된 참가자인지 구분
                is_base = participant in self.base_participants
                icon = "🔹" if is_base else "➕"
                participant_list.append(f"{icon} {i}. {participant['username']}")
            
            participant_text = '\n'.join(participant_list)
            if len(self.current_participants) > 20:
                participant_text += f"\n... 외 {len(self.current_participants) - 20}명"
            
            embed.add_field(
                name="👤 현재 참가자 목록",
                value=participant_text,
                inline=False
            )
        else:
            embed.add_field(
                name="👤 현재 참가자 목록",
                value="참가자가 없습니다.",
                inline=False
            )
        
        # 범례
        embed.add_field(
            name="📝 범례",
            value="🔹 참가 버튼을 누른 기본 참가자\n➕ 수동으로 추가된 참가자",
            inline=False
        )
        
        return embed
    
    async def add_participant_callback(self, interaction: discord.Interaction):
        """참가자 추가 버튼 클릭"""
        # 전체 등록 유저 목록에서 현재 참가자를 제외한 사용자들 가져오기
        all_users = await self.bot.db_manager.get_registered_users_list(self.guild_id, limit=100)
        
        # 현재 참가자가 아닌 사용자들만 필터링
        current_user_ids = {p['user_id'] for p in self.current_participants}
        available_users = [user for user in all_users if user['user_id'] not in current_user_ids]
        
        if not available_users:
            await interaction.response.send_message(
                "❌ 추가할 수 있는 유저가 없습니다.", ephemeral=True
            )
            return
        
        # 유저 선택 드롭다운 표시
        user_selection_view = UserSelectionView(
            parent_view=self,
            available_users=available_users,
            selection_type="add"
        )
        
        embed = discord.Embed(
            title="➕ 참가자 추가",
            description="추가할 참가자를 선택해주세요.",
            color=0x00ff88
        )
        
        await interaction.response.send_message(embed=embed, view=user_selection_view, ephemeral=True)
    
    async def remove_participant_callback(self, interaction: discord.Interaction):
        """참가자 제거 버튼 클릭"""
        if not self.current_participants:
            await interaction.response.send_message(
                "❌ 제거할 참가자가 없습니다.", ephemeral=True
            )
            return
        
        # 현재 참가자들에서 선택
        user_selection_view = UserSelectionView(
            parent_view=self,
            available_users=self.current_participants,
            selection_type="remove"
        )
        
        embed = discord.Embed(
            title="➖ 참가자 제거",
            description="제거할 참가자를 선택해주세요.",
            color=0xff6666
        )
        
        await interaction.response.send_message(embed=embed, view=user_selection_view, ephemeral=True)
    
    async def reset_participants_callback(self, interaction: discord.Interaction):
        """참가자 리스트 초기화"""
        self.current_participants = self.base_participants.copy()
        await self.show_management_screen(interaction)
    
    async def confirm_participants_callback(self, interaction: discord.Interaction):
        """참가자 최종 확정"""
        if len(self.current_participants) < 10:
            await interaction.response.send_message(
                f"❌ 참가자가 {len(self.current_participants)}명으로 부족합니다. (최소 10명 필요)",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            max_match = await self.bot.db_manager.get_max_match_number(self.recruitment_id)
            next_match = (max_match or 0) + 1

            # 새 결과 기록 세션 생성
            session = ScrimResultSession(
                recruitment_id=self.recruitment_id,
                participants=self.current_participants,
                created_by=str(interaction.user.id)
            )
            
            # 세션 저장
            active_sessions[self.guild_id] = session
            
            # 성공 메시지
            embed = discord.Embed(
                title="✅ 내전 결과 기록 세션 시작!",
                description=f"**{self.recruitment_info['title']}** 내전의 결과 기록을 시작합니다.",
                color=0x00ff88
            )
            
            embed.add_field(
                name="👥 확정된 참가자",
                value=f"총 **{len(self.current_participants)}명**",
                inline=True
            )

            embed.add_field(
                name="📊 기록 현황",
                value=f"기존 기록된 경기: **{max_match}경기**\n"
                    f"다음 경기 번호: **{next_match}경기**",
                inline=True
            )
            
            embed.add_field(
                name="🎯 다음 단계",
                value=f"`/팀세팅 {next_match}` 명령어로 {next_match}경기 팀 구성을 시작하세요.",
                inline=True
            )
            
            # 추가/제거된 참가자 요약
            added_users = [p for p in self.current_participants if p not in self.base_participants]
            removed_users = [p for p in self.base_participants if p not in self.current_participants]
            
            summary_text = []
            if added_users:
                summary_text.append(f"➕ 추가: {len(added_users)}명")
            if removed_users:
                summary_text.append(f"➖ 제거: {len(removed_users)}명")
            
            if summary_text:
                embed.add_field(
                    name="📝 변경 사항",
                    value=" | ".join(summary_text),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 세션 생성 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    async def confirm_participants_callback(self, interaction: discord.Interaction):
        """참가자 최종 확정 - 개선 버전"""
        if len(self.current_participants) < 10:
            await interaction.response.send_message(
                f"❌ 참가자가 {len(self.current_participants)}명으로 부족합니다. (최소 10명 필요)",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # 🆕 기존 경기 최대 번호 확인
            max_match = await self.bot.db_manager.get_max_match_number(self.recruitment_id)
            next_match = (max_match or 0) + 1
            
            # 🆕 세션 생성 시 초기 경기 번호 전달
            session = ScrimResultSession(
                recruitment_id=self.recruitment_id,
                participants=self.current_participants,
                created_by=str(interaction.user.id),
                initial_match_number=next_match
            )
            
            # 세션 저장
            active_sessions[self.guild_id] = session
            
            # 🆕 대시보드 생성 및 표시
            dashboard = ScrimDashboardView(
                self.bot, session, self.guild_id, self.recruitment_info
            )
            
            dashboard_embed = dashboard.create_dashboard_embed()
            dashboard_message = await interaction.followup.send(
                embed=dashboard_embed,
                view=dashboard
            )
            
            # 대시보드 메시지 추적
            session.dashboard_message = dashboard_message
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 세션 생성 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )


class UserSelectionView(discord.ui.View):
    """유저 선택 드롭다운 (추가/제거용)"""
    
    def __init__(self, parent_view: ParticipantManagementView, available_users: List[Dict], 
                 selection_type: str):
        super().__init__(timeout=300)
        self.parent_view = parent_view
        self.available_users = available_users
        self.selection_type = selection_type  # "add" or "remove"
        
        self.setup_select()
    
    def setup_select(self):
        """드롭다운 설정"""
        if not self.available_users:
            return
        
        # 최대 25개까지만 표시 (Discord 제한)
        options = []
        for user in self.available_users[:25]:
            # 유저 정보 포맷팅
            description_parts = []
            if user.get('main_position'):
                description_parts.append(user['main_position'])
            if user.get('current_season_tier'):
                description_parts.append(user['current_season_tier'])
            
            description = " | ".join(description_parts) if description_parts else "정보 없음"
            
            options.append(discord.SelectOption(
                label=user['username'],
                description=description[:100],  # Discord 제한
                value=user['user_id'],
                emoji="👤" if self.selection_type == "add" else "🗑️"
            ))
        
        if options:
            placeholder = "추가할 유저를 선택하세요" if self.selection_type == "add" else "제거할 유저를 선택하세요"
            
            self.user_select = discord.ui.Select(
                placeholder=placeholder,
                options=options,
                max_values=min(len(options), 5)  # 최대 5명까지 한 번에 선택
            )
            self.user_select.callback = self.user_select_callback
            self.add_item(self.user_select)
    
    async def user_select_callback(self, interaction: discord.Interaction):
        """유저 선택 처리"""
        selected_user_ids = self.user_select.values
        
        if self.selection_type == "add":
            # 참가자 추가
            for user_id in selected_user_ids:
                user_data = next((u for u in self.available_users if u['user_id'] == user_id), None)
                if user_data and user_data not in self.parent_view.current_participants:
                    self.parent_view.current_participants.append(user_data)
            
            action_text = f"➕ {len(selected_user_ids)}명의 참가자를 추가했습니다."
            
        else:  # remove
            # 참가자 제거
            for user_id in selected_user_ids:
                self.parent_view.current_participants = [
                    p for p in self.parent_view.current_participants 
                    if p['user_id'] != user_id
                ]
            
            action_text = f"➖ {len(selected_user_ids)}명의 참가자를 제거했습니다."
        
        # 원래 화면으로 돌아가기
        await interaction.response.edit_message(
            content=f"✅ {action_text}",
            embed=None,
            view=None
        )
        
        # 부모 뷰 업데이트 (새로운 메시지로)
        embed = self.parent_view.create_management_embed()
        self.parent_view.setup_buttons()
        
        await interaction.followup.send(embed=embed, view=self.parent_view)

class TeamSetupView(discord.ui.View):
    """팀 구성 설정 View - A팀과 B팀 각각 선택"""
    
    def __init__(self, bot, session: ScrimResultSession, match_number: int, dashboard: ScrimDashboardView):
        super().__init__(timeout=300)
        self.bot = bot
        self.session = session
        self.match_number = match_number
        self.dashboard = dashboard
        self.selected_team_a = []
        self.selected_team_b = []
        self.current_step = "team_a"  # team_a -> team_b -> confirm
        
        # A팀 5명 선택 드롭다운
        self.setup_team_a_selection()
    
    def setup_team_a_selection(self):
        """A팀 선택 드롭다운 설정"""
        options = []
        for i, participant in enumerate(self.session.participants):
            options.append(discord.SelectOption(
                label=f"{i+1}. {participant['username']}",
                value=participant['user_id'],
                description=f"참가자 {i+1}번"
            ))
        
        self.team_a_select = discord.ui.Select(
            placeholder="🔵 A팀 5명을 선택하세요",
            options=options,
            min_values=5,
            max_values=5
        )
        self.team_a_select.callback = self.select_team_a_callback
        self.add_item(self.team_a_select)
    
    async def select_team_a_callback(self, interaction: discord.Interaction):
        """A팀 선택 처리"""
        self.selected_team_a = self.team_a_select.values
        
        # A팀 선택된 유저들 표시
        team_a_users = []
        for participant in self.session.participants:
            if participant['user_id'] in self.selected_team_a:
                team_a_users.append(participant['username'])
        
        embed = discord.Embed(
            title=f"🔵 {self.match_number}경기 A팀 선택 완료",
            color=0x0099ff
        )
        
        embed.add_field(
            name="🔵 A팀 (5명)",
            value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_a_users)]),
            inline=False
        )
        
        embed.add_field(
            name="🔄 다음 단계",
            value="이제 🔴 B팀 5명을 선택해주세요.",
            inline=False
        )
        
        # B팀 선택으로 전환
        self.clear_items()
        self.setup_team_b_selection()
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    def setup_team_b_selection(self):
        """B팀 선택 드롭다운 설정 (A팀에서 선택된 유저 제외)"""
        options = []
        available_participants = [
            p for p in self.session.participants 
            if p['user_id'] not in self.selected_team_a
        ]
        
        for i, participant in enumerate(available_participants):
            options.append(discord.SelectOption(
                label=f"{participant['username']}",
                value=participant['user_id'],
                description="B팀 후보"
            ))
        
        self.team_b_select = discord.ui.Select(
            placeholder="🔴 B팀 5명을 선택하세요",
            options=options,
            min_values=5,
            max_values=5
        )
        self.team_b_select.callback = self.select_team_b_callback
        self.add_item(self.team_b_select)

        self.back_to_team_a_button = discord.ui.Button(
            label="← A팀 다시 선택",
            style=discord.ButtonStyle.secondary
        )
        self.back_to_team_a_button.callback = self.back_to_team_a_callback
        self.add_item(self.back_to_team_a_button)

    async def back_to_team_a_callback(self, interaction: discord.Interaction):
        """A팀 선택으로 되돌아가기"""
        self.selected_team_a = []  # A팀 선택 초기화
        
        embed = discord.Embed(
            title=f"🔵 {self.match_number}경기 A팀 선택",
            description="A팀에 포함될 5명을 다시 선택해주세요.",
            color=0x0099ff
        )
        
        # A팀 선택으로 되돌아가기
        self.clear_items()
        self.setup_team_a_selection()
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def select_team_b_callback(self, interaction: discord.Interaction):
        """B팀 선택 처리"""
        self.selected_team_b = self.team_b_select.values
        
        # A팀과 B팀 최종 확인
        team_a_users = []
        team_b_users = []
        
        for participant in self.session.participants:
            if participant['user_id'] in self.selected_team_a:
                team_a_users.append(participant['username'])
            elif participant['user_id'] in self.selected_team_b:
                team_b_users.append(participant['username'])
        
        embed = discord.Embed(
            title=f"🔵🔴 {self.match_number}경기 팀 구성 확인",
            color=0x0099ff
        )
        
        embed.add_field(
            name="🔵 A팀 (5명)",
            value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_a_users)]),
            inline=True
        )
        
        embed.add_field(
            name="🔴 B팀 (5명)",
            value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_b_users)]),
            inline=True
        )
        
        # 제외된 참가자들 표시
        excluded_participants = [
            p['username'] for p in self.session.participants 
            if p['user_id'] not in self.selected_team_a and p['user_id'] not in self.selected_team_b
        ]
        
        if excluded_participants:
            embed.add_field(
                name="⏸️ 이번 경기 미참여",
                value="\n".join([f"• {name}" for name in excluded_participants]),
                inline=False
            )
        
        embed.add_field(
            name="✅ 확인 후 다음 단계",
            value="팀 구성이 맞다면 '팀 구성 확인' 버튼을 눌러주세요.",
            inline=False
        )
        
        # 최종 확인 버튼
        self.clear_items()
        self.confirm_button = discord.ui.Button(
            label="팀 구성 확인",
            style=discord.ButtonStyle.success
        )
        self.confirm_button.callback = self.confirm_teams_callback
        self.add_item(self.confirm_button)
        
        # 다시 선택 버튼
        self.retry_button = discord.ui.Button(
            label="다시 선택하기",
            style=discord.ButtonStyle.secondary
        )
        self.retry_button.callback = self.retry_selection_callback
        self.add_item(self.retry_button)
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def confirm_teams_callback(self, interaction: discord.Interaction):
        """팀 구성 확인 및 저장 - 개선 버전"""
        try:
            # 팀 구성 저장
            team_a_data = []
            team_b_data = []
            
            for participant in self.session.participants:
                if participant['user_id'] in self.selected_team_a:
                    team_a_data.append(participant)
                elif participant['user_id'] in self.selected_team_b:
                    team_b_data.append(participant)
            
            # 매치 데이터 초기화
            self.session.matches[self.match_number] = {
                'team_a': team_a_data,
                'team_b': team_b_data,
                'team_a_positions': {},
                'team_b_positions': {},
                'winner': None,
                'completed': False
            }
            
            # 🆕 경기 기록으로 바로 진행
            await self.start_match_recording(interaction)
            
        except Exception as e:
            await interaction.response.send_message(
                f"팀 구성 저장 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    async def start_match_recording(self, interaction: discord.Interaction):
        """🆕 팀 구성 완료 후 바로 경기 기록 시작"""
        view = MatchResultView(self.bot, self.session, self.match_number, self.dashboard)
        
        match_data = self.session.matches[self.match_number]
        embed = discord.Embed(
            title=f"🎯 {self.match_number}경기 결과 기록",
            description="승리팀을 선택한 후, 각 팀의 포지션을 설정해주세요.",
            color=0x0099ff
        )
        
        # 팀 구성 표시
        team_a_list = [p['username'] for p in match_data['team_a']]
        team_b_list = [p['username'] for p in match_data['team_b']]
        
        embed.add_field(
            name="🔵 A팀",
            value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_a_list)]),
            inline=True
        )
        
        embed.add_field(
            name="🔴 B팀",
            value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_b_list)]),
            inline=True
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def retry_selection_callback(self, interaction: discord.Interaction):
        """팀 선택 다시 시작"""
        self.selected_team_a = []
        self.selected_team_b = []
        self.current_step = "team_a"
        
        embed = discord.Embed(
            title=f"🔵🔴 {self.match_number}경기 팀 구성",
            description="A팀에 포함될 5명을 선택해주세요.",
            color=0x0099ff
        )
        
        # A팀 선택부터 다시 시작
        self.clear_items()
        self.setup_team_a_selection()
        
        await interaction.response.edit_message(embed=embed, view=self)

class MatchResultView(discord.ui.View):
    """경기 결과 기록 View"""
    
    def __init__(self, bot, session: ScrimResultSession, match_number: int, dashboard: ScrimDashboardView):
        super().__init__(timeout=600)  # 10분
        self.bot = bot
        self.session = session
        self.match_number = match_number
        self.match_data = session.matches[match_number]
        self.current_step = "winner" 
        self.dashboard = dashboard
        
        # 승리팀 선택
        self.winner_select = discord.ui.Select(
            placeholder="승리팀을 선택하세요",
            options=[
                discord.SelectOption(label="🔵 A팀 승리", value="team_a", emoji="🔵"),
                discord.SelectOption(label="🔴 B팀 승리", value="team_b", emoji="🔴")
            ]
        )
        self.winner_select.callback = self.select_winner_callback
        self.add_item(self.winner_select)
    
    async def select_winner_callback(self, interaction: discord.Interaction):
        """승리팀 선택 처리 (수정된 버전)"""
        winner = self.winner_select.values[0]
        self.match_data['winner'] = winner
        
        # 승리팀 선택 확인 및 재선택 옵션 제공
        await self.show_winner_confirmation(interaction, winner)
    
    async def show_winner_confirmation(self, interaction: discord.Interaction, winner: str):
        """승리팀 선택 확인 단계"""
        winner_text = "🔵 A팀" if winner == "team_a" else "🔴 B팀"
        
        embed = discord.Embed(
            title=f"🏆 {self.match_number}경기 승리팀 선택",
            description=f"**{winner_text}**을(를) 승리팀으로 선택하셨습니다.",
            color=0x0099ff if winner == "team_a" else 0xff4444
        )
        
        # 팀 구성 재확인
        team_a_list = [p['username'] for p in self.match_data['team_a']]
        team_b_list = [p['username'] for p in self.match_data['team_b']]
        
        embed.add_field(
            name="🔵 A팀",
            value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_a_list)]),
            inline=True
        )
        
        embed.add_field(
            name="🔴 B팀", 
            value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_b_list)]),
            inline=True
        )
        
        self.clear_items()
        
        # 확인 후 포지션 선택 시작 버튼
        confirm_button = discord.ui.Button(
            label="포지션 선택 시작",
            style=discord.ButtonStyle.success,
            emoji="✅"
        )
        confirm_button.callback = self.start_position_selection
        self.add_item(confirm_button)
        
        # 승리팀 다시 선택 버튼
        retry_winner_button = discord.ui.Button(
            label="승리팀 다시 선택",
            style=discord.ButtonStyle.secondary,
            emoji="🔄"
        )
        retry_winner_button.callback = self.retry_winner_selection
        self.add_item(retry_winner_button)
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def start_position_selection(self, interaction: discord.Interaction):
        """포지션 선택 시작"""
        # A팀 포지션 선택 단계로 이동
        await self.show_position_selection(interaction, "team_a")
    
    async def retry_winner_selection(self, interaction: discord.Interaction):
        """승리팀 재선택"""
        self.match_data['winner'] = None
        
        embed = discord.Embed(
            title=f"🎯 {self.match_number}경기 결과 기록",
            description="승리팀을 다시 선택해주세요.",
            color=0x0099ff
        )
        
        # 팀 구성 표시
        team_a_list = [p['username'] for p in self.match_data['team_a']]
        team_b_list = [p['username'] for p in self.match_data['team_b']]
        
        embed.add_field(
            name="🔵 A팀",
            value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_a_list)]),
            inline=True
        )
        
        embed.add_field(
            name="🔴 B팀", 
            value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_b_list)]),
            inline=True
        )
        
        # 원래 승리팀 선택 상태로 되돌리기
        self.clear_items()
        self.winner_select = discord.ui.Select(
            placeholder="승리팀을 선택하세요",
            options=[
                discord.SelectOption(label="🔵 A팀 승리", value="team_a", emoji="🔵"),
                discord.SelectOption(label="🔴 B팀 승리", value="team_b", emoji="🔴")
            ]
        )
        self.winner_select.callback = self.select_winner_callback
        self.add_item(self.winner_select)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def show_position_selection(self, interaction, team: str):
        """포지션 선택 화면 표시"""
        team_data = self.match_data[team]
        team_name = "🔵 A팀" if team == "team_a" else "🔴 B팀"
        
        embed = discord.Embed(
            title=f"🎯 {self.match_number}경기 - {team_name} 포지션 선택",
            description="각 플레이어의 포지션을 선택해주세요",
            color=0x0099ff if team == "team_a" else 0xff4444
        )
        
        # 현재까지 설정된 정보 표시
        if self.match_data.get('winner'):
            winner_text = "🔵 A팀 승리" if self.match_data['winner'] == "team_a" else "🔴 B팀 승리"
            embed.add_field(name="🏆 승리팀", value=winner_text, inline=False)
        
        # 🔧 dashboard 전달
        view = PositionSelectionView(self.bot, self.session, self.match_number, team, self.dashboard)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)

class PositionSelectionView(discord.ui.View):
    """포지션 선택 시작 View"""
    
    def __init__(self, bot, session: ScrimResultSession, match_number: int, team: str, dashboard: ScrimDashboardView): 
        super().__init__(timeout=600)
        self.bot = bot
        self.session = session
        self.match_number = match_number
        self.team = team
        self.dashboard = dashboard
        self.current_player_index = 0
        self.team_data = session.matches[match_number][team]
        
        # 포지션 선택 진행 상황 추적
        self.position_selections = {}  # {player_index: selected_position}
        
        # 포지션 선택 시작 버튼
        self.start_button = discord.ui.Button(
            label="포지션 선택 시작",
            style=discord.ButtonStyle.primary,
            emoji="🎯"
        )
        self.start_button.callback = self.start_position_selection
        self.add_item(self.start_button)
    
    async def start_position_selection(self, interaction: discord.Interaction):
        """포지션 선택 시작 - 첫 번째 플레이어부터"""
        await self.show_single_player_position(interaction, 0)

    async def confirm_team_positions(self, interaction: discord.Interaction):
        """팀 포지션 확정"""
        # 포지션 데이터를 세션에 저장
        position_key = f"{self.team}_positions"
        for i, player in enumerate(self.team_data):
            position = self.position_selections[i]
            self.session.matches[self.match_number][position_key][player['user_id']] = position
        
        if self.team == "team_a":
            # A팀 완료 -> B팀으로 이동
            self.current_step = "set_positions_b"
            view = PositionSelectionView(self.bot, self.session, self.match_number, "team_b", self.dashboard)
            await view.show_single_player_position(interaction, 0)
        else:
            # B팀 완료 -> 최종 검토 단계로
            final_review = FinalReviewView(self.bot, self.session, self.match_number, self.dashboard)
            await final_review.show_final_review(interaction)

    async def retry_team_positions(self, interaction: discord.Interaction):
        """팀 포지션 다시 선택"""
        self.position_selections.clear()
        await self.show_single_player_position(interaction, 0)

    async def show_team_position_review(self, interaction: discord.Interaction):
        """팀 포지션 선택 검토 단계"""
        team_name = "🔵 A팀" if self.team == "team_a" else "🔴 B팀"
        
        embed = discord.Embed(
            title=f"📋 {self.match_number}경기 - {team_name} 포지션 검토",
            description="선택된 포지션을 확인해주세요",
            color=0x0099ff if self.team == "team_a" else 0xff4444
        )
        
        # 선택된 포지션 표시
        position_summary = []
        for i, player in enumerate(self.team_data):
            pos = self.position_selections[i]
            emoji = "🛡️" if pos == "탱커" else "⚔️" if pos == "딜러" else "💚"
            position_summary.append(f"{emoji} **{player['username']}** - {pos}")
        
        embed.add_field(
            name=f"{team_name} 포지션 구성",
            value="\n".join(position_summary),
            inline=False
        )
        
        # 포지션 구성 검증
        positions = list(self.position_selections.values())
        tank_count = positions.count("탱커")
        dps_count = positions.count("딜러")  
        support_count = positions.count("힐러")
        
        if tank_count == 1 and dps_count == 2 and support_count == 2:
            embed.add_field(
                name="✅ 구성 검증",
                value="올바른 구성 (탱1딜2힐2)",
                inline=False
            )
        else:
            embed.add_field(
                name="⚠️ 구성 확인",
                value=f"현재 구성: 탱{tank_count}딜{dps_count}힐{support_count}\n"
                      f"권장 구성: 탱1딜2힐2",
                inline=False
            )
        
        self.clear_items()
        
        # 확인 버튼
        confirm_button = discord.ui.Button(
            label="포지션 확정",
            style=discord.ButtonStyle.success,
            emoji="✅"
        )
        confirm_button.callback = self.confirm_team_positions
        self.add_item(confirm_button)
        
        # 다시 선택하기 버튼
        retry_button = discord.ui.Button(
            label="다시 선택하기",
            style=discord.ButtonStyle.secondary,
            emoji="🔄"
        )
        retry_button.callback = self.retry_team_positions
        self.add_item(retry_button)
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_single_player_position(self, interaction: discord.Interaction, player_index: int):
        """개별 플레이어 포지션 선택 (개선된 버전)"""
        self.current_player_index = player_index
        
        if player_index >= len(self.team_data):
            # 모든 플레이어 포지션 선택 완료 -> 검토 단계로
            await self.show_team_position_review(interaction)
            return
            
        player = self.team_data[player_index]
        team_name = "🔵 A팀" if self.team == "team_a" else "🔴 B팀"
        
        embed = discord.Embed(
            title=f"🎯 {self.match_number}경기 - {team_name} 포지션 선택",
            description=f"**{player['username']}**의 포지션을 선택해주세요 ({player_index + 1}/5)",
            color=0x0099ff if self.team == "team_a" else 0xff4444
        )
        
        # 진행 상황 표시 (개선된 부분)
        progress_text = []
        for i, p in enumerate(self.team_data):
            if i in self.position_selections:
                pos = self.position_selections[i]
                emoji = "🛡️" if pos == "탱커" else "⚔️" if pos == "딜러" else "💚"
                progress_text.append(f"{emoji} {p['username']} - {pos}")
            elif i == player_index:
                progress_text.append(f"➡️ {p['username']} - 선택 중...")
            else:
                progress_text.append(f"⏳ {p['username']} - 대기 중")
        
        embed.add_field(
            name="진행 상황",
            value="\n".join(progress_text),
            inline=False
        )
        
        self.clear_items()
        
        # 포지션 선택 드롭다운
        position_select = discord.ui.Select(
            placeholder="포지션을 선택하세요",
            options=[
                discord.SelectOption(label="탱커", value="탱커", emoji="🛡️"),
                discord.SelectOption(label="딜러", value="딜러", emoji="⚔️"),
                discord.SelectOption(label="힐러", value="힐러", emoji="💚")
            ]
        )
        position_select.callback = self.position_select_callback
        self.add_item(position_select)
        
        # 이전 플레이어로 되돌리기 버튼 (첫 번째 플레이어가 아닌 경우)
        if player_index > 0:
            back_button = discord.ui.Button(
                label="이전 플레이어로",
                style=discord.ButtonStyle.secondary,
                emoji="⬅️"
            )
            back_button.callback = self.back_to_previous_player
            self.add_item(back_button)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def position_select_callback(self, interaction: discord.Interaction):
        """포지션 선택 처리 (개선된 버전)"""
        selected_position = interaction.data['values'][0]
        self.position_selections[self.current_player_index] = selected_position
        
        # 다음 플레이어로 진행
        await self.show_single_player_position(interaction, self.current_player_index + 1)
    
    async def back_to_previous_player(self, interaction: discord.Interaction):
        """이전 플레이어로 되돌리기 (새로 추가된 기능)"""
        # 이전 플레이어의 선택 취소
        prev_index = self.current_player_index - 1
        if prev_index in self.position_selections:
            del self.position_selections[prev_index]
        
        # 이전 플레이어 선택 화면으로
        await self.show_single_player_position(interaction, prev_index)

class FinalReviewView(discord.ui.View):
    """최종 검토 단계 View"""
    
    def __init__(self, bot, session: ScrimResultSession, match_number: int, dashboard: ScrimDashboardView):
        super().__init__(timeout=600)
        self.bot = bot
        self.session = session
        self.match_number = match_number
        self.match_data = session.matches[match_number]
        self.dashboard = dashboard
    
    async def show_final_review(self, interaction: discord.Interaction):
        """경기 최종 검토 단계"""
        embed = discord.Embed(
            title=f"🎯 {self.match_number}경기 최종 검토",
            description="모든 설정을 확인해주세요",
            color=0x00ff88
        )
        
        # 승리팀 표시
        winner_text = "🔵 A팀" if self.match_data['winner'] == "team_a" else "🔴 B팀"
        embed.add_field(name="🏆 승리팀", value=winner_text, inline=False)
        
        # 양팀 포지션 구성 표시
        for team_key, team_name in [("team_a", "🔵 A팀"), ("team_b", "🔴 B팀")]:
            team_summary = []
            position_key = f"{team_key}_positions"
            
            for player in self.match_data[team_key]:
                pos = self.match_data[position_key][player['user_id']]
                emoji = "🛡️" if pos == "탱커" else "⚔️" if pos == "딜러" else "💚"
                team_summary.append(f"{emoji} {player['username']}")
            
            embed.add_field(
                name=team_name,
                value="\n".join(team_summary),
                inline=True
            )
        
        # 구성 검증 결과 표시
        validation_results = []
        for team_key, team_name in [("team_a", "A팀"), ("team_b", "B팀")]:
            position_key = f"{team_key}_positions"
            positions = list(self.match_data[position_key].values())
            tank_count = positions.count("탱커")
            dps_count = positions.count("딜러")
            support_count = positions.count("힐러")
            
            if tank_count == 1 and dps_count == 2 and support_count == 2:
                validation_results.append(f"✅ {team_name}: 올바른 구성")
            else:
                validation_results.append(f"⚠️ {team_name}: 탱{tank_count}딜{dps_count}힐{support_count}")
        
        embed.add_field(
            name="📊 구성 검증",
            value="\n".join(validation_results),
            inline=False
        )
        
        self.clear_items()
        
        # 최종 확인 버튼
        final_confirm_button = discord.ui.Button(
            label="경기 기록 완료",
            style=discord.ButtonStyle.success,
            emoji="✅"
        )
        final_confirm_button.callback = self.final_confirm_match
        self.add_item(final_confirm_button)
        
        # B팀 포지션 다시 선택
        retry_b_team_button = discord.ui.Button(
            label="B팀 포지션 재선택",
            style=discord.ButtonStyle.secondary,
            emoji="🔴"
        )
        retry_b_team_button.callback = self.retry_b_team_positions
        self.add_item(retry_b_team_button)
        
        # A팀 포지션 다시 선택
        retry_a_team_button = discord.ui.Button(
            label="A팀 포지션 재선택", 
            style=discord.ButtonStyle.secondary,
            emoji="🔵"
        )
        retry_a_team_button.callback = self.retry_a_team_positions
        self.add_item(retry_a_team_button)
        
        # 승리팀 다시 선택
        retry_winner_button = discord.ui.Button(
            label="승리팀 재선택",
            style=discord.ButtonStyle.secondary,
            emoji="🏆"
        )
        retry_winner_button.callback = self.retry_winner_selection
        self.add_item(retry_winner_button)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def retry_b_team_positions(self, interaction: discord.Interaction):
        """B팀 포지션 다시 선택"""
        # B팀 포지션 데이터 초기화
        self.match_data['team_b_positions'] = {}
        
        # B팀 포지션 선택 시작
        view = PositionSelectionView(self.bot, self.session, self.match_number, "team_b", self.dashboard)
        await view.show_single_player_position(interaction, 0)

    async def retry_a_team_positions(self, interaction: discord.Interaction):
        """A팀 포지션 다시 선택"""
        # A팀 포지션 데이터 초기화
        self.match_data['team_a_positions'] = {}
        
        # A팀 포지션 선택 시작
        view = PositionSelectionView(self.bot, self.session, self.match_number, "team_a", self.dashboard)
        await view.show_single_player_position(interaction, 0)

    async def retry_winner_selection(self, interaction: discord.Interaction):
        """승리팀 다시 선택"""
        # 승리팀 데이터 초기화
        self.match_data['winner'] = None
        
        # 승리팀 선택 화면으로 되돌아가기
        view = MatchResultView(self.bot, self.session, self.match_number)
        
        embed = discord.Embed(
            title=f"🎯 {self.match_number}경기 결과 기록",
            description="승리팀을 다시 선택해주세요.",
            color=0x0099ff
        )
        
        # 팀 구성 표시
        team_a_list = [p['username'] for p in self.match_data['team_a']]
        team_b_list = [p['username'] for p in self.match_data['team_b']]
        
        embed.add_field(
            name="🔵 A팀",
            value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_a_list)]),
            inline=True
        )
        
        embed.add_field(
            name="🔴 B팀", 
            value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_b_list)]),
            inline=True
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

    async def final_confirm_match(self, interaction: discord.Interaction):
        """포지션 설정 완료 후 맵 선택 단계로 이동 (기존 최종 확인 대신)"""
        # 🆕 맵 선택 단계로 이동
        view = MapSelectionView(self.bot, self.session, self.match_number, self.dashboard)
        
        embed = discord.Embed(
            title="🗺️ 맵 선택 (선택사항)",
            description="플레이한 맵을 기록하시겠습니까?\n맵별 통계를 위해 선택하시는 것을 권장합니다.",
            color=0x0099ff
        )
        
        # 현재까지의 경기 정보 요약 표시
        winner_text = "🔵 A팀" if self.match_data['winner'] == "team_a" else "🔴 B팀"
        embed.add_field(name="🏆 승리팀", value=winner_text, inline=True)
        
        # 포지션 구성 간단 요약
        team_summary = []
        for team_key, team_name in [("team_a", "🔵 A팀"), ("team_b", "🔴 B팀")]:
            position_key = f"{team_key}_positions"
            positions_count = {"탱커": 0, "딜러": 0, "힐러": 0}
            
            for player in self.match_data[team_key]:
                pos = self.match_data[position_key].get(player['user_id'], '미설정')
                if pos in positions_count:
                    positions_count[pos] += 1
            
            team_summary.append(f"{team_name}: 탱{positions_count['탱커']}딜{positions_count['딜러']}힐{positions_count['힐러']}")
        
        embed.add_field(
            name="👥 팀 구성", 
            value="\n".join(team_summary), 
            inline=True
        )
        
        embed.add_field(
            name="📊 맵 정보의 활용",
            value="• 개인/팀별 맵 승률 통계\n• 맵 타입별 성과 분석\n• 포지션-맵 조합 분석",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def save_match_to_database(self, guild_id: str):
        """매치 데이터를 데이터베이스에 저장"""
        try:
            # 매치 데이터 준비
            match_data_for_db = {
                'recruitment_id': self.session.recruitment_id,
                'match_number': self.match_number,
                'winner': self.match_data['winner'],
                'created_by': self.session.created_by,
                'guild_id': guild_id,
                'team_a': self.match_data['team_a'],
                'team_b': self.match_data['team_b'],
                'team_a_positions': self.match_data['team_a_positions'],
                'team_b_positions': self.match_data['team_b_positions']
            }
            
            # 데이터베이스에 저장
            match_id = await self.bot.db_manager.save_match_result(match_data_for_db)
            return match_id
            
        except Exception as e:
            print(f"매치 저장 실패: {e}")
            raise

class RetryPositionView(discord.ui.View):
    """포지션 재선택 View"""
    
    def __init__(self, bot, session: ScrimResultSession, match_number: int, team: str, dashboard: ScrimDashboardView):
        super().__init__(timeout=300)
        self.bot = bot
        self.session = session
        self.match_number = match_number
        self.team = team
        self.dashboard = dashboard
        
        # 다시 선택하기 버튼
        self.retry_button = discord.ui.Button(
            label="다시 선택하기",
            style=discord.ButtonStyle.primary,
            emoji="🔄"
        )
        self.retry_button.callback = self.retry_selection
        self.add_item(self.retry_button)
    
    async def retry_selection(self, interaction: discord.Interaction):
        """포지션 재선택 시작"""
        position_key = f"{self.team}_positions"
        self.session.matches[self.match_number][position_key] = {}
        
        view = PositionSelectionView(
            self.bot, self.session, self.match_number, self.team, self.dashboard
        )
        await view.show_single_player_position(interaction, 0)

class ScrimResultCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        return await self.bot.db_manager.is_server_admin(guild_id, user_id)
    
    @app_commands.command(name="내전결과시작", description="[관리자] 마감된 내전의 결과 기록을 시작합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def start_result_recording(self, interaction: discord.Interaction):
        """내전 결과 기록 시작"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # 마감된 내전 모집 조회
            guild_id = str(interaction.guild_id)

            # 기존 활성 세션 확인
            if guild_id in active_sessions:
                existing_session = active_sessions[guild_id]
                await interaction.followup.send(
                    f"❌ 이미 진행 중인 결과 기록 세션이 있습니다.\n"
                    f"세션 ID: {existing_session.session_id[:8]}...\n"
                    f"기존 대시보드를 사용하거나 세션을 취소해주세요.",
                    ephemeral=True
                )
                return
            
            completed_recruitments = await self.bot.db_manager.get_completed_recruitments(guild_id)
            
            if not completed_recruitments:
                await interaction.followup.send(
                    "❌ 마감된 내전 모집이 없습니다.\n"
                    "먼저 `/내전공지등록`으로 내전을 모집하고 마감시간이 지난 후 사용해주세요.",
                    ephemeral=True
                )
                return
            
            # 내전 선택 View 표시
            view = RecruitmentSelectView(self.bot, completed_recruitments, guild_id)
            embed = discord.Embed(
                title="📋 내전 결과 기록 시작",
                description="결과를 기록할 내전을 선택해주세요.",
                color=0x0099ff
            )
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 오류가 발생했습니다: {str(e)}", ephemeral=True
            )
    
    # @app_commands.command(name="팀세팅", description="[관리자] 특정 경기의 팀 구성을 설정합니다")
    # @app_commands.describe(경기번호="경기 번호 (1, 2, 3...)")
    # @app_commands.default_permissions(manage_guild=True)
    # async def setup_teams(self, interaction: discord.Interaction, 경기번호: int):
    #     """팀 구성 설정"""
    #     if not await self.is_admin(interaction):
    #         await interaction.response.send_message(
    #             "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
    #         )
    #         return
        
    #     guild_id = str(interaction.guild_id)
        
    #     # 활성 세션 확인
    #     if guild_id not in active_sessions:
    #         await interaction.response.send_message(
    #             "❌ 진행 중인 결과 기록 세션이 없습니다.\n"
    #             "`/내전결과시작` 명령어로 먼저 세션을 시작해주세요.",
    #             ephemeral=True
    #         )
    #         return
        
    #     session = active_sessions[guild_id]
        
    #     # 경기 번호 검증
    #     if 경기번호 < 1:
    #         await interaction.response.send_message(
    #             "❌ 경기 번호는 1 이상이어야 합니다.", ephemeral=True
    #         )
    #         return
        
    #     # 이미 설정된 경기 확인
    #     if 경기번호 in session.matches and session.matches[경기번호].get('completed'):
    #         await interaction.response.send_message(
    #             f"❌ {경기번호}경기는 이미 완료된 경기입니다.\n"
    #             "`/내전현황` 명령어로 현재 상태를 확인해주세요.",
    #             ephemeral=True
    #         )
    #         return
        
    #     # 팀 설정 View 표시
    #     view = TeamSetupView(self.bot, session, 경기번호)
    #     embed = discord.Embed(
    #         title=f"🔵🔴 {경기번호}경기 팀 구성",
    #         description="A팀에 포함될 5명을 선택해주세요. (나머지 5명은 자동으로 B팀이 됩니다)",
    #         color=0x0099ff
    #     )
        
    #     await interaction.response.send_message(embed=embed, view=view)
    
    # @app_commands.command(name="경기기록", description="[관리자] 경기 결과를 기록합니다")
    # @app_commands.describe(경기번호="기록할 경기 번호")
    # @app_commands.default_permissions(manage_guild=True)
    # async def record_match(self, interaction: discord.Interaction, 경기번호: int):
    #     """경기 결과 기록"""
    #     if not await self.is_admin(interaction):
    #         await interaction.response.send_message(
    #             "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
    #         )
    #         return
        
    #     guild_id = str(interaction.guild_id)
        
    #     # 활성 세션 확인
    #     if guild_id not in active_sessions:
    #         await interaction.response.send_message(
    #             "❌ 진행 중인 결과 기록 세션이 없습니다.", ephemeral=True
    #         )
    #         return
        
    #     session = active_sessions[guild_id]
        
    #     # 팀 구성 확인
    #     if 경기번호 not in session.matches:
    #         await interaction.response.send_message(
    #             f"❌ {경기번호}경기의 팀 구성이 설정되지 않았습니다.\n"
    #             f"`/팀세팅 {경기번호}` 명령어로 먼저 팀을 구성해주세요.",
    #             ephemeral=True
    #         )
    #         return
        
    #     # 이미 완료된 경기 확인
    #     if session.matches[경기번호].get('completed'):
    #         await interaction.response.send_message(
    #             f"❌ {경기번호}경기는 이미 기록이 완료되었습니다.", ephemeral=True
    #         )
    #         return
        
    #     # 경기 결과 기록 View 표시
    #     view = MatchResultView(self.bot, session, 경기번호)
        
    #     match_data = session.matches[경기번호]
    #     embed = discord.Embed(
    #         title=f"🎯 {경기번호}경기 결과 기록",
    #         description="승리팀을 선택한 후, 각 팀의 포지션을 설정해주세요.",
    #         color=0x0099ff
    #     )
        
    #     # 팀 구성 표시
    #     team_a_list = [p['username'] for p in match_data['team_a']]
    #     team_b_list = [p['username'] for p in match_data['team_b']]
        
    #     embed.add_field(
    #         name="🔵 A팀",
    #         value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_a_list)]),
    #         inline=True
    #     )
        
    #     embed.add_field(
    #         name="🔴 B팀", 
    #         value="\n".join([f"{i+1}. {name}" for i, name in enumerate(team_b_list)]),
    #         inline=True
    #     )
        
    #     await interaction.response.send_message(embed=embed, view=view)
    
    # @app_commands.command(name="내전현황", description="[관리자] 현재 내전 결과 기록 진행 상황을 확인합니다")
    # @app_commands.default_permissions(manage_guild=True)
    # async def check_progress(self, interaction: discord.Interaction):
    #     """진행 상황 확인"""
    #     if not await self.is_admin(interaction):
    #         await interaction.response.send_message(
    #             "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
    #         )
    #         return
        
    #     guild_id = str(interaction.guild_id)
        
    #     if guild_id not in active_sessions:
    #         await interaction.response.send_message(
    #             "❌ 진행 중인 결과 기록 세션이 없습니다.", ephemeral=True
    #         )
    #         return
        
    #     session = active_sessions[guild_id]
        
    #     embed = discord.Embed(
    #         title="📊 내전 결과 기록 현황",
    #         color=0x0099ff
    #     )
        
    #     # 세션 정보
    #     recruitment = await self.bot.db_manager.get_recruitment_by_id(session.recruitment_id)
    #     embed.add_field(
    #         name="🎮 내전 정보",
    #         value=f"**제목**: {recruitment['title']}\n"
    #               f"**참가자**: {len(session.participants)}명\n"
    #               f"**세션 시작**: <t:{int(session.created_at.timestamp())}:R>",
    #         inline=False
    #     )
        
    #     # 경기 진행 상황
    #     if session.matches:
    #         match_status = []
    #         for match_num in sorted(session.matches.keys()):
    #             match_data = session.matches[match_num]
    #             if match_data.get('completed'):
    #                 winner = "🔵 A팀" if match_data['winner'] == "team_a" else "🔴 B팀"
    #                 match_status.append(f"✅ {match_num}경기: {winner} 승리")
    #             else:
    #                 match_status.append(f"⏳ {match_num}경기: 진행 중")
            
    #         embed.add_field(
    #             name="🏆 경기 결과",
    #             value="\n".join(match_status) if match_status else "아직 기록된 경기가 없습니다.",
    #             inline=False
    #         )
    #     else:
    #         embed.add_field(
    #             name="🏆 경기 결과",
    #             value="아직 설정된 경기가 없습니다.\n`/팀세팅 1` 명령어로 첫 경기를 시작하세요.",
    #             inline=False
    #         )
        
    #     embed.set_footer(text=f"세션 ID: {session.session_id[:8]}...")
        
    #     await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="내전결과완료", description="[관리자] 모든 경기 기록을 완료하고 통계에 반영합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def complete_recording(self, interaction: discord.Interaction):
        """내전 결과 기록 완료"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        guild_id = str(interaction.guild_id)
        
        if guild_id not in active_sessions:
            await interaction.response.send_message(
                "❌ 진행 중인 결과 기록 세션이 없습니다.", ephemeral=True
            )
            return
        
        session = active_sessions[guild_id]
        
        # 완료된 경기 확인
        completed_matches = [
            num for num, data in session.matches.items() 
            if data.get('completed')
        ]
        
        if not completed_matches:
            await interaction.response.send_message(
                "❌ 완료된 경기가 없습니다.\n먼저 경기를 기록해주세요.", ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # 모든 매치 데이터를 데이터베이스에 저장하고 통계 업데이트
            completed_match_data = []
            total_saved = 0
            
            for match_num in completed_matches:
                match_data = session.matches[match_num].copy()
                match_data['guild_id'] = guild_id
                match_data['recruitment_id'] = session.recruitment_id
                match_data['match_number'] = match_num
                match_data['created_by'] = session.created_by
                
                # 개별 매치가 아직 저장되지 않았다면 저장
                if not match_data.get('saved_to_db'):
                    await self.bot.db_manager.save_match_result(match_data)
                    # 세션의 매치 데이터에도 플래그 설정
                    session.matches[match_num]['saved_to_db'] = True
                
                completed_match_data.append(match_data)
                total_saved += 1
            
            # 전체 세션 통계 업데이트
            await self.bot.db_manager.update_user_statistics(guild_id, completed_match_data)
            
            # 세션 종료
            del active_sessions[guild_id]
            
            embed = discord.Embed(
                title="🎉 내전 결과 기록 완료!",
                description=f"총 {total_saved}경기의 결과가 성공적으로 저장되었습니다.",
                color=0x00ff88
            )
            
            embed.add_field(
                name="📊 통계 업데이트",
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
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 완료 처리 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ScrimResultCommands(bot))