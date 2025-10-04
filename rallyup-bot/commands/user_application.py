import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Literal
from datetime import datetime

class OnePageApplicationView(discord.ui.View):
    """모든 입력을 한 페이지에서 처리"""
    
    def __init__(self, bot):
        super().__init__(timeout=600)
        self.bot = bot
        
        # 입력 데이터
        self.entry_method = None
        self.battle_tag = None
        self.main_position = None
        self.birth_year = None
        self.previous_tier = None
        self.current_tier = None
        self.highest_tier = None
        
        self.add_ui_components()
    
    def add_ui_components(self):
        """모든 UI 컴포넌트 추가"""
        
        # 텍스트 입력 버튼 (유입경로, 배틀태그)
        text_input_btn = discord.ui.Button(
            label="📝 기본정보 입력 (유입경로/배틀태그/생년)",
            style=discord.ButtonStyle.primary,
            row=0
        )
        text_input_btn.callback = self.open_text_modal
        self.add_item(text_input_btn)
        
        # 메인 포지션 선택
        position_select = discord.ui.Select(
            placeholder="🎯 메인 포지션 선택",
            options=[
                discord.SelectOption(label="탱커", value="탱커", emoji="🛡️"),
                discord.SelectOption(label="딜러", value="딜러", emoji="⚔️"),
                discord.SelectOption(label="힐러", value="힐러", emoji="💚"),
                discord.SelectOption(label="탱커 & 딜러", value="탱커 & 딜러"),
                discord.SelectOption(label="탱커 & 힐러", value="탱커 & 힐러"),
                discord.SelectOption(label="딜러 & 힐러", value="딜러 & 힐러"),
                discord.SelectOption(label="탱커 & 딜러 & 힐러", value="탱커 & 딜러 & 힐러"),
            ],
            row=1
        )
        position_select.callback = self.position_selected
        self.add_item(position_select)
        
        # 전시즌 티어
        prev_tier = discord.ui.Select(
            placeholder="📊 전시즌 티어",
            options=self._tier_options(),
            row=2
        )
        prev_tier.callback = self.prev_tier_selected
        self.add_item(prev_tier)
        
        # 현시즌 티어
        curr_tier = discord.ui.Select(
            placeholder="📈 현시즌 티어",
            options=self._tier_options(),
            row=3
        )
        curr_tier.callback = self.curr_tier_selected
        self.add_item(curr_tier)
        
        # 최고 티어
        high_tier = discord.ui.Select(
            placeholder="🏆 최고 티어",
            options=self._tier_options(),
            row=4
        )
        high_tier.callback = self.high_tier_selected
        self.add_item(high_tier)
    
    def _tier_options(self):
        return [
            discord.SelectOption(label="언랭", value="언랭", emoji="⬛"),
            discord.SelectOption(label="브론즈", value="브론즈", emoji="🟫"),
            discord.SelectOption(label="실버", value="실버", emoji="⬜"),
            discord.SelectOption(label="골드", value="골드", emoji="🟨"),
            discord.SelectOption(label="플래티넘", value="플래티넘", emoji="🟦"),
            discord.SelectOption(label="다이아", value="다이아", emoji="💎"),
            discord.SelectOption(label="마스터", value="마스터", emoji="🟪"),
            discord.SelectOption(label="그마", value="그마", emoji="🔴"),
            discord.SelectOption(label="챔피언", value="챔피언", emoji="👑"),
        ]
    
    async def open_text_modal(self, interaction: discord.Interaction):
        """텍스트 입력 Modal 열기"""
        modal = QuickTextModal(self)
        await interaction.response.send_modal(modal)
    
    async def position_selected(self, interaction: discord.Interaction):
        self.main_position = interaction.data['values'][0]
        await self.update_view(interaction)
    
    async def prev_tier_selected(self, interaction: discord.Interaction):
        self.previous_tier = interaction.data['values'][0]
        await self.update_view(interaction)
    
    async def curr_tier_selected(self, interaction: discord.Interaction):
        self.current_tier = interaction.data['values'][0]
        await self.update_view(interaction)
    
    async def high_tier_selected(self, interaction: discord.Interaction):
        self.highest_tier = interaction.data['values'][0]
        await self.update_view(interaction)
    
    async def update_view(self, interaction: discord.Interaction):
        """View 업데이트 및 제출 버튼 관리"""
        
        # 모든 항목 완료 체크
        all_complete = all([
            self.entry_method, self.battle_tag, self.main_position,
            self.previous_tier, self.current_tier, self.highest_tier
        ])
        
        # 제출 버튼 추가/업데이트
        if all_complete and not any(isinstance(item, discord.ui.Button) and item.label == "✅ 신청 제출" for item in self.children):
            submit_btn = discord.ui.Button(
                label="✅ 신청 제출",
                style=discord.ButtonStyle.success,
                row=0
            )
            submit_btn.callback = self.submit_application
            self.add_item(submit_btn)
        
        await interaction.response.edit_message(
            embed=self._create_status_embed(),
            view=self
        )
    
    def _create_status_embed(self):
        """현재 상태 표시 임베드"""
        embed = discord.Embed(
            title="📝 서버 가입 신청",
            description="아래 항목들을 모두 입력/선택해주세요",
            color=0x0099ff
        )
        
        status = [
            f"{'✅' if self.entry_method else '⬜'} 유입경로: {self.entry_method or '미입력'}",
            f"{'✅' if self.battle_tag else '⬜'} 배틀태그: {self.battle_tag or '미입력'}",
            f"{'✅' if self.birth_year else '⬜'} 생년(뒤2자리): {self.birth_year or '미입력'}",
            f"{'✅' if self.main_position else '⬜'} 메인 포지션: {self.main_position or '미선택'}",
            f"{'✅' if self.previous_tier else '⬜'} 전시즌 티어: {self.previous_tier or '미선택'}",
            f"{'✅' if self.current_tier else '⬜'} 현시즌 티어: {self.current_tier or '미선택'}",
            f"{'✅' if self.highest_tier else '⬜'} 최고 티어: {self.highest_tier or '미선택'}",
        ]
        
        embed.add_field(
            name="📋 입력 현황",
            value="\n".join(status),
            inline=False
        )
        
        if all([self.entry_method, self.battle_tag, self.main_position, 
                self.previous_tier, self.current_tier, self.highest_tier]):
            embed.add_field(
                name="🎉 준비 완료!",
                value="**'신청 제출'** 버튼을 눌러주세요",
                inline=False
            )
        
        return embed
    
    async def submit_application(self, interaction: discord.Interaction):
        """최종 제출"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            username = interaction.user.display_name
            
            # 이미 등록된 유저 체크
            if await self.bot.db_manager.is_user_registered(guild_id, user_id):
                await interaction.followup.send(
                    "✅ 이미 이 서버에 등록된 유저입니다!",
                    ephemeral=True
                )
                return
            
            success = await self.bot.db_manager.create_user_application(
                guild_id, user_id, username,
                self.entry_method, self.battle_tag, self.birth_year, self.main_position,
                self.previous_tier, self.current_tier, self.highest_tier
            )
            
            if success:
                # 성공 임베드
                embed = discord.Embed(
                    title="✅ 신청 완료!",
                    description="관리자 검토 후 연락드리겠습니다",
                    color=0x00ff88,
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="📋 신청 내용",
                    value=f"**유입경로**: {self.entry_method}\n"
                          f"**배틀태그**: {self.battle_tag}\n"
                          f"**생년(뒤2자리)**: {self.birth_year}\n"
                          f"**포지션**: {self.main_position}\n"
                          f"**전시즌**: {self.previous_tier}\n"
                          f"**현시즌**: {self.current_tier}\n"
                          f"**최고**: {self.highest_tier}",
                    inline=False
                )
                embed.add_field(
                    name="⏳ 다음 단계",
                    value="• 관리자가 신청을 검토합니다\n"
                          "• 승인/거절 시 DM으로 알려드립니다\n"
                          "• 승인 시 서버 닉네임이 자동으로 설정됩니다",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # 관리자 DM 알림 발송
                try:
                    application_data = {
                        'entry_method': self.entry_method,
                        'battle_tag': self.battle_tag,
                        'birth_year': self.birth_year,
                        'main_position': self.main_position,
                        'previous_season_tier': self.previous_tier,
                        'current_season_tier': self.current_tier,
                        'highest_tier': self.highest_tier
                    }
                    
                    success_count, fail_count = await self._send_admin_notification(
                        interaction.guild,
                        interaction.user,
                        application_data
                    )
                    
                    if success_count > 0:
                        print(f"✅ {success_count}명의 관리자에게 신청 알림 전송")
                    if fail_count > 0:
                        print(f"⚠️ {fail_count}명의 관리자에게 DM 전송 실패")
                        
                except Exception as dm_error:
                    print(f"❌ 관리자 DM 알림 실패: {dm_error}")
                    
            else:
                await interaction.followup.send("❌ 신청 처리 실패", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ 오류: {str(e)}", ephemeral=True)
    
    async def _send_admin_notification(self, guild: discord.Guild, 
                                       applicant: discord.Member, 
                                       application_data: dict):
        """모든 관리자에게 신규 신청 알림 DM 발송"""
        try:
            guild_id = str(guild.id)
            guild_owner_id = str(guild.owner_id)
            
            # 모든 관리자 ID 조회
            admin_ids = await self.bot.db_manager.get_all_server_admins_for_notification(
                guild_id, guild_owner_id
            )
            
            # DM 임베드 생성
            embed = discord.Embed(
                title="🔔 새로운 유저 신청 알림",
                description=f"**{guild.name}** 서버에 새로운 가입 신청이 접수되었습니다!",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="👤 신청자 정보",
                value=f"**이름**: {applicant.display_name} ({applicant.name})\n"
                      f"**ID**: <@{applicant.id}>\n"
                      f"**가입일**: <t:{int(applicant.joined_at.timestamp())}:R>",
                inline=False
            )
            
            embed.add_field(
                name="📋 신청 내용",
                value=f"**유입경로**: {application_data['entry_method']}\n"
                      f"**배틀태그**: {application_data['battle_tag']}\n"
                      f"**메인 포지션**: {application_data['main_position']}\n"
                      f"**전시즌 티어**: {application_data['previous_season_tier']}\n"
                      f"**현시즌 티어**: {application_data['current_season_tier']}\n"
                      f"**최고 티어**: {application_data['highest_tier']}",
                inline=False
            )
            
            embed.add_field(
                name="⚡ 빠른 액션",
                value=f"**승인**: `/신청승인 {applicant.display_name}`\n"
                      f"**거절**: `/신청거절 {applicant.display_name} [사유]`\n"
                      f"**목록 확인**: `/신청현황`",
                inline=False
            )
            
            embed.set_thumbnail(url=applicant.display_avatar.url)
            embed.set_footer(
                text=f"서버: {guild.name} | RallyUp 관리자 알림",
                icon_url=guild.icon.url if guild.icon else None
            )
            
            # 각 관리자에게 DM 발송
            success_count = 0
            fail_count = 0
            
            for admin_id in admin_ids:
                try:
                    admin_user = self.bot.get_user(int(admin_id))
                    if not admin_user:
                        admin_user = await self.bot.fetch_user(int(admin_id))
                    
                    if admin_user:
                        await admin_user.send(embed=embed)
                        success_count += 1
                    
                except discord.Forbidden:
                    fail_count += 1
                except discord.NotFound:
                    fail_count += 1
                except Exception:
                    fail_count += 1
            
            return success_count, fail_count
            
        except Exception as e:
            print(f"❌ 관리자 DM 알림 전체 실패: {e}")
            return 0, len(admin_ids) if 'admin_ids' in locals() else 1

class QuickTextModal(discord.ui.Modal, title="텍스트 정보 입력"):
    """간단한 텍스트 입력 Modal"""
    
    entry_method = discord.ui.TextInput(
        label="유입경로",
        placeholder="예: 친구 추천, 유튜브 등",
        style=discord.TextStyle.short,
        max_length=200
    )
    
    battle_tag = discord.ui.TextInput(
        label="배틀태그",
        placeholder="닉네임#1234",
        style=discord.TextStyle.short,
        max_length=50
    )

    birth_year = discord.ui.TextInput(
        label="출생년도 뒤 2자리",
        placeholder="예: 00 (2000년생), 95 (1995년생)",
        style=discord.TextStyle.short,
        min_length=2,
        max_length=2,
        required=True
    )
    
    def __init__(self, parent_view: OnePageApplicationView):
        super().__init__()
        self.parent_view = parent_view
    
    async def on_submit(self, interaction: discord.Interaction):
        if not self.birth_year.value.isdigit():
            await interaction.response.send_message(
                "❌ 출생년도는 숫자 2자리만 입력해주세요 (예: 00, 95)",
                ephemeral=True
            )
            return
        
        self.parent_view.entry_method = self.entry_method.value
        self.parent_view.battle_tag = self.battle_tag.value
        self.parent_view.birth_year = self.birth_year.value

        await interaction.response.edit_message(
            embed=self.parent_view._create_status_embed(),
            view=self.parent_view
        )

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
    
    @app_commands.command(name="유저신청", description="서버 가입 신청 (한 페이지 완성)")
    async def apply_user(self, interaction: discord.Interaction):
        # 1단계: 즉시 등록 여부 체크
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        # 이미 등록된 유저 체크
        if await self.bot.db_manager.is_user_registered(guild_id, user_id):
            embed = discord.Embed(
                title="✅ 이미 등록된 유저입니다",
                description=f"**{interaction.user.display_name}**님은 이미 이 서버에 등록되어 있습니다!",
                color=0x00ff88
            )
            embed.add_field(
                name="💡 안내",
                value="• 추가 정보 수정이 필요하시면 `/정보수정` 명령어를 사용하세요\n"
                      "• 내 정보 확인은 `/내정보` 명령어를 사용하세요\n"
                      "• 기타 문의사항은 관리자에게 연락해주세요",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 기존 신청 상태 확인 (pending/rejected)
        existing_app = await self.bot.db_manager.get_user_application(guild_id, user_id)
        
        if existing_app and existing_app['status'] == 'pending':
            applied_at = datetime.fromisoformat(existing_app['applied_at'])
            embed = discord.Embed(
                title="⏳ 이미 신청 대기 중입니다",
                description="신청이 이미 접수되어 관리자 검토를 기다리고 있습니다.",
                color=0xffaa00
            )
            embed.add_field(
                name="📋 신청 정보",
                value=f"**신청일**: <t:{int(applied_at.timestamp())}:F>\n"
                      f"**상태**: 대기 중\n"
                      f"**배틀태그**: {existing_app.get('battle_tag', 'N/A')}\n"
                      f"**포지션**: {existing_app.get('main_position', 'N/A')}",
                inline=False
            )
            embed.add_field(
                name="💡 안내",
                value="관리자가 검토 후 승인/거절 시 DM으로 연락드립니다.\n"
                      "급한 문의사항은 관리자에게 직접 연락해주세요.",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 재신청 안내 (거절된 경우)
        reapplication_note = ""
        if existing_app and existing_app['status'] == 'rejected':
            reviewed_at = datetime.fromisoformat(existing_app['reviewed_at']) if existing_app.get('reviewed_at') else None
            reapplication_note = (
                f"**🔄 재신청 감지**\n"
                f"• 이전 거절일: <t:{int(reviewed_at.timestamp())}:R>\n"
                f"• 거절 사유: {existing_app.get('admin_note', '사유 없음')}\n"
                f"• 개선 사항을 반영하여 신중하게 작성해주세요\n\n"
            )

        view = OnePageApplicationView(self.bot)
        embed = view._create_status_embed()

        if reapplication_note:
            embed.description = reapplication_note + (embed.description or "")

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="신청현황", description="[관리자] 대기 중인 유저 신청을 확인합니다")
    @app_commands.default_permissions(manage_guild=True)
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
    @app_commands.default_permissions(manage_guild=True)
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
    @app_commands.default_permissions(manage_guild=True)
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
                
                try:
                    dm_embed = discord.Embed(
                        title="📋 가입 신청 결과",
                        description=f"**{interaction.guild.name}** 서버 가입 신청이 거절되었습니다.",
                        color=0xff4444
                    )
                    if 사유:
                        dm_embed.add_field(name="거절 사유", value=사유, inline=False)
                    
                    dm_embed.add_field(
                        name="🔄 재신청 안내",
                        value="문제를 해결하신 후 **언제든지 다시 신청**하실 수 있습니다.\n"
                            "위의 거절 사유를 참고하여 개선해주세요.\n\n"
                            "**재신청 방법**: `/유저신청` 명령어 사용\n"
                            "**개선 팁**: 정확한 정보 입력, 거절 사유 반영",
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
    @app_commands.default_permissions(manage_guild=True)
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
        """등록된 유저들만 자동완성으로 표시 (서버 존재 여부 무관)"""
        try:
            guild_id = str(interaction.guild_id)
            
            # 등록된 유저 목록 가져오기
            registered_users = await self.bot.db_manager.get_registered_users_list(guild_id, 100)
            
            matching_users = []
            
            for user_data in registered_users:
                user_id = user_data['user_id']
                username = user_data['username']
                battle_tag = user_data.get('battle_tag', '')
                position = user_data.get('main_position', '')
                tier = user_data.get('current_season_tier', '')
                
                # 검색어 매칭 확인
                if (current.lower() in username.lower() or 
                    current.lower() in battle_tag.lower()):
                    
                    # Discord 멤버 객체 찾기 (상태 표시용)
                    guild_member = interaction.guild.get_member(int(user_id))
                    
                    # 🔧 수정: 서버 존재 여부와 관계없이 모든 등록된 유저 표시
                    if guild_member:
                        # 서버에 있는 멤버
                        display_name = f"✅ {username} ({battle_tag}/{position}/{tier})"
                    else:
                        # 서버를 떠났지만 DB에는 등록되어 있는 멤버
                        display_name = f"👻 {username} ({battle_tag}/{position}/{tier}) - 서버 없음"
                    
                    matching_users.append(
                        app_commands.Choice(
                            name=display_name[:100],  # Discord 제한
                            value=username
                        )
                    )
            
            # Discord 자동완성 한도는 25개
            return matching_users[:25]
            
        except Exception as e:
            print(f"[DEBUG] 유저삭제 자동완성 오류: {e}")
            import traceback
            print(f"[DEBUG] 스택트레이스: {traceback.format_exc()}")
            return []

    @app_commands.command(name="등록유저목록", description="[관리자] 등록된 유저 목록을 확인합니다")
    @app_commands.describe(검색어="유저명, 배틀태그, 또는 유입경로로 검색 (선택사항)")
    @app_commands.default_permissions(manage_guild=True)
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

    async def send_admin_notification_dm(self, guild: discord.Guild, applicant: discord.Member, application_data: dict):
        """모든 관리자에게 신규 신청 알림 DM 발송"""
        try:
            guild_id = str(guild.id)
            guild_owner_id = str(guild.owner_id)
            
            # 모든 관리자 ID 조회
            admin_ids = await self.bot.db_manager.get_all_server_admins_for_notification(
                guild_id, guild_owner_id
            )
            
            # DM 임베드 생성
            embed = discord.Embed(
                title="🔔 새로운 유저 신청 알림",
                description=f"**{guild.name}** 서버에 새로운 가입 신청이 접수되었습니다!",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="👤 신청자 정보",
                value=f"**이름**: {applicant.display_name} ({applicant.name})\n"
                    f"**ID**: <@{applicant.id}>\n"
                    f"**가입일**: <t:{int(applicant.joined_at.timestamp())}:R>",
                inline=False
            )
            
            embed.add_field(
                name="📋 신청 내용",
                value=f"**유입경로**: {application_data['entry_method']}\n"
                    f"**배틀태그**: {application_data['battle_tag']}\n"
                    f"**메인 포지션**: {application_data['main_position']}\n"
                    f"**전시즌 티어**: {application_data['previous_season_tier']}\n"
                    f"**현시즌 티어**: {application_data['current_season_tier']}\n"
                    f"**최고 티어**: {application_data['highest_tier']}",
                inline=False
            )
            
            embed.add_field(
                name="⚡ 빠른 액션",
                value=f"**승인**: `/신청승인 {applicant.display_name}`\n"
                    f"**거절**: `/신청거절 {applicant.display_name} [사유]`\n"
                    f"**목록 확인**: `/신청현황`",
                inline=False
            )
            
            embed.set_thumbnail(url=applicant.display_avatar.url)
            embed.set_footer(
                text=f"서버: {guild.name} | RallyUp 관리자 알림",
                icon_url=guild.icon.url if guild.icon else None
            )
            
            # 각 관리자에게 DM 발송
            success_count = 0
            fail_count = 0
            
            for admin_id in admin_ids:
                try:
                    admin_user = self.bot.get_user(int(admin_id))
                    if not admin_user:
                        # 캐시에 없으면 API로 가져오기
                        admin_user = await self.bot.fetch_user(int(admin_id))
                    
                    if admin_user:
                        await admin_user.send(embed=embed)
                        success_count += 1
                        print(f"✅ 관리자 DM 전송 성공: {admin_user.name} (ID: {admin_id})")
                    
                except discord.Forbidden:
                    # DM 차단된 경우
                    fail_count += 1
                    print(f"❌ DM 차단됨: 관리자 ID {admin_id}")
                except discord.NotFound:
                    # 사용자를 찾을 수 없는 경우
                    fail_count += 1
                    print(f"❌ 사용자 없음: 관리자 ID {admin_id}")
                except Exception as e:
                    # 기타 오류
                    fail_count += 1
                    print(f"❌ DM 전송 실패: 관리자 ID {admin_id}, 오류: {e}")
            
            print(f"📊 관리자 DM 알림 결과: 성공 {success_count}명, 실패 {fail_count}명")
            return success_count, fail_count
            
        except Exception as e:
            print(f"❌ 관리자 DM 알림 전체 실패: {e}")
            return 0, len(admin_ids) if 'admin_ids' in locals() else 1

async def setup(bot):
    await bot.add_cog(UserApplicationCommands(bot))