import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional
from datetime import datetime, time, timedelta
import re

def get_upcoming_weekday(weekday: int) -> datetime:
    """
    다가오는 특정 요일 날짜를 반환
    - 오늘이 해당 요일이면 오늘 반환
    - 이미 지난 요일이면 다음 주 해당 요일 반환
    - weekday: 0=월요일, 1=화요일, ..., 6=일요일
    """
    today = datetime.now()
    days_ahead = weekday - today.weekday()
    if days_ahead < 0:  # 이미 지난 요일
        days_ahead += 7
    return today + timedelta(days=days_ahead)

def get_next_week_weekday(weekday: int) -> datetime:
    """
    다음 주 특정 요일 날짜를 반환 (무조건 다음 주)
    - weekday: 0=월요일, 1=화요일, ..., 6=일요일
    """
    today = datetime.now()
    days_ahead = weekday - today.weekday() + 7
    return today + timedelta(days=days_ahead)

def generate_date_options() -> List[discord.SelectOption]:
    """날짜 선택 옵션들을 동적으로 생성"""
    now = datetime.now()
    options = []
    
    # 기본 옵션들
    options.extend([
        discord.SelectOption(
            label="오늘",
            value="today",
            description=f"오늘 ({now.strftime('%m월 %d일 %A')})",
            emoji="📅"
        ),
        discord.SelectOption(
            label="내일",
            value="tomorrow",
            description=f"내일 ({(now + timedelta(days=1)).strftime('%m월 %d일 %A')})",
            emoji="📅"
        ),
        discord.SelectOption(
            label="모레",
            value="day_after_tomorrow",
            description=f"모레 ({(now + timedelta(days=2)).strftime('%m월 %d일 %A')})",
            emoji="📅"
        )
    ])
    
    # 다가오는 주중/주말 옵션들
    upcoming_friday = get_upcoming_weekday(4)  # 금요일
    upcoming_saturday = get_upcoming_weekday(5)  # 토요일
    upcoming_sunday = get_upcoming_weekday(6)  # 일요일
    
    # 다가오는 금요일이 3일 이상 남았을 때만 표시
    if (upcoming_friday - now).days >= 1:
        options.append(discord.SelectOption(
            label="다가오는 금요일",
            value="upcoming_friday",
            description=f"금요일 ({upcoming_friday.strftime('%m월 %d일')})",
            emoji="📅"
        ))
    
    options.extend([
        discord.SelectOption(
            label="다가오는 토요일",
            value="upcoming_saturday",
            description=f"토요일 ({upcoming_saturday.strftime('%m월 %d일')})",
            emoji="📅"
        ),
        discord.SelectOption(
            label="다가오는 일요일",
            value="upcoming_sunday",
            description=f"일요일 ({upcoming_sunday.strftime('%m월 %d일')})",
            emoji="📅"
        )
    ])
    
    # 다음 주 옵션들
    next_friday = get_next_week_weekday(4)
    next_saturday = get_next_week_weekday(5)
    next_sunday = get_next_week_weekday(6)
    
    options.extend([
        discord.SelectOption(
            label="다음 주 금요일",
            value="next_friday",
            description=f"다음 주 금요일 ({next_friday.strftime('%m월 %d일')})",
            emoji="📅"
        ),
        discord.SelectOption(
            label="다음 주 토요일",
            value="next_saturday",
            description=f"다음 주 토요일 ({next_saturday.strftime('%m월 %d일')})",
            emoji="📅"
        ),
        discord.SelectOption(
            label="다음 주 일요일",
            value="next_sunday",
            description=f"다음 주 일요일 ({next_sunday.strftime('%m월 %d일')})",
            emoji="📅"
        )
    ])
    
    # Discord 선택 옵션은 최대 25개까지만 가능하므로 적절히 제한
    return options[:25]

class DateTimeModal(discord.ui.Modal):
    """날짜/시간 선택을 위한 Modal"""
    
    def __init__(self, bot, channel_id: str):
        super().__init__(title="📅 내전 모집 등록")
        self.bot = bot
        self.channel_id = channel_id
        
        # 제목 입력
        self.title_input = discord.ui.TextInput(
            label="내전 제목",
            placeholder="예: 금요일 정기 내전",
            required=True,
            max_length=50
        )
        self.add_item(self.title_input)
        
        # 내용 입력
        self.content_input = discord.ui.TextInput(
            label="내전 설명",
            placeholder="내전에 대한 추가 설명을 입력하세요",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.content_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Modal 제출 시 모집 타입 선택 단계로 진행"""
        
        # 🆕 모집 타입 선택 View 생성
        view = RecruitmentTypeSelectView(
            self.bot, 
            self.channel_id,
            self.title_input.value,
            self.content_input.value or "내전 참가자를 모집합니다!"
        )
        
        await interaction.response.send_message(
            "📋 **내전 모집 방식을 선택해주세요:**\n\n"
            "🕐 **고정 시간**: 관리자가 지정한 시간에 모집\n"
            "🗳️ **시간대 투표**: 유저들이 가능한 시간대를 투표하여 자동 확정",
            view=view,
            ephemeral=True
        )
        
        # 전송된 메시지 참조 저장
        view.message = await interaction.original_response()

class RecruitmentTypeSelectView(discord.ui.View):
    """모집 타입 선택 View (고정 시간 vs 시간대 투표)"""
    
    def __init__(self, bot, channel_id: str, title: str, description: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.channel_id = channel_id
        self.title = title
        self.description = description
        self.message = None
    
    @discord.ui.button(
        label="고정 시간 모집",
        style=discord.ButtonStyle.primary,
        emoji="🕐",
        custom_id="fixed_time_recruitment"
    )
    async def fixed_time_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """고정 시간 모집 선택"""
        # 기존 DateTimeSelectionView로 이동
        view = DateTimeSelectionView(
            self.bot,
            self.channel_id,
            self.title,
            self.description
        )
        
        await interaction.response.edit_message(
            content="📅 내전 날짜와 시간을 선택해주세요:",
            view=view
        )
        
        view.message = await interaction.original_response()
    
    @discord.ui.button(
        label="시간대 투표 모집",
        style=discord.ButtonStyle.success,
        emoji="🗳️",
        custom_id="voting_time_recruitment"
    )
    async def voting_time_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """시간대 투표 모집 선택"""
        view = VotingConfigView(self.bot, self.channel_id, self.title, self.description)
        
        await interaction.response.edit_message(
            content="🗳️ **시간대 투표 모집 설정**\n\n"
                "아래에서 순서대로 설정을 선택해주세요:",
            view=view
        )
        
        view.message = await interaction.original_response()
    
    async def on_timeout(self):
        """타임아웃 처리"""
        if self.message:
            try:
                await self.message.edit(
                    content="⏱️ 시간 초과로 모집 등록이 취소되었습니다.",
                    view=None
                )
            except:
                pass

class VotingConfigView(discord.ui.View):
    """투표 방식 모집 설정 View (시간대 직접 선택)"""
    
    def __init__(self, bot, channel_id: str, title: str, description: str):
        super().__init__(timeout=600)
        self.bot = bot
        self.channel_id = channel_id
        self.recruitment_title = title
        self.recruitment_description = description
        self.message = None
        
        # 선택된 값들
        self.selected_base_time = None  # 기준 시간
        self.selected_time_slots = []   # 선택된 시간대들
        self.selected_deadline = None
        
        # 고정값
        self.min_participants = 10  # 고정
        
        self._setup_ui()
    
    def _setup_ui(self):
        """UI 초기 설정"""
        # 1. 기준 시간 선택
        self.base_time_select = discord.ui.Select(
            placeholder="🕐 기준 시간을 선택하세요",
            options=self._generate_base_time_options(),
            custom_id="base_time_select",
            row=0
        )
        self.base_time_select.callback = self.base_time_callback
        self.add_item(self.base_time_select)
        
        # 2. 시간대 선택 (다중 선택, 비활성)
        self.time_slots_select = discord.ui.Select(
            placeholder="⏰ 먼저 기준 시간을 선택하세요",
            options=[discord.SelectOption(label="먼저 기준 시간을 선택하세요", value="placeholder")],
            min_values=1,
            max_values=1,
            disabled=True,
            custom_id="time_slots_select",
            row=1
        )
        self.time_slots_select.callback = self.time_slots_callback
        self.add_item(self.time_slots_select)
        
        # 3. 마감 시간 선택 (비활성)
        self.deadline_select = discord.ui.Select(
            placeholder="⏰ 먼저 시간대를 선택하세요",
            options=[discord.SelectOption(label="먼저 시간대를 선택하세요", value="placeholder")],
            disabled=True,
            custom_id="deadline_select",
            row=2
        )
        self.deadline_select.callback = self.deadline_callback
        self.add_item(self.deadline_select)
        
        # 4. 등록 버튼 (비활성)
        self.register_button = discord.ui.Button(
            label="📝 모집 등록",
            style=discord.ButtonStyle.success,
            disabled=True
        )
        self.register_button.callback = self.register_callback
        self.add_item(self.register_button)
    
    def _generate_base_time_options(self) -> List[discord.SelectOption]:
        """기준 시간 선택 옵션"""
        options = []
        for hour in range(17, 24):
            time_str = f"{hour:02d}:00"
            display = f"오후 {hour-12}시" if hour > 12 else "정오" if hour == 12 else f"오전 {hour}시"
            options.append(
                discord.SelectOption(
                    label=time_str,
                    value=time_str,
                    description=display,
                    emoji="🕐"
                )
            )
        
        options.append(
            discord.SelectOption(
                label="직접 입력",
                value="custom",
                description="원하는 시간을 직접 입력합니다",
                emoji="⌨️"
            )
        )
        
        return options
    
    def _generate_time_slots_options(self, base_hour: int, base_minute: int) -> List[discord.SelectOption]:
        """기준 시간 기준으로 주변 시간대 생성"""
        from datetime import datetime, timedelta
        
        # 기준 시간
        base_time = datetime.now().replace(hour=base_hour, minute=base_minute, second=0, microsecond=0)
        
        options = []
        
        # 기준 시간 기준으로 -90분 ~ +90분 (30분 간격, 총 7개)
        for offset in range(-90, 120, 30):
            slot_time = base_time + timedelta(minutes=offset)
            hour = slot_time.hour
            minute = slot_time.minute
            
            # 시간 제한 없이 모든 시간대 허용 (새벽 시간대도 포함)
            # 단, 너무 이른 오전 시간(0~13시)은 제외하되, 23시 이후는 자정을 넘어가도 허용
            if hour < 14 and base_hour >= 17:
                # 기준 시간이 17시 이후인데 슬롯이 오전/이른 오후라면
                # 이는 자정을 넘어간 다음날 새벽 시간대
                if hour >= 14:  # 오후 2시 이전은 스킵
                    continue
                # 0~2시(새벽)는 허용
                if hour > 2:
                    continue
            
            time_str = f"{hour:02d}:{minute:02d}"
            
            # 기준 시간 표시
            if offset == 0:
                label = f"⭐ {time_str} (기준)"
                emoji = "⭐"
            else:
                label = time_str
                # 자정 이후 시간대는 특별 이모지
                if hour < 3:
                    emoji = "🌙"
                else:
                    emoji = "🕐"
            
            options.append(
                discord.SelectOption(
                    label=label,
                    value=time_str,
                    emoji=emoji
                )
            )
        
        return options[:25]  # Discord 최대 25개 제한
    
    def _generate_deadline_options(self) -> List[discord.SelectOption]:
        """마감 시간 옵션 (고정 시간 모집과 동일)"""
        from datetime import datetime
        
        if not self.selected_time_slots:
            return [discord.SelectOption(label="시간대를 먼저 선택하세요", value="placeholder")]
        
        # 첫 번째 시간대 기준
        first_slot = self.selected_time_slots[0]
        hour, minute = map(int, first_slot.split(':'))
        scrim_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # 고정 시간 모집과 동일한 옵션들
        deadline_options = [
            ("10min_before", "🔥 내전 10분 전 (깜짝 내전)", scrim_time - timedelta(minutes=10)),
            ("30min_before", "🔥 내전 30분 전 (깜짝 내전)", scrim_time - timedelta(minutes=30)),
            ("1hour_before", "내전 1시간 전", scrim_time - timedelta(hours=1)),
            ("2hour_before", "내전 2시간 전", scrim_time - timedelta(hours=2)),
            ("3hour_before", "내전 3시간 전", scrim_time - timedelta(hours=3)),
            ("1day_before", "내전 하루 전", scrim_time - timedelta(days=1)),
            ("same_day_3pm", "내전 당일 오후 3시", scrim_time.replace(hour=15, minute=0)),
            ("same_day_4pm", "내전 당일 오후 4시", scrim_time.replace(hour=16, minute=0)),
            ("same_day_5pm", "내전 당일 오후 5시", scrim_time.replace(hour=17, minute=0)),
            ("same_day_6pm", "내전 당일 오후 6시", scrim_time.replace(hour=18, minute=0)),
            ("6hour_before", "내전 6시간 전", scrim_time - timedelta(hours=6)),
            ("12hour_before", "내전 12시간 전", scrim_time - timedelta(hours=12)),
        ]
        
        options = []
        for value, label, deadline_time in deadline_options:
            # 마감 시간이 현재보다 미래인 것만
            if deadline_time > datetime.now():
                # 10분전, 30분전은 특별한 이모지와 설명 추가
                if value in ["10min_before", "30min_before"]:
                    emoji = "⚡"
                    desc = "긴급 모집용" if value == "10min_before" else "빠른 모집용"
                else:
                    emoji = "⏰"
                    desc = deadline_time.strftime('%m월 %d일 %H:%M')
                
                options.append(
                    discord.SelectOption(
                        label=label,
                        value=value,
                        description=desc,
                        emoji=emoji
                    )
                )
        
        # 커스텀 옵션
        options.append(
            discord.SelectOption(
                label="🛠️ 정확한 시간 입력",
                value="custom",
                description="원하는 시간을 직접 입력합니다",
                emoji="📅"
            )
        )
        
        return options
    
    async def base_time_callback(self, interaction: discord.Interaction):
        """기준 시간 선택"""
        selected_value = self.base_time_select.values[0]
        
        if selected_value == "custom":
            modal = CustomStartTimeModal(self)
            await interaction.response.send_modal(modal)
        else:
            self.selected_base_time = selected_value
            hour, minute = map(int, selected_value.split(':'))
            
            # 시간대 선택 활성화
            self.time_slots_select.disabled = False
            self.time_slots_select.placeholder = "⏰ 참가 가능한 시간대들을 선택하세요 (여러 개 가능)"
            self.time_slots_select.options = self._generate_time_slots_options(hour, minute)
            self.time_slots_select.min_values = 2  # 최소 2개
            self.time_slots_select.max_values = min(len(self.time_slots_select.options), 7)  # 최대 7개
            
            await interaction.response.edit_message(
                content=f"✅ **기준 시간**: {selected_value}\n"
                       f"⏰ 이제 참가 가능한 시간대들을 선택해주세요 (2개 이상):",
                view=self
            )
    
    async def time_slots_callback(self, interaction: discord.Interaction):
        """시간대 선택"""
        self.selected_time_slots = sorted(self.time_slots_select.values)
        
        # 마감 시간 선택 활성화
        self.deadline_select.disabled = False
        self.deadline_select.placeholder = "⏰ 모집 마감 시간을 선택하세요"
        self.deadline_select.options = self._generate_deadline_options()
        
        # 선택된 시간대 표시
        slots_display = '\n'.join([f"🕐 {slot}" for slot in self.selected_time_slots])
        
        await interaction.response.edit_message(
            content=f"✅ **기준 시간**: {self.selected_base_time}\n"
                   f"✅ **선택된 시간대** ({len(self.selected_time_slots)}개):\n{slots_display}\n"
                   f"👥 **필요 인원**: 10명 (고정)\n\n"
                   f"⏰ 마지막으로 모집 마감 시간을 선택해주세요:",
            view=self
        )
    
    async def deadline_callback(self, interaction: discord.Interaction):
        """마감 시간 선택"""
        from datetime import datetime, timedelta
        
        selected_value = self.deadline_select.values[0]
        
        if selected_value == "custom":
            modal = CustomDeadlineTimeModal(self)
            await interaction.response.send_modal(modal)
        else:
            # 첫 번째 시간대 기준으로 마감 시간 계산
            first_slot = self.selected_time_slots[0]
            hour, minute = map(int, first_slot.split(':'))
            scrim_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # 마감 시간 계산 (고정시간 모집과 동일)
            deadline_map = {
                "10min_before": timedelta(minutes=-10),
                "30min_before": timedelta(minutes=-30),
                "1hour_before": timedelta(hours=-1),
                "2hour_before": timedelta(hours=-2),
                "3hour_before": timedelta(hours=-3),
                "6hour_before": timedelta(hours=-6),
                "12hour_before": timedelta(hours=-12),
                "1day_before": timedelta(days=-1),
                "same_day_3pm": None,  # 특별 처리
                "same_day_4pm": None,  # 특별 처리
                "same_day_5pm": None,  # 특별 처리
                "same_day_6pm": None,  # 특별 처리
            }
            
            # 당일 고정 시간 처리
            if selected_value == "same_day_3pm":
                self.selected_deadline = scrim_time.replace(hour=15, minute=0)
            elif selected_value == "same_day_4pm":
                self.selected_deadline = scrim_time.replace(hour=16, minute=0)
            elif selected_value == "same_day_5pm":
                self.selected_deadline = scrim_time.replace(hour=17, minute=0)
            elif selected_value == "same_day_6pm":
                self.selected_deadline = scrim_time.replace(hour=18, minute=0)
            else:
                self.selected_deadline = scrim_time + deadline_map[selected_value]
            
            # 등록 버튼 활성화
            self.register_button.disabled = False
            
            slots_display = '\n'.join([f"🕐 {slot}" for slot in self.selected_time_slots])
            
            await interaction.response.edit_message(
                content=f"✅ **기준 시간**: {self.selected_base_time}\n"
                    f"✅ **선택된 시간대** ({len(self.selected_time_slots)}개):\n{slots_display}\n"
                    f"✅ **필요 인원**: 10명 (고정)\n"
                    f"✅ **마감 시간**: {self.selected_deadline.strftime('%m월 %d일 %H:%M')}\n\n"
                    f"🎯 모든 설정이 완료되었습니다! **모집 등록** 버튼을 눌러주세요.",
                view=self
            )
    
    async def register_callback(self, interaction: discord.Interaction):
        """최종 등록"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 시간 간격 계산
            from datetime import datetime
            times = [datetime.strptime(t, "%H:%M") for t in self.selected_time_slots]
            intervals = [(times[i+1] - times[i]).seconds // 60 for i in range(len(times)-1)]
            avg_interval = sum(intervals) // len(intervals) if intervals else 30
            
            # DB에 투표 모집 생성
            guild_id = str(interaction.guild_id)
            recruitment_id = await self.bot.db_manager.create_voting_recruitment_with_slots(
                guild_id=guild_id,
                title=self.recruitment_title,
                description=self.recruitment_description,
                time_slots=self.selected_time_slots,
                deadline=self.selected_deadline,
                created_by=str(interaction.user.id),
                min_participants=self.min_participants
            )
            
            # 채널에 투표 메시지 발송
            channel = self.bot.get_channel(int(self.channel_id))
            if not channel:
                await interaction.followup.send(
                    "❌ 공지 채널을 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # Embed와 View 생성
            embed, view = await self._create_voting_embed_and_view(recruitment_id)
            
            # View의 Select Menu 옵션 업데이트
            await view.update_select_options()
            
            # 메시지 발송
            message = await channel.send(embed=embed, view=view)
            
            # 메시지 ID 저장
            await self.bot.db_manager.update_recruitment_message_info(
                recruitment_id, str(message.id), str(channel.id)
            )
            
            # 성공 메시지
            slots_display = '\n'.join([f"🕐 {slot}" for slot in self.selected_time_slots])
            
            await interaction.followup.send(
                f"✅ **시간대 투표 모집이 등록되었습니다!**\n\n"
                f"📋 **모집**: {self.recruitment_title}\n"
                f"📊 **시간대** ({len(self.selected_time_slots)}개):\n{slots_display}\n"
                f"👥 **필요 인원**: {self.min_participants}명\n"
                f"⏰ **마감**: {self.selected_deadline.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🔗 {channel.mention}에 투표 공지가 게시되었습니다!",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 모집 등록 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
            import traceback
            traceback.print_exc()
    
    async def _create_voting_embed_and_view(self, recruitment_id: str):
        """투표 Embed와 View 생성"""
        recruitment = await self.bot.db_manager.get_voting_recruitment_info(recruitment_id)
        
        embed = discord.Embed(
            title=f"🗳️ {recruitment['title']}",
            description=f"{recruitment['description']}\n\n"
                       f"**참가 가능한 시간대를 모두 선택해주세요!**",
            color=0x00ff88
        )
        
        embed.add_field(
            name="⏰ 투표 마감",
            value=self.selected_deadline.strftime('%Y년 %m월 %d일 (%A) %H:%M'),
            inline=True
        )
        
        embed.add_field(
            name="👥 필요 인원",
            value=f"{self.min_participants}명",
            inline=True
        )
        
        embed.add_field(
            name="📊 현재 상태",
            value="🟢 투표 진행 중",
            inline=True
        )
        
        # 시간대별 투표 현황
        time_slots_text = ""
        for slot in recruitment['time_slots']:
            time_slots_text += f"🕐 **{slot['time_slot']}** ░░░░░░░░░░ 0명\n"
        
        embed.add_field(
            name="⏱️ 시간대별 참가 현황",
            value=time_slots_text,
            inline=False
        )
        
        embed.set_footer(text=f"모집 ID: {recruitment_id} | 중복 선택 가능")
        
        # View 생성
        view = VotingRecruitmentView(self.bot, recruitment_id)
        
        return embed, view
    
    async def on_timeout(self):
        """타임아웃 처리"""
        if self.message:
            try:
                await self.message.edit(
                    content="⏱️ 시간 초과로 모집 등록이 취소되었습니다.",
                    view=None
                )
            except:
                pass


class CustomStartTimeModal(discord.ui.Modal):
    """커스텀 시작 시간 입력 Modal"""
    
    def __init__(self, parent_view):
        super().__init__(title="⌨️ 시작 시간 직접 입력")
        self.parent_view = parent_view
        
        self.time_input = discord.ui.TextInput(
            label="시작 시간 (24시간 형식)",
            placeholder="예: 21:00",
            required=True,
            max_length=5
        )
        self.add_item(self.time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """시간 입력 제출"""
        time_str = self.time_input.value.strip()
        
        # 검증
        if not self._validate_time_format(time_str):
            await interaction.response.send_message(
                "❌ 올바른 시간 형식이 아닙니다. (예: 21:00)",
                ephemeral=True
            )
            return
        
        # VotingConfigView인 경우
        if hasattr(self.parent_view, 'selected_base_time'):
            self.parent_view.selected_base_time = time_str
            hour, minute = map(int, time_str.split(':'))
            
            # 시간대 선택 활성화
            self.parent_view.time_slots_select.disabled = False
            self.parent_view.time_slots_select.placeholder = "⏰ 참가 가능한 시간대들을 선택하세요 (여러 개 가능)"
            self.parent_view.time_slots_select.options = self.parent_view._generate_time_slots_options(hour, minute)
            self.parent_view.time_slots_select.min_values = 2  # 최소 2개
            self.parent_view.time_slots_select.max_values = min(len(self.parent_view.time_slots_select.options), 7)  # 최대 7개
            
            await interaction.response.edit_message(
                content=f"✅ **기준 시간**: {time_str}\n"
                       f"⏰ 이제 참가 가능한 시간대들을 선택해주세요 (2개 이상):",
                view=self.parent_view
            )
        # 다른 View인 경우 (기존 로직)
        else:
            self.parent_view.selected_start_time = time_str
            
            # 다음 단계 활성화
            self.parent_view.interval_select.disabled = False
            self.parent_view.interval_select.placeholder = "⏱️ 시간 간격을 선택하세요"
            self.parent_view.interval_select.options = self.parent_view._generate_interval_options()
            
            await interaction.response.edit_message(
                content=f"✅ **시작 시간**: {time_str}\n⏱️ 이제 시간 간격을 선택해주세요:",
                view=self.parent_view
            )
    
    def _validate_time_format(self, time_str: str) -> bool:
        """시간 형식 검증"""
        import re
        pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'
        return bool(re.match(pattern, time_str))


class CustomDeadlineTimeModal(discord.ui.Modal):
    """커스텀 마감 시간 입력 Modal"""
    
    def __init__(self, parent_view):
        super().__init__(title="⌨️ 마감 시간 직접 입력")
        self.parent_view = parent_view
        
        self.datetime_input = discord.ui.TextInput(
            label="마감 시간",
            placeholder="예: 18:00 (오늘) 또는 12-25 18:00",
            required=True,
            max_length=20
        )
        self.add_item(self.datetime_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """마감 시간 입력 제출"""
        from datetime import datetime, timedelta
        
        datetime_str = self.datetime_input.value.strip()
        
        # 파싱
        parsed_datetime = self._parse_deadline(datetime_str)
        if not parsed_datetime:
            await interaction.response.send_message(
                "❌ 올바른 형식이 아닙니다.\n"
                "형식: 18:00 (오늘) 또는 12-25 18:00",
                ephemeral=True
            )
            return
        
        if parsed_datetime <= datetime.now():
            await interaction.response.send_message(
                "❌ 마감 시간은 현재 시간보다 미래여야 합니다.",
                ephemeral=True
            )
            return
        
        self.parent_view.selected_deadline = parsed_datetime
        
        # 등록 버튼 활성화
        self.parent_view.register_button.disabled = False
        
        preview = self.parent_view._generate_time_slots_preview()
        
        await interaction.response.edit_message(
            content=f"✅ **시작 시간**: {self.parent_view.selected_start_time}\n"
                   f"✅ **시간 간격**: {self.parent_view.selected_interval}분\n"
                   f"✅ **시간대 개수**: {self.parent_view.selected_slot_count}개\n"
                   f"✅ **최소 인원**: {self.parent_view.selected_min_participants}명\n"
                   f"✅ **마감 시간**: {parsed_datetime.strftime('%m월 %d일 %H:%M')}\n\n"
                   f"📋 **시간대 미리보기**:\n{preview}\n\n"
                   f"🎯 모든 설정이 완료되었습니다! **모집 등록** 버튼을 눌러주세요.",
            view=self.parent_view
        )
    
    def _parse_deadline(self, datetime_str: str):
        """마감 시간 파싱"""
        import re
        from datetime import datetime, timedelta
        
        # HH:MM (오늘)
        pattern1 = r'^(\d{1,2}):(\d{2})$'
        match1 = re.match(pattern1, datetime_str)
        if match1:
            hour, minute = map(int, match1.groups())
            result = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            if result < datetime.now():
                result += timedelta(days=1)
            return result
        
        # MM-DD HH:MM
        pattern2 = r'^(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})$'
        match2 = re.match(pattern2, datetime_str)
        if match2:
            month, day, hour, minute = map(int, match2.groups())
            year = datetime.now().year
            result = datetime(year, month, day, hour, minute)
            if result < datetime.now():
                result = datetime(year + 1, month, day, hour, minute)
            return result
        
        return None

class VotingConfigModal(discord.ui.Modal):
    """투표 방식 모집 설정 Modal"""
    def __init__(self, bot, channel_id: str, title: str, description: str):
        super().__init__(title="시간대 투표 설정")
        self.bot = bot
        self.channel_id = channel_id
        self.recruitment_title = title
        self.recruitment_description = description
        
        # 시작 시간 입력
        self.start_time_input = discord.ui.TextInput(
            label="시작 시간 (24시간 형식)",
            placeholder="예: 21:00",
            required=True,
            max_length=5
        )
        self.add_item(self.start_time_input)
        
        # 시간 간격 입력
        self.interval_input = discord.ui.TextInput(
            label="시간 간격 (분)",
            placeholder="기본값: 30분 (15~120분)",
            required=False,
            default="30",
            max_length=3
        )
        self.add_item(self.interval_input)
        
        # 시간대 개수 입력
        self.slot_count_input = discord.ui.TextInput(
            label="시간대 개수",
            placeholder="기본값: 4개 (2~8개)",
            required=False,
            default="4",
            max_length=1
        )
        self.add_item(self.slot_count_input)
        
        # 최소 참가 인원 입력
        self.min_participants_input = discord.ui.TextInput(
            label="최소 참가 인원",
            placeholder="기본값: 10명 (4~20명)",
            required=False,
            default="10",
            max_length=2
        )
        self.add_item(self.min_participants_input)
        
        # 마감 시간 입력
        self.deadline_input = discord.ui.TextInput(
            label="모집 마감 날짜와 시간",
            placeholder="예: 12-25 18:00 (오늘이면 생략 가능: 18:00)",
            required=True,
            max_length=20
        )
        self.add_item(self.deadline_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """투표 설정 제출 처리"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 1. 시작 시간 검증
            start_time = self.start_time_input.value.strip()
            if not self._validate_time_format(start_time):
                await interaction.followup.send(
                    "❌ 시작 시간 형식이 올바르지 않습니다.\n"
                    "24시간 형식으로 입력해주세요. (예: 21:00)",
                    ephemeral=True
                )
                return
            
            # 2. 시간 간격 검증
            try:
                interval = int(self.interval_input.value.strip() or "30")
                if not (15 <= interval <= 120):
                    raise ValueError
            except ValueError:
                await interaction.followup.send(
                    "❌ 시간 간격은 15~120분 사이여야 합니다.",
                    ephemeral=True
                )
                return
            
            # 3. 시간대 개수 검증
            try:
                slot_count = int(self.slot_count_input.value.strip() or "4")
                if not (2 <= slot_count <= 8):
                    raise ValueError
            except ValueError:
                await interaction.followup.send(
                    "❌ 시간대 개수는 2~8개 사이여야 합니다.",
                    ephemeral=True
                )
                return
            
            # 4. 최소 인원 검증
            try:
                min_participants = int(self.min_participants_input.value.strip() or "10")
                if not (4 <= min_participants <= 20):
                    raise ValueError
            except ValueError:
                await interaction.followup.send(
                    "❌ 최소 참가 인원은 4~20명 사이여야 합니다.",
                    ephemeral=True
                )
                return
            
            # 5. 마감 시간 검증
            deadline = self._parse_deadline_datetime(self.deadline_input.value.strip())
            if not deadline:
                await interaction.followup.send(
                    "❌ 마감 시간 형식이 올바르지 않습니다.\n"
                    "형식: MM-DD HH:MM 또는 YYYY-MM-DD HH:MM\n"
                    "예: 12-25 18:00",
                    ephemeral=True
                )
                return
            
            if deadline <= datetime.now():
                await interaction.followup.send(
                    "❌ 마감 시간은 현재 시간보다 미래여야 합니다.",
                    ephemeral=True
                )
                return
            
            # 6. DB에 투표 모집 생성
            guild_id = str(interaction.guild_id)
            recruitment_id = await self.bot.db_manager.create_voting_recruitment(
                guild_id=guild_id,
                title=self.recruitment_title,
                description=self.recruitment_description,
                start_time=start_time,
                deadline=deadline,
                created_by=str(interaction.user.id),
                time_interval_minutes=interval,
                time_slot_count=slot_count,
                min_participants=min_participants
            )
            
            # 7. 채널에 투표 메시지 발송
            channel = self.bot.get_channel(int(self.channel_id))
            if not channel:
                await interaction.followup.send(
                    "❌ 공지 채널을 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # Embed와 View 생성
            embed, view = await self._create_voting_embed_and_view(recruitment_id)

            await view.update_select_options()
            
            # 메시지 발송
            message = await channel.send(embed=embed, view=view)
            
            # 메시지 ID 저장
            await self.bot.db_manager.update_recruitment_message_info(
                recruitment_id, str(message.id), str(channel.id)
            )
            
            # 성공 메시지
            await interaction.followup.send(
                f"✅ **시간대 투표 모집이 등록되었습니다!**\n\n"
                f"📋 모집: {self.recruitment_title}\n"
                f"🕐 시작 시간: {start_time}\n"
                f"⏱️ 간격: {interval}분\n"
                f"📊 시간대: {slot_count}개\n"
                f"👥 최소 인원: {min_participants}명\n"
                f"⏰ 마감: {deadline.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"🔗 {channel.mention}에 투표 공지가 게시되었습니다!",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 모집 등록 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    async def _create_voting_embed_and_view(self, recruitment_id: str):
        """투표 Embed와 View 생성"""
        recruitment = await self.bot.db_manager.get_voting_recruitment_info(recruitment_id)
        
        embed = discord.Embed(
            title=f"🗳️ {recruitment['title']}",
            description=f"{recruitment['description']}\n\n"
                    f"**참가 가능한 시간대를 모두 선택해주세요!**",
            color=0x00ff88
        )
        
        deadline = datetime.fromisoformat(recruitment['deadline'])
        embed.add_field(
            name="⏰ 투표 마감",
            value=deadline.strftime('%Y년 %m월 %d일 (%A) %H:%M'),
            inline=True
        )
        
        embed.add_field(
            name="👥 필요 인원",
            value=f"{recruitment['min_participants']}명",
            inline=True
        )
        
        embed.add_field(
            name="📊 현재 상태",
            value="🟢 투표 진행 중",
            inline=True
        )
        
        # 시간대별 투표 현황
        time_slots_text = ""
        for slot in recruitment['time_slots']:
            bar = self._create_vote_bar(slot['vote_count'], recruitment['min_participants'])
            time_slots_text += f"🕐 **{slot['time_slot']}** {bar} {slot['vote_count']}명\n"
        
        embed.add_field(
            name="⏱️ 시간대별 참가 현황",
            value=time_slots_text or "아직 투표가 없습니다.",
            inline=False
        )
        
        embed.set_footer(text=f"모집 ID: {recruitment_id} | 중복 선택 가능")
        
        # View 생성
        view = VotingRecruitmentView(self.bot, recruitment_id)
        
        return embed, view


    def _create_vote_bar(self, current: int, target: int) -> str:
        """투표 진행 바 생성"""
        if target == 0:
            return "░░░░░░░░░░"
        
        ratio = min(current / target, 1.0)
        filled = int(ratio * 10)
        empty = 10 - filled
        
        if current >= target:
            return "🟢" + "█" * filled + "░" * empty
        else:
            return "█" * filled + "░" * empty
    
    def _validate_time_format(self, time_str: str) -> bool:
        """시간 형식 검증 (HH:MM)"""
        import re
        pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'
        if not re.match(pattern, time_str):
            return False
        
        try:
            hour, minute = map(int, time_str.split(':'))
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except ValueError:
            return False
    
    def _parse_deadline_datetime(self, datetime_str: str) -> Optional[datetime]:
        """마감 시간 파싱"""
        import re
        
        # 패턴 0: HH:MM (오늘 날짜로 간주)
        pattern0 = r'^(\d{1,2}):(\d{2})$'
        match0 = re.match(pattern0, datetime_str)
        
        if match0:
            hour, minute = map(int, match0.groups())
            target_date = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # 이미 지난 시간이면 내일로
            if target_date < datetime.now():
                target_date += timedelta(days=1)
            
            return target_date
        
        # 패턴 1: MM-DD HH:MM
        pattern1 = r'^(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})$'
        match1 = re.match(pattern1, datetime_str)
        
        if match1:
            month, day, hour, minute = map(int, match1.groups())
            year = datetime.now().year
            
            # 월/일이 이미 지났으면 내년으로
            target_date = datetime(year, month, day, hour, minute)
            if target_date < datetime.now():
                target_date = datetime(year + 1, month, day, hour, minute)
            
            return target_date
        
        # 패턴 2: YYYY-MM-DD HH:MM
        pattern2 = r'^(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})$'
        match2 = re.match(pattern2, datetime_str)
        
        if match2:
            year, month, day, hour, minute = map(int, match2.groups())
            return datetime(year, month, day, hour, minute)
        
        return None
    
class VotingRecruitmentView(discord.ui.View):
    """시간대 투표 View"""
    
    def __init__(self, bot, recruitment_id: str):
        super().__init__(timeout=None)  # 타임아웃 없음
        self.bot = bot
        self.recruitment_id = recruitment_id
        
        # Select Menu 추가
        self.time_slot_select = TimeSlotSelect(bot, recruitment_id)
        self.add_item(self.time_slot_select)

    async def update_select_options(self):
        """Select Menu 옵션 업데이트 (View 생성 직후 호출)"""
        await self.time_slot_select.update_options()
    
    @discord.ui.button(
        label="내 투표 확인",
        style=discord.ButtonStyle.secondary,
        emoji="📋",
        custom_id="check_my_votes"
    )
    async def check_votes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """내가 투표한 시간대 확인"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            time_slots = await self.bot.db_manager.get_time_slots_by_recruitment(self.recruitment_id)
            user_id = str(interaction.user.id)
            
            voted_slots = []
            for slot in time_slots:
                voters = slot['voter_ids'].split(',') if slot['voter_ids'] else []
                if user_id in voters:
                    voted_slots.append(slot['time_slot'])
            
            if voted_slots:
                slots_text = '\n'.join([f"🕐 {slot}" for slot in voted_slots])
                await interaction.followup.send(
                    f"**📋 내가 투표한 시간대:**\n\n{slots_text}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "아직 투표하지 않았습니다.\n위의 메뉴에서 참가 가능한 시간대를 선택해주세요!",
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 투표 확인 중 오류: {str(e)}",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="참가자 목록",
        style=discord.ButtonStyle.primary,
        emoji="👥",
        custom_id="show_voters_list"
    )
    async def show_voters_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """시간대별 참가자 목록 표시"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 모집 정보 및 시간대 조회
            recruitment = await self.bot.db_manager.get_voting_recruitment_info(self.recruitment_id)
            if not recruitment:
                await interaction.followup.send(
                    "❌ 모집 정보를 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            time_slots = recruitment.get('time_slots', [])
            
            if not time_slots:
                await interaction.followup.send(
                    "❌ 시간대 정보를 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            # 임베드 생성
            embed = discord.Embed(
                title=f"👥 {recruitment['title']} - 시간대별 참가자 목록",
                description=f"**필요 인원**: {recruitment['min_participants']}명",
                color=0x00ff88
            )
            
            # 확정된 시간대가 있는 경우
            if recruitment.get('confirmed_time'):
                embed.add_field(
                    name="✅ 확정된 시간",
                    value=f"**{recruitment['confirmed_time']}**",
                    inline=False
                )
            
            # 각 시간대별 투표자 목록
            for slot in sorted(time_slots, key=lambda x: x['time_slot']):
                time_slot = slot['time_slot']
                vote_count = slot['vote_count']
                voter_names = slot.get('voter_names', '').split(',') if slot.get('voter_names') else []
                
                # 필요 인원 달성 여부에 따라 이모지 변경
                if vote_count >= recruitment['min_participants']:
                    emoji = "✅"
                    status = "확정 가능!"
                else:
                    emoji = "🕐"
                    status = f"{vote_count}/{recruitment['min_participants']}명"
                
                # 투표자가 있는 경우
                if voter_names and voter_names[0]:
                    # 최대 10명까지만 표시
                    if len(voter_names) <= 10:
                        voters_text = '\n'.join([f"{i}. {name}" for i, name in enumerate(voter_names, 1)])
                    else:
                        voters_text = '\n'.join([f"{i}. {name}" for i, name in enumerate(voter_names[:10], 1)])
                        voters_text += f"\n... 외 {len(voter_names) - 10}명"
                    
                    field_value = f"{emoji} **{status}**\n{voters_text}"
                else:
                    field_value = f"{emoji} **{status}**\n아직 투표자가 없습니다."
                
                embed.add_field(
                    name=f"🕐 {time_slot}",
                    value=field_value,
                    inline=False
                )
            
            # 마감 시간 정보
            deadline = datetime.fromisoformat(recruitment['deadline'])
            embed.add_field(
                name="⏰ 투표 마감",
                value=deadline.strftime('%Y년 %m월 %d일 %H:%M'),
                inline=False
            )
            
            embed.set_footer(text=f"모집 ID: {self.recruitment_id}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 참가자 목록 조회 중 오류가 발생했습니다: {str(e)}", 
                ephemeral=True
            )
            import traceback
            traceback.print_exc()


class TimeSlotSelect(discord.ui.Select):
    """시간대 선택 Select Menu"""
    
    def __init__(self, bot, recruitment_id: str):
        self.bot = bot
        self.recruitment_id = recruitment_id
        
        # 초기 옵션 (실제 옵션은 View가 생성될 때 업데이트됨)
        options = [
            discord.SelectOption(
                label="로딩 중...",
                value="loading",
                description="시간대를 불러오는 중입니다"
            )
        ]
        
        super().__init__(
            placeholder="참가 가능한 시간대를 선택하세요 (여러 개 선택 가능)",
            min_values=0, 
            max_values=1,
            options=options,
        )

    async def update_options(self):
        """시간대 옵션 업데이트"""
        try:
            recruitment = await self.bot.db_manager.get_voting_recruitment_info(self.recruitment_id)
            
            if not recruitment:
                return
            
            # 확정된 경우 비활성화
            if recruitment.get('confirmed_time'):
                self.disabled = True
                self.placeholder = f"✅ {recruitment['confirmed_time']}에 확정되었습니다"
                return
            
            time_slots = recruitment.get('time_slots', [])
            
            if not time_slots:
                return
            
            # 옵션 생성
            options = []
            for slot in time_slots:
                vote_count = slot['vote_count']
                min_participants = recruitment['min_participants']
                
                # 투표 진행 상태 표시
                if vote_count >= min_participants:
                    emoji = "✅"
                    description = f"참가 가능 ({vote_count}명) - 확정 가능!"
                else:
                    emoji = "🕐"
                    description = f"참가 가능 ({vote_count}/{min_participants}명)"
                
                options.append(
                    discord.SelectOption(
                        label=f"{slot['time_slot']}",
                        value=slot['time_slot'],
                        description=description,
                        emoji=emoji
                    )
                )
            
            # 옵션 업데이트
            self.options = options
            self.max_values = len(options)  # 모든 시간대 선택 가능
            
        except Exception as e:
            print(f"❌ 시간대 옵션 업데이트 오류: {e}")
    
    async def callback(self, interaction: discord.Interaction):
        """시간대 선택 콜백"""
        await interaction.response.defer()
        
        try:
            user_id = str(interaction.user.id)
            username = interaction.user.display_name
            
            # 선택된 시간대들
            selected_slots = self.values
            
            # 모든 시간대 조회
            all_slots = await self.bot.db_manager.get_time_slots_by_recruitment(self.recruitment_id)
            
            # 기존 투표 제거 (선택하지 않은 시간대)
            for slot in all_slots:
                if slot['time_slot'] not in selected_slots:
                    await self.bot.db_manager.remove_time_slot_vote(
                        self.recruitment_id, slot['time_slot'], user_id
                    )
            
            # 새로운 투표 추가
            for slot_time in selected_slots:
                await self.bot.db_manager.add_time_slot_vote(
                    self.recruitment_id, slot_time, user_id, username
                )
            
            # 자동 확정 체크
            confirmed_time = await self.bot.db_manager.check_and_confirm_time_slot(self.recruitment_id)
            
            # 메시지 업데이트
            await self._update_voting_message(interaction, confirmed_time)
            
            # 확정되었으면 알림
            if confirmed_time:
                await self._send_confirmation_notification(interaction, confirmed_time)
            
        except Exception as e:
            print(f"❌ 시간대 투표 처리 오류: {e}")
    
    async def _update_voting_message(self, interaction: discord.Interaction, confirmed_time: Optional[str]):
        """투표 메시지 업데이트"""
        from datetime import datetime, timedelta

        try:
            recruitment = await self.bot.db_manager.get_voting_recruitment_info(self.recruitment_id)
            
            if confirmed_time:
                # 확정됨
                embed = discord.Embed(
                    title=f"✅ {recruitment['title']} - 시간 확정!",
                    description=f"{recruitment['description']}\n\n"
                            f"**🎉 {confirmed_time}에 내전이 확정되었습니다!**",
                    color=0x00ff00
                )
                
                # 확정된 시간대의 투표자 목록
                confirmed_slot = next((s for s in recruitment['time_slots'] if s['time_slot'] == confirmed_time), None)
                if confirmed_slot:
                    voter_count = confirmed_slot['vote_count']
                    embed.add_field(
                        name="👥 참가 확정 인원",
                        value=f"{voter_count}명",
                        inline=True
                    )
                
                embed.add_field(
                    name="🕐 확정 시간",
                    value=confirmed_time,
                    inline=True
                )
                
                # 🆕 예상 내전 날짜 표시
                deadline_str = recruitment['deadline']
                from datetime import datetime, timedelta
                deadline_dt = datetime.fromisoformat(deadline_str)
                base_date = deadline_dt.date()
                hour, minute = map(int, confirmed_time.split(':'))
                scrim_dt = datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute))
                if scrim_dt <= deadline_dt:
                    scrim_dt += timedelta(days=1)
                
                embed.add_field(
                    name="📅 내전 일시",
                    value=scrim_dt.strftime('%Y년 %m월 %d일 (%A) %H:%M'),
                    inline=False
                )
                
                embed.set_footer(text=f"모집 ID: {self.recruitment_id} | 확정 완료")
                
                # View 비활성화
                view = discord.ui.View()
                
            else:
                # 아직 미확정
                embed = discord.Embed(
                    title=f"🗳️ {recruitment['title']}",
                    description=f"{recruitment['description']}\n\n"
                            f"**참가 가능한 시간대를 모두 선택해주세요!**",
                    color=0x00ff88
                )
                
                deadline = datetime.fromisoformat(recruitment['deadline'])
                embed.add_field(
                    name="⏰ 투표 마감",
                    value=deadline.strftime('%Y년 %m월 %d일 %H:%M'),
                    inline=True
                )
                
                embed.add_field(
                    name="👥 필요 인원",
                    value=f"{recruitment['min_participants']}명",
                    inline=True
                )
                
                embed.add_field(
                    name="📊 현재 상태",
                    value="🟢 투표 진행 중",
                    inline=True
                )
                
                # 시간대별 투표 현황
                time_slots_text = ""
                for slot in recruitment['time_slots']:
                    bar = self._create_vote_bar(slot['vote_count'], recruitment['min_participants'])
                    emoji = "✅" if slot['vote_count'] >= recruitment['min_participants'] else "🕐"
                    time_slots_text += f"{emoji} **{slot['time_slot']}** {bar} {slot['vote_count']}명\n"
                
                embed.add_field(
                    name="⏱️ 시간대별 참가 현황",
                    value=time_slots_text,
                    inline=False
                )
                
                embed.set_footer(text=f"모집 ID: {self.recruitment_id} | 중복 선택 가능")
                
                # View 재생성 및 옵션 업데이트
                view = VotingRecruitmentView(self.bot, self.recruitment_id)
                await view.update_select_options()
            
            # 메시지 수정
            await interaction.message.edit(embed=embed, view=view)
            
        except Exception as e:
            print(f"❌ 메시지 업데이트 오류: {e}")
    
    async def _send_confirmation_notification(self, interaction: discord.Interaction, confirmed_time: str):
        """확정 알림 발송"""
        try:
            # 확정된 시간대에 투표한 사람들 조회
            voters = await self.bot.db_manager.get_time_slot_voters(self.recruitment_id, confirmed_time)
            
            if not voters:
                return
            
            # 멘션 생성
            mentions = ' '.join([f"<@{voter_id}>" for voter_id in voters])
            
            # 채널에 알림 발송
            await interaction.channel.send(
                f"🎉 **내전 시간이 확정되었습니다!**\n\n"
                f"🕐 확정 시간: **{confirmed_time}**\n"
                f"👥 참가 확정: {len(voters)}명\n\n"
                f"{mentions}\n\n"
                f"내전 10분 전에 다시 알림드리겠습니다!"
            )
            
        except Exception as e:
            print(f"❌ 확정 알림 발송 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_vote_bar(self, current: int, target: int) -> str:
        """투표 진행 바 생성"""
        if target == 0:
            return "░░░░░░░░░░"
        
        ratio = min(current / target, 1.0)
        filled = int(ratio * 10)
        empty = 10 - filled
        
        if current >= target:
            return "🟢" + "█" * filled + "░" * empty
        else:
            return "█" * filled + "░" * empty

class CustomTimeModal(discord.ui.Modal):
    """커스텀 시간 입력을 위한 Modal"""
    
    def __init__(self, parent_view):
        super().__init__(title="⏰ 커스텀 시간 입력")
        self.parent_view = parent_view
        
        self.time_input = discord.ui.TextInput(
            label="시간 입력 (24시간 형식)",
            placeholder="예: 14:30, 09:15, 21:45",
            required=True,
            max_length=5
        )
        self.add_item(self.time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """시간 입력 처리"""
        time_str = self.time_input.value.strip()
        
        # 시간 형식 검증
        if not self._validate_time_format(time_str):
            await interaction.response.send_message(
                "❌ 올바른 시간 형식이 아닙니다.\n"
                "24시간 형식으로 입력해주세요. (예: 14:30, 09:15, 21:45)",
                ephemeral=True
            )
            return
        
        # 부모 뷰에 선택된 시간 전달
        self.parent_view.selected_time = time_str
        
        # UI 상태 업데이트
        self.parent_view._update_ui_state()
        
        try:
            await interaction.response.send_message(
                f"✅ 선택된 시간: **{self._format_time_display(time_str)}**\n"
                f"이제 모집 마감시간을 선택해주세요.",
                ephemeral=True
            )
            
            if self.parent_view.message:
                await self.parent_view.message.edit(
                    content=f"✅ 선택된 시간: **{self._format_time_display(time_str)}**\n"
                           f"이제 모집 마감시간을 선택해주세요.",
                    view=self.parent_view
                )
            
        except discord.NotFound:
            print(f"⚠️ 원본 메시지를 찾을 수 없습니다 (타임아웃 가능성)")
            pass
        except Exception as e:
            print(f"⚠️ 메시지 업데이트 중 오류: {e}")
            pass
    
    def _validate_time_format(self, time_str: str) -> bool:
        """시간 형식 검증 (HH:MM)"""
        import re
        pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'
        if not re.match(pattern, time_str):
            return False
        
        try:
            hour, minute = map(int, time_str.split(':'))
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except ValueError:
            return False
    
    def _format_time_display(self, time_str: str) -> str:
        """시간을 사용자 친화적 형식으로 포맷팅"""
        try:
            hour, minute = map(int, time_str.split(':'))
            
            if hour == 0:
                return f"자정 ({time_str})"
            elif hour < 12:
                return f"오전 {hour}시 {minute:02d}분 ({time_str})"
            elif hour == 12:
                return f"정오 ({time_str})"
            else:
                return f"오후 {hour-12}시 {minute:02d}분 ({time_str})"
        except:
            return time_str
        
class CustomDeadlineModal(discord.ui.Modal):
    """커스텀 마감시간 입력을 위한 Modal"""
    
    def __init__(self, parent_view):
        super().__init__(title="⏰ 커스텀 마감시간 입력")
        self.parent_view = parent_view
        
        self.datetime_input = discord.ui.TextInput(
            label="마감 날짜와 시간 입력",
            placeholder="예: 12-25 14:30, 2024-12-25 14:30",
            required=True,
            max_length=20,
            style=discord.TextStyle.short
        )
        self.add_item(self.datetime_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """마감시간 입력 처리 - 수정됨"""
        datetime_str = self.datetime_input.value.strip()
        
        # 날짜시간 형식 검증 및 파싱
        parsed_datetime = self._parse_deadline_datetime(datetime_str)
        if not parsed_datetime:
            await interaction.response.send_message(
                "❌ 올바른 날짜시간 형식이 아닙니다.\n"
                "형식: `MM-DD HH:MM` 또는 `YYYY-MM-DD HH:MM`\n"
                "예: `12-25 14:30`, `2024-12-25 14:30`",
                ephemeral=True
            )
            return
        
        # 현재 시간보다 미래인지 확인
        if parsed_datetime <= datetime.now():
            await interaction.response.send_message(
                "❌ 마감시간은 현재 시간보다 미래여야 합니다.",
                ephemeral=True
            )
            return
        
        # 내전 시간과 비교
        if self.parent_view.selected_date and self.parent_view.selected_time:
            scrim_datetime = self.parent_view._calculate_datetime()
            if parsed_datetime >= scrim_datetime:
                await interaction.response.send_message(
                    "❌ 마감시간은 내전 시간보다 이전이어야 합니다.\n"
                    f"내전 시간: {scrim_datetime.strftime('%Y-%m-%d %H:%M')}",
                    ephemeral=True
                )
                return
        
        # 부모 뷰에 선택된 마감시간 전달
        self.parent_view.selected_deadline = f"custom_datetime_{parsed_datetime.isoformat()}"
        print(f"DEBUG: CustomDeadlineModal에서 마감시간 설정됨: {self.parent_view.selected_deadline}")

        self.parent_view._update_ui_state()

        try:
            await interaction.response.send_message(
                f"✅ 선택된 마감시간: **{self._format_datetime_display(parsed_datetime)}**\n"
                f"모든 정보가 설정되었습니다! 등록 버튼을 눌러주세요.",
                ephemeral=True
            )
            
            if self.parent_view.message:
                await self.parent_view.message.edit(
                    content=f"✅ 선택된 마감시간: **{self._format_datetime_display(parsed_datetime)}**\n"
                           f"모든 정보가 설정되었습니다! 등록 버튼을 눌러주세요.",
                    view=self.parent_view
                )
                
        except discord.NotFound:
            print(f"⚠️ 원본 메시지를 찾을 수 없습니다")
            pass
        except Exception as e:
            print(f"⚠️ 메시지 업데이트 중 오류: {e}")
            pass
    
    def _parse_deadline_datetime(self, datetime_str: str) -> datetime:
        """마감시간 문자열을 datetime 객체로 파싱"""
        try:
            current_year = datetime.now().year
            
            # 공백으로 날짜와 시간 분리
            parts = datetime_str.strip().split()
            if len(parts) != 2:
                return None
            
            date_part, time_part = parts
            
            # 날짜 부분 파싱
            if '-' in date_part:
                date_components = date_part.split('-')
                if len(date_components) == 2:  # MM-DD 형식
                    month, day = map(int, date_components)
                    year = current_year
                elif len(date_components) == 3:  # YYYY-MM-DD 형식
                    year, month, day = map(int, date_components)
                else:
                    return None
            else:
                return None
            
            # 시간 부분 파싱 (HH:MM)
            if ':' not in time_part:
                return None
            
            hour, minute = map(int, time_part.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return None
            
            # datetime 객체 생성
            result = datetime(year, month, day, hour, minute)
            
            # 올해 날짜가 이미 지났으면 내년으로 조정 (MM-DD 형식의 경우)
            if len(date_components) == 2 and result < datetime.now():
                result = result.replace(year=current_year + 1)
            
            return result
            
        except (ValueError, TypeError):
            return None
    
    def _format_datetime_display(self, dt: datetime) -> str:
        """날짜시간을 사용자 친화적 형식으로 포맷팅"""
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        weekday = weekdays[dt.weekday()]
        
        hour = dt.hour
        if hour == 0:
            time_str = "자정"
        elif hour < 12:
            time_str = f"오전 {hour}시 {dt.minute:02d}분"
        elif hour == 12:
            time_str = f"정오 {dt.minute:02d}분" if dt.minute > 0 else "정오"
        else:
            time_str = f"오후 {hour-12}시 {dt.minute:02d}분"
        
        return f"{dt.strftime('%Y년 %m월 %d일')} ({weekday}) {time_str}"

class DateTimeSelectionView(discord.ui.View):
    """날짜/시간 선택을 위한 View"""
    
    def __init__(self, bot, channel_id: str, title: str, content: str):
        super().__init__(timeout=300)  # 5분 제한
        self.bot = bot
        self.channel_id = channel_id
        self.title = title
        self.content = content
        self.selected_date = None
        self.selected_time = None
        self.selected_deadline = None
        self.message = None
        self._setup_ui()

    def _setup_ui(self):
        """UI 컴포넌트 설정"""
        # 날짜 선택
        self.date_select = discord.ui.Select(
            placeholder="📅 내전 날짜를 선택하세요",
            options= generate_date_options(),
            row=0
        )
        self.date_select.callback = self.select_date_callback
        self.add_item(self.date_select)
        
        # 개선된 시간 선택 드롭다운
        self.time_select = discord.ui.Select(
            placeholder="🕕 내전 시간을 선택하세요",
            disabled=True,
            options=self._generate_time_options(),
            row=1
        )
        self.time_select.callback = self.select_time_callback
        self.add_item(self.time_select)
        
        # 마감시간 선택 (기존 로직 유지)
        self.deadline_select = discord.ui.Select(
            placeholder="⏰ 모집 마감시간을 선택하세요",
            disabled=True,
            options=self._generate_deadline_options(),
            row=2
        )
        self.deadline_select.callback = self.select_deadline_callback
        self.add_item(self.deadline_select)
        
        # 등록 버튼 (기존 로직 유지)
        self.register_button = discord.ui.Button(
            label="📝 내전 모집 등록",
            style=discord.ButtonStyle.success,
            disabled=True,
            row=3
        )
        self.register_button.callback = self.register_recruitment_callback
        self.add_item(self.register_button)

    def _generate_time_options(self) -> list:
        """시간 선택 옵션 생성 (커스텀 입력 옵션 포함)"""
        options = [
            # 기존 인기 시간대들
            discord.SelectOption(label="오후 5시 (17:00)", value="17:00", emoji="🕕"),
            discord.SelectOption(label="오후 6시 (18:00)", value="18:00", emoji="🕕"),
            discord.SelectOption(label="오후 7시 (19:00)", value="19:00", emoji="🕕"),
            discord.SelectOption(label="오후 8시 (20:00)", value="20:00", emoji="🕕"),
            discord.SelectOption(label="오후 9시 (21:00)", value="21:00", emoji="🕕"),
            discord.SelectOption(label="오후 10시 (22:00)", value="22:00", emoji="🕕"),
            discord.SelectOption(label="오후 11시 (23:00)", value="23:00", emoji="🕕"),
            discord.SelectOption(label="자정 (00:00)", value="00:00", emoji="🕕"),
            
            # 커스텀 시간 입력 옵션 (맨 마지막)
            discord.SelectOption(
                label="🛠️ 직접 입력하기", 
                value="custom_time", 
                emoji="⏰",
                description="원하는 시간을 직접 입력합니다"
            ),
        ]
        return options
    
    def _generate_deadline_options(self) -> list:
        """마감시간 옵션 생성 (커스텀 입력 옵션 포함)"""
        options = [
            discord.SelectOption(
                label="🔥 내전 10분 전 (깜짝 내전)", 
                value="10min_before", 
                emoji="⚡",
                description="긴급 모집용"
            ),
            discord.SelectOption(
                label="🔥 내전 30분 전 (깜짝 내전)", 
                value="30min_before", 
                emoji="⚡",
                description="빠른 모집용"
            ),
            discord.SelectOption(label="내전 1시간 전", value="1hour_before", emoji="⏰"),
            discord.SelectOption(label="내전 2시간 전", value="2hour_before", emoji="⏰"),
            discord.SelectOption(label="내전 3시간 전", value="3hour_before", emoji="⏰"),
            discord.SelectOption(label="내전 하루 전", value="1day_before", emoji="⏰"),
            discord.SelectOption(label="내전 당일 오후 3시", value="same_day_3pm", emoji="⏰"),
            discord.SelectOption(label="내전 당일 오후 4시", value="same_day_4pm", emoji="⏰"),
            discord.SelectOption(label="내전 당일 오후 5시", value="same_day_5pm", emoji="⏰"),
            discord.SelectOption(label="내전 당일 오후 6시", value="same_day_6pm", emoji="⏰"),
            discord.SelectOption(label="내전 6시간 전", value="6hour_before", emoji="⏰"),
            discord.SelectOption(label="내전 12시간 전", value="12hour_before", emoji="⏰"),
            
            # 커스텀 마감시간 입력 옵션 (맨 마지막)
            discord.SelectOption(
                label="🛠️ 정확한 시간 입력", 
                value="custom_deadline", 
                emoji="📅",
                description="정확한 날짜와 시간을 직접 입력합니다"
            ),
        ]
        return options

    async def select_date_callback(self, interaction: discord.Interaction):
        """날짜 선택 처리"""
        self.selected_date = self.date_select.values[0]
        self.time_select.disabled = False
        
        # 선택된 날짜 정보 표시
        selected_date_info = next(
            (opt.description for opt in self.date_select.options if opt.value == self.selected_date),
            self.selected_date
        )
        
        await interaction.response.edit_message(
            content=f"✅ **날짜 선택됨**: {selected_date_info}\n📅 이제 내전 시간을 선택해주세요:",
            view=self
        )

    async def select_time_callback(self, interaction: discord.Interaction):
        """시간 선택 콜백"""
        selected_value = self.time_select.values[0]
        
        if selected_value == "custom_time":
            modal = CustomTimeModal(self)
            await interaction.response.send_modal(modal)
        else:
            self.selected_time = selected_value

            self._update_ui_state()
            
            # UI 업데이트
            await interaction.response.edit_message(
                content=f"✅ 선택된 시간: **{self._format_display_time(selected_value)}**\n"
                       f"이제 모집 마감시간을 선택해주세요.",
                view=self
            )
            
    def _update_ui_state(self):
        """UI 상태 업데이트 - 수정됨"""
        print(f"DEBUG: _update_ui_state 호출됨")
        print(f"DEBUG: selected_date={self.selected_date}, selected_time={self.selected_time}, selected_deadline={self.selected_deadline}")
        
        # 날짜와 시간이 모두 선택되었으면 마감시간 드롭다운 활성화
        if self.selected_date and self.selected_time:
            self.deadline_select.disabled = False
            print(f"DEBUG: 마감시간 드롭다운 활성화됨")
        
        # 모든 정보가 설정되었으면 등록 버튼 활성화
        if self.selected_date and self.selected_time and self.selected_deadline:
            self.register_button.disabled = False
            print(f"DEBUG: 등록 버튼 활성화됨")

    def _format_display_time(self, time_str: str) -> str:
        """시간 표시 형식 개선"""
        time_map = {
            "17:00": "오후 5시", "18:00": "오후 6시", "19:00": "오후 7시",
            "20:00": "오후 8시", "21:00": "오후 9시", "22:00": "오후 10시",
            "23:00": "오후 11시", "00:00": "자정", "13:00": "오후 1시",
            "14:00": "오후 2시", "15:00": "오후 3시", "16:00": "오후 4시"
        }
        return time_map.get(time_str, time_str)
    
    def _format_deadline_display(self, deadline_value: str) -> str:
        """마감시간 표시 형식 개선"""
        deadline_map = {
            "1day_before": "내전 하루 전",
            "3hour_before": "내전 3시간 전", 
            "2hour_before": "내전 2시간 전",
            "1hour_before": "내전 1시간 전",
            "same_day_5pm": "내전 당일 오후 5시",
            "same_day_6pm": "내전 당일 오후 6시",
            "same_day_3pm": "내전 당일 오후 3시",
            "same_day_4pm": "내전 당일 오후 4시",
            "6hour_before": "내전 6시간 전",
            "12hour_before": "내전 12시간 전"
        }
        return deadline_map.get(deadline_value, deadline_value)

    async def select_deadline_callback(self, interaction: discord.Interaction):
        """마감시간 선택 콜백 (커스텀 입력 지원)"""
        selected_value = self.deadline_select.values[0]
        
        if selected_value == "custom_deadline":
            # 커스텀 마감시간 입력 Modal 띄우기
            modal = CustomDeadlineModal(self)
            await interaction.response.send_modal(modal)
        else:
            self.selected_deadline = selected_value
            
            self._update_ui_state()
            
            await interaction.response.edit_message(
                content=f"✅ **날짜**: {self.selected_date}\n"
                       f"✅ **시간**: {self.selected_time}\n"
                       f"✅ **마감**: {self._format_deadline_display(selected_value)}\n\n"
                       f"🎯 모든 정보가 설정되었습니다! 등록 버튼을 눌러주세요.",
                view=self
            )
            
            self._update_ui_state()

    async def register_recruitment_callback(self, interaction: discord.Interaction):
        """최종 등록 처리"""
        await interaction.response.defer()
        
        try:
            # 날짜/시간 계산
            scrim_datetime = self._calculate_datetime()
            deadline_datetime = self._calculate_deadline(scrim_datetime)
            
            # 유효성 검사
            if scrim_datetime <= datetime.now():
                await interaction.followup.send(
                    "❌ 내전 시간은 현재 시간보다 미래여야 합니다.", ephemeral=True
                )
                return
            
            if deadline_datetime >= scrim_datetime:
                await interaction.followup.send(
                    "❌ 마감시간은 내전 시간보다 빨라야 합니다.", ephemeral=True
                )
                return
            
            channel = self.bot.get_channel(int(self.channel_id))
        
            if not channel:
                await interaction.followup.send(
                    f"❌ 채널을 찾을 수 없습니다.\n"
                    f"채널 ID: `{self.channel_id}`\n\n"
                    f"💡 `/내전공지채널설정` 명령어로 채널을 다시 설정해주세요.",
                    ephemeral=True
                )
                return

            bot_permissions = channel.permissions_for(channel.guild.me)
        
            if not bot_permissions.view_channel:
                await interaction.followup.send(
                    f"❌ {channel.mention} 채널을 볼 수 없습니다.\n\n"
                    f"**필요한 권한:** 채널 보기\n"
                    f"봇의 역할 설정에서 해당 채널에 대한 '채널 보기' 권한을 부여해주세요.",
                    ephemeral=True
                )
                return

            if not bot_permissions.send_messages:
                await interaction.followup.send(
                    f"❌ {channel.mention} 채널에 메시지를 보낼 권한이 없습니다.\n\n"
                    f"**필요한 권한:** 메시지 보내기\n"
                    f"봇의 역할 설정에서 해당 채널에 대한 '메시지 보내기' 권한을 부여해주세요.",
                    ephemeral=True
                )
                return
            
            if not bot_permissions.embed_links:
                await interaction.followup.send(
                    f"❌ {channel.mention} 채널에 임베드를 보낼 권한이 없습니다.\n\n"
                    f"**필요한 권한:** 링크 첨부\n"
                    f"봇의 역할 설정에서 해당 채널에 대한 '링크 첨부' 권한을 부여해주세요.",
                    ephemeral=True
                )
                return
        
            # 데이터베이스에 저장
            recruitment_id = await self.bot.db_manager.create_scrim_recruitment(
                guild_id=str(interaction.guild_id),
                title=self.title,
                description=self.content,
                scrim_date=scrim_datetime,  
                deadline=deadline_datetime,
                created_by=str(interaction.user.id)
            )
            
            if not recruitment_id:
                await interaction.followup.send(
                    "❌ 모집 등록 중 오류가 발생했습니다.", ephemeral=True
                )
                return
            
            # 모집 공지 메시지 생성 및 전송
            embed, view = self._create_recruitment_embed_and_view(
                recruitment_id, scrim_datetime, deadline_datetime
            )
            
            channel = self.bot.get_channel(int(self.channel_id))

            if channel:
                message = await channel.send(embed=embed, view=view)
            
                result = await self.bot.db_manager.update_recruitment_message_info(
                    recruitment_id, str(message.id), str(channel.id)
                )

                self.bot.add_view(view)

                dm_stats = await self._send_dm_notifications(
                    interaction.guild, recruitment_id, embed, scrim_datetime
                )
                
                await interaction.followup.send(
                    f"✅ **{self.title}** 내전 모집이 성공적으로 등록되었습니다!\n"
                    f"📅 **일시**: {scrim_datetime.strftime('%Y년 %m월 %d일 %H:%M')}\n"
                    f"⏰ **마감**: {deadline_datetime.strftime('%Y년 %m월 %d일 %H:%M')}\n\n"
                    f"🔔 **DM 알림 결과**: {dm_stats['success']}명 성공, {dm_stats['failed']}명 실패",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ 설정된 채널을 찾을 수 없습니다.", ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 등록 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    async def _send_dm_notifications(self, guild: discord.Guild, recruitment_id: str,
                                     embed: discord.Embed, scrim_datetime: datetime) -> dict:
        """서버 멤버들에게 내전 모집 DM 알림 전송"""
        success_count = 0
        failed_count = 0

        try:
            print(f"🔔 {guild.name} 서버 멤버들에게 내전 모집 DM 알림 전송을 시작합니다...")

            members = [member for member in guild.members if not member.bot]
            print(f"대상 멤버 수: {len(members)}명 (봇 제외)")

            # DM 용 임베드 생성
            dm_embed = await self._create_dm_notification_embed(embed, guild, scrim_datetime)

            import asyncio

            async def send_single_dm(member):
                nonlocal success_count, failed_count
                try:
                    await member.send(embed=dm_embed)
                    success_count += 1
                    print(f"✅ {member.display_name}님에게 DM 알림 전송 성공")
                except discord.Forbidden:
                    failed_count += 1
                    print(f"❌ {member.display_name}님에게 DM 알림 전송 실패 (DM 차단)")
                except discord.HTTPException as e:
                    failed_count += 1
                    print(f"❌ {member.display_name}님에게 DM 알림 전송 실패 (HTTP 오류: {str(e)})")
                except Exception as e:
                    failed_count += 1
                    print(f"❌ {member.display_name}님에게 DM 알림 전송 실패 (기타 오류: {str(e)})")

                await asyncio.sleep(0.1)

            tasks = [send_single_dm(member) for member in members]
            await asyncio.gather(*tasks, return_exceptions=True)

            print(f"🔔 DM 알림 전송 완료: 성공 {success_count}명, 실패 {failed_count}명")

            return {
                'success': success_count,
                'failed': failed_count,
                'total': len(members)
            }

        except Exception as e:
            print("❌ DM 알림 전송 중 오류 발생:", str(e))
            return {
                'success': success_count,
                'failed': failed_count,
                'total': len(members)
            }

    async def _create_dm_notification_embed(self, original_embed: discord.Embed, 
                                           guild: discord.Guild, scrim_datetime: datetime) -> discord.Embed:
        """DM 알림용 임베드 생성"""
        dm_embed = discord.Embed(
            title=f"🎮 새로운 내전 모집 알림",
            description=f"**{guild.name}** 서버에서 새로운 내전 모집이 등록되었습니다!",
            color=0x00ff88,
            timestamp=datetime.utcnow()
        )       

        dm_embed.add_field(
            name="📅 내전 제목",
            value=self.title,
            inline=False
        )

        dm_embed.add_field(
            name="📝 상세 내용",
            value=self.content or "내전 참가자를 모집합니다!",
            inline=False
        )

        dm_embed.add_field(
            name="📅 일정",
            value=f"**내전 일시**: {scrim_datetime.strftime('%Y년 %m월 %d일 (%A) %H:%M')}\n"
                  f"**모집 마감**: {self._calculate_deadline(scrim_datetime).strftime('%Y년 %m월 %d일 %H:%M')}",
            inline=False
        )

        dm_embed.add_field(
            name="🍬 참여 방법",
            value=f"**{guild.name}** 서버의 내전 채널로 이동해서\n"
                   "모집 공지의 버튼을 클릭하여 참가/불참을 표시해주세요!",
            inline=False
        )

        dm_embed.add_field(
            name="⚡️ 빠른 참여",
            value="서버에서 해당 모집글을 찾아 **참가** 버튼을 눌러주세요!",
            inline=False
        )

        dm_embed.set_footer(
            text=f"{guild.name} | RallyUp Bot",
            icon_url=guild.icon.url if guild.icon else None
        )

        return dm_embed
    
    def _calculate_datetime(self) -> datetime:
        """선택된 날짜/시간을 datetime 객체로 변환"""
        now = datetime.now()
        time_parts = self.selected_time.split(':')
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        # 날짜 계산 - 명확하고 예측 가능한 로직
        if self.selected_date == "today":
            target_date = now.date()
        elif self.selected_date == "tomorrow":
            target_date = (now + timedelta(days=1)).date()
        elif self.selected_date == "day_after_tomorrow":
            target_date = (now + timedelta(days=2)).date()
        elif self.selected_date == "upcoming_friday":
            target_date = get_upcoming_weekday(4).date()
        elif self.selected_date == "upcoming_saturday":
            target_date = get_upcoming_weekday(5).date()
        elif self.selected_date == "upcoming_sunday":
            target_date = get_upcoming_weekday(6).date()
        elif self.selected_date == "next_friday":
            target_date = get_next_week_weekday(4).date()
        elif self.selected_date == "next_saturday":
            target_date = get_next_week_weekday(5).date()
        elif self.selected_date == "next_sunday":
            target_date = get_next_week_weekday(6).date()
        else:
            # 기본값: 오늘
            target_date = now.date()
        
        return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))
    
    def _calculate_deadline(self, scrim_datetime: datetime) -> datetime:
        """마감시간 계산 (깜짝 내전 지원)"""
        if self.selected_deadline.startswith("custom_datetime_"):
            # 커스텀 날짜시간 파싱
            iso_string = self.selected_deadline.replace("custom_datetime_", "")
            return datetime.fromisoformat(iso_string)
        
        deadline_map = {
            "10min_before": timedelta(minutes=10),
            "30min_before": timedelta(minutes=30),
            
            "1hour_before": timedelta(hours=1),
            "2hour_before": timedelta(hours=2),
            "3hour_before": timedelta(hours=3),
            "6hour_before": timedelta(hours=6),
            "12hour_before": timedelta(hours=12),
            "1day_before": timedelta(days=1),
            
            "same_day_3pm": None,
            "same_day_4pm": None,
            "same_day_5pm": None,
            "same_day_6pm": None
        }
        
        if self.selected_deadline in ["same_day_3pm", "same_day_4pm", "same_day_5pm", "same_day_6pm"]:
            # 당일 특정 시간
            hour_map = {
                "same_day_3pm": 15, 
                "same_day_4pm": 16,
                "same_day_5pm": 17, 
                "same_day_6pm": 18
            }
            hour = hour_map[self.selected_deadline]
            return datetime.combine(scrim_datetime.date(), datetime.min.time().replace(hour=hour))
        else:
            # 상대적 시간
            delta = deadline_map.get(self.selected_deadline, timedelta(hours=1))
            return scrim_datetime - delta
    
    def _create_recruitment_embed_and_view(self, recruitment_id: str, 
                                               scrim_datetime: datetime, 
                                               deadline_datetime: datetime):
        """모집 임베드와 뷰 생성"""
        from commands.scrim_recruitment import RecruitmentView 
        
        embed = discord.Embed(
            title=f"🎮 {self.title}",
            description=self.content,
            color=0x0099ff
        )
        
        embed.add_field(
            name="📅 내전 일시",
            value=scrim_datetime.strftime('%Y년 %m월 %d일 (%A) %H:%M'),
            inline=True
        )
        
        embed.add_field(
            name="⏰ 모집 마감", 
            value=deadline_datetime.strftime('%Y년 %m월 %d일 (%A) %H:%M'),
            inline=True
        )
        
        embed.add_field(
            name="👥 참가 현황",
            value="참가: 0명 | 불참: 0명",
            inline=False
        )
                
        view = RecruitmentView(self.bot, recruitment_id)
        
        return embed, view

class JoinButton(discord.ui.Button):
    def __init__(self, recruitment_id: str):
        super().__init__(
            label="✅ 참가",
            style=discord.ButtonStyle.success,
            custom_id=f"join_scrim_{recruitment_id}"
        )
        self.recruitment_id = recruitment_id

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if hasattr(view, '_handle_participation'):
            await view._handle_participation(interaction, "joined")
        else:
            await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)

class DeclineButton(discord.ui.Button):
    def __init__(self, recruitment_id: str):
        super().__init__(
            label="❌ 불참",
            style=discord.ButtonStyle.danger,
            custom_id=f"decline_scrim_{recruitment_id}"
        )
        self.recruitment_id = recruitment_id

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if hasattr(view, '_handle_participation'):
            await view._handle_participation(interaction, "declined")
        else:
            await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)

class LateJoinButton(discord.ui.Button):
    def __init__(self, recruitment_id: str):
        super().__init__(
            label="⏰ 늦참",
            style=discord.ButtonStyle.primary,
            custom_id=f"late_join_scrim_{recruitment_id}"
        )
        self.recruitment_id = recruitment_id

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if hasattr(view, '_handle_participation'):
            await view._handle_participation(interaction, "late_join")
        else:
            await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)

class ParticipantsButton(discord.ui.Button):
    def __init__(self, recruitment_id: str):
        super().__init__(
            label="📋 참가자 목록",
            style=discord.ButtonStyle.secondary,
            custom_id=f"show_participants_{recruitment_id}"
        )
        self.recruitment_id = recruitment_id

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if hasattr(view, '_show_participants_list'):
            await view._show_participants_list(interaction)
        else:
            await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)

class RecruitmentView(discord.ui.View):
    """내전 모집 참가/불참 버튼 View"""
    
    def __init__(self, bot, recruitment_id: str):
        super().__init__(timeout=None)  # 시간 제한 없음 (마감시간까지 유효)
        self.bot = bot
        self.recruitment_id = recruitment_id

        self.add_item(JoinButton(recruitment_id))
        self.add_item(DeclineButton(recruitment_id))
        self.add_item(LateJoinButton(recruitment_id))
        self.add_item(ParticipantsButton(recruitment_id))
    
    async def _handle_participation(self, interaction: discord.Interaction, status: str):
        """참가/불참 처리 공통 로직"""
        await interaction.response.defer()
        
        try:
            # 1. 모집 정보 조회
            recruitment = await self.bot.db_manager.get_recruitment_by_id(self.recruitment_id)
            if not recruitment:
                await interaction.followup.send(
                    "❌ 모집 정보를 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            if recruitment['status'] != 'active':
                await interaction.followup.send(
                    "❌ 취소되었거나 마감된 모집입니다.", ephemeral=True
                )
                return
            
            # 2. 모집 마감 확인
            deadline = datetime.fromisoformat(recruitment['deadline'])
            if datetime.now() > deadline:
                await interaction.followup.send(
                    "❌ 이미 마감된 모집입니다.", ephemeral=True
                )
                return
            
            # 3. 참가자 정보 저장
            success = await self.bot.db_manager.add_recruitment_participant(
                self.recruitment_id,
                str(interaction.user.id),
                interaction.user.display_name,
                status
            )
            
            if not success:
                await interaction.followup.send(
                    "❌ 참가 정보 저장 중 오류가 발생했습니다.", ephemeral=True
                )
                return
            
            # 4. 메시지 업데이트
            await self._update_recruitment_message(interaction)
            
            if status == "joined":
                status_text = "참가"
            elif status == "declined":
                status_text = "불참"
            elif status == "late_join":
                status_text = "늦참"
            else:
                status_text = status

            await interaction.followup.send(
                f"✅ **{recruitment['title']}** 내전 모집에 **{status_text}**로 등록되었습니다!",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 처리 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    
    async def _show_participants_list(self, interaction: discord.Interaction):
        """참가자 목록 표시"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 모집 정보 및 참가자 목록 조회
            recruitment = await self.bot.db_manager.get_recruitment_by_id(self.recruitment_id)
            if not recruitment:
                await interaction.followup.send(
                    "❌ 모집 정보를 찾을 수 없습니다.", ephemeral=True
                )
                return

            if recruitment['status'] != 'active':
                await interaction.followup.send(
                    "❌ 취소되었거나 마감된 모집입니다.", ephemeral=True
                )
                return
            
            participants = await self.bot.db_manager.get_recruitment_participants(self.recruitment_id)
            joined_users = [p for p in participants if p['status'] == 'joined']
            late_join_users = [p for p in participants if p['status'] == 'late_join']
            declined_users = [p for p in participants if p['status'] == 'declined']
            
            # 임베드 생성
            embed = discord.Embed(
                title=f"📋 {recruitment['title']} - 참가자 목록",
                color=0x0099ff
            )
            
            scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
            embed.add_field(
                name="📅 내전 일시",
                value=scrim_date.strftime('%Y년 %m월 %d일 (%A) %H:%M'),
                inline=False
            )
            
            # 참가자 목록
            if joined_users:
                joined_list = [f"{i}. {user['username']}" for i, user in enumerate(joined_users, 1)]
                embed.add_field(
                    name=f"✅ 참가자 ({len(joined_users)}명)",
                    value='\n'.join(joined_list),
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ 참가자 (0명)",
                    value="아직 참가자가 없습니다.",
                    inline=False
                )

            if late_join_users:
                late_join_list = [f"{i}. {user['username']}" for i, user in enumerate(late_join_users, 1)]
                embed.add_field(
                    name=f"⏰ 늦참자 ({len(late_join_users)}명)",
                    value='\n'.join(late_join_list),
                    inline=False
                )
            
            # 불참자 목록 (간략하게)
            if declined_users:
                embed.add_field(
                    name=f"❌ 불참자 ({len(declined_users)}명)",
                    value="(목록 생략)" if len(declined_users) > 5 else ", ".join([u['username'] for u in declined_users]),
                    inline=False
                )
            
            embed.set_footer(text=f"모집 ID: {self.recruitment_id}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 참가자 목록 조회 중 오류가 발생했습니다: {str(e)}", 
                ephemeral=True
            )
    
    async def _update_recruitment_message(self, interaction: discord.Interaction):
        """모집 메시지 업데이트 (참가자 수 실시간 반영, 늦참자 포함)"""
        try:
            recruitment = await self.bot.db_manager.get_recruitment_by_id(self.recruitment_id)
            participants = await self.bot.db_manager.get_recruitment_participants(self.recruitment_id)
            
            joined_count = len([p for p in participants if p['status'] == 'joined'])
            late_join_count = len([p for p in participants if p['status'] == 'late_join']) 
            declined_count = len([p for p in participants if p['status'] == 'declined'])
            
            # 업데이트된 임베드 생성
            scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
            deadline = datetime.fromisoformat(recruitment['deadline'])
            
            # 상태에 따른 색상 및 텍스트
            if datetime.now() > deadline:
                status_text = "🔒 모집 마감"
                color = 0x666666
            else:
                status_text = "🟢 모집 중"
                color = 0x0099ff
            
            embed = discord.Embed(
                title=f"🎮 {recruitment['title']}",
                description=f"{recruitment['description']}\n",
                color=color
            )
            
            embed.add_field(
                name="📅 내전 일시",
                value=scrim_date.strftime('%Y년 %m월 %d일 (%A) %H:%M'),
                inline=True
            )
            
            embed.add_field(
                name="⏰ 모집 마감",
                value=deadline.strftime('%Y년 %m월 %d일 (%A) %H:%M'),
                inline=True
            )
            
            embed.add_field(
                name="📊 현재 상황",
                value=status_text,
                inline=True
            )
            
            # 참가 현황 (시각적 바 포함)
            participation_bar = self._create_participation_bar(joined_count, late_join_count, declined_count)
            embed.add_field(
                name="👥 참가 현황",
                value=f"✅ **참가**: {joined_count}명\n"
                    f"⏰ **늦참**: {late_join_count}명\n"
                    f"❌ **불참**: {declined_count}명\n"
                    f"{participation_bar}",
                inline=False
            )
            
            embed.set_footer(text=f"모집 ID: {recruitment['id']} | 버튼을 눌러 참가 의사를 표시하세요!")
            
            # 원본 메시지 업데이트
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            print(f"❌ 모집 메시지 업데이트 실패: {e}")
    
    async def _create_updated_embed(self, recruitment: dict, joined_count: int, declined_count: int):
        """업데이트된 임베드 생성"""
        scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
        deadline = datetime.fromisoformat(recruitment['deadline'])
        
        # 마감까지 남은 시간 계산
        now = datetime.now()
        if now < deadline:
            time_left = deadline - now
            if time_left.days > 0:
                time_left_str = f"{time_left.days}일 {time_left.seconds//3600}시간"
            else:
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60
                time_left_str = f"{hours}시간 {minutes}분"
            status_color = 0x00ff00  # 초록색
            status_text = f"⏰ 마감까지: {time_left_str}"
        else:
            status_color = 0xff6b6b  # 빨간색  
            status_text = "🔒 모집 마감"
        
        embed = discord.Embed(
            title=f"🎮 {recruitment['title']}",
            description=recruitment['description'] or "이번주 정기 내전에 참가해주세요!",
            color=status_color,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📅 내전 일시",
            value=scrim_date.strftime('%Y년 %m월 %d일 (%A) %H:%M'),
            inline=True
        )
        
        embed.add_field(
            name="⏰ 모집 마감",
            value=deadline.strftime('%Y년 %m월 %d일 %H:%M'),
            inline=True
        )
        
        embed.add_field(
            name="📊 현재 상황",
            value=status_text,
            inline=True
        )
        
        # 참가자 현황 - 시각적으로 개선
        participation_bar = self._create_participation_bar(joined_count, declined_count)
        embed.add_field(
            name="👥 참가 현황",
            value=f"✅ **참가**: {joined_count}명\n"
                  f"❌ **불참**: {declined_count}명\n"
                  f"{participation_bar}",
            inline=False
        )
        
        embed.set_footer(text=f"모집 ID: {recruitment['id']} | 버튼을 눌러 참가 의사를 표시하세요!")
        
        return embed
    
    def _create_participation_bar(self, joined_count, late_join_count, declined_count):
        """참가 현황 시각적 바 생성"""
        total = joined_count + late_join_count + declined_count
        if total == 0:
            return "📊 `아직 응답이 없습니다`"
        
        # 비율 계산
        joined_ratio = joined_count / total
        late_join_ratio = late_join_count / total
        
        # 바 생성 (총 10칸)
        bar_length = 10
        joined_bars = int(joined_ratio * bar_length)
        late_join_bars = int(late_join_ratio * bar_length)
        declined_bars = bar_length - joined_bars - late_join_bars
        
        bar = "🟢" * joined_bars + "🟡" * late_join_bars + "🔴" * declined_bars
        
        return f"📊 `{bar}` ({total}명 응답)"

class AutoScrimSetupModal(discord.ui.Modal):
    """정기 내전 설정을 위한 Modal"""
    
    def __init__(self, bot, channel_id: str):
        super().__init__(title="🤖 정기 내전 자동 스케줄 설정")
        self.bot = bot
        self.channel_id = channel_id
        
        # 스케줄 이름
        self.schedule_name_input = discord.ui.TextInput(
            label="스케줄 이름",
            placeholder="예: 금요정기내전, 주말내전",
            required=True,
            max_length=50
        )
        self.add_item(self.schedule_name_input)
        
        # 모집 제목
        self.title_input = discord.ui.TextInput(
            label="모집 제목",
            placeholder="예: 금요일 정기 내전, 주말 내전",
            required=True,
            max_length=100
        )
        self.add_item(self.title_input)
        
        # 모집 설명
        self.description_input = discord.ui.TextInput(
            label="모집 설명 (선택)",
            placeholder="예: 매주 금요일 밤 9시 정기 내전입니다!",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        self.add_item(self.description_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Modal 제출 시 요일/시간 선택 단계로 진행"""
        
        schedule_name = self.schedule_name_input.value
        title = self.title_input.value
        description = self.description_input.value or f"{title} 참가자를 모집합니다!"
        
        # 중복 이름 체크
        guild_id = str(interaction.guild_id)
        existing_schedules = await self.bot.db_manager.get_auto_schedules(guild_id)
        
        if any(s['schedule_name'] == schedule_name for s in existing_schedules):
            await interaction.response.send_message(
                f"❌ 이미 **{schedule_name}** 이름의 스케줄이 존재합니다.\n"
                f"다른 이름을 사용해주세요.",
                ephemeral=True
            )
            return
        
        # 선택 View 생성
        view = AutoScrimConfigView(
            self.bot,
            self.channel_id,
            schedule_name,
            title,
            description
        )
        
        await interaction.response.send_message(
            "📅 **정기 내전 설정**\n아래에서 내전 요일, 시간, 마감시간을 선택해주세요:",
            view=view,
            ephemeral=True
        )

class AutoScrimConfigView(discord.ui.View):
    """정기 내전 설정을 위한 View (요일/시간/마감 선택)"""
    
    def __init__(self, bot, channel_id: str, schedule_name: str, title: str, description: str):
        super().__init__(timeout=600)
        self.bot = bot
        self.channel_id = channel_id
        self.schedule_name = schedule_name
        self.title = title
        self.description = description
        
        self.selected_weekday = None
        self.selected_time = None
        self.selected_post_timing = None  # 🆕
        self.selected_recurrence = None  # 🆕
        self.selected_deadline = None
        self.reminder_enabled = False  # 🆕
        
        self._setup_ui()
    
    def _setup_ui(self):
        """UI 초기 설정"""
        # 1. 요일 선택
        self.weekday_select = discord.ui.Select(
            placeholder="📅 내전 요일을 선택하세요",
            options=self._generate_weekday_options(),
            custom_id="weekday_select",
            row=0
        )
        self.weekday_select.callback = self.weekday_callback
        self.add_item(self.weekday_select)
        
        # 2. 시간 선택 (비활성)
        self.time_select = discord.ui.Select(
            placeholder="⏰ 먼저 요일을 선택하세요",
            options=[discord.SelectOption(label="요일을 먼저 선택하세요", value="placeholder")],
            disabled=True,
            custom_id="time_select",
            row=1
        )
        self.time_select.callback = self.time_callback
        self.add_item(self.time_select)
        
        # 3. 🆕 공지 등록 시점 (비활성)
        self.post_timing_select = discord.ui.Select(
            placeholder="📢 먼저 시간을 선택하세요",
            options=[discord.SelectOption(label="시간을 먼저 선택하세요", value="placeholder")],
            disabled=True,
            custom_id="post_timing_select",
            row=2
        )
        self.post_timing_select.callback = self.post_timing_callback
        self.add_item(self.post_timing_select)
        
        # 4. 🆕 반복 주기 (비활성)
        self.recurrence_select = discord.ui.Select(
            placeholder="🔁 먼저 등록 시점을 선택하세요",
            options=[discord.SelectOption(label="등록 시점을 먼저 선택하세요", value="placeholder")],
            disabled=True,
            custom_id="recurrence_select",
            row=3
        )
        self.recurrence_select.callback = self.recurrence_callback
        self.add_item(self.recurrence_select)
        
        # 5. 마감시간 선택 (비활성)
        self.deadline_select = discord.ui.Select(
            placeholder="⏰ 먼저 반복 주기를 선택하세요",
            options=[discord.SelectOption(label="반복 주기를 먼저 선택하세요", value="placeholder")],
            disabled=True,
            custom_id="deadline_select",
            row=4
        )
        self.deadline_select.callback = self.deadline_callback
        self.add_item(self.deadline_select)
    
    def _generate_weekday_options(self) -> list:
        """요일 옵션 생성"""
        weekdays = [
            ("월요일", 0, "🌙"),
            ("화요일", 1, "🔥"),
            ("수요일", 2, "💧"),
            ("목요일", 3, "🌳"),
            ("금요일", 4, "🎉"),
            ("토요일", 5, "🌈"),
            ("일요일", 6, "☀️")
        ]
        
        return [
            discord.SelectOption(
                label=name,
                value=str(value),
                emoji=emoji,
                description=f"매주 {name}마다 자동 등록"
            )
            for name, value, emoji in weekdays
        ]
    
    def _generate_time_options(self) -> list:
        """시간 옵션 생성"""
        times = []
        
        for hour in range(17, 24):
            times.append(
                discord.SelectOption(
                    label=f"{hour:02d}:00",
                    value=f"{hour:02d}:00",
                    emoji="🌙"
                )
            )
            times.append(
                discord.SelectOption(
                    label=f"{hour:02d}:30",
                    value=f"{hour:02d}:30",
                    emoji="🌙"
                )
            )
        
        for hour in range(0, 3):
            times.append(
                discord.SelectOption(
                    label=f"{hour:02d}:00",
                    value=f"{hour:02d}:00",
                    emoji="🌃"
                )
            )
        
        times.append(
            discord.SelectOption(
                label="🛠️ 직접 입력하기",
                value="custom_time",
                emoji="⏰"
            )
        )
        
        return times[:25]
    
    def _generate_post_timing_options(self) -> list:
        """공지 등록 시점 옵션"""
        return [
            discord.SelectOption(
                label="내전 당일 (오전 6시)",
                value="0",
                emoji="📅",
                description="내전 당일 아침에 공지 등록"
            ),
            discord.SelectOption(
                label="내전 1일 전 (오전 6시)",
                value="1",
                emoji="📅",
                description="하루 전에 미리 공지"
            ),
            discord.SelectOption(
                label="내전 2일 전 (오전 6시)",
                value="2",
                emoji="📅",
                description="이틀 전에 미리 공지"
            ),
            discord.SelectOption(
                label="내전 3일 전 (오전 6시)",
                value="3",
                emoji="📅",
                description="3일 전에 미리 공지"
            ),
            discord.SelectOption(
                label="내전 4일 전 (오전 6시)",
                value="4",
                emoji="📅",
                description="4일 전에 미리 공지"
            ),
            discord.SelectOption(
                label="내전 5일 전 (오전 6시)",
                value="5",
                emoji="📅",
                description="5일 전에 미리 공지"
            )
        ]
    
    def _generate_recurrence_options(self) -> list:
        """반복 주기 옵션"""
        return [
            discord.SelectOption(
                label="매주",
                value="1",
                emoji="🔁",
                description="매주 반복"
            ),
            discord.SelectOption(
                label="격주 (2주마다)",
                value="2",
                emoji="🔁",
                description="2주에 한 번씩"
            ),
            discord.SelectOption(
                label="3주마다",
                value="3",
                emoji="🔁",
                description="3주에 한 번씩"
            ),
            discord.SelectOption(
                label="매달 (4주마다)",
                value="4",
                emoji="📅",
                description="한 달에 한 번씩 (월례전)"
            )
        ]
    
    def _generate_deadline_options(self) -> list:
        """마감시간 옵션 생성"""
        return [
            discord.SelectOption(
                label="⚡ 내전 10분 전", 
                value="10min_before", 
                emoji="🔥"
            ),
            discord.SelectOption(
                label="⚡ 내전 30분 전", 
                value="30min_before", 
                emoji="🔥"
            ),
            discord.SelectOption(
                label="내전 1시간 전", 
                value="1hour_before", 
                emoji="⏰"
            ),
            discord.SelectOption(
                label="내전 3시간 전", 
                value="3hour_before", 
                emoji="⏰"
            ),
            discord.SelectOption(
                label="내전 6시간 전", 
                value="6hour_before", 
                emoji="⏰"
            ),
            discord.SelectOption(
                label="내전 하루 전", 
                value="1day_before", 
                emoji="⏰"
            ),
            discord.SelectOption(
                label="내전 당일 오후 5시", 
                value="same_day_5pm", 
                emoji="🕔"
            ),
            discord.SelectOption(
                label="내전 당일 오후 6시", 
                value="same_day_6pm", 
                emoji="🕕"
            ),
        ]
    
    async def weekday_callback(self, interaction: discord.Interaction):
        """요일 선택 콜백"""
        self.selected_weekday = int(self.weekday_select.values[0])
        
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        
        # 시간 선택 활성화
        self.time_select.placeholder = "⏰ 내전 시간을 선택하세요"
        self.time_select.options = self._generate_time_options()
        self.time_select.disabled = False
        
        await interaction.response.edit_message(
            content=f"✅ **{weekday_names[self.selected_weekday]}** 선택됨\n다음: 내전 시간 선택",
            view=self
        )
    
    async def time_callback(self, interaction: discord.Interaction):
        """시간 선택 콜백"""
        time_value = self.time_select.values[0]
        
        if time_value == "custom_time":
            modal = CustomAutoScrimTimeModal(self)
            await interaction.response.send_modal(modal)
            return
        
        self.selected_time = time_value
        
        # 🆕 공지 등록 시점 활성화
        self.post_timing_select.placeholder = "📢 공지 등록 시점을 선택하세요"
        self.post_timing_select.options = self._generate_post_timing_options()
        self.post_timing_select.disabled = False
        
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        
        await interaction.response.edit_message(
            content=f"✅ **{weekday_names[self.selected_weekday]} {self.selected_time}** 선택됨\n"
                   f"다음: 공지 등록 시점 선택",
            view=self
        )
    
    async def post_timing_callback(self, interaction: discord.Interaction):
        """🆕 공지 등록 시점 선택"""
        self.selected_post_timing = int(self.post_timing_select.values[0])
        
        # 반복 주기 활성화
        self.recurrence_select.placeholder = "🔁 반복 주기를 선택하세요"
        self.recurrence_select.options = self._generate_recurrence_options()
        self.recurrence_select.disabled = False
        
        timing_text = {
            0: "내전 당일",
            1: "내전 1일 전",
            2: "내전 2일 전",
            3: "내전 3일 전",
            4: "내전 4일 전",
            5: "내전 5일 전"
        }
        
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        
        await interaction.response.edit_message(
            content=f"✅ **{weekday_names[self.selected_weekday]} {self.selected_time}**\n"
                   f"✅ **{timing_text[self.selected_post_timing]} 오전 6시** 공지 등록\n"
                   f"다음: 반복 주기 선택",
            view=self
        )
    
    async def recurrence_callback(self, interaction: discord.Interaction):
        """🆕 반복 주기 선택"""
        self.selected_recurrence = int(self.recurrence_select.values[0])
        
        # 마감시간 활성화
        self.deadline_select.placeholder = "⏰ 모집 마감시간을 선택하세요"
        self.deadline_select.options = self._generate_deadline_options()
        self.deadline_select.disabled = False
        
        recurrence_text = {1: "매주", 2: "격주"}
        timing_text = {
            0: "내전 당일",
            1: "내전 1일 전",
            2: "내전 2일 전",
            3: "내전 3일 전",
            4: "내전 4일 전", 
            5: "내전 5일 전", 
        }
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        
        await interaction.response.edit_message(
            content=f"✅ **{recurrence_text[self.selected_recurrence]} {weekday_names[self.selected_weekday]} {self.selected_time}**\n"
                   f"✅ **{timing_text[self.selected_post_timing]} 오전 6시** 공지 등록\n"
                   f"다음: 모집 마감시간 선택",
            view=self
        )
    
    async def deadline_callback(self, interaction: discord.Interaction):
        """마감시간 선택 + 🆕 미응답자 독촉 버튼 추가"""
        self.selected_deadline = self.deadline_select.values[0]
        
        # 🆕 미응답자 독촉 버튼 추가
        self.clear_items()
        
        # 미응답자 독촉 토글 버튼
        reminder_button = discord.ui.Button(
            label="미응답자 독촉 알림: OFF",
            style=discord.ButtonStyle.secondary,
            emoji="🔔",
            custom_id="reminder_toggle"
        )
        reminder_button.callback = self.reminder_toggle_callback
        self.add_item(reminder_button)
        
        # 등록 버튼
        register_button = discord.ui.Button(
            label="등록하기",
            style=discord.ButtonStyle.success,
            emoji="✅",
            custom_id="register_button"
        )
        register_button.callback = self.register_callback
        self.add_item(register_button)
        
        deadline_map = {
            "10min_before": "내전 10분 전",
            "30min_before": "내전 30분 전",
            "1hour_before": "내전 1시간 전",
            "3hour_before": "내전 3시간 전",
            "6hour_before": "내전 6시간 전",
            "1day_before": "내전 하루 전",
            "same_day_5pm": "내전 당일 오후 5시",
            "same_day_6pm": "내전 당일 오후 6시"
        }
        
        recurrence_text = {1: "매주", 2: "격주"}
        timing_text = {
            0: "내전 당일",
            1: "내전 1일 전",
            2: "내전 2일 전",
            3: "내전 3일 전",
            4: "내전 4일 전",
            5: "내전 5일 전"
        }
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        
        await interaction.response.edit_message(
            content=f"📋 **설정 요약**\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"✅ **{recurrence_text[self.selected_recurrence]} {weekday_names[self.selected_weekday]} {self.selected_time}**\n"
                   f"✅ **{timing_text[self.selected_post_timing]} 오전 6시** 공지 등록\n"
                   f"✅ **{deadline_map.get(self.selected_deadline)}** 모집 마감\n"
                   f"━━━━━━━━━━━━━━━\n\n"
                   f"💡 **미응답자 독촉 알림**을 활성화하면\n"
                   f"마감 5시간 전, 아직 응답 안한 사람들에게만 DM을 발송합니다.\n\n"
                   f"설정을 완료하려면 **등록하기** 버튼을 눌러주세요!",
            view=self
        )
    
    async def reminder_toggle_callback(self, interaction: discord.Interaction):
        """🆕 미응답자 독촉 토글"""
        self.reminder_enabled = not self.reminder_enabled
        
        # 버튼 텍스트 업데이트
        for item in self.children:
            if item.custom_id == "reminder_toggle":
                if self.reminder_enabled:
                    item.label = "미응답자 독촉 알림: ON"
                    item.style = discord.ButtonStyle.success
                else:
                    item.label = "미응답자 독촉 알림: OFF"
                    item.style = discord.ButtonStyle.secondary
        
        deadline_map = {
            "10min_before": "내전 10분 전",
            "30min_before": "내전 30분 전",
            "1hour_before": "내전 1시간 전",
            "3hour_before": "내전 3시간 전",
            "6hour_before": "내전 6시간 전",
            "1day_before": "내전 하루 전",
            "same_day_5pm": "내전 당일 오후 5시",
            "same_day_6pm": "내전 당일 오후 6시"
        }
        
        recurrence_text = {1: "매주", 2: "격주"}
        timing_text = {
            0: "내전 당일",
            1: "내전 1일 전",
            2: "내전 2일 전",
            3: "내전 3일 전",
            4: "내전 4일 전", 
            5: "내전 5일 전",
        }
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        
        reminder_status = "🔔 **활성화** (마감 5시간 전 미응답자에게 DM)" if self.reminder_enabled else "🔕 비활성화"
        
        await interaction.response.edit_message(
            content=f"📋 **설정 요약**\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"✅ **{recurrence_text[self.selected_recurrence]} {weekday_names[self.selected_weekday]} {self.selected_time}**\n"
                   f"✅ **{timing_text[self.selected_post_timing]} 오전 6시** 공지 등록\n"
                   f"✅ **{deadline_map.get(self.selected_deadline)}** 모집 마감\n"
                   f"✅ **미응답자 독촉**: {reminder_status}\n"
                   f"━━━━━━━━━━━━━━━\n\n"
                   f"설정을 완료하려면 **등록하기** 버튼을 눌러주세요!",
            view=self
        )
    
    async def register_callback(self, interaction: discord.Interaction):
        """최종 등록 처리"""
        await interaction.response.defer()
        
        try:
            guild_id = str(interaction.guild_id)
            
            # DB에 저장
            success = await self.bot.db_manager.create_auto_schedule(
                guild_id=guild_id,
                schedule_name=self.schedule_name,
                day_of_week=self.selected_weekday,
                scrim_time=self.selected_time,
                recruitment_title=self.title,
                recruitment_description=self.description,
                deadline_type="relative",
                deadline_value=self.selected_deadline,
                channel_id=self.channel_id,
                send_dm=True,
                created_by=str(interaction.user.id),
                post_days_before=self.selected_post_timing,  # 🆕
                recurrence_interval=self.selected_recurrence,  # 🆕
                reminder_enabled=self.reminder_enabled,  # 🆕
                reminder_hours_before=5  # 🆕 고정값
            )
            
            if not success:
                await interaction.followup.send(
                    "❌ 스케줄 등록 중 오류가 발생했습니다.",
                    ephemeral=True
                )
                return
            
            # 성공 임베드
            embed = self._create_success_embed()
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # View 비활성화
            for item in self.children:
                item.disabled = True
            
            await interaction.edit_original_response(
                content="✅ 등록이 완료되었습니다!",
                view=self
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ 등록 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    def _create_success_embed(self) -> discord.Embed:
        """성공 임베드 생성"""
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        recurrence_text = {1: "매주", 2: "격주"}
        timing_text = {
            0: "내전 당일",
            1: "내전 1일 전",
            2: "내전 2일 전",
            3: "내전 3일 전",
            4: "내전 4일 전", 
            5: "내전 5일 전"
        }
        deadline_map = {
            "10min_before": "내전 10분 전",
            "30min_before": "내전 30분 전",
            "1hour_before": "내전 1시간 전",
            "3hour_before": "내전 3시간 전",
            "6hour_before": "내전 6시간 전",
            "1day_before": "내전 하루 전",
            "same_day_5pm": "내전 당일 오후 5시",
            "same_day_6pm": "내전 당일 오후 6시"
        }
        
        embed = discord.Embed(
            title="✅ 정기 내전 자동 스케줄 등록 완료",
            description=f"**{self.schedule_name}** 스케줄이 성공적으로 등록되었습니다!",
            color=0x00ff88,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📅 스케줄 정보",
            value=f"**{recurrence_text[self.selected_recurrence]} {weekday_names[self.selected_weekday]} {self.selected_time}**",
            inline=False
        )
        
        embed.add_field(
            name="📢 공지 등록",
            value=f"{timing_text[self.selected_post_timing]} 오전 6시",
            inline=True
        )
        
        embed.add_field(
            name="⏰ 모집 마감",
            value=deadline_map.get(self.selected_deadline),
            inline=True
        )
        
        if self.reminder_enabled:
            embed.add_field(
                name="🔔 미응답자 독촉",
                value="마감 5시간 전 활성화",
                inline=True
            )
        
        channel = self.bot.get_channel(int(self.channel_id))
        embed.add_field(
            name="📍 공지 채널",
            value=channel.mention if channel else f"<#{self.channel_id}>",
            inline=False
        )
        
        # 다음 실행 날짜
        next_date = self._calculate_next_post_date()
        embed.add_field(
            name="🚀 다음 자동 등록",
            value=f"{next_date.strftime('%Y년 %m월 %d일 (%A)')} 오전 6시경",
            inline=False
        )
        
        embed.set_footer(text="정기 내전 자동 스케줄 | /정기내전목록으로 확인")
        
        return embed
    
    def _calculate_next_post_date(self) -> datetime:
        """다음 공지 등록 날짜 계산"""
        today = datetime.now()
        days_ahead = self.selected_weekday - today.weekday()
        
        if days_ahead <= 0:
            days_ahead += 7
        
        next_scrim_date = today + timedelta(days=days_ahead)
        next_post_date = next_scrim_date - timedelta(days=self.selected_post_timing)
        
        return next_post_date.replace(hour=6, minute=0, second=0, microsecond=0)
    
class CustomAutoScrimTimeModal(discord.ui.Modal):
    """정기 내전 커스텀 시간 입력 Modal"""
    
    def __init__(self, parent_view):
        super().__init__(title="⏰ 커스텀 시간 입력")
        self.parent_view = parent_view
        
        self.time_input = discord.ui.TextInput(
            label="시간 입력 (24시간 형식)",
            placeholder="예: 14:30, 09:15, 21:45",
            required=True,
            max_length=5
        )
        self.add_item(self.time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """시간 입력 처리"""
        time_str = self.time_input.value.strip()
        
        # 시간 형식 검증
        if not self._validate_time_format(time_str):
            await interaction.response.send_message(
                "❌ 올바른 시간 형식이 아닙니다.\n"
                "24시간 형식으로 입력해주세요. (예: 14:30, 09:15, 21:45)",
                ephemeral=True
            )
            return
        
        self.parent_view.selected_time = time_str
        
        # 마감시간 선택 드롭다운 활성화
        self.parent_view.deadline_select.placeholder = "⏰ 모집 마감시간을 선택하세요"
        self.parent_view.deadline_select.options = self.parent_view._generate_deadline_options()
        self.parent_view.deadline_select.disabled = False
        
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        
        await interaction.response.edit_message(
            content=f"✅ 선택된 요일: **매주 {weekday_names[self.parent_view.selected_weekday]}**\n"
                   f"✅ 선택된 시간: **{time_str}** ({self._format_time_display(time_str)})\n"
                   f"이제 모집 마감시간을 선택해주세요:",
            view=self.parent_view
        )
    
    def _validate_time_format(self, time_str: str) -> bool:
        """시간 형식 검증"""
        import re
        pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'
        if not re.match(pattern, time_str):
            return False
        
        try:
            hour, minute = map(int, time_str.split(':'))
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except ValueError:
            return False
    
    def _format_time_display(self, time_str: str) -> str:
        """시간 표시 포맷"""
        try:
            hour, minute = map(int, time_str.split(':'))
            
            if hour == 0:
                return f"자정"
            elif hour < 12:
                return f"오전 {hour}시 {minute:02d}분"
            elif hour == 12:
                return f"정오" if minute == 0 else f"오후 12시 {minute:02d}분"
            else:
                return f"오후 {hour-12}시 {minute:02d}분"
        except:
            return time_str

class ScrimRecruitmentCommands(commands.Cog):
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

    @app_commands.command(name="내전공지등록", description="[관리자] 내전 공지를 등록합니다")
    @app_commands.describe(채널="내전 공지를 게시할 채널")
    @app_commands.default_permissions(manage_guild=True)
    async def register_recruitment(
        self,
        interaction: discord.Interaction,
        채널: discord.TextChannel = None
    ):
        """내전 공지 등록 - 3초 타임아웃 방지"""
        
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
            return
        
        if 채널:
            modal = DateTimeModal(self.bot, str(채널.id))
            await interaction.response.send_modal(modal)
            return
        
        try:
            default_channel_id = await self.bot.db_manager.get_recruitment_channel(
                str(interaction.guild_id)
            )
            
            if not default_channel_id:
                await interaction.response.send_message(
                    "❌ 채널을 지정하거나 `/내전공지채널설정`으로 기본 채널을 설정해주세요.", 
                    ephemeral=True
                )
                return
            
            target_channel = interaction.guild.get_channel(int(default_channel_id))
            if not target_channel:
                await interaction.response.send_message(
                    "❌ 설정된 기본 채널을 찾을 수 없습니다. 다시 설정해주세요.",
                    ephemeral=True
                )
                return
            
            # Modal 전송
            modal = DateTimeModal(self.bot, str(target_channel.id))
            await interaction.response.send_modal(modal)
            
        except discord.errors.NotFound:
            logger.warning(f"⚠️ Interaction timeout in register_recruitment for guild {interaction.guild_id}")
        except Exception as e:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ 오류가 발생했습니다: {str(e)}",
                        ephemeral=True
                    )
            except:
                logger.error(f"❌ register_recruitment 에러: {e}")

    @app_commands.command(name="내전공지채널설정", description="[관리자] 내전 공지가 게시될 채널을 설정합니다")
    @app_commands.describe(채널="내전 공지 채널")
    @app_commands.default_permissions(manage_guild=True)
    async def set_announcement_channel(
        self,
        interaction: discord.Interaction,
        채널: discord.TextChannel
    ):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
            return
        
        target_channel = None
        
        if 채널:
            target_channel = 채널
        else:
            cached_channel_id = self.bot.recruitment_channels_cache.get(str(interaction.guild_id))
            
            if cached_channel_id:
                target_channel = interaction.guild.get_channel(int(cached_channel_id))
            else:
                try:
                    default_channel_id = await self.bot.db_manager.get_recruitment_channel(
                        str(interaction.guild_id)
                    )
                    if default_channel_id:
                        self.bot.recruitment_channels_cache[str(interaction.guild_id)] = default_channel_id
                        target_channel = interaction.guild.get_channel(int(default_channel_id))
                except:
                    pass
        
        if not target_channel:
            await interaction.response.send_message(
                "❌ 채널을 지정하거나 `/내전공지채널설정`으로 기본 채널을 설정해주세요.", 
                ephemeral=True
            )
            return
        
        modal = DateTimeModal(self.bot, str(target_channel.id))
        await interaction.response.send_modal(modal)

    @app_commands.command(
        name="정기내전설정", 
        description="[관리자] 매주 자동으로 등록되는 정기 내전을 설정합니다"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def setup_auto_scrim(self, interaction: discord.Interaction):
        """정기 내전 자동 등록 설정 - UX 개선"""
        
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
            return
        
        # 채널 확인 먼저
        guild_id = str(interaction.guild_id)
        channel_id = await self.bot.db_manager.get_recruitment_channel(guild_id)
        
        if not channel_id:
            await interaction.response.send_message(
                "❌ 먼저 `/내전공지채널설정` 명령어로 공지 채널을 설정해주세요.",
                ephemeral=True
            )
            return
        
        # Modal 표시
        modal = AutoScrimSetupModal(self.bot, channel_id)
        await interaction.response.send_modal(modal)

    @app_commands.command(
        name="정기내전목록",
        description="[관리자] 등록된 정기 내전 스케줄 목록을 확인합니다"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def list_auto_scrims(self, interaction: discord.Interaction):
        """정기 내전 목록 조회"""
        
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            schedules = await self.bot.db_manager.get_auto_schedules(guild_id)
            
            if not schedules:
                await interaction.followup.send(
                    "ℹ️ 등록된 정기 내전 스케줄이 없습니다.\n"
                    "`/정기내전설정` 명령어로 스케줄을 등록해보세요!",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="📋 정기 내전 스케줄 목록",
                description=f"총 {len(schedules)}개의 스케줄이 등록되어 있습니다.",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
            
            for schedule in schedules:
                status_emoji = "🟢" if schedule['is_active'] else "🔴"
                weekday = weekday_names[schedule['day_of_week']]
                
                value_text = (
                    f"**요일**: {weekday}\n"
                    f"**시간**: {schedule['scrim_time']}\n"
                    f"**채널**: <#{schedule['channel_id']}>\n"
                    f"**상태**: {status_emoji} {'활성' if schedule['is_active'] else '비활성'}\n"
                    f"**마지막 생성**: {schedule['last_created_date'] or '없음'}\n"
                    f"**ID**: `{schedule['id']}`"
                )
                
                embed.add_field(
                    name=f"{status_emoji} {schedule['schedule_name']}",
                    value=value_text,
                    inline=False
                )
            
            embed.set_footer(text="스케줄 ID는 수정/삭제 시 필요합니다")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 스케줄 목록 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="정기내전삭제",
        description="[관리자] 등록된 정기 내전 스케줄을 삭제합니다"
    )
    @app_commands.describe(
        스케줄id="삭제할 스케줄의 ID (/정기내전목록에서 확인)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def delete_auto_scrim(
        self,
        interaction: discord.Interaction,
        스케줄id: int
    ):
        """정기 내전 삭제"""
        
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            # 스케줄 존재 확인
            schedule = await self.bot.db_manager.get_schedule_by_id(스케줄id)
            
            if not schedule:
                await interaction.followup.send(
                    f"❌ ID가 `{스케줄id}`인 스케줄을 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            if schedule['guild_id'] != guild_id:
                await interaction.followup.send(
                    "❌ 다른 서버의 스케줄은 삭제할 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 삭제 실행
            success = await self.bot.db_manager.delete_auto_schedule(스케줄id, guild_id)
            
            if not success:
                await interaction.followup.send(
                    "❌ 스케줄 삭제 중 오류가 발생했습니다.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="✅ 정기 내전 스케줄 삭제 완료",
                description=f"**{schedule['schedule_name']}** 스케줄이 삭제되었습니다.",
                color=0xff6b6b,
                timestamp=datetime.now()
            )
            
            weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
            
            embed.add_field(
                name="📋 삭제된 스케줄 정보",
                value=f"**요일**: {weekday_names[schedule['day_of_week']]}\n"
                    f"**시간**: {schedule['scrim_time']}\n"
                    f"**제목**: {schedule['recruitment_title']}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 스케줄 삭제 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="정기내전토글",
        description="[관리자] 정기 내전 스케줄을 활성화/비활성화합니다"
    )
    @app_commands.describe(
        스케줄id="토글할 스케줄의 ID (/정기내전목록에서 확인)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def toggle_auto_scrim(
        self,
        interaction: discord.Interaction,
        스케줄id: int
    ):
        """정기 내전 활성화/비활성화"""
        
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            # 스케줄 존재 확인
            schedule = await self.bot.db_manager.get_schedule_by_id(스케줄id)
            
            if not schedule:
                await interaction.followup.send(
                    f"❌ ID가 `{스케줄id}`인 스케줄을 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            if schedule['guild_id'] != guild_id:
                await interaction.followup.send(
                    "❌ 다른 서버의 스케줄은 변경할 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 상태 토글
            new_status = not schedule['is_active']
            success = await self.bot.db_manager.toggle_schedule_status(스케줄id, new_status)
            
            if not success:
                await interaction.followup.send(
                    "❌ 스케줄 상태 변경 중 오류가 발생했습니다.",
                    ephemeral=True
                )
                return
            
            status_text = "활성화" if new_status else "비활성화"
            status_emoji = "🟢" if new_status else "🔴"
            color = 0x00ff88 if new_status else 0x666666
            
            embed = discord.Embed(
                title=f"{status_emoji} 정기 내전 스케줄 {status_text}",
                description=f"**{schedule['schedule_name']}** 스케줄이 {status_text}되었습니다.",
                color=color,
                timestamp=datetime.now()
            )
            
            weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
            
            embed.add_field(
                name="📋 스케줄 정보",
                value=f"**요일**: {weekday_names[schedule['day_of_week']]}\n"
                    f"**시간**: {schedule['scrim_time']}\n"
                    f"**제목**: {schedule['recruitment_title']}\n"
                    f"**새 상태**: {status_emoji} {status_text}",
                inline=False
            )
            
            if new_status:
                next_date = self._calculate_next_occurrence(
                    schedule['day_of_week'], 
                    schedule['scrim_time']
                )
                embed.add_field(
                    name="🚀 다음 자동 등록",
                    value=next_date.strftime('%Y년 %m월 %d일 (%A) 오전 6시경'),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 스케줄 상태 변경 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    # @app_commands.command(
    #     name="정기내전테스트",
    #     description="[관리자] 정기 내전 자동 생성을 즉시 테스트합니다"
    # )
    # @app_commands.default_permissions(administrator=True)
    # async def test_auto_scrim(self, interaction: discord.Interaction):
    #     """정기 내전 자동 생성 즉시 테스트"""
        
    #     if not await self.is_admin(interaction):
    #         await interaction.response.send_message(
    #             "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
    #             ephemeral=True
    #         )
    #         return
        
    #     await interaction.response.defer(ephemeral=True)
        
    #     try:
    #         if not self.bot.auto_recruitment_scheduler:
    #             await interaction.followup.send(
    #                 "❌ 자동 스케줄러가 초기화되지 않았습니다.",
    #                 ephemeral=True
    #             )
    #             return
            
    #         # 수동 트리거
    #         result = await self.bot.auto_recruitment_scheduler.manual_trigger()
            
    #         embed = discord.Embed(
    #             title="🧪 자동 생성 테스트 완료",
    #             description="오늘 요일에 해당하는 스케줄을 강제로 실행했습니다.",
    #             color=0x00ff88,
    #             timestamp=datetime.now()
    #         )
            
    #         embed.add_field(
    #             name="📊 결과",
    #             value=f"상태: {result.get('status', 'unknown')}",
    #             inline=False
    #         )
            
    #         embed.add_field(
    #             name="ℹ️ 참고",
    #             value="• 이미 오늘 생성된 스케줄은 건너뜁니다\n"
    #                 "• 서버 로그에서 상세 결과를 확인하세요",
    #             inline=False
    #         )
            
    #         await interaction.followup.send(embed=embed, ephemeral=True)
            
    #     except Exception as e:
    #         await interaction.followup.send(
    #             f"❌ 테스트 실행 중 오류가 발생했습니다: {str(e)}",
    #             ephemeral=True
    #         )

    @app_commands.command(name="내전모집현황", description="[관리자] 현재 진행 중인 내전 모집 현황을 확인합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def recruitment_status(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            recruitments = await self.bot.db_manager.get_active_recruitments(
                str(interaction.guild_id)
            )

            if not recruitments:
                await interaction.followup.send(
                    "ℹ️ 현재 진행 중인 내전 모집이 없습니다.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="📋 내전 모집 현황",
                description=f"현재 진행 중인 모집 {len(recruitments)}건",
                color=0x0099ff,
                timestamp=datetime.now()
            )

            for recruitment in recruitments:
                participants = await self.bot.db_manager.get_recruitment_participants(
                    recruitment['id']
                )
                
                joined_count = len([p for p in participants if p['status'] == 'joined'])
                declined_count = len([p for p in participants if p['status'] == 'declined'])
                
                scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
                deadline = datetime.fromisoformat(recruitment['deadline'])
                
                embed.add_field(
                    name=f"🎮 {recruitment['title']}",
                    value=f"**일시**: {scrim_date.strftime('%m/%d %H:%M')}\n"
                          f"**마감**: {deadline.strftime('%m/%d %H:%M')}\n"
                          f"**참가**: {joined_count}명 | **불참**: {declined_count}명\n"
                          f"**ID**: `{recruitment['id']}`",
                    inline=True
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                f"❌ 현황 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="내전모집취소", description="[관리자] 진행 중인 내전 모집을 취소합니다")
    @app_commands.describe(모집id="취소할 모집의 ID")
    @app_commands.default_permissions(manage_guild=True)
    async def cancel_recruitment(self, interaction: discord.Interaction, 모집id: str):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        scrim_date = None
        recruitment = None

        try:
            # 1. 모집 정보 확인
            recruitment = await self.bot.db_manager.get_recruitment_by_id(모집id)
            if not recruitment:
                await interaction.followup.send(
                    f"❌ 모집 ID `{모집id}`를 찾을 수 없습니다.", ephemeral=True
                )
                return

            scrim_date = datetime.fromisoformat(recruitment['scrim_date'])

            if recruitment['guild_id'] != str(interaction.guild_id):
                await interaction.followup.send(
                    "❌ 다른 서버의 모집은 취소할 수 없습니다.", ephemeral=True
                )
                return

            if recruitment['status'] != 'active':
                await interaction.followup.send(
                    "❌ 이미 취소되었거나 마감된 모집입니다.", ephemeral=True
                )
                return

            # 2. 모집 취소 처리
            success = await self.bot.db_manager.cancel_recruitment(모집id)
            if not success:
                await interaction.followup.send(
                    "❌ 모집 취소 처리 중 오류가 발생했습니다.", ephemeral=True
                )
                return

            # 3. 원본 메시지 업데이트 (취소 표시)
            if recruitment['message_id'] and recruitment['channel_id']:
                try:
                    channel = self.bot.get_channel(int(recruitment['channel_id']))
                    if channel:
                        message = await channel.fetch_message(int(recruitment['message_id']))
                        
                        # 취소된 임베드 생성
                        canceled_embed = discord.Embed(
                            title=f"🚫 [취소됨] {recruitment['title']}",
                            description=f"**이 모집은 관리자에 의해 취소되었습니다.**\n\n"
                                    f"~~{recruitment['description'] or '내전 모집'}~~",
                            color=0x666666,  # 회색
                        )
                        
                        canceled_embed.add_field(
                            name="📅 예정이었던 내전 일시",
                            value=f"~~{scrim_date.strftime('%Y년 %m월 %d일 %H:%M')}~~",
                            inline=True
                        )
                        
                        canceled_embed.add_field(
                            name="🚫 취소 사유",
                            value="관리자에 의한 취소",
                            inline=True
                        )
                        
                        canceled_embed.set_footer(text=f"모집 ID: {모집id} | 취소됨")
                        
                        # 버튼 제거하고 메시지 업데이트
                        await message.edit(embed=canceled_embed, view=None)
                        
                except Exception as e:
                    print(f"❌ 취소 메시지 업데이트 실패: {e}")

            # 4. 성공 메시지
            participants = await self.bot.db_manager.get_recruitment_participants(모집id)
            joined_count = len([p for p in participants if p['status'] == 'joined']) 

            date_str = "알 수 없음"
            if scrim_date:
                try:
                    date_str = scrim_date.strftime('%Y년 %m월 %d일 %H:%M')
                except:
                    date_str = "날짜 형식 오류"         
            
            await interaction.followup.send(
                f"✅ **내전 모집이 취소되었습니다.**\n\n"
                f"📋 **취소된 모집**: {recruitment['title']}\n"
                f"📅 **예정 일시**: {date_str}\n"
                f"👥 **참가 예정이었던 인원**: {joined_count}명\n"
                f"🆔 **모집 ID**: `{모집id}`",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"✅ 모집이 취소되었습니다. (ID: {모집id})\n"
                f"상세 정보 표시 중 오류: {str(e)}",
                ephemeral=True
            )

    # @app_commands.command(name="내전모집통계", description="[관리자] 서버의 내전 모집 통계를 확인합니다")
    # @app_commands.default_permissions(manage_guild=True)
    # async def recruitment_statistics(self, interaction: discord.Interaction):
    #     if not await self.is_admin(interaction):
    #         await interaction.response.send_message(
    #             "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
    #         )
    #         return

    #     await interaction.response.defer(ephemeral=True)

    #     try:
    #         guild_id = str(interaction.guild_id)
            
    #         # 1. 기본 통계 조회
    #         stats = await self.bot.db_manager.get_recruitment_stats(guild_id)
    #         if not stats:
    #             await interaction.followup.send(
    #                 "❌ 통계 데이터를 불러올 수 없습니다.", ephemeral=True
    #             )
    #             return

    #         # 2. 시간대별 인기도 조회
    #         time_stats = await self.bot.db_manager.get_popular_participation_times(guild_id)

    #         # 3. 임베드 생성
    #         embed = discord.Embed(
    #             title="📊 내전 모집 통계",
    #             description=f"**{interaction.guild.name}** 서버의 내전 모집 현황",
    #             color=0x0099ff,
    #             timestamp=datetime.now()
    #         )

    #         # 기본 통계
    #         embed.add_field(
    #             name="📋 모집 현황",
    #             value=f"📊 **전체 모집**: {stats.get('total_recruitments', 0)}건\n"
    #                   f"🟢 **진행 중**: {stats.get('active_recruitments', 0)}건\n"
    #                   f"✅ **완료됨**: {stats.get('closed_recruitments', 0)}건\n"
    #                   f"❌ **취소됨**: {stats.get('cancelled_recruitments', 0)}건",
    #             inline=True
    #         )

    #         embed.add_field(
    #             name="👥 참가자 통계",
    #             value=f"👤 **고유 참가자**: {stats.get('unique_participants', 0)}명\n"
    #                   f"📈 **평균 참가률**: "
    #                   f"{round((stats.get('unique_participants', 0) / max(stats.get('total_recruitments', 1), 1)) * 100, 1)}%",
    #             inline=True
    #         )

    #         # 시간대별 통계
    #         if time_stats:
    #             time_analysis = []
    #             for period, data in sorted(time_stats.items()):
    #                 time_analysis.append(
    #                     f"**{period}**: 평균 {data['avg_participants']}명 "
    #                     f"({data['recruitment_count']}회)"
    #                 )
                
    #             embed.add_field(
    #                 name="🕐 시간대별 인기도",
    #                 value='\n'.join(time_analysis) if time_analysis else "데이터 없음",
    #                 inline=False
    #             )

    #         # 최근 활동
    #         recent_recruitments = await self.bot.db_manager.get_active_recruitments(guild_id)
    #         if recent_recruitments:
    #             embed.add_field(
    #                 name="🚀 현재 활성 모집",
    #                 value=f"{len(recent_recruitments)}건의 모집이 진행 중입니다.",
    #                 inline=True
    #             )

    #         embed.set_footer(text="RallyUp Bot | 내전 모집 통계")

    #         await interaction.followup.send(embed=embed, ephemeral=True)

    #     except Exception as e:
    #         await interaction.followup.send(
    #             f"❌ 통계 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True
    #         )

    @cancel_recruitment.autocomplete('모집id')
    async def recruitment_id_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        """모집 ID 자동완성"""
        try:
            guild_id = str(interaction.guild_id)
            recruitments = await self.bot.db_manager.get_active_recruitments(guild_id)
            
            # 현재 입력과 매칭되는 모집들 필터링
            matching_recruitments = []
            for recruitment in recruitments:
                recruitment_id = recruitment['id']
                title = recruitment['title']
                scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
                
                # ID나 제목에 현재 입력이 포함된 경우
                if current.lower() in recruitment_id.lower() or current.lower() in title.lower():
                    display_name = f"{title} ({scrim_date.strftime('%m/%d %H:%M')})"
                    # Discord 선택지 이름은 100자 제한
                    if len(display_name) > 100:
                        display_name = display_name[:97] + "..."
                    
                    matching_recruitments.append(
                        app_commands.Choice(
                            name=display_name,
                            value=recruitment_id
                        )
                    )
            
            # Discord 자동완성 한도는 25개
            return matching_recruitments[:25]
            
        except Exception as e:
            print(f"[DEBUG] 모집 ID 자동완성 오류: {e}")
            return []

    def _validate_time_format(self, time_str: str) -> bool:
        """시간 형식 검증 (HH:MM)"""
        import re
        pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'
        if not re.match(pattern, time_str):
            return False
        
        try:
            hour, minute = map(int, time_str.split(':'))
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except ValueError:
            return False

    def _calculate_next_occurrence(self, day_of_week: int, time_str: str) -> datetime:
        """다음 발생 날짜 계산"""
        from datetime import datetime, timedelta
        
        today = datetime.now()
        days_ahead = day_of_week - today.weekday()
        
        if days_ahead <= 0:  # 이미 지났거나 오늘
            days_ahead += 7
        
        next_date = today + timedelta(days=days_ahead)
        hour, minute = map(int, time_str.split(':'))
        
        return next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def _parse_datetime(self, date_str: str, time_str: str) -> Optional[datetime]:
        """날짜와 시간 문자열을 datetime 객체로 변환"""
        try:
            # 날짜 파싱
            current_year = datetime.now().year
            
            if '-' in date_str:
                if len(date_str.split('-')) == 2:  # MM-DD 형식
                    month, day = date_str.split('-')
                    date_obj = datetime(current_year, int(month), int(day))
                else:  # YYYY-MM-DD 형식
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                return None
            
            # 시간 파싱
            time_str = time_str.upper().replace(' ', '')
            
            if 'PM' in time_str or 'AM' in time_str:
                time_obj = datetime.strptime(time_str, '%I:%M%p').time()
            else:
                time_obj = datetime.strptime(time_str, '%H:%M').time()
            
            return datetime.combine(date_obj.date(), time_obj)
            
        except (ValueError, IndexError):
            return None

    def _parse_full_datetime(self, datetime_str: str) -> Optional[datetime]:
        """전체 날짜시간 문자열을 datetime 객체로 변환"""
        try:
            return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        except ValueError:
            try:
                return datetime.strptime(datetime_str, '%m-%d %H:%M')
            except ValueError:
                return None

    async def _get_announcement_channel(self, guild_id: str) -> Optional[discord.TextChannel]:
        """설정된 공지 채널 가져오기"""
        channel_id = await self.bot.db_manager.get_recruitment_channel(guild_id)
        if not channel_id:
            return None
        
        guild = self.bot.get_guild(int(guild_id))
        return guild.get_channel(int(channel_id)) if guild else None
    
    def _get_korean_weekday(self, date: datetime) -> str:
        """한국어 요일 반환"""
        weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        return weekdays[date.weekday()]

    async def _create_recruitment_message(self, recruitment_id, title, description, scrim_date, deadline):
        """모집 공지 메시지 생성 (한국어 요일 포함)"""
        
        # 1. 임베드 생성
        embed = discord.Embed(
            title=f"🎮 {title}",
            description=description or "이번주 정기 내전에 참가해주세요!",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        korean_weekday = self._get_korean_weekday(scrim_date)
        embed.add_field(
            name="📅 내전 일시",
            value=f"{scrim_date.strftime('%Y년 %m월 %d일')} ({korean_weekday}) {scrim_date.strftime('%H:%M')}",
            inline=True
        )
        
        embed.add_field(
            name="⏰ 모집 마감",
            value=deadline.strftime('%Y년 %m월 %d일 %H:%M'),
            inline=True
        )
        
        # 마감까지 남은 시간
        time_left = deadline - datetime.now()
        if time_left.days > 0:
            time_left_str = f"{time_left.days}일 {time_left.seconds//3600}시간"
        else:
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            time_left_str = f"{hours}시간 {minutes}분"
        
        embed.add_field(
            name="📊 현재 상황",
            value=f"⏰ 마감까지: {time_left_str}",
            inline=True
        )
        
        embed.add_field(
            name="👥 참가 현황",
            value="✅ **참가**: 0명\n❌ **불참**: 0명\n⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ (0명)",
            inline=False
        )
        
        embed.add_field(
            name="📝 참가 방법",
            value="🔽 **아래 버튼을 눌러 참가 의사를 표시해주세요!**\n"
                  "• 언제든 참가 ↔ 불참 변경 가능합니다\n"
                  "• 참가자 목록 버튼으로 현황 확인 가능합니다",
            inline=False
        )
        
        embed.set_footer(text=f"모집 ID: {recruitment_id}")
        
        # 2. View 생성
        view = RecruitmentView(self.bot, recruitment_id)
        
        return embed, view

async def setup(bot):
    await bot.add_cog(ScrimRecruitmentCommands(bot))