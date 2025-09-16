import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional
from datetime import datetime
import uuid

class ScrimSessionCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="내전시작", description="내전 세션을 시작하고 참여자를 등록합니다")
    @app_commands.describe(
        음성채널="내전 참여자들이 모인 음성채널명",
        세션명="내전 세션 이름 (선택사항)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def start_scrim(
        self, 
        interaction: discord.Interaction,
        음성채널: str,
        세션명: str = None
    ):
        await interaction.response.defer()
        
        try:
            # 1. 음성채널 찾기
            voice_channel = discord.utils.get(interaction.guild.voice_channels, name=음성채널)
            if not voice_channel:
                await interaction.followup.send(f"❌ '{음성채널}' 음성채널을 찾을 수 없습니다.", ephemeral=True)
                return
            
            # 2. 참여자 수집 (봇 제외)
            participants = [m for m in voice_channel.members if not m.bot]
            
            if len(participants) < 4:
                await interaction.followup.send(
                    f"❌ 최소 4명이 필요합니다. (현재: {len(participants)}명)",
                    ephemeral=True
                )
                return
            
            # 3. 기존 활성 세션 확인
            existing_session = await self.bot.db_manager.get_active_session(str(interaction.guild_id))
            if existing_session:
                await interaction.followup.send(
                    "❌ 이미 진행 중인 내전 세션이 있습니다.\n"
                    f"먼저 `/내전종료`를 실행하거나 기존 세션을 완료해주세요.",
                    ephemeral=True
                )
                return
            
            # 4. 새 세션 생성
            session_uuid = await self.bot.db_manager.create_scrim_session(
                guild_id=str(interaction.guild_id),
                voice_channel=음성채널,
                participants=participants,
                started_by=str(interaction.user.id),
                session_name=세션명
            )
            
            # 5. 성공 메시지
            embed = discord.Embed(
                title="🎮 내전 세션 시작!",
                description=f"**{voice_channel.name}** 채널에서 내전이 시작되었습니다!",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            # 참여자 목록 (2열로 표시)
            participants_list = []
            for i, participant in enumerate(participants):
                participants_list.append(f"{i+1}. {participant.display_name}")
            
            # 참여자를 두 그룹으로 나누기
            mid_point = len(participants_list) // 2
            left_column = participants_list[:mid_point + (len(participants_list) % 2)]
            right_column = participants_list[mid_point + (len(participants_list) % 2):]
            
            embed.add_field(
                name=f"👥 참여자 ({len(participants)}명)",
                value="\n".join(left_column) if left_column else "없음",
                inline=True
            )
            
            if right_column:
                embed.add_field(
                    name="​", # 공백 문자
                    value="\n".join(right_column),
                    inline=True
                )
            
            # 세션 정보
            session_info = f"**세션 ID**: `{session_uuid[:8]}...`\n"
            if 세션명:
                session_info += f"**세션명**: {세션명}\n"
            session_info += f"**시작 시간**: <t:{int(datetime.now().timestamp())}:F>\n"
            session_info += f"**운영자**: {interaction.user.display_name}"
            
            embed.add_field(
                name="📋 세션 정보",
                value=session_info,
                inline=False
            )
            
            # 다음 단계 안내
            embed.add_field(
                name="🔧 다음 단계",
                value="• `/팀배정` - 자동 팀 배정\n"
                      "• `/내전결과` - 경기 결과 기록\n"
                      "• `/세션현황` - 현재 세션 상태 확인\n"
                      "• `/내전종료` - 세션 종료",
                inline=False
            )
            
            embed.set_footer(text="모든 참여자의 게임 데이터가 자동으로 추적됩니다!")
            
            await interaction.followup.send(embed=embed)
            
            # 6. 각 참여자의 참여 횟수 업데이트
            await self.bot.db_manager.update_participation_counts(participants)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 세션 시작 중 오류: {str(e)}", ephemeral=True)

    @app_commands.command(name="내전세션현황", description="현재 진행 중인 내전 세션 상태를 확인합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def session_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            session_info = await self.bot.db_manager.get_active_session_details(str(interaction.guild_id))
            
            if not session_info:
                await interaction.followup.send(
                    "❌ 현재 진행 중인 내전 세션이 없습니다.\n"
                    "`/내전시작` 명령어로 세션을 시작해주세요.",
                    ephemeral=True
                )
                return
            
            session, participants, matches = session_info
            
            embed = discord.Embed(
                title="📊 내전 세션 현황",
                description=f"**{session['voice_channel']}** 채널 세션",
                color=0x0099ff
            )
            
            # 세션 기본 정보
            started_time = datetime.fromisoformat(session['started_at'])
            duration = datetime.now() - started_time
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            
            embed.add_field(
                name="⏱️ 세션 정보",
                value=f"**시작 시간**: <t:{int(started_time.timestamp())}:R>\n"
                      f"**진행 시간**: {hours}시간 {minutes}분\n"
                      f"**완료된 경기**: {len(matches)}경기\n"
                      f"**참여자 수**: {len(participants)}명",
                inline=True
            )
            
            # 현재 참여자들 (온라인 상태 표시)
            voice_channel = discord.utils.get(interaction.guild.voice_channels, name=session['voice_channel'])
            current_members = {m.id for m in voice_channel.members if not m.bot} if voice_channel else set()
            
            participants_status = []
            for p in participants[:10]:  # 최대 10명까지만 표시
                status = "🟢" if int(p['user_id']) in current_members else "🔴"
                participants_status.append(f"{status} {p['username']}")
            
            if len(participants) > 10:
                participants_status.append(f"... 외 {len(participants) - 10}명")
            
            embed.add_field(
                name="👥 참여자 현황",
                value="\n".join(participants_status),
                inline=True
            )
            
            # 최근 경기 결과
            if matches:
                recent_matches = []
                for match in matches[-3:]:  # 최근 3경기
                    winner = "1팀" if match['winning_team'] == 1 else "2팀"
                    match_time = datetime.fromisoformat(match['created_at'])
                    recent_matches.append(f"**{match['match_number']}경기**: {winner} 승리 (<t:{int(match_time.timestamp())}:R>)")
                
                embed.add_field(
                    name="🏆 최근 경기 결과",
                    value="\n".join(recent_matches),
                    inline=False
                )
            
            # 통계 정보
            if matches:
                team1_wins = sum(1 for m in matches if m['winning_team'] == 1)
                team2_wins = len(matches) - team1_wins
                
                embed.add_field(
                    name="📈 세션 통계",
                    value=f"**1팀 승**: {team1_wins}경기\n**2팀 승**: {team2_wins}경기\n**경기당 평균 시간**: {duration.total_seconds() / len(matches) / 60:.1f}분" if len(matches) > 0 else "아직 경기 없음",
                    inline=True
                )
            
            embed.set_footer(text=f"세션 ID: {session['session_uuid'][:8]}...")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 세션 현황 조회 중 오류: {str(e)}", ephemeral=True)

    @app_commands.command(name="내전종료", description="현재 진행 중인 내전 세션을 종료합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def end_scrim(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            session_info = await self.bot.db_manager.get_active_session_details(str(interaction.guild_id))
            
            if not session_info:
                await interaction.followup.send(
                    "❌ 현재 진행 중인 내전 세션이 없습니다.",
                    ephemeral=True
                )
                return
            
            session, participants, matches = session_info
            
            await self.bot.db_manager.end_scrim_session(session['id'])
            
            embed = discord.Embed(
                title="🏁 내전 세션 종료!",
                description=f"**{session['voice_channel']}** 채널 세션이 완료되었습니다",
                color=0xff9500,
                timestamp=datetime.now()
            )
            
            started_time = datetime.fromisoformat(session['started_at'])
            duration = datetime.now() - started_time
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            
            embed.add_field(
                name="📊 세션 요약",
                value=f"**총 진행 시간**: {hours}시간 {minutes}분\n"
                      f"**총 경기 수**: {len(matches)}경기\n"
                      f"**참여자 수**: {len(participants)}명\n"
                      f"**경기당 평균 시간**: {duration.total_seconds() / len(matches) / 60:.1f}분" if len(matches) > 0 else "경기 없음",
                inline=True
            )
            
            if matches:
                team1_wins = sum(1 for m in matches if m['winning_team'] == 1)
                team2_wins = len(matches) - team1_wins
                
                embed.add_field(
                    name="🏆 경기 결과",
                    value=f"**1팀**: {team1_wins}승\n**2팀**: {team2_wins}승",
                    inline=True
                )
            
            if participants:
                mvp_participants = sorted(participants, key=lambda x: x['join_order'])[:3]
                mvp_list = [f"🥇 {mvp_participants[0]['username']}"] if len(mvp_participants) > 0 else []
                if len(mvp_participants) > 1:
                    mvp_list.append(f"🥈 {mvp_participants[1]['username']}")
                if len(mvp_participants) > 2:
                    mvp_list.append(f"🥉 {mvp_participants[2]['username']}")
                
                embed.add_field(
                    name="🌟 활발한 참여자",
                    value="\n".join(mvp_list),
                    inline=False
                )
            
            embed.set_footer(text="모든 데이터가 개인 통계에 반영되었습니다!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 세션 종료 중 오류: {str(e)}", ephemeral=True)

    # 음성채널명 자동완성
    @start_scrim.autocomplete('음성채널')
    async def voice_channel_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        voice_channels = interaction.guild.voice_channels
        matching_channels = [
            ch for ch in voice_channels 
            if current.lower() in ch.name.lower()
        ]
        return [
            app_commands.Choice(name=channel.name, value=channel.name)
            for channel in matching_channels[:25]
        ]

async def setup(bot):
    await bot.add_cog(ScrimSessionCommands(bot))