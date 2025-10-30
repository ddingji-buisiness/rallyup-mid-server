import discord
from discord.ext import commands
from discord import app_commands
from typing import List
from datetime import datetime

class AdminSystemCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인 (서버 소유자 또는 등록된 관리자)"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        # 서버 소유자는 항상 관리자
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        # 데이터베이스에서 관리자 확인
        return await self.bot.db_manager.is_server_admin(guild_id, user_id)

    @app_commands.command(name="관리자추가", description="[관리자] 새로운 관리자를 추가합니다")
    @app_commands.describe(유저="관리자로 추가할 유저")
    @app_commands.default_permissions(manage_guild=True)
    async def add_admin(self, interaction: discord.Interaction, 유저: discord.Member):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(유저.id)
            username = 유저.display_name
            added_by = str(interaction.user.id)
            
            # 서버 소유자를 추가하려는 경우
            if 유저.id == interaction.guild.owner_id:
                await interaction.followup.send(
                    "❌ 서버 소유자는 이미 최고 관리자입니다.", ephemeral=True
                )
                return
            
            # 봇을 추가하려는 경우
            if 유저.bot:
                await interaction.followup.send(
                    "❌ 봇은 관리자로 추가할 수 없습니다.", ephemeral=True
                )
                return
            
            # 자기 자신을 추가하려는 경우 (서버 소유자가 아닌데)
            if user_id == added_by and interaction.user.id != interaction.guild.owner_id:
                await interaction.followup.send(
                    "❌ 자기 자신을 관리자로 추가할 수 없습니다.", ephemeral=True
                )
                return
            
            success = await self.bot.db_manager.add_server_admin(
                guild_id, user_id, username, added_by
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 관리자 추가 완료",
                    description=f"**{유저.display_name}**님이 서버 관리자로 추가되었습니다!",
                    color=0x00ff88,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📋 추가 정보",
                    value=f"**추가된 관리자**: <@{user_id}>\n"
                          f"**추가한 관리자**: {interaction.user.display_name}\n"
                          f"**추가 시간**: <t:{int(datetime.now().timestamp())}:F>",
                    inline=False
                )
                
                embed.add_field(
                    name="🔧 관리자 권한",
                    value="• 유저 신청 승인/거절\n"
                          "• 신청 현황 확인\n"
                          "• 새로운 관리자 추가/제거\n"
                          "• 클랜전 관리 (해당되는 경우)",
                    inline=False
                )
                
                embed.set_footer(text="RallyUp Bot | 관리자 시스템")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # 추가된 관리자에게 DM 발송 시도
                try:
                    dm_embed = discord.Embed(
                        title="🎉 관리자 권한 부여",
                        description=f"**{interaction.guild.name}** 서버에서 관리자 권한을 받으셨습니다!",
                        color=0x00ff88
                    )
                    dm_embed.add_field(
                        name="부여자",
                        value=f"{interaction.user.display_name}님이 권한을 부여했습니다.",
                        inline=False
                    )
                    dm_embed.add_field(
                        name="사용 가능한 명령어",
                        value="이제 `/신청현황`, `/신청승인`, `/신청거절` 등의 관리자 명령어를 사용하실 수 있습니다.",
                        inline=False
                    )
                    await 유저.send(embed=dm_embed)
                except:
                    # DM 발송 실패해도 무시
                    pass
                    
            else:
                await interaction.followup.send(
                    f"❌ **{유저.display_name}**님은 이미 관리자입니다.", ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 관리자 추가 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="관리자제거", description="[관리자] 관리자 권한을 제거합니다")
    @app_commands.describe(유저="관리자 권한을 제거할 유저")
    @app_commands.default_permissions(manage_guild=True)
    async def remove_admin(self, interaction: discord.Interaction, 유저: discord.Member):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(유저.id)
            
            # 서버 소유자를 제거하려는 경우
            if 유저.id == interaction.guild.owner_id:
                await interaction.followup.send(
                    "❌ 서버 소유자의 관리자 권한은 제거할 수 없습니다.", ephemeral=True
                )
                return
            
            success = await self.bot.db_manager.remove_server_admin(guild_id, user_id)
            
            if success:
                embed = discord.Embed(
                    title="✅ 관리자 제거 완료",
                    description=f"**{유저.display_name}**님의 관리자 권한이 제거되었습니다.",
                    color=0xff6b6b,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📋 제거 정보",
                    value=f"**제거된 관리자**: <@{user_id}>\n"
                          f"**제거한 관리자**: {interaction.user.display_name}\n"
                          f"**제거 시간**: <t:{int(datetime.now().timestamp())}:F>",
                    inline=False
                )
                
                embed.set_footer(text="RallyUp Bot | 관리자 시스템")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # 제거된 관리자에게 DM 발송 시도
                try:
                    dm_embed = discord.Embed(
                        title="📢 관리자 권한 해제",
                        description=f"**{interaction.guild.name}** 서버에서 관리자 권한이 해제되었습니다.",
                        color=0xff6b6b
                    )
                    dm_embed.add_field(
                        name="해제자",
                        value=f"{interaction.user.display_name}님이 권한을 해제했습니다.",
                        inline=False
                    )
                    await 유저.send(embed=dm_embed)
                except:
                    # DM 발송 실패해도 무시
                    pass
                    
            else:
                await interaction.followup.send(
                    f"❌ **{유저.display_name}**님은 관리자가 아닙니다.", ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 관리자 제거 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="관리자목록", description="[관리자] 현재 서버의 관리자 목록을 확인합니다")
    async def list_admins(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            admins = await self.bot.db_manager.get_server_admins(guild_id)
            admin_count = await self.bot.db_manager.get_admin_count(guild_id)
            
            embed = discord.Embed(
                title="👥 서버 관리자 목록",
                description=f"현재 서버의 관리자 현황을 확인하세요",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            # 서버 소유자 정보
            owner = interaction.guild.owner
            if owner:
                embed.add_field(
                    name="👑 서버 소유자",
                    value=f"**{owner.display_name}** (<@{owner.id}>)\n└ 최고 관리자 (영구 권한)",
                    inline=False
                )
            else:
                # 서버 소유자 정보를 가져올 수 없는 경우
                try:
                    owner = await interaction.guild.fetch_owner()
                    embed.add_field(
                        name="👑 서버 소유자",
                        value=f"**{owner.display_name}** (<@{owner.id}>)\n└ 최고 관리자 (영구 권한)",
                        inline=False
                    )
                except:
                    embed.add_field(
                        name="👑 서버 소유자",
                        value=f"<@{interaction.guild.owner_id}>\n└ 최고 관리자 (영구 권한)",
                        inline=False
                    )
            
            # 추가 관리자들
            if admins:
                admin_list = []
                for i, admin in enumerate(admins[:15]):  # 최대 15명까지 표시
                    added_time = datetime.fromisoformat(admin['added_at'])
                    admin_list.append(
                        f"{i+1}. **{admin['username']}** (<@{admin['user_id']}>)\n"
                        f"└ 추가일: <t:{int(added_time.timestamp())}:R>"
                    )
                
                if len(admins) > 15:
                    admin_list.append(f"... 외 {len(admins) - 15}명")
                
                embed.add_field(
                    name=f"⚙️ 추가 관리자 ({admin_count}명)",
                    value="\n\n".join(admin_list),
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚙️ 추가 관리자",
                    value="추가된 관리자가 없습니다.",
                    inline=False
                )
            
            # 관리 명령어 안내
            embed.add_field(
                name="🔧 관리 명령어",
                value="• `/관리자추가 @유저` - 새 관리자 추가\n"
                      "• `/관리자제거 @유저` - 관리자 권한 제거\n"
                      "• `/관리자목록` - 관리자 목록 확인",
                inline=False
            )
            
            embed.add_field(
                name="📊 요약",
                value=f"**총 관리자**: {admin_count + 1}명 (소유자 1명 + 추가 {admin_count}명)",
                inline=False
            )
            
            embed.set_footer(text="RallyUp Bot | 관리자 시스템")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 관리자 목록 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="설정역할", description="[관리자] 신입/구성원 역할을 설정합니다")
    @app_commands.describe(
        신입역할="신입 유저에게 부여되는 역할",
        구성원역할="승인된 구성원에게 부여되는 역할",
        자동변경="승인 시 자동으로 역할을 변경할지 여부"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def setup_roles(
        self, 
        interaction: discord.Interaction,
        신입역할: discord.Role = None,
        구성원역할: discord.Role = None,
        자동변경: bool = True
    ):
        if not await self.is_admin(interaction):
            await interaction.response.send_message("❌ 관리자만 사용 가능합니다.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 역할 위치 검증 (봇 역할보다 아래에 있어야 함)
            bot_member = interaction.guild.get_member(self.bot.user.id)
            bot_top_role = bot_member.top_role
            
            role_errors = []
            
            if 신입역할 and 신입역할.position >= bot_top_role.position:
                role_errors.append(f"신입역할 '{신입역할.name}'이 봇 역할보다 높습니다")
            
            if 구성원역할 and 구성원역할.position >= bot_top_role.position:
                role_errors.append(f"구성원역할 '{구성원역할.name}'이 봇 역할보다 높습니다")
            
            if role_errors:
                await interaction.followup.send(
                    f"❌ 역할 설정 실패:\n• " + "\n• ".join(role_errors) + 
                    f"\n\n💡 해결방법: 서버 설정에서 봇 역할을 더 높은 위치로 이동해주세요.",
                    ephemeral=True
                )
                return
            
            # 데이터베이스에 설정 저장
            await self.bot.db_manager.update_server_settings(
                guild_id=str(interaction.guild_id),
                newbie_role_id=str(신입역할.id) if 신입역할 else None,
                member_role_id=str(구성원역할.id) if 구성원역할 else None,
                auto_role_change=자동변경
            )
            
            embed = discord.Embed(
                title="⚙️ 역할 설정 완료",
                description="서버 역할 설정이 업데이트되었습니다!",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="🆕 신입 역할",
                value=신입역할.mention if 신입역할 else "❌ 설정되지 않음",
                inline=True
            )
            
            embed.add_field(
                name="👥 구성원 역할", 
                value=구성원역할.mention if 구성원역할 else "❌ 설정되지 않음",
                inline=True
            )
            
            embed.add_field(
                name="🔄 자동 역할 변경",
                value="✅ 활성화" if 자동변경 else "❌ 비활성화",
                inline=False
            )
            
            if not 신입역할 or not 구성원역할:
                embed.add_field(
                    name="⚠️ 주의사항",
                    value="역할이 설정되지 않으면 승인 시 닉네임만 변경됩니다.",
                    inline=False
                )
            
            if 신입역할 and 구성원역할 and 자동변경:
                embed.add_field(
                    name="✨ 자동화 활성화",
                    value=f"이제 `/신청승인` 시 자동으로:\n"
                        f"• {신입역할.mention} → 제거\n"
                        f"• {구성원역할.mention} → 추가\n"
                        f"• 닉네임 → `배틀태그/포지션/티어` 형식으로 변경",
                    inline=False
                )
            
            embed.set_footer(text="RallyUp Bot | 서버 설정 시스템")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 설정 저장 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

    @app_commands.command(name="설정확인", description="[관리자] 현재 서버 설정을 확인합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def check_settings(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message("❌ 관리자만 사용 가능합니다.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            settings = await self.bot.db_manager.get_server_settings(str(interaction.guild_id))
            
            embed = discord.Embed(
                title="⚙️ 서버 설정 현황",
                description=f"**{interaction.guild.name}** 서버의 RallyUp 봇 설정",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            # 역할 정보 표시
            newbie_role = None
            member_role = None
            
            if settings.get('newbie_role_id'):
                newbie_role = interaction.guild.get_role(int(settings['newbie_role_id']))
            
            if settings.get('member_role_id'):
                member_role = interaction.guild.get_role(int(settings['member_role_id']))
            
            embed.add_field(
                name="🆕 신입 역할",
                value=newbie_role.mention if newbie_role else "❌ 설정되지 않음",
                inline=True
            )
            
            embed.add_field(
                name="👥 구성원 역할",
                value=member_role.mention if member_role else "❌ 설정되지 않음", 
                inline=True
            )
            
            auto_role_change = settings.get('auto_role_change', False)
            embed.add_field(
                name="🔄 자동 역할 변경",
                value="✅ 활성화" if auto_role_change else "❌ 비활성화",
                inline=False
            )
            
            # 현재 상태 분석
            status_messages = []
            
            if newbie_role and member_role and auto_role_change:
                status_messages.append("✅ 완전 자동화 활성화 - 승인 시 역할과 닉네임이 모두 자동 변경됩니다")
            elif auto_role_change and (not newbie_role or not member_role):
                status_messages.append("⚠️ 부분 설정 - 역할이 완전히 설정되지 않아 닉네임만 변경됩니다")
            elif not auto_role_change:
                status_messages.append("ℹ️ 수동 모드 - 승인 시 닉네임만 변경됩니다")
            
            if newbie_role and newbie_role.position >= interaction.guild.get_member(self.bot.user.id).top_role.position:
                status_messages.append("❌ 신입 역할이 봇 역할보다 높아 변경할 수 없습니다")
            
            if member_role and member_role.position >= interaction.guild.get_member(self.bot.user.id).top_role.position:
                status_messages.append("❌ 구성원 역할이 봇 역할보다 높아 변경할 수 없습니다")
            
            if status_messages:
                embed.add_field(
                    name="📊 현재 상태",
                    value="\n".join(status_messages),
                    inline=False
                )
            
            # 설정 방법 안내
            embed.add_field(
                name="🔧 설정 명령어",
                value="`/설정역할 @신입 @구성원 자동변경:True`\n"
                    "`/설정역할 자동변경:False` (비활성화)",
                inline=False
            )
            
            if settings.get('updated_at'):
                updated_time = datetime.fromisoformat(settings['updated_at'])
                embed.set_footer(text=f"마지막 업데이트: {updated_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 설정 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

    # @app_commands.command(name="역할테스트", description="[관리자] 역할 변경 기능을 테스트합니다")
    # @app_commands.describe(대상유저="테스트할 유저 (본인 권장)")
    # @app_commands.default_permissions(manage_guild=True)
    # async def test_role_change(self, interaction: discord.Interaction, 대상유저: discord.Member):
    #     if not await self.is_admin(interaction):
    #         await interaction.response.send_message("❌ 관리자만 사용 가능합니다.", ephemeral=True)
    #         return
        
    #     await interaction.response.defer(ephemeral=True)
        
    #     try:
    #         guild_id = str(interaction.guild_id)
    #         result = await self.bot.db_manager._update_user_roles_conditional(대상유저, guild_id)
            
    #         embed = discord.Embed(
    #             title="🧪 역할 변경 테스트 결과",
    #             description=f"**{대상유저.display_name}**님에 대한 테스트 결과",
    #             color=0xff9500,
    #             timestamp=datetime.now()
    #         )
            
    #         embed.add_field(
    #             name="📊 테스트 결과",
    #             value=result,
    #             inline=False
    #         )
            
    #         embed.add_field(
    #             name="ℹ️ 주의사항",
    #             value="이것은 테스트 기능이며, 실제 유저 승인과 동일한 로직을 사용합니다.\n"
    #                 "문제가 있다면 `/설정확인` 명령어로 설정을 점검해주세요.",
    #             inline=False
    #         )
            
    #         embed.set_footer(text="RallyUp Bot | 테스트 기능")
            
    #         await interaction.followup.send(embed=embed)
            
    #     except Exception as e:
    #         await interaction.followup.send(f"❌ 테스트 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

    @app_commands.command(name="신규역할설정", description="[관리자] 신규 입장자에게 자동으로 배정할 역할을 설정합니다")
    @app_commands.describe(
        역할="신규 입장자에게 자동 배정할 역할",
        활성화="자동 배정 기능을 활성화할지 선택 (기본값: True)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def set_new_member_role(
        self, 
        interaction: discord.Interaction, 
        역할: discord.Role,
        활성화: bool = True
    ):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            role_id = str(역할.id)
            
            # 봇의 역할보다 높은 역할인지 확인
            bot_member = interaction.guild.get_member(self.bot.user.id)
            if bot_member and 역할.position >= bot_member.top_role.position:
                await interaction.followup.send(
                    f"❌ **{역할.name}** 역할은 봇의 최고 역할보다 높거나 같습니다.\n"
                    f"봇이 이 역할을 배정할 수 없습니다. 서버 설정에서 봇의 역할을 더 높이거나, 더 낮은 역할을 선택해주세요.",
                    ephemeral=True
                )
                return
            
            # @everyone 역할은 배정할 수 없음
            if 역할.id == interaction.guild.id:
                await interaction.followup.send(
                    "❌ @everyone 역할은 신규 입장자 역할로 설정할 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 봇 역할인지 확인
            if 역할.managed:
                await interaction.followup.send(
                    f"❌ **{역할.name}**은 봇 전용 역할이므로 설정할 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 데이터베이스에 설정 저장
            success = await self.bot.db_manager.set_new_member_auto_role(
                guild_id, role_id, 활성화
            )
            
            if success:
                status = "✅ 활성화됨" if 활성화 else "⏸️ 비활성화됨"
                
                embed = discord.Embed(
                    title="🎯 신규 입장자 자동 역할 설정 완료",
                    description=f"새로운 멤버가 서버에 입장하면 자동으로 역할이 배정됩니다!",
                    color=0x00ff88 if 활성화 else 0xffa500,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="🎭 설정된 역할",
                    value=f"**{역할.name}** ({역할.mention})\n"
                        f"└ 색상: {str(역할.color)}\n"
                        f"└ 위치: {역할.position}번째",
                    inline=False
                )
                
                embed.add_field(
                    name="⚙️ 상태",
                    value=f"{status}\n"
                        f"└ 설정자: {interaction.user.display_name}",
                    inline=True
                )
                
                if 활성화:
                    embed.add_field(
                        name="📋 작동 방식",
                        value="• 새로운 멤버가 서버 입장\n"
                            "• 봇이 자동으로 역할 배정\n" 
                            "• 배정 실패시 로그 기록",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="⚠️ 알림",
                        value="현재 비활성화 상태입니다.\n"
                            "자동 배정이 작동하지 않습니다.",
                        inline=True
                    )
                
                embed.set_footer(
                    text=f"설정 변경: `/신규역할설정` | 현황 확인: `/신규역할현황`"
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            else:
                await interaction.followup.send(
                    "❌ 역할 설정 중 오류가 발생했습니다. 다시 시도해주세요.",
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 명령어 실행 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="신규역할현황", description="[관리자] 현재 신규 입장자 자동 역할 설정을 확인합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def check_new_member_role_status(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            settings = await self.bot.db_manager.get_new_member_auto_role_settings(guild_id)
            
            embed = discord.Embed(
                title="📊 신규 입장자 자동 역할 현황",
                description="현재 서버의 신규 멤버 자동 역할 배정 설정을 확인하세요",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            if settings['role_id'] and settings['enabled']:
                # 역할 정보 가져오기
                role = interaction.guild.get_role(int(settings['role_id']))
                
                if role:
                    embed.color = 0x00ff88
                    embed.add_field(
                        name="✅ 현재 상태",
                        value="**활성화됨** - 자동 배정 작동 중",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="🎭 설정된 역할",
                        value=f"**{role.name}** ({role.mention})\n"
                            f"└ 색상: {str(role.color)}\n"
                            f"└ 위치: {role.position}번째\n"
                            f"└ 멤버 수: {len(role.members)}명",
                        inline=False
                    )
                    
                    # 봇 권한 확인
                    bot_member = interaction.guild.get_member(self.bot.user.id)
                    if bot_member:
                        if role.position >= bot_member.top_role.position:
                            embed.add_field(
                                name="⚠️ 권한 문제",
                                value="봇의 역할이 설정된 역할보다 낮아서\n"
                                    "자동 배정이 실패할 수 있습니다.",
                                inline=True
                            )
                        else:
                            embed.add_field(
                                name="✅ 권한 상태",
                                value="봇이 해당 역할을 배정할 수 있습니다.",
                                inline=True
                            )
                    
                else:
                    embed.color = 0xff6b6b
                    embed.add_field(
                        name="❌ 오류 발생",
                        value="설정된 역할을 찾을 수 없습니다.\n"
                            "역할이 삭제되었을 가능성이 있습니다.",
                        inline=False
                    )
                    
            elif settings['role_id'] and not settings['enabled']:
                role = interaction.guild.get_role(int(settings['role_id']))
                role_name = role.name if role else "삭제된 역할"
                
                embed.color = 0xffa500
                embed.add_field(
                    name="⏸️ 현재 상태", 
                    value="**비활성화됨** - 자동 배정 중단됨",
                    inline=False
                )
                
                embed.add_field(
                    name="🎭 설정된 역할",
                    value=f"**{role_name}**\n"
                        f"└ 상태: 비활성화",
                    inline=False
                )
                
            else:
                embed.color = 0x888888
                embed.add_field(
                    name="❓ 현재 상태",
                    value="**미설정** - 자동 역할 배정이 설정되지 않음",
                    inline=False
                )
                
                embed.add_field(
                    name="🔧 설정 방법",
                    value="`/신규역할설정 [역할]` 명령어로\n"
                        "신규 입장자 자동 역할을 설정하세요.",
                    inline=False
                )
            
            embed.set_footer(text=f"조회자: {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 현황 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="신규역할해제", description="[관리자] 신규 입장자 자동 역할 배정을 비활성화합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def disable_new_member_role(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            # 현재 설정 확인
            settings = await self.bot.db_manager.get_new_member_auto_role_settings(guild_id)
            
            if not settings['enabled']:
                await interaction.followup.send(
                    "ℹ️ 신규 입장자 자동 역할 배정이 이미 비활성화되어 있습니다.",
                    ephemeral=True
                )
                return
            
            # 비활성화 실행
            success = await self.bot.db_manager.disable_new_member_auto_role(guild_id)
            
            if success:
                role_name = "알 수 없음"
                if settings['role_id']:
                    role = interaction.guild.get_role(int(settings['role_id']))
                    if role:
                        role_name = role.name
                
                embed = discord.Embed(
                    title="⏸️ 신규 입장자 자동 역할 배정 비활성화",
                    description="자동 역할 배정이 비활성화되었습니다.",
                    color=0xffa500,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📋 변경 사항",
                    value=f"• 이전 상태: **활성화됨**\n"
                        f"• 현재 상태: **비활성화됨**\n"
                        f"• 설정된 역할: **{role_name}** (유지됨)",
                    inline=False
                )
                
                embed.add_field(
                    name="ℹ️ 안내",
                    value="• 새로운 멤버에게 자동 역할 배정이 중단됩니다\n"
                        f"• 재활성화: `/신규역할설정 [@역할] True`",
                    inline=False
                )
                
                embed.set_footer(text=f"비활성화한 관리자: {interaction.user.display_name}")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            else:
                await interaction.followup.send(
                    "❌ 비활성화 중 오류가 발생했습니다. 다시 시도해주세요.",
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 명령어 실행 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AdminSystemCommands(bot))