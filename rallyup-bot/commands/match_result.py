import discord
from discord.ext import commands
from discord import app_commands
from typing import List
from datetime import datetime
from utils.helpers import validate_positions

class MatchResultCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="내전결과", description="A팀 vs B팀 내전 결과를 기록합니다")
    @app_commands.describe(
        team_a="A팀 음성채널명",
        team_b="B팀 음성채널명", 
        winner="승리한 팀의 음성채널명"
    )
    async def match_result(
        self, 
        interaction: discord.Interaction,
        team_a: str,
        team_b: str,
        winner: str
    ):
        # 1. 기본 검증
        validation_result = await self._validate_input(
            interaction, team_a, team_b, winner
        )
        if not validation_result:
            return
        
        team1_channel, team2_channel, team1_members, team2_members = validation_result
        
        # 2. 승리팀 결정
        if winner.lower() == team_a.lower():
            winning_team = 1
            winning_channel_name = team_a
            losing_channel_name = team_b
        else:
            winning_team = 2
            winning_channel_name = team_b
            losing_channel_name = team_a
        
        try:
            # 3. 데이터베이스에 매치 생성
            match_uuid = await self.bot.db_manager.create_match(
                guild_id=str(interaction.guild_id),
                team1_channel=team_a,
                team2_channel=team_b,
                winning_team=winning_team,
                team1_members=team1_members,
                team2_members=team2_members
            )
            
            # 4. 성공 메시지 전송
            await self._send_success_message(
                interaction, team_a, team_b, winning_channel_name, 
                losing_channel_name, team1_members, team2_members, match_uuid
            )
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 데이터베이스 저장 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    async def _validate_input(self, interaction, team1_name, team2_name, winner_name):
        """입력값 검증 및 음성채널 정보 수집"""
        
        # 1. 승리팀이 A팀/B팀 중 하나인지 확인
        if winner_name.lower() not in [team1_name.lower(), team2_name.lower()]:
            await interaction.response.send_message(
                f"❌ 승리팀은 **{team1_name}** 또는 **{team2_name}** 중 하나여야 합니다.\n"
                f"입력된 승리팀: **{winner_name}**",
                ephemeral=True
            )
            return None
        
        # 2. A팀과 B팀이 같은 이름이 아닌지 확인
        if team1_name.lower() == team2_name.lower():
            await interaction.response.send_message(
                "❌ A팀과 B팀은 서로 다른 음성채널이어야 합니다.",
                ephemeral=True
            )
            return None
        
        # 3. 음성채널 찾기
        team1_channel = await self._find_voice_channel(interaction, team1_name)
        if not team1_channel:
            return None
        
        team2_channel = await self._find_voice_channel(interaction, team2_name)
        if not team2_channel:
            return None
        
        # 4. 각 채널의 인원 확인
        team1_members = [m for m in team1_channel.members if not m.bot]
        team2_members = [m for m in team2_channel.members if not m.bot]
        
        if len(team1_members) != 5:
            await interaction.response.send_message(
                f"❌ **{team1_name}** 음성채널에 5명이 있어야 합니다.\n"
                f"**현재 인원:** {len(team1_members)}명\n"
                f"**참여자:** {', '.join([m.display_name for m in team1_members]) if team1_members else '없음'}",
                ephemeral=True
            )
            return None
        
        if len(team2_members) != 5:
            await interaction.response.send_message(
                f"❌ **{team2_name}** 음성채널에 5명이 있어야 합니다.\n"
                f"**현재 인원:** {len(team2_members)}명\n"
                f"**참여자:** {', '.join([m.display_name for m in team2_members]) if team2_members else '없음'}",
                ephemeral=True
            )
            return None
        
        # 5. 중복 참가자 확인
        team1_ids = {m.id for m in team1_members}
        team2_ids = {m.id for m in team2_members}
        overlap = team1_ids & team2_ids
        
        if overlap:
            overlap_names = [m.display_name for m in team1_members + team2_members if m.id in overlap]
            await interaction.response.send_message(
                f"❌ 같은 사용자가 양팀에 모두 참여할 수 없습니다.\n"
                f"**중복 참가자:** {', '.join(overlap_names)}",
                ephemeral=True
            )
            return None
        
        return team1_channel, team2_channel, team1_members, team2_members
    
    async def _find_voice_channel(self, interaction: discord.Interaction, channel_name: str):
        """음성채널 찾기"""
        voice_channels = [ch for ch in interaction.guild.voice_channels 
                         if ch.name.lower() == channel_name.lower()]
        
        if not voice_channels:
            # 비슷한 이름의 채널 찾기
            similar_channels = [ch for ch in interaction.guild.voice_channels 
                              if channel_name.lower() in ch.name.lower()]
            
            if similar_channels:
                similar_names = ", ".join([f"`{ch.name}`" for ch in similar_channels[:3]])
                await interaction.response.send_message(
                    f"❌ **{channel_name}** 음성채널을 찾을 수 없습니다.\n\n"
                    f"**비슷한 채널들:** {similar_names}\n"
                    f"정확한 채널명을 입력해주세요.",
                    ephemeral=True
                )
            else:
                channel_list = ", ".join([f"`{ch.name}`" for ch in interaction.guild.voice_channels[:5]])
                await interaction.response.send_message(
                    f"❌ **{channel_name}** 음성채널을 찾을 수 없습니다.\n\n"
                    f"**사용 가능한 음성채널:** {channel_list}{'...' if len(interaction.guild.voice_channels) > 5 else ''}",
                    ephemeral=True
                )
            return None
        
        return voice_channels[0]
    
    async def _send_success_message(self, interaction, team1_name, team2_name, 
                                  winning_name, losing_name, team1_members, team2_members, match_uuid):
        """성공 메시지 전송"""
        
        # 승리팀과 패배팀 구분
        if winning_name.lower() == team1_name.lower():
            winner_members = team1_members
            loser_members = team2_members
        else:
            winner_members = team2_members
            loser_members = team1_members
        
        embed = discord.Embed(
            title="🎮 내전 결과 기록 완료!",
            description=f"**{winning_name}** vs **{losing_name}** 경기에서 **{winning_name}**이 승리했습니다! 🎉",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        # 승리팀 정보
        winner_list = "\n".join([f"{i+1}. {member.display_name}" for i, member in enumerate(winner_members)])
        embed.add_field(
            name=f"🏆 {winning_name} (승리)",
            value=winner_list,
            inline=True
        )
        
        # 패배팀 정보
        loser_list = "\n".join([f"{i+1}. {member.display_name}" for i, member in enumerate(loser_members)])
        embed.add_field(
            name=f"💔 {losing_name} (패배)",
            value=loser_list,
            inline=True
        )
        
        # 포지션 추가 안내
        embed.add_field(
            name="📋 포지션 정보 추가하기",
            value=f"포지션별 세부 통계를 원한다면:\n"
                  f"`/포지션 탱딜딜힐힐 딜탱딜힐힐`\n\n"
                  f"**순서:** 위에 표시된 1-5번 순서대로\n"
                  f"**{team1_name}팀 포지션** **{team2_name}팀 포지션**",
            inline=False
        )
        
        # 경기 정보
        embed.add_field(
            name="📊 경기 정보",
            value=f"**경기 ID:** `{match_uuid[:8]}...`\n"
                  f"**기본 승패 기록:** ✅ 완료\n"
                  f"**포지션 정보:** ⏳ 대기중",
            inline=False
        )
        
        embed.set_footer(text="RallyUp Bot | 포지션 정보는 선택사항입니다")
        
        await interaction.response.send_message(embed=embed)

    # 음성채널명 자동완성 기능들
    @match_result.autocomplete('team_a')
    async def team1_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        return await self._voice_channel_autocomplete(interaction, current)
    
    @match_result.autocomplete('team_b')
    async def team2_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        return await self._voice_channel_autocomplete(interaction, current)
    
    @match_result.autocomplete('winner')
    async def winner_autocomplete(
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
        """음성채널명 자동완성 공통 함수"""
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

async def setup(bot):
    await bot.add_cog(MatchResultCommand(bot))