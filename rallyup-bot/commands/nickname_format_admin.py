import discord
from discord.ext import commands
from discord import app_commands
from typing import List
import re

class NicknameFormatCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        return await self.bot.db_manager.is_server_admin(guild_id, user_id)

    @app_commands.command(name="닉네임일괄적용", description="[관리자] 모든 등록 유저의 닉네임을 현재 포맷에 맞춰 변경합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def apply_nickname_format_bulk(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            guild = interaction.guild
            
            # 현재 포맷 확인
            format_settings = await self.bot.db_manager.get_nickname_format(guild_id)
            
            # 모든 등록 유저 조회
            registered_users = await self.bot.db_manager.get_all_registered_users(guild_id)
            
            if not registered_users:
                await interaction.followup.send(
                    "❌ 등록된 유저가 없습니다.", ephemeral=True
                )
                return
            
            # 진행 메시지
            progress_embed = discord.Embed(
                title="🔄 닉네임 일괄 변경 진행 중...",
                description=f"총 {len(registered_users)}명의 유저 닉네임을 변경합니다.\n잠시만 기다려주세요...",
                color=0xffaa00
            )
            await interaction.followup.send(embed=progress_embed, ephemeral=True)
            
            # 결과 추적
            success_count = 0
            failed_count = 0
            skipped_count = 0
            failed_users = []
            
            # 각 유저에 대해 닉네임 변경
            for user_data in registered_users:
                user_id = user_data['user_id']
                member = guild.get_member(int(user_id))
                
                if not member:
                    skipped_count += 1
                    continue
                
                # 닉네임 변경 시도
                result = await self.bot.db_manager._update_user_nickname(
                    member,
                    user_data['main_position'],
                    user_data['current_season_tier'],
                    user_data['battle_tag'],  # 이제는 대표 닉네임
                    user_data.get('birth_year')
                )
                
                if "✅" in result:
                    success_count += 1
                elif "⚠️" in result or "❌" in result:
                    failed_count += 1
                    failed_users.append({
                        'name': member.display_name,
                        'reason': result
                    })
            
            # 결과 임베드
            result_embed = discord.Embed(
                title="✅ 닉네임 일괄 변경 완료",
                color=0x00ff88
            )
            
            result_embed.add_field(
                name="📊 변경 결과",
                value=f"✅ 성공: {success_count}명\n"
                    f"❌ 실패: {failed_count}명\n"
                    f"⏭️ 건너뜀: {skipped_count}명 (서버 미참여)",
                inline=False
            )
            
            result_embed.add_field(
                name="🎨 적용된 포맷",
                value=f"`{format_settings['format_template']}`",
                inline=False
            )
            
            # 실패 목록 (최대 5개만 표시)
            if failed_users:
                failed_list = "\n".join([
                    f"• {u['name']}: {u['reason'][:50]}" 
                    for u in failed_users[:5]
                ])
                if len(failed_users) > 5:
                    failed_list += f"\n... 외 {len(failed_users) - 5}명"
                
                result_embed.add_field(
                    name="⚠️ 실패 사유",
                    value=failed_list,
                    inline=False
                )
            
            result_embed.set_footer(text=f"관리자: {interaction.user.display_name}")
            
            await interaction.edit_original_response(embed=result_embed)
            
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ 일괄 변경 중 오류가 발생했습니다: {str(e)}"
            )
    
    @app_commands.command(name="닉네임포맷설정", description="[관리자] 서버 닉네임 자동 변경 포맷 설정")
    @app_commands.default_permissions(manage_guild=True)
    async def set_nickname_format(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        # 1단계: 프리셋 선택 화면
        preset_view = NicknamePresetSelectView(self.bot)
        embed = preset_view.create_initial_embed()
        
        await interaction.response.send_message(
            embed=embed, view=preset_view, ephemeral=True
        )
    
    @app_commands.command(name="닉네임포맷확인", description="[관리자] 현재 서버의 닉네임 포맷 확인")
    @app_commands.default_permissions(manage_guild=True)
    async def check_nickname_format(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            format_settings = await self.bot.db_manager.get_nickname_format(guild_id)
            
            embed = discord.Embed(
                title="📋 현재 닉네임 포맷 설정",
                color=0x0099ff
            )
            
            embed.add_field(
                name="포맷 템플릿",
                value=f"`{format_settings['format_template']}`",
                inline=False
            )
            
            # 예시 생성
            example_data = {
                'nickname': '헤븐',
                'battle_tag': '헤븐#1234',
                'birth_year': '00',
                'position': '탱커',
                'tier': '그마',
                'previous_tier': '다이아',
                'highest_tier': '그마'
            }
            
            example_nickname = self.bot.db_manager._generate_nickname_from_template(
                format_settings['format_template'], 
                example_data
            )
            
            embed.add_field(
                name="📌 적용 예시",
                value=f"**입력**: 헤븐#1234, 탱커, 그마, 00년생\n"
                      f"**결과**: `{example_nickname}`",
                inline=False
            )
            
            embed.set_footer(text="포맷 변경: /닉네임포맷설정")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 오류가 발생했습니다: {str(e)}", ephemeral=True
            )


class NicknamePresetSelectView(discord.ui.View):
    """프리셋 선택 View"""
    
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
        
        # 프리셋 정의
        self.presets = {
            'preset1': {
                'name': '닉네임 생년 티어',
                'template': '{nickname} {birth_year} {tier}',
                'example': '헤븐 00 그마',
                'emoji': '🎯'
            },
            'preset2': {
                'name': '배틀태그/포지션/티어',
                'template': '{battle_tag}/{position}/{tier}',
                'example': 'PEEDI#3742/탱/다이아',
                'emoji': '🎮'
            },
            'preset3': {
                'name': '[티어] 닉네임',
                'template': '[{tier}] {nickname}',
                'example': '[그마] 헤븐',
                'emoji': '🏆'
            },
            'preset4': {
                'name': '닉네임 (포지션) 티어',
                'template': '{nickname} ({position}) {tier}',
                'example': '헤븐 (탱) 그마',
                'emoji': '⚔️'
            },
            'preset5': {
                'name': '배틀태그 - 티어',
                'template': '{battle_tag} - {tier}',
                'example': 'PEEDI#3742 - 다이아',
                'emoji': '💎'
            }
        }
        
        self.add_preset_buttons()
    
    def create_initial_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎨 닉네임 포맷 설정",
            description="원하는 방식을 선택해주세요",
            color=0x0099ff
        )
        
        embed.add_field(
            name="📦 프리셋 선택",
            value="아래 버튼에서 자주 사용되는 포맷을 바로 선택할 수 있습니다.",
            inline=False
        )
        
        embed.add_field(
            name="🛠️ 직접 제작",
            value="원하는 필드를 순서대로 선택하여 커스텀 포맷을 만들 수 있습니다.",
            inline=False
        )
        
        return embed
    
    def add_preset_buttons(self):
        """프리셋 버튼 추가"""
        row = 0
        for preset_id, preset_data in self.presets.items():
            button = discord.ui.Button(
                label=f"{preset_data['emoji']} {preset_data['name']}",
                style=discord.ButtonStyle.primary,
                custom_id=preset_id,
                row=row
            )
            button.callback = lambda i, pid=preset_id: self.preset_selected(i, pid)
            self.add_item(button)
            row += 1
            
            if row >= 5:  # Discord 최대 5행 제한
                break
        
        # 커스텀 제작 버튼
        custom_button = discord.ui.Button(
            label="🛠️ 직접 제작하기",
            style=discord.ButtonStyle.success,
            row=4
        )
        custom_button.callback = self.custom_builder
        self.add_item(custom_button)
    
    async def preset_selected(self, interaction: discord.Interaction, preset_id: str):
        """프리셋 선택됨"""
        preset = self.presets[preset_id]
        
        # 확인 View로 이동
        confirm_view = NicknameFormatConfirmView(
            self.bot,
            preset['template'],
            self._extract_fields(preset['template'])
        )
        
        embed = confirm_view.create_preview_embed(
            preset['template'],
            preset['name']
        )
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)
    
    async def custom_builder(self, interaction: discord.Interaction):
        """커스텀 빌더로 이동"""
        builder_view = NicknameCustomBuilderView(self.bot)
        embed = builder_view.create_builder_embed()
        
        await interaction.response.edit_message(embed=embed, view=builder_view)
    
    def _extract_fields(self, template: str) -> List[str]:
        """템플릿에서 필드 추출"""
        return re.findall(r'\{([a-z_]+)\}', template)


class NicknameCustomBuilderView(discord.ui.View):
    """커스텀 닉네임 빌더 View"""
    
    def __init__(self, bot):
        super().__init__(timeout=600)
        self.bot = bot
        self.selected_fields = []  # 선택된 필드들
        self.separator = ' '  # 기본 구분자
        
        # 필드 정의 (한국어)
        self.field_info = {
            'nickname': {'label': '닉네임', 'emoji': '📝', 'example': '헤븐'},
            'battle_tag': {'label': '배틀태그', 'emoji': '🎮', 'example': '헤븐#1234'},
            'birth_year': {'label': '생년(뒤2자리)', 'emoji': '🎂', 'example': '00'},
            'position': {'label': '포지션', 'emoji': '⚔️', 'example': '탱'},
            'tier': {'label': '현시즌 티어', 'emoji': '🏆', 'example': '그마'},
            'previous_tier': {'label': '전시즌 티어', 'emoji': '📊', 'example': '다이아'},
            'highest_tier': {'label': '최고 티어', 'emoji': '👑', 'example': '그마'}
        }
        
        self.add_field_buttons()
        self.add_control_buttons()
    
    def create_builder_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🛠️ 닉네임 포맷 직접 제작",
            description="원하는 필드를 **순서대로** 클릭해서 추가하세요",
            color=0x00ff88
        )
        
        if self.selected_fields:
            # 현재 구성
            template = self._build_template()
            preview = self._generate_preview()
            
            field_names = [self.field_info[f]['label'] for f in self.selected_fields]
            
            embed.add_field(
                name="📋 현재 구성",
                value=' → '.join(field_names),
                inline=False
            )
            
            embed.add_field(
                name="🔤 생성되는 포맷",
                value=f"`{template}`",
                inline=False
            )
            
            embed.add_field(
                name="📌 미리보기",
                value=f"`{preview}`",
                inline=False
            )
        else:
            embed.add_field(
                name="💡 사용 방법",
                value="1️⃣ 아래 버튼을 **원하는 순서대로** 클릭\n"
                      "2️⃣ 실시간 미리보기 확인\n"
                      "3️⃣ 구분자 변경 (선택)\n"
                      "4️⃣ 완료 버튼 클릭",
                inline=False
            )
        
        return embed
    
    def add_field_buttons(self):
        """필드 선택 버튼 추가"""
        row = 0
        for field_id, field_data in self.field_info.items():
            button = discord.ui.Button(
                label=f"{field_data['emoji']} {field_data['label']}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"field_{field_id}",
                row=row
            )
            button.callback = lambda i, fid=field_id: self.add_field(i, fid)
            self.add_item(button)
            
            row = (row + 1) % 3  # 3줄로 배치
    
    def add_control_buttons(self):
        """제어 버튼 추가"""
        # 마지막 항목 제거
        remove_button = discord.ui.Button(
            label="◀️ 마지막 항목 제거",
            style=discord.ButtonStyle.danger,
            row=3
        )
        remove_button.callback = self.remove_last_field
        self.add_item(remove_button)
        
        # 구분자 변경
        separator_button = discord.ui.Button(
            label="➗ 구분자 변경",
            style=discord.ButtonStyle.secondary,
            row=3
        )
        separator_button.callback = self.change_separator
        self.add_item(separator_button)
        
        # 완료
        finish_button = discord.ui.Button(
            label="✅ 완료",
            style=discord.ButtonStyle.success,
            row=4,
            disabled=len(self.selected_fields) == 0
        )
        finish_button.callback = self.finish_building
        self.add_item(finish_button)
        
        # 처음부터
        reset_button = discord.ui.Button(
            label="🔄 처음부터",
            style=discord.ButtonStyle.secondary,
            row=4
        )
        reset_button.callback = self.reset_builder
        self.add_item(reset_button)
    
    async def add_field(self, interaction: discord.Interaction, field_id: str):
        """필드 추가"""
        self.selected_fields.append(field_id)
        
        # UI 업데이트
        self.clear_items()
        self.add_field_buttons()
        self.add_control_buttons()
        
        await interaction.response.edit_message(
            embed=self.create_builder_embed(),
            view=self
        )
    
    async def remove_last_field(self, interaction: discord.Interaction):
        """마지막 필드 제거"""
        if self.selected_fields:
            self.selected_fields.pop()
        
        # UI 업데이트
        self.clear_items()
        self.add_field_buttons()
        self.add_control_buttons()
        
        await interaction.response.edit_message(
            embed=self.create_builder_embed(),
            view=self
        )
    
    async def change_separator(self, interaction: discord.Interaction):
        """구분자 변경 Modal"""
        modal = SeparatorChangeModal(self)
        await interaction.response.send_modal(modal)
    
    async def reset_builder(self, interaction: discord.Interaction):
        """처음부터 다시"""
        self.selected_fields = []
        self.separator = ' '
        
        # UI 업데이트
        self.clear_items()
        self.add_field_buttons()
        self.add_control_buttons()
        
        await interaction.response.edit_message(
            embed=self.create_builder_embed(),
            view=self
        )
    
    async def finish_building(self, interaction: discord.Interaction):
        """빌드 완료"""
        if not self.selected_fields:
            await interaction.response.send_message(
                "❌ 최소 1개 이상의 필드를 선택해주세요.", ephemeral=True
            )
            return
        
        template = self._build_template()
        
        # 확인 화면으로 이동
        confirm_view = NicknameFormatConfirmView(
            self.bot,
            template,
            self.selected_fields
        )
        
        embed = confirm_view.create_preview_embed(template, "커스텀 포맷")
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)
    
    def _build_template(self) -> str:
        """현재 선택된 필드로 템플릿 생성"""
        fields = [f'{{{field}}}' for field in self.selected_fields]
        return self.separator.join(fields)
    
    def _generate_preview(self) -> str:
        """미리보기 생성"""
        example_data = {
            'nickname': '헤븐',
            'battle_tag': '헤븐#1234',
            'birth_year': '00',
            'position': '탱',
            'tier': '그마',
            'previous_tier': '다이아',
            'highest_tier': '그마'
        }
        
        preview_parts = []
        for field in self.selected_fields:
            preview_parts.append(example_data.get(field, '?'))
        
        return self.separator.join(preview_parts)


class SeparatorChangeModal(discord.ui.Modal, title="구분자 변경"):
    """구분자 변경 Modal"""
    
    separator = discord.ui.TextInput(
        label="구분자",
        placeholder="예: 공백( ), 슬래시(/), 하이픈(-), 등",
        style=discord.TextStyle.short,
        default=' ',
        max_length=5
    )
    
    def __init__(self, parent_view: NicknameCustomBuilderView):
        super().__init__()
        self.parent_view = parent_view
        self.separator.default = parent_view.separator
    
    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.separator = self.separator.value
        
        await interaction.response.edit_message(
            embed=self.parent_view.create_builder_embed(),
            view=self.parent_view
        )


class NicknameFormatConfirmView(discord.ui.View):
    """닉네임 포맷 최종 확인 View"""
    
    def __init__(self, bot, template: str, fields: List[str]):
        super().__init__(timeout=300)
        self.bot = bot
        self.template = template
        self.fields = fields
    
    def create_preview_embed(self, template: str, format_name: str) -> discord.Embed:
        """최종 확인 임베드"""
        embed = discord.Embed(
            title="✅ 닉네임 포맷 확인",
            description=f"**{format_name}**을(를) 적용하시겠습니까?",
            color=0x0099ff
        )
        
        embed.add_field(
            name="🔤 포맷",
            value=f"`{template}`",
            inline=False
        )
        
        # 다양한 예시
        examples = [
            {
                'nickname': '헤븐', 'battle_tag': '헤븐#1234', 'birth_year': '00',
                'position': '탱', 'tier': '그마', 'previous_tier': '다이아', 'highest_tier': '그마'
            },
            {
                'nickname': 'PEEDI', 'battle_tag': 'PEEDI#3742', 'birth_year': '95',
                'position': '드', 'tier': '다이아', 'previous_tier': '플래티넘', 'highest_tier': '마스터'
            },
            {
                'nickname': '루시오', 'battle_tag': '루시오#9999', 'birth_year': '03',
                'position': '힐', 'tier': '골드', 'previous_tier': '실버', 'highest_tier': '플래티넘'
            }
        ]
        
        preview_texts = []
        for ex in examples:
            result = self.bot.db_manager._generate_nickname_from_template(template, ex)
            preview_texts.append(f"• `{result}`")
        
        embed.add_field(
            name="📌 미리보기",
            value='\n'.join(preview_texts),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ 안내",
            value="• 새로 승인되는 유저부터 적용됩니다\n"
                  "• 기존 유저는 `/정보수정` 시 새 포맷으로 변경됩니다",
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="✅ 적용", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """적용"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            success = await self.bot.db_manager.set_nickname_format(
                guild_id, self.template, self.fields
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 닉네임 포맷 적용 완료",
                    description=f"새 포맷이 적용되었습니다",
                    color=0x00ff88
                )
                
                embed.add_field(
                    name="적용된 포맷",
                    value=f"`{self.template}`",
                    inline=False
                )
                
                # 버튼 비활성화
                for item in self.children:
                    item.disabled = True
                
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.followup.send("❌ 포맷 저장 실패", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ 오류: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """취소"""
        embed = discord.Embed(
            title="❌ 설정 취소",
            description="닉네임 포맷 설정이 취소되었습니다",
            color=0x999999
        )
        
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)


async def setup(bot):
    await bot.add_cog(NicknameFormatCommands(bot))