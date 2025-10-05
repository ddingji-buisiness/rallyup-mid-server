import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from datetime import datetime

class BattleTagLogAdmin(commands.Cog):
    """배틀태그 로그 관리 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="배틀태그로그설정", description="[관리자] 배틀태그 활동 로그 채널을 설정합니다")
    @app_commands.describe(채널="로그를 전송할 채널을 선택하세요")
    @app_commands.default_permissions(manage_guild=True)
    async def setup_battle_tag_log(
        self,
        interaction: discord.Interaction,
        채널: discord.TextChannel
    ):
        # 관리자 권한 확인
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            channel_id = str(채널.id)
            
            # 봇 권한 확인
            bot_member = interaction.guild.get_member(self.bot.user.id)
            channel_perms = 채널.permissions_for(bot_member)
            
            if not channel_perms.send_messages or not channel_perms.embed_links:
                await interaction.followup.send(
                    f"❌ {채널.mention} 채널에 메시지 전송 또는 임베드 권한이 없습니다.\n"
                    f"봇에게 다음 권한을 부여해주세요:\n"
                    f"• 메시지 보내기\n"
                    f"• 링크 임베드",
                    ephemeral=True
                )
                return
            
            # DB에 저장
            success = await self.bot.db_manager.set_battle_tag_log_channel(guild_id, channel_id)
            
            if not success:
                await interaction.followup.send(
                    "❌ 로그 채널 설정에 실패했습니다.",
                    ephemeral=True
                )
                return
            
            # 현재 설정 조회
            settings = await self.bot.db_manager.get_battle_tag_log_settings(guild_id)
            
            # 성공 메시지
            embed = discord.Embed(
                title="✅ 배틀태그 로그 설정 완료",
                description=f"로그 채널이 {채널.mention}로 설정되었습니다",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            # 현재 로그 항목 상태
            log_status = []
            if settings:
                log_status.append(f"{'✅' if settings['log_add'] else '⬜'} 배틀태그 추가")
                log_status.append(f"{'✅' if settings['log_delete'] else '⬜'} 배틀태그 삭제")
                log_status.append(f"{'✅' if settings['log_primary_change'] else '⬜'} 주계정 변경")
                log_status.append(f"{'✅' if settings['log_tier_change'] else '⬜'} 티어 변동")
            
            embed.add_field(
                name="📋 로그 항목",
                value="\n".join(log_status) if log_status else "기본 설정",
                inline=False
            )
            
            embed.add_field(
                name="⚙️ 로그 항목 조정",
                value="`/배틀태그로그토글` 명령어로 개별 항목을 켜고 끌 수 있습니다",
                inline=False
            )
            
            embed.set_footer(text="RallyUp Bot | 배틀태그 로그 시스템")
            
            # 설정 관리 View
            view = LogSettingsView(self.bot, guild_id)
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            # 로그 채널에 테스트 메시지
            await self.send_test_log(채널)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 로그 채널 설정 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    async def send_test_log(self, channel: discord.TextChannel):
        """로그 채널 설정 완료 테스트 메시지"""
        try:
            embed = discord.Embed(
                title="🎉 배틀태그 로그 시스템 활성화",
                description="이 채널에 배틀태그 관련 활동이 기록됩니다",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📝 로그 항목",
                value="• 배틀태그 추가\n"
                      "• 배틀태그 삭제\n"
                      "• 주계정 변경\n"
                      "• 티어 변동 (선택)",
                inline=False
            )
            
            embed.set_footer(text="RallyUp Bot | 로그 설정 완료")
            
            await channel.send(embed=embed)
        except Exception as e:
            print(f"❌ 테스트 로그 전송 실패: {e}")
    
    @app_commands.command(name="배틀태그로그토글", description="[관리자] 배틀태그 로그 항목을 켜고 끕니다")
    @app_commands.describe(
        항목="토글할 로그 항목을 선택하세요",
        켜기="켜기(True) 또는 끄기(False)"
    )
    @app_commands.choices(항목=[
        app_commands.Choice(name="배틀태그 추가", value="log_add"),
        app_commands.Choice(name="배틀태그 삭제", value="log_delete"),
        app_commands.Choice(name="주계정 변경", value="log_primary_change"),
        app_commands.Choice(name="티어 변동", value="log_tier_change")
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def toggle_battle_tag_log(
        self,
        interaction: discord.Interaction,
        항목: str,
        켜기: bool
    ):
        # 관리자 권한 확인
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            # 설정 확인
            settings = await self.bot.db_manager.get_battle_tag_log_settings(guild_id)
            if not settings or not settings['log_channel_id']:
                await interaction.followup.send(
                    "❌ 로그 채널이 설정되지 않았습니다.\n"
                    "`/배틀태그로그설정` 명령어로 먼저 채널을 설정해주세요.",
                    ephemeral=True
                )
                return
            
            # 토글 업데이트
            success = await self.bot.db_manager.update_battle_tag_log_toggle(
                guild_id, 항목, 켜기
            )
            
            if not success:
                await interaction.followup.send(
                    "❌ 로그 항목 토글에 실패했습니다.",
                    ephemeral=True
                )
                return
            
            # 항목 이름 매핑
            항목_이름 = {
                'log_add': '배틀태그 추가',
                'log_delete': '배틀태그 삭제',
                'log_primary_change': '주계정 변경',
                'log_tier_change': '티어 변동'
            }
            
            # 성공 메시지
            embed = discord.Embed(
                title=f"{'✅' if 켜기 else '⬜'} {항목_이름[항목]} 로그",
                description=f"{항목_이름[항목]} 로그가 **{'활성화' if 켜기 else '비활성화'}**되었습니다",
                color=0x00ff88 if 켜기 else 0x666666,
                timestamp=datetime.now()
            )
            
            # 업데이트된 설정 조회
            updated_settings = await self.bot.db_manager.get_battle_tag_log_settings(guild_id)
            
            if updated_settings:
                log_status = []
                log_status.append(f"{'✅' if updated_settings['log_add'] else '⬜'} 배틀태그 추가")
                log_status.append(f"{'✅' if updated_settings['log_delete'] else '⬜'} 배틀태그 삭제")
                log_status.append(f"{'✅' if updated_settings['log_primary_change'] else '⬜'} 주계정 변경")
                log_status.append(f"{'✅' if updated_settings['log_tier_change'] else '⬜'} 티어 변동")
                
                embed.add_field(
                    name="📋 현재 로그 항목",
                    value="\n".join(log_status),
                    inline=False
                )
            
            embed.set_footer(text="RallyUp Bot | 로그 설정")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 로그 토글 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        return await self.bot.db_manager.is_server_admin(guild_id, user_id)


class LogSettingsView(discord.ui.View):
    """로그 설정 관리 View"""
    
    def __init__(self, bot, guild_id: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
    
    @discord.ui.button(label="현재 설정 보기", style=discord.ButtonStyle.primary, emoji="⚙️")
    async def view_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """현재 로그 설정 확인"""
        await interaction.response.defer()
        
        settings = await self.bot.db_manager.get_battle_tag_log_settings(self.guild_id)
        
        if not settings:
            await interaction.followup.send(
                "❌ 로그 설정을 찾을 수 없습니다.", ephemeral=True
            )
            return
        
        # 채널 정보
        channel = None
        if settings['log_channel_id']:
            channel = self.bot.get_channel(int(settings['log_channel_id']))
        
        embed = discord.Embed(
            title="⚙️ 배틀태그 로그 설정",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📍 로그 채널",
            value=channel.mention if channel else "❌ 설정되지 않음",
            inline=False
        )
        
        log_status = []
        log_status.append(f"{'✅' if settings['log_add'] else '⬜'} 배틀태그 추가")
        log_status.append(f"{'✅' if settings['log_delete'] else '⬜'} 배틀태그 삭제")
        log_status.append(f"{'✅' if settings['log_primary_change'] else '⬜'} 주계정 변경")
        log_status.append(f"{'✅' if settings['log_tier_change'] else '⬜'} 티어 변동")
        
        embed.add_field(
            name="📋 로그 항목",
            value="\n".join(log_status),
            inline=False
        )
        
        embed.set_footer(text="RallyUp Bot | 로그 시스템")
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BattleTagLogAdmin(bot))