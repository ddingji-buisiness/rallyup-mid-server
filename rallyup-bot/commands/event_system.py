import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List
from datetime import datetime
from time import time
from config.settings import Settings, EventSystemSettings

logger = logging.getLogger(__name__)

class ViewConstants:
    """View 관련 상수"""
    TIMEOUT = 300  # 5분
    DISCORD_SELECT_MAX = 25  # Discord Select 최대 옵션 수
    
class DisplayConstants:
    """표시 관련 상수"""
    TOP_TEAMS_DISPLAY = 10  # 순위표에 표시할 최대 팀 수
    TOP_MISSIONS_DISPLAY = 3  # 인기 미션 TOP N
    RECENT_HISTORY_LIMIT = 5  # 최근 이력 표시 개수
    MISSION_HISTORY_LIMIT = 15  # 팀 미션 이력 조회 개수
    RECENT_ACTIVITIES_LIMIT = 10  # 최근 활동 표시 개수
    
class ScoreConstants:
    """점수 관련 상수"""
    DEFAULT_WORDLE_POINTS = 10000  # 기본 워들 포인트
    MIN_SCORE = 1000  # 최소 점수

class ErrorMessages:
    """표준화된 에러 메시지"""
    ADMIN_ONLY = "❌ 이 명령어는 관리자만 사용할 수 있습니다."
    NO_TEAMS = "❌ 생성된 팀이 없습니다.\n`/이벤트팀생성`으로 먼저 팀을 만들어주세요."
    NO_MISSIONS = "❌ 등록된 미션이 없습니다.\n`/이벤트미션등록`으로 먼저 미션을 등록해주세요."
    NO_MEMBERS = "❌ 서버에 봇이 아닌 멤버가 없습니다."
    TEAM_NOT_FOUND = "❌ '{team_name}' 팀을 찾을 수 없습니다."
    MISSION_NOT_FOUND = "❌ '{mission_name}' 미션을 찾을 수 없습니다."
    MISSION_INFO_NOT_FOUND = "❌ 미션 정보를 찾을 수 없습니다."
    NOT_IN_TEAM = "❌ 현재 이벤트 팀에 속해있지 않습니다.\n관리자에게 팀 배정을 요청하세요."
    NO_EVENT = "❌ 진행 중인 이벤트가 없습니다."
    SETUP_ERROR = "❌ 점수 부여 설정 중 오류가 발생했습니다."
    MIN_PARTICIPANTS = "❌ 최소 {min_count}명 이상 참여해야 합니다."
    INVALID_NUMBER = "❌ {field}는 숫자로 입력해주세요."
    POSITIVE_NUMBER = "❌ {field}는 1 이상이어야 합니다."
    DUPLICATE_EXISTS = "❌ '{name}'이(가) 이미 존재합니다."
    PARTICIPANTS_MIN = "❌ 참여 인원은 1명 이상이어야 합니다."
    POINTS_MIN = "❌ 점수는 1 이상이어야 합니다."

class SuccessMessages:
    """표준화된 성공 메시지"""
    TEAM_CREATED = "✅ **{team_name}** 팀이 생성되었습니다!"
    MISSION_CREATED = "✅ 미션 등록 완료"
    MISSION_DELETED = "🗑️ 미션 삭제 완료"
    MISSION_COMPLETED = "✅ 미션 완료 처리"
    MEMBER_ADDED = "✅ 팀원이 추가되었습니다."
    MEMBER_REMOVED = "✅ 팀원이 제거되었습니다."
    TEAM_DELETED = "✅ 팀이 삭제되었습니다."

class InfoMessages:
    """표준화된 안내 메시지"""
    SELECT_TEAM = "1단계: 점수를 부여할 팀을 선택하세요"
    SELECT_MISSION = "완료한 미션을 선택해주세요"
    SELECT_MEMBERS = "**{team_name}** 팀의 팀원을 선택해주세요:"
    TEAM_SELECTED = "✅ **{team_name}** 팀이 선택되었습니다.\n완료한 미션을 선택해주세요:"
    MEMBERS_SELECTED = "✅ {count}명의 팀원이 선택되었습니다.\n'팀 생성 완료' 버튼을 눌러주세요."
    CONFIRM_CREATION = "'팀 생성 완료' 버튼을 눌러주세요."
    CANCELLED = "❌ 점수 부여가 취소되었습니다."

class CancelPointsView(discord.ui.View):
    """점수 취소용 View (2단계: 팀 선택 → 점수 선택)"""
    
    def __init__(self, bot, guild_id: str, teams: List[Dict], all_items: List[Dict], admin_id: str):
        super().__init__(timeout=ViewConstants.TIMEOUT)
        self.bot = bot
        self.guild_id = guild_id
        self.teams = teams  # 모든 팀 목록
        self.all_items = all_items  # 모든 점수 내역
        self.admin_id = admin_id
        
        self.state = 'select_team'  # 'select_team' -> 'select_item' -> 'confirm'
        self.selected_team_id = None
        self.selected_team_name = None
        self.filtered_items = []
        self.selected_item = None
        
        # 초기: 팀 선택 드롭다운
        self._add_team_select()
    
    def _add_team_select(self):
        """1단계: 팀 선택 드롭다운"""
        options = []
        
        for team in self.teams[:25]:  # Discord 제한
            # 해당 팀의 점수 내역 개수 계산
            team_items = [
                item for item in self.all_items 
                if item['team_id'] == team['team_id']
            ]
            
            if not team_items:
                continue  # 점수 내역이 없는 팀은 제외
            
            mission_count = sum(1 for item in team_items if item['type'] == 'mission')
            voice_count = sum(1 for item in team_items if item['type'] == 'voice')
            
            label = f"🎯 {team['team_name']}"
            description = f"미션 {mission_count}개 | 음성 {voice_count}개"
            
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    description=description[:100],
                    value=team['team_id'],
                    emoji="🎯"
                )
            )
        
        if not options:
            options.append(
                discord.SelectOption(
                    label="취소할 내역이 없습니다",
                    value="none",
                    description="최근 24시간 내 점수 부여 내역이 없습니다"
                )
            )
        
        select = discord.ui.Select(
            placeholder="1단계: 팀을 선택하세요",
            options=options,
            custom_id="select_team"
        )
        select.callback = self.team_selected
        self.add_item(select)
    
    async def team_selected(self, interaction: discord.Interaction):
        """팀 선택 완료"""
        selected_team_id = interaction.data['values'][0]
        
        if selected_team_id == "none":
            await interaction.response.send_message(
                "❌ 취소할 내역이 없습니다.",
                ephemeral=True
            )
            return
        
        self.selected_team_id = selected_team_id
        
        # 선택된 팀 정보
        selected_team = next(
            (team for team in self.teams if team['team_id'] == selected_team_id),
            None
        )
        
        if not selected_team:
            await interaction.response.send_message(
                "❌ 팀을 찾을 수 없습니다.",
                ephemeral=True
            )
            return
        
        self.selected_team_name = selected_team['team_name']
        
        # 해당 팀의 점수 내역만 필터링
        self.filtered_items = [
            item for item in self.all_items 
            if item['team_id'] == selected_team_id
        ]
        
        if not self.filtered_items:
            await interaction.response.send_message(
                f"❌ **{self.selected_team_name}** 팀의 취소 가능한 점수 내역이 없습니다.",
                ephemeral=True
            )
            return
        
        # 2단계: 점수 내역 선택으로 전환
        self.state = 'select_item'
        self.clear_items()
        self._add_item_select()
        
        mission_count = sum(1 for item in self.filtered_items if item['type'] == 'mission')
        voice_count = sum(1 for item in self.filtered_items if item['type'] == 'voice')
        
        await interaction.response.edit_message(
            content=f"**{self.selected_team_name}** 팀 선택됨\n\n"
                    f"📊 총 **{len(self.filtered_items)}개**의 점수 내역\n"
                    f"📋 미션: {mission_count}개 | 🎤 음성: {voice_count}개\n\n"
                    f"취소할 점수를 선택하세요:",
            view=self
        )
    
    def _add_item_select(self):
        """2단계: 점수 내역 선택 드롭다운"""
        options = []
        
        for item in self.filtered_items[:25]:
            from datetime import datetime
            
            if item['type'] == 'mission':
                completed_time = datetime.fromisoformat(item['completed_at'])
                icon = "📋"
                label_prefix = "미션"
                description = f"{item['mission_name'][:80]}"  # 길이 제한
            else:  # voice
                completed_time = datetime.fromisoformat(item['awarded_at'])
                icon = "🎤"
                label_prefix = "음성"
                if item['is_bonus']:
                    description = f"보너스 ({item['member_count']}명, 1시간)"
                else:
                    description = f"일반 ({item['member_count']}명, {item['hours_completed']}시간)"
            
            now = datetime.now()
            time_diff = now - completed_time
            
            if time_diff.total_seconds() < 3600:
                time_str = f"{int(time_diff.total_seconds() / 60)}분 전"
            elif time_diff.total_seconds() < 86400:
                time_str = f"{int(time_diff.total_seconds() / 3600)}시간 전"
            else:
                time_str = completed_time.strftime("%m/%d %H:%M")
            
            points = item['points'] if item['type'] == 'mission' else item['points']
            label = f"{icon} [{time_str}] {label_prefix} +{points}점"
            
            if item['type'] == 'mission':
                value = f"mission:{item['completion_id']}"
            else:
                value = f"voice:{item['team_id']}:{item['date']}:{item['awarded_at']}"
            
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    description=description[:100],
                    value=value[:100],
                    emoji=icon
                )
            )
        
        select = discord.ui.Select(
            placeholder="2단계: 취소할 점수를 선택하세요",
            options=options,
            custom_id="select_item"
        )
        select.callback = self.item_selected
        self.add_item(select)
        
        # "다른 팀 선택" 버튼 추가
        back_btn = discord.ui.Button(
            label="◀️ 다른 팀 선택",
            style=discord.ButtonStyle.secondary,
            custom_id="back_to_teams"
        )
        back_btn.callback = self.back_to_teams
        self.add_item(back_btn)
    
    async def item_selected(self, interaction: discord.Interaction):
        """점수 내역 선택 완료"""
        selected_value = interaction.data['values'][0]
        
        parts = selected_value.split(':', 1)
        item_type = parts[0]
        
        if item_type == 'mission':
            completion_id = parts[1]
            self.selected_item = next(
                (item for item in self.filtered_items 
                 if item['type'] == 'mission' and item['completion_id'] == completion_id),
                None
            )
        else:  # voice
            _, team_id, date, awarded_at = selected_value.split(':', 3)
            self.selected_item = next(
                (item for item in self.filtered_items 
                 if item['type'] == 'voice' 
                 and item['team_id'] == team_id 
                 and item['date'] == date
                 and item['awarded_at'] == awarded_at),
                None
            )
        
        if not self.selected_item:
            await interaction.response.send_message(
                "❌ 선택한 내역을 찾을 수 없습니다.",
                ephemeral=True
            )
            return
        
        # 3단계: 확인 단계
        self.state = 'confirm'
        self.clear_items()
        
        confirm_btn = discord.ui.Button(
            label="✅ 점수 취소 확정",
            style=discord.ButtonStyle.danger,
            custom_id="confirm_cancel"
        )
        confirm_btn.callback = self.confirm_cancel
        self.add_item(confirm_btn)
        
        reselect_btn = discord.ui.Button(
            label="🔄 다시 선택",
            style=discord.ButtonStyle.secondary,
            custom_id="reselect"
        )
        reselect_btn.callback = self.reselect
        self.add_item(reselect_btn)
        
        back_btn = discord.ui.Button(
            label="◀️ 다른 팀 선택",
            style=discord.ButtonStyle.secondary,
            custom_id="back_to_teams"
        )
        back_btn.callback = self.back_to_teams
        self.add_item(back_btn)
        
        cancel_btn = discord.ui.Button(
            label="❌ 취소",
            style=discord.ButtonStyle.secondary,
            custom_id="cancel_action"
        )
        cancel_btn.callback = self.cancel_action
        self.add_item(cancel_btn)
        
        # 확인 메시지
        if self.selected_item['type'] == 'mission':
            completed_time = datetime.fromisoformat(self.selected_item['completed_at'])
            content = (
                f"**다음 미션 점수 부여를 취소하시겠습니까?**\n\n"
                f"📋 **타입**: 미션 완료\n"
                f"🎯 **팀**: {self.selected_item['team_name']}\n"
                f"📋 **미션**: {self.selected_item['mission_name']}\n"
                f"💰 **점수**: +{self.selected_item['points']}점\n"
                f"👥 **참여 인원**: {self.selected_item['participants_count']}명\n"
                f"⏰ **부여 시간**: <t:{int(completed_time.timestamp())}:F>\n\n"
                f"⚠️ **경고**: 이 작업은 되돌릴 수 없습니다!"
            )
        else:  # voice
            awarded_time = datetime.fromisoformat(self.selected_item['awarded_at'])
            activity_type = "🎉 보너스 모드" if self.selected_item['is_bonus'] else "⏱️ 일반 모드"
            content = (
                f"**다음 음성 활동 점수를 취소하시겠습니까?**\n\n"
                f"🎤 **타입**: 음성 활동\n"
                f"🎯 **팀**: {self.selected_item['team_name']}\n"
                f"📊 **모드**: {activity_type}\n"
                f"💰 **점수**: +{self.selected_item['points']}점\n"
                f"👥 **참여 인원**: {self.selected_item['member_count']}명\n"
                f"⏰ **획득 시간**: <t:{int(awarded_time.timestamp())}:F>\n\n"
                f"⚠️ **경고**: 이 작업은 되돌릴 수 없습니다!"
            )
        
        await interaction.response.edit_message(
            content=content,
            view=self
        )
    
    async def confirm_cancel(self, interaction: discord.Interaction):
        """점수 취소 확정"""
        await interaction.response.defer()
        
        if self.selected_item['type'] == 'mission':
            success, message, cancelled_info = await self.bot.db_manager.cancel_mission_completion(
                completion_id=self.selected_item['completion_id'],
                cancelled_by=self.admin_id,
                reason="관리자 수동 취소"
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 미션 점수 취소 완료",
                    description=f"**{cancelled_info['team_name']}** 팀의 미션 점수가 취소되었습니다.",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📋 취소된 내역",
                    value=f"**미션**: {cancelled_info['mission_name']}\n"
                          f"**점수**: -{cancelled_info['awarded_points']}점\n"
                          f"**참여**: {cancelled_info['participants_count']}명",
                    inline=False
                )
                
                announcement_msg = (
                    f"⚠️ **{cancelled_info['team_name']}** 팀의 "
                    f"**{cancelled_info['mission_name']}** 미션 점수 "
                    f"**({cancelled_info['awarded_points']}점)**가 취소되었습니다."
                )
        else:  # voice
            success, message, cancelled_info = await self.bot.db_manager.cancel_voice_score(
                team_id=self.selected_item['team_id'],
                date=self.selected_item['date'],
                awarded_at=self.selected_item['awarded_at'],
                cancelled_by=self.admin_id,
                reason="관리자 수동 취소"
            )
            
            if success:
                activity_type = "보너스" if cancelled_info['is_bonus'] else f"{cancelled_info['hours_completed']}시간"
                embed = discord.Embed(
                    title="✅ 음성 활동 점수 취소 완료",
                    description=f"**{cancelled_info['team_name']}** 팀의 음성 점수가 취소되었습니다.",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="🎤 취소된 내역",
                    value=f"**활동**: {activity_type}\n"
                          f"**점수**: -{cancelled_info['points']}점\n"
                          f"**인원**: {cancelled_info['member_count']}명",
                    inline=False
                )
                
                announcement_msg = (
                    f"⚠️ **{cancelled_info['team_name']}** 팀의 "
                    f"음성 활동 점수 **({cancelled_info['points']}점)**가 취소되었습니다."
                )
        
        if success:
            embed.set_footer(text=f"취소자: {interaction.user.name}")
            
            self.clear_items()
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                content=None,
                embed=embed,
                view=self
            )
            
            # 공지 채널 알림
            channel_id = await self.bot.db_manager.get_event_announcement_channel(self.guild_id)
            if channel_id:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    try:
                        await channel.send(announcement_msg)
                    except:
                        pass
        else:
            await interaction.followup.send(
                f"❌ 점수 취소 실패: {message}",
                ephemeral=True
            )
    
    async def reselect(self, interaction: discord.Interaction):
        """같은 팀에서 다시 선택"""
        self.state = 'select_item'
        self.selected_item = None
        self.clear_items()
        self._add_item_select()
        
        mission_count = sum(1 for item in self.filtered_items if item['type'] == 'mission')
        voice_count = sum(1 for item in self.filtered_items if item['type'] == 'voice')
        
        await interaction.response.edit_message(
            content=f"**{self.selected_team_name}** 팀\n\n"
                    f"📊 총 **{len(self.filtered_items)}개**의 점수 내역\n"
                    f"📋 미션: {mission_count}개 | 🎤 음성: {voice_count}개\n\n"
                    f"취소할 점수를 선택하세요:",
            view=self
        )
    
    async def back_to_teams(self, interaction: discord.Interaction):
        """팀 선택으로 돌아가기"""
        self.state = 'select_team'
        self.selected_team_id = None
        self.selected_team_name = None
        self.filtered_items = []
        self.selected_item = None
        self.clear_items()
        self._add_team_select()
        
        await interaction.response.edit_message(
            content="1단계: 점수를 취소할 팀을 선택하세요:",
            view=self
        )
    
    async def cancel_action(self, interaction: discord.Interaction):
        """전체 취소"""
        await interaction.response.edit_message(
            content="❌ 점수 취소 작업이 취소되었습니다.",
            view=None
        )

class TeamManagementView(discord.ui.View):
    """팀 생성 시 팀원 선택용 View (UserSelect 사용)"""
    
    def __init__(self, bot, guild: discord.Guild, team_name: str, admin_id: str):
        super().__init__(timeout=ViewConstants.TIMEOUT)
        self.bot = bot
        self.guild = guild
        self.team_name = team_name
        self.admin_id = admin_id
        self.selected_members = []  # [(user_id, username), ...]
        self.view_id = f"{guild.id}_{id(self)}"
        
        # UserSelect 추가
        self._add_user_select()
    
    def _add_user_select(self):
        """Discord 네이티브 유저 선택 UI 추가"""
        user_select = discord.ui.UserSelect(
            placeholder="팀원을 선택하세요 (최대 25명)",
            min_values=1,
            max_values=25,
            custom_id=f"team_user_select_{self.view_id}"
        )
        user_select.callback = self.user_selected
        self.add_item(user_select)
    
    async def user_selected(self, interaction: discord.Interaction):
        """유저 선택 완료"""
        # 선택된 유저들 처리
        selected_users = interaction.data['values']  # User IDs
        
        # 봇 필터링 및 데이터 수집
        valid_members = []
        bot_count = 0
        
        for user_id in selected_users:
            member = self.guild.get_member(int(user_id))
            if member:
                if not member.bot:
                    # 중복 체크
                    if user_id not in [uid for uid, _ in self.selected_members]:
                        valid_members.append((user_id, member.display_name))
                else:
                    bot_count += 1
        
        if not valid_members:
            await interaction.response.send_message(
                "❌ 유효한 팀원이 없습니다. 봇이 아닌 멤버를 선택해주세요.",
                ephemeral=True
            )
            return
        
        # 기존 선택에 추가
        self.selected_members.extend(valid_members)
        
        # View 업데이트
        self.clear_items()
        
        # "더 추가하기" 버튼 (25명 미만일 때만)
        if len(self.selected_members) < 25:
            add_more_btn = discord.ui.Button(
                label=f"➕ 팀원 더 추가 (현재 {len(self.selected_members)}명)",
                style=discord.ButtonStyle.secondary
            )
            add_more_btn.callback = self.add_more_members
            self.add_item(add_more_btn)
        
        # "팀 생성 완료" 버튼
        confirm_btn = discord.ui.Button(
            label=f"✅ 팀 생성 완료 ({len(self.selected_members)}명)",
            style=discord.ButtonStyle.success
        )
        confirm_btn.callback = self.confirm_team_creation
        self.add_item(confirm_btn)
        
        # "취소" 버튼
        cancel_btn = discord.ui.Button(
            label="❌ 취소",
            style=discord.ButtonStyle.danger
        )
        cancel_btn.callback = self.cancel_creation
        self.add_item(cancel_btn)
        
        # 선택된 멤버 목록 표시
        members_preview = "\n".join([
            f"• <@{user_id}>" for user_id, _ in self.selected_members[:10]
        ])
        
        if len(self.selected_members) > 10:
            members_preview += f"\n... 외 {len(self.selected_members) - 10}명"
        
        warning = ""
        if bot_count > 0:
            warning = f"\n⚠️ {bot_count}개의 봇 계정은 제외되었습니다."
        
        await interaction.response.edit_message(
            content=f"**{self.team_name}** 팀원 선택 중\n\n"
                    f"**선택된 팀원 ({len(self.selected_members)}명):**\n"
                    f"{members_preview}"
                    f"{warning}\n\n"
                    f"{'더 추가하거나 ' if len(self.selected_members) < 25 else ''}"
                    f"'팀 생성 완료' 버튼을 눌러주세요.",
            view=self
        )
    
    async def add_more_members(self, interaction: discord.Interaction):
        """팀원 추가 선택"""
        # View 초기화하고 다시 UserSelect 추가
        self.clear_items()
        self._add_user_select()
        
        # 현재 선택된 멤버 표시
        members_preview = "\n".join([
            f"• <@{user_id}>" for user_id, _ in self.selected_members[:10]
        ])
        
        if len(self.selected_members) > 10:
            members_preview += f"\n... 외 {len(self.selected_members) - 10}명"
        
        await interaction.response.edit_message(
            content=f"**{self.team_name}** 팀원 추가 선택\n\n"
                    f"**현재 선택된 팀원 ({len(self.selected_members)}명):**\n"
                    f"{members_preview}\n\n"
                    f"추가할 팀원을 선택해주세요:",
            view=self
        )
    
    async def confirm_team_creation(self, interaction: discord.Interaction):
        """팀 생성 확정"""
        await interaction.response.defer(ephemeral=True)
        
        if not self.selected_members:
            await interaction.followup.send(
                "❌ 최소 1명 이상의 팀원을 선택해주세요.",
                ephemeral=True
            )
            return
        
        # DB에 팀 생성
        success, result = await self.bot.db_manager.create_event_team(
            guild_id=str(self.guild.id),
            team_name=self.team_name,
            member_ids=self.selected_members,
            created_by=self.admin_id
        )
        
        if success:
            embed = discord.Embed(
                title="✅ 팀 생성 완료",
                description=f"**{self.team_name}** 팀이 생성되었습니다!",
                color=EventSystemSettings.Colors.SUCCESS,
                timestamp=datetime.now()
            )
            
            # 팀원 목록 (최대 20명까지 표시)
            members_text = "\n".join([
                f"• <@{user_id}>" for user_id, _ in self.selected_members[:20]
            ])
            
            if len(self.selected_members) > 20:
                members_text += f"\n... 외 {len(self.selected_members) - 20}명"
            
            embed.add_field(
                name=f"👥 팀원 ({len(self.selected_members)}명)",
                value=members_text,
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                f"❌ 팀 생성 실패: {result}",
                ephemeral=True
            )
        
        # 원본 메시지 삭제
        try:
            await interaction.message.delete()
        except:
            pass
        
        self.stop()
    
    async def cancel_creation(self, interaction: discord.Interaction):
        """팀 생성 취소"""
        await interaction.response.edit_message(
            content="❌ 팀 생성이 취소되었습니다.",
            view=None
        )
        self.stop()
    
    async def on_timeout(self):
        """View 타임아웃 시 처리"""
        for item in self.children:
            item.disabled = True

class MissionCreateModal(discord.ui.Modal, title="미션 등록"):
    """미션 생성용 Modal"""
    
    mission_name = discord.ui.TextInput(
        label="미션 이름",
        placeholder="예: 오버워치 3연승",
        max_length=100,
        required=True
    )
    
    description = discord.ui.TextInput(
        label="미션 설명",
        placeholder="상세한 미션 내용을 입력하세요",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False
    )
    
    base_points = discord.ui.TextInput(
        label="기본 점수",
        placeholder="예: 10",
        max_length=5,
        required=True
    )
    
    min_participants = discord.ui.TextInput(
        label="최소 참여 인원",
        placeholder="예: 1 (기본값)",
        max_length=2,
        required=False,
        default="1"
    )
    
    def __init__(self, bot, guild_id: str, category: str):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.category = category
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 점수 검증
            points = int(self.base_points.value)
            if points <= 0:
                await interaction.followup.send(
                    ErrorMessages.POSITIVE_NUMBER.format(field="점수"),
                    ephemeral=True
                )
                return
            
            # 최소 인원 검증
            min_part = int(self.min_participants.value or "1")
            if min_part <= 0:
                await interaction.followup.send(
                    ErrorMessages.POSITIVE_NUMBER.format(field="최소 참여 인원"),
                    ephemeral=True
                )
                return
            
            # 미션 생성
            success, result = await self.bot.db_manager.create_event_mission(
                guild_id=self.guild_id,
                mission_name=self.mission_name.value,
                description=self.description.value or "",
                base_points=points,
                category=self.category,
                min_participants=min_part
            )
            
            if success:
                # 카테고리 이모지 매핑
                category_emoji = {
                    'daily': '📅',
                    'online': '💻',
                    'offline': '🏃',
                    'hidden': '🎁'
                }
                
                category_name = {
                    'daily': '일일 퀘스트',
                    'online': '온라인',
                    'offline': '오프라인',
                    'hidden': '히든 미션'
                }
                
                embed = discord.Embed(
                    title=SuccessMessages.MISSION_CREATED,
                    description=f"{category_emoji.get(self.category, '📋')} **{self.mission_name.value}**",
                    color=0x00ff88,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📋 미션 정보",
                    value=f"**카테고리**: {category_name.get(self.category, self.category)}\n"
                          f"**기본 점수**: {points}점\n"
                          f"**최소 인원**: {min_part}명\n"
                          f"**설명**: {self.description.value or '없음'}",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ 미션 등록 실패: {result}",
                    ephemeral=True
                )
                
        except ValueError:
            await interaction.followup.send(
                ErrorMessages.INVALID_NUMBER.format(field="점수 또는 최소 참여 인원"),
                ephemeral=True
            )

class ScoreAwardView(discord.ui.View):
    """미션 완료 점수 부여용 View"""
    
    def __init__(self, bot, guild_id: str, admin_id: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.admin_id = admin_id
        
        self.selected_team = None
        self.selected_mission = None
        self.participants_count = None
        
        # 초기 단계: 팀 선택
        self.current_step = "team"
        self.add_team_select()
    
    def add_team_select(self):
        """팀 선택 드롭다운 추가"""
        async def get_teams():
            return await self.bot.db_manager.get_event_teams(self.guild_id)
        
        # 비동기 함수를 동기로 실행할 수 없으므로 버튼으로 대체
        # 실제로는 명령어 호출 시 팀 목록을 미리 가져와서 View에 전달
        pass
    
    async def setup_team_select(self):
        """팀 선택 설정 (비동기)"""
        teams = await self.bot.db_manager.get_event_teams(self.guild_id)
        
        if not teams:
            return False
        
        options = []
        for team in teams[:25]:  # Discord 제한
            options.append(
                discord.SelectOption(
                    label=team['team_name'],
                    value=team['team_id'],
                    description=f"팀원: {team['member_count']}명"
                )
            )
        
        select = discord.ui.Select(
            placeholder=InfoMessages.SELECT_TEAM,
            options=options
        )
        select.callback = self.team_selected
        self.add_item(select)
        return True
    
    async def team_selected(self, interaction: discord.Interaction):
        """팀 선택 완료"""
        self.selected_team = interaction.data['values'][0]
        
        # 팀 정보 조회
        team_info = await self.bot.db_manager.get_event_team_details(self.selected_team)
        
        # ✅ 먼저 View 수정
        self.clear_items()
        await self.setup_mission_select()
        
        # ✅ 그 다음 메시지 업데이트
        await interaction.response.edit_message(
            content=InfoMessages.TEAM_SELECTED.format(team_name=team_info['team_name']),
            view=self
        )
    
    async def setup_mission_select(self):
        """미션 선택 설정"""
        missions = await self.bot.db_manager.get_event_missions(self.guild_id)
        
        if not missions:
            # 미션이 없으면 취소 버튼만 추가
            cancel_btn = discord.ui.Button(
                label="❌ 취소",
                style=discord.ButtonStyle.danger
            )
            cancel_btn.callback = self.cancel_callback
            self.add_item(cancel_btn)
            return False
        
        # 카테고리별로 그룹화하여 옵션 생성
        options = []
        category_emoji = {
            'daily': '📅',
            'online': '💻',
            'offline': '🏃',
            'hidden': '🎁'
        }
        
        for mission in missions[:25]:  # Discord 제한
            options.append(
                discord.SelectOption(
                    label=mission['mission_name'][:100],
                    value=mission['mission_id'],
                    description=f"{mission['base_points']}점 | 최소 {mission['min_participants']}명"[:100],
                    emoji=category_emoji.get(mission['category'], '📋')
                )
            )
        
        select = discord.ui.Select(
            placeholder="완료한 미션을 선택하세요",
            options=options,
            custom_id=f"mission_select_{self.guild_id}_{id(self)}"
        )
        select.callback = self.mission_selected
        self.add_item(select)
        
        # 취소 버튼 추가
        cancel_btn = discord.ui.Button(
            label="❌ 취소",
            style=discord.ButtonStyle.danger,
            row=1
        )
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)
        
        return True

    async def cancel_callback(self, interaction: discord.Interaction):
        """취소 버튼 콜백"""
        await interaction.response.edit_message(
            content=InfoMessages.CANCELLED,
            view=None
        )
        self.stop()
    
    async def mission_selected(self, interaction: discord.Interaction):
        """미션 선택 완료"""
        self.selected_mission = interaction.data['values'][0]
        
        # 미션 정보 조회
        mission_info = await self.bot.db_manager.get_event_mission_details(
            self.selected_mission
        )
        
        if not mission_info:
            await interaction.response.send_message(
                ErrorMessages.MISSION_INFO_NOT_FOUND,
                ephemeral=True
            )
            self.stop()
            return
        
        modal = ParticipantsModal(self, mission_info)
        await interaction.response.send_modal(modal)

    async def on_timeout(self):
        """View 타임아웃 시 처리"""
        for item in self.children:
            item.disabled = True

class ParticipantsModal(discord.ui.Modal, title="참여 인원 입력"):
    """미션 참여 인원 입력"""
    
    participants = discord.ui.TextInput(
        label="참여 인원 수",
        placeholder="예: 4",
        max_length=2,
        required=True
    )
    
    notes = discord.ui.TextInput(
        label="메모 (선택사항)",
        placeholder="추가 메모가 있다면 입력하세요",
        style=discord.TextStyle.paragraph,
        max_length=200,
        required=False
    )
    
    def __init__(self, parent_view: ScoreAwardView, mission_info: dict):
        super().__init__()
        self.parent_view = parent_view
        self.mission_info = mission_info
        
        # 최소 인원 힌트 추가
        self.participants.placeholder = f"최소 {mission_info['min_participants']}명 이상"
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 인원 수 검증
            count = int(self.participants.value)
            if count <= 0:
                await interaction.followup.send(
                    "❌ 참여 인원은 1명 이상이어야 합니다.",
                    ephemeral=True
                )
                return
            
            # 미션 완료 기록
            success, message, awarded_points = await self.parent_view.bot.db_manager.record_mission_completion(
                team_id=self.parent_view.selected_team,
                mission_id=self.parent_view.selected_mission,
                participants_count=count,
                completed_by=self.parent_view.admin_id,
                notes=self.notes.value or None
            )
            
            if success:
                # 팀 정보
                team_info = await self.parent_view.bot.db_manager.get_event_team_details(
                    self.parent_view.selected_team
                )
                
                # 총점 계산
                total_score = await self.parent_view.bot.db_manager.get_team_total_score(
                    self.parent_view.selected_team
                )
                
                embed = discord.Embed(
                    title="✅ 미션 완료 처리",
                    description=f"**{team_info['team_name']}** 팀에 점수가 부여되었습니다!",
                    color=0x00ff88,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="🎯 완료한 미션",
                    value=f"**{self.mission_info['mission_name']}**\n"
                        f"카테고리: {self.mission_info['category']}",
                    inline=False
                )
                
                embed.add_field(
                    name="👥 참여 정보",
                    value=f"참여 인원: {count}명\n"
                        f"최소 요구: {self.mission_info['min_participants']}명",
                    inline=True
                )
                
                # 점수 상세 표시 개선
                score_detail = f"**기본 점수**: {self.mission_info['base_points']}점\n"
                
                # 일일 퀘스트 보너스 표시
                if self.mission_info['category'] == 'daily':
                    if count >= 5:
                        score_detail += f"**5명 이상 보너스**: +1점\n"
                    
                    # 올클리어 보너스 확인
                    if "올클리어" in message:
                        score_detail += f"**올클리어 보너스**: +5점\n"
                
                score_detail += f"━━━━━━━━━━━━━━\n**총 획득**: **+{awarded_points}점**\n"
                score_detail += f"**팀 총점**: **{total_score}점**"
                
                embed.add_field(
                    name="🏆 점수",
                    value=score_detail,
                    inline=True
                )
                
                if self.notes.value:
                    embed.add_field(
                        name="📝 메모",
                        value=self.notes.value,
                        inline=False
                    )
                
                # 올클리어 축하 메시지
                if "올클리어" in message:
                    embed.add_field(
                        name="🎉 특별 달성!",
                        value="**일일 퀘스트 올클리어!**\n"
                            "5개 미션을 모두 완료하여 보너스 점수를 획득했습니다!",
                        inline=False
                    )
                
                embed.set_footer(text=f"처리자: {interaction.user.display_name}")
                
                await interaction.followup.send(embed=embed, ephemeral=True)

                # 공지 채널에 메시지 발송
                await self.send_announcement(
                    interaction.guild,
                    team_info,
                    self.mission_info,
                    awarded_points,
                    "올클리어" in message
                )
                
            else:
                # ✅ 에러 메시지 표시 개선
                embed = discord.Embed(
                    title="❌ 미션 완료 처리 실패",
                    description=message,
                    color=0xff6b6b,
                    timestamp=datetime.now()
                )
                
                # 이미 완료한 미션인 경우 추가 안내
                if "이미 완료" in message:
                    embed.add_field(
                        name="💡 안내",
                        value="일일 퀘스트는 하루에 한 번만 완료할 수 있습니다.\n"
                            "내일 다시 도전해주세요!",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except ValueError:
            await interaction.followup.send(
                "❌ 참여 인원은 숫자로 입력해주세요.",
                ephemeral=True
            )
        except Exception as e:
            print(f"❌ ParticipantsModal 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                "❌ 예상치 못한 오류가 발생했습니다. 관리자에게 문의하세요.",
                ephemeral=True
            )
        
        self.parent_view.stop()

    async def send_announcement(
        self,
        guild: discord.Guild,
        team_info: dict,
        mission_info: dict,
        awarded_points: int,
        is_all_clear: bool
    ):
        """공지 채널에 미션 완료 메시지 발송"""
        try:
            # 공지 채널 조회
            channel_id = await self.parent_view.bot.db_manager.get_event_announcement_channel(
                str(guild.id)
            )
            
            if not channel_id:
                print("ℹ️ 공지 채널이 설정되지 않음")
                return
            
            channel = guild.get_channel(int(channel_id))
            if not channel:
                print(f"⚠️ 공지 채널을 찾을 수 없음: {channel_id}")
                return
            
            # ✅ 심플한 한 줄 메시지
            emoji = "🎉" if is_all_clear else "✅"
            all_clear_text = " **(올클리어!)**" if is_all_clear else ""
            
            message = (
                f"{emoji} **{team_info['team_name']}** 팀이 "
                f"'{mission_info['mission_name']}' 미션을 완료했습니다! "
                f"**(+{awarded_points}점)**{all_clear_text}"
            )
            
            await channel.send(message)
            print(f"✅ 공지 발송 완료: {team_info['team_name']} - {mission_info['mission_name']}")
            
        except discord.Forbidden:
            print(f"❌ 공지 채널 권한 없음: {channel_id}")
        except Exception as e:
            print(f"❌ 공지 발송 실패: {e}")
            import traceback
            traceback.print_exc()

class ManualScoreAdjustmentView(discord.ui.View):
    """팀 선택용 View"""
    
    def __init__(self, bot, guild_id: str):
        super().__init__(timeout=ViewConstants.TIMEOUT)
        self.bot = bot
        self.guild_id = guild_id
    
    async def setup_team_select(self):
        """팀 선택 드롭다운 설정"""
        teams = await self.bot.db_manager.get_event_teams(self.guild_id)
        
        if not teams:
            return False
        
        options = []
        for team in teams[:25]:  # Discord 제한
            # 현재 점수 조회
            total_score = await self.bot.db_manager.get_team_total_score(team['team_id'])
            
            options.append(
                discord.SelectOption(
                    label=team['team_name'],
                    value=team['team_id'],
                    description=f"현재 점수: {total_score}점 | 팀원: {team['member_count']}명",
                    emoji="🎯"
                )
            )
        
        select = discord.ui.Select(
            placeholder="점수를 조정할 팀을 선택하세요",
            options=options,
            custom_id="select_team_for_adjustment"
        )
        select.callback = self.team_selected
        self.add_item(select)
        
        return True
    
    async def team_selected(self, interaction: discord.Interaction):
        """팀 선택 완료 → Modal 표시"""
        team_id = interaction.data['values'][0]
        
        # 선택된 팀 정보
        team_info = await self.bot.db_manager.get_event_team_details(team_id)
        
        if not team_info:
            await interaction.response.send_message(
                "❌ 팀을 찾을 수 없습니다.",
                ephemeral=True
            )
            return
        
        # Modal 표시
        modal = ManualScoreModal(self, team_id, team_info['team_name'])
        await interaction.response.send_modal(modal)

class ManualScoreModal(discord.ui.Modal, title="팀 점수 수동 조정"):
    """점수와 사유를 입력받는 Modal"""
    
    score_input = discord.ui.TextInput(
        label="점수 (양수: 추가, 음수: 차감)",
        placeholder="예: +10, -5, 15",
        max_length=5,
        required=True
    )
    
    reason = discord.ui.TextInput(
        label="조정 사유",
        placeholder="예: 특별 보너스, 규칙 위반 페널티",
        style=discord.TextStyle.paragraph,
        max_length=200,
        required=True
    )
    
    def __init__(self, parent_view, team_id: str, team_name: str):
        super().__init__()
        self.parent_view = parent_view
        self.team_id = team_id
        self.team_name = team_name
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 점수 파싱 (+/- 부호 처리)
            score_str = self.score_input.value.strip()
            if score_str.startswith('+'):
                score_str = score_str[1:]
            
            score = int(score_str)
            
            if score == 0:
                await interaction.followup.send(
                    "❌ 0점은 조정할 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # DB에 기록
            success, message = await self.parent_view.bot.db_manager.manual_adjust_team_score(
                team_id=self.team_id,
                score_adjustment=score,
                adjusted_by=str(interaction.user.id),
                reason=self.reason.value
            )
            
            if success:
                # 현재 총점 조회
                total_score = await self.parent_view.bot.db_manager.get_team_total_score(
                    self.team_id
                )
                
                # 임베드 생성
                embed = discord.Embed(
                    title="✅ 팀 점수 수동 조정 완료",
                    description=f"**{self.team_name}** 팀의 점수가 조정되었습니다.",
                    color=discord.Color.green() if score > 0 else discord.Color.red(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📊 조정 내역",
                    value=f"**점수 변동**: {'+' if score > 0 else ''}{score}점\n"
                          f"**현재 총점**: {total_score}점",
                    inline=False
                )
                
                embed.add_field(
                    name="📝 사유",
                    value=self.reason.value,
                    inline=False
                )
                
                embed.set_footer(text=f"조정자: {interaction.user.display_name}")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # 공지 채널에 알림
                channel_id = await self.parent_view.bot.db_manager.get_event_announcement_channel(
                    self.parent_view.guild_id
                )
                
                if channel_id:
                    channel = interaction.guild.get_channel(int(channel_id))
                    if channel:
                        emoji = "📈" if score > 0 else "📉"
                        sign = "+" if score > 0 else ""
                        await channel.send(
                            f"{emoji} **{self.team_name}** 팀의 점수가 **{sign}{score}점** 조정되었습니다.\n"
                            f"💡 사유: {self.reason.value}"
                        )
            else:
                await interaction.followup.send(
                    f"❌ 점수 조정 실패: {message}",
                    ephemeral=True
                )
                
        except ValueError:
            await interaction.followup.send(
                "❌ 점수는 숫자로 입력해주세요.",
                ephemeral=True
            )
        except Exception as e:
            print(f"❌ 수동 점수 조정 실패: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                "❌ 점수 조정 중 오류가 발생했습니다.",
                ephemeral=True
            )

class EventSystemCommands(commands.Cog):
    """이벤트 시스템 관리 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
        self._admin_cache = {}  # {(guild_id, user_id): (is_admin, timestamp)}
        self._cache_ttl = 300  # 5분 캐시

    async def safe_defer(self, interaction: discord.Interaction) -> bool:
        """안전한 defer (타임아웃 시 False 반환)"""
        try:
            await interaction.response.defer(ephemeral=True)
            return True
        except discord.NotFound:
            print(f"⚠️ Interaction timeout for /{interaction.command.name}, continuing...")
            return False
        except Exception as e:
            print(f"⚠️ Defer failed for /{interaction.command.name}: {e}, continuing...")
            return False

    async def safe_send(
        self, 
        interaction: discord.Interaction, 
        use_followup: bool, 
        content: str = None, 
        embed: discord.Embed = None, 
        view: discord.ui.View = None,
        ephemeral: bool = True
    ):
        """안전한 메시지 전송 (followup 또는 channel)"""
        if use_followup:
            await interaction.followup.send(
                content=content,
                embed=embed,
                view=view,
                ephemeral=ephemeral
            )
        else:
            # 타임아웃 시 채널에 직접
            if content or embed:
                await interaction.channel.send(
                    content=f"{interaction.user.mention}\n{content}" if content else None,
                    embed=embed,
                    view=view
                )
    
    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        cache_key = (guild_id, user_id)
        
        if interaction.user.id == interaction.guild.owner_id:
            return True

        # 캐시 확인
        if cache_key in self._admin_cache:
            is_admin, timestamp = self._admin_cache[cache_key]
            if time() - timestamp < self._cache_ttl:
                return is_admin

        # DB 조회
        is_admin = await self.bot.db_manager.is_server_admin(guild_id, user_id)
        
        # 캐시 저장
        self._admin_cache[cache_key] = (is_admin, time())
        
        return is_admin
    
    @app_commands.command(name="이벤트팀생성", description="[관리자] 이벤트 팀 생성")
    @app_commands.describe(팀명="팀 이름 (예: 1조, A팀)")
    @app_commands.default_permissions(manage_guild=True)
    async def create_team(self, interaction: discord.Interaction, 팀명: str):
        """이벤트 팀 생성"""
        try:
            await interaction.response.defer(ephemeral=True)
            use_followup = True
        except discord.NotFound:
            # 이미 타임아웃됐지만 계속 진행
            print("⚠️ Interaction timeout, but continuing...")
            use_followup = False
        except Exception as e:
            print(f"⚠️ Defer failed: {e}, but continuing...")
            use_followup = False
        
        if not await self.is_admin(interaction):
            error_msg = ErrorMessages.ADMIN_ONLY
            if use_followup:
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                # 타임아웃 시 그냥 로그만
                print(f"⚠️ Admin check failed for {interaction.user.name}")
            return
        
        members = [m for m in interaction.guild.members if not m.bot]
        
        if not members:
            error_msg = ErrorMessages.NO_MEMBERS
            if use_followup:
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                print(f"⚠️ No members found in guild")
            return
        
        view = TeamManagementView(
            self.bot,
            interaction.guild,
            팀명,
            str(interaction.user.id)
        )
        
        content = (
            f"**{팀명}** 팀의 팀원을 선택해주세요:\n"
            f"💡 Discord의 유저 선택 UI를 사용합니다 (자동완성 지원)"
        )
        
        if use_followup:
            await interaction.followup.send(content, view=view, ephemeral=True)
        else:
            # 타임아웃 시 채널에 직접 메시지 (fallback)
            await interaction.channel.send(
                f"{interaction.user.mention}\n{content}",
                view=view
            )
    
    @app_commands.command(name="이벤트팀목록", description="[관리자] 생성된 팀 목록 확인")
    @app_commands.default_permissions(manage_guild=True)
    async def list_teams(self, interaction: discord.Interaction):
        """팀 목록 조회"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                ErrorMessages.ADMIN_ONLY,
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild_id)
        teams = await self.bot.db_manager.get_event_teams(guild_id)
        
        if not teams:
            await interaction.followup.send(
                "📋 생성된 팀이 없습니다.\n`/이벤트팀생성`으로 팀을 만들어주세요.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📋 이벤트 팀 목록",
            description=f"총 {len(teams)}개의 팀이 있습니다.",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        for team in teams:
            created_time = datetime.fromisoformat(team['created_at'])
            embed.add_field(
                name=f"🏷️ {team['team_name']}",
                value=f"👥 팀원: {team['member_count']}명\n",
                    #   f"📅 생성일: <t:{int(created_time.timestamp())}:R>",
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="이벤트미션등록", description="[관리자] 이벤트 미션 등록")
    @app_commands.describe(
        카테고리="미션 카테고리 선택"
    )
    @app_commands.choices(카테고리=[
        app_commands.Choice(name="📅 일일 퀘스트", value="daily"),
        app_commands.Choice(name="💻 온라인", value="online"),
        app_commands.Choice(name="🏃 오프라인", value="offline"),
        app_commands.Choice(name="🎁 히든 미션", value="hidden")
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def create_mission(
        self, 
        interaction: discord.Interaction,
        카테고리: app_commands.Choice[str]
    ):
        """이벤트 미션 등록"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                ErrorMessages.ADMIN_ONLY,
                ephemeral=True
            )
            return
        
        # Modal 표시
        modal = MissionCreateModal(
            self.bot,
            str(interaction.guild_id),
            카테고리.value
        )
        
        await interaction.response.send_modal(modal)

    @app_commands.command(name="이벤트미션목록", description="등록된 미션 목록 확인")
    @app_commands.describe(
        카테고리="특정 카테고리만 보기 (선택사항)"
    )
    @app_commands.choices(카테고리=[
        app_commands.Choice(name="📅 일일 퀘스트", value="daily"),
        app_commands.Choice(name="💻 온라인", value="online"),
        app_commands.Choice(name="🏃 오프라인", value="offline"),
        app_commands.Choice(name="🎁 히든 미션", value="hidden"),
        app_commands.Choice(name="🌟 전체 보기", value="all")
    ])
    async def list_missions(
        self,
        interaction: discord.Interaction,
        카테고리: app_commands.Choice[str] = None
    ):
        """미션 목록 조회 (모든 유저 사용 가능)"""
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild_id)
        
        # 카테고리 필터링
        category_filter = None if (카테고리 and 카테고리.value == "all") else (카테고리.value if 카테고리 else None)
        
        missions = await self.bot.db_manager.get_event_missions(
            guild_id,
            category_filter
        )
        
        if not missions:
            await interaction.followup.send(
                "📋 등록된 미션이 없습니다.\n"
                "관리자가 `/이벤트미션등록`으로 미션을 만들어야 합니다.",
                ephemeral=True
            )
            return
        
        # 카테고리별로 그룹화
        grouped_missions = {
            'daily': [],
            'online': [],
            'offline': [],
            'hidden': []
        }
        
        for mission in missions:
            grouped_missions[mission['category']].append(mission)
        
        # 카테고리 정보
        category_info = {
            'daily': {'name': '일일 퀘스트', 'emoji': '📅'},
            'online': {'name': '온라인', 'emoji': '💻'},
            'offline': {'name': '오프라인', 'emoji': '🏃'},
            'hidden': {'name': '히든 미션', 'emoji': '🎁'}
        }
        
        embed = discord.Embed(
            title="📋 이벤트 미션 목록",
            description=f"총 {len(missions)}개의 미션이 등록되어 있습니다.",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        # 카테고리별로 필드 추가
        for cat, cat_missions in grouped_missions.items():
            if not cat_missions:
                continue
            
            mission_list = []
            for i, mission in enumerate(cat_missions, 1):
                desc = f" - {mission['description'][:30]}" if mission['description'] else ""
                mission_list.append(
                    f"**{i}. {mission['mission_name']}** ({mission['base_points']}점){desc}\n"
                    f"   ├ 최소 인원: {mission['min_participants']}명"
                )
            
            if mission_list:
                embed.add_field(
                    name=f"{category_info[cat]['emoji']} {category_info[cat]['name']} ({len(cat_missions)}개)",
                    value="\n".join(mission_list),
                    inline=False
                )
        
        # 통계 정보 추가
        stats = await self.bot.db_manager.get_mission_stats(guild_id)
        total_points = sum(s['total_points'] for s in stats.values())
        
        embed.add_field(
            name="📊 통계",
            value=f"**총 획득 가능 점수**: {total_points}점\n"
                f"**카테고리별**: "
                f"일일 {stats['daily']['count']}개, "
                f"온라인 {stats['online']['count']}개, "
                f"오프라인 {stats['offline']['count']}개, "
                f"히든 {stats['hidden']['count']}개",
            inline=False
        )
        
        embed.set_footer(text="💡 미션 완료는 관리자에게 인증 후 점수가 부여됩니다")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="이벤트미션삭제", description="[관리자] 등록된 미션 삭제")
    @app_commands.describe(미션명="삭제할 미션 이름")
    @app_commands.default_permissions(manage_guild=True)
    async def delete_mission(
        self,
        interaction: discord.Interaction,
        미션명: str
    ):
        """미션 삭제"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                ErrorMessages.ADMIN_ONLY,
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild_id)
        
        # 미션 찾기
        missions = await self.bot.db_manager.get_event_missions(guild_id)
        target_mission = None
        
        for mission in missions:
            if mission['mission_name'].lower() == 미션명.lower():
                target_mission = mission
                break
        
        if not target_mission:
            # 유사한 미션 찾기
            similar = [m['mission_name'] for m in missions if 미션명.lower() in m['mission_name'].lower()]
            
            error_msg = ErrorMessages.MISSION_NOT_FOUND.format(mission_name=미션명)
            if similar:
                error_msg += f"\n\n**유사한 미션:**\n• " + "\n• ".join(similar[:5])
            
            await interaction.followup.send(error_msg, ephemeral=True)
            return
        
        # 미션 삭제
        success, result = await self.bot.db_manager.delete_event_mission(
            target_mission['mission_id']
        )
        
        if success:
            embed = discord.Embed(
                title=SuccessMessages.MISSION_DELETED,
                description=f"**{target_mission['mission_name']}** 미션이 삭제되었습니다.",
                color=0xff6b6b,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="삭제된 미션 정보",
                value=f"**카테고리**: {target_mission['category']}\n"
                    f"**점수**: {target_mission['base_points']}점\n"
                    f"**설명**: {target_mission['description'] or '없음'}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                f"❌ 미션 삭제 실패: {result}",
                ephemeral=True
            )

    @delete_mission.autocomplete('미션명')
    async def mission_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """미션 삭제 시 미션명 자동완성"""
        try:
            guild_id = str(interaction.guild_id)
            missions = await self.bot.db_manager.get_event_missions(guild_id)
            
            # 현재 입력과 매칭되는 미션 찾기
            matching = []
            for mission in missions:
                if current.lower() in mission['mission_name'].lower():
                    matching.append(
                        app_commands.Choice(
                            name=f"{mission['mission_name']} ({mission['base_points']}점)",
                            value=mission['mission_name']
                        )
                    )
            
            return matching[:25]  # Discord 제한
            
        except Exception as e:
            print(f"[DEBUG] 미션명 자동완성 오류: {e}")
            return []

    @app_commands.command(name="이벤트점수부여", description="[관리자] 팀의 미션 완료 처리 및 점수 부여")
    @app_commands.default_permissions(manage_guild=True)
    async def award_score(self, interaction: discord.Interaction):
        """팀에 미션 완료 점수 부여"""
        # ✅ defer 시도 (실패해도 계속 진행)
        try:
            await interaction.response.defer(ephemeral=True)
            use_followup = True
        except discord.NotFound:
            print("⚠️ Interaction timeout (award_score), but continuing...")
            use_followup = False
        except Exception as e:
            print(f"⚠️ Defer failed (award_score): {e}, but continuing...")
            use_followup = False
        
        if not await self.is_admin(interaction):
            error_msg = ErrorMessages.ADMIN_ONLY
            if use_followup:
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                print(f"⚠️ Admin check failed for {interaction.user.name}")
            return
        
        guild_id = str(interaction.guild_id)
        
        # 팀이 있는지 확인
        teams = await self.bot.db_manager.get_event_teams(guild_id)
        if not teams:
            error_msg = ErrorMessages.NO_TEAMS
            if use_followup:
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                print(f"⚠️ No teams found in guild {guild_id}")
            return
        
        # 미션이 있는지 확인
        missions = await self.bot.db_manager.get_event_missions(guild_id)
        if not missions:
            error_msg = ErrorMessages.NO_MISSIONS
            if use_followup:
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                print(f"⚠️ No missions found in guild {guild_id}")
            return
        
        # View 생성 후 setup 완료 확인
        view = ScoreAwardView(
            self.bot,
            guild_id,
            str(interaction.user.id)
        )
        
        setup_success = await view.setup_team_select()
        
        if not setup_success:
            error_msg = ErrorMessages.SETUP_ERROR
            if use_followup:
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                print(f"⚠️ Setup error for award_score")
            return
        
        content = (
            "🎯 **미션 완료 점수 부여**\n"
            "1단계: 점수를 부여할 팀을 선택하세요"
        )
        
        if use_followup:
            await interaction.followup.send(content, view=view, ephemeral=True)
        else:
            # 타임아웃 시 채널에 직접 메시지 (fallback)
            await interaction.channel.send(
                f"{interaction.user.mention}\n{content}",
                view=view
            )

    @app_commands.command(name="이벤트점수조정", description="[관리자] 팀 점수 수동 조정 (추가/차감)")
    @app_commands.default_permissions(manage_guild=True)
    async def adjust_team_score(self, interaction: discord.Interaction):
        """팀 점수 수동 조정"""
        use_followup = await self.safe_defer(interaction)
        
        if not await self.is_admin(interaction):
            await self.safe_send(interaction, use_followup, ErrorMessages.ADMIN_ONLY)
            return
        
        guild_id = str(interaction.guild_id)
        
        # 팀 확인
        teams = await self.bot.db_manager.get_event_teams(guild_id)
        if not teams:
            await self.safe_send(interaction, use_followup, ErrorMessages.NO_TEAMS)
            return
        
        # View 생성
        view = ManualScoreAdjustmentView(self.bot, guild_id)
        setup_success = await view.setup_team_select()
        
        if not setup_success:
            await self.safe_send(
                interaction,
                use_followup,
                "❌ 팀 선택 설정에 실패했습니다."
            )
            return
        
        await self.safe_send(
            interaction,
            use_followup,
            "🔧 **팀 점수 수동 조정**\n"
            "점수를 조정할 팀을 선택하세요.\n"
            "💡 양수(+)는 점수 추가, 음수(-)는 점수 차감",
            view=view
        )

    @app_commands.command(name="이벤트점수취소", description="[관리자] 잘못 부여된 점수를 취소합니다 (미션 + 음성 활동)")
    @app_commands.default_permissions(manage_guild=True)
    async def cancel_event_points(self, interaction: discord.Interaction):
        """점수 취소 명령어 (2단계: 팀 선택 → 점수 선택)"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                ErrorMessages.ADMIN_ONLY,
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild_id)
        
        # 모든 활성 팀 조회
        teams = await self.bot.db_manager.get_event_teams(guild_id)
        
        if not teams:
            await interaction.followup.send(
                ErrorMessages.NO_TEAMS,
                ephemeral=True
            )
            return
        
        # 미션 완료 내역 조회
        mission_completions = await self.bot.db_manager.get_recent_mission_completions(
            guild_id=guild_id,
            hours=24,
            limit=100  # 충분히 큰 수
        )
        
        # 음성 활동 점수 내역 조회
        voice_scores = await self.bot.db_manager.get_recent_voice_scores(
            guild_id=guild_id,
            hours=24,
            limit=100
        )
        
        # 미션 완료 내역에 type 추가
        for item in mission_completions:
            item['type'] = 'mission'
            item['points'] = item['awarded_points']
        
        # 통합
        all_items = mission_completions + voice_scores
        
        # 시간순 정렬
        all_items.sort(
            key=lambda x: x.get('completed_at') if x['type'] == 'mission' else x.get('awarded_at'),
            reverse=True
        )
        
        if not all_items:
            embed = discord.Embed(
                title="ℹ️ 취소할 내역 없음",
                description="최근 24시간 내 점수 부여 내역이 없습니다.",
                color=EventSystemSettings.Colors.INFO
            )
            
            embed.set_footer(text="💡 점수 부여 후 24시간 이내만 취소 가능합니다")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # 통계
        mission_count = sum(1 for item in all_items if item['type'] == 'mission')
        voice_count = sum(1 for item in all_items if item['type'] == 'voice')
        
        # View 생성
        view = CancelPointsView(
            bot=self.bot,
            guild_id=guild_id,
            teams=teams,
            all_items=all_items,
            admin_id=str(interaction.user.id)
        )
        
        embed = discord.Embed(
            title="🔄 점수 취소 (2단계)",
            description=f"최근 24시간 내 **{len(all_items)}개**의 점수 부여 내역이 있습니다.\n"
                        f"📋 미션: {mission_count}개 | 🎤 음성: {voice_count}개\n\n"
                        f"**1단계**: 먼저 팀을 선택하세요.",
            color=EventSystemSettings.Colors.WARNING,
            timestamp=datetime.now()
        )
        
        embed.set_footer(text="⚠️ 점수 취소는 되돌릴 수 없습니다")
        
        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True
        )

    @app_commands.command(name="이벤트팀이력", description="[관리자] 특정 팀의 미션 완료 이력 확인")
    @app_commands.describe(팀명="이력을 확인할 팀 이름")
    @app_commands.default_permissions(manage_guild=True)
    async def team_history(
        self,
        interaction: discord.Interaction,
        팀명: str
    ):
        """팀의 미션 완료 이력 조회"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                ErrorMessages.ADMIN_ONLY,
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild_id)
        
        # 팀 찾기
        teams = await self.bot.db_manager.get_event_teams(guild_id)
        target_team = None
        
        for team in teams:
            if team['team_name'].lower() == 팀명.lower():
                target_team = team
                break
        
        if not target_team:
            await interaction.followup.send(
                ErrorMessages.TEAM_NOT_FOUND.format(팀명=팀명),
                ephemeral=True
            )
            return
        
        # 팀 상세 정보
        team_info = await self.bot.db_manager.get_event_team_details(
            target_team['team_id']
        )
        
        # 미션 이력
        history = await self.bot.db_manager.get_team_mission_history(
            target_team['team_id'],
            limit=DisplayConstants.MISSION_HISTORY_LIMIT
        )
        
        # 총점
        total_score = await self.bot.db_manager.get_team_total_score(
            target_team['team_id']
        )
        
        # 카테고리별 통계
        category_stats = await self.bot.db_manager.get_team_category_stats(
            target_team['team_id']
        )
        
        embed = discord.Embed(
            title=f"📊 {팀명} 팀 미션 이력",
            description=f"총점: **{total_score}점** | 완료: {len(history)}개",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        # 카테고리별 통계
        stats_text = []
        category_names = {
            'daily': '📅 일일',
            'online': '💻 온라인',
            'offline': '🏃 오프라인',
            'hidden': '🎁 히든'
        }
        
        for cat, name in category_names.items():
            stat = category_stats.get(cat, {'count': 0, 'points': 0})
            if stat['count'] > 0:
                stats_text.append(f"{name}: {stat['count']}개 ({stat['points']}점)")
        
        if stats_text:
            embed.add_field(
                name="📈 카테고리별 현황",
                value="\n".join(stats_text),
                inline=False
            )
        
        # 최근 완료 미션
        if history:
            history_text = []
            for i, record in enumerate(history[:10], 1):
                completed_time = datetime.fromisoformat(record['completed_at'])
                history_text.append(
                    f"{i}. **{record['mission_name']}** (+{record['awarded_points']}점)\n"
                    f"   └ <t:{int(completed_time.timestamp())}:R> | {record['participants_count']}명 참여"
                )
            
            embed.add_field(
                name="🕐 최근 완료 미션",
                value="\n".join(history_text),
                inline=False
            )
        else:
            embed.add_field(
                name="🕐 완료 이력",
                value="아직 완료한 미션이 없습니다.",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


    @team_history.autocomplete('팀명')
    async def team_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """팀명 자동완성"""
        try:
            guild_id = str(interaction.guild_id)
            teams = await self.bot.db_manager.get_event_teams(guild_id)
            
            matching = []
            for team in teams:
                if current.lower() in team['team_name'].lower():
                    matching.append(
                        app_commands.Choice(
                            name=f"{team['team_name']} ({team['member_count']}명)",
                            value=team['team_name']
                        )
                    )
            
            return matching[:25]
            
        except Exception as e:
            print(f"[DEBUG] 팀명 자동완성 오류: {e}")
            return []

    @app_commands.command(name="이벤트순위", description="전체 팀 순위표 확인")
    async def event_rankings(self, interaction: discord.Interaction):
        """전체 팀 순위 조회 (개선된 레이아웃)"""
        await interaction.response.defer(ephemeral=False)
        
        guild_id = str(interaction.guild_id)
        
        # 순위 조회
        rankings = await self.bot.db_manager.get_team_rankings(guild_id)
        
        if not rankings:
            await interaction.followup.send(
                "📋 아직 생성된 팀이 없거나 진행 중인 이벤트가 없습니다.",
                ephemeral=False
            )
            return
        
        embed = discord.Embed(
            title="🏆 이벤트 팀 순위표",
            description=f"총 {len(rankings)}개 팀이 경쟁 중입니다!",
            color=0xffd700,
            timestamp=datetime.now()
        )
        
        # 순위 이모지
        rank_emojis = {
            1: "🥇",
            2: "🥈", 
            3: "🥉"
        }
        
        # ⭐ 상위 10개 팀 - 2줄 구조 (옵션 B)
        ranking_text = []
        for team_rank in rankings[:DisplayConstants.TOP_TEAMS_DISPLAY]:
            rank_emoji = rank_emojis.get(team_rank['rank'], f"{team_rank['rank']}.")
            
            # 1줄: 팀명 + 총점
            line1 = f"{rank_emoji} **{team_rank['team_name']}** - **{team_rank['total_score']}점**"
            
            # 2줄: 상세 정보 (들여쓰기로 시각적 구분)
            all_clear_display = ""
            if team_rank['all_clear_count'] >= 10:
                all_clear_display = f" | 올클: {team_rank['all_clear_count']}회 🔥🔥"
            elif team_rank['all_clear_count'] >= 5:
                all_clear_display = f" | 올클: {team_rank['all_clear_count']}회 🔥"
            elif team_rank['all_clear_count'] > 0:
                all_clear_display = f" | 올클: {team_rank['all_clear_count']}회"
            
            line2 = (
                f"   └ 완료: {team_rank['completed_missions']}개"
                f"{all_clear_display}"
                f" | 팀원: {team_rank['member_count']}명"
            )
            
            ranking_text.append(f"{line1}\n{line2}")
        
        embed.add_field(
            name="📊 순위",
            value="\n\n".join(ranking_text),  # 팀 간 줄바꿈 2개로 구분
            inline=False
        )
        
        # 나머지 팀 수 표시
        if len(rankings) > 10:
            embed.add_field(
                name="📋 기타",
                value=f"... 외 {len(rankings) - 10}개 팀",
                inline=False
            )
        
        # 통계 정보
        total_points = sum(r['total_score'] for r in rankings)
        total_completions = sum(r['completed_missions'] for r in rankings)
        total_all_clears = sum(r['all_clear_count'] for r in rankings)

        stats_text = (
            f"**총 획득 점수**: {total_points}점\n"
            f"**총 완료 미션**: {total_completions}개\n"
            f"**총 올클리어**: {total_all_clears}회 🔥\n"
            f"**평균 점수**: {round(total_points / len(rankings), 1)}점"
        )
        
        embed.add_field(
            name="📈 전체 통계",
            value=stats_text,
            inline=False
        )
        
        embed.set_footer(text="💡 /내팀정보 명령어로 내 팀의 상세 정보를 확인하세요")
        
        await interaction.followup.send(embed=embed, ephemeral=False)

    @app_commands.command(name="내팀정보", description="내가 속한 팀의 정보 및 점수 확인")
    async def my_team_info(self, interaction: discord.Interaction):
        """자신의 팀 정보 조회"""
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        # 유저의 팀 조회
        my_team = await self.bot.db_manager.get_user_event_team(guild_id, user_id)
        
        if not my_team:
            await interaction.followup.send(
                ErrorMessages.NOT_IN_TEAM,
                ephemeral=True
            )
            return
        
        team_id = my_team['team_id']
        
        # 팀 상세 정보
        team_details = await self.bot.db_manager.get_event_team_details(team_id)
        
        # 팀 순위
        team_rank = await self.bot.db_manager.get_team_rank(team_id)
        
        # 팀 완료율
        completion_rates = await self.bot.db_manager.get_team_completion_rate(team_id)
        
        # 카테고리별 통계
        category_stats = await self.bot.db_manager.get_team_category_stats(team_id)
        
        # 오늘 음성 활동 점수
        voice_today = await self.bot.db_manager.get_team_today_voice_score(team_id)
        
        # 최근 이력
        recent_history = await self.bot.db_manager.get_team_mission_history(
            team_id,
            limit=5
        )
        
        # Embed 생성
        embed = discord.Embed(
            title=f"💥 {team_details['team_name']}",
            description=f"**순위**: {team_rank['rank']}위 / {team_rank['total_teams']}팀",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        # 점수 정보 (미션 + 음성 구분)
        score_text = (
            f"**총 점수**: {team_rank['total_score']}점\n"
            f"├─ 미션 점수: {team_rank['mission_score']}점\n"
            f"└─ 음성 활동: {team_rank['voice_score']}점"
        )
        
        embed.add_field(
            name="🏆 점수",
            value=score_text,
            inline=True
        )
        
        # 팀원 목록
        members_text = []
        for member in team_details['members']:
            members_text.append(f"• <@{member['user_id']}>")
        
        embed.add_field(
            name=f"👥 팀원 ({len(team_details['members'])}명)",
            value="\n".join(members_text) if members_text else "없음",
            inline=True
        )
        
        # 오늘의 음성 활동 상세
        voice_text = (
            f"**오늘 획득**: {voice_today['today_score']}/{voice_today['max_score']}점\n"
            f"**남은 점수**: {voice_today['remaining']}점\n"
            f"**세션 수**: {voice_today['session_count']}회"
        )
        
        # 현재 활성 세션 확인
        if self.bot.voice_session_tracker:
            active_sessions = self.bot.voice_session_tracker.get_active_sessions_info()
            team_session = next((s for s in active_sessions if s["team_id"] == team_id), None)
            
            if team_session:
                elapsed_min = int(team_session["elapsed_seconds"] / 60)
                if team_session["is_bonus_mode"]:
                    bonus_elapsed = team_session.get("bonus_elapsed_seconds")
                    bonus_min = int(bonus_elapsed / 60) if bonus_elapsed else 0
                    voice_text += f"\n\n🎉 **보너스 모드 진행 중!**\n({team_session['member_count']}명, {bonus_min}분 경과)"
                else:
                    voice_text += f"\n\n🎮 **활동 중**\n({team_session['member_count']}명, {elapsed_min}분 경과)"
        
        embed.add_field(
            name="🎤 오늘의 음성 활동",
            value=voice_text + "\n\n💡 *2명+ 1시간당 1점, 5명+ 1시간 유지 시 10점!*",
            inline=False
        )
        
        # 카테고리별 현황
        category_info = {
            'daily': {'name': '📅 일일', 'emoji': '📅'},
            'online': {'name': '💻 온라인', 'emoji': '💻'},
            'offline': {'name': '🏃 오프라인', 'emoji': '🏃'},
            'hidden': {'name': '🎁 히든', 'emoji': '🎁'}
        }
        
        category_text = []
        for cat, info in category_info.items():
            stat = category_stats.get(cat, {'count': 0, 'points': 0})
            rate = completion_rates.get(cat, {'rate': 0})
            
            if rate['total'] > 0:
                category_text.append(
                    f"{info['emoji']} **{info['name']}**: "
                    f"{stat['count']}개 완료 ({stat['points']}점) | "
                    f"진행률: {rate['rate']}%"
                )
        
        if category_text:
            embed.add_field(
                name="📊 카테고리별 현황",
                value="\n".join(category_text),
                inline=False
            )
        
        # 최근 완료 미션
        if recent_history:
            history_text = []
            for record in recent_history[:3]:
                completed_time = datetime.fromisoformat(record['completed_at'])
                history_text.append(
                    f"• **{record['mission_name']}** (+{record['awarded_points']}점)\n"
                    f"  └ <t:{int(completed_time.timestamp())}:R>"
                )
            
            embed.add_field(
                name="🕐 최근 완료 미션",
                value="\n".join(history_text),
                inline=False
            )
        else:
            embed.add_field(
                name="🕐 최근 완료 미션",
                value="아직 완료한 미션이 없습니다.\n팀원들과 함께 미션을 시작해보세요!",
                inline=False
            )
        
        # 목표 메시지
        if team_rank['rank'] == 1:
            goal_msg = "🏆 현재 1등! 이 자리를 지켜보세요!"
        elif team_rank['rank'] <= 3:
            goal_msg = f"🎯 목표: {team_rank['rank']-1}위 달성!"
        else:
            goal_msg = "💪 화이팅! 팀원들과 함께 순위를 올려보세요!"
        
        embed.add_field(
            name="🎯 목표",
            value=goal_msg,
            inline=False
        )
        
        embed.set_footer(text=f"{interaction.user.display_name} 님의 팀 | /이벤트순위로 전체 순위 확인")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="이벤트현황", description="전체 이벤트 진행 상황 확인")
    async def event_overview(self, interaction: discord.Interaction):
        """이벤트 전체 현황 조회 (모든 유저 사용 가능)"""
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild_id)
        
        # 전체 통계
        overview = await self.bot.db_manager.get_event_overview(guild_id)
        
        if not overview or overview['total_teams'] == 0:
            await interaction.followup.send(
                "📋 진행 중인 이벤트가 없습니다.",
                ephemeral=True
            )
            return
        
        # 순위 정보
        rankings = await self.bot.db_manager.get_team_rankings(guild_id)
        
        # 최근 활동
        recent_activities = await self.bot.db_manager.get_recent_event_activities(
            guild_id,
            limit=5
        )
        
        embed = discord.Embed(
            title="📊 미션 띵파서블 이벤트 현황",
            description=EventSystemSettings.EVENT_DESCRIPTION,
            color=EventSystemSettings.Colors.EVENT,
            timestamp=datetime.now()
        )
        
        # 기본 통계
        embed.add_field(
            name="📈 전체 통계",
            value=f"**참가 팀**: {overview['total_teams']}팀\n"
                f"**등록 미션**: {overview['total_missions']}개\n"
                f"**총 완료**: {overview['total_completions']}회\n"
                f"**부여 점수**: {overview['total_points_awarded']}점\n"
                f"**평균 점수**: {overview['avg_team_score']}점/팀",
            inline=True
        )
        
        # 카테고리별 미션
        missions_by_cat = overview['missions_by_category']
        embed.add_field(
            name="📋 미션 구성",
            value=f"📅 일일: {missions_by_cat['daily']}개\n"
                f"💻 온라인: {missions_by_cat['online']}개\n"
                f"🏃 오프라인: {missions_by_cat['offline']}개\n"
                f"🎁 히든: {missions_by_cat['hidden']}개",
            inline=True
        )
        
        # 인기 미션 TOP 3
        if overview['popular_missions']:
            popular_text = []
            for i, mission in enumerate(overview['popular_missions'], 1):
                category_emoji = {
                    cat: info['emoji'] 
                    for cat, info in EventSystemSettings.CATEGORY_INFO.items()
                }
                emoji = category_emoji.get(mission['category'], '📋')
                
                popular_text.append(
                    f"{i}. {emoji} **{mission['mission_name']}**\n"
                    f"   └ {mission['completion_count']}회 완료"
                )
            
            embed.add_field(
                name="🔥 인기 미션 TOP 3",
                value="\n".join(popular_text),
                inline=False
            )
        
        # 상위 3팀
        if rankings:
            top3_text = []
            rank_emojis = EventSystemSettings.RANK_EMOJIS
            
            for team in rankings[:3]:
                emoji = rank_emojis.get(team['rank'], "")
                top3_text.append(
                    f"{emoji} **{team['team_name']}** - {team['total_score']}점"
                )
            
            embed.add_field(
                name="🏆 상위 3팀",
                value="\n".join(top3_text),
                inline=False
            )
        
        # 최근 활동
        if recent_activities:
            activity_text = []
            for activity in recent_activities[:3]:
                completed_time = datetime.fromisoformat(activity['completed_at'])
                
                category_emoji = {
                    'daily': '📅',
                    'online': '💻',
                    'offline': '🏃',
                    'hidden': '🎁'
                }
                emoji = category_emoji.get(activity['category'], '📋')
                
                activity_text.append(
                    f"{emoji} **{activity['team_name']}** - {activity['mission_name']}\n"
                    f"   └ <t:{int(completed_time.timestamp())}:R> | +{activity['awarded_points']}점"
                )
            
            embed.add_field(
                name="🕐 최근 활동",
                value="\n".join(activity_text),
                inline=False
            )
        
        embed.set_footer(text="💡 /이벤트순위로 전체 순위 확인 | /내팀정보로 내 팀 확인")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="이벤트공지채널설정", description="[관리자] 이벤트 미션 완료 공지 채널 설정")
    @app_commands.describe(채널="공지를 보낼 채널")
    @app_commands.default_permissions(manage_guild=True)
    async def set_announcement_channel(
        self,
        interaction: discord.Interaction,
        채널: discord.TextChannel
    ):
        """이벤트 공지 채널 설정"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                ErrorMessages.ADMIN_ONLY,
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild_id)
        channel_id = str(채널.id)
        
        # 봇이 해당 채널에 메시지를 보낼 수 있는지 확인
        permissions = 채널.permissions_for(interaction.guild.me)
        if not permissions.send_messages or not permissions.embed_links:
            await interaction.followup.send(
                f"❌ {채널.mention} 채널에 메시지를 보낼 권한이 없습니다.\n"
                "봇에게 '메시지 보내기' 및 '링크 첨부' 권한을 부여해주세요.",
                ephemeral=True
            )
            return
        
        # DB에 저장
        success, message = await self.bot.db_manager.set_event_announcement_channel(
            guild_id, channel_id
        )
        
        if success:
            embed = discord.Embed(
                title="✅ 공지 채널 설정 완료",
                description=f"{채널.mention} 채널이 이벤트 공지 채널로 설정되었습니다.",
                color=EventSystemSettings.Colors.SUCCESS,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📢 공지 내용",
                value="팀이 미션을 완료할 때마다 자동으로 공지됩니다.",
                inline=False
            )
            
            embed.set_footer(text="💡 /이벤트공지채널해제 명령어로 해제할 수 있습니다")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 테스트 메시지 발송
            try:
                await 채널.send(
                    "✅ 이벤트 공지 채널로 설정되었습니다!\n"
                    "앞으로 팀의 미션 완료 소식이 여기에 공지됩니다. 🎉"
                )
            except:
                pass
        else:
            await interaction.followup.send(
                f"❌ 공지 채널 설정 실패: {message}",
                ephemeral=True
            )

    @app_commands.command(name="이벤트공지채널해제", description="[관리자] 이벤트 공지 채널 설정 해제")
    @app_commands.default_permissions(manage_guild=True)
    async def remove_announcement_channel(self, interaction: discord.Interaction):
        """이벤트 공지 채널 해제"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                ErrorMessages.ADMIN_ONLY,
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild_id)
        
        success, message = await self.bot.db_manager.remove_event_announcement_channel(
            guild_id
        )
        
        if success:
            embed = discord.Embed(
                title="✅ 공지 채널 설정 해제",
                description=message,
                color=EventSystemSettings.Colors.INFO,
                timestamp=datetime.now()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                f"❌ {message}",
                ephemeral=True
            )

    @app_commands.command(name="이벤트공지채널확인", description="[관리자] 현재 설정된 공지 채널 확인")
    @app_commands.default_permissions(manage_guild=True)
    async def check_announcement_channel(self, interaction: discord.Interaction):
        """이벤트 공지 채널 확인"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                ErrorMessages.ADMIN_ONLY,
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild_id)
        channel_id = await self.bot.db_manager.get_event_announcement_channel(guild_id)
        
        if channel_id:
            channel = interaction.guild.get_channel(int(channel_id))
            
            if channel:
                embed = discord.Embed(
                    title="📢 현재 공지 채널",
                    description=f"{channel.mention}",
                    color=EventSystemSettings.Colors.INFO,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="채널 정보",
                    value=f"**이름**: {channel.name}\n**ID**: {channel_id}",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="⚠️ 공지 채널 오류",
                    description=f"설정된 채널(ID: {channel_id})을 찾을 수 없습니다.\n"
                            "채널이 삭제되었을 수 있습니다.",
                    color=EventSystemSettings.Colors.WARNING
                )
        else:
            embed = discord.Embed(
                title="📢 공지 채널 미설정",
                description="현재 설정된 공지 채널이 없습니다.",
                color=EventSystemSettings.Colors.INFO
            )
            
            embed.add_field(
                name="💡 설정 방법",
                value="`/이벤트공지채널설정 #채널명` 명령어로 설정할 수 있습니다.",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(EventSystemCommands(bot))