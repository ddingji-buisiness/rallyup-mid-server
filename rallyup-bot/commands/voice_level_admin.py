import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class VoiceLevelAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_manager
    
    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인"""
        # 서버 관리자 권한 확인
        if interaction.user.guild_permissions.administrator:
            return True
        
        # DB에 등록된 관리자 확인
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        # admin_system에 있는 메서드 사용
        async with self.db.get_connection() as db:
            cursor = await db.execute('''
                SELECT id FROM server_admins 
                WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
            ''', (guild_id, user_id))
            return await cursor.fetchone() is not None
    
    @app_commands.command(name="음성레벨_활성화", description="음성 레벨 시스템을 활성화합니다")
    @app_commands.describe(알림채널="알림을 받을 텍스트 채널")  
    async def enable_voice_level(
        self,
        interaction: discord.Interaction,
        알림채널: discord.TextChannel = None  
    ):
        """음성 레벨 시스템 활성화"""
        try:
            # 권한 확인
            if not await self.is_admin(interaction):
                await interaction.response.send_message(
                    "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            guild_id = str(interaction.guild.id)
            
            # 활성화
            await self.db.set_voice_level_enabled(guild_id, True)
            
            # ✅ 알림 채널 설정
            if 알림채널:
                await self.db.set_notification_channel(guild_id, str(알림채널.id))
            
            embed = discord.Embed(
                title="✅ 음성 레벨 시스템 활성화",
                description="음성 채널 활동 추적 및 알림이 시작되었습니다!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📊 활성화된 기능",
                value=(
                    "✅ 음성 채널 체류 시간 추적\n"
                    "✅ 유저 간 관계 시간 누적\n"
                    "✅ EXP 계산 및 레벨링\n"
                    "✅ 자동 알림 (마일스톤 & 레벨업)"  
                ),
                inline=False
            )
            
            if 알림채널:
                embed.add_field(
                    name="📢 알림 채널",
                    value=f"{알림채널.mention}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚠️ 알림 채널 미설정",
                    value="`/알림채널설정` 명령어로 알림 채널을 설정해주세요.",
                    inline=False
                )
            
            embed.add_field(
                name="🎯 마일스톤",
                value="1h, 5h, 10h, 20h, 50h, 100h, 200h, 500h",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"✅ Voice level system enabled for guild {interaction.guild.name}")
        
        except Exception as e:
            logger.error(f"Error enabling voice level: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="음성레벨_비활성화", description="음성 레벨 시스템을 비활성화합니다")
    async def disable_voice_level(self, interaction: discord.Interaction):
        """음성 레벨 시스템 비활성화"""
        try:
            # 권한 확인
            if not await self.is_admin(interaction):
                await interaction.response.send_message(
                    "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            guild_id = str(interaction.guild.id)
            
            # 비활성화
            await self.db.set_voice_level_enabled(guild_id, False)
            
            embed = discord.Embed(
                title="⏸️ 음성 레벨 시스템 비활성화",
                description="음성 채널 활동 추적이 중지되었습니다.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="ℹ️ 안내",
                value="기존에 누적된 데이터는 유지됩니다.\n언제든지 다시 활성화할 수 있습니다.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"⏸️ Voice level system disabled for guild {interaction.guild.name}")
        
        except Exception as e:
            logger.error(f"Error disabling voice level: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="알림채널설정", description="음성 레벨 알림을 받을 채널을 설정합니다")
    @app_commands.describe(채널="알림을 받을 텍스트 채널")
    async def set_notification_channel(
        self,
        interaction: discord.Interaction,
        채널: discord.TextChannel
    ):
        """알림 채널 설정"""
        try:
            # 권한 확인
            if not await self.is_admin(interaction):
                await interaction.response.send_message(
                    "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            guild_id = str(interaction.guild.id)
            
            # 봇이 해당 채널에 메시지를 보낼 수 있는지 확인
            permissions = 채널.permissions_for(interaction.guild.me)
            if not permissions.send_messages:
                await interaction.response.send_message(
                    f"❌ {채널.mention} 채널에 메시지를 보낼 권한이 없습니다.\n"
                    "봇에게 해당 채널의 '메시지 보내기' 권한을 부여해주세요.",
                    ephemeral=True
                )
                return
            
            # 알림 채널 설정
            await self.db.set_notification_channel(guild_id, str(채널.id))
            
            embed = discord.Embed(
                title="✅ 알림 채널 설정 완료",
                description=f"음성 레벨 알림이 {채널.mention}로 발송됩니다.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📢 알림 종류",
                value=(
                    "• 관계 마일스톤 (1h, 5h, 10h...)\n"
                    "• 레벨업 알림\n"
                    "• 그룹 플레이 알림"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🛡️ 스팸 방지",
                value="같은 페어는 하루 최대 3개까지만 알림이 발송됩니다.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            
            # 테스트 메시지 발송
            await 채널.send(
                "✅ 음성 레벨 시스템 알림 채널로 설정되었습니다!\n"
                "앞으로 이 채널에서 마일스톤 및 레벨업 알림을 받으실 수 있습니다."
            )
            
            logger.info(f"📢 Notification channel set to {채널.name} for guild {interaction.guild.name}")
        
        except Exception as e:
            logger.error(f"Error setting notification channel: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="알림채널해제", description="음성 레벨 알림 채널을 해제합니다")
    async def clear_notification_channel(self, interaction: discord.Interaction):
        """알림 채널 해제"""
        try:
            # 권한 확인
            if not await self.is_admin(interaction):
                await interaction.response.send_message(
                    "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            guild_id = str(interaction.guild.id)
            
            # 알림 채널 해제
            await self.db.clear_notification_channel(guild_id)
            
            embed = discord.Embed(
                title="⏸️ 알림 채널 해제",
                description="음성 레벨 알림이 더 이상 발송되지 않습니다.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="ℹ️ 안내",
                value=(
                    "• 데이터는 계속 수집됩니다\n"
                    "• `/알림채널설정` 명령어로 다시 설정할 수 있습니다\n"
                    "• 유저는 여전히 `/내레벨`, `/관계` 등의 커맨드로 통계를 확인할 수 있습니다"
                ),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"⏸️ Notification channel cleared for guild {interaction.guild.name}")
        
        except Exception as e:
            logger.error(f"Error clearing notification channel: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="음성레벨_상태", description="음성 레벨 시스템 현재 상태를 확인합니다")
    async def voice_level_status(self, interaction: discord.Interaction):
        """음성 레벨 시스템 상태 확인"""
        try:
            guild_id = str(interaction.guild.id)
            
            # 설정 조회
            settings = await self.db.get_voice_level_settings(guild_id)
            
            # 통계 조회
            async with self.db.get_connection() as db:
                # 활성 세션 수
                cursor = await db.execute('''
                    SELECT COUNT(*) FROM voice_sessions
                    WHERE guild_id = ? AND is_active = TRUE
                ''', (guild_id,))
                active_sessions = (await cursor.fetchone())[0]
                
                # 총 관계 수
                cursor = await db.execute('''
                    SELECT COUNT(*) FROM user_relationships
                    WHERE guild_id = ?
                ''', (guild_id,))
                total_relationships = (await cursor.fetchone())[0]
                
                # 총 유저 수
                cursor = await db.execute('''
                    SELECT COUNT(*) FROM user_levels
                    WHERE guild_id = ?
                ''', (guild_id,))
                total_users = (await cursor.fetchone())[0]
            
            # Embed 생성
            status_emoji = "✅" if settings['enabled'] else "⏸️"
            status_text = "활성화" if settings['enabled'] else "비활성화"
            color = discord.Color.green() if settings['enabled'] else discord.Color.orange()
            
            embed = discord.Embed(
                title=f"{status_emoji} 음성 레벨 시스템 상태",
                description=f"현재 상태: **{status_text}**",
                color=color
            )
            
            # 설정 정보
            embed.add_field(
                name="⚙️ 설정",
                value=(
                    f"• 최소 체류 시간: {settings['min_session_minutes']}분\n"
                    f"• 음소거 체크: {'활성화' if settings['check_mute_status'] else '비활성화'}\n"
                    f"• 기본 EXP/분: {settings['base_exp_per_minute']}\n"
                    f"• 일일 상한: {settings['daily_exp_limit']} exp"
                ),
                inline=False
            )
            
            # ✅ 알림 채널 정보 추가
            if settings['notification_channel_id']:
                channel = interaction.guild.get_channel(int(settings['notification_channel_id']))
                if channel:
                    embed.add_field(
                        name="📢 알림 채널",
                        value=f"{channel.mention} (알림 활성화 ✅)",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="⚠️ 알림 채널",
                        value="설정된 채널을 찾을 수 없습니다. 다시 설정해주세요.",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="📢 알림 채널",
                    value="❌ 미설정 - `/알림채널설정` 명령어로 설정하세요",
                    inline=False
                )
            
            # 통계
            embed.add_field(
                name="📊 통계",
                value=(
                    f"• 현재 활성 세션: {active_sessions}개\n"
                    f"• 등록된 유저: {total_users}명\n"
                    f"• 유저 간 관계: {total_relationships}쌍"
                ),
                inline=False
            )
            
            # Phase 정보
            embed.add_field(
                name="🚀 현재 Phase",
                value=(
                    "**Phase 3** - 알림 시스템 (완료) ✅\n"
                    "✅ 관계 마일스톤 알림\n"
                    "✅ 레벨업 알림\n"
                    "✅ 스팸 방지 시스템"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"서버 ID: {guild_id}")
            
            await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            logger.error(f"Error checking voice level status: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="관계확인", description="[테스트] 특정 유저와의 함께한 시간을 확인합니다")
    @app_commands.describe(유저="확인할 유저")
    async def check_relationship(
        self,
        interaction: discord.Interaction,
        유저: discord.Member
    ):
        """두 유저 간 관계 시간 확인 (Phase 1 테스트용)"""
        try:
            guild_id = str(interaction.guild.id)
            user_id = str(interaction.user.id)
            partner_id = str(유저.id)
            
            if user_id == partner_id:
                await interaction.response.send_message(
                    "❌ 자기 자신과의 관계는 확인할 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 관계 조회
            relationship = await self.db.get_relationship(guild_id, user_id, partner_id)
            
            if not relationship:
                await interaction.response.send_message(
                    f"❌ {유저.mention}님과 아직 함께 음성 채널에서 시간을 보낸 기록이 없습니다.",
                    ephemeral=True
                )
                return
            
            total_seconds = relationship['total_time_seconds']
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            embed = discord.Embed(
                title="🤝 관계 정보",
                description=f"{interaction.user.mention} ↔ {유저.mention}",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="⏱️ 함께한 시간",
                value=f"**{hours}시간 {minutes}분 {seconds}초**",
                inline=False
            )
            
            if relationship['last_played_together']:
                embed.add_field(
                    name="📅 마지막 플레이",
                    value=f"<t:{int(relationship['last_played_together'])}:R>",
                    inline=False
                )
            
            embed.set_footer(text="Phase 1: 데이터 추적 단계")
            
            await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            logger.error(f"Error checking relationship: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="음성세션검증", description="[관리자] 음성 세션 데이터 무결성 검사")
    async def verify_voice_sessions(self, interaction: discord.Interaction):
        """데이터 검증 및 자동 복구"""
        try:
            # 권한 확인
            if not await self.is_admin(interaction):
                await interaction.response.send_message(
                    "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            guild_id = str(interaction.guild.id)
            issues = []
            fixed = []
            
            # 1. 유령 세션 체크 (DB에는 있지만 실제로는 없음)
            async with self.db.get_connection() as db:
                cursor = await db.execute('''
                    SELECT session_uuid, user_id, channel_id
                    FROM voice_sessions
                    WHERE guild_id = ? AND is_active = TRUE
                ''', (guild_id,))
                active_sessions = await cursor.fetchall()
            
            for session_uuid, user_id, channel_id in active_sessions:
                member = interaction.guild.get_member(int(user_id))
                
                if not member or not member.voice:
                    issues.append(f"👻 유령 세션: <@{user_id}> (채널에 없음)")
                    
                    # 자동 종료
                    await self.db.end_voice_session_with_mute(session_uuid)
                    fixed.append(f"✅ 세션 종료: <@{user_id}>")
                
                elif str(member.voice.channel.id) != channel_id:
                    issues.append(f"🔄 채널 불일치: <@{user_id}>")
                    
                    # 세션 종료 후 새로 생성
                    await self.db.end_voice_session_with_mute(session_uuid)
                    
                    is_muted = member.voice.self_mute if member.voice else False
                    new_uuid = await self.db.create_voice_session(
                        guild_id, user_id, str(member.voice.channel.id), is_muted
                    )
                    
                    fixed.append(f"✅ 세션 재생성: <@{user_id}>")
            
            # 2. 누락된 세션 체크 (실제로는 있지만 DB에 없음)
            for voice_channel in interaction.guild.voice_channels:
                for member in voice_channel.members:
                    if member.bot:
                        continue
                    
                    user_id = str(member.id)
                    
                    session_data = await self.db.get_active_session(guild_id, user_id)
                    
                    if not session_data:
                        issues.append(f"❌ 세션 누락: {member.mention}")
                        
                        # 세션 생성
                        is_muted = member.voice.self_mute if member.voice else False
                        session_uuid = await self.db.create_voice_session(
                            guild_id, user_id, str(voice_channel.id), is_muted
                        )
                        
                        # 메모리 캐시에도 추가
                        if self.bot.voice_level_tracker:
                            session_key = (guild_id, user_id)
                            self.bot.voice_level_tracker.active_sessions[session_key] = session_uuid
                        
                        fixed.append(f"✅ 세션 생성: {member.mention}")
            
            # 3. 음수 시간 체크
            async with self.db.get_connection() as db:
                cursor = await db.execute('''
                    SELECT user1_id, user2_id, total_time_seconds
                    FROM user_relationships
                    WHERE guild_id = ? AND total_time_seconds < 0
                ''', (guild_id,))
                negative_rels = await cursor.fetchall()
            
            if negative_rels:
                for user1_id, user2_id, seconds in negative_rels:
                    issues.append(f"⚠️ 음수 시간: <@{user1_id}> ↔ <@{user2_id}> ({seconds}초)")
                    
                    # 0으로 리셋
                    async with self.db.get_connection() as db:
                        await db.execute('''
                            UPDATE user_relationships
                            SET total_time_seconds = 0
                            WHERE guild_id = ? AND user1_id = ? AND user2_id = ?
                        ''', (guild_id, user1_id, user2_id))
                        await db.commit()
                    
                    fixed.append(f"✅ 음수 시간 수정: <@{user1_id}> ↔ <@{user2_id}>")
            
            # 결과 출력
            embed = discord.Embed(
                title="🔍 음성 세션 검증 결과",
                color=discord.Color.blue() if not issues else discord.Color.orange()
            )
            
            if issues:
                embed.add_field(
                    name=f"⚠️ 발견된 문제 ({len(issues)}건)",
                    value="\n".join(issues[:10]) + (f"\n... 외 {len(issues)-10}건" if len(issues) > 10 else ""),
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ 검증 완료",
                    value="문제가 발견되지 않았습니다.",
                    inline=False
                )
            
            if fixed:
                embed.add_field(
                    name=f"🔧 자동 수정 ({len(fixed)}건)",
                    value="\n".join(fixed[:10]) + (f"\n... 외 {len(fixed)-10}건" if len(fixed) > 10 else ""),
                    inline=False
                )
            
            embed.set_footer(text=f"검사 완료 | 서버 ID: {guild_id}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            logger.info(f"🔍 Session verification: {len(issues)} issues, {len(fixed)} fixed")
        
        except Exception as e:
            logger.error(f"Error in verify_voice_sessions: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ 검증 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(VoiceLevelAdmin(bot))
    logger.info("✅ VoiceLevelAdmin cog loaded")