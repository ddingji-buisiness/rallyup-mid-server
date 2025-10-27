import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Literal, List
from datetime import datetime, timezone
import logging
import asyncio

logger = logging.getLogger(__name__)


class PrivateInquiryModal(discord.ui.Modal, title="1:1 개인 상담 신청"):
    """1:1 상담 신청 모달"""
    
    def __init__(self, view, admin_user_id: str, admin_name: str):
        super().__init__()
        self.view = view
        self.admin_user_id = admin_user_id
        self.admin_name = admin_name
        
        # 카테고리 입력
        self.category_input = discord.ui.TextInput(
            label="카테고리",
            placeholder="분쟁조정/신고/개인사정/기타 중 하나를 입력",
            required=True,
            max_length=20,
            default="개인사정"
        )
        self.add_item(self.category_input)
        
        # 상담 내용 (간단히)
        self.content_input = discord.ui.TextInput(
            label="상담 내용 (간단히)",
            placeholder="어떤 내용으로 상담하고 싶으신가요?",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.content_input)
        
        # 긴급도
        self.urgent_input = discord.ui.TextInput(
            label="긴급 여부 (Yes 입력 시 긴급)",
            placeholder="긴급한 경우 'Yes' 입력",
            required=False,
            max_length=3,
            default="No"
        )
        self.add_item(self.urgent_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """1:1 상담 신청 제출 처리"""
        try:
            category = self.category_input.value.strip()
            content = self.content_input.value.strip()
            is_urgent = self.urgent_input.value.strip().lower() in ['yes', 'y', '예']

            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            username = interaction.user.display_name

            # 이미 진행 중인 상담이 있는지 확인
            active_consultation = await self.view.bot.db_manager.get_user_active_consultation(
                guild_id, user_id
            )

            if active_consultation:
                await interaction.response.send_message(
                    f"❌ **이미 진행 중인 상담이 있습니다.**\n"
                    f"📋 티켓: `{active_consultation['ticket_number']}`\n"
                    f"👤 관리자: {active_consultation['admin_name']}\n"
                    f"📊 상태: `{active_consultation['status']}`\n\n"
                    "기존 상담을 완료한 후 새로운 상담을 신청해주세요.",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # 티켓 번호 생성
            ticket_number = await self.view.bot.db_manager.get_next_ticket_number(guild_id)

            # 관리자에게 DM 전송
            try:
                admin = await self.view.bot.fetch_user(int(self.admin_user_id))

                # 요청 임베드 생성
                request_embed = discord.Embed(
                    title="📞 새 1:1 상담 요청",
                    description=f"**{username}**님이 상담을 요청했습니다.",
                    color=discord.Color.red() if is_urgent else discord.Color.blue()
                )

                request_embed.add_field(
                    name="🎫 티켓 번호",
                    value=f"`{ticket_number}`",
                    inline=True
                )
                request_embed.add_field(
                    name="📂 카테고리",
                    value=f"`{category}`",
                    inline=True
                )
                request_embed.add_field(
                    name="🚨 긴급",
                    value="⚠️ 긴급" if is_urgent else "일반",
                    inline=True
                )
                request_embed.add_field(
                    name="📝 상담 내용",
                    value=content[:500] + ("..." if len(content) > 500 else ""),
                    inline=False
                )
                request_embed.set_footer(text=f"요청자 ID: {user_id}")
                request_embed.timestamp = discord.utils.utcnow()

                # 수락/거절 버튼
                request_view = ConsultationRequestView(
                    bot=self.view.bot,
                    ticket_number=ticket_number,
                    user_id=user_id,
                    username=username,
                    guild_id=guild_id,
                    admin_id=self.admin_user_id,
                    admin_name=self.admin_name,
                    category=category,
                    content=content,
                    is_urgent=is_urgent
                )

                dm_message = await admin.send(embed=request_embed, view=request_view)

                # DB 저장
                await self.view.bot.db_manager.save_consultation(
                    guild_id=guild_id,
                    ticket_number=ticket_number,
                    user_id=user_id,
                    username=username,
                    admin_id=self.admin_user_id,
                    admin_name=self.admin_name,
                    category=category,
                    content=content,
                    is_urgent=is_urgent,
                    request_message_id=str(dm_message.id)
                )

                await interaction.followup.send(
                    f"✅ **1:1 상담 요청이 전송되었습니다!**\n"
                    f"📋 티켓 번호: `{ticket_number}`\n"
                    f"👤 담당 관리자: **{self.admin_name}**\n"
                    f"📂 카테고리: `{category}`\n\n"
                    "관리자가 수락하면 DM으로 알림을 받으실 수 있습니다.",
                    ephemeral=True
                )

                logger.info(f"📞 1:1 상담 요청: {ticket_number} ({username} → {self.admin_name})")

            except discord.Forbidden:
                await interaction.followup.send(
                    f"❌ **{self.admin_name}** 관리자의 DM이 비활성화되어 있습니다.\n"
                    "다른 관리자를 선택해주세요.",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"❌ 관리자 DM 전송 실패: {e}", exc_info=True)
                await interaction.followup.send(
                    "❌ 상담 요청 전송 중 오류가 발생했습니다.\n다시 시도해주세요.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"❌ 1:1 상담 신청 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 상담 신청 처리 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass


class ConsultationRequestView(discord.ui.View):
    """상담 요청 수락/거절 View (관리자가 받는 DM)"""
    
    def __init__(
        self,
        bot,
        ticket_number: str,
        user_id: str,
        username: str,
        guild_id: str,
        admin_id: str,      
        admin_name: str,      
        category: str,
        content: str,
        is_urgent: bool
    ):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_number = ticket_number
        self.user_id = user_id
        self.username = username
        self.guild_id = guild_id
        self.admin_id = admin_id         
        self.admin_name = admin_name     
        self.category = category
        self.content = content
        self.is_urgent = is_urgent
    
    @discord.ui.button(
        label="수락",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="consult_accept"
    )
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """상담 수락"""
        try:
            # 이미 처리되었는지 확인
            consultation = await self.bot.db_manager.get_consultation_by_ticket(
                self.guild_id,
                self.ticket_number
            )
            
            if not consultation or consultation.get('status') != 'pending':
                await interaction.response.send_message(
                    "이미 처리된 상담 요청입니다.",
                    ephemeral=True
                )
                return
            
            # 상태 업데이트
            await self.bot.db_manager.update_consultation_status(
                self.guild_id,
                self.ticket_number,
                'accepted',
                str(interaction.user.id)
            )
            
            # 신청자에게 DM
            user = await self.bot.fetch_user(int(self.user_id))
            
            accept_embed = discord.Embed(
                title="✅ 상담이 수락되었습니다",
                description=f"**{interaction.user.display_name}** 관리자님이 상담을 수락했습니다.",
                color=0x57F287,
                timestamp=datetime.now()
            )
            
            accept_embed.add_field(
                name="🎫 티켓",
                value=self.ticket_number,
                inline=True
            )
            
            accept_embed.add_field(
                name="📂 카테고리",
                value=self.category,
                inline=True
            )
            
            accept_embed.add_field(
                name="💬 상담 진행",
                value=(
                    "이제 이 DM에서 관리자님과 상담하실 수 있습니다.\n"
                    "자유롭게 대화해주세요."
                ),
                inline=False
            )
            
            # 상담 세션 버튼
            session_view = ConsultationSessionView(
                self.bot,
                self.ticket_number,
                self.user_id,
                str(interaction.user.id),
                self.guild_id,
                'user'
            )
            
            await user.send(embed=accept_embed, view=session_view)
            
            # 관리자에게도 확인
            admin_confirm_embed = discord.Embed(
                title="✅ 상담을 수락했습니다",
                description=f"**{self.username}**님과의 상담이 시작되었습니다.",
                color=0x57F287,
                timestamp=datetime.now()
            )
            
            admin_confirm_embed.add_field(
                name="💬 상담 진행",
                value=(
                    "이제 이 DM에서 신청자와 상담하실 수 있습니다.\n"
                    "상담이 끝나면 아래 버튼으로 종료해주세요."
                ),
                inline=False
            )
            
            admin_session_view = ConsultationSessionView(
                self.bot,
                self.ticket_number,
                self.user_id,
                str(interaction.user.id),
                self.guild_id,
                'admin'
            )
            
            # 기존 메시지 업데이트
            original_embed = interaction.message.embeds[0]
            original_embed.color = 0x57F287
            original_embed.title = "✅ 수락한 상담"
            
            # 버튼 비활성화
            for item in self.children:
                item.disabled = True
            
            await interaction.message.edit(embed=original_embed, view=self)
            await interaction.response.send_message(
                embed=admin_confirm_embed,
                view=admin_session_view
            )
            
            logger.info(f"✅ 상담 수락: {self.ticket_number} by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"❌ 상담 수락 실패: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다.\n{str(e)}",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="거절",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="consult_reject"
    )
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """상담 거절"""
        try:
            # 상태 업데이트
            await self.bot.db_manager.update_consultation_status(
                self.guild_id,
                self.ticket_number,
                'rejected',
                str(interaction.user.id)
            )
            
            # 신청자에게 DM
            user = await self.bot.fetch_user(int(self.user_id))
            
            reject_embed = discord.Embed(
                title="❌ 상담이 거절되었습니다",
                description=f"죄송합니다. 현재 상담이 어려운 상황입니다.",
                color=0xED4245,
                timestamp=datetime.now()
            )
            
            reject_embed.add_field(
                name="📌 안내",
                value=(
                    "• 다른 관리자를 선택하여 다시 신청해주세요\n"
                    "• 또는 관리팀 문의를 이용해주세요"
                ),
                inline=False
            )
            
            await user.send(embed=reject_embed)
            
            # 관리자 확인
            original_embed = interaction.message.embeds[0]
            original_embed.color = 0xED4245
            original_embed.title = "❌ 거절한 상담"
            
            for item in self.children:
                item.disabled = True
            
            await interaction.message.edit(embed=original_embed, view=self)
            await interaction.response.send_message(
                "상담을 거절했습니다.",
                ephemeral=True
            )
            
            logger.info(f"❌ 상담 거절: {self.ticket_number} by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"❌ 상담 거절 실패: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다.\n{str(e)}",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="다른 관리자에게",
        style=discord.ButtonStyle.secondary,
        emoji="↪️",
        custom_id="consult_forward"
    )
    async def forward_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """다른 관리자에게 상담 전달"""
        try:
            # 권한 확인
            if str(interaction.user.id) != self.admin_id:
                await interaction.response.send_message(
                    "❌ 담당 관리자만 전달할 수 있습니다.",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # 현재 상담 거절 처리
            await self.bot.db_manager.update_consultation_status(
                self.guild_id,
                self.ticket_number,
                'rejected',
                str(interaction.user.id)
            )

            # 🆕 버튼 비활성화
            for item in self.children:
                item.disabled = True
            
            try:
                await interaction.message.edit(view=self)
            except:
                pass

            # 사용자에게 안내
            try:
                user = await self.bot.fetch_user(int(self.user_id))
                
                # 관리자 선택 View 다시 표시
                from .inquiry_system import AdminSelectView  # 순환 참조 방지
                admin_select_view = AdminSelectView(
                    bot=self.bot,
                    guild_id=self.guild_id,
                    user_id=self.user_id,
                    username=self.username,
                    category=self.category,
                    content=self.content,
                    is_urgent=self.is_urgent,
                    previous_ticket=self.ticket_number
                )
                
                embed = discord.Embed(
                    title="↪️ 상담이 다른 관리자에게 전달되었습니다",
                    description=(
                        f"**{self.admin_name}** 관리자가 상담을 다른 관리자에게 전달했습니다.\n\n"
                        "아래에서 다른 관리자를 선택해주세요."
                    ),
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="📋 이전 티켓",
                    value=f"`{self.ticket_number}`",
                    inline=True
                )
                embed.add_field(
                    name="📂 카테고리",
                    value=f"`{self.category}`",
                    inline=True
                )
                
                await user.send(embed=embed, view=admin_select_view)
                
            except discord.Forbidden:
                logger.warning(f"⚠️ {self.username}에게 DM 전송 실패 (DM 비활성화)")
            except Exception as e:
                logger.error(f"❌ 사용자 DM 전송 실패: {e}")

            await interaction.followup.send(
                f"↪️ **상담을 전달했습니다.**\n"
                f"사용자에게 다른 관리자 선택 안내를 보냈습니다.",
                ephemeral=True
            )

            logger.info(f"↪️ 상담 전달: {self.ticket_number} by {interaction.user.name}")

        except Exception as e:
            logger.error(f"❌ 상담 전달 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 상담 전달 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass


class ConsultationSessionView(discord.ui.View):
    """상담 진행 중 버튼 View"""
    
    def __init__(
        self,
        bot,
        ticket_number: str,
        user_id: str,
        admin_id: str,
        guild_id: str,
        role: str  # 'user' or 'admin'
    ):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_number = ticket_number
        self.user_id = user_id
        self.admin_id = admin_id
        self.guild_id = guild_id
        self.role = role
    
    @discord.ui.button(
        label="상담 종료",
        style=discord.ButtonStyle.danger,
        emoji="📚",
        custom_id="consult_end"
    )
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """상담 종료 버튼"""
        try:
            # 권한 확인 (관리자 또는 사용자만)
            if str(interaction.user.id) not in [self.user_id, self.admin_id]:
                await interaction.response.send_message(
                    "❌ 상담 참여자만 종료할 수 있습니다.",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # DB 상태 업데이트
            await self.bot.db_manager.update_consultation_status(
                self.guild_id,
                self.ticket_number,
                'completed',
                str(interaction.user.id)
            )

            # 🆕 모든 버튼 비활성화
            for item in self.children:
                item.disabled = True
            
            # 🆕 메시지 업데이트
            try:
                await interaction.message.edit(view=self)
            except:
                pass

            # 양측에 알림
            try:
                user = await self.bot.fetch_user(int(self.user_id))
                await user.send(
                    f"✅ **상담이 종료되었습니다.**\n"
                    f"📋 티켓: `{self.ticket_number}`\n"
                    f"🙏 이용해주셔서 감사합니다!"
                )
            except:
                pass

            try:
                admin = await self.bot.fetch_user(int(self.admin_id))
                await admin.send(
                    f"✅ **상담이 종료되었습니다.**\n"
                    f"📋 티켓: `{self.ticket_number}`\n"
                    f"👤 종료자: {interaction.user.mention}"
                )
            except:
                pass

            await interaction.followup.send(
                "✅ 상담이 정상적으로 종료되었습니다.",
                ephemeral=True
            )

            logger.info(f"✅ 상담 종료: {self.ticket_number} by {interaction.user.name}")

        except Exception as e:
            logger.error(f"❌ 상담 종료 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 상담 종료 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass


class AdminSelectView(discord.ui.View):
    """관리자 선택 View"""
    
    def __init__(self, bot, admins: List[dict]):
        super().__init__(timeout=300)
        self.bot = bot
        self.admins = admins
        
        # Select 메뉴 생성
        options = []
        
        # "아무나" 옵션 (랜덤)
        options.append(
            discord.SelectOption(
                label="아무 관리자나",
                value="random",
                description="가용한 관리자 중 자동 선택",
                emoji="🎲"
            )
        )
        
        # 관리자 목록
        for admin in admins[:24]:  # 최대 24명 (아무나 포함 25개)
            options.append(
                discord.SelectOption(
                    label=admin['display_name'][:100],
                    value=admin['user_id'],
                    # description=f"ID: {admin['user_id'][:50]}",
                    emoji="👤"
                )
            )
        
        select = discord.ui.Select(
            placeholder="상담받을 관리자를 선택하세요",
            options=options,
            custom_id="admin_select"
        )
        select.callback = self.select_callback
        self.add_item(select)
    
    async def select_callback(self, interaction: discord.Interaction):
        """관리자 선택 콜백"""
        selected_value = interaction.data['values'][0]
        
        if selected_value == 'random':
            # 랜덤 선택
            import random
            selected_admin = random.choice(self.admins)
            admin_id = selected_admin['user_id']
            admin_name = selected_admin['display_name']
        else:
            # 선택된 관리자
            admin_id = selected_value
            selected_admin = next((a for a in self.admins if a['user_id'] == admin_id), None)
            admin_name = selected_admin['display_name'] if selected_admin else "관리자"
        
        # 모달 열기
        modal = PrivateInquiryModal(self, admin_id, admin_name)
        await interaction.response.send_modal(modal)


class InquiryOptionsView(discord.ui.View):
    """문의 옵션 선택 View (카테고리 + 익명 여부)"""
    
    def __init__(self, bot, inquiry_system): 
        super().__init__(timeout=180)  # 3분
        self.bot = bot
        self.inquiry_system = inquiry_system
        self.selected_category = "일반"  # 기본값
        self.is_anonymous = False  # 기본값
        
        # 익명 버튼 초기 스타일 설정
        self.anonymous_button.style = discord.ButtonStyle.secondary
        self.anonymous_button.label = "익명 작성: OFF"
    
    @discord.ui.select(
        placeholder="📂 카테고리를 선택하세요",
        options=[
            discord.SelectOption(
                label="일반",
                value="일반",
                emoji="📋",
                description="일반적인 문의사항",
                default=True
            ),
            discord.SelectOption(
                label="건의",
                value="건의",
                emoji="💡",
                description="개선 제안이나 아이디어"
            ),
            discord.SelectOption(
                label="버그",
                value="버그",
                emoji="🐛",
                description="버그나 오류 제보"
            ),
            discord.SelectOption(
                label="계정",
                value="계정",
                emoji="👤",
                description="계정 관련 문의"
            ),
            discord.SelectOption(
                label="기타",
                value="기타",
                emoji="📝",
                description="기타 문의사항"
            )
        ],
        custom_id="category_select"
    )
    async def category_select(
        self, 
        interaction: discord.Interaction, 
        select: discord.ui.Select
    ):
        """카테고리 선택"""
        self.selected_category = select.values[0]
        
        # 선택 표시 업데이트
        for option in select.options:
            option.default = (option.value == self.selected_category)
        
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(
        label="익명 작성: OFF",
        style=discord.ButtonStyle.secondary,
        emoji="🎭",
        custom_id="anonymous_toggle",
        row=1
    )
    async def anonymous_button(
        self, 
        interaction: discord.Interaction, 
        button: discord.ui.Button
    ):
        """익명 여부 토글"""
        self.is_anonymous = not self.is_anonymous
        
        if self.is_anonymous:
            button.style = discord.ButtonStyle.primary
            button.label = "익명 작성: ON"
        else:
            button.style = discord.ButtonStyle.secondary
            button.label = "익명 작성: OFF"
        
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(
        label="다음",
        style=discord.ButtonStyle.success,
        emoji="▶️",
        custom_id="next_button",
        row=1
    )
    async def next_button(
        self, 
        interaction: discord.Interaction, 
        button: discord.ui.Button
    ):
        """다음 단계 - 모달 표시"""
        
        # 🆕 익명 선택 시 상세 안내
        if self.is_anonymous:
            confirm_embed = discord.Embed(
                title="🎭 익명 문의 안내",
                description=(
                    "**익명 문의를 선택하셨습니다.**\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "✅ **보장되는 것:**\n"
                    "• 관리자 채널에 '익명'으로만 표시\n"
                    "• 관리자도 작성자를 확인할 수 없음\n"
                    "• 비공개 쓰레드에서만 논의 (일반 멤버 못 봄)\n"
                    "• 답변은 DM으로만 전송\n"
                    "• 양방향 대화 가능 (무제한 답장)\n\n"
                    "⚠️ **주의사항:**\n"
                    "• DM이 꺼져있으면 답변을 받을 수 없습니다\n"
                    "• 악의적 도배 시 자동 제재됩니다\n"
                    "• 허위 신고는 서버 규칙 위반입니다\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "📌 **스팸 방지 정책:**\n"
                    "• 1시간 내 5회 이상 문의 → 1시간 제한\n"
                    "• 1일 내 15회 이상 문의 → 24시간 제한\n"
                    "• 동일 내용 반복 → 작성 차단\n\n"
                    "계속 진행하시겠습니까?"
                ),
                color=discord.Color.gold()
            )
            
            # 확인 View
            confirm_view = discord.ui.View(timeout=60)
            
            async def confirm_callback(confirm_interaction: discord.Interaction):
                if confirm_interaction.user.id != interaction.user.id:
                    await confirm_interaction.response.send_message(
                        "❌ 본인만 선택할 수 있습니다.",
                        ephemeral=True
                    )
                    return
                
                modal = TeamInquiryModal(
                    view=self,
                    category=self.selected_category,
                    is_anonymous=self.is_anonymous
                )
                await confirm_interaction.response.send_modal(modal)
            
            async def cancel_callback(cancel_interaction: discord.Interaction):
                if cancel_interaction.user.id != interaction.user.id:
                    await cancel_interaction.response.send_message(
                        "❌ 본인만 선택할 수 있습니다.",
                        ephemeral=True
                    )
                    return
                await cancel_interaction.response.edit_message(
                    content="❌ 문의 작성이 취소되었습니다.",
                    embed=None,
                    view=None
                )
            
            confirm_button = discord.ui.Button(
                label="익명으로 계속 진행",
                style=discord.ButtonStyle.success,
                emoji="✅"
            )
            confirm_button.callback = confirm_callback
            
            back_button = discord.ui.Button(
                label="뒤로가기",
                style=discord.ButtonStyle.secondary,
                emoji="◀️"
            )
            
            async def back_callback(back_interaction: discord.Interaction):
                if back_interaction.user.id != interaction.user.id:
                    await back_interaction.response.send_message(
                        "❌ 본인만 선택할 수 있습니다.",
                        ephemeral=True
                    )
                    return
                # 익명 OFF로 변경
                self.is_anonymous = False
                self.anonymous_button.style = discord.ButtonStyle.secondary
                self.anonymous_button.label = "익명 작성: OFF"
                
                # 원래 화면으로
                embed = discord.Embed(
                    title="📋 관리팀 문의 작성",
                    description=(
                        "**1단계: 옵션 선택**\n\n"
                        "**📂 카테고리**\n"
                        "드롭다운에서 문의 유형을 선택하세요.\n\n"
                        "**🎭 익명 여부**\n"
                        "익명으로 작성하려면 버튼을 클릭하세요.\n"
                        "(`익명 작성: ON` 상태가 되면 익명으로 작성됩니다)\n\n"
                        "선택 완료 후 **다음** 버튼을 눌러주세요."
                    ),
                    color=discord.Color.blue()
                )
                
                await back_interaction.response.edit_message(
                    embed=embed,
                    view=self
                )
            
            back_button.callback = back_callback
            
            cancel_button = discord.ui.Button(
                label="취소",
                style=discord.ButtonStyle.danger,
                emoji="❌"
            )
            cancel_button.callback = cancel_callback
            
            confirm_view.add_item(confirm_button)
            confirm_view.add_item(back_button)
            confirm_view.add_item(cancel_button)
            
            await interaction.response.send_message(
                embed=confirm_embed,
                view=confirm_view,
                ephemeral=True
            )
        else:
            modal = TeamInquiryModal(
                view=self,
                category=self.selected_category,
                is_anonymous=self.is_anonymous
            )
            await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="취소",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="cancel_button",
        row=1
    )
    async def cancel_button(
        self, 
        interaction: discord.Interaction, 
        button: discord.ui.Button
    ):
        """취소"""
        await interaction.response.edit_message(
            content="❌ 문의 작성이 취소되었습니다.",
            embed=None,
            view=None
        )

class ConsultationOptionsView(discord.ui.View):
    """1:1 상담 옵션 선택 View"""
    
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild = guild
        self.selected_admin = None  # 선택된 관리자
        self.selected_category = "일반"  # 기본 카테고리
        self.is_urgent = False  # 긴급 여부
        
        # 관리자 목록 가져오기 (초기화 시 동적 생성)
        self._setup_admin_select()
        
        # 긴급 버튼 초기 스타일
        self.urgent_button.style = discord.ButtonStyle.secondary
        self.urgent_button.label = "긴급: OFF"
    
    def _setup_admin_select(self):
        """관리자 선택 드롭다운 동적 생성"""
        # 관리자 권한 가진 멤버 찾기
        admin_members = [
            member for member in self.guild.members
            if not member.bot and (
                member.guild_permissions.administrator or
                member.guild_permissions.manage_guild
            )
        ]
        
        if not admin_members:
            # 관리자가 없으면 경고
            options = [
                discord.SelectOption(
                    label="관리자 없음",
                    value="none",
                    description="현재 관리자가 없습니다",
                    emoji="❌"
                )
            ]
        else:
            # 최대 25명까지만 표시 (Discord 제한)
            options = [
                discord.SelectOption(
                    label=member.display_name,
                    value=str(member.id),
                    description=f"@{member.name}",
                    emoji="👤",
                    default=False
                )
                for member in admin_members[:25]
            ]
        
        self.admin_select.options = options
    
    @discord.ui.select(
        placeholder="👤 상담받을 관리자를 선택하세요",
        options=[],  # 동적으로 생성됨
        custom_id="admin_select"
    )
    async def admin_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select
    ):
        """관리자 선택"""
        selected_id = select.values[0]
        
        if selected_id == "none":
            await interaction.response.send_message(
                "❌ 현재 관리자가 없어 1:1 상담을 신청할 수 없습니다.",
                ephemeral=True
            )
            return
        
        self.selected_admin = selected_id
        
        # 선택 표시 업데이트
        for option in select.options:
            option.default = (option.value == selected_id)
        
        await interaction.response.edit_message(view=self)
    
    @discord.ui.select(
        placeholder="📂 카테고리를 선택하세요",
        options=[
            discord.SelectOption(
                label="일반",
                value="일반",
                emoji="📋",
                description="일반적인 상담",
                default=True
            ),
            discord.SelectOption(
                label="분쟁조정",
                value="분쟁조정",
                emoji="⚖️",
                description="멤버 간 분쟁 조정"
            ),
            discord.SelectOption(
                label="신고",
                value="신고",
                emoji="🚨",
                description="규칙 위반 신고"
            ),
            discord.SelectOption(
                label="개인사정",
                value="개인사정",
                emoji="🔒",
                description="개인적인 사정 상담"
            ),
            discord.SelectOption(
                label="기타",
                value="기타",
                emoji="📝",
                description="기타 상담"
            )
        ],
        custom_id="category_select",
        row=1
    )
    async def category_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select
    ):
        """카테고리 선택"""
        self.selected_category = select.values[0]
        
        # 선택 표시 업데이트
        for option in select.options:
            option.default = (option.value == self.selected_category)
        
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(
        label="긴급: OFF",
        style=discord.ButtonStyle.secondary,
        emoji="🚨",
        custom_id="urgent_toggle",
        row=2
    )
    async def urgent_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """긴급 여부 토글"""
        self.is_urgent = not self.is_urgent
        
        if self.is_urgent:
            button.style = discord.ButtonStyle.danger
            button.label = "긴급: ON"
        else:
            button.style = discord.ButtonStyle.secondary
            button.label = "긴급: OFF"
        
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(
        label="다음",
        style=discord.ButtonStyle.success,
        emoji="▶️",
        custom_id="next_button",
        row=2
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """다음 단계 - 모달 표시"""
        # 관리자 선택 확인
        if not self.selected_admin:
            await interaction.response.send_message(
                "❌ 상담받을 관리자를 먼저 선택해주세요.",
                ephemeral=True
            )
            return
        
        # 관리자 정보 가져오기
        admin = self.guild.get_member(int(self.selected_admin))
        if not admin:
            await interaction.response.send_message(
                "❌ 선택한 관리자를 찾을 수 없습니다.",
                ephemeral=True
            )
            return
        
        # 모달 표시
        modal = PrivateConsultationModal(
            view=self,
            admin=admin,
            category=self.selected_category,
            is_urgent=self.is_urgent
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="취소",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="cancel_button",
        row=2
    )
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """취소"""
        await interaction.response.edit_message(
            content="❌ 상담 신청이 취소되었습니다.",
            embed=None,
            view=None
        )

class PrivateConsultationModal(discord.ui.Modal, title="1:1 상담 신청"):
    """1:1 상담 모달 (내용만 입력)"""
    
    def __init__(self, view, admin: discord.Member, category: str, is_urgent: bool):
        super().__init__()
        self.view = view
        self.admin = admin
        self.category = category
        self.is_urgent = is_urgent
        
        # 내용만 입력받음
        self.content_input = discord.ui.TextInput(
            label="상담 내용",
            placeholder="상담하실 내용을 자세히 작성해주세요",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        self.add_item(self.content_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """1:1 상담 신청 처리"""
        try:
            content = self.content_input.value.strip()
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            username = interaction.user.display_name
            
            # 진행 중인 상담 확인
            active_consultation = await self.view.bot.db_manager.get_user_active_consultation(
                guild_id,
                user_id
            )
            
            if active_consultation:
                await interaction.response.send_message(
                    f"⚠️ **이미 진행 중인 상담이 있습니다.**\n\n"
                    f"📋 티켓: `{active_consultation['ticket_number']}`\n"
                    f"👤 담당: {active_consultation['admin_name']}\n"
                    f"📂 카테고리: {active_consultation['category']}\n\n"
                    f"기존 상담이 완료된 후 새로운 상담을 신청할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 티켓 번호 생성
            ticket_number = await self.view.bot.db_manager.get_next_ticket_number(guild_id)
            
            # 관리자에게 DM 전송
            try:
                request_embed = discord.Embed(
                    title="💬 1:1 상담 요청",
                    description=(
                        f"**{username}**님이 1:1 상담을 요청했습니다.\n\n"
                        f"{'🚨 **긴급 상담입니다!**' if self.is_urgent else ''}"
                    ),
                    color=discord.Color.red() if self.is_urgent else discord.Color.blue()
                )
                request_embed.add_field(
                    name="🎫 티켓 번호",
                    value=f"`{ticket_number}`",
                    inline=True
                )
                request_embed.add_field(
                    name="📂 카테고리",
                    value=self.category,
                    inline=True
                )
                request_embed.add_field(
                    name="🚨 긴급도",
                    value="긴급" if self.is_urgent else "일반",
                    inline=True
                )
                request_embed.add_field(
                    name="📝 상담 내용",
                    value=content[:1000] + ("..." if len(content) > 1000 else ""),
                    inline=False
                )
                request_embed.set_footer(
                    text=f"신청자: {username}",
                    icon_url=interaction.user.display_avatar.url
                )
                request_embed.timestamp = discord.utils.utcnow()
                
                # 수락/거절 버튼
                consultation_view = ConsultationResponseView(
                    bot=self.view.bot,
                    guild_id=guild_id,
                    ticket_number=ticket_number,
                    user_id=user_id,
                    username=username,
                    admin=self.admin
                )
                
                dm_message = await self.admin.send(
                    embed=request_embed,
                    view=consultation_view
                )
                
                # DB 저장
                save_success = await self.view.bot.db_manager.save_consultation(
                    guild_id=guild_id,
                    ticket_number=ticket_number,
                    user_id=user_id,
                    username=username,
                    admin_id=str(self.admin.id),
                    admin_name=self.admin.display_name,
                    category=self.category,
                    content=content,
                    is_urgent=self.is_urgent,
                    request_message_id=str(dm_message.id)
                )
                
                if save_success:
                    await interaction.followup.send(
                        f"✅ **1:1 상담이 신청되었습니다!**\n\n"
                        f"📋 티켓: `{ticket_number}`\n"
                        f"👤 담당 관리자: {self.admin.mention}\n"
                        f"📂 카테고리: `{self.category}`\n"
                        f"🚨 긴급도: `{'긴급' if self.is_urgent else '일반'}`\n\n"
                        f"관리자가 확인 후 DM으로 연락드립니다.",
                        ephemeral=True
                    )
                    
                    logger.info(
                        f"💬 1:1 상담 신청: {ticket_number} "
                        f"by {username} → {self.admin.display_name} "
                        f"({'긴급' if self.is_urgent else '일반'})"
                    )
                else:
                    await dm_message.delete()
                    await interaction.followup.send(
                        "❌ 상담 신청 중 오류가 발생했습니다.",
                        ephemeral=True
                    )
                
            except discord.Forbidden:
                await interaction.followup.send(
                    f"❌ **관리자의 DM이 비활성화되어 있습니다.**\n\n"
                    f"{self.admin.mention}님께 DM을 활성화하도록 요청하거나,\n"
                    f"다른 관리자를 선택해주세요.",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"❌ 상담 요청 전송 실패: {e}")
                await interaction.followup.send(
                    "❌ 상담 요청 전송 중 오류가 발생했습니다.",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"❌ 1:1 상담 신청 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 상담 신청 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass


class ConsultationResponseView(discord.ui.View):
    """1:1 상담 요청 수락/거절 View (관리자용)"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, user_id: str, username: str, admin: discord.Member):
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.user_id = user_id
        self.username = username
        self.admin = admin
    
    @discord.ui.button(
        label="수락",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="consultation:accept"
    )
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """상담 수락"""
        try:
            # 더미 View인 경우
            if not self.guild_id or not self.ticket_number:
                await interaction.response.send_message(
                    "❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                    ephemeral=True
                )
                logger.error("❌ ConsultationResponseView: 빈 데이터로 버튼 클릭됨")
                return
            
            # admin이 None인 경우
            if not self.admin:
                self.admin = interaction.user

            # 권한 확인
            if interaction.user.id != self.admin.id:
                await interaction.response.send_message(
                    "❌ 본인에게 요청된 상담만 수락할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # 상태 업데이트
            await self.bot.db_manager.update_consultation_status(
                self.guild_id,
                self.ticket_number,
                'accepted',
                str(self.admin.id)
            )
            
            try:
                user = await self.bot.fetch_user(int(self.user_id))
                
                # 1) 상담 수락 알림 (버튼 없음)
                accept_embed = discord.Embed(
                    title="✅ 1:1 상담 수락됨",
                    description=(
                        f"**{self.admin.display_name}**님과 상담이 연결되었습니다.\n\n"
                        f"💬 **아래 [답장하기] 버튼으로 대화하세요.**\n"
                        f"💡 상담이 필요한 내용을 편하게 말씀해주세요."
                    ),
                    color=discord.Color.green()
                )
                accept_embed.add_field(
                    name="🎫 티켓 번호",
                    value=f"`{self.ticket_number}`",
                    inline=True
                )
                accept_embed.add_field(
                    name="👤 담당 관리자",
                    value=self.admin.display_name,
                    inline=True
                )
                
                await user.send(embed=accept_embed)
                
                # 2) 컨트롤 패널 (버튼 있음) - 고정 위치
                control_embed = discord.Embed(
                    title="🎮 상담 컨트롤 패널",
                    description=(
                        f"💬 **[답장하기]** 버튼으로 대화하세요.\n"
                        f"상담이 필요한 내용을 편하게 말씀해주세요.\n\n"
                        f"🎫 티켓: `{self.ticket_number}`"
                    ),
                    color=discord.Color.blue()
                )
                control_embed.set_footer(text="이 메시지는 상담이 끝날 때까지 유지됩니다")
                
                # 사용자용 버튼
                user_reply_view = ConsultationReplyView(
                    bot=self.bot,
                    guild_id=self.guild_id,
                    ticket_number=self.ticket_number,
                    target_user_id=str(self.admin.id),
                    is_admin=False
                )
                
                await user.send(embed=control_embed, view=user_reply_view)
                
            except discord.Forbidden:
                await interaction.followup.send(
                    "⚠️ 사용자의 DM이 비활성화되어 있어 알림을 보낼 수 없습니다.\n"
                    "직접 멘션하여 연락해주세요.",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"❌ 사용자 알림 전송 실패: {e}")
        
            original_embed = interaction.message.embeds[0]
            original_embed.color = discord.Color.green()
            original_embed.title = "✅ 1:1 상담 수락됨"
            
            await interaction.message.edit(embed=original_embed, view=None)
            
            # 1) 상담 시작 알림 (버튼 없음)
            guidance_embed = discord.Embed(
                title="✅ 상담 시작",
                description=(
                    f"**{self.username}**님과의 1:1 상담이 시작되었습니다.\n\n"
                    f"💬 **아래 [답장하기] 버튼으로 대화하세요.**\n"
                    f"• 사용자가 메시지를 보내면 이 DM으로 전달됩니다\n"
                    f"• 상담 완료 시 [상담 완료] 버튼을 클릭하세요\n\n"
                    f"🎫 티켓: `{self.ticket_number}`"
                ),
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=guidance_embed)
            
            # 2) 컨트롤 패널 (버튼 있음)
            admin_control_embed = discord.Embed(
                title="🎮 상담 컨트롤 패널",
                description=(
                    f"💬 **[답장하기]** 버튼으로 대화하세요.\n"
                    f"✅ **[상담 완료]** 버튼으로 상담을 종료하세요.\n\n"
                    f"🎫 티켓: `{self.ticket_number}`\n"
                    f"👤 상담 상대: {self.username}"
                ),
                color=discord.Color.blue()
            )
            admin_control_embed.set_footer(text="이 메시지는 상담이 끝날 때까지 유지됩니다")
            
            # 관리자용 버튼
            admin_reply_view = ConsultationReplyView(
                bot=self.bot,
                guild_id=self.guild_id,
                ticket_number=self.ticket_number,
                target_user_id=self.user_id,
                is_admin=True
            )
            
            await interaction.followup.send(embed=admin_control_embed, view=admin_reply_view)
            
            logger.info(f"✅ 상담 수락: {self.ticket_number} by {self.admin.display_name}")
            
        except Exception as e:
            logger.error(f"❌ 상담 수락 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 상담 수락 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass
    
    @discord.ui.button(
        label="거절",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="consultation:reject"
    )
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """상담 거절"""
        try:
            # 더미 View인 경우
            if not self.guild_id or not self.ticket_number:
                await interaction.response.send_message(
                    "❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                    ephemeral=True
                )
                logger.error("❌ ConsultationResponseView: 빈 데이터로 버튼 클릭됨")
                return
            
            # admin이 None인 경우
            if not self.admin:
                self.admin = interaction.user

            # 권한 확인 (본인만 거절 가능)
            if interaction.user.id != self.admin.id:
                await interaction.response.send_message(
                    "❌ 본인에게 요청된 상담만 거절할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            # 거절 사유 모달
            modal = ConsultationRejectModal(
                bot=self.bot,
                guild_id=self.guild_id,
                ticket_number=self.ticket_number,
                user_id=self.user_id,
                username=self.username,
                admin=self.admin,
                original_message=interaction.message
            )
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"❌ 상담 거절 버튼 오류: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

class ConsultationRejectModal(discord.ui.Modal, title="상담 거절 사유"):
    """상담 거절 사유 입력 모달"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, user_id: str, username: str, admin: discord.Member, original_message: discord.Message):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.user_id = user_id
        self.username = username
        self.admin = admin
        self.original_message = original_message
        
        self.reason_input = discord.ui.TextInput(
            label="거절 사유 (선택)",
            placeholder="사용자에게 전달할 거절 사유를 입력하세요 (선택사항)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """거절 처리"""
        try:
            reason = self.reason_input.value.strip() or "관리자가 상담을 거절했습니다."
            
            await interaction.response.defer()
            
            # 상태 업데이트
            await self.bot.db_manager.update_consultation_status(
                self.guild_id,
                self.ticket_number,
                'rejected',
                str(self.admin.id)
            )
            
            # 사용자에게 알림
            try:
                user = await self.bot.fetch_user(int(self.user_id))
                
                reject_embed = discord.Embed(
                    title="❌ 1:1 상담 거절됨",
                    description=(
                        f"**{self.admin.display_name}**님이 상담을 거절했습니다.\n\n"
                        f"**사유:**\n{reason}\n\n"
                        f"다른 관리자에게 상담을 신청하시거나,\n"
                        f"`/문의하기 → 관리팀 문의`를 이용해주세요."
                    ),
                    color=discord.Color.red()
                )
                reject_embed.add_field(
                    name="🎫 티켓 번호",
                    value=f"`{self.ticket_number}`",
                    inline=True
                )
                reject_embed.set_footer(text=f"거절한 관리자: {self.admin.display_name}")
                reject_embed.timestamp = discord.utils.utcnow()
                
                await user.send(embed=reject_embed)
                
            except discord.Forbidden:
                await interaction.followup.send(
                    "⚠️ 사용자의 DM이 비활성화되어 있어 알림을 보낼 수 없습니다.",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"❌ 사용자 알림 전송 실패: {e}")
            
            # 원본 메시지 업데이트
            original_embed = self.original_message.embeds[0]
            original_embed.color = discord.Color.red()
            original_embed.title = "❌ 1:1 상담 거절됨"
            original_embed.add_field(
                name="📝 거절 사유",
                value=reason,
                inline=False
            )
            
            await self.original_message.edit(embed=original_embed, view=None)
            
            await interaction.followup.send(
                f"✅ 상담을 거절했습니다.\n사용자에게 알림이 전송되었습니다.",
                ephemeral=True
            )
            
            logger.info(f"❌ 상담 거절: {self.ticket_number} by {self.admin.display_name}")
            
        except Exception as e:
            logger.error(f"❌ 상담 거절 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 상담 거절 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

class ConsultationReplyView(discord.ui.View):
    """1:1 상담 답장 View (봇 재시작 대응)"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, target_user_id: str, is_admin: bool):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.target_user_id = target_user_id
        self.is_admin = is_admin  # True: 관리자, False: 사용자
        self._processing = False
        
        # 🆕 custom_id에 데이터 인코딩 (봇 재시작 대응)
        self._setup_buttons()
    
    def _setup_buttons(self):
        """버튼 설정 (custom_id에 데이터 포함)"""
        # 기존 버튼 제거
        self.clear_items()
        
        # 데이터 인코딩
        data = f"{self.guild_id}:{self.ticket_number}:{self.target_user_id}:{int(self.is_admin)}"
        
        # 답장하기 버튼
        reply_button = discord.ui.Button(
            label="답장하기",
            style=discord.ButtonStyle.primary,
            emoji="💬",
            custom_id=f"consultation:reply:{data}"  # 데이터 포함
        )
        reply_button.callback = self.reply_button_callback
        self.add_item(reply_button)
        
        # 상담 완료 버튼
        end_button = discord.ui.Button(
            label="상담 완료",
            style=discord.ButtonStyle.success,
            emoji="✅",
            custom_id=f"consultation:end:{data}"  # 데이터 포함
        )
        end_button.callback = self.end_button_callback
        self.add_item(end_button)
    
    def _parse_custom_id(self, custom_id: str) -> tuple:
        """custom_id에서 데이터 파싱"""
        try:
            # consultation:reply:guild_id:ticket_number:target_user_id:is_admin
            parts = custom_id.split(':', 2)  # 최대 3개로 분리
            if len(parts) < 3:
                return None, None, None, None
            
            _, action, data = parts
            data_parts = data.split(':')
            
            if len(data_parts) != 4:
                return None, None, None, None
            
            guild_id, ticket_number, target_user_id, is_admin = data_parts
            is_admin = bool(int(is_admin))
            
            return guild_id, ticket_number, target_user_id, is_admin
            
        except Exception as e:
            logger.error(f"❌ custom_id 파싱 실패: {e}")
            return None, None, None, None
    
    async def reply_button_callback(self, interaction: discord.Interaction):
        """답장 버튼 콜백"""
        if self._processing:
            logger.warning("⚠️ 이미 처리 중인 인터랙션")
            return
        
        self._processing = True

        try:
            if interaction.response.is_done():
                logger.warning(f"⚠️ 인터랙션이 이미 처리됨 - 중복 클릭 감지")
                return
        
            # custom_id에서 데이터 복원
            guild_id, ticket_number, target_user_id, is_admin = self._parse_custom_id(
                interaction.data['custom_id']
            )
            
            # 데이터 검증
            if not guild_id or not ticket_number:
                # self 속성도 확인
                guild_id = guild_id or self.guild_id
                ticket_number = ticket_number or self.ticket_number
                target_user_id = target_user_id or self.target_user_id
                is_admin = is_admin if is_admin is not None else self.is_admin
            
            # 여전히 없으면 에러
            if not guild_id or not ticket_number:
                await interaction.response.send_message(
                    "⚠️ **봇이 재시작되어 버튼 정보가 초기화되었습니다.**\n\n"
                    "📌 **해결 방법:**\n"
                    "1. 이 DM 대화에서 직접 메시지를 보내주세요\n"
                    "2. 관리자가 답장을 보내면 새로운 버튼이 생성됩니다\n\n"
                    "💡 상담은 계속 진행 중이니 걱정하지 마세요!",
                    ephemeral=True
                )
                logger.error("❌ ConsultationReplyView: 빈 데이터로 버튼 클릭됨")
                return
            
            # 데이터 복원 (self에 저장)
            self.guild_id = guild_id
            self.ticket_number = ticket_number
            self.target_user_id = target_user_id
            self.is_admin = is_admin
            
            # 상담 상태 확인
            consultation = await self.bot.db_manager.get_consultation_by_ticket(
                guild_id,
                ticket_number
            )
            
            if not consultation:
                await interaction.response.send_message(
                    "❌ 상담 정보를 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            if consultation['status'] == 'completed':
                await interaction.response.send_message(
                    "ℹ️ 이미 완료된 상담입니다.",
                    ephemeral=True
                )
                return
            
            # 답장 모달
            modal = ConsultationReplyModal(
                bot=self.bot,
                guild_id=guild_id,
                ticket_number=ticket_number,
                target_user_id=target_user_id,
                sender=interaction.user,
                is_admin=is_admin
            )
            await interaction.response.send_modal(modal)
        except discord.errors.HTTPException as e:
            if e.code == 40060:  # Interaction already acknowledged
                logger.warning(f"⚠️ 인터랙션 중복 처리 시도 (무시됨)")
                return  # 조용히 무시
            logger.error(f"❌ 답장 버튼 HTTP 오류: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                        ephemeral=True
                    )
            except:
                pass
        except Exception as e:
            logger.error(f"❌ 답장 버튼 오류: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                        ephemeral=True
                    )
            except:
                pass
        finally:
            self._processing = False
    
    async def end_button_callback(self, interaction: discord.Interaction):
        """상담 종료 콜백"""
        try: 
            await interaction.response.defer()
            
            # custom_id에서 데이터 복원
            guild_id, ticket_number, target_user_id, is_admin = self._parse_custom_id(
                interaction.data['custom_id']
            )
            
            # 데이터 검증
            if not guild_id or not ticket_number:
                # self 속성도 확인
                guild_id = guild_id or self.guild_id
                ticket_number = ticket_number or self.ticket_number
                target_user_id = target_user_id or self.target_user_id
                is_admin = is_admin if is_admin is not None else self.is_admin
            
            # 여전히 없으면 에러
            if not guild_id or not ticket_number:
                await interaction.response.send_message(
                    "⚠️ **봇이 재시작되어 버튼 정보가 초기화되었습니다.**\n\n"
                    "📌 상담 완료는 DM으로 관리자에게 말씀해주세요!",
                    ephemeral=True
                )
                logger.error("❌ ConsultationReplyView: 빈 데이터로 버튼 클릭됨")
                return
            
            # 데이터 복원
            self.guild_id = guild_id
            self.ticket_number = ticket_number
            self.target_user_id = target_user_id
            self.is_admin = is_admin
                        
            consultation = await self.bot.db_manager.get_consultation_by_ticket(
                guild_id,
                ticket_number
            )
            
            if not consultation:
                await interaction.followup.send(
                    "❌ 상담 정보를 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            if consultation['status'] == 'completed':
                await interaction.followup.send(
                    "ℹ️ 이미 완료된 상담입니다.",
                    ephemeral=True
                )
                return
            
            # 상태 업데이트
            await self.bot.db_manager.update_consultation_status(
                guild_id,
                ticket_number,
                'completed',
                str(interaction.user.id)
            )
            
            # 상대방에게 알림
            try:
                target_user = await self.bot.fetch_user(int(target_user_id))
                
                if is_admin:
                    # 관리자가 종료 → 사용자에게
                    end_embed = discord.Embed(
                        title="✅ 상담 완료",
                        description=(
                            f"**{consultation['admin_name']}**님이 상담을 완료했습니다.\n\n"
                            f"🎫 티켓: `{ticket_number}`\n\n"
                            f"상담에 참여해주셔서 감사합니다.\n"
                            f"추가 문의가 있으시면 언제든 `/문의하기`를 이용해주세요."
                        ),
                        color=discord.Color.green()
                    )
                else:
                    # 사용자가 종료 → 관리자에게
                    end_embed = discord.Embed(
                        title="✅ 상담 완료",
                        description=(
                            f"**{consultation['username']}**님이 상담을 완료했습니다.\n\n"
                            f"🎫 티켓: `{ticket_number}`"
                        ),
                        color=discord.Color.green()
                    )
                
                await target_user.send(embed=end_embed)
                
            except discord.Forbidden:
                logger.warning(f"⚠️ 상담 완료 알림 전송 실패 (DM 비활성화)")
            except Exception as e:
                logger.error(f"❌ 상담 완료 알림 전송 실패: {e}")
            
            # 버튼 비활성화
            for item in self.children:
                item.disabled = True
                if item.custom_id and 'end' in item.custom_id:
                    item.label = "완료됨"
                    item.style = discord.ButtonStyle.secondary
            
            await interaction.message.edit(view=self)
            
            await interaction.followup.send(
                "✅ 상담이 완료되었습니다.\n상대방에게 알림이 전송되었습니다.",
                ephemeral=True
            )
            
            logger.info(f"✅ 상담 완료: {ticket_number} by {interaction.user.name}")
        
        except Exception as e:
            logger.error(f"❌ 상담 종료 오류: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ 상담 종료 중 오류가 발생했습니다.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ 상담 종료 중 오류가 발생했습니다.",
                        ephemeral=True
                    )
            except:
                pass

class ConsultationReplyModal(discord.ui.Modal, title="답장 보내기"):
    """1:1 상담 답장 모달"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, target_user_id: str, sender: discord.User, is_admin: bool):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.target_user_id = target_user_id
        self.sender = sender
        self.is_admin = is_admin
        
        self.message_input = discord.ui.TextInput(
            label="메시지",
            placeholder="전달할 메시지를 입력하세요",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        self.add_item(self.message_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """답장 전송"""
        try:
            message_content = self.message_input.value.strip()
            
            await interaction.response.defer(ephemeral=True)
            
            # 1. 상대방에게 메시지 전달
            try:
                target_user = await self.bot.fetch_user(int(self.target_user_id))
                
                # 상대방에게 보이는 메시지
                if self.is_admin:
                    # 관리자 → 사용자
                    received_embed = discord.Embed(
                        description=f"💬 **{self.sender.display_name}** (관리자)\n\n{message_content}",
                        color=discord.Color.blue()
                    )
                else:
                    # 사용자 → 관리자  
                    received_embed = discord.Embed(
                        description=f"💭 **{self.sender.display_name}**\n\n{message_content}",
                        color=discord.Color.green()
                    )
                
                received_embed.set_footer(
                    text=f"티켓: {self.ticket_number} • 답장하려면 컨트롤 패널의 버튼을 사용하세요"
                )
                received_embed.timestamp = discord.utils.utcnow()
                
                # 상대방에게 전송
                await target_user.send(embed=received_embed)
                
                # 2. 나 자신에게도 내가 보낸 메시지 표시 (대화 흐름 유지)
                sent_embed = discord.Embed(
                    description=f"📤 **나** ({self.sender.display_name})\n\n{message_content}",
                    color=discord.Color.greyple()  # 회색톤으로 구분
                )
                sent_embed.set_footer(
                    text=f"티켓: {self.ticket_number} • 상대방에게 전송됨"
                )
                sent_embed.timestamp = discord.utils.utcnow()
                
                # 나에게도 전송 (내가 보낸 메시지 확인용)
                await self.sender.send(embed=sent_embed)
                
                await interaction.followup.send(
                    f"✅ 메시지가 전송되었습니다.",
                    ephemeral=True
                )
                
                logger.info(f"💬 상담 메시지 전송: {self.ticket_number} by {self.sender.name}")
                
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ 상대방의 DM이 비활성화되어 있어 메시지를 전송할 수 없습니다.",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"❌ 메시지 전송 실패: {e}")
                await interaction.followup.send(
                    "❌ 메시지 전송 중 오류가 발생했습니다.",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"❌ 답장 전송 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 답장 전송 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

class ConsultationEndView(discord.ui.View):
    """상담 종료 버튼 View"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, is_user: bool):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.is_user = is_user  # True: 사용자, False: 관리자
    
    @discord.ui.button(
        label="상담 완료",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="end_consultation"
    )
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """상담 종료"""
        try:
            await interaction.response.defer()
            
            # 상담 정보 조회
            consultation = await self.bot.db_manager.get_consultation_by_ticket(
                self.guild_id,
                self.ticket_number
            )
            
            if not consultation:
                await interaction.followup.send(
                    "❌ 상담 정보를 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 이미 완료된 상담인지 확인
            if consultation['status'] == 'completed':
                await interaction.followup.send(
                    "ℹ️ 이미 완료된 상담입니다.",
                    ephemeral=True
                )
                return
            
            # 상태 업데이트
            await self.bot.db_manager.update_consultation_status(
                self.guild_id,
                self.ticket_number,
                'completed',
                str(interaction.user.id)
            )
            
            # 상대방에게 알림
            try:
                if self.is_user:
                    # 사용자가 종료 → 관리자에게 알림
                    admin = await self.bot.fetch_user(int(consultation['admin_id']))
                    
                    end_embed = discord.Embed(
                        title="✅ 상담 완료",
                        description=(
                            f"**{consultation['username']}**님이 상담을 완료했습니다.\n\n"
                            f"🎫 티켓: `{self.ticket_number}`"
                        ),
                        color=discord.Color.green()
                    )
                    
                    await admin.send(embed=end_embed)
                    
                else:
                    # 관리자가 종료 → 사용자에게 알림
                    user = await self.bot.fetch_user(int(consultation['user_id']))
                    
                    end_embed = discord.Embed(
                        title="✅ 상담 완료",
                        description=(
                            f"**{consultation['admin_name']}**님과의 상담이 완료되었습니다.\n\n"
                            f"🎫 티켓: `{self.ticket_number}`\n\n"
                            f"상담에 참여해주셔서 감사합니다.\n"
                            f"추가 문의가 있으시면 언제든 `/문의하기`를 이용해주세요."
                        ),
                        color=discord.Color.green()
                    )
                    
                    await user.send(embed=end_embed)
                    
            except discord.Forbidden:
                logger.warning(f"⚠️ 상담 완료 알림 전송 실패 (DM 비활성화)")
            except Exception as e:
                logger.error(f"❌ 상담 완료 알림 전송 실패: {e}")
            
            # 버튼 비활성화
            button.disabled = True
            button.label = "완료됨"
            button.style = discord.ButtonStyle.secondary
            
            await interaction.message.edit(view=self)
            
            await interaction.followup.send(
                "✅ 상담이 완료되었습니다.\n상대방에게 알림이 전송되었습니다.",
                ephemeral=True
            )
            
            logger.info(f"✅ 상담 완료: {self.ticket_number} by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"❌ 상담 종료 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 상담 종료 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

class TeamInquiryModal(discord.ui.Modal, title="관리팀에게 문의하기"):
    """관리팀 문의 작성 모달 (제목 + 내용만)"""
    
    def __init__(self, view, category: str, is_anonymous: bool):
        super().__init__()
        self.view = view
        self.category = category  # 🆕 미리 선택된 카테고리
        self.is_anonymous = is_anonymous  # 🆕 미리 선택된 익명 여부
        
        # 제목 입력
        self.title_input = discord.ui.TextInput(
            label="제목",
            placeholder="문의 제목을 간단히 입력해주세요",
            required=True,
            max_length=100
        )
        self.add_item(self.title_input)
        
        # 내용 입력
        self.content_input = discord.ui.TextInput(
            label="문의 내용",
            placeholder="문의하실 내용을 자세히 작성해주세요",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        self.add_item(self.content_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """관리팀 문의 모달 제출 처리"""
        try:
            title = self.title_input.value.strip()
            content = self.content_input.value.strip()
            
            category = self.category
            is_anonymous = self.is_anonymous

            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            username = interaction.user.display_name

            # 🆕 쿨다운 체크 (스팸 제재 중인지)
            cooldown_check = await self.view.bot.db_manager.check_inquiry_cooldown(
                guild_id,
                user_id
            )
            
            if cooldown_check.get('is_cooldown'):
                remaining = cooldown_check.get('remaining_minutes', 0)
                hours = remaining // 60
                minutes = remaining % 60
                
                time_str = f"{hours}시간 {minutes}분" if hours > 0 else f"{minutes}분"
                
                await interaction.response.send_message(
                    f"⏰ **문의 작성이 일시적으로 제한되었습니다.**\n\n"
                    f"**사유:** 단시간 내 과도한 문의 감지\n"
                    f"**해제까지:** 약 {time_str} 남음\n\n"
                    f"문의가 긴급한 경우 관리자에게 직접 DM을 보내주세요.",
                    ephemeral=True
                )
                return

            # 🆕 스팸 체크
            spam_check = await self.view.bot.db_manager.check_inquiry_spam(
                guild_id,
                user_id
            )
            
            # 1시간 내 5회 이상
            if spam_check['hour_count'] >= 5:
                await self.view.bot.db_manager.add_inquiry_cooldown(
                    guild_id,
                    user_id,
                    hours=1
                )
                
                await interaction.response.send_message(
                    f"⚠️ **문의 작성이 제한되었습니다.**\n\n"
                    f"**사유:** 1시간 내 {spam_check['hour_count']}회 문의 (제한: 5회)\n"
                    f"**제한 시간:** 1시간\n\n"
                    f"💡 잠시 후 다시 시도해주세요.",
                    ephemeral=True
                )
                
                logger.warning(f"⚠️ 스팸 감지 (1시간): {username} ({spam_check['hour_count']}회)")
                return
            
            # 1일 내 15회 이상
            if spam_check['day_count'] >= 15:
                await self.view.bot.db_manager.add_inquiry_cooldown(
                    guild_id,
                    user_id,
                    hours=24
                )
                
                await interaction.response.send_message(
                    f"🚫 **문의 작성이 24시간 제한되었습니다.**\n\n"
                    f"**사유:** 하루 내 {spam_check['day_count']}회 문의 (제한: 15회)\n"
                    f"**제한 시간:** 24시간\n\n"
                    f"긴급한 경우 관리자에게 직접 DM을 보내주세요.",
                    ephemeral=True
                )
                
                logger.warning(f"🚫 스팸 감지 (24시간): {username} ({spam_check['day_count']}회)")
                return
            
            # 🆕 유사도 체크 (동일 내용 반복)
            if spam_check['recent_contents']:
                from difflib import SequenceMatcher
                
                for recent_content in spam_check['recent_contents']:
                    similarity = SequenceMatcher(None, content, recent_content).ratio()
                    
                    if similarity > 0.9:  # 90% 이상 유사
                        await interaction.response.send_message(
                            f"⚠️ **유사한 내용의 문의가 이미 존재합니다.**\n\n"
                            f"최근에 작성하신 문의와 거의 동일한 내용입니다.\n"
                            f"기존 문의의 답변을 기다려주시거나,\n"
                            f"다른 내용으로 작성해주세요.\n\n"
                            f"💡 `/내문의` 명령어로 기존 문의를 확인할 수 있습니다.",
                            ephemeral=True
                        )
                        
                        logger.warning(f"⚠️ 중복 내용 감지: {username} (유사도: {similarity:.2%})")
                        return

            # 일일 제한 재확인 (기존 코드)
            today_count = await self.view.bot.db_manager.get_user_daily_inquiry_count(
                guild_id,
                user_id
            )
            
            settings = await self.view.bot.db_manager.get_inquiry_settings(guild_id)
            daily_limit = settings.get('daily_limit', 3)
            
            if today_count >= daily_limit:
                await interaction.response.send_message(
                    f"❌ **일일 문의 제한에 도달했습니다.**\n"
                    f"📊 오늘 작성한 문의: **{today_count}/{daily_limit}건**\n"
                    f"⏰ 내일 00시에 초기화됩니다.",
                    ephemeral=True
                )
                return

            # 문의 채널 확인 (기존 코드)
            channel_id = await self.view.bot.db_manager.get_inquiry_channel(guild_id)
            
            if not channel_id:
                await interaction.response.send_message(
                    "❌ 관리팀 문의 채널이 설정되지 않았습니다.\n"
                    "관리자에게 `/문의채널설정` 명령어로 채널을 설정하도록 요청하세요.",
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.response.send_message(
                    "❌ 설정된 문의 채널을 찾을 수 없습니다.\n관리자에게 문의하세요.",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # 티켓 번호 생성
            ticket_number = await self.view.bot.db_manager.get_next_ticket_number(guild_id)

            # 티켓 임베드 생성
            inquiry_system = self.view.inquiry_system
            embed = await inquiry_system._create_ticket_embed(
                interaction=interaction,
                ticket_number=ticket_number,
                title=title,
                category=category,
                content=content,
                is_anonymous=is_anonymous
            )

            # 티켓 관리 View 생성 (익명이면 작성자 확인 버튼 자동 제거됨)
            ticket_view = TicketManagementView(
                bot=self.view.bot,
                guild_id=guild_id,
                ticket_number=ticket_number,
                is_anonymous=is_anonymous,
                user_id=user_id
            )

            # 채널에 티켓 게시
            ticket_message = await channel.send(embed=embed, view=ticket_view)

            # DB 저장
            save_success = await self.view.bot.db_manager.save_inquiry(
                guild_id=guild_id,
                ticket_number=ticket_number,
                user_id=user_id,
                username=username,
                inquiry_type='team',
                category=category,
                title=title,
                content=content,
                is_anonymous=is_anonymous,
                channel_message_id=str(ticket_message.id)
            )

            if save_success:
                await interaction.followup.send(
                    f"✅ **문의가 등록되었습니다!**\n"
                    f"📋 티켓 번호: `{ticket_number}`\n"
                    f"📂 카테고리: `{category}`\n"
                    f"🔒 {'익명' if is_anonymous else '실명'} 문의\n\n"
                    f"{'💬 관리팀이 비공개 쓰레드에서 확인 후 DM으로 답변드립니다.' if is_anonymous else '💬 관리팀이 확인 후 답변드립니다.'}\n"
                    f"📱 DM으로 답변이 전달되므로 DM을 켜두세요!",
                    ephemeral=True
                )
                
                logger.info(f"📋 문의 등록: {ticket_number} by {username} ({'익명' if is_anonymous else '실명'})")
            else:
                await ticket_message.delete()
                await interaction.followup.send(
                    "❌ 문의 등록 중 오류가 발생했습니다. 다시 시도해주세요.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"❌ 관리팀 문의 제출 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 문의 처리 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

class AnonymousReplyModal(discord.ui.Modal, title="익명 문의 답변 (DM 발송)"):
    """익명 문의 DM 답변 모달"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, user_id: str, admin: discord.User):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.user_id = user_id
        self.admin = admin
        
        self.reply_input = discord.ui.TextInput(
            label="답변 내용",
            placeholder="익명 작성자에게 전달할 답변을 작성하세요",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        self.add_item(self.reply_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """DM으로 답변 전송"""
        try:
            reply_content = self.reply_input.value.strip()
            
            await interaction.response.defer(ephemeral=True)
            
            # 작성자에게 DM 전송
            try:
                user = await self.bot.fetch_user(int(self.user_id))
                
                # 문의 정보 조회
                inquiry = await self.bot.db_manager.get_inquiry_by_ticket(
                    self.guild_id,
                    self.ticket_number
                )
                
                embed = discord.Embed(
                    title=f"💬 문의 답변 도착 - {self.ticket_number}",
                    description=reply_content,
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="📋 원문의 제목",
                    value=inquiry['title'],
                    inline=False
                )
                embed.add_field(
                    name="👤 답변자",
                    value=f"{self.admin.display_name}",
                    inline=True
                )
                embed.add_field(
                    name="📂 카테고리",
                    value=inquiry['category'],
                    inline=True
                )
                embed.set_footer(text="익명 문의에 대한 답변입니다")
                embed.timestamp = discord.utils.utcnow()
                
                await user.send(embed=embed)
                
                # 상태 업데이트
                await self.bot.db_manager.update_inquiry_status(
                    self.guild_id,
                    self.ticket_number,
                    'processing',
                    str(self.admin.id)
                )
                
                # 로그 기록
                await self.bot.db_manager.add_inquiry_log(
                    self.guild_id,
                    self.ticket_number,
                    str(self.admin.id),
                    self.admin.display_name,
                    'dm_reply_sent',
                    f"익명 문의 DM 답변 전송 (길이: {len(reply_content)}자)"
                )
                
                await interaction.followup.send(
                    f"✅ **DM으로 답변이 전송되었습니다.**\n"
                    f"📋 티켓: `{self.ticket_number}`\n"
                    f"👤 수신자: 익명 작성자\n\n"
                    f"추가 답변이 필요하면 다시 **답변하기** 버튼을 눌러주세요.",
                    ephemeral=True
                )
                
                logger.info(f"💬 익명 문의 DM 답변: {self.ticket_number} by {self.admin.name}")
                
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ 작성자의 DM이 비활성화되어 있습니다.\n"
                    "작성자에게 DM을 활성화하도록 요청하거나, 서버 공지로 답변해주세요.",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"❌ DM 전송 실패: {e}")
                await interaction.followup.send(
                    "❌ DM 전송 중 오류가 발생했습니다.",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"❌ 익명 답변 전송 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 답변 전송 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

class ThreadDMBridgeView(discord.ui.View):
    """쓰레드-DM 브리지 View"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, user_id: str, thread: discord.Thread):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.user_id = user_id
        self.thread = thread

    async def _check_admin_permission(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인"""
        # 서버 관리자 권한
        if interaction.user.guild_permissions.administrator:
            return True
        
        # 길드 관리 권한
        if interaction.user.guild_permissions.manage_guild:
            return True
        
        # DB에 등록된 관리자
        try:
            async with self.bot.db_manager.get_connection() as db:
                async with db.execute('''
                    SELECT user_id FROM server_admins
                    WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
                ''', (self.guild_id, str(interaction.user.id))) as cursor:
                    result = await cursor.fetchone()
                    if result:
                        return True
        except Exception as e:
            logger.error(f"권한 확인 오류: {e}")
        
        return False
    
    @discord.ui.button(
        label="DM 전송",
        style=discord.ButtonStyle.success,
        emoji="📨",
        custom_id="thread_dm:send"
    )
    async def send_dm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """답변을 DM으로 전송"""
        try:
            # 더미 View인 경우
            if not self.guild_id or not self.ticket_number:
                await interaction.response.send_message(
                    "❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                    ephemeral=True
                )
                return
            
            # 권한 체크 추가
            if not await self._check_admin_permission(interaction):
                await interaction.response.send_message(
                    "❌ 관리자만 DM을 전송할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            modal = DMReplyModal(
                bot=self.bot,
                guild_id=self.guild_id,
                ticket_number=self.ticket_number,
                user_id=self.user_id,
                thread=self.thread,
                admin=interaction.user
            )
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"❌ DM 전송 버튼 오류: {e}", exc_info=True)


class DMReplyModal(discord.ui.Modal, title="사용자에게 DM 전송"):
    """DM 답변 모달"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, user_id: str, thread: discord.Thread, admin: discord.User):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.user_id = user_id
        self.thread = thread
        self.admin = admin
        
        self.reply_input = discord.ui.TextInput(
            label="답변 내용",
            placeholder="사용자에게 전달할 답변을 작성하세요",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        self.add_item(self.reply_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """DM 전송"""
        try:
            reply_content = self.reply_input.value.strip()
            
            await interaction.response.defer(ephemeral=True)
            
            # 사용자에게 DM 전송
            try:
                user = await self.bot.fetch_user(int(self.user_id))
                
                # 문의 정보 조회
                inquiry = await self.bot.db_manager.get_inquiry_by_ticket(
                    self.guild_id,
                    self.ticket_number
                )
                
                embed = discord.Embed(
                    title=f"💬 문의 답변 - {self.ticket_number}",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="📋 문의 제목",
                    value=inquiry['title'],
                    inline=False
                )

                original_content = inquiry.get('content', '내용 없음')
                if len(original_content) > 500:
                    original_content = original_content[:500] + "..."
                
                embed.add_field(
                    name="❓ 내 질문",
                    value=original_content,
                    inline=False
                )

                embed.add_field(
                    name="✅ 답변",
                    value=reply_content,
                    inline=False
                )

                embed.add_field(
                    name="📂 카테고리",
                    value=inquiry['category'],
                    inline=True
                )
                embed.set_footer(text=f"티켓: {self.ticket_number}")
                embed.timestamp = discord.utils.utcnow()
                
                # 답장 버튼 추가
                reply_view = UserReplyView(
                    bot=self.bot,
                    guild_id=self.guild_id,
                    ticket_number=self.ticket_number,
                    thread_id=str(self.thread.id)
                )
                
                await user.send(embed=embed, view=reply_view)
                
                # 쓰레드에 전송 기록
                thread_embed = discord.Embed(
                    title="📨 DM 전송 완료",
                    description=reply_content,
                    color=discord.Color.green()
                )
                # thread_embed.set_footer(text=f"전송자: {self.admin.display_name}")
                thread_embed.timestamp = discord.utils.utcnow()
                
                await self.thread.send(embed=thread_embed)
                
                # 로그 기록
                await self.bot.db_manager.add_inquiry_log(
                    self.guild_id,
                    self.ticket_number,
                    str(self.admin.id),
                    self.admin.display_name,
                    'dm_sent',
                    f"DM 답변 전송 ({len(reply_content)}자)"
                )
                
                await interaction.followup.send(
                    f"✅ **DM이 전송되었습니다!**\n"
                    f"📋 티켓: `{self.ticket_number}`\n"
                    f"사용자가 답장하면 이 쓰레드에 자동으로 전달됩니다.",
                    ephemeral=True
                )
                
                logger.info(f"📨 DM 전송: {self.ticket_number} by {self.admin.name}")
                
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ 사용자의 DM이 비활성화되어 있습니다.\n"
                    "사용자에게 DM을 활성화하도록 요청해주세요.",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"❌ DM 전송 실패: {e}")
                await interaction.followup.send(
                    "❌ DM 전송 중 오류가 발생했습니다.",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"❌ DM 전송 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 답변 전송 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass


class UserReplyView(discord.ui.View):
    """사용자 답장 View"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, thread_id: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.thread_id = thread_id
    
    @discord.ui.button(
        label="답장하기",
        style=discord.ButtonStyle.primary,
        emoji="↩️",
        custom_id="user_reply:send"
    )
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """사용자가 답장"""
        # 더미 View인 경우
        if not self.guild_id or not self.ticket_number:
            await interaction.response.send_message(
                "❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                ephemeral=True
            )
            return
        
        modal = UserReplyModal(
            bot=self.bot,
            guild_id=self.guild_id,
            ticket_number=self.ticket_number,
            thread_id=self.thread_id,
            user=interaction.user
        )
        await interaction.response.send_modal(modal)


class UserReplyModal(discord.ui.Modal, title="답장하기"):
    """사용자 답장 모달"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, thread_id: str, user: discord.User):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.thread_id = thread_id
        self.user = user
        
        self.reply_input = discord.ui.TextInput(
            label="답장 내용",
            placeholder="관리팀에게 전달할 내용을 작성하세요",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        self.add_item(self.reply_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """답장 전송"""
        try:
            reply_content = self.reply_input.value.strip()
            
            await interaction.response.defer(ephemeral=True)
            
            # 쓰레드 찾기
            guild = self.bot.get_guild(int(self.guild_id))
            if not guild:
                await interaction.followup.send(
                    "❌ 서버를 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            thread = guild.get_thread(int(self.thread_id))
            if not thread:
                await interaction.followup.send(
                    "❌ 답변 쓰레드를 찾을 수 없습니다.\n"
                    "티켓이 종료되었을 수 있습니다.",
                    ephemeral=True
                )
                return
            
            # 문의 정보 조회 (담당 관리자 정보 가져오기)
            inquiry = await self.bot.db_manager.get_inquiry_by_ticket(
                self.guild_id,
                self.ticket_number
            )
            
            if not inquiry:
                logger.warning(f"⚠️ 문의 정보를 찾을 수 없음: {self.ticket_number}")
            
            # 쓰레드에 답장 전달 (관리자 멘션 포함)
            embed = discord.Embed(
                title="↩️ 사용자 답장",
                description=reply_content,
                color=discord.Color.gold()
            )
            embed.set_author(
                name=f"{self.user.display_name} ({self.user.name})",
                icon_url=self.user.display_avatar.url
            )
            embed.timestamp = discord.utils.utcnow()
            
            # 관리자 멘션과 함께 전송
            mention_text = ""
            admin = None
            
            if inquiry and inquiry.get('assigned_to'):
                try:
                    admin = await guild.fetch_member(int(inquiry['assigned_to']))
                    if admin:
                        mention_text = f"📢 {admin.mention} 님, 사용자가 답장했습니다!"
                        logger.info(f"✅ 관리자 찾음: {admin.name} (ID: {inquiry['assigned_to']})")
                except Exception as e:
                    logger.warning(f"⚠️ 관리자 멘션 실패: {e}")
            else:
                logger.warning(f"⚠️ 담당 관리자 없음: assigned_to={inquiry.get('assigned_to') if inquiry else None}")
            
            # 쓰레드에 전송 (멘션 + Embed)
            await thread.send(
                content=mention_text if mention_text else None,
                embed=embed
            )
            
            # 관리자에게 DM 알림 (추가 알림)
            if admin:
                try:
                    dm_embed = discord.Embed(
                        title="🔔 새 답장 알림",
                        description=(
                            f"**{self.user.display_name}**님이 문의에 답장했습니다.\n\n"
                            f"**답장 내용:**\n{reply_content[:200]}{'...' if len(reply_content) > 200 else ''}"
                        ),
                        color=discord.Color.gold()
                    )
                    dm_embed.add_field(
                        name="🎫 티켓 번호",
                        value=f"`{self.ticket_number}`",
                        inline=True
                    )
                    dm_embed.add_field(
                        name="📋 문의 제목",
                        value=inquiry.get('title', '제목 없음'),
                        inline=True
                    )
                    dm_embed.set_footer(text="쓰레드에서 확인하세요")
                    
                    await admin.send(embed=dm_embed)
                    logger.info(f"✅ 관리자 DM 알림 전송: {admin.name}")
                    
                except discord.Forbidden:
                    logger.warning(f"⚠️ 관리자 DM 전송 실패 (비활성화): {admin.name}")
                except Exception as e:
                    logger.error(f"❌ 관리자 DM 알림 실패: {e}")
            
            # 로그 기록
            await self.bot.db_manager.add_inquiry_log(
                self.guild_id,
                self.ticket_number,
                str(self.user.id),
                self.user.display_name,
                'user_reply',
                f"사용자 답장 ({len(reply_content)}자)"
            )
            
            await interaction.followup.send(
                f"✅ **답장이 전송되었습니다!**\n"
                f"🎫 티켓: `{self.ticket_number}`\n\n"
                f"관리팀이 확인 후 다시 답변드리겠습니다.",
                ephemeral=True
            )
            
            logger.info(f"↩️ 사용자 답장: {self.ticket_number} from {self.user.name}")
            
        except Exception as e:
            logger.error(f"❌ 답장 전송 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 답장 전송 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

class TicketManagementView(discord.ui.View):
    """티켓 관리 View (관리자용 버튼들)"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, is_anonymous: bool, user_id: str):
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.is_anonymous = is_anonymous
        self.user_id = user_id
        
        # 익명 문의면 작성자 확인 버튼 제거
        if is_anonymous:
            items_to_remove = []
            for item in self.children:
                if hasattr(item, 'custom_id') and item.custom_id == 'ticket_reveal':
                    items_to_remove.append(item)
            
            for item in items_to_remove:
                self.remove_item(item)
        
    async def _load_ticket_data_from_message(self, interaction: discord.Interaction) -> bool:
        """메시지에서 티켓 데이터를 추출하고 DB에서 조회"""
        try:
            # 이미 데이터가 있으면 스킵
            if self.guild_id and self.ticket_number:
                return True
            
            # 메시지에서 티켓 번호 추출
            if not interaction.message or not interaction.message.embeds:
                logger.error("❌ 메시지 또는 embed 없음")
                return False
            
            embed = interaction.message.embeds[0]
            guild_id = str(interaction.guild_id)
            ticket_number = None
            
            # Footer에서 추출: "티켓: #0011"
            if embed.footer and embed.footer.text:
                footer_text = embed.footer.text
                if '#' in footer_text:
                    parts = footer_text.split('#')
                    if len(parts) > 1:
                        ticket_part = parts[1].split()[0].split('•')[0].strip()
                        ticket_number = f"#{ticket_part}"
            
            # Title에서 추출
            if not ticket_number and embed.title:
                if '#' in embed.title:
                    parts = embed.title.split('#')
                    if len(parts) > 1:
                        ticket_part = parts[1].split()[0].strip()
                        ticket_number = f"#{ticket_part}"
            
            # Fields에서 추출
            if not ticket_number:
                for field in embed.fields:
                    if '티켓' in field.name or 'ticket' in field.name.lower():
                        value = field.value.strip()
                        if '#' in value:
                            ticket_number = value.strip('`').strip()
                        else:
                            ticket_number = f"#{value.strip('`').strip()}"
                        break
            
            if not ticket_number:
                logger.error("❌ 티켓 번호를 찾을 수 없음")
                return False
            
            logger.info(f"🔍 티켓 번호 추출: {ticket_number}")
            
            # DB에서 티켓 정보 조회
            inquiry = await self.bot.db_manager.get_inquiry_by_ticket(
                guild_id,
                ticket_number
            )
            
            if not inquiry:
                logger.error(f"❌ DB에서 티켓을 찾을 수 없음: {ticket_number}")
                return False
            
            # 데이터 복원
            self.guild_id = guild_id
            self.ticket_number = ticket_number
            self.is_anonymous = inquiry.get('is_anonymous', False)
            self.user_id = inquiry['user_id']
            
            logger.info(f"✅ 티켓 데이터 복원 성공: {ticket_number}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 티켓 데이터 추출 실패: {e}", exc_info=True)
            return False

    @discord.ui.button(
        label="답변하기",
        style=discord.ButtonStyle.primary,
        emoji="💬",
        custom_id="ticket:reply"
    )
    async def reply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """답변 버튼 - 비공개 쓰레드 생성"""
        try:
            # 더미 View인 경우
            if not self.guild_id or not self.ticket_number:
                if not await self._load_ticket_data_from_message(interaction):
                    await interaction.response.send_message(
                        "❌ 티켓 정보를 불러올 수 없습니다.",
                        ephemeral=True
                    )
                    return
            
            # 관리자 권한 확인
            if not await self._check_admin_permission(interaction):
                await interaction.response.send_message(
                    "❌ 관리자만 답변할 수 있습니다.",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # 이미 쓰레드가 있는지 확인
            message = interaction.message
            if message.thread:
                await interaction.followup.send(
                    f"ℹ️ 이미 답변 쓰레드가 존재합니다: {message.thread.mention}",
                    ephemeral=True
                )
                return

            # 비공개 쓰레드 생성 (관리자만 볼 수 있음)
            thread = await message.create_thread(
                name=f"🔒 {self.ticket_number} 답변 (비공개)",
                auto_archive_duration=1440  # 24시간
            )

            # 쓰레드 시작 메시지
            embed = discord.Embed(
                title="🔒 비공개 답변 쓰레드",
                description=(
                    f"**티켓:** `{self.ticket_number}`\n"
                    f"**작성자:** {'🎭 익명' if self.is_anonymous else f'<@{self.user_id}>'}\n"
                    f"**답변 시작:** {interaction.user.mention}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "📌 **이 쓰레드는 관리자만 볼 수 있습니다.**\n\n"
                    "**답변 방법:**\n"
                    "1️⃣ 이 쓰레드에서 관리자들끼리 논의\n"
                    "2️⃣ 아래 **[DM 전송]** 버튼으로 사용자에게 답변 전달\n"
                    "3️⃣ 사용자가 답장하면 이 쓰레드에 자동 전달됨\n"
                    "4️⃣ 완료 시 원본 메시지의 **[처리 완료]** 버튼 클릭\n\n"
                    "💡 **TIP:** 답변 내용을 이 쓰레드에 먼저 작성 → 버튼으로 전송"
                ),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"답변 담당: {interaction.user.display_name}")
            embed.timestamp = discord.utils.utcnow()

            # DM 전송 View 추가
            dm_view = ThreadDMBridgeView(
                bot=self.bot,
                guild_id=self.guild_id,
                ticket_number=self.ticket_number,
                user_id=self.user_id,
                thread=thread
            )

            await thread.send(embed=embed, view=dm_view)

            # 상태를 'processing'으로 업데이트
            await self.bot.db_manager.update_inquiry_status(
                self.guild_id,
                self.ticket_number,
                'processing',
                str(interaction.user.id)
            )

            # 로그 기록
            await self.bot.db_manager.add_inquiry_log(
                self.guild_id,
                self.ticket_number,
                str(interaction.user.id),
                interaction.user.display_name,
                'thread_created',
                f"비공개 쓰레드 생성: {thread.id}"
            )

            # 원본 임베드 업데이트
            embed = message.embeds[0]
            
            status_field_index = None
            for i, field in enumerate(embed.fields):
                if field.name == "📊 상태":
                    status_field_index = i
                    break
            
            if status_field_index is not None:
                embed.set_field_at(
                    status_field_index,
                    name="📊 상태",
                    value="🔄 답변 진행 중",
                    inline=True
                )
            else:
                embed.add_field(
                    name="📊 상태",
                    value="🔄 답변 진행 중",
                    inline=True
                )
            
            embed.add_field(
                name="👤 담당자",
                value=interaction.user.mention,
                inline=True
            )
            embed.color = discord.Color.orange()
            
            await message.edit(embed=embed)

            await interaction.followup.send(
                f"✅ **비공개 답변 쓰레드가 생성되었습니다!**\n"
                f"{thread.mention}\n\n"
                f"💡 쓰레드 내 **[DM 전송]** 버튼으로 사용자에게 답변을 전달하세요.",
                ephemeral=True
            )

            logger.info(f"🔒 비공개 쓰레드 생성: {self.ticket_number} by {interaction.user.name}")

        except Exception as e:
            logger.error(f"❌ 쓰레드 생성 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 쓰레드 생성 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

    @discord.ui.button(
        label="처리 완료",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="ticket:complete",
    )
    async def complete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """처리 완료 버튼"""
        try:
            # 데이터가 없으면 메시지에서 추출
            if not self.guild_id or not self.ticket_number:
                if not await self._load_ticket_data_from_message(interaction):
                    await interaction.response.send_message(
                        "❌ 티켓 정보를 불러올 수 없습니다.",
                        ephemeral=True
                    )
                    return
            
            # 관리자 권한 확인
            if not await self._check_admin_permission(interaction):
                await interaction.response.send_message(
                    "❌ 관리자만 처리 완료할 수 있습니다.",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # 상태를 'completed'로 업데이트
            await self.bot.db_manager.update_inquiry_status(
                self.guild_id,
                self.ticket_number,
                'completed',
                str(interaction.user.id)
            )

            # 로그 기록
            await self.bot.db_manager.add_inquiry_log(
                self.guild_id,
                self.ticket_number,
                str(interaction.user.id),
                interaction.user.display_name,
                'completed',
                '문의 처리 완료'
            )

            # 모든 버튼 비활성화
            for item in self.children:
                item.disabled = True

            # 원본 임베드 업데이트
            message = interaction.message
            embed = message.embeds[0]
            
            # 상태 필드 업데이트
            for i, field in enumerate(embed.fields):
                if field.name == "📊 상태":
                    embed.set_field_at(
                        i,
                        name="📊 상태",
                        value="✅ 처리 완료",
                        inline=True
                    )
                    break
            
            embed.add_field(
                name="✅ 완료 처리자",
                value=interaction.user.mention,
                inline=True
            )
            embed.add_field(
                name="⏰ 완료 시각",
                value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>",
                inline=True
            )
            embed.color = discord.Color.green()
            
            await message.edit(embed=embed, view=self)

            # 쓰레드가 있으면 잠금
            if message.thread:
                try:
                    await message.thread.edit(
                        archived=True,
                        locked=True,
                        reason=f"문의 처리 완료 by {interaction.user.display_name}"
                    )
                except:
                    pass

            # 사용자에게 DM 알림
            try:
                user = await self.bot.fetch_user(int(self.user_id))
                
                # 티켓 정보 조회
                inquiry = await self.bot.db_manager.get_inquiry_by_ticket(
                    self.guild_id,
                    self.ticket_number
                )
                
                notification_embed = discord.Embed(
                    title="✅ 문의 처리 완료",
                    description=(
                        f"**티켓:** `{self.ticket_number}`\n"
                        f"**카테고리:** `{inquiry['category']}`\n"
                        f"**제목:** {inquiry['title']}\n\n"
                        "문의가 정상적으로 처리되었습니다.\n"
                        "이용해주셔서 감사합니다! 🙏"
                    ),
                    color=discord.Color.green()
                )
                notification_embed.add_field(
                    name="👤 처리자",
                    value=interaction.user.display_name,
                    inline=True
                )
                notification_embed.add_field(
                    name="⏰ 완료 시각",
                    value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>",
                    inline=True
                )
                notification_embed.set_footer(text="추가 문의사항이 있으시면 /문의하기를 이용해주세요")
                notification_embed.timestamp = discord.utils.utcnow()
                
                await user.send(embed=notification_embed)
            except discord.Forbidden:
                logger.warning(f"⚠️ 사용자 {self.user_id} DM 전송 실패")
            except Exception as e:
                logger.error(f"❌ 완료 알림 전송 실패: {e}")

            await interaction.followup.send(
                "✅ 문의가 처리 완료되었습니다.",
                ephemeral=True
            )

            logger.info(f"✅ 문의 처리 완료: {self.ticket_number} by {interaction.user.name}")

        except Exception as e:
            logger.error(f"❌ 처리 완료 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 처리 완료 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

    @discord.ui.button(
        label="티켓 삭제",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id="ticket:delete",
        row=1
    )
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """티켓 삭제 버튼 (확인 후 삭제)"""
        try:
            # 데이터가 없으면 메시지에서 추출
            if not self.guild_id or not self.ticket_number:
                if not await self._load_ticket_data_from_message(interaction):
                    await interaction.response.send_message(
                        "❌ 티켓 정보를 불러올 수 없습니다.",
                        ephemeral=True
                    )
                    return
            
            # 관리자 권한 확인
            if not await self._check_admin_permission(interaction):
                await interaction.response.send_message(
                    "❌ 관리자만 티켓을 삭제할 수 있습니다.",
                    ephemeral=True
                )
                return

            # 확인 View 생성
            confirm_view = TicketDeleteConfirmView(
                bot=self.bot,
                guild_id=self.guild_id,
                ticket_number=self.ticket_number,
                user_id=self.user_id,
                original_message=interaction.message
            )

            embed = discord.Embed(
                title="⚠️ 티켓 삭제 확인",
                description=(
                    f"**티켓:** `{self.ticket_number}`\n\n"
                    "정말로 이 티켓을 삭제하시겠습니까?\n"
                    "⚠️ **이 작업은 되돌릴 수 없습니다.**\n\n"
                    "• 티켓 메시지가 삭제됩니다\n"
                    "• 답변 쓰레드가 삭제됩니다\n"
                    "• DB에서 상태가 'closed'로 변경됩니다"
                ),
                color=discord.Color.red()
            )

            await interaction.response.send_message(
                embed=embed,
                view=confirm_view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 티켓 삭제 확인 오류: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ 티켓 삭제 확인 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

    async def _check_admin_permission(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인"""
        # 서버 관리자 권한 확인
        if interaction.user.guild_permissions.administrator:
            return True
        
        # DB에 등록된 관리자 확인
        guild_id = str(interaction.guild_id)
        admins = await self.bot.db_manager.get_server_admins(guild_id)
        
        for admin in admins:
            if str(interaction.user.id) == admin['user_id'] and admin['is_active']:
                return True
        
        return False

class TicketDeleteConfirmView(discord.ui.View):
    """티켓 삭제 확인 View"""
    
    def __init__(self, bot, guild_id: str, ticket_number: str, user_id: str, original_message):
        super().__init__(timeout=60)  # 60초 타임아웃
        self.bot = bot
        self.guild_id = guild_id
        self.ticket_number = ticket_number
        self.user_id = user_id
        self.original_message = original_message

    @discord.ui.button(
        label="삭제 확인",
        style=discord.ButtonStyle.danger,
        emoji="✅"
    )
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """삭제 확인"""
        try:
            await interaction.response.defer(ephemeral=True)

            # DB 상태 업데이트
            await self.bot.db_manager.update_inquiry_status(
                self.guild_id,
                self.ticket_number,
                'closed',
                str(interaction.user.id)
            )

            # 로그 기록
            await self.bot.db_manager.add_inquiry_log(
                self.guild_id,
                self.ticket_number,
                str(interaction.user.id),
                interaction.user.display_name,
                'deleted',
                '티켓 삭제됨'
            )

            # 쓰레드 삭제 시도
            if self.original_message.thread:
                try:
                    await self.original_message.thread.delete()
                    logger.info(f"🗑️ 쓰레드 삭제: {self.original_message.thread.id}")
                except Exception as e:
                    logger.error(f"⚠️ 쓰레드 삭제 실패: {e}")

            # 원본 메시지 삭제
            try:
                await self.original_message.delete()
                logger.info(f"🗑️ 티켓 메시지 삭제: {self.ticket_number}")
            except Exception as e:
                logger.error(f"⚠️ 메시지 삭제 실패: {e}")

            # 사용자에게 알림 (선택적)
            try:
                user = await self.bot.fetch_user(int(self.user_id))
                
                notification_embed = discord.Embed(
                    title="🗑️ 문의 티켓 삭제됨",
                    description=(
                        f"**티켓:** `{self.ticket_number}`\n\n"
                        "관리팀에 의해 티켓이 삭제되었습니다.\n"
                        "추가 문의사항이 있으시면 `/문의하기`를 이용해주세요."
                    ),
                    color=discord.Color.red()
                )
                notification_embed.timestamp = discord.utils.utcnow()
                
                await user.send(embed=notification_embed)
            except:
                pass  # DM 전송 실패는 무시

            await interaction.followup.send(
                f"✅ 티켓 `{self.ticket_number}`이(가) 삭제되었습니다.",
                ephemeral=True
            )

            # 확인 메시지도 삭제
            try:
                await interaction.message.delete()
            except:
                pass

            logger.info(f"🗑️ 티켓 삭제 완료: {self.ticket_number} by {interaction.user.name}")

        except Exception as e:
            logger.error(f"❌ 티켓 삭제 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 티켓 삭제 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

    @discord.ui.button(
        label="취소",
        style=discord.ButtonStyle.secondary,
        emoji="❌"
    )
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """삭제 취소"""
        try:
            await interaction.response.send_message(
                "✅ 티켓 삭제가 취소되었습니다.",
                ephemeral=True
            )
            
            # 확인 메시지 삭제
            await interaction.message.delete()
            
        except Exception as e:
            logger.error(f"❌ 취소 처리 오류: {e}")

    async def on_timeout(self):
        """타임아웃 처리"""
        try:
            for item in self.children:
                item.disabled = True
            
            # 메시지가 아직 존재하면 업데이트
            # (이미 삭제되었을 수도 있음)
        except:
            pass

class InquiryTypeSelectView(discord.ui.View):
    """문의 방식 선택 View (관리팀 문의 vs 1:1 상담)"""
    
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
    
    @discord.ui.button(
        label="관리팀 문의",
        style=discord.ButtonStyle.primary,
        emoji="📋",
        custom_id="team_inquiry"
    )
    async def team_inquiry_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """관리팀 문의 버튼"""
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            
            # 일일 제한 체크
            today_count = await self.bot.db_manager.get_user_daily_inquiry_count(
                guild_id,
                user_id
            )
            
            settings = await self.bot.db_manager.get_inquiry_settings(guild_id)
            daily_limit = settings.get('daily_limit', 3)
            
            if today_count >= daily_limit:
                await interaction.response.send_message(
                    f"❌ **일일 문의 제한에 도달했습니다.**\n"
                    f"📊 오늘 작성한 문의: **{today_count}/{daily_limit}건**\n"
                    f"⏰ 내일 00시에 초기화됩니다.",
                    ephemeral=True
                )
                return
            
            inquiry_system = self.bot.get_cog('InquirySystem')
            if not inquiry_system:
                await interaction.response.send_message(
                    "❌ 문의 시스템을 불러올 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 옵션 선택 View 표시
            options_view = InquiryOptionsView(
                bot=self.bot,
                inquiry_system=inquiry_system
            )
            
            embed = discord.Embed(
                title="📋 관리팀 문의 작성",
                description=(
                    "**1단계: 옵션 선택**\n\n"
                    "**📂 카테고리**\n"
                    "드롭다운에서 문의 유형을 선택하세요.\n\n"
                    "**🎭 익명 여부**\n"
                    "익명으로 작성하려면 버튼을 클릭하세요.\n"
                    "(`익명 작성: ON` 상태가 되면 익명으로 작성됩니다)\n\n"
                    "선택 완료 후 **다음** 버튼을 눌러주세요."
                ),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"오늘 작성한 문의: {today_count}/{daily_limit}건")
            
            await interaction.response.edit_message(
                embed=embed,
                view=options_view
            )
            
        except Exception as e:
            logger.error(f"❌ 관리팀 문의 버튼 오류: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ 문의 작성 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass
        
    @discord.ui.button(
        label="1:1 개인 상담",
        style=discord.ButtonStyle.secondary,
        emoji="💬",
        custom_id="private_consultation"
    )
    async def private_consultation_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """1:1 상담 버튼"""
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            
            # 🆕 옵션 선택 View 표시
            options_view = ConsultationOptionsView(
                bot=self.bot,
                guild=interaction.guild
            )
            
            embed = discord.Embed(
                title="💬 1:1 상담 신청",
                description=(
                    "**관리자와 1:1로 상담하실 수 있습니다.**\n\n"
                    "**1단계: 옵션 선택**\n\n"
                    "**👤 관리자 선택**\n"
                    "상담받을 관리자를 선택하세요.\n\n"
                    "**📂 카테고리**\n"
                    "상담 유형을 선택하세요.\n\n"
                    "**🚨 긴급 여부**\n"
                    "긴급한 경우 버튼을 클릭하세요.\n\n"
                    "선택 완료 후 **다음** 버튼을 눌러주세요."
                ),
                color=discord.Color.blue()
            )
            embed.set_footer(text="1:1 상담은 실명으로만 진행됩니다")
            
            await interaction.response.edit_message(
                embed=embed,
                view=options_view
            )
            
        except Exception as e:
            logger.error(f"❌ 1:1 상담 버튼 오류: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ 상담 신청 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass


class InquirySystem(commands.Cog):
    """문의 시스템 - 관리팀 문의 & 1:1 상담"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("📋 문의 시스템이 로드되었습니다.")

    @app_commands.command(name="상담강제종료", description="[관리자] 진행 중인 상담을 강제로 종료합니다")
    @app_commands.describe(
        티켓번호="종료할 상담의 티켓 번호 (예: #0006)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def force_end_consultation(
        self,
        interaction: discord.Interaction,
        티켓번호: str
    ):
        """관리자가 상담을 강제 종료"""
        try:
            guild_id = str(interaction.guild_id)
            
            # 티켓 번호 정규화 (# 제거)
            ticket_number = 티켓번호.strip()
            if not ticket_number.startswith('#'):
                ticket_number = f"#{ticket_number}"
            
            # 상담 조회
            consultation = await self.bot.db_manager.get_consultation_by_ticket(
                guild_id,
                ticket_number
            )
            
            if not consultation:
                await interaction.response.send_message(
                    f"❌ 티켓 `{ticket_number}`을(를) 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 이미 완료된 상담
            if consultation['status'] == 'completed':
                await interaction.response.send_message(
                    f"ℹ️ 티켓 `{ticket_number}`은(는) 이미 완료된 상담입니다.",
                    ephemeral=True
                )
                return
            
            # 상태 업데이트
            await self.bot.db_manager.update_consultation_status(
                guild_id,
                ticket_number,
                'completed',
                str(interaction.user.id)
            )
            
            # 사용자에게 알림 (선택사항)
            try:
                user = await self.bot.fetch_user(int(consultation['user_id']))
                
                notice_embed = discord.Embed(
                    title="⚠️ 상담 강제 종료",
                    description=(
                        f"관리자에 의해 상담이 종료되었습니다.\n\n"
                        f"🎫 티켓: `{ticket_number}`\n"
                        f"👤 담당 관리자: {consultation['admin_name']}\n\n"
                        f"추가 상담이 필요하시면 `/문의하기`를 이용해주세요."
                    ),
                    color=discord.Color.orange()
                )
                notice_embed.set_footer(text=f"종료 처리: {interaction.user.display_name}")
                
                await user.send(embed=notice_embed)
                
            except discord.Forbidden:
                logger.warning(f"⚠️ 사용자 DM 전송 실패 (DM 비활성화)")
            except Exception as e:
                logger.error(f"❌ 사용자 알림 실패: {e}")
            
            # 관리자에게 알림 (선택사항)
            try:
                admin = await self.bot.fetch_user(int(consultation['admin_id']))
                
                notice_embed = discord.Embed(
                    title="⚠️ 상담 강제 종료",
                    description=(
                        f"{interaction.user.mention}님이 상담을 강제 종료했습니다.\n\n"
                        f"🎫 티켓: `{ticket_number}`\n"
                        f"👤 신청자: {consultation['username']}"
                    ),
                    color=discord.Color.orange()
                )
                
                await admin.send(embed=notice_embed)
                
            except:
                pass
            
            # 성공 메시지
            embed = discord.Embed(
                title="✅ 상담 강제 종료 완료",
                description=(
                    f"🎫 티켓: `{ticket_number}`\n"
                    f"👤 신청자: {consultation['username']}\n"
                    f"👤 담당 관리자: {consultation['admin_name']}\n"
                    f"📂 카테고리: {consultation['category']}\n"
                    f"📅 신청일: <t:{int(consultation['created_at'].timestamp()) if hasattr(consultation['created_at'], 'timestamp') else 0}:F>"
                ),
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"⚠️ 상담 강제 종료: {ticket_number} by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"❌ 상담 강제 종료 오류: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ 상담 종료 중 오류가 발생했습니다.",
                ephemeral=True
            )
    
    @app_commands.command(name="문의하기", description="관리자에게 문의하거나 상담을 신청합니다")
    async def inquiry(self, interaction: discord.Interaction):
        """문의하기 메인 명령어 - 방식 선택"""
        
        embed = discord.Embed(
            title="📋 문의 시스템",
            description=(
                "관리자에게 문의하거나 상담을 신청하실 수 있습니다.\n"
                "아래에서 원하시는 방식을 선택해주세요."
            ),
            color=0x5865F2,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🏢 관리팀에게 문의",
            value=(
                "• 여러 관리자가 함께 확인합니다\n"
                "• 빠른 처리가 가능합니다\n"
                "• 익명으로 작성할 수 있습니다\n"
                "• 일반적인 질문, 건의사항, 버그 제보 등"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💬 1:1 개인 상담",
            value=(
                "• 관리자 한 분과만 대화합니다\n"
                "• 민감한 내용도 안전합니다\n"
                "• 실명으로만 상담 가능합니다\n"
                "• 분쟁조정, 개인사정, 신고 등"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"{interaction.user.display_name}님의 문의")
        
        view = InquiryTypeSelectView(self.bot)
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )
        
        logger.info(f"📋 {interaction.user.name}이(가) 문의 시스템을 실행했습니다.")

    @app_commands.command(
        name="내문의",
        description="내가 작성한 문의 목록을 조회합니다"
    )
    @app_commands.describe(
        필터="조회할 문의 상태를 선택하세요"
    )
    @app_commands.choices(필터=[
        app_commands.Choice(name="전체", value="all"),
        app_commands.Choice(name="대기/진행중", value="active"),
        app_commands.Choice(name="완료", value="completed"),
        app_commands.Choice(name="닫힘", value="closed")
    ])
    async def my_inquiries(
        self,
        interaction: discord.Interaction,
        필터: app_commands.Choice[str] = None
    ):
        """내가 작성한 문의 목록 조회"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            
            # 필터 값 추출
            status_filter = 필터.value if 필터 else "all"
            
            # 문의 목록 조회
            if status_filter == "all":
                inquiries = await self.bot.db_manager.get_user_inquiries(
                    guild_id, user_id, limit=100
                )
            elif status_filter == "active":
                # 대기중 + 진행중
                pending = await self.bot.db_manager.get_user_inquiries(
                    guild_id, user_id, limit=50, status='pending'
                )
                processing = await self.bot.db_manager.get_user_inquiries(
                    guild_id, user_id, limit=50, status='processing'
                )
                inquiries = pending + processing
                # 생성 시간순 정렬
                inquiries.sort(key=lambda x: x['created_at'], reverse=True)
            else:
                inquiries = await self.bot.db_manager.get_user_inquiries(
                    guild_id, user_id, limit=100, status=status_filter
                )
            
            # 상담 목록도 조회 (1:1 상담)
            if status_filter == "all":
                consultations = await self.bot.db_manager.get_user_consultations(
                    guild_id, user_id, limit=100
                )
            elif status_filter == "active":
                pending_consult = await self.bot.db_manager.get_user_consultations(
                    guild_id, user_id, limit=50, status='pending'
                )
                accepted_consult = await self.bot.db_manager.get_user_consultations(
                    guild_id, user_id, limit=50, status='accepted'
                )
                consultations = pending_consult + accepted_consult
                consultations.sort(key=lambda x: x['created_at'], reverse=True)
            elif status_filter == "completed":
                consultations = await self.bot.db_manager.get_user_consultations(
                    guild_id, user_id, limit=100, status='completed'
                )
            else:
                consultations = []
            
            # 문의가 없는 경우
            if not inquiries and not consultations:
                filter_text = {
                    "all": "전체",
                    "active": "진행중인",
                    "completed": "완료된",
                    "closed": "닫힌"
                }.get(status_filter, "전체")
                
                await interaction.followup.send(
                    f"📋 **{filter_text} 문의 내역이 없습니다.**\n\n"
                    "`/문의하기` 명령어로 새 문의를 작성할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            # 페이지네이션 View 생성
            pagination_view = MyInquiriesPaginationView(
                bot=self.bot,
                user=interaction.user,
                inquiries=inquiries,
                consultations=consultations,
                status_filter=status_filter
            )
            
            # 첫 페이지 임베드 생성
            embed = await pagination_view.create_page_embed()
            
            await interaction.followup.send(
                embed=embed,
                view=pagination_view,
                ephemeral=True
            )
            
            logger.info(f"📋 내문의 조회: {interaction.user.name} (필터: {status_filter})")
            
        except Exception as e:
            logger.error(f"❌ 내문의 조회 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 문의 목록 조회 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass
    
    @app_commands.command(name="문의채널설정", description="[관리자] 관리팀 문의가 올라갈 채널을 설정합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def set_inquiry_channel(
        self,
        interaction: discord.Interaction,
        채널: discord.TextChannel
    ):
        """문의 채널 설정"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # 봇 권한 체크 및 자동 추가
            bot_member = interaction.guild.me
            channel_perms = 채널.permissions_for(bot_member)
            
            # 필요한 권한 목록
            required_perms = {
                'view_channel': '채널 보기',
                'send_messages': '메시지 보내기',
                'embed_links': '링크 첨부',
                'attach_files': '파일 첨부',
                'read_message_history': '메시지 기록 보기',
                'create_public_threads': '공개 스레드 만들기',
                'send_messages_in_threads': '스레드에서 메시지 보내기',
                'manage_threads': '스레드 관리하기'
            }
            
            missing_perms = []
            for perm, perm_name in required_perms.items():
                if not getattr(channel_perms, perm, False):
                    missing_perms.append(perm_name)
            
            # 권한이 부족하면 자동으로 추가 시도
            if missing_perms:
                try:
                    # 봇에게 필요한 권한 부여
                    await 채널.set_permissions(
                        bot_member,
                        view_channel=True,
                        send_messages=True,
                        embed_links=True,
                        attach_files=True,
                        read_message_history=True,
                        create_public_threads=True,
                        send_messages_in_threads=True,
                        manage_threads=True,
                        reason="문의 시스템 채널 설정 - 봇 권한 자동 추가"
                    )
                    
                    logger.info(f"✅ 봇 권한 자동 추가: {채널.name}")
                    
                except discord.Forbidden:
                    # 권한 추가 실패 (관리자 권한 부족)
                    await interaction.followup.send(
                        f"❌ **봇 권한 추가 실패**\n\n"
                        f"**문제:** {채널.mention}에 봇 권한을 추가할 수 없습니다.\n\n"
                        f"**부족한 권한:**\n" + "\n".join(f"• {p}" for p in missing_perms) + "\n\n"
                        f"**해결 방법:**\n"
                        f"1. {채널.mention} 채널 설정으로 이동\n"
                        f"2. 권한 → 멤버 추가 → **{bot_member.mention}** 선택\n"
                        f"3. 다음 권한 활성화:\n"
                        f"   • 채널 보기\n"
                        f"   • 메시지 보내기\n"
                        f"   • 링크 첨부\n"
                        f"   • 스레드 만들기\n"
                        f"   • 스레드에서 메시지 보내기\n\n"
                        f"권한 추가 후 다시 `/문의채널설정`을 실행해주세요.",
                        ephemeral=True
                    )
                    return
            
            # @everyone 권한 체크 (공개 채널 경고)
            channel_permissions = 채널.permissions_for(interaction.guild.default_role)
            
            if channel_permissions.view_channel or channel_permissions.read_messages:
                # 경고 표시
                warning_embed = discord.Embed(
                    title="⚠️ 보안 경고",
                    description=(
                        f"**{채널.mention}은(는) 일반 멤버가 볼 수 있는 채널입니다!**\n\n"
                        "**문제점:**\n"
                        "• 문의 티켓이 모든 멤버에게 공개됩니다\n"
                        "• 비공개 쓰레드도 모든 멤버가 볼 수 있습니다\n"
                        "• **익명성이 보장되지 않습니다**\n\n"
                        "**권장 설정:**\n"
                        "1. 관리자 전용 채널을 만드세요\n"
                        "2. 채널 권한 → @everyone → 채널 보기 OFF\n"
                        "3. 채널 권한 → 관리자 역할 → 채널 보기 ON\n"
                        f"4. 채널 권한 → {bot_member.mention} → 채널 보기 ON ✅ (자동 추가됨)\n\n"
                        "그래도 이 채널로 설정하시겠습니까?"
                    ),
                    color=discord.Color.red()
                )
                
                confirm_view = discord.ui.View(timeout=60)
                
                async def confirm_callback(confirm_interaction: discord.Interaction):
                    if confirm_interaction.user.id != interaction.user.id:
                        return
                    
                    await self.bot.db_manager.set_inquiry_channel(
                        str(interaction.guild_id),
                        str(채널.id)
                    )
                    
                    await confirm_interaction.response.edit_message(
                        content=f"⚠️ {채널.mention}을(를) 문의 채널로 설정했습니다.\n"
                                f"**주의:** 모든 멤버에게 공개되는 채널입니다!\n"
                                f"✅ 봇 권한은 자동으로 추가되었습니다.",
                        embed=None,
                        view=None
                    )
                
                async def cancel_callback(cancel_interaction: discord.Interaction):
                    if cancel_interaction.user.id != interaction.user.id:
                        return
                    await cancel_interaction.response.edit_message(
                        content="❌ 채널 설정이 취소되었습니다.\n"
                                "관리자 전용 채널을 만든 후 다시 설정해주세요.",
                        embed=None,
                        view=None
                    )
                
                confirm_btn = discord.ui.Button(label="그래도 설정", style=discord.ButtonStyle.danger)
                cancel_btn = discord.ui.Button(label="취소", style=discord.ButtonStyle.secondary)
                
                confirm_btn.callback = confirm_callback
                cancel_btn.callback = cancel_callback
                
                confirm_view.add_item(confirm_btn)
                confirm_view.add_item(cancel_btn)
                
                await interaction.followup.send(
                    embed=warning_embed,
                    view=confirm_view,
                    ephemeral=True
                )
                return
            
            # 권한이 올바른 경우 바로 설정
            await self.bot.db_manager.set_inquiry_channel(
                str(interaction.guild_id),
                str(채널.id)
            )
            
            success_embed = discord.Embed(
                title="✅ 문의 채널 설정 완료",
                description=(
                    f"**채널:** {채널.mention}\n"
                    f"**권한:** 🔒 관리자 전용 (올바른 설정)\n"
                    f"**봇 권한:** ✅ 자동으로 추가되었습니다\n\n"
                    "이제 `/문의하기` 명령어로 작성된 문의가 이 채널에 올라갑니다."
                ),
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
            logger.info(f"✅ 문의 채널 설정: {채널.name} (봇 권한 자동 추가)")
            
        except discord.Forbidden as e:
            logger.error(f"❌ 권한 오류: {e}")
            await interaction.followup.send(
                "❌ 봇에게 필요한 권한이 없습니다.\n"
                "서버 설정에서 봇 역할에 **관리자** 권한을 부여하거나,\n"
                "해당 채널에서 봇이 메시지를 보낼 수 있도록 권한을 추가해주세요.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"❌ 문의 채널 설정 오류: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ 채널 설정 중 오류가 발생했습니다.",
                ephemeral=True
            )
    
    @app_commands.command(name="문의설정확인", description="[관리자] 현재 문의 시스템 설정을 확인합니다")
    @app_commands.checks.has_permissions(administrator=True)
    async def check_inquiry_settings(self, interaction: discord.Interaction):
        """문의 시스템 설정 확인"""
        
        guild_id = str(interaction.guild_id)
        
        settings = await self.bot.db_manager.get_inquiry_settings(guild_id)
        stats = await self.bot.db_manager.get_inquiry_stats(guild_id)
        
        # 상담 통계 추가
        consultation_stats = await self.bot.db_manager.get_consultation_stats(guild_id)
        
        embed = discord.Embed(
            title="⚙️ 문의 시스템 설정 현황",
            description=f"**{interaction.guild.name}** 서버의 문의 시스템 설정",
            color=0x5865F2,
            timestamp=datetime.now()
        )
        
        # 문의 채널 정보
        channel_id = settings.get('team_inquiry_channel_id')
        if channel_id:
            channel = interaction.guild.get_channel(int(channel_id))
            channel_info = f"✅ {channel.mention}" if channel else "❌ 채널을 찾을 수 없음"
        else:
            channel_info = "❌ 채널 미설정\n`/문의채널설정` 명령어로 설정하세요."
        
        embed.add_field(
            name="📋 관리팀 문의",
            value=channel_info,
            inline=False
        )
        
        # 설정 정보
        embed.add_field(
            name="⚙️ 설정",
            value=(
                f"• 일일 문의 제한: {settings.get('daily_limit', 3)}건\n"
                f"• 익명 문의: {'✅ 허용' if settings.get('enable_anonymous', True) else '❌ 비허용'}\n"
                f"• 1:1 상담: {'✅ 활성화' if settings.get('enable_private_inquiry', True) else '❌ 비활성화'}"
            ),
            inline=False
        )
        
        # 통계
        embed.add_field(
            name="📊 문의 통계",
            value=(
                f"• 총 문의: **{stats.get('total', 0)}**건\n"
                f"• 🕐 대기중: {stats.get('pending', 0)}건\n"
                f"• 🔄 진행중: {stats.get('processing', 0)}건\n"
                f"• ✅ 완료: {stats.get('completed', 0)}건"
            ),
            inline=True
        )
        
        # 상담 통계
        embed.add_field(
            name="💬 상담 통계",
            value=(
                f"• 총 상담: **{consultation_stats.get('total', 0)}**건\n"
                f"• 🕐 대기: {consultation_stats.get('pending', 0)}건\n"
                f"• ✅ 수락: {consultation_stats.get('accepted', 0)}건\n"
                f"• ❌ 거절: {consultation_stats.get('rejected', 0)}건"
            ),
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _create_ticket_embed(
        self,
        interaction: discord.Interaction,
        ticket_number: str,
        title: str,
        category: str,
        content: str,
        is_anonymous: bool
    ) -> discord.Embed:
        """티켓 임베드 생성"""
        
        # 카테고리 이모지
        category_emoji = {
            '일반': '📋',
            '건의': '💡',
            '버그': '🐛',
            '계정': '👤',
            '기타': '📝'
        }
        
        # 색상
        category_color = {
            '일반': 0x5865F2,
            '건의': 0xFEE75C,
            '버그': 0xED4245,
            '계정': 0x57F287,
            '기타': 0x99AAB5
        }
        
        embed = discord.Embed(
            title=f"🎫 티켓 {ticket_number}",
            description=f"**{title}**",
            color=category_color.get(category, 0x5865F2),
            timestamp=datetime.now()
        )
        
        # 작성자 정보
        if is_anonymous:
            embed.add_field(
                name="👤 작성자",
                value="🎭 익명 (작성자 확인 버튼으로 확인 가능)",
                inline=True
            )
        else:
            embed.add_field(
                name="👤 작성자",
                value=f"{interaction.user.mention}\n({interaction.user.name})",
                inline=True
            )
        
        # 카테고리
        emoji = category_emoji.get(category, '📝')
        embed.add_field(
            name="📂 카테고리",
            value=f"{emoji} {category}",
            inline=True
        )
        
        # 상태
        embed.add_field(
            name="📊 상태",
            value="🕐 대기중",
            inline=True
        )
        
        # 문의 내용
        embed.add_field(
            name="📝 문의 내용",
            value=content[:1000] + ("..." if len(content) > 1000 else ""),
            inline=False
        )
        
        # 푸터
        embed.set_footer(
            text=f"작성 시간",
            icon_url=interaction.user.display_avatar.url if not is_anonymous else None
        )
        
        return embed

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        """쓰레드 생성 시 자동 알림"""
        try:
            # 티켓 답변 쓰레드인지 확인
            if not thread.name.startswith("📋"):
                return
            
            # 부모 메시지 가져오기
            if not thread.parent:
                return
            
            try:
                parent_message = await thread.parent.fetch_message(thread.id)
            except:
                return
            
            # 임베드에서 티켓 정보 추출
            if not parent_message.embeds:
                return
            
            embed = parent_message.embeds[0]
            
            # 티켓 번호 추출
            ticket_number = None
            for field in embed.fields:
                if field.name == "🎫 티켓 번호":
                    ticket_number = field.value.strip("`")
                    break
            
            if not ticket_number:
                return
            
            logger.info(f"🔔 쓰레드 생성 감지: {thread.name} (티켓: {ticket_number})")
            
        except Exception as e:
            logger.error(f"❌ 쓰레드 생성 이벤트 처리 오류: {e}", exc_info=True)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """쓰레드 내 메시지 알림 (답변 알림)"""
        try:
            # 봇 메시지는 무시
            if message.author.bot:
                return
            
            # 쓰레드가 아니면 무시
            if not isinstance(message.channel, discord.Thread):
                return
            
            thread = message.channel
            
            # 티켓 답변 쓰레드인지 확인
            if not thread.name.startswith("📋"):
                return
            
            # 티켓 번호 추출
            parts = thread.name.split()
            if len(parts) < 2:
                return
            
            ticket_number = parts[1]
            guild_id = str(message.guild.id)
            
            # 티켓 정보 조회
            inquiry = await self.bot.db_manager.get_inquiry_by_ticket(guild_id, ticket_number)
            
            if not inquiry:
                return
            
            # 작성자에게 DM 알림
            try:
                user = await self.bot.fetch_user(int(inquiry['user_id']))
                
                notification_embed = discord.Embed(
                    title="💬 새 답변이 도착했습니다",
                    description=(
                        f"**티켓:** `{ticket_number}`\n"
                        f"**카테고리:** `{inquiry['category']}`\n\n"
                        f"**답변 내용 미리보기:**\n"
                        f"{message.content[:200]}{'...' if len(message.content) > 200 else ''}"
                    ),
                    color=discord.Color.blue()
                )
                notification_embed.add_field(
                    name="👤 답변자",
                    value=message.author.display_name,
                    inline=True
                )
                notification_embed.add_field(
                    name="📍 위치",
                    value=f"[답변 보러가기]({message.jump_url})",
                    inline=True
                )
                notification_embed.timestamp = discord.utils.utcnow()
                
                await user.send(embed=notification_embed)
                
                logger.info(f"🔔 답변 알림 전송: {ticket_number} → {user.name}")
                
            except discord.Forbidden:
                logger.warning(f"⚠️ 사용자 {inquiry['user_id']} DM 전송 실패")
            except Exception as e:
                logger.error(f"❌ 답변 알림 전송 실패: {e}")
            
        except Exception as e:
            logger.error(f"❌ 메시지 이벤트 처리 오류: {e}", exc_info=True)

class MyInquiriesPaginationView(discord.ui.View):
    """내문의 페이지네이션 View"""
    
    def __init__(
        self,
        bot,
        user: discord.User,
        inquiries: List[dict],
        consultations: List[dict],
        status_filter: str
    ):
        super().__init__(timeout=180)  # 3분 타임아웃
        self.bot = bot
        self.user = user
        self.inquiries = inquiries
        self.consultations = consultations
        self.status_filter = status_filter
        
        # 통합 리스트 생성 (시간순 정렬)
        self.all_items = []
        
        for inquiry in inquiries:
            self.all_items.append({
                'type': 'inquiry',
                'data': inquiry,
                'created_at': inquiry['created_at']
            })
        
        for consultation in consultations:
            self.all_items.append({
                'type': 'consultation',
                'data': consultation,
                'created_at': consultation['created_at']
            })
        
        # 시간순 정렬
        self.all_items.sort(key=lambda x: x['created_at'], reverse=True)
        
        # 페이지 설정
        self.items_per_page = 5
        self.current_page = 0
        self.total_pages = (len(self.all_items) - 1) // self.items_per_page + 1
        
        # 버튼 상태 업데이트
        self._update_buttons()
    
    def _update_buttons(self):
        """버튼 활성화/비활성화"""
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.total_pages - 1)
    
    async def create_page_embed(self) -> discord.Embed:
        """현재 페이지의 임베드 생성"""
        
        # 필터 이름
        filter_names = {
            "all": "전체",
            "active": "진행중",
            "completed": "완료",
            "closed": "닫힌"
        }
        filter_name = filter_names.get(self.status_filter, "전체")
        
        embed = discord.Embed(
            title=f"📋 내 문의 내역 ({filter_name})",
            description=f"총 **{len(self.all_items)}건**의 문의가 있습니다.",
            color=discord.Color.blue()
        )
        
        # 현재 페이지 아이템
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = self.all_items[start_idx:end_idx]
        
        if not page_items:
            embed.add_field(
                name="📭 문의 내역 없음",
                value="조회된 문의가 없습니다.",
                inline=False
            )
        else:
            for item in page_items:
                if item['type'] == 'inquiry':
                    # 관리팀 문의
                    inquiry = item['data']
                    
                    # 상태 이모지
                    status_emoji = {
                        'pending': '⏳',
                        'processing': '🔄',
                        'completed': '✅',
                        'closed': '🔒'
                    }.get(inquiry['status'], '❓')
                    
                    # 카테고리 이모지
                    category_emoji = {
                        '일반': '📋',
                        '건의': '💡',
                        '버그': '🐛',
                        '계정': '👤',
                        '기타': '📝'
                    }.get(inquiry['category'], '📝')
                    
                    try:
                        created_dt = datetime.fromisoformat(inquiry['created_at'].replace('Z', '+00:00'))
                        timestamp = int(created_dt.timestamp())
                    except:
                        timestamp = int(datetime.now(timezone.utc).timestamp())
            
                    field_name = f"{status_emoji} {inquiry['ticket_number']} - {inquiry['title'][:30]}"
                    field_value = (
                        f"{category_emoji} **{inquiry['category']}** | "
                        f"🔒 {'익명' if inquiry['is_anonymous'] else '실명'}\n"
                        f"📅 <t:{timestamp}:R>"
                    )
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=False
                    )
                    
                elif item['type'] == 'consultation':
                    # 1:1 상담
                    consultation = item['data']
                    
                    # 상태 이모지
                    status_emoji = {
                        'pending': '⏳',
                        'accepted': '🔄',
                        'rejected': '❌',
                        'completed': '✅'
                    }.get(consultation['status'], '❓')
                    
                    try:
                        created_dt = datetime.fromisoformat(consultation['created_at'].replace('Z', '+00:00'))
                        timestamp = int(created_dt.timestamp())
                    except:
                        timestamp = int(datetime.now(timezone.utc).timestamp())

                    field_name = f"{status_emoji} {consultation['ticket_number']} - 1:1 상담"
                    field_value = (
                        f"📂 **{consultation['category']}** | "
                        f"👤 {consultation['admin_name']}\n"
                        f"🚨 {'긴급' if consultation['is_urgent'] else '일반'} | "
                        f"📅 <t:{timestamp}:R>"
                    )
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=False
                    )
        
        # 페이지 정보
        embed.set_footer(
            text=f"페이지 {self.current_page + 1}/{self.total_pages} | {self.user.display_name}",
            icon_url=self.user.display_avatar.url
        )
        embed.timestamp = discord.utils.utcnow()
        
        return embed
    
    @discord.ui.button(
        label="◀ 이전",
        style=discord.ButtonStyle.secondary,
        custom_id="prev_page"
    )
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """이전 페이지"""
        try:
            # 권한 확인
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    "❌ 본인의 문의 목록만 조작할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            self.current_page -= 1
            self._update_buttons()
            
            embed = await self.create_page_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"❌ 페이지 이동 오류: {e}")
    
    @discord.ui.button(
        label="▶ 다음",
        style=discord.ButtonStyle.secondary,
        custom_id="next_page"
    )
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """다음 페이지"""
        try:
            # 권한 확인
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    "❌ 본인의 문의 목록만 조작할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            self.current_page += 1
            self._update_buttons()
            
            embed = await self.create_page_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"❌ 페이지 이동 오류: {e}")
    
    @discord.ui.button(
        label="🔍 상세보기",
        style=discord.ButtonStyle.primary,
        custom_id="view_detail",
        row=1
    )
    async def detail_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """상세보기 - 티켓 번호 입력 모달"""
        try:
            # 권한 확인
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    "❌ 본인의 문의 목록만 조작할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            # 티켓 번호 입력 모달
            modal = InquiryDetailModal(self.bot, self.user)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"❌ 상세보기 버튼 오류: {e}")
    
    @discord.ui.button(
        label="🔄 새로고침",
        style=discord.ButtonStyle.secondary,
        custom_id="refresh",
        row=1
    )
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """목록 새로고침"""
        try:
            # 권한 확인
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    "❌ 본인의 문의 목록만 조작할 수 있습니다.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # 데이터 재조회
            guild_id = str(interaction.guild_id)
            user_id = str(self.user.id)
            
            if self.status_filter == "all":
                self.inquiries = await self.bot.db_manager.get_user_inquiries(
                    guild_id, user_id, limit=100
                )
                self.consultations = await self.bot.db_manager.get_user_consultations(
                    guild_id, user_id, limit=100
                )
            elif self.status_filter == "active":
                pending = await self.bot.db_manager.get_user_inquiries(
                    guild_id, user_id, limit=50, status='pending'
                )
                processing = await self.bot.db_manager.get_user_inquiries(
                    guild_id, user_id, limit=50, status='processing'
                )
                self.inquiries = pending + processing
                
                pending_consult = await self.bot.db_manager.get_user_consultations(
                    guild_id, user_id, limit=50, status='pending'
                )
                accepted_consult = await self.bot.db_manager.get_user_consultations(
                    guild_id, user_id, limit=50, status='accepted'
                )
                self.consultations = pending_consult + accepted_consult
            else:
                self.inquiries = await self.bot.db_manager.get_user_inquiries(
                    guild_id, user_id, limit=100, status=self.status_filter
                )
                if self.status_filter == "completed":
                    self.consultations = await self.bot.db_manager.get_user_consultations(
                        guild_id, user_id, limit=100, status='completed'
                    )
                else:
                    self.consultations = []
            
            # 통합 리스트 재생성
            self.all_items = []
            for inquiry in self.inquiries:
                self.all_items.append({
                    'type': 'inquiry',
                    'data': inquiry,
                    'created_at': inquiry['created_at']
                })
            for consultation in self.consultations:
                self.all_items.append({
                    'type': 'consultation',
                    'data': consultation,
                    'created_at': consultation['created_at']
                })
            self.all_items.sort(key=lambda x: x['created_at'], reverse=True)
            
            # 페이지 재계산
            self.total_pages = (len(self.all_items) - 1) // self.items_per_page + 1
            if self.current_page >= self.total_pages:
                self.current_page = max(0, self.total_pages - 1)
            
            self._update_buttons()
            
            embed = await self.create_page_embed()
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"❌ 새로고침 오류: {e}", exc_info=True)
    
    async def on_timeout(self):
        """타임아웃 시 버튼 비활성화"""
        for item in self.children:
            item.disabled = True

class InquiryDetailModal(discord.ui.Modal, title="문의 상세보기"):
    """문의 상세보기 모달"""
    
    def __init__(self, bot, user: discord.User):
        super().__init__()
        self.bot = bot
        self.user = user
        
        self.ticket_input = discord.ui.TextInput(
            label="티켓 번호",
            placeholder="#0001 형식으로 입력해주세요",
            required=True,
            max_length=10
        )
        self.add_item(self.ticket_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """티켓 상세 조회"""
        try:
            ticket_number = self.ticket_input.value.strip()
            
            # # 자동 추가
            if not ticket_number.startswith('#'):
                ticket_number = f"#{ticket_number}"
            
            guild_id = str(interaction.guild_id)
            user_id = str(self.user.id)
            
            await interaction.response.defer(ephemeral=True)
            
            # 관리팀 문의 조회
            inquiry = await self.bot.db_manager.get_inquiry_by_ticket(guild_id, ticket_number)
            
            # 1:1 상담 조회
            consultation = await self.bot.db_manager.get_consultation_by_ticket(guild_id, ticket_number)
            
            # 둘 다 없으면
            if not inquiry and not consultation:
                await interaction.followup.send(
                    f"❌ 티켓 `{ticket_number}`을(를) 찾을 수 없습니다.\n"
                    "티켓 번호를 다시 확인해주세요.",
                    ephemeral=True
                )
                return
            
            # 관리팀 문의 상세
            if inquiry:
                # 본인 문의인지 확인
                if inquiry['user_id'] != user_id:
                    await interaction.followup.send(
                        "❌ 본인의 문의만 조회할 수 있습니다.",
                        ephemeral=True
                    )
                    return
                
                # 상태 텍스트
                status_text = {
                    'pending': '⏳ 대기 중',
                    'processing': '🔄 답변 진행 중',
                    'completed': '✅ 처리 완료',
                    'closed': '🔒 닫힘'
                }.get(inquiry['status'], '❓ 알 수 없음')
                
                embed = discord.Embed(
                    title=f"📋 {inquiry['title']}",
                    description=inquiry['content'],
                    color=discord.Color.green() if inquiry['status'] == 'completed' else discord.Color.blue()
                )
                
                embed.add_field(
                    name="🎫 티켓 번호",
                    value=f"`{ticket_number}`",
                    inline=True
                )
                embed.add_field(
                    name="📂 카테고리",
                    value=inquiry['category'],
                    inline=True
                )
                embed.add_field(
                    name="📊 상태",
                    value=status_text,
                    inline=True
                )
                embed.add_field(
                    name="🔒 익명 여부",
                    value="익명" if inquiry['is_anonymous'] else "실명",
                    inline=True
                )
                try:
                    created_dt = datetime.fromisoformat(inquiry['created_at'].replace('Z', '+00:00'))
                    created_timestamp = int(created_dt.timestamp())
                except:
                    created_timestamp = int(datetime.now(timezone.utc).timestamp())
    
                embed.add_field(
                    name="📅 작성일",
                    value=f"<t:{created_timestamp}:F>",
                    inline=True
                )
                
                if inquiry.get('resolved_at'):
                    try:
                        resolved_dt = datetime.fromisoformat(inquiry['resolved_at'].replace('Z', '+00:00'))
                        resolved_timestamp = int(resolved_dt.timestamp())
                        
                        embed.add_field(
                            name="✅ 완료일",
                            value=f"<t:{resolved_timestamp}:F>",
                            inline=True
                        )
                    except:
                        pass
                
                embed.set_footer(text=f"관리팀 문의 | ID: {inquiry['id']}")
                embed.timestamp = discord.utils.utcnow()
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 1:1 상담 상세
            elif consultation:
                # 본인 상담인지 확인
                if consultation['user_id'] != user_id:
                    await interaction.followup.send(
                        "❌ 본인의 상담만 조회할 수 있습니다.",
                        ephemeral=True
                    )
                    return
                
                # 상태 텍스트
                status_text = {
                    'pending': '⏳ 대기 중',
                    'accepted': '🔄 상담 진행 중',
                    'rejected': '❌ 거절됨',
                    'completed': '✅ 상담 완료'
                }.get(consultation['status'], '❓ 알 수 없음')
                
                embed = discord.Embed(
                    title=f"💬 1:1 상담 - {consultation['category']}",
                    description=consultation['content'],
                    color=discord.Color.green() if consultation['status'] == 'completed' else discord.Color.blue()
                )
                
                embed.add_field(
                    name="🎫 티켓 번호",
                    value=f"`{ticket_number}`",
                    inline=True
                )
                embed.add_field(
                    name="👤 담당 관리자",
                    value=consultation['admin_name'],
                    inline=True
                )
                embed.add_field(
                    name="📊 상태",
                    value=status_text,
                    inline=True
                )
                embed.add_field(
                    name="🚨 긴급 여부",
                    value="⚠️ 긴급" if consultation['is_urgent'] else "일반",
                    inline=True
                )
                embed.add_field(
                    name="📅 신청일",
                    value=f"<t:{int(discord.utils.fromisoformat(consultation['created_at']).timestamp())}:F>",
                    inline=True
                )
                
                if consultation.get('accepted_at'):
                    embed.add_field(
                        name="✅ 수락일",
                        value=f"<t:{int(discord.utils.fromisoformat(consultation['accepted_at']).timestamp())}:R>",
                        inline=True
                    )
                
                if consultation.get('completed_at'):
                    embed.add_field(
                        name="✅ 완료일",
                        value=f"<t:{int(discord.utils.fromisoformat(consultation['completed_at']).timestamp())}:F>",
                        inline=True
                    )
                
                embed.set_footer(text=f"1:1 상담 | ID: {consultation['id']}")
                embed.timestamp = discord.utils.utcnow()
                
                await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            logger.error(f"❌ 티켓 상세 조회 오류: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 티켓 조회 중 오류가 발생했습니다.",
                    ephemeral=True
                )
            except:
                pass

async def setup(bot):
    """Cog 로드"""
    await bot.add_cog(InquirySystem(bot))
    logger.info("✅ InquirySystem Cog이 로드되었습니다.")