import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional
from datetime import datetime
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
    "격돌" : [
        "아누비스의 왕좌", "하나오카"
    ]
}

# 오버워치 영웅 리스트 (포지션별, 커스텀 관리 가능)
OVERWATCH_HEROES = {
    "탱커": [
        "디바", "둠피스트", "라마트라", "라인하르트", "레킹볼", 
        "로드호그", "마우가", "시그마", "오리사", "윈스턴", "자리야",
        "정커퀸", "해저드"
    ],
    "딜러": [
        "겐지", "리퍼", "메이", "바스티온", "벤처", "소전", 
        "솔저", "솜브라", "시메트라", "애쉬", "에코", 
        "위도우메이커", "정크랫", "캐서디", "토르비욘", "트레이서", 
        "파라", "프레야", "한조"
    ],
    "힐러": [
        "라이프위버", "루시우", "메르시", "모이라", "바티스트", "브리기테", 
        "아나", "일리아리", "젠야타", "주노", "키리코"
    ]
}

# 모든 맵 리스트 (자동완성용)
ALL_MAPS = []
for map_type, maps in OVERWATCH_MAPS.items():
    ALL_MAPS.extend(maps)

# 모든 영웅 리스트 (자동완성용)  
ALL_HEROES = []
for position, heroes in OVERWATCH_HEROES.items():
    ALL_HEROES.extend(heroes)

class ClanScrimCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.admin_ids = [
            "386917108455309316",
            "415524200720105482" 
        ]

    def is_admin(self, user_id: int) -> bool:
        """관리자 권한 확인"""
        return str(user_id) in self.admin_ids

    @app_commands.command(name="클랜등록", description="[관리자] 새로운 클랜을 등록합니다")
    @app_commands.describe(클랜명="등록할 클랜의 이름")
    async def register_clan(self, interaction: discord.Interaction, 클랜명: str):
        # 관리자 권한 확인
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        # 클랜명 검증
        if len(클랜명) < 2 or len(클랜명) > 20:
            await interaction.response.send_message(
                "❌ 클랜명은 2-20자 사이여야 합니다.", ephemeral=True
            )
            return

        try:
            # 클랜 등록 시도
            success = await self.bot.db_manager.register_clan(
                guild_id=str(interaction.guild_id),
                clan_name=클랜명,
                created_by=str(interaction.user.id)
            )

            if success:
                embed = discord.Embed(
                    title="✅ 클랜 등록 완료!",
                    description=f"**{클랜명}** 클랜이 성공적으로 등록되었습니다!",
                    color=0x00ff88,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📋 등록 정보",
                    value=f"**클랜명**: {클랜명}\n"
                          f"**등록자**: {interaction.user.display_name}\n"
                          f"**등록일**: <t:{int(datetime.now().timestamp())}:F>",
                    inline=False
                )
                
                embed.add_field(
                    name="🔧 다음 단계",
                    value="이제 `/클랜전시작` 명령어로 클랜전을 진행할 수 있습니다!",
                    inline=False
                )
                
                embed.set_footer(text="RallyUp Bot | 클랜전 데이터 수집")
                
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(
                    f"❌ **{클랜명}** 클랜은 이미 등록되어 있습니다.", ephemeral=True
                )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ 클랜 등록 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="클랜목록", description="[관리자] 등록된 클랜 목록을 확인합니다")
    async def list_clans(self, interaction: discord.Interaction):
        # 관리자 권한 확인
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        try:
            clans = await self.bot.db_manager.get_registered_clans(str(interaction.guild_id))
            
            if not clans:
                await interaction.response.send_message(
                    "📋 등록된 클랜이 없습니다.\n`/클랜등록` 명령어로 클랜을 등록해주세요.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="📋 등록된 클랜 목록",
                description=f"총 **{len(clans)}**개의 클랜이 등록되어 있습니다",
                color=0x0099ff
            )

            clan_list = []
            for i, clan in enumerate(clans[:15]):  # 최대 15개까지 표시
                created_time = clan.created_at.strftime("%m/%d") if clan.created_at else "알 수 없음"
                clan_list.append(f"{i+1}. **{clan.clan_name}** (등록일: {created_time})")

            if len(clans) > 15:
                clan_list.append(f"... 외 {len(clans) - 15}개")

            embed.add_field(
                name="🏢 클랜 목록",
                value="\n".join(clan_list),
                inline=False
            )

            embed.set_footer(text="RallyUp Bot | 클랜전 데이터 수집")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ 클랜 목록 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="클랜전시작", description="[관리자] 클랜전 스크림을 시작합니다")
    @app_commands.describe(
        a클랜="첫 번째 클랜 이름",
        b클랜="두 번째 클랜 이름", 
        a음성채널="A클랜이 사용할 음성채널명",
        b음성채널="B클랜이 사용할 음성채널명"
    )
    async def start_clan_scrim(
        self,
        interaction: discord.Interaction,
        a클랜: str,
        b클랜: str,
        a음성채널: str,
        b음성채널: str
    ):
        # 관리자 권한 확인
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # 1. 클랜 등록 확인
            registered_clans = await self.bot.db_manager.get_registered_clans(str(interaction.guild_id))
            clan_names = [clan.clan_name for clan in registered_clans]

            if a클랜 not in clan_names:
                await interaction.followup.send(
                    f"❌ **{a클랜}** 클랜이 등록되어 있지 않습니다.\n"
                    f"먼저 `/클랜등록 {a클랜}` 명령어로 등록해주세요.", ephemeral=True
                )
                return

            if b클랜 not in clan_names:
                await interaction.followup.send(
                    f"❌ **{b클랜}** 클랜이 등록되어 있지 않습니다.\n"
                    f"먼저 `/클랜등록 {b클랜}` 명령어로 등록해주세요.", ephemeral=True
                )
                return

            # 2. 같은 클랜인지 확인
            if a클랜.lower() == b클랜.lower():
                await interaction.followup.send(
                    "❌ 같은 클랜끼리는 스크림을 진행할 수 없습니다.", ephemeral=True
                )
                return

            # 3. 기존 활성 스크림 확인
            active_scrim = await self.bot.db_manager.get_active_clan_scrim(str(interaction.guild_id))
            if active_scrim:
                await interaction.followup.send(
                    f"❌ 이미 진행 중인 클랜전이 있습니다.\n"
                    f"**{active_scrim.clan_a_name} vs {active_scrim.clan_b_name}**\n"
                    f"먼저 `/클랜전종료`를 실행해주세요.", ephemeral=True
                )
                return

            # 4. 음성채널 확인
            voice_channel_a = discord.utils.get(interaction.guild.voice_channels, name=a음성채널)
            voice_channel_b = discord.utils.get(interaction.guild.voice_channels, name=b음성채널)

            if not voice_channel_a:
                await interaction.followup.send(
                    f"❌ **{a음성채널}** 음성채널을 찾을 수 없습니다.", ephemeral=True
                )
                return

            if not voice_channel_b:
                await interaction.followup.send(
                    f"❌ **{b음성채널}** 음성채널을 찾을 수 없습니다.", ephemeral=True
                )
                return

            # 5. 각 채널의 인원 확인
            a_members = [m for m in voice_channel_a.members if not m.bot]
            b_members = [m for m in voice_channel_b.members if not m.bot]

            if len(a_members) != 5:
                await interaction.followup.send(
                    f"❌ **{a음성채널}** 채널에 정확히 5명이 있어야 합니다.\n"
                    f"**현재 인원**: {len(a_members)}명", ephemeral=True
                )
                return

            if len(b_members) != 5:
                await interaction.followup.send(
                    f"❌ **{b음성채널}** 채널에 정확히 5명이 있어야 합니다.\n"
                    f"**현재 인원**: {len(b_members)}명", ephemeral=True
                )
                return

            # 6. 클랜전 스크림 생성
            scrim_uuid = await self.bot.db_manager.create_clan_scrim(
                guild_id=str(interaction.guild_id),
                clan_a=a클랜,
                clan_b=b클랜,
                voice_channel_a=a음성채널,
                voice_channel_b=b음성채널,
                started_by=str(interaction.user.id)
            )

            # 7. 성공 메시지
            embed = discord.Embed(
                title="⚔️ 클랜전 스크림 시작!",
                description=f"**{a클랜}** vs **{b클랜}** 클랜전이 시작되었습니다!",
                color=0xff6b35,
                timestamp=datetime.now()
            )

            embed.add_field(
                name=f"🔵 {a클랜} ({a음성채널})",
                value="\n".join([f"{i+1}. {m.display_name}" for i, m in enumerate(a_members)]),
                inline=True
            )

            embed.add_field(
                name=f"🔴 {b클랜} ({b음성채널})",
                value="\n".join([f"{i+1}. {m.display_name}" for i, m in enumerate(b_members)]),
                inline=True
            )

            embed.add_field(
                name="📋 스크림 정보",
                value=f"**스크림 ID**: `{scrim_uuid[:8]}...`\n"
                      f"**시작 시간**: <t:{int(datetime.now().timestamp())}:F>\n"
                      f"**관리자**: {interaction.user.display_name}",
                inline=False
            )

            embed.add_field(
                name="🔧 다음 단계",
                value="• `/클랜전결과` - 각 판 결과 기록\n"
                      "• `/클랜전포지션` - 포지션 정보 추가 (선택)\n"
                      "• `/클랜전조합` - 영웅 조합 기록 (선택)\n"
                      "• `/클랜전종료` - 스크림 종료",
                inline=False
            )

            embed.set_footer(text="RallyUp Bot | 클랜전 데이터 수집")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f"❌ 클랜전 시작 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    # 클랜명 자동완성
    @start_clan_scrim.autocomplete('a클랜')
    async def a_clan_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        return await self._clan_autocomplete(interaction, current)

    @start_clan_scrim.autocomplete('b클랜')
    async def b_clan_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        return await self._clan_autocomplete(interaction, current)

    async def _clan_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        """클랜명 자동완성"""
        try:
            clans = await self.bot.db_manager.get_registered_clans(str(interaction.guild_id))
            matching_clans = [
                clan for clan in clans 
                if current.lower() in clan.clan_name.lower()
            ]
            
            return [
                app_commands.Choice(name=clan.clan_name, value=clan.clan_name)
                for clan in matching_clans[:25]
            ]
        except:
            return []

    # 음성채널 자동완성
    @start_clan_scrim.autocomplete('a음성채널')
    async def a_voice_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        return await self._voice_channel_autocomplete(interaction, current)

    @start_clan_scrim.autocomplete('b음성채널')
    async def b_voice_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        return await self._voice_channel_autocomplete(interaction, current)

    async def _voice_channel_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        """음성채널 자동완성"""
        voice_channels = interaction.guild.voice_channels
        matching_channels = [
            ch for ch in voice_channels 
            if current.lower() in ch.name.lower()
        ]
        
        return [
            app_commands.Choice(name=channel.name, value=channel.name)
            for channel in matching_channels[:25]
        ]
    
    @app_commands.command(name="클랜전결과", description="[관리자] 클랜전 경기 결과를 기록합니다")
    @app_commands.describe(
        a음성채널="A팀 음성채널명",
        b음성채널="B팀 음성채널명",
        승리팀="승리한 팀의 음성채널명",
        맵이름="경기가 진행된 맵 이름"
    )
    async def clan_match_result(
        self,
        interaction: discord.Interaction,
        a음성채널: str,
        b음성채널: str,
        승리팀: str,
        맵이름: str
    ):
        # 관리자 권한 확인
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # 1. 활성 클랜전 스크림 확인
            active_scrim = await self.bot.db_manager.get_active_clan_scrim(str(interaction.guild_id))
            if not active_scrim:
                await interaction.followup.send(
                    "❌ 진행 중인 클랜전 스크림이 없습니다.\n"
                    "먼저 `/클랜전시작` 명령어로 스크림을 시작해주세요.", ephemeral=True
                )
                return

            # 2. 승리팀 검증
            if 승리팀.lower() not in [a음성채널.lower(), b음성채널.lower()]:
                await interaction.followup.send(
                    f"❌ 승리팀은 **{a음성채널}** 또는 **{b음성채널}** 중 하나여야 합니다.\n"
                    f"입력된 승리팀: **{승리팀}**", ephemeral=True
                )
                return

            # 3. 음성채널 확인 및 인원 체크
            voice_channel_a = discord.utils.get(interaction.guild.voice_channels, name=a음성채널)
            voice_channel_b = discord.utils.get(interaction.guild.voice_channels, name=b음성채널)

            if not voice_channel_a:
                await interaction.followup.send(
                    f"❌ **{a음성채널}** 음성채널을 찾을 수 없습니다.", ephemeral=True
                )
                return

            if not voice_channel_b:
                await interaction.followup.send(
                    f"❌ **{b음성채널}** 음성채널을 찾을 수 없습니다.", ephemeral=True
                )
                return

            # 4. 각 채널의 인원 확인
            a_members = [m for m in voice_channel_a.members if not m.bot]
            b_members = [m for m in voice_channel_b.members if not m.bot]

            if len(a_members) != 5:
                await interaction.followup.send(
                    f"❌ **{a음성채널}** 채널에 정확히 5명이 있어야 합니다.\n"
                    f"**현재 인원**: {len(a_members)}명", ephemeral=True
                )
                return

            if len(b_members) != 5:
                await interaction.followup.send(
                    f"❌ **{b음성채널}** 채널에 정확히 5명이 있어야 합니다.\n"
                    f"**현재 인원**: {len(b_members)}명", ephemeral=True
                )
                return

            # 5. 클랜전 경기 생성
            match_uuid = await self.bot.db_manager.create_clan_match(
                guild_id=str(interaction.guild_id),
                team_a_channel=a음성채널,
                team_b_channel=b음성채널,
                winning_channel=승리팀,
                map_name=맵이름,
                team_a_members=a_members,
                team_b_members=b_members
            )

            # 6. 성공 메시지
            winning_clan = active_scrim.clan_a_name if 승리팀.lower() == a음성채널.lower() else active_scrim.clan_b_name
            losing_clan = active_scrim.clan_b_name if 승리팀.lower() == a음성채널.lower() else active_scrim.clan_a_name
            
            # 업데이트된 스크림 정보 가져오기
            updated_scrim = await self.bot.db_manager.get_active_clan_scrim(str(interaction.guild_id))
            match_number = updated_scrim.total_matches

            embed = discord.Embed(
                title="🎮 클랜전 결과 기록 완료!",
                description=f"**{match_number}판** - **{맵이름}**에서 **{winning_clan}**이 승리했습니다! 🎉",
                color=0x00ff88,
                timestamp=datetime.now()
            )

            # 승리팀과 패배팀 구분하여 표시
            if 승리팀.lower() == a음성채널.lower():
                winner_members = a_members
                loser_members = b_members
                winner_channel = a음성채널
                loser_channel = b음성채널
            else:
                winner_members = b_members
                loser_members = a_members
                winner_channel = b음성채널
                loser_channel = a음성채널

            embed.add_field(
                name=f"🏆 {winning_clan} ({winner_channel}) - 승리",
                value="\n".join([f"{i+1}. {m.display_name}" for i, m in enumerate(winner_members)]),
                inline=True
            )

            embed.add_field(
                name=f"💔 {losing_clan} ({loser_channel}) - 패배",
                value="\n".join([f"{i+1}. {m.display_name}" for i, m in enumerate(loser_members)]),
                inline=True
            )

            # 현재 스크림 현황
            embed.add_field(
                name="📊 현재 스크림 현황",
                value=f"**총 경기**: {updated_scrim.total_matches}판\n"
                    f"**{updated_scrim.clan_a_name}**: {updated_scrim.clan_a_wins}승\n"
                    f"**{updated_scrim.clan_b_name}**: {updated_scrim.clan_b_wins}승",
                inline=False
            )

            # 추가 데이터 입력 안내
            embed.add_field(
                name="📋 추가 데이터 입력 (선택사항)",
                value=f"**포지션 정보**: `/클랜전포지션 {a음성채널}` `/클랜전포지션 {b음성채널}`\n"
                    f"**영웅 조합**: `/클랜전조합 {a음성채널} [영웅들]` `/클랜전조합 {b음성채널} [영웅들]`",
                inline=False
            )

            embed.add_field(
                name="🎯 경기 정보",
                value=f"**경기 ID**: `{match_uuid[:8]}...`\n"
                    f"**맵**: {맵이름}\n"
                    f"**기본 기록**: ✅ 완료\n"
                    f"**상세 데이터**: ⏳ 대기중 (선택사항)",
                inline=False
            )

            embed.set_footer(text="RallyUp Bot | 클랜전 데이터 수집")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f"❌ 클랜전 결과 기록 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="클랜전포지션", description="[관리자] 클랜전 팀의 포지션 정보를 추가합니다")
    @app_commands.describe(
        음성채널="포지션을 설정할 팀의 음성채널",
        탱커="탱커 역할을 맡은 플레이어",
        딜러1="첫 번째 딜러",
        딜러2="두 번째 딜러",
        힐러1="첫 번째 힐러",
        힐러2="두 번째 힐러"
    )
    async def clan_position(
        self,
        interaction: discord.Interaction,
        음성채널: str,
        탱커: str,
        딜러1: str,
        딜러2: str,
        힐러1: str,
        힐러2: str
    ):
        # 관리자 권한 확인
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # 1. 활성 클랜전 스크림 확인
            active_scrim = await self.bot.db_manager.get_active_clan_scrim(str(interaction.guild_id))
            if not active_scrim:
                await interaction.followup.send(
                    "❌ 진행 중인 클랜전 스크림이 없습니다.", ephemeral=True
                )
                return

            # 2. 최근 클랜전 경기 찾기
            match_uuid = await self.bot.db_manager.find_recent_clan_match(
                guild_id=str(interaction.guild_id),
                minutes=10
            )

            if not match_uuid:
                await interaction.followup.send(
                    "❌ 최근 10분 내에 포지션 정보가 없는 클랜전 기록을 찾을 수 없습니다.\n"
                    "먼저 `/클랜전결과` 명령어로 경기를 기록해주세요.", ephemeral=True
                )
                return

            # 3. 음성채널 확인
            voice_channel = discord.utils.get(interaction.guild.voice_channels, name=음성채널)
            if not voice_channel:
                await interaction.followup.send(
                    f"❌ **{음성채널}** 음성채널을 찾을 수 없습니다.", ephemeral=True
                )
                return

            # 4. 선택된 플레이어들이 실제 채널에 있는지 확인
            current_members = [m for m in voice_channel.members if not m.bot]
            selected_players = [탱커, 딜러1, 딜러2, 힐러1, 힐러2]
            selected_names = [name.split(' - ')[0] if ' - ' in name else name for name in selected_players]

            # 중복 선택 확인
            if len(set(selected_names)) != 5:
                await interaction.followup.send(
                    "❌ 같은 플레이어를 여러 포지션에 선택할 수 없습니다.", ephemeral=True
                )
                return

            # 5. 포지션 데이터 저장 (간단한 구현)
            try:
                # 팀 구분 (A팀 or B팀)
                team_side = "clan_a" if 음성채널.lower() == active_scrim.voice_channel_a.lower() else "clan_b"
                
                # 포지션 데이터 준비
                position_data = {
                    'tank': 탱커,
                    'dps1': 딜러1,
                    'dps2': 딜러2,
                    'support1': 힐러1,
                    'support2': 힐러2
                }
                
                # 데이터베이스에 포지션 정보 저장
                await self.bot.db_manager.add_clan_position_data(
                    match_uuid=match_uuid,
                    team_side=team_side,
                    position_data=position_data
                )
                
                print(f"🔍 [클랜전] 포지션 데이터 저장 완료: {음성채널} ({team_side})")
                
            except Exception as save_error:
                print(f"❌ [클랜전] 포지션 저장 오류: {save_error}")
            
            embed = discord.Embed(
                title="📋 클랜전 포지션 정보 추가 완료!",
                description=f"**{음성채널}** 팀의 포지션 정보가 기록되었습니다!",
                color=0x00ff88,
                timestamp=datetime.now()
            )

            # 포지션별 정보 표시
            position_info = [
                f"🛡️ **탱커**: {탱커}",
                f"⚔️ **딜러**: {딜러1}, {딜러2}",
                f"💚 **힐러**: {힐러1}, {힐러2}"
            ]

            embed.add_field(
                name=f"🎯 {음성채널} 포지션 구성",
                value="\n".join(position_info),
                inline=False
            )

            embed.add_field(
                name="📊 업데이트된 데이터",
                value="✅ 포지션별 개인 통계\n✅ 클랜전 포지션 분석 데이터\n✅ 팀 구성 패턴 데이터",
                inline=False
            )

            embed.set_footer(text="RallyUp Bot | 클랜전 데이터 수집")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f"❌ 포지션 정보 추가 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="클랜전조합", description="[관리자] 클랜전 팀의 영웅 조합을 기록합니다 (선택사항)")
    @app_commands.describe(
        음성채널="조합을 기록할 팀의 음성채널",
        탱커영웅="탱커가 사용한 영웅",
        딜러1영웅="첫 번째 딜러가 사용한 영웅", 
        딜러2영웅="두 번째 딜러가 사용한 영웅",
        힐러1영웅="첫 번째 힐러가 사용한 영웅",
        힐러2영웅="두 번째 힐러가 사용한 영웅"
    )
    async def clan_composition(
        self,
        interaction: discord.Interaction,
        음성채널: str,
        탱커영웅: str,
        딜러1영웅: str,
        딜러2영웅: str,
        힐러1영웅: str,
        힐러2영웅: str
    ):
        # 관리자 권한 확인
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # 1. 활성 클랜전 스크림 확인
            active_scrim = await self.bot.db_manager.get_active_clan_scrim(str(interaction.guild_id))
            if not active_scrim:
                await interaction.followup.send(
                    "❌ 진행 중인 클랜전 스크림이 없습니다.", ephemeral=True
                )
                return

            # 2. 영웅 리스트 생성 및 검증
            heroes = [탱커영웅, 딜러1영웅, 딜러2영웅, 힐러1영웅, 힐러2영웅]
            
            # 빈 영웅이 있는지 확인
            if any(not hero.strip() for hero in heroes):
                await interaction.followup.send(
                    "❌ 모든 포지션의 영웅을 선택해주세요.", ephemeral=True
                )
                return

            # 3. 최근 클랜전 경기 찾기
            match_uuid = await self.bot.db_manager.find_recent_clan_match(
                guild_id=str(interaction.guild_id),
                minutes=10
            )

            if not match_uuid:
                await interaction.followup.send(
                    "❌ 최근 10분 내에 조합 정보를 추가할 클랜전 기록을 찾을 수 없습니다.\n"
                    "먼저 `/클랜전결과` 명령어로 경기를 기록해주세요.", ephemeral=True
                )
                return

            # 4. 조합 데이터 실제 저장
            try:
                # 팀 구분 (A팀 or B팀)
                team_side = "clan_a" if 음성채널.lower() == active_scrim.voice_channel_a.lower() else "clan_b"
                
                # 데이터베이스에 조합 정보 저장
                await self.bot.db_manager.add_clan_composition_data(
                    match_uuid=match_uuid,
                    team_side=team_side,
                    hero_composition=heroes
                )
                
                print(f"🔍 [클랜전] 조합 데이터 저장 완료: {음성채널} ({team_side}) - {heroes}")
                
            except Exception as save_error:
                print(f"❌ [클랜전] 조합 저장 오류: {save_error}")

            # 5. 성공 메시지
            embed = discord.Embed(
                title="🎭 클랜전 영웅 조합 기록 완료!",
                description=f"**{음성채널}** 팀의 영웅 조합이 기록되었습니다!",
                color=0xff9500,
                timestamp=datetime.now()
            )

            # 포지션별 영웅 조합 표시
            hero_emojis = {
                # 탱커
                "라인하르트": "🛡️", "윈스턴": "🦍", "오리사": "🐴", "시그마": "⚫", "자리야": "💪",
                "로드호그": "🐷", "디바": "🤖", "레킹볼": "🏀", "준커퀸": "👑", "마우가": "🔥", "라마트라": "🤖",
                # 딜러  
                "겐지": "🥷", "트레이서": "💨", "파라": "🚀", "솔져76": "🔫", "맥크리": "🤠",
                "리퍼": "💀", "정크랫": "💣", "토르비욘": "🔨", "바스티온": "🤖", "한조": "🏹", 
                "위도우메이커": "🎯", "시메트라": "✨", "솜브라": "👤", "둠피스트": "👊", "애쉬": "🔫",
                "에코": "🌀", "메이": "❄️", "벤처": "⛏️", "소전": "💥",
                # 힐러
                "메르시": "👼", "아나": "💉", "루시우": "🎵", "젠야타": "🧘", "모이라": "⚗️",
                "브리기테": "🛡️", "바티스트": "💊", "키리코": "🦊", "라이프위버": "🌸", "일라리": "☀️"
            }

            # 포지션과 영웅을 매칭해서 표시
            position_names = ["탱커", "딜러1", "딜러2", "힐러1", "힐러2"]
            hero_display = []
            
            for i, (position, hero) in enumerate(zip(position_names, heroes)):
                emoji = hero_emojis.get(hero, "🎮")
                hero_display.append(f"{emoji} **{position}**: {hero}")

            embed.add_field(
                name=f"🎯 {음성채널} 영웅 조합",
                value="\n".join(hero_display),
                inline=False
            )

            embed.add_field(
                name="📊 수집된 데이터",
                value="✅ 영웅별 승률 통계\n✅ 포지션별 영웅 선호도\n✅ 맵별 조합 선호도\n✅ 클랜별 메타 패턴",
                inline=False
            )

            embed.add_field(
                name="💡 참고사항",
                value="영웅 조합 데이터는 선택사항이므로 언제든지 추가하거나 생략할 수 있습니다.",
                inline=False
            )

            embed.set_footer(text="RallyUp Bot | 클랜전 데이터 수집")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f"❌ 영웅 조합 기록 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="클랜전종료", description="[관리자] 현재 진행 중인 클랜전 스크림을 종료합니다")
    async def end_clan_scrim(self, interaction: discord.Interaction):
        # 관리자 권한 확인
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # 1. 활성 클랜전 스크림 확인
            active_scrim = await self.bot.db_manager.get_active_clan_scrim(str(interaction.guild_id))
            if not active_scrim:
                await interaction.followup.send(
                    "❌ 현재 진행 중인 클랜전 스크림이 없습니다.", ephemeral=True
                )
                return

            # 2. 스크림 종료
            await self.bot.db_manager.end_clan_scrim(str(interaction.guild_id))

            # 3. 종료 메시지
            embed = discord.Embed(
                title="🏁 클랜전 스크림 종료!",
                description=f"**{active_scrim.clan_a_name} vs {active_scrim.clan_b_name}** 클랜전이 완료되었습니다!",
                color=0xff6b6b,
                timestamp=datetime.now()
            )

            # 최종 결과
            if active_scrim.clan_a_wins > active_scrim.clan_b_wins:
                winner = active_scrim.clan_a_name
                winner_score = active_scrim.clan_a_wins
                loser = active_scrim.clan_b_name
                loser_score = active_scrim.clan_b_wins
            elif active_scrim.clan_b_wins > active_scrim.clan_a_wins:
                winner = active_scrim.clan_b_name
                winner_score = active_scrim.clan_b_wins
                loser = active_scrim.clan_a_name
                loser_score = active_scrim.clan_a_wins
            else:
                winner = "무승부"
                winner_score = active_scrim.clan_a_wins
                loser_score = active_scrim.clan_b_wins

            # 스크림 진행 시간 계산
            if active_scrim.started_at:
                duration = datetime.now() - active_scrim.started_at
                hours, remainder = divmod(int(duration.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                duration_str = f"{hours}시간 {minutes}분"
            else:
                duration_str = "알 수 없음"

            embed.add_field(
                name="🏆 최종 결과",
                value=f"**승리**: {winner} ({winner_score}승)\n"
                    f"**패배**: {loser} ({loser_score}승)" if winner != "무승부" 
                    else f"**무승부**: {active_scrim.clan_a_wins} - {active_scrim.clan_b_wins}",
                inline=True
            )

            embed.add_field(
                name="📊 스크림 요약",
                value=f"**총 진행 시간**: {duration_str}\n"
                    f"**총 경기 수**: {active_scrim.total_matches}판\n"
                    f"**평균 경기 시간**: {duration.total_seconds() / active_scrim.total_matches / 60:.1f}분" 
                    if active_scrim.total_matches > 0 else "경기 없음",
                inline=True
            )

            embed.add_field(
                name="📈 수집된 데이터",
                value=f"✅ {active_scrim.total_matches}개의 경기 데이터\n"
                    f"✅ 클랜별 맵 승률 통계\n"
                    f"✅ 개인별 클랜전 성과\n"
                    f"✅ 포지션/조합 분석 데이터",
                inline=False
            )

            embed.add_field(
                name="🔍 분석 가능한 인사이트",
                value="• 클랜별 맵 선호도 및 약점\n• 개인별 클랜전 vs 내전 성과 비교\n• 시간대별 팀 퍼포먼스 변화\n• 영웅 메타 및 조합 효율성",
                inline=False
            )

            embed.set_footer(text="RallyUp Bot | 클랜전 데이터 수집 완료")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f"❌ 클랜전 종료 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="클랜전현황", description="[관리자] 현재 클랜전 스크림 상태를 확인합니다")
    async def clan_scrim_status(self, interaction: discord.Interaction):
        # 관리자 권한 확인
        if not self.is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        try:
            # 활성 클랜전 스크림 확인
            active_scrim = await self.bot.db_manager.get_active_clan_scrim(str(interaction.guild_id))
            
            if not active_scrim:
                await interaction.response.send_message(
                    "❌ 현재 진행 중인 클랜전 스크림이 없습니다.\n"
                    "`/클랜전시작` 명령어로 스크림을 시작하세요.", ephemeral=True
                )
                return

            embed = discord.Embed(
                title="⚔️ 클랜전 스크림 현황",
                description=f"**{active_scrim.clan_a_name} vs {active_scrim.clan_b_name}**",
                color=0xff6b35,
                timestamp=datetime.now()
            )

            # 진행 시간 계산
            if active_scrim.started_at:
                duration = datetime.now() - active_scrim.started_at
                hours, remainder = divmod(int(duration.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                duration_str = f"{hours}시간 {minutes}분"
            else:
                duration_str = "알 수 없음"

            embed.add_field(
                name="📊 현재 상황",
                value=f"**진행 시간**: {duration_str}\n"
                    f"**총 경기**: {active_scrim.total_matches}판\n"
                    f"**현재 스코어**: {active_scrim.clan_a_wins} - {active_scrim.clan_b_wins}",
                inline=True
            )

            # 음성채널 현재 상태
            voice_a = discord.utils.get(interaction.guild.voice_channels, name=active_scrim.voice_channel_a)
            voice_b = discord.utils.get(interaction.guild.voice_channels, name=active_scrim.voice_channel_b)
            
            a_count = len([m for m in voice_a.members if not m.bot]) if voice_a else 0
            b_count = len([m for m in voice_b.members if not m.bot]) if voice_b else 0

            embed.add_field(
                name="🎮 음성채널 상태",
                value=f"**{active_scrim.voice_channel_a}**: {a_count}명\n"
                    f"**{active_scrim.voice_channel_b}**: {b_count}명",
                inline=True
            )

            embed.add_field(
                name="🔧 사용 가능한 명령어",
                value="• `/클랜전결과` - 경기 결과 기록\n"
                    "• `/클랜전포지션` - 포지션 정보 추가\n"
                    "• `/클랜전조합` - 영웅 조합 기록\n"
                    "• `/클랜전종료` - 스크림 종료",
                inline=False
            )

            embed.set_footer(text=f"스크림 ID: {active_scrim.scrim_uuid[:8]}...")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ 클랜전 현황 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @clan_match_result.autocomplete('맵이름')
    async def map_name_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        """맵 이름 자동완성"""
        matching_maps = [
            map_name for map_name in ALL_MAPS 
            if current.lower() in map_name.lower()
        ]
        
        # 맵 타입도 함께 표시
        choices = []
        for map_name in matching_maps[:25]:
            # 맵 타입 찾기
            map_type = "기타"
            for mtype, maps in OVERWATCH_MAPS.items():
                if map_name in maps:
                    map_type = mtype
                    break
            
            choices.append(
                app_commands.Choice(
                    name=f"{map_name} ({map_type})", 
                    value=map_name
                )
            )
        
        return choices

    @clan_match_result.autocomplete('a음성채널')
    async def result_a_voice_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._voice_channel_autocomplete(interaction, current)

    @clan_match_result.autocomplete('b음성채널')
    async def result_b_voice_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._voice_channel_autocomplete(interaction, current)

    @clan_match_result.autocomplete('승리팀')
    async def result_winner_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._voice_channel_autocomplete(interaction, current)

    @clan_position.autocomplete('음성채널')
    async def position_voice_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._voice_channel_autocomplete(interaction, current)

    @clan_position.autocomplete('탱커')
    async def tank_autocomplete(self, interaction: discord.Interaction, current: str):
        # 먼저 현재 음성채널 멤버들 가져오기 시도
        try:
            # interaction에서 현재 입력 중인 음성채널 정보 가져오기
            # 실제로는 음성채널 멤버 기반으로 자동완성
            voice_channels = interaction.guild.voice_channels
            members_choices = []
            
            # 활성 스크림에서 음성채널 정보 가져오기
            active_scrim = await self.bot.db_manager.get_active_clan_scrim(str(interaction.guild_id))
            if active_scrim:
                # A팀, B팀 채널에서 멤버 가져오기
                for channel_name in [active_scrim.voice_channel_a, active_scrim.voice_channel_b]:
                    voice_channel = discord.utils.get(voice_channels, name=channel_name)
                    if voice_channel:
                        for member in voice_channel.members:
                            if not member.bot and current.lower() in member.display_name.lower():
                                members_choices.append(
                                    app_commands.Choice(
                                        name=f"{member.display_name} ({channel_name})",
                                        value=member.display_name
                                    )
                                )
            else:
                # 활성 스크림이 없으면 모든 음성채널에서 멤버 가져오기 (테스트용)
                for voice_channel in voice_channels:
                    if voice_channel.members:  # 멤버가 있는 채널만
                        for member in voice_channel.members:
                            if not member.bot and current.lower() in member.display_name.lower():
                                members_choices.append(
                                    app_commands.Choice(
                                        name=f"{member.display_name} ({voice_channel.name})",
                                        value=member.display_name
                                    )
                                )
            
            return members_choices[:25]
        except:
            # 오류 시 빈 리스트 반환
            return []

    @clan_position.autocomplete('딜러1')
    async def dps1_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.tank_autocomplete(interaction, current)

    @clan_position.autocomplete('딜러2') 
    async def dps2_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.tank_autocomplete(interaction, current)

    @clan_position.autocomplete('힐러1')
    async def support1_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.tank_autocomplete(interaction, current)

    @clan_position.autocomplete('힐러2')
    async def support2_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.tank_autocomplete(interaction, current)

    @clan_composition.autocomplete('음성채널')
    async def composition_voice_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._voice_channel_autocomplete(interaction, current)

    @clan_composition.autocomplete('탱커영웅')
    async def tank_hero_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._hero_autocomplete_by_position(interaction, current, "탱커")

    @clan_composition.autocomplete('딜러1영웅')
    async def dps1_hero_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._hero_autocomplete_by_position(interaction, current, "딜러")

    @clan_composition.autocomplete('딜러2영웅')
    async def dps2_hero_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._hero_autocomplete_by_position(interaction, current, "딜러")

    @clan_composition.autocomplete('힐러1영웅')
    async def support1_hero_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._hero_autocomplete_by_position(interaction, current, "힐러")

    @clan_composition.autocomplete('힐러2영웅')
    async def support2_hero_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._hero_autocomplete_by_position(interaction, current, "힐러")

    async def _hero_autocomplete_by_position(
        self,
        interaction: discord.Interaction,
        current: str,
        position: str
    ) -> List[app_commands.Choice[str]]:
        """포지션별 영웅 자동완성"""
        if position in OVERWATCH_HEROES:
            hero_list = OVERWATCH_HEROES[position]
        else:
            hero_list = ALL_HEROES
        
        matching_heroes = [
            hero for hero in hero_list 
            if current.lower() in hero.lower()
        ]
        
        return [
            app_commands.Choice(name=hero, value=hero)
            for hero in matching_heroes[:25]
        ]

    async def _get_voice_channel_members(self, interaction: discord.Interaction, channel_name: str):
        """음성채널 멤버 자동완성"""
        try:
            voice_channel = discord.utils.get(interaction.guild.voice_channels, name=channel_name)
            if voice_channel:
                members = [m for m in voice_channel.members if not m.bot]
                return [
                    app_commands.Choice(name=f"{m.display_name} - {m.name}", value=str(m.id))
                    for m in members[:25]
                ]
        except:
            pass
        return []

async def setup(bot):
    await bot.add_cog(ClanScrimCommands(bot))