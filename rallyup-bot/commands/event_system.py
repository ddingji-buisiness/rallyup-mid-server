import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import List
from datetime import datetime
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

class TeamMembersInputModal(discord.ui.Modal, title="팀원 선택"):
    """팀원 멘션 입력 Modal"""
    
    members_input = discord.ui.TextInput(
        label="팀원 멘션",
        placeholder="@유저1 @유저2 @유저3 형태로 입력하세요",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )
    
    def __init__(self, bot, guild: discord.Guild, team_name: str, admin_id: str):
        super().__init__()
        self.bot = bot
        self.guild = guild
        self.team_name = team_name
        self.admin_id = admin_id
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 멘션에서 유저 ID 추출
            import re
            
            # <@123456789> 형태 추출
            mention_pattern = r'<@!?(\d+)>'
            user_ids = re.findall(mention_pattern, self.members_input.value)
            
            if not user_ids:
                await interaction.followup.send(
                    "❌ 유효한 멘션을 찾을 수 없습니다.\n"
                    "@유저명 형태로 입력해주세요.",
                    ephemeral=True
                )
                return
            
            # 유저 정보 수집
            member_data = []
            invalid_users = []
            
            for user_id in user_ids:
                member = self.guild.get_member(int(user_id))
                if member and not member.bot:
                    member_data.append((user_id, member.display_name))
                elif member and member.bot:
                    invalid_users.append(f"{member.display_name} (봇)")
                else:
                    invalid_users.append(f"<@{user_id}> (찾을 수 없음)")
            
            if not member_data:
                await interaction.followup.send(
                    "❌ 유효한 팀원이 없습니다.\n"
                    "봇이 아닌 서버 멤버를 멘션해주세요.",
                    ephemeral=True
                )
                return
            
            # 팀 생성
            success, result = await self.bot.db_manager.create_event_team(
                guild_id=str(self.guild.id),
                team_name=self.team_name,
                member_ids=member_data,
                created_by=self.admin_id
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 팀 생성 완료",
                    description=f"**{self.team_name}** 팀이 생성되었습니다!",
                    color=EventSystemSettings.Colors.SUCCESS,
                    timestamp=datetime.now()
                )
                
                members_text = "\n".join([
                    f"• <@{user_id}>" for user_id, _ in member_data
                ])
                
                embed.add_field(
                    name=f"👥 팀원 ({len(member_data)}명)",
                    value=members_text,
                    inline=False
                )
                
                if invalid_users:
                    embed.add_field(
                        name="⚠️ 제외된 유저",
                        value="\n".join([f"• {user}" for user in invalid_users]),
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ 팀 생성 실패: {result}",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ 팀 생성 Modal 처리 오류: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                "❌ 팀 생성 중 오류가 발생했습니다.",
                ephemeral=True
            )

# class TeamManagementView(discord.ui.View):
#     """팀 생성 시 팀원 선택용 View"""
    
#     def __init__(self, bot, guild: discord.Guild, team_name: str, admin_id: str, members: list):
#         super().__init__(timeout=ViewConstants.TIMEOUT)
#         self.bot = bot
#         self.guild = guild
#         self.team_name = team_name
#         self.admin_id = admin_id
#         self.selected_members = []
#         self.view_id = f"{guild.id}_{id(self)}"
        
#         # 서버 멤버 목록을 드롭다운에 추가
#         self._add_member_select(members)
    
#     def _add_member_select(self, members: list):
#         """멤버 선택 드롭다운 추가 (동기 메서드)"""
#         options = []
#         for member in members[:ViewConstants.DISCORD_SELECT_MAX]:
#             options.append(
#                 discord.SelectOption(
#                     label=member.display_name,
#                     value=str(member.id),
#                     description=f"ID: {member.id}"
#                 )
#             )
        
#         if not options:
#             # 멤버가 없는 경우 처리
#             return
        
#         select = discord.ui.Select(
#             placeholder="팀원을 선택하세요 (최대 25명)",
#             min_values=1,
#             max_values=min(len(options), 25),
#             options=options,
#             custom_id=f"team_member_select_{self.view_id}"
#         )
#         select.callback = self.member_selected
#         self.add_item(select)
    
#     async def member_selected(self, interaction: discord.Interaction):
#         """팀원 선택 완료"""
#         self.selected_members = [
#             (user_id, self.guild.get_member(int(user_id)).display_name)
#             for user_id in interaction.data['values']
#         ]
        
#         # 1. 기존 아이템 제거
#         self.clear_items()
        
#         # 2. 확인 버튼 추가
#         confirm_btn = discord.ui.Button(
#             label="✅ 팀 생성 완료",
#             style=discord.ButtonStyle.success
#         )
#         confirm_btn.callback = self.confirm_team_creation
#         self.add_item(confirm_btn)
        
#         await interaction.response.edit_message(
#             content=InfoMessages.MEMBERS_SELECTED.format(count=len(self.selected_members)),
#             view=self
#         )
    
#     async def confirm_team_creation(self, interaction: discord.Interaction):
#         """팀 생성 확정"""
#         await interaction.response.defer(ephemeral=True)
        
#         # DB에 팀 생성
#         success, result = await self.bot.db_manager.create_event_team(
#             guild_id=str(self.guild.id),
#             team_name=self.team_name,
#             member_ids=self.selected_members,
#             created_by=self.admin_id
#         )
        
#         if success:
#             embed = discord.Embed(
#                 title="✅ 팀 생성 완료",
#                 description=SuccessMessages.TEAM_CREATED.format(team_name=self.team_name),
#                 color=0x00ff88,
#                 timestamp=datetime.now()
#             )
            
#             members_text = "\n".join([
#                 f"• <@{user_id}>" for user_id, _ in self.selected_members
#             ])
            
#             embed.add_field(
#                 name=f"👥 팀원 ({len(self.selected_members)}명)",
#                 value=members_text,
#                 inline=False
#             )
            
#             await interaction.followup.send(embed=embed, ephemeral=True)
#         else:
#             await interaction.followup.send(
#                 f"❌ 팀 생성 실패: {result}",
#                 ephemeral=True
#             )
        
#         self.stop()

#     async def on_timeout(self):
#         """View 타임아웃 시 처리"""
#         for item in self.children:
#             item.disabled = True

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
                    if count >= 4:
                        score_detail += f"**4명 이상 보너스**: +1점\n"
                    
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

class EventSystemCommands(commands.Cog):
    """이벤트 시스템 관리 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        return await self.bot.db_manager.is_server_admin(guild_id, user_id)
    
    @app_commands.command(name="이벤트팀생성", description="[관리자] 이벤트 팀 생성")
    @app_commands.describe(팀명="팀 이름 (예: 1조, A팀)")
    @app_commands.default_permissions(manage_guild=True)
    async def create_team(self, interaction: discord.Interaction, 팀명: str):
        """이벤트 팀 생성"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                ErrorMessages.ADMIN_ONLY,
                ephemeral=True
            )
            return
        
        members = [m for m in interaction.guild.members if not m.bot]
        
        if not members:
            await interaction.response.send_message(
                ErrorMessages.NO_MEMBERS,
                ephemeral=True
            )
            return
        
        modal = TeamMembersInputModal(
            self.bot,
            interaction.guild,
            팀명,
            str(interaction.user.id)
        )
        
        await interaction.response.send_modal(modal)
    
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
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                ErrorMessages.ADMIN_ONLY,
                ephemeral=True
            )
            return
        
        guild_id = str(interaction.guild_id)
        
        # 팀이 있는지 확인
        teams = await self.bot.db_manager.get_event_teams(guild_id)
        if not teams:
            await interaction.response.send_message(
                ErrorMessages.NO_TEAMS,
                ephemeral=True
            )
            return
        
        # 미션이 있는지 확인
        missions = await self.bot.db_manager.get_event_missions(guild_id)
        if not missions:
            await interaction.response.send_message(
                ErrorMessages.NO_MISSIONS,
                ephemeral=True
            )
            return
        
        # ✅ View 생성 후 setup 완료 확인
        view = ScoreAwardView(
            self.bot,
            guild_id,
            str(interaction.user.id)
        )
        
        setup_success = await view.setup_team_select()
        
        if not setup_success:
            await interaction.response.send_message(
                ErrorMessages.SETUP_ERROR,
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            "🎯 **미션 완료 점수 부여**\n"
            "1단계: 점수를 부여할 팀을 선택하세요",
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
        """전체 팀 순위 조회 (모든 유저 사용 가능)"""
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild_id)
        
        # 순위 조회
        rankings = await self.bot.db_manager.get_team_rankings(guild_id)
        
        if not rankings:
            await interaction.followup.send(
                "📋 아직 생성된 팀이 없거나 진행 중인 이벤트가 없습니다.",
                ephemeral=True
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
        
        # 상위 10개 팀만 표시
        ranking_text = []
        for team_rank in rankings[:DisplayConstants.TOP_TEAMS_DISPLAY]:
            rank_emoji = rank_emojis.get(team_rank['rank'], f"{team_rank['rank']}.")
            
            # 막대 그래프 효과
            max_score = rankings[0]['total_score'] if rankings else 1
            bar_length = int((team_rank['total_score'] / max(max_score, 1)) * 10)
            bar = "█" * bar_length + "░" * (10 - bar_length)
            
            ranking_text.append(
                f"{rank_emoji} **{team_rank['team_name']}**\n"
                f"   {bar} **{team_rank['total_score']}점**\n"
                f"   └ 완료: {team_rank['completed_missions']}개 | "
                f"팀원: {team_rank['member_count']}명"
            )
        
        embed.add_field(
            name="📊 순위",
            value="\n\n".join(ranking_text),
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
        
        embed.add_field(
            name="📈 전체 통계",
            value=f"**총 획득 점수**: {total_points}점\n"
                f"**총 완료 미션**: {total_completions}개\n"
                f"**평균 점수**: {round(total_points / len(rankings), 1)}점",
            inline=False
        )
        
        embed.set_footer(text="💡 /내팀정보 명령어로 내 팀의 상세 정보를 확인하세요")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

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
                ErrorMessages.NOT_IN_EVENT_TEAM,
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
        
        # 최근 이력
        recent_history = await self.bot.db_manager.get_team_mission_history(
            team_id,
            limit=5
        )
        
        # Embed 생성
        embed = discord.Embed(
            title=f"👥 {team_details['team_name']}",
            description=f"**순위**: {team_rank['rank']}위 / {team_rank['total_teams']}팀\n"
                        f"**총점**: **{team_rank['total_score']}점**",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        # 팀원 목록
        members_text = []
        for member in team_details['members']:
            members_text.append(f"• <@{member['user_id']}>")
        
        embed.add_field(
            name=f"👥 팀원 ({len(team_details['members'])}명)",
            value="\n".join(members_text) if members_text else "없음",
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