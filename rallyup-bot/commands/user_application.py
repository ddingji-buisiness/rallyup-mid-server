import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Literal
from datetime import datetime

class UserApplicationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_position_short(self, position: str) -> str:
        """포지션 축약 (미리보기용)"""
        position_map = {
            "탱커": "탱",
            "딜러": "딜", 
            "힐러": "힐",
            "탱커 & 딜러": "탱딜",
            "탱커 & 힐러": "탱힐",
            "딜러 & 힐러": "딜힐",
            "탱커 & 딜러 & 힐러": "탱딜힐" 
        }
        return position_map.get(position, position)

    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인 (서버 소유자 또는 등록된 관리자)"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        # 서버 소유자는 항상 관리자
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        # 데이터베이스에서 관리자 확인
        return await self.bot.db_manager.is_server_admin(guild_id, user_id)

    @app_commands.command(name="유저신청", description="서버 가입을 신청합니다")
    @app_commands.describe(
        유입경로="어떻게 이 서버를 알게 되셨나요?",
        배틀태그="오버워치 배틀태그를 입력해주세요 (예: 닉네임#1234)",
        메인포지션="주로 플레이하는 포지션을 선택해주세요",
        전시즌티어="전시즌 최종 티어를 선택해주세요",
        현시즌티어="현시즌 현재 티어를 선택해주세요",
        최고티어="역대 최고 달성 티어를 선택해주세요"
    )
    async def apply_user(
        self,
        interaction: discord.Interaction,
        유입경로: str,
        배틀태그: str,
        메인포지션: Literal["탱커", "딜러", "힐러", "탱커 & 딜러", "탱커 & 힐러", "딜러 & 힐러", "탱커 & 딜러 & 힐러"],
        전시즌티어: Literal["언랭", "브론즈", "실버", "골드", "플래티넘", "다이아", "마스터", "그마", "챔피언"],
        현시즌티어: Literal["언랭", "브론즈", "실버", "골드", "플래티넘", "다이아", "마스터", "그마", "챔피언"],
        최고티어: Literal["언랭", "브론즈", "실버", "골드", "플래티넘", "다이아", "마스터", "그마", "챔피언"]
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            username = interaction.user.display_name
            
            # 이미 등록된 유저인지 확인
            if await self.bot.db_manager.is_user_registered(guild_id, user_id):
                await interaction.followup.send(
                    "✅ 이미 이 서버에 등록된 유저입니다!\n"
                    "추가적인 도움이 필요하시면 관리자에게 문의해주세요.",
                    ephemeral=True
                )
                return
            
            # 이미 신청한 유저인지 확인
            existing_app = await self.bot.db_manager.get_user_application(guild_id, user_id)
            if existing_app:
                status_msg = {
                    'pending': '⏳ 검토 대기 중',
                    'approved': '✅ 승인됨',
                    'rejected': '❌ 거절됨'
                }.get(existing_app['status'], '❓ 알 수 없음')
                
                embed = discord.Embed(
                    title="📋 기존 신청 정보",
                    description=f"이미 신청하신 내역이 있습니다.\n**상태**: {status_msg}",
                    color=0xff9500
                )
                
                embed.add_field(
                    name="신청 정보",
                    value=f"**유입경로**: {existing_app['entry_method']}\n"
                          f"**배틀태그**: {existing_app['battle_tag']}\n"
                          f"**메인 포지션**: {existing_app['main_position']}\n"
                          f"**전시즌 티어**: {existing_app['previous_season_tier']}\n"
                          f"**현시즌 티어**: {existing_app['current_season_tier']}\n"
                          f"**최고 티어**: {existing_app['highest_tier']}\n"
                          f"**신청일**: <t:{int(datetime.fromisoformat(existing_app['applied_at']).timestamp())}:F>",
                    inline=False
                )
                
                if existing_app['status'] == 'rejected':
                    embed.add_field(
                        name="재신청 안내",
                        value="거절된 신청입니다. 관리자에게 문의 후 재신청하시기 바랍니다.",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 입력값 검증
            if len(유입경로) > 200:
                await interaction.followup.send(
                    "❌ 유입경로는 200자 이하로 입력해주세요.", ephemeral=True
                )
                return
            
            # 배틀태그 형식 검증
            # if not self._validate_battle_tag(배틀태그):
            #     await interaction.followup.send(
            #         "❌ 배틀태그 형식이 올바르지 않습니다.\n\n"
            #         "**올바른 형식**: `닉네임#1234` (영문/한글/숫자 + # + 4자리 숫자)\n"
            #         "**예시**: `지켜줬잖아#3979`, `Tracer#1234`\n\n"
            #         "**규칙**:\n"
            #         "• 닉네임: 2-12자 (영문/한글/숫자)\n"
            #         "• # 기호 필수\n"
            #         "• 태그: 정확히 4자리 숫자", 
            #         ephemeral=True
            #     )
            #     return
            
            # 신청 생성
            success = await self.bot.db_manager.create_user_application(
                guild_id, user_id, username, 유입경로, 배틀태그, 메인포지션, 
                전시즌티어, 현시즌티어, 최고티어
            )
            
            if success:
                embed = discord.Embed(
                    title="📝 서버 가입 신청 완료!",
                    description="신청이 정상적으로 접수되었습니다. 관리자 검토 후 연락드리겠습니다.",
                    color=0x00ff88,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📋 신청 내용",
                    value=f"**유입경로**: {유입경로}\n"
                          f"**배틀태그**: {배틀태그}\n"
                          f"**메인 포지션**: {메인포지션}\n"
                          f"**전시즌 티어**: {전시즌티어}\n"
                          f"**현시즌 티어**: {현시즌티어}\n"
                          f"**최고 티어**: {최고티어}",
                    inline=False
                )
                
                embed.add_field(
                    name="⏳ 다음 단계",
                    value="• 관리자가 신청을 검토합니다\n"
                          "• 승인/거절 시 DM으로 알려드립니다\n"
                          "• 승인 시 서버 닉네임이 자동으로 설정됩니다\n"
                          "• 문의사항은 관리자에게 연락해주세요",
                    inline=False
                )
                
                embed.add_field(
                    name="🏷️ 닉네임 설정 안내",
                    value=f"승인 시 닉네임이 다음과 같이 설정됩니다:\n"
                        f"`{배틀태그} / {self._get_position_short(메인포지션)} / {현시즌티어}`",
                    inline=False
                )
                
                embed.set_footer(text="RallyUp Bot | 유저 신청 시스템")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ 신청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 신청 처리 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="신청현황", description="[관리자] 대기 중인 유저 신청을 확인합니다")
    async def check_applications(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            pending_apps = await self.bot.db_manager.get_pending_applications(guild_id)
            stats = await self.bot.db_manager.get_application_stats(guild_id)
            
            embed = discord.Embed(
                title="📊 유저 신청 현황",
                description=f"서버의 유저 신청 상황을 확인하세요",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            # 통계 정보
            status_counts = stats.get('status_counts', {})
            embed.add_field(
                name="📈 신청 통계",
                value=f"**대기 중**: {status_counts.get('pending', 0)}개\n"
                      f"**승인됨**: {status_counts.get('approved', 0)}개\n"
                      f"**거절됨**: {status_counts.get('rejected', 0)}개\n"
                      f"**등록된 유저**: {stats.get('total_registered', 0)}명",
                inline=True
            )
            
            # 대기 중인 신청들
            if pending_apps:
                app_list = []
                for app in pending_apps[:10]:  # 최대 10개까지만 표시
                    applied_time = datetime.fromisoformat(app['applied_at'])
                    app_list.append(
                        f"**{app['username']}** (<@{app['user_id']}>)\n"
                        f"├ 유입: {app['entry_method'][:25]}{'...' if len(app['entry_method']) > 25 else ''}\n"
                        f"├ 배틀태그: {app['battle_tag']}\n"
                        f"├ 포지션: {app['main_position']}\n"
                        f"├ 현재 티어: {app['current_season_tier']}\n"
                        f"└ 신청일: <t:{int(applied_time.timestamp())}:R>"
                    )
                
                if len(pending_apps) > 10:
                    app_list.append(f"... 외 {len(pending_apps) - 10}개")
                
                embed.add_field(
                    name=f"⏳ 대기 중인 신청 ({len(pending_apps)}개)",
                    value="\n\n".join(app_list) if app_list else "없음",
                    inline=False
                )
                
                embed.add_field(
                    name="🔧 관리 명령어",
                    value="• `/신청승인 @유저` - 신청 승인 (자동 닉네임 설정)\n"
                          "• `/신청거절 @유저 [사유]` - 신청 거절",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⏳ 대기 중인 신청",
                    value="현재 대기 중인 신청이 없습니다.",
                    inline=False
                )
            
            embed.set_footer(text="RallyUp Bot | 관리자 전용")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 신청 현황 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="신청승인", description="[관리자] 유저 신청을 승인하고 닉네임을 자동 설정합니다")
    @app_commands.describe(
        유저명="승인할 유저명 (자동완성)",
        메모="관리자 메모 (선택사항)"
    )
    async def approve_application(
        self,
        interaction: discord.Interaction,
        유저명: str,  # Member 대신 str 사용
        메모: str = None
    ):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            # 유저명으로 실제 멤버 찾기
            guild = interaction.guild
            user_member = None
            
            # 여러 방법으로 유저 찾기
            for member in guild.members:
                if (member.display_name == 유저명 or 
                    member.name == 유저명 or 
                    str(member.id) == 유저명):
                    user_member = member
                    break
            
            if not user_member:
                await interaction.followup.send(
                    f"❌ '{유저명}' 유저를 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            user_id = str(user_member.id)
            admin_id = str(interaction.user.id)
            
            # 닉네임 변경 기능이 포함된 승인 메서드 사용
            success, nickname_result = await self.bot.db_manager.approve_user_application_with_nickname(
                guild_id, user_id, admin_id, user_member, 메모
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 신청 승인 완료",
                    description=f"**{user_member.display_name}**님의 가입 신청이 승인되었습니다!",
                    color=0x00ff88,
                    timestamp=datetime.now()
                )
                
                if 메모:
                    embed.add_field(name="📝 관리자 메모", value=메모, inline=False)
                
                # 닉네임 변경 결과 표시
                embed.add_field(
                    name="🔄 자동 변경 내역",
                    value=nickname_result, 
                    inline=False
                )
                
                embed.set_footer(text=f"승인자: {interaction.user.display_name}")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # 유저에게 DM 발송 시도
                try:
                    dm_embed = discord.Embed(
                        title="🎉 가입 승인 안내",
                        description=f"**{interaction.guild.name}** 서버 가입이 승인되었습니다!",
                        color=0x00ff88
                    )
                    dm_embed.add_field(
                        name="환영합니다!",
                        value="이제 서버의 모든 기능을 이용하실 수 있습니다.\n"
                            "궁금한 점이 있으시면 언제든 문의해주세요!",
                        inline=False
                    )
                    dm_embed.add_field(
                        name="🔄 자동 설정 완료", 
                        value="서버 닉네임과 역할이 자동으로 설정되었습니다.\n"
                            "이제 서버의 모든 기능을 이용하실 수 있습니다!",
                        inline=False
                    )
                    await user_member.send(embed=dm_embed)
                except:
                    # DM 발송 실패해도 무시
                    pass
                    
            else:
                await interaction.followup.send(
                    f"❌ {user_member.display_name}님의 대기 중인 신청을 찾을 수 없습니다.",
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 신청 승인 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @approve_application.autocomplete('유저명')
    async def approve_user_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """신청한 유저들만 자동완성으로 표시 - 디버깅 버전"""
        try:
            guild_id = str(interaction.guild_id)
            
            # 로그 출력 (콘솔에서 확인용)
            print(f"[DEBUG] 자동완성 호출됨. Guild ID: {guild_id}, Current: '{current}'")
            
            # 대기 중인 신청 목록 가져오기
            pending_applications = await self.bot.db_manager.get_pending_applications(guild_id)
            print(f"[DEBUG] 대기 중인 신청 수: {len(pending_applications)}")
            
            if not pending_applications:
                print("[DEBUG] 대기 중인 신청이 없음")
                return []
            
            matching_users = []
            
            for app in pending_applications:
                try:
                    print(f"[DEBUG] 처리 중인 신청: {app}")
                    
                    username = app['username']
                    user_id = app['user_id']
                    
                    # 실제 길드 멤버인지 확인
                    member = interaction.guild.get_member(int(user_id))
                    if member:
                        print(f"[DEBUG] 멤버 찾음: {member.display_name}")
                        
                        # 현재 입력과 매칭되는지 확인
                        if (current.lower() in username.lower() or 
                            current.lower() in member.display_name.lower() or
                            current == ""):  # 빈 문자열이면 모든 유저 표시
                            
                            # 간단한 표시용 텍스트
                            try:
                                display_text = f"{member.display_name} ({app.get('main_position', '알수없음')})"
                            except:
                                display_text = f"{member.display_name}"
                            
                            matching_users.append(
                                app_commands.Choice(
                                    name=display_text[:100],  # Discord 제한
                                    value=member.display_name
                                )
                            )
                            print(f"[DEBUG] 매칭 유저 추가: {display_text}")
                    else:
                        print(f"[DEBUG] 멤버 찾지 못함: {user_id}")
                        
                except Exception as e:
                    print(f"[DEBUG] 신청 처리 중 오류: {e}")
                    continue
            
            print(f"[DEBUG] 최종 매칭 유저 수: {len(matching_users)}")
            return matching_users[:25]  # Discord 제한
            
        except Exception as e:
            print(f"[DEBUG] 자동완성 전체 오류: {e}")
            import traceback
            print(f"[DEBUG] 스택 트레이스: {traceback.format_exc()}")
            return []

    @app_commands.command(name="신청거절", description="[관리자] 유저 신청을 거절합니다")
    @app_commands.describe(
        유저명="거절할 유저명 (자동완성)",
        사유="거절 사유 (선택사항)"
    )
    async def reject_application(
        self,
        interaction: discord.Interaction,
        유저명: str,  # Member 대신 str 사용
        사유: str = None
    ):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            # 유저명으로 실제 멤버 찾기
            guild = interaction.guild
            user_member = None
            
            for member in guild.members:
                if (member.display_name == 유저명 or 
                    member.name == 유저명 or 
                    str(member.id) == 유저명):
                    user_member = member
                    break
            
            if not user_member:
                await interaction.followup.send(
                    f"❌ '{유저명}' 유저를 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            user_id = str(user_member.id)
            admin_id = str(interaction.user.id)
            
            success = await self.bot.db_manager.reject_user_application(
                guild_id, user_id, admin_id, 사유
            )
            
            if success:
                embed = discord.Embed(
                    title="❌ 신청 거절 완료",
                    description=f"**{user_member.display_name}**님의 가입 신청이 거절되었습니다.",
                    color=0xff4444,
                    timestamp=datetime.now()
                )
                
                if 사유:
                    embed.add_field(name="📝 거절 사유", value=사유, inline=False)
                
                embed.set_footer(text=f"처리자: {interaction.user.display_name}")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # 유저에게 DM 발송 시도
                try:
                    dm_embed = discord.Embed(
                        title="📋 가입 신청 결과",
                        description=f"**{interaction.guild.name}** 서버 가입 신청이 거절되었습니다.",
                        color=0xff4444
                    )
                    if 사유:
                        dm_embed.add_field(name="거절 사유", value=사유, inline=False)
                    dm_embed.add_field(
                        name="재신청 안내",
                        value="문제를 해결하신 후 다시 신청하실 수 있습니다.\n"
                            "궁금한 점이 있으시면 관리자에게 문의해주세요.",
                        inline=False
                    )
                    await user_member.send(embed=dm_embed)
                except:
                    pass
                    
            else:
                await interaction.followup.send(
                    f"❌ {user_member.display_name}님의 대기 중인 신청을 찾을 수 없습니다.",
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 신청 거절 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @reject_application.autocomplete('유저명')
    async def reject_user_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """신청한 유저들만 자동완성으로 표시 (거절용)"""
        # 승인용과 동일한 로직 사용
        return await self.approve_user_autocomplete(interaction, current)

    @app_commands.command(name="유저삭제", description="[관리자] 등록된 유저를 삭제합니다 (재신청 가능)")
    @app_commands.describe(
        유저명="삭제할 등록된 유저명 (자동완성)",
        사유="삭제 사유 (선택사항)"
    )
    async def delete_user(
        self,
        interaction: discord.Interaction,
        유저명: str,
        사유: str = None
    ):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            # 1. 먼저 데이터베이스에서 등록된 사용자 정보 찾기
            registered_users = await self.bot.db_manager.get_registered_users_list(guild_id, 1000)
            
            target_user_data = None
            for user_data in registered_users:
                if (user_data['username'].lower() == 유저명.lower() or 
                    user_data.get('battle_tag', '').lower() == 유저명.lower()):
                    target_user_data = user_data
                    break
            
            if not target_user_data:
                # 비슷한 이름의 사용자들 찾기
                similar_users = []
                for user_data in registered_users:
                    if (유저명.lower() in user_data['username'].lower() or 
                        유저명.lower() in user_data.get('battle_tag', '').lower()):
                        similar_users.append(user_data['username'])
                
                error_msg = f"❌ '{유저명}' 등록된 유저를 찾을 수 없습니다."
                if similar_users:
                    error_msg += f"\n\n**비슷한 유저들:**\n• " + "\n• ".join(similar_users[:5])
                
                await interaction.followup.send(error_msg, ephemeral=True)
                return
            
            user_id = target_user_data['user_id']
            username = target_user_data['username']
            
            # 2. Discord 멤버 객체 찾기 (User ID로 정확히 찾기)
            try:
                user_member = interaction.guild.get_member(int(user_id))
            except:
                user_member = None
            
            # 3. 데이터베이스에서 사용자 삭제
            admin_id = str(interaction.user.id)
            success = await self.bot.db_manager.delete_registered_user(
                guild_id, user_id, admin_id, 사유
            )
            
            if not success:
                await interaction.followup.send(
                    f"❌ **{username}**님의 삭제 처리 중 오류가 발생했습니다.", ephemeral=True
                )
                return
            
            # 4. 역할과 닉네임 복구 (Discord 멤버가 존재하는 경우)
            role_result = ""
            nickname_result = ""
            
            if user_member:
                # 4-1. 역할 복구 (구성원 → 신입)
                role_result = await self.bot.db_manager._reverse_user_roles_conditional(
                    user_member, guild_id
                )
                
                # 4-2. 닉네임 원상복구 (Discord 원래 닉네임으로)
                nickname_result = await self.bot.db_manager._restore_user_nickname(
                    user_member
                )
            else:
                role_result = "⚠️ 사용자가 서버에 없어 역할을 변경할 수 없음"
                nickname_result = "⚠️ 사용자가 서버에 없어 닉네임을 복구할 수 없음"
            
            # 5. 성공 메시지 전송
            embed = discord.Embed(
                title="✅ 유저 삭제 완료",
                description=f"**{username}**님이 등록된 유저 목록에서 삭제되었습니다.",
                color=0xff6b6b,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📋 삭제 정보",
                value=f"**삭제된 유저**: {username}\n"
                    f"**User ID**: `{user_id}`\n"
                    f"**삭제한 관리자**: {interaction.user.display_name}\n"
                    f"**삭제 시간**: <t:{int(datetime.now().timestamp())}:F>",
                inline=False
            )
            
            if 사유:
                embed.add_field(
                    name="📝 삭제 사유",
                    value=사유,
                    inline=False
                )
            
            # 6. 역할/닉네임 복구 결과 표시
            if user_member:
                embed.add_field(
                    name="🔄 자동 복구 결과",
                    value=f"**역할 변경**: {role_result}\n"
                        f"**닉네임 복구**: {nickname_result}",
                    inline=False
                )
            
            embed.add_field(
                name="ℹ️ 안내사항",
                value="• 해당 유저는 다시 `/유저신청`을 할 수 있습니다\n"
                    "• 기존 내전 기록은 유지됩니다\n"
                    "• 역할과 닉네임이 자동으로 복구되었습니다",
                inline=False
            )
            
            embed.set_footer(text="RallyUp Bot | 관리자 시스템")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 7. 삭제된 유저에게 DM 발송 (가능한 경우)
            if user_member:
                try:
                    dm_embed = discord.Embed(
                        title="📢 등록 해제 안내",
                        description=f"**{interaction.guild.name}** 서버에서 등록이 해제되었습니다.",
                        color=0xff6b6b
                    )
                    if 사유:
                        dm_embed.add_field(
                            name="📝 해제 사유",
                            value=사유,
                            inline=False
                        )
                    dm_embed.add_field(
                        name="🔄 자동 처리 내용",
                        value="• 역할이 원래대로 복구되었습니다\n"
                            "• 닉네임이 원래대로 복구되었습니다",
                        inline=False
                    )
                    dm_embed.add_field(
                        name="🔄 재신청 방법",
                        value="언제든지 `/유저신청` 명령어로 다시 신청하실 수 있습니다.",
                        inline=False
                    )
                    await user_member.send(embed=dm_embed)
                except:
                    pass
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 유저 삭제 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @delete_user.autocomplete('유저명')
    async def delete_user_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """등록된 유저들만 자동완성으로 표시"""
        try:
            guild_id = str(interaction.guild_id)
            
            # 등록된 유저 목록 가져오기
            registered_users = await self.bot.db_manager.get_registered_users_list(guild_id, 50)
            
            matching_users = []
            
            for user_data in registered_users:
                user_id = user_data['user_id']
                username = user_data['username']
                battle_tag = user_data.get('battle_tag', '')
                position = user_data.get('main_position', '')
                tier = user_data.get('current_season_tier', '')
                
                # 검색어와 매칭되는지 확인
                if (current.lower() in username.lower() or 
                    current.lower() in battle_tag.lower()):
                    
                    # Discord 멤버 객체 찾기 (추가 정보 표시용)
                    guild_member = interaction.guild.get_member(int(user_id))
                    if guild_member:
                        display_name = f"{username} ({battle_tag}/{position}/{tier})"
                        
                        matching_users.append(
                            app_commands.Choice(
                                name=display_name[:100],  # Discord 제한
                                value=username
                            )
                        )
            
            return matching_users[:25]  # Discord 제한
            
        except Exception as e:
            print(f"[DEBUG] 유저삭제 자동완성 오류: {e}")
            return []

    @app_commands.command(name="등록유저목록", description="[관리자] 등록된 유저 목록을 확인합니다")
    @app_commands.describe(검색어="유저명, 배틀태그, 또는 유입경로로 검색 (선택사항)")
    async def list_registered_users(self, interaction: discord.Interaction, 검색어: str = None):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            if 검색어:
                # 검색 모드
                users = await self.bot.db_manager.search_registered_user(guild_id, 검색어)
                title = f"🔍 등록 유저 검색: '{검색어}'"
            else:
                # 전체 목록 모드
                users = await self.bot.db_manager.get_registered_users_list(guild_id, 20)
                title = "👥 등록된 유저 목록"
            
            embed = discord.Embed(
                title=title,
                description=f"총 {len(users)}명의 유저가 {'검색되었습니다' if 검색어 else '등록되어 있습니다'}",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            if users:
                user_list = []
                for i, user in enumerate(users):
                    registered_time = datetime.fromisoformat(user['registered_at'])
                    
                    user_info = (
                        f"{i+1}. **{user['username']}** (<@{user['user_id']}>)\n"
                        f"   ├ 유입: {user.get('entry_method', '알수없음')}\n"
                        f"   ├ 배틀태그: {user.get('battle_tag', 'N/A')}\n"
                        f"   ├ 포지션: {user.get('main_position', 'N/A')}\n"
                        f"   ├ 현재 티어: {user.get('current_season_tier', 'N/A')}\n"
                        f"   └ 등록일: <t:{int(registered_time.timestamp())}:R>"
                    )
                    user_list.append(user_info)
                
                # 긴 목록을 여러 필드로 나누기 (Discord 2048자 제한 때문)
                chunk_size = 5  # 한 필드당 5명씩 표시
                for i in range(0, len(user_list), chunk_size):
                    chunk = user_list[i:i+chunk_size]
                    field_name = f"📋 등록 유저 ({i+1}-{min(i+chunk_size, len(user_list))})"
                    field_value = "\n\n".join(chunk)
                    
                    # Discord 필드 값 길이 제한 (1024자)
                    if len(field_value) > 1024:
                        # 너무 길면 간략하게 표시
                        simplified_chunk = []
                        for j, user in enumerate(users[i:i+chunk_size]):
                            simplified_chunk.append(
                                f"{i+j+1}. **{user['username']}** | "
                                f"{user.get('entry_method', '알수없음')} | "
                                f"{user.get('main_position', 'N/A')} | "
                                f"{user.get('current_season_tier', 'N/A')}"
                            )
                        field_value = "\n".join(simplified_chunk)
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=False
                    )
            else:
                embed.add_field(
                    name="📭 결과 없음",
                    value="조건에 맞는 등록된 유저가 없습니다.",
                    inline=False
                )
            
            # 통계 정보 추가
            if users:
                # 유입경로별 통계
                entry_stats = {}
                for user in users:
                    entry = user.get('entry_method', '알수없음')
                    entry_stats[entry] = entry_stats.get(entry, 0) + 1
                
                stats_text = []
                for entry, count in sorted(entry_stats.items(), key=lambda x: x[1], reverse=True):
                    stats_text.append(f"• {entry}: {count}명")
                
                embed.add_field(
                    name="📊 유입경로별 통계",
                    value="\n".join(stats_text[:10]) if stats_text else "데이터 없음",  # 상위 10개만
                    inline=True
                )
            
            # 관리 명령어 안내
            embed.add_field(
                name="🔧 관리 명령어",
                value="• `/유저삭제 @유저` - 등록 해제\n• `/등록유저목록 검색어` - 특정 조건으로 검색",
                inline=True
            )
            
            embed.set_footer(text="RallyUp Bot | 관리자 전용")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 등록 유저 목록 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(UserApplicationCommands(bot))