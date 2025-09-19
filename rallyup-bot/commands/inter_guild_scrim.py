import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

# 상수 정의
TIME_SLOTS = [
    "18:00-20:00 (오후)",
    "19:00-21:00 (오후)", 
    "20:00-22:00 (저녁)", 
    "21:00-23:00 (저녁)", 
    "22:00-24:00 (야간)"
]

TIER_RANGES = [
    "플래티넘", 
    "플래티넘~다이아", 
    "다이아", 
    "다이아~마스터", 
    "마스터", 
    "마스터~그마", 
    "그마", 
    "그마~챔피언"
]

POSITION_EMOJIS = {
    "탱커": "🛡️",
    "딜러": "⚔️", 
    "힐러": "💚",
    "플렉스": "🔄"
}

class ScrimMainConfigurationView(discord.ui.View):    
    def __init__(self, bot, channel_id, available_clans=None):
        super().__init__(timeout=300)
        self.bot = bot
        self.channel_id = channel_id
        self.available_clans = available_clans or []
        
        # 선택된 값들 저장
        self.selected_clan = None
        self.selected_dates = []
        self.selected_times = []
        self.selected_tier = None
        self.selected_deadline = None
        self.use_custom_input = False
        self.use_custom_time = False

        # UI 컴포넌트 추가
        self.setup_ui()
    
    def setup_ui(self):
        """UI 컴포넌트 설정"""
        self.add_clan_selector()
        self.add_date_selector()
        self.add_time_selector()
        self.add_tier_selector()
        self.add_deadline_and_actions()
        # self.add_deadline_selector()
        # self.add_action_buttons()
    
    def add_clan_selector(self):
        """클랜 선택 드롭다운"""
        clan_options = []

        if self.available_clans:
            for clan in self.available_clans[:20]:
                clan_options.append(discord.SelectOption(
                    label=clan['display'],
                    value=clan['name'],
                    description=f"클랜: {clan['name']}"
                ))
        
        # 등록된 클랜이 없거나 직접입력을 원하는 경우
        clan_options.append(discord.SelectOption(
            label="✏️ 직접입력",
            value="__CUSTOM_INPUT__",
            description="상대팀명을 직접 입력합니다"
        ))
        
        clan_select = discord.ui.Select(
            placeholder="🏠 상대팀 클랜을 선택하세요 (필수)",
            options=clan_options,
            max_values=1,
            row=0
        )
        clan_select.callback = self.clan_callback
        self.add_item(clan_select)
    
    def add_date_selector(self):
        """날짜 선택 드롭다운"""
        today = datetime.now()
        date_options = []
        
        for i in range(14):  # 2주간의 날짜 제공
            date = today + timedelta(days=i)
            weekday = ["월", "화", "수", "목", "금", "토", "일"][date.weekday()]
            
            date_options.append(discord.SelectOption(
                label=f"{date.month}/{date.day}({weekday})",
                value=date.strftime("%Y-%m-%d"),
                description=f"{date.strftime('%Y년 %m월 %d일')}"
            ))
        
        date_select = discord.ui.Select(
            placeholder="📅 날짜를 선택하세요 (복수선택 가능, 필수)",
            options=date_options[:25],  # Discord 제한
            max_values=min(7, len(date_options)),
            row=1
        )
        date_select.callback = self.date_callback
        self.add_item(date_select)
    
    def add_time_selector(self):
        """시간대 선택 드롭다운"""
        time_options = []
        for time_slot in TIME_SLOTS:
            time_options.append(discord.SelectOption(
                label=time_slot,
                value=time_slot
            ))
        
        # 직접입력 옵션 추가
        time_options.append(discord.SelectOption(
            label="✏️ 직접입력 (추후 설정)",
            value="__CUSTOM_TIME__",
            description="사용자 정의 시간대를 설정합니다"
        ))
        
        time_select = discord.ui.Select(
            placeholder="⏰ 시간대를 선택하세요 (복수선택 가능, 필수)",
            options=time_options,
            max_values=len(time_options),
            row=2
        )
        time_select.callback = self.time_callback
        self.add_item(time_select)
    
    def add_tier_selector(self):
        """티어 선택 드롭다운"""
        tier_options = []
        for tier in TIER_RANGES:
            tier_options.append(discord.SelectOption(
                label=tier,
                value=tier
            ))
        
        tier_select = discord.ui.Select(
            placeholder="🏆 참여 티어를 선택하세요 (필수)",
            options=tier_options,
            max_values=1,
            row=3
        )
        tier_select.callback = self.tier_callback
        self.add_item(tier_select)

    def add_deadline_selector(self):
        """마감기한 선택 드롭다운"""
        today = datetime.now()
        deadline_options = []
        
        # 1시간 후부터 7일 후까지 옵션 제공
        for hours in [1, 2, 3, 6, 12, 24, 48, 72, 168]:  # 시간 단위
            deadline_time = today + timedelta(hours=hours)
            if hours < 24:
                label = f"{hours}시간 후 ({deadline_time.strftime('%m/%d %H:%M')})"
            else:
                days = hours // 24
                label = f"{days}일 후 ({deadline_time.strftime('%m/%d %H:%M')})"
            
            deadline_options.append(discord.SelectOption(
                label=label,
                value=deadline_time.isoformat(),
                description=f"{deadline_time.strftime('%Y년 %m월 %d일 %H:%M')}"
            ))
        
        # 마감기한 없음 옵션
        deadline_options.append(discord.SelectOption(
            label="⏰ 마감기한 없음",
            value="__NO_DEADLINE__",
            description="언제까지나 참가 신청 가능"
        ))
        
        deadline_select = discord.ui.Select(
            placeholder="⏳ 참가 신청 마감기한을 선택하세요 (선택사항)",
            options=deadline_options,
            max_values=1,
            row=4 
        )
        deadline_select.callback = self.deadline_callback
        self.add_item(deadline_select)

    def add_deadline_and_actions(self):
        """마감기한 + 액션 버튼들 (row 4) - 모두 버튼 형태로 통합"""
        
        # 마감기한 설정 버튼 (Modal로 처리)
        deadline_button = discord.ui.Button(
            label="⏳ 마감기한 설정",
            style=discord.ButtonStyle.secondary,
            row=4
        )
        deadline_button.callback = self.deadline_button_callback
        self.add_item(deadline_button)
        
        # 등록하기 버튼
        register_button = discord.ui.Button(
            label="📝 등록하기",
            style=discord.ButtonStyle.success,
            row=4
        )
        register_button.callback = self.register_callback
        self.add_item(register_button)
        
        # 취소 버튼
        cancel_button = discord.ui.Button(
            label="❌ 취소",
            style=discord.ButtonStyle.secondary, 
            row=4
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    async def deadline_button_callback(self, interaction: discord.Interaction):
        """마감기한 설정 버튼 콜백 - Modal 또는 간단한 선택지 제공"""
        if not self.selected_dates:
            await interaction.response.send_message(
                "📅 먼저 스크림 날짜를 선택해주세요!", ephemeral=True
            )
            return
        
        # 간단한 마감기한 선택 View
        deadline_view = DeadlineSelectionView(self)
        
        embed = discord.Embed(
            title="⏳ 마감기한 설정",
            description="참가 신청 마감기한을 선택해주세요",
            color=0x0099ff
        )
        
        # 현재 마감기한 상태 표시
        if hasattr(self, 'selected_deadline') and self.selected_deadline:
            deadline = datetime.fromisoformat(self.selected_deadline)
            embed.add_field(
                name="현재 설정된 마감기한",
                value=f"{deadline.strftime('%m월 %d일 %H:%M')}",
                inline=False
            )
        else:
            embed.add_field(
                name="현재 마감기한",
                value="설정되지 않음 (언제든 참가 가능)",
                inline=False
            )
        
        await interaction.response.send_message(
            embed=embed, view=deadline_view, ephemeral=True
        )

    def generate_deadline_options(self):
        """선택된 스크림 날짜 기준으로 마감기한 옵션 생성"""
        deadline_options = []
        
        if not self.selected_dates:
            # 날짜가 선택되지 않았으면 기본 옵션만
            deadline_options.append(discord.SelectOption(
                label="📅 먼저 날짜를 선택해주세요",
                value="__NO_DATES_SELECTED__",
                description="스크림 날짜 선택 후 마감기한을 설정할 수 있습니다"
            ))
            return deadline_options
        
        # 선택된 날짜들 중 가장 빠른 날짜 찾기
        earliest_date_str = min(self.selected_dates)
        earliest_date = datetime.strptime(earliest_date_str, "%Y-%m-%d")
        
        # 현재 시간과 비교하여 유효한 마감기한만 생성
        now = datetime.now()
        
        # 마감기한 옵션들: 스크림 날짜 기준 역산
        deadline_scenarios = [
            (0, "당일", "스크림 당일까지"),
            (1, "1일 전", "스크림 하루 전까지"), 
            (2, "2일 전", "스크림 이틀 전까지"),
            (3, "3일 전", "스크림 3일 전까지"),
            (7, "1주일 전", "스크림 1주일 전까지")
        ]
        
        for days_before, label, description in deadline_scenarios:
            # 마감 시간 계산 (스크림 날짜에서 역산)
            deadline_date = earliest_date - timedelta(days=days_before)
            # 마감 시간을 저녁 11시로 설정 (당일이면 현재시간 + 1시간)
            if days_before == 0:
                deadline_time = max(now + timedelta(hours=1), 
                                deadline_date.replace(hour=23, minute=0))
            else:
                deadline_time = deadline_date.replace(hour=23, minute=0)
            
            # 이미 지난 마감기한은 제외
            if deadline_time <= now:
                continue
                
            # 옵션 추가
            deadline_options.append(discord.SelectOption(
                label=f"{label} ({deadline_time.strftime('%m/%d %H:%M')})",
                value=deadline_time.isoformat(),
                description=f"{description}"
            ))
        
        # 마감기한 없음 옵션
        deadline_options.append(discord.SelectOption(
            label="⏰ 마감기한 없음",
            value="__NO_DEADLINE__",
            description="스크림 직전까지 참가 신청 가능"
        ))
        
        return deadline_options

    async def deadline_callback(self, interaction: discord.Interaction):
        """마감기한 선택 콜백 - 유효성 검사 추가"""
        selected_value = interaction.data['values'][0]
        
        if selected_value == "__NO_DEADLINE__":
            self.selected_deadline = None
        elif selected_value == "__NO_DATES_SELECTED__":
            await interaction.response.send_message(
                "📅 먼저 스크림 날짜를 선택해주세요!", ephemeral=True
            )
            return
        else:
            # 선택된 마감기한이 유효한지 재검사
            deadline_time = datetime.fromisoformat(selected_value)
            if deadline_time <= datetime.now():
                await interaction.response.send_message(
                    "⚠️ 선택하신 마감기한이 이미 지났습니다. 다른 옵션을 선택해주세요.", 
                    ephemeral=True
                )
                return
                
            self.selected_deadline = selected_value
        
        await self.update_status(interaction)
    
    def add_action_buttons(self):
        """액션 버튼들"""
        # 다음 단계 버튼 (선택사항 입력)
        next_button = discord.ui.Button(
            label="➡️ 다음 (선택사항 입력)",
            style=discord.ButtonStyle.primary,
            row=5
        )
        next_button.callback = self.next_step_callback
        self.add_item(next_button)
        
        # 바로 등록 버튼
        register_button = discord.ui.Button(
            label="📝 바로 등록",
            style=discord.ButtonStyle.success,
            row=5
        )
        register_button.callback = self.direct_register_callback
        self.add_item(register_button)
        
        # 취소 버튼
        cancel_button = discord.ui.Button(
            label="❌ 취소",
            style=discord.ButtonStyle.secondary,
            row=5
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)
    
    async def clan_callback(self, interaction: discord.Interaction):
        """클랜 선택 콜백"""
        selected_value = interaction.data['values'][0]
        
        if selected_value == "__CUSTOM_INPUT__":
            self.use_custom_input = True
            self.selected_clan = None
        else:
            # 우리 서버 클랜인지 체크
            try:
                our_clan_name = await self.bot.db_manager.get_our_clan_name(str(interaction.guild_id))
                if selected_value == our_clan_name:
                    await interaction.response.send_message(
                        "❌ 자기 자신과는 스크림을 할 수 없습니다! 다른 클랜을 선택해주세요.", 
                        ephemeral=True
                    )
                    return
            except Exception as e:
                print(f"우리 클랜명 체크 오류: {e}")

            self.use_custom_input = False
            self.selected_clan = selected_value
        
        await self.update_status(interaction)
    
    async def date_callback(self, interaction: discord.Interaction):
        """날짜 선택 콜백 - 마감기한 옵션 업데이트 포함"""
        self.selected_dates = interaction.data['values']
        
        # 날짜가 변경되면 마감기한 리셋
        if hasattr(self, 'selected_deadline'):
            self.selected_deadline = None
        
        # UI 전체 재구성 (마감기한 옵션이 업데이트되도록)
        await self.rebuild_ui_with_updated_deadlines(interaction)

    async def rebuild_ui_with_updated_deadlines(self, interaction: discord.Interaction):
        """날짜 변경 후 마감기한 옵션을 업데이트하여 UI 재구성"""
        
        # 기존 컴포넌트 제거
        self.clear_items()
        
        # UI 다시 구성
        self.add_clan_selector()
        self.add_date_selector() 
        self.add_time_selector()
        self.add_tier_selector()
        self.add_deadline_and_actions() 
        
        # 상태 업데이트
        await self.update_status(interaction)
    
    async def time_callback(self, interaction: discord.Interaction):
        """시간대 선택 콜백"""
        values = interaction.data['values']
        
        # 직접입력이 포함되어 있는지 확인
        if "__CUSTOM_TIME__" in values:
            self.use_custom_time = True
            self.selected_times = [v for v in values if v != "__CUSTOM_TIME__"]
        else:
            self.use_custom_time = False
            self.selected_times = values
            
        await self.update_status(interaction)
    
    async def tier_callback(self, interaction: discord.Interaction):
        """티어 선택 콜백"""
        self.selected_tier = interaction.data['values'][0]
        await self.update_status(interaction)
    
    async def update_status(self, interaction: discord.Interaction):
        """현재 선택 상태 업데이트"""
        embed = discord.Embed(
            title="🎯 스크림 모집 설정",
            description="필수 항목들을 선택해주세요",
            color=0x0099ff
        )
        
        # 클랜 선택 상태
        if self.use_custom_input:
            embed.add_field(
                name="🏠 상대팀",
                value="✏️ 직접입력 (다음 단계에서 입력)",
                inline=False
            )
        elif self.selected_clan:
            embed.add_field(
                name="🏠 상대팀",
                value=f"**{self.selected_clan}**",
                inline=False
            )
        
        # 선택된 날짜들
        if self.selected_dates:
            dates_text = []
            for date_str in self.selected_dates:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                weekday = ["월", "화", "수", "목", "금", "토", "일"][date_obj.weekday()]
                dates_text.append(f"{date_obj.month}/{date_obj.day}({weekday})")
            
            embed.add_field(
                name="📅 선택된 날짜",
                value=", ".join(dates_text),
                inline=False
            )
        
        # 선택된 시간대들 - 직접입력 포함 표시
        time_display_parts = []
        if self.selected_times:
            time_display_parts.extend(self.selected_times)
        if self.use_custom_time:
            time_display_parts.append("✏️ 직접입력 (다음 단계에서 설정)")
        
        if time_display_parts:
            embed.add_field(
                name="⏰ 선택된 시간대",
                value=", ".join(time_display_parts),
                inline=False
            )
        
        # 선택된 티어
        if self.selected_tier:
            embed.add_field(
                name="🏆 참여 티어",
                value=self.selected_tier,
                inline=False
            )

        # 선택된 마감기한
        # if hasattr(self, 'selected_deadline'):
        #     if self.selected_deadline:
        #         deadline = datetime.fromisoformat(self.selected_deadline)
        #         embed.add_field(
        #             name="⏳ 참가 신청 마감",
        #             value=f"{deadline.strftime('%m월 %d일 %H:%M')}",
        #             inline=False
        #         )
        #     else:
        #         embed.add_field(
        #             name="⏰ 참가 신청 마감",
        #             value="없음 (언제든 참가 가능)",
        #             inline=False
        #         )
        
        basic_ready = self._validate_required_fields()
        
        if basic_ready:
            embed.color = 0x00ff00
            embed.add_field(
                name="✅ 기본 설정 완료",
                value="**다음**: 선택사항 입력 (직접시간, 설명 등)\n"
                    "**바로 등록**: 현재 설정으로 즉시 등록",
                inline=False
            )
        else:
            # 🔧 수정된 누락 항목 체크
            missing = []
            clan_ready = self.selected_clan or self.use_custom_input
            time_ready = self.selected_times or self.use_custom_time 
            
            if not clan_ready:
                missing.append("상대팀")
            if not self.selected_dates:
                missing.append("날짜")
            if not time_ready:  
                missing.append("시간대")
            if not self.selected_tier:
                missing.append("티어")
            
            embed.add_field(
                name="⚠️ 필수 항목 미완료",
                value=f"다음을 선택해주세요: {', '.join(missing)}",
                inline=False
            )
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def register_callback(self, interaction: discord.Interaction):
        """등록 처리 (다음 단계와 바로 등록 통합)"""
        if not self._validate_required_fields():
            await interaction.response.send_message(
                "❌ 모든 필수 항목을 선택해주세요!", ephemeral=True
            )
            return
        
        # 직접입력이 필요한 경우 Modal 표시
        if self.use_custom_input or self.use_custom_time:
            modal = ScrimOptionalInputModal(
                bot=self.bot,
                channel_id=self.channel_id,
                main_config=self
            )
            await interaction.response.send_modal(modal)
        else:
            # 바로 등록 (선택사항 없이)
            await self._process_registration(
                interaction, 
                custom_time=None, 
                description=None, 
                custom_opponent=None
            )
    
    async def next_step_callback(self, interaction: discord.Interaction):
        """선택사항 입력 단계로 이동"""
        if not self._validate_required_fields():
            await interaction.response.send_message(
                "❌ 모든 필수 항목을 선택해주세요!", ephemeral=True
            )
            return
        
        # 선택사항 입력을 위한 Modal 표시
        modal = ScrimOptionalInputModal(
            bot=self.bot,
            channel_id=self.channel_id,
            main_config=self
        )
        
        await interaction.response.send_modal(modal)
    
    async def direct_register_callback(self, interaction: discord.Interaction):
        """선택사항 없이 바로 등록"""
        if not self._validate_required_fields():
            await interaction.response.send_message(
                "❌ 모든 필수 항목을 선택해주세요!", ephemeral=True
            )
            return
        
        await self._process_registration(interaction, custom_time=None, description=None)
    
    async def cancel_callback(self, interaction: discord.Interaction):
        """취소 처리"""
        embed = discord.Embed(
            title="❌ 스크림 공지 등록 취소",
            description="스크림 공지 등록이 취소되었습니다.",
            color=0xff4444
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    def _validate_required_fields(self) -> bool:
        """필수 필드 검증"""
        clan_ready = self.selected_clan or self.use_custom_input
        time_ready = self.selected_times or self.use_custom_time 
        return (clan_ready and self.selected_dates and 
                time_ready and self.selected_tier)
    
    async def _process_registration(self, interaction, custom_time=None, description=None, custom_opponent=None):
        """실제 스크림 등록 처리"""
        await interaction.response.defer()
        
        try:
            # 상대팀명 결정
            if self.use_custom_input and custom_opponent:
                opponent_team = custom_opponent
            elif self.selected_clan:
                opponent_team = self.selected_clan
            else:
                await interaction.followup.send("❌ 상대팀명이 설정되지 않았습니다.", ephemeral=True)
                return
            
            # 우리 클랜명 가져오기
            our_clan = await self.bot.db_manager.get_our_clan_name(str(interaction.guild_id))
            our_team_name = our_clan or "우리서버"
            
            # 시간대 목록 준비
            available_times = self.selected_times.copy()
            if custom_time:
                available_times.append(custom_time)
            
            # 날짜/시간 조합 생성
            time_combinations = []
            for date_str in self.selected_dates:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                weekday = ["월", "화", "수", "목", "금", "토", "일"][date_obj.weekday()]
                date_display = f"{date_obj.month}/{date_obj.day}({weekday})"
                
                for time_slot in available_times:
                    time_combinations.append({
                        'date': date_str,
                        'date_display': date_display,
                        'time': time_slot,
                        'is_custom': time_slot == custom_time
                    })

            # 마감기한 설정
            if hasattr(self, 'selected_deadline') and self.selected_deadline:
                deadline_date = self.selected_deadline
            else:
                earliest_date_str = min(self.selected_dates)  
                earliest_date = datetime.strptime(earliest_date_str, "%Y-%m-%d")
                auto_deadline = earliest_date - timedelta(days=1)
                auto_deadline = auto_deadline.replace(hour=23, minute=59, second=59)
                deadline_date = auto_deadline.isoformat()
            
            # 스크림 데이터 준비
            scrim_data = {
                'guild_id': str(interaction.guild_id),
                'title': f"{our_team_name} vs {opponent_team}",
                'description': description,
                'tier_range': self.selected_tier,
                'opponent_team': opponent_team,
                'primary_date': self.selected_dates[0],
                'deadline_date': deadline_date,
                'channel_id': str(self.channel_id or interaction.channel_id),
                'created_by': str(interaction.user.id),
                'time_combinations': time_combinations
            }
            
            # 데이터베이스에 스크림 저장
            scrim_id = await self.bot.db_manager.create_enhanced_scrim(scrim_data)
            
            # 공지 메시지 생성 및 전송
            channel = interaction.guild.get_channel(self.channel_id or interaction.channel_id)
            if not channel:
                await interaction.followup.send("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
                return
            
            # 공지 임베드와 View 생성
            embed, view = await self.create_recruitment_message(
                scrim_id, our_team_name, opponent_team, time_combinations, description
            )
            
            # 공지 메시지 전송
            message = await channel.send(embed=embed, view=view)
            
            # 성공 메시지
            success_embed = discord.Embed(
                title="✅ 스크림 공지 등록 완료!",
                description=f"**{opponent_team}**과의 스크림 모집이 등록되었습니다!",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            
            success_embed.add_field(
                name="📍 등록 정보",
                value=f"**채널**: {channel.mention}\n"
                      f"**티어**: {self.selected_tier}\n"
                      f"**날짜/시간**: {len(time_combinations)}개 조합\n"
                      f"**스크림 ID**: `{scrim_id[:8]}...`",
                inline=False
            )
            
            # 자동 DM 알림 발송
            try:
                eligible_users = await self.bot.db_manager.get_tier_eligible_users(
                    str(interaction.guild_id), self.selected_tier
                )
                notification_count = await self.send_tier_notifications(
                    eligible_users, scrim_data, interaction.guild
                )
                
                if notification_count > 0:
                    success_embed.add_field(
                        name="📬 자동 알림",
                        value=f"{notification_count}명의 해당 티어 유저에게 DM 알림을 발송했습니다!",
                        inline=False
                    )
            except Exception as e:
                print(f"❌ DM 알림 발송 실패: {e}")
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 스크림 공지 등록 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )
    
    async def create_recruitment_message(self, scrim_id: str, our_team: str, opponent_team: str, 
                                       time_combinations: list, description: str = None):
        """모집 공지 메시지 생성"""
        embed = discord.Embed(
            title=f"{our_team} vs {opponent_team}",
            description=f"**티어**: {self.selected_tier}",
            color=0xff6b35,
            timestamp=datetime.now()
        )
        
        # 날짜/시간 조합 표시
        schedule_text = []
        for combo in time_combinations:
            schedule_text.append(f"**{combo['date_display']}** - {combo['time']}")
        
        embed.add_field(
            name="📅 스크림 일정",
            value="\n".join(schedule_text),
            inline=False
        )
        
        if description:
            embed.add_field(
                name="📝 추가 안내",
                value=description,
                inline=False
            )
        
        embed.add_field(
            name="🎯 참여 방법",
            value="• 원하는 날짜/시간 조합을 선택하세요\n"
                  "• 포지션 버튼을 눌러 참여 의사를 표시하세요\n"
                  "• 언제든 참가 ↔ 불참 변경 가능합니다\n"
                  "• 참가자 목록 버튼으로 현황 확인 가능합니다",
            inline=False
        )
        
        embed.set_footer(text=f"모집 ID: {scrim_id[:8]}")
        
        # View 생성
        view = ScrimParticipationView(self.bot, scrim_id)

        if hasattr(self, 'selected_deadline') and self.selected_deadline:
            view.update_embed_with_deadline(embed, self.selected_deadline)
        
        return embed, view
    
    async def send_tier_notifications(self, eligible_users: List[Dict], scrim_data: Dict, guild) -> int:
        """해당 티어 유저들에게 DM 알림 발송"""
        success_count = 0
        
        for user_data in eligible_users:
            try:
                user_id = int(user_data['user_id'])
                user = self.bot.get_user(user_id)
                
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except:
                        continue
                
                # DM 임베드 생성
                dm_embed = discord.Embed(
                    title="🎯 새로운 스크림 모집 알림",
                    description=f"**{guild.name}**에서 당신의 티어에 맞는 스크림 모집이 등록되었습니다!",
                    color=0xff6b35
                )
                
                dm_embed.add_field(
                    name="⚔️ 스크림 정보",
                    value=f"**상대팀**: {scrim_data['opponent_team']}\n"
                          f"**티어**: {scrim_data['tier_range']}\n"
                          f"**일정**: {len(scrim_data['time_combinations'])}개 시간대",
                    inline=False
                )
                
                if scrim_data.get('description'):
                    dm_embed.add_field(
                        name="📝 상세 내용",
                        value=scrim_data['description'],
                        inline=False
                    )
                
                dm_embed.add_field(
                    name="🚀 참여하기",
                    value=f"서버의 스크림 공지 채널을 확인하여 참여해보세요!",
                    inline=False
                )
                
                await user.send(embed=dm_embed)
                success_count += 1
                
            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"❌ DM 발송 실패 (User ID: {user_data.get('user_id')}): {e}")
        
        return success_count

class ScrimOptionalInputModal(discord.ui.Modal):
    """선택사항 입력을 위한 Modal (직접입력 상대팀명, 시간, 설명)"""
    
    def __init__(self, bot, channel_id: int, main_config: ScrimMainConfigurationView):
        super().__init__(title="🎯 스크림 선택사항 입력", timeout=300)
        self.bot = bot
        self.channel_id = channel_id
        self.main_config = main_config
        
        # 직접입력 상대팀명 (직접입력 선택시에만)
        if main_config.use_custom_input:
            self.opponent_team = discord.ui.TextInput(
                label="상대팀명 (필수)",
                placeholder="예: 명지대학교, 서강대학교 등",
                required=True,
                max_length=50
            )
            self.add_item(self.opponent_team)
        
        # 직접입력 시간대 (선택사항)
        self.custom_time = discord.ui.TextInput(
            label="직접입력 시간대 (선택사항)",
            placeholder="예: 18:00-20:00, 21:30-23:30 등",
            required=False,
            max_length=100
        )
        self.add_item(self.custom_time)
        
        # 추가 설명
        self.description = discord.ui.TextInput(
            label="추가 설명 (선택사항)",
            placeholder="특별한 조건이나 안내사항을 입력하세요",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        """Modal 제출 시 처리"""
        custom_opponent = str(self.opponent_team) if hasattr(self, 'opponent_team') else None
        custom_time = str(self.custom_time) if str(self.custom_time).strip() else None
        description = str(self.description) if str(self.description).strip() else None
        
        await self.main_config._process_registration(
            interaction, 
            custom_time=custom_time,
            description=description,
            custom_opponent=custom_opponent
        )

class ScrimParticipationView(discord.ui.View):
    """스크림 참여를 위한 View"""
    
    def __init__(self, bot, scrim_id: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.scrim_id = scrim_id
        self.user_selected_position = {}  
        self.user_selected_slot = {}      
        self.time_slots = []
        
        self.setup_static_components()
        self.datetime_selectors = {} 
    
    def setup_static_components(self):
        """항상 표시되는 컴포넌트들 설정"""
        # 1️⃣ 포지션 버튼들 (첫 번째 row)
        for position, emoji in POSITION_EMOJIS.items():
            button = discord.ui.Button(
                label=f"{position} 선택",
                emoji=emoji,
                style=discord.ButtonStyle.primary,
                row=0
            )
            button.callback = self.create_position_callback(position)
            self.add_item(button)
        
        # 2️⃣ 현황 확인 버튼 (두 번째 row)
        status_button = discord.ui.Button(
            label="📋 참가자 현황",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        status_button.callback = self.status_callback
        self.add_item(status_button)

        # 3️⃣ 관리자용 마감 버튼 (두 번째 row)
        finalize_button = discord.ui.Button(
            label="스크림 마감",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            row=1
        )
        finalize_button.callback = self.finalize_callback
        self.add_item(finalize_button)

    async def finalize_callback(self, interaction: discord.Interaction):
        """관리자용 스크림 마감 콜백"""
        # 관리자 권한 체크
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ 스크림 마감은 관리자만 가능합니다.", ephemeral=True
            )
            return
        
        try:
            # 스크림 시간대 목록 조회
            time_slots = await self.bot.db_manager.get_scrim_time_slots(self.scrim_id)
            
            if not time_slots:
                await interaction.response.send_message(
                    "❌ 등록된 시간대가 없습니다.", ephemeral=True
                )
                return
            
            # 마감 시간대 선택 View 생성
            finalize_view = ScrimFinalizeView(self.bot, self.scrim_id, time_slots)
            
            embed = discord.Embed(
                title="🔒 스크림 마감 처리",
                description="확정할 시간대를 선택하면 해당 시간대의 모든 참가자에게 확정 알림을 보냅니다.",
                color=0xff6600
            )
            
            # 시간대별 현재 참가자 수 표시
            time_slot_info = []
            for slot in time_slots:
                participants = await self.bot.db_manager.get_position_participants(slot['id'])
                total_count = sum(len(pos_list) for pos_list in participants.values())
                
                time_slot_info.append(
                    f"**{slot['date_display']} {slot['time_slot']}**: {total_count}명 참가"
                )
            
            embed.add_field(
                name="📊 현재 참가 현황",
                value="\n".join(time_slot_info),
                inline=False
            )
            
            embed.add_field(
                name="⚠️ 주의사항",
                value="• 마감 후에는 새로운 참가 신청이 불가능합니다\n"
                      "• 확정된 시간대의 모든 참가자에게 DM이 발송됩니다\n"
                      "• 마감 처리 후에는 되돌릴 수 없습니다",
                inline=False
            )
            
            await interaction.response.send_message(
                embed=embed, view=finalize_view, ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 마감 처리 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )
            print(f"❌ Finalize callback error: {e}")
    
    def create_position_callback(self, position: str):
        """포지션 선택 콜백 생성기"""
        async def position_callback(interaction: discord.Interaction):
            # 스크림이 이미 마감되었는지 체크
            if await self.bot.db_manager.is_scrim_finalized(self.scrim_id):
                await interaction.response.send_message(
                    "🔒 이 스크림은 이미 마감되었습니다. 새로운 참가 신청은 불가능합니다.", 
                    ephemeral=True
                )
                return
            
            # 스크림 정보 조회 (마감기한 포함)
            scrim_info = await self.bot.db_manager.get_scrim_info(self.scrim_id)
            
            # 마감기한 체크
            if scrim_info and self.is_deadline_passed(scrim_info.get('deadline_date')):
                embed = discord.Embed(
                    title="⏰ 참가 신청 마감",
                    description="죄송합니다. 이 스크림의 참가 신청 마감기한이 지났습니다.",
                    color=0xff4444
                )
                
                deadline = datetime.fromisoformat(scrim_info['deadline_date'])
                embed.add_field(
                    name="마감 시간",
                    value=f"{deadline.strftime('%Y년 %m월 %d일 %H:%M')}",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            user_id = str(interaction.user.id)
            
            try:
                # 시간대 데이터 로딩 (첫 포지션 선택시)
                if not self.time_slots:
                    self.time_slots = await self.bot.db_manager.get_scrim_time_slots(self.scrim_id)
                
                if not self.time_slots:
                    await interaction.response.send_message(
                        "❌ 사용 가능한 시간대가 없습니다.", ephemeral=True
                    )
                    return
                
                # 사용자의 포지션 선택 기록
                self.user_selected_position[user_id] = position
                
                # 사용자의 현재 참가 상태 조회
                user_status = await self.bot.db_manager.get_user_participation_status(
                    self.scrim_id, user_id
                )
                
                # 시간대 선택 옵션 생성
                time_options = []
                status_info = []
                
                for slot in self.time_slots:
                    slot_key = f"{slot['date_display']} {slot['time_slot']}"
                    
                    # 현재 참가 상태 확인
                    current_positions = user_status.get(slot_key, {}).get('positions', [])
                    is_participating = position in current_positions
                    
                    # 옵션 라벨 설정
                    label = f"{'✅' if is_participating else '⭕'} {slot_key}"
                    if is_participating:
                        label += " (참가중)"
                    
                    time_options.append(discord.SelectOption(
                        label=label,
                        value=str(slot['id']),
                        description=f"{'참가 취소' if is_participating else '참가 신청'}"
                    ))
                    
                    if is_participating:
                        status_info.append(f"✅ {slot_key}")
                
                # 임시 View 생성 (시간대 선택용)
                time_select_view = TimeSlotSelectionView(
                    self, position, time_options, user_id
                )
                
                # 응답 메시지 생성
                current_status = f"\n\n**현재 {position} 참가 시간:**\n" + "\n".join(status_info) if status_info else f"\n\n**{position} 포지션에 아직 참가하지 않았습니다.**"
                
                await interaction.response.send_message(
                    f"🎯 **{position}** 포지션을 선택했습니다!"
                    f"{current_status}\n\n"
                    f"⬇️ 아래에서 참가하고 싶은 시간대를 선택하거나 참가를 취소하세요:",
                    view=time_select_view,
                    ephemeral=True
                )
                
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ 포지션 선택 처리 중 오류: {str(e)}", ephemeral=True
                )
                print(f"❌ Position callback error: {e}")
                import traceback
                traceback.print_exc()
        
        return position_callback
    
    async def status_callback(self, interaction: discord.Interaction):
        """참가자 현황 표시 (오류 방지 강화)"""
        try:
            scrim_summary = await self.bot.db_manager.get_enhanced_scrim_summary(self.scrim_id)
            
            if not scrim_summary:
                await interaction.response.send_message(
                    "❌ 스크림 정보를 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="📋 스크림 참가자 현황",
                description=f"**{scrim_summary['title']}**",
                color=0x0099ff
            )
            
            for slot in scrim_summary['time_slots']:
                participants_text = []
                
                for position, participants in slot['participants'].items():
                    # 포지션 정규화 (공백, 대소문자 등 처리)
                    normalized_position = str(position).strip()
                    emoji = POSITION_EMOJIS.get(normalized_position, "❓")
                    
                    if emoji == "❓":
                        print(f"⚠️ 알 수 없는 포지션 감지: '{position}' (정규화: '{normalized_position}')")
                        print(f"📝 사용 가능한 포지션들: {list(POSITION_EMOJIS.keys())}")
                    
                    if participants:
                        names = [p['username'] for p in participants]
                        participants_text.append(f"{emoji} **{normalized_position}**: {', '.join(names)}")
                    else:
                        participants_text.append(f"{emoji} **{normalized_position}**: 없음")
                
                embed.add_field(
                    name=f"📅 {slot['date_display']} {slot['time_slot']}",
                    value="\n".join(participants_text) + f"\n**총 {slot['total_participants']}명**",
                    inline=True
                )
            
            embed.set_footer(text=f"전체 {scrim_summary['total_time_slots']}개 시간대")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except KeyError as e:
            # 🔧 구체적인 키 오류 정보
            await interaction.response.send_message(
                f"❌ 포지션 키 오류: {str(e)}\n디버깅 정보를 콘솔에서 확인해주세요.", ephemeral=True
            )
            print(f"❌ KeyError in status_callback: {e}")
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 현황 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )
            print(f"❌ General error in status_callback: {e}")
            import traceback
            traceback.print_exc()

    def update_embed_with_deadline(self, embed, deadline_iso: str):
        """모집 공지에 마감기한 정보 추가/업데이트"""
        if deadline_iso:
            deadline = datetime.fromisoformat(deadline_iso)
            now = datetime.now()
            
            if now > deadline:
                embed.add_field(
                    name="⏰ 참가 신청 마감",
                    value=f"~~{deadline.strftime('%Y년 %m월 %d일 %H:%M')}~~ **마감됨**",
                    inline=True
                )
                embed.color = 0x888888  # 회색으로 변경
            else:
                time_left = deadline - now
                if time_left.total_seconds() < 3600:  # 1시간 미만
                    minutes_left = int(time_left.total_seconds() / 60)
                    urgency = f"⚠️ **{minutes_left}분 남음!**"
                    embed.color = 0xff6600  # 주황색으로 변경
                else:
                    urgency = f"{deadline.strftime('%m월 %d일 %H:%M')} 마감"
                
                embed.add_field(
                    name="⏳ 참가 신청 마감",
                    value=urgency,
                    inline=True
                )

    def is_deadline_passed(self, deadline_iso: str) -> bool:
        """마감기한이 지났는지 확인"""
        if not deadline_iso:
            return False
        
        deadline = datetime.fromisoformat(deadline_iso)
        return datetime.now() > deadline

    async def position_callback_with_deadline_check(self, interaction: discord.Interaction):
        """마감기한을 체크하는 포지션 콜백"""
        # 스크림 정보 조회 (마감기한 포함)
        scrim_info = await self.bot.db_manager.get_scrim_info(self.scrim_id)
        
        if scrim_info and self.is_deadline_passed(scrim_info.get('deadline_date')):
            embed = discord.Embed(
                title="⏰ 참가 신청 마감",
                description="죄송합니다. 이 스크림의 참가 신청 마감기한이 지났습니다.",
                color=0xff4444
            )
            
            deadline = datetime.fromisoformat(scrim_info['deadline_date'])
            embed.add_field(
                name="마감 시간",
                value=f"{deadline.strftime('%Y년 %m월 %d일 %H:%M')}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

class ScrimFinalizeView(discord.ui.View):
    """스크림 마감 시간대 선택을 위한 View"""
    
    def __init__(self, bot, scrim_id: str, time_slots: List[Dict]):
        super().__init__(timeout=300)
        self.bot = bot
        self.scrim_id = scrim_id
        self.time_slots = time_slots
        
        self.setup_time_slot_selector()
    
    def setup_time_slot_selector(self):
        """시간대 선택 드롭다운 설정"""
        if not self.time_slots:
            return
        
        # 시간대 선택 옵션들 생성
        slot_options = []
        for slot in self.time_slots[:25]:  # Discord 제한
            slot_options.append(discord.SelectOption(
                label=f"{slot['date_display']} {slot['time_slot']}",
                value=str(slot['id']),
                description=f"이 시간대를 확정하고 참가자들에게 알림 발송"
            ))
        
        time_slot_select = discord.ui.Select(
            placeholder="🔒 확정할 시간대를 선택하세요",
            options=slot_options,
            max_values=1,
            row=0
        )
        time_slot_select.callback = self.time_slot_selected_callback
        self.add_item(time_slot_select)
        
        # 취소 버튼
        cancel_button = discord.ui.Button(
            label="❌ 취소",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)
    
    async def time_slot_selected_callback(self, interaction: discord.Interaction):
        """시간대 선택 시 마감 처리"""
        try:
            selected_slot_id = int(interaction.data['values'][0])
            
            # 선택된 시간대 정보 찾기
            selected_slot = None
            for slot in self.time_slots:
                if slot['id'] == selected_slot_id:
                    selected_slot = slot
                    break
            
            if not selected_slot:
                await interaction.response.send_message(
                    "❌ 선택된 시간대를 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # 해당 시간대의 참가자들 조회
            participants = await self.bot.db_manager.get_position_participants(selected_slot_id)
            
            # 참가자들의 상세 정보 수집
            all_participants = []
            for position, participant_list in participants.items():
                for participant in participant_list:
                    all_participants.append({
                        'user_id': participant['user_id'],
                        'username': participant['username'],
                        'position': position
                    })
            
            if not all_participants:
                await interaction.followup.send(
                    f"❌ **{selected_slot['date_display']} {selected_slot['time_slot']}** 시간대에 참가자가 없습니다.", 
                    ephemeral=True
                )
                return
            
            # 스크림 기본 정보 조회
            scrim_info = await self.bot.db_manager.get_scrim_info(self.scrim_id)
            if not scrim_info:
                await interaction.followup.send("❌ 스크림 정보를 찾을 수 없습니다.", ephemeral=True)
                return
            
            # 해당 시간대를 확정 상태로 변경
            success = await self.bot.db_manager.finalize_time_slot(
                self.scrim_id, selected_slot_id
            )
            
            if not success:
                await interaction.followup.send("❌ 시간대 확정 처리에 실패했습니다.", ephemeral=True)
                return
            
            # 확정된 참가자들에게 DM 발송
            dm_sent_count = await self.send_confirmation_dms(
                all_participants, selected_slot, scrim_info, interaction.guild
            )
            
            # 성공 메시지
            success_embed = discord.Embed(
                title="✅ 스크림 마감 완료!",
                description=f"**{selected_slot['date_display']} {selected_slot['time_slot']}** 시간대가 확정되었습니다.",
                color=0x00ff00
            )
            
            # 확정된 참가자 목록 표시
            participant_summary = []
            for position, participant_list in participants.items():
                if participant_list:
                    names = [p['username'] for p in participant_list]
                    emoji = POSITION_EMOJIS.get(position, "❓")
                    participant_summary.append(f"{emoji} **{position}**: {', '.join(names)}")
            
            success_embed.add_field(
                name="🎮 확정된 참가자 명단",
                value="\n".join(participant_summary),
                inline=False
            )
            
            success_embed.add_field(
                name="📬 알림 발송 결과",
                value=f"총 {len(all_participants)}명 중 {dm_sent_count}명에게 확정 알림을 발송했습니다.",
                inline=False
            )
            
            success_embed.add_field(
                name="🔒 주의사항",
                value="이제 이 시간대는 새로운 참가 신청을 받지 않습니다.",
                inline=False
            )
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 마감 처리 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )
            print(f"❌ Time slot finalization error: {e}")
            import traceback
            traceback.print_exc()
    
    async def send_confirmation_dms(self, participants: List[Dict], 
                                   time_slot: Dict, scrim_info: Dict, guild) -> int:
        """확정된 참가자들에게 확정 DM 발송"""
        success_count = 0
        
        for participant in participants:
            try:
                user_id = int(participant['user_id'])
                user = self.bot.get_user(user_id)
                
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except:
                        continue
                
                # 확정 알림 embed 생성
                dm_embed = discord.Embed(
                    title="🎯 스크림 확정 알림",
                    description=f"**{guild.name}**에서 참가 신청한 스크림이 확정되었습니다!",
                    color=0x00ff00
                )
                
                dm_embed.add_field(
                    name="⚔️ 스크림 정보",
                    value=f"**제목**: {scrim_info['title']}\n"
                          f"**상대팀**: {scrim_info['opponent_team']}\n"
                          f"**티어**: {scrim_info['tier_range']}",
                    inline=False
                )
                
                dm_embed.add_field(
                    name="📅 확정된 일정",
                    value=f"**날짜**: {time_slot['date_display']}\n"
                          f"**시간**: {time_slot['time_slot']}\n"
                          f"**포지션**: {participant['position']}",
                    inline=False
                )
                
                if scrim_info.get('description'):
                    dm_embed.add_field(
                        name="📝 추가 안내",
                        value=scrim_info['description'],
                        inline=False
                    )
                
                dm_embed.add_field(
                    name="🚀 다음 단계",
                    value="스크림 시작 전까지 디스코드에 접속해 계시기 바랍니다.\n"
                          "추가 안내사항이 있으면 서버 공지를 확인해주세요!",
                    inline=False
                )
                
                dm_embed.set_footer(text=f"스크림 ID: {self.scrim_id[:8]}")
                
                await user.send(embed=dm_embed)
                success_count += 1
                
            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"❌ DM 발송 실패 (User ID: {participant.get('user_id')}): {e}")
        
        return success_count
    
    async def cancel_callback(self, interaction: discord.Interaction):
        """취소 버튼 콜백"""
        await interaction.response.edit_message(
            content="❌ 스크림 마감이 취소되었습니다.",
            embed=None,
            view=None
        )


class TimeSlotSelectionView(discord.ui.View):
    """시간대 선택을 위한 임시 View"""
    
    def __init__(self, parent_view, position: str, time_options: list, user_id: str):
        super().__init__(timeout=300)  # 5분 후 만료
        self.parent_view = parent_view
        self.position = position
        self.user_id = user_id
        
        if time_options:
            time_select = discord.ui.Select(
                placeholder=f"🎯 {position} 포지션으로 참가할 시간대를 선택하세요",
                options=time_options[:25],  # Discord 제한
                row=0
            )
            time_select.callback = self.time_slot_callback
            self.add_item(time_select)
    
    async def time_slot_callback(self, interaction: discord.Interaction):
        """시간대 선택 처리"""
        try:
            selected_slot_id = int(interaction.data['values'][0])
            
            # 선택된 슬롯 정보 찾기
            selected_slot = None
            for slot in self.parent_view.time_slots:
                if slot['id'] == selected_slot_id:
                    selected_slot = slot
                    break
            
            if not selected_slot:
                await interaction.response.send_message(
                    "❌ 선택된 시간대를 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            username = interaction.user.display_name
            
            # 현재 참가 상태 확인
            current_participants = await self.parent_view.bot.db_manager.get_position_participants(selected_slot_id)
            user_positions = []
            
            for pos, participants in current_participants.items():
                for participant in participants:
                    if participant['user_id'] == self.user_id:
                        user_positions.append(pos)
            
            if self.position in user_positions:
                # 참가 취소
                success = await self.parent_view.bot.db_manager.remove_position_participant(
                    self.parent_view.scrim_id, selected_slot_id, self.user_id, self.position
                )
                if success:
                    await self.notify_admin_participation_change(
                        interaction, selected_slot, "취소", self.position
                    )
                    
                    await interaction.response.edit_message(
                        content=f"✅ **{selected_slot['date_display']} {selected_slot['time_slot']}**\n"
                               f"**{self.position}** 포지션 참가가 취소되었습니다!",
                        view=None
                    )
                else:
                    await interaction.response.send_message(
                        "❌ 참가 취소 처리 중 오류가 발생했습니다.", ephemeral=True
                    )
            else:
                # 참가 신청
                success = await self.parent_view.bot.db_manager.add_position_participant(
                    self.parent_view.scrim_id, selected_slot_id, self.user_id, username, self.position
                )
                if success:
                    await self.notify_admin_participation_change(
                        interaction, selected_slot, "신청", self.position
                    )

                    await interaction.response.edit_message(
                        content=f"🎯 **{selected_slot['date_display']} {selected_slot['time_slot']}**\n"
                               f"**{self.position}** 포지션으로 참가 신청되었습니다!",
                        view=None
                    )
                else:
                    await interaction.response.send_message(
                        "❌ 참가 신청 처리 중 오류가 발생했습니다.", ephemeral=True
                    )
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 시간대 선택 처리 중 오류: {str(e)}", ephemeral=True
            )
            print(f"❌ Time slot callback error: {e}")
            import traceback
            traceback.print_exc()

    async def notify_admin_participation_change(self, interaction: discord.Interaction, 
                                            time_slot: Dict, action_type: str, position: str):
        """관리자에게 참가 신청/취소 알림 DM 발송"""
        try:
            # 스크림 정보 조회 (생성자 정보 포함)
            scrim_info = await self.parent_view.bot.db_manager.get_scrim_info(self.parent_view.scrim_id)
            if not scrim_info:
                print("❌ 스크림 정보 조회 실패")
                return
            
            # 스크림 생성자(관리자) 가져오기
            admin_id = int(scrim_info['created_by'])
            admin_user = self.parent_view.bot.get_user(admin_id)
            
            if not admin_user:
                try:
                    admin_user = await self.parent_view.bot.fetch_user(admin_id)
                except:
                    print(f"❌ 관리자 사용자 조회 실패 (ID: {admin_id})")
                    return
            
            # 현재 해당 시간대의 총 참가자 수 조회
            current_participants = await self.parent_view.bot.db_manager.get_position_participants(
                time_slot['id']
            )
            total_participants = sum(len(pos_list) for pos_list in current_participants.values())
            
            # 알림 embed 생성
            if action_type == "신청":
                embed_color = 0x00ff00  # 초록색
                embed_title = "🎯 새로운 참가 신청"
                action_emoji = "✅"
            else:  # 취소
                embed_color = 0xff6600  # 주황색
                embed_title = "📤 참가 취소 알림"
                action_emoji = "❌"
            
            admin_embed = discord.Embed(
                title=embed_title,
                description=f"**{scrim_info['title']}**에 참가 변동이 있습니다.",
                color=embed_color
            )
            
            admin_embed.add_field(
                name=f"{action_emoji} 참가 {action_type} 정보",
                value=f"**사용자**: {interaction.user.display_name} (`{interaction.user.name}`)\n"
                    f"**포지션**: {position}\n"
                    f"**시간대**: {time_slot['date_display']} {time_slot['time_slot']}",
                inline=False
            )
            
            # 현재 참가 현황 요약
            position_summary = []
            for pos, participants in current_participants.items():
                if participants:
                    position_emoji = POSITION_EMOJIS.get(pos, "❓")
                    position_summary.append(f"{position_emoji} **{pos}**: {len(participants)}명")
                else:
                    position_emoji = POSITION_EMOJIS.get(pos, "❓")
                    position_summary.append(f"{position_emoji} **{pos}**: 0명")
            
            admin_embed.add_field(
                name="📊 해당 시간대 현재 참가 현황",
                value="\n".join(position_summary) + f"\n\n**총 참가자**: {total_participants}명",
                inline=False
            )
            
            admin_embed.add_field(
                name="🔗 바로가기",
                value=f"서버의 스크림 공지 채널에서 현황을 확인하세요.\n"
                    f"스크림 ID: `{scrim_info['id'][:8]}...`",
                inline=False
            )
            
            admin_embed.set_footer(text=f"{interaction.guild.name}")
            admin_embed.timestamp = datetime.now()
            
            # 관리자에게 DM 발송
            await admin_user.send(embed=admin_embed)
            print(f"✅ 관리자에게 참가 {action_type} 알림 발송 완료")
            
        except discord.Forbidden:
            print(f"❌ 관리자 DM 발송 실패 - DM 차단됨 (Admin ID: {admin_id})")
        except Exception as e:
            print(f"❌ 관리자 알림 발송 중 오류: {e}")
            import traceback
            traceback.print_exc()

class DeadlineSelectionView(discord.ui.View):
    """마감기한 선택을 위한 별도 View"""
    
    def __init__(self, parent_config: ScrimMainConfigurationView):
        super().__init__(timeout=300)
        self.parent_config = parent_config
        self.setup_deadline_buttons()
    
    def setup_deadline_buttons(self):
        """마감기한 버튼들 설정"""
        if not self.parent_config.selected_dates:
            return
        
        # 가장 빠른 스크림 날짜 기준으로 마감기한 옵션 생성
        earliest_date_str = min(self.parent_config.selected_dates)
        earliest_date = datetime.strptime(earliest_date_str, "%Y-%m-%d")
        now = datetime.now()
        
        # 주요 마감기한 옵션들
        deadline_options = [
            (0, "당일", "스크림 당일까지"),
            (1, "1일 전", "스크림 하루 전"),
            (2, "2일 전", "스크림 이틀 전"),
            (3, "3일 전", "스크림 3일 전")
        ]
        
        row = 0
        for days_before, label, description in deadline_options:
            if row >= 4:  # row 제한
                break
                
            deadline_date = earliest_date - timedelta(days=days_before)
            deadline_time = deadline_date.replace(hour=23, minute=0)
            
            # 이미 지난 시간은 제외
            if deadline_time <= now:
                continue
            
            button = discord.ui.Button(
                label=f"{label} ({deadline_time.strftime('%m/%d %H:%M')})",
                style=discord.ButtonStyle.primary,
                row=row
            )
            button.callback = self.create_deadline_callback(deadline_time.isoformat())
            self.add_item(button)
            row += 1
        
        # 마감기한 없음 버튼
        no_deadline_button = discord.ui.Button(
            label="⏰ 마감기한 없음",
            style=discord.ButtonStyle.secondary,
            row=row if row < 4 else 3
        )
        no_deadline_button.callback = self.no_deadline_callback
        self.add_item(no_deadline_button)
    
    def create_deadline_callback(self, deadline_iso: str):
        """마감기한 선택 콜백 생성기"""
        async def callback(interaction: discord.Interaction):
            self.parent_config.selected_deadline = deadline_iso
            
            deadline = datetime.fromisoformat(deadline_iso)
            await interaction.response.edit_message(
                content=f"✅ 마감기한이 **{deadline.strftime('%m월 %d일 %H:%M')}**로 설정되었습니다!",
                embed=None,
                view=None
            )
        return callback
    
    async def no_deadline_callback(self, interaction: discord.Interaction):
        """마감기한 없음 콜백"""
        self.parent_config.selected_deadline = None
        await interaction.response.edit_message(
            content="✅ 마감기한이 **없음**으로 설정되었습니다! (언제든 참가 신청 가능)",
            embed=None,
            view=None
        )

class InterGuildScrimCommands(commands.Cog):
    """개선된 스크림 모집 명령어"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="스크림공지등록", description="[관리자] 길드간 스크림 모집 공지를 등록합니다")
    @app_commands.describe(channel="공지를 게시할 채널 (생략시 현재 채널)")
    @app_commands.default_permissions(manage_guild=True)
    async def register_scrim_recruitment(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None
    ):
        try:
            await interaction.response.defer(ephemeral=True)
            
            # 채널 설정
            target_channel = channel or interaction.channel
            
            # 등록된 클랜 목록 가져오기
            try:
                all_available_clans = await self.bot.db_manager.get_available_clans_for_dropdown(
                    str(interaction.guild_id)
                )
                
                # 우리 서버 클랜명 가져오기
                our_clan_name = await self.bot.db_manager.get_our_clan_name(str(interaction.guild_id))
                
                # 우리 서버 클랜을 제외한 클랜들만 필터링
                available_clans = []
                for clan in all_available_clans:
                    if clan['name'] != our_clan_name:
                        available_clans.append(clan)
                        
            except Exception as e:
                print(f"클랜 목록 조회 오류: {e}")
                available_clans = []
            
            # 메인 설정 View 생성 및 표시
            view = ScrimMainConfigurationView(
                bot=self.bot,
                channel_id=target_channel.id,
                available_clans=available_clans
            )
            
            embed = discord.Embed(
                title="🎯 스크림 모집 공지 등록",
                description="필수 항목들을 차례대로 선택해주세요",
                color=0x0099ff
            )
            
            embed.add_field(
                name="📋 설정 순서",
                value="1️⃣ **상대팀 클랜** 선택 (등록된 클랜 또는 직접입력)\n"
                      "2️⃣ **날짜** 선택 (복수 선택 가능)\n"
                      "3️⃣ **시간대** 선택 (복수 선택 가능)\n"
                      "4️⃣ **참여 티어** 선택\n"
                      "5️⃣ **선택사항** 입력 (직접시간, 설명 등)",
                inline=False
            )
            
            if available_clans:
                embed.add_field(
                    name="🏠 등록된 클랜",
                    value=f"{len(available_clans)}개의 클랜이 드롭다운에서 선택 가능합니다",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📝 참고사항",
                    value="등록된 상대팀 클랜이 없어서 직접입력만 가능합니다.",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 스크림 공지 등록 중 오류가 발생했습니다: {str(e)}", 
                ephemeral=True
            )

    @app_commands.command(name="스크림모집현황", description="[관리자] 현재 모집중인 스크림 현황을 확인합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def check_scrim_status(self, interaction: discord.Interaction):
        """스크림 모집 현황 확인"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            active_scrims = await self.bot.db_manager.get_active_scrims(str(interaction.guild_id))
            
            embed = discord.Embed(
                title="🎯 스크림 모집 현황",
                description=f"현재 **{len(active_scrims)}**개의 스크림이 모집 중입니다.",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            if active_scrims:
                for scrim in active_scrims[:5]:
                    embed.add_field(
                        name=f"🎮 {scrim['title']}",
                        value=f"**티어**: {scrim['tier_range']}\n"
                              f"**참가자**: {scrim.get('participant_count', 0)}명\n"
                              f"**ID**: `{scrim['id'][:8]}...`",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="📭 모집 중인 스크림 없음",
                    value="현재 진행 중인 스크림 모집이 없습니다.",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 현황 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="스크림모집취소", description="[관리자] 진행중인 스크림 모집을 취소합니다")
    @app_commands.describe(scrim_id="취소할 스크림 모집 ID")
    @app_commands.default_permissions(manage_guild=True)
    async def cancel_scrim_recruitment(self, interaction: discord.Interaction, scrim_id: str):
        """스크림 모집 취소"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            success = await self.bot.db_manager.update_scrim_status(scrim_id, 'cancelled')
            
            if success:
                embed = discord.Embed(
                    title="✅ 스크림 모집 취소 완료",
                    description=f"스크림 모집 (ID: `{scrim_id[:8]}...`)이 취소되었습니다.",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="❌ 스크림 모집 취소 실패",
                    description=f"해당 ID의 스크림을 찾을 수 없습니다: `{scrim_id[:8]}...`",
                    color=0xff4444
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 취소 처리 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(InterGuildScrimCommands(bot))