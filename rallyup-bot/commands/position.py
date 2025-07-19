# commands/position.py
from typing import List
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from utils.helpers import validate_positions

class PositionCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="포지션", description="특정 내전 경기의 포지션 정보를 추가합니다")
    @app_commands.describe(
        team_a_channel="A팀 음성채널명",
        team_a_positions="A팀 포지션 구성 (예: 탱딜딜힐힐)",
        team_b_channel="B팀 음성채널명",
        team_b_positions="B팀 포지션 구성 (예: 딜탱딜힐힐)"
    )
    async def position(
        self, 
        interaction: discord.Interaction,
        team_a_channel: str,
        team_a_positions: str,
        team_b_channel: str,
        team_b_positions: str
    ):
        # 1. 포지션 형식 검증
        if not self._validate_positions(team_a_positions):
            await interaction.response.send_message(
                f"❌ A팀 포지션 형식이 올바르지 않습니다: `{team_a_positions}`\n\n"
                f"**오버워치 내전 구성:** 탱커1명, 딜러2명, 힐러2명\n"
                f"**올바른 예시:**\n"
                f"• `탱딜딜힐힐` - 탱커가 1번 순서\n"
                f"• `딜탱딜힐힐` - 탱커가 2번 순서\n"
                f"• `딜딜탱힐힐` - 탱커가 3번 순서\n\n"
                f"**규칙:** 반드시 탱1딜2힐2 구성",
                ephemeral=True
            )
            return
        
        if not self._validate_positions(team_b_positions):
            await interaction.response.send_message(
                f"❌ B팀 포지션 형식이 올바르지 않습니다: `{team_b_positions}`\n\n"
                f"**오버워치 내전 구성:** 탱커1명, 딜러2명, 힐러2명\n"
                f"**올바른 예시:**\n"
                f"• `탱딜딜힐힐` - 탱커가 1번 순서\n"
                f"• `딜탱딜힐힐` - 탱커가 2번 순서\n" 
                f"• `딜딜탱힐힐` - 탱커가 3번 순서\n\n"
                f"**규칙:** 반드시 탱1딜2힐2 구성",
                ephemeral=True
            )
            return
        
        try:
            # 2. 최근 매치 찾기
            match_uuid = await self.bot.db_manager.find_recent_match(
                guild_id=str(interaction.guild_id),
                user_id=str(interaction.user.id),
                minutes=10
            )
            
            if not match_uuid:
                await interaction.response.send_message(
                    "❌ 최근 10분 내에 포지션 정보가 없는 내전 기록을 찾을 수 없습니다.\n\n"
                    "**가능한 원인:**\n"
                    "• 최근에 참여한 내전이 없음\n"
                    "• 이미 포지션 정보가 추가됨\n"
                    "• 10분이 지났음\n\n"
                    "먼저 `/내전결과` 명령어로 경기를 기록해주세요.",
                    ephemeral=True
                )
                return
            
            # 3. 매치 참가자 정보 가져오기
            team1_participants, team2_participants = await self.bot.db_manager.get_match_participants(match_uuid)
            
            if not team1_participants or not team2_participants:
                await interaction.response.send_message(
                    "❌ 매치 참가자 정보를 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 4. 포지션 정보 추가
            await self.bot.db_manager.add_position_data(
                match_uuid=match_uuid,
                team1_positions=team_a_positions,
                team2_positions=team_b_positions
            )
            
            # 5. 성공 메시지 전송
            await self._send_success_message(
                interaction, match_uuid, team_a_positions, team_b_positions,
                team1_participants, team2_participants
            )
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 포지션 정보 추가 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    def _validate_positions(self, positions: str) -> bool:
        """포지션 검증"""
        return validate_positions(positions)
    
    async def _send_success_message(self, interaction, match_uuid, team_a_channel, team_b_channel,
                                  team_a_positions, team_b_positions, 
                                  team1_participants, team2_participants):
        """성공 메시지 전송"""
        
        embed = discord.Embed(
            title="📋 포지션 정보 추가 완료!",
            description=f"**{team_a_channel}** vs **{team_b_channel}** 경기의 포지션별 세부 통계가 업데이트되었습니다! 🎯",
            color=0x00ff88,
            timestamp=datetime.now()
        )
        
        # 팀A 포지션 정보
        team_a_positions_display = []
        position_emojis = {"탱": "🛡️", "딜": "⚔️", "힐": "💚"}
        
        for i, (participant, position) in enumerate(zip(team1_participants, team_a_positions)):
            emoji = position_emojis.get(position, "❓")
            status = "🏆" if participant.won else "💔"
            team_a_positions_display.append(f"{emoji} {position}: {participant.username} {status}")
        
        embed.add_field(
            name=f"🔵 {team_a_channel} ({team_a_positions})",
            value="\n".join(team_a_positions_display),
            inline=True
        )
        
        # 팀B 포지션 정보
        team_b_positions_display = []
        for i, (participant, position) in enumerate(zip(team2_participants, team_b_positions)):
            emoji = position_emojis.get(position, "❓")
            status = "🏆" if participant.won else "💔"
            team_b_positions_display.append(f"{emoji} {position}: {participant.username} {status}")
        
        embed.add_field(
            name=f"🔴 {team_b_channel} ({team_b_positions})",
            value="\n".join(team_b_positions_display),
            inline=True
        )
        
        # 분석 정보
        embed.add_field(
            name="📊 업데이트된 통계",
            value="✅ 포지션별 승률\n"
                  "✅ 개인 vs 개인 매치업\n"
                  "✅ 포지션 조합 분석\n"
                  "✅ 세부 전적 데이터",
            inline=False
        )
        
        # 경기 정보
        embed.add_field(
            name="🎮 경기 정보",
            value=f"**매치:** {team_a_channel} vs {team_b_channel}\n"
                  f"**경기 ID:** `{match_uuid[:8]}...`\n"
                  f"**기본 기록:** ✅ 완료\n"
                  f"**포지션 정보:** ✅ 완료\n"
                  f"**상세 분석:** 이제 가능!",
            inline=False
        )
        
        embed.set_footer(text="RallyUp Bot | 이제 포지션별 세부 통계를 확인할 수 있습니다!")
        
        await interaction.response.send_message(embed=embed)
    
    # 음성채널명 자동완성
    @position.autocomplete('team_a_channel')
    async def team_a_channel_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        return await self._voice_channel_autocomplete(interaction, current)
    
    @position.autocomplete('team_b_channel')
    async def team_b_channel_autocomplete(
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
        """음성채널명 자동완성"""
        voice_channels = interaction.guild.voice_channels
        
        # 현재 입력된 텍스트와 매칭되는 채널들 필터링
        matching_channels = [
            ch for ch in voice_channels 
            if current.lower() in ch.name.lower()
        ]
        
        # 최대 25개까지만 반환 (Discord 제한)
        return [
            app_commands.Choice(name=channel.name, value=channel.name)
            for channel in matching_channels[:25]
        ]

    # 포지션 자동완성
    @position.autocomplete('team_a_positions')
    async def team1_position_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        return self._get_position_choices(current)
    
    @position.autocomplete('team_b_positions')
    async def team2_position_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        return self._get_position_choices(current)
    
    def _get_position_choices(self, current: str) -> List[app_commands.Choice[str]]:
        """오버워치 5명 구성 (탱1딜2힐2) 조합 제공"""
        # 탱1딜2힐2 구성의 모든 순열 (총 60가지)
        import itertools
        
        positions = ['탱', '딜', '딜', '힐', '힐']
        
        # 중복 제거된 순열 생성
        unique_combinations = list(set([''.join(p) for p in itertools.permutations(positions)]))
        unique_combinations.sort()  # 정렬
        
        # 현재 입력과 매칭되는 조합들 필터링
        if current:
            matching = [combo for combo in unique_combinations if current in combo]
        else:
            # 입력이 없으면 자주 사용될만한 순서 우선 표시
            common_first = [
                '탱딜딜힐힐', '딜탱딜힐힐', '딜딜탱힐힐',  # 탱커가 앞쪽
                '힐딜딜힐탱', '딜힐딜힐탱', '딜딜힐힐탱',  # 탱커가 뒤쪽
                '딜딜힐탱힐', '딜힐딜탱힐', '힐딜딜탱힐'   # 탱커가 중간
            ]
            # 자주 사용되는 조합을 앞에, 나머지를 뒤에
            remaining = [combo for combo in unique_combinations if combo not in common_first]
            matching = common_first + remaining
        
        # 최대 25개까지만 반환 (Discord 제한)
        return [
            app_commands.Choice(name=combo, value=combo)
            for combo in matching[:25]
        ]

async def setup(bot):
    await bot.add_cog(PositionCommand(bot))