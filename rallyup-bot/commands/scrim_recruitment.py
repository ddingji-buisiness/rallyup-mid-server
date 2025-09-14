import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional
from datetime import datetime, timedelta
import re

class RecruitmentView(discord.ui.View):
    """내전 모집 참가/불참 버튼 View"""
    
    def __init__(self, bot, recruitment_id: str):
        super().__init__(timeout=None)  # 시간 제한 없음 (마감시간까지 유효)
        self.bot = bot
        self.recruitment_id = recruitment_id
    
    @discord.ui.button(
        label="✅ 참가",
        style=discord.ButtonStyle.success,
        custom_id="join_scrim"
    )
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """참가 버튼 클릭 처리"""
        await self._handle_participation(interaction, "joined")
    
    @discord.ui.button(
        label="❌ 불참", 
        style=discord.ButtonStyle.danger,
        custom_id="decline_scrim"
    )
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """불참 버튼 클릭 처리"""
        await self._handle_participation(interaction, "declined")
    
    @discord.ui.button(
        label="📋 참가자 목록",
        style=discord.ButtonStyle.secondary,
        custom_id="show_participants"
    )
    async def participants_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """참가자 목록 보기"""
        await self._show_participants_list(interaction)
    
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
            
            # 5. 사용자 피드백
            status_text = "참가" if status == "joined" else "불참"
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
            # 1. 모집 정보 조회
            recruitment = await self.bot.db_manager.get_recruitment_by_id(self.recruitment_id)
            if not recruitment:
                await interaction.followup.send(
                    "❌ 모집 정보를 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            # 2. 참가자 목록 조회
            participants = await self.bot.db_manager.get_recruitment_participants(self.recruitment_id)
            
            joined_users = [p for p in participants if p['status'] == 'joined']
            declined_users = [p for p in participants if p['status'] == 'declined']
            
            # 3. 임베드 생성
            embed = discord.Embed(
                title=f"📋 {recruitment['title']} - 참가자 목록",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
            embed.add_field(
                name="📅 내전 일시",
                value=scrim_date.strftime('%Y년 %m월 %d일 %H:%M'),
                inline=False
            )
            
            # 4. 참가자 목록
            if joined_users:
                joined_list = []
                for i, user in enumerate(joined_users, 1):
                    joined_time = datetime.fromisoformat(user['joined_at'])
                    joined_list.append(f"{i}. {user['username']} ({joined_time.strftime('%m/%d %H:%M')})")
                
                embed.add_field(
                    name=f"✅ 참가자 ({len(joined_users)}명)",
                    value='\n'.join(joined_list) or "없음",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ 참가자 (0명)",
                    value="아직 참가자가 없습니다.",
                    inline=False
                )
            
            # 5. 불참자 목록 (선택적 표시)
            if declined_users and len(declined_users) <= 10:  # 너무 많으면 생략
                declined_list = [f"• {user['username']}" for user in declined_users]
                embed.add_field(
                    name=f"❌ 불참자 ({len(declined_users)}명)",
                    value='\n'.join(declined_list),
                    inline=False
                )
            elif declined_users:
                embed.add_field(
                    name=f"❌ 불참자 ({len(declined_users)}명)",
                    value="(목록 생략)",
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
        """모집 메시지 업데이트 (참가자 수 실시간 반영)"""
        try:
            # 1. 모집 정보 및 참가자 조회
            recruitment = await self.bot.db_manager.get_recruitment_by_id(self.recruitment_id)
            participants = await self.bot.db_manager.get_recruitment_participants(self.recruitment_id)
            
            joined_count = len([p for p in participants if p['status'] == 'joined'])
            declined_count = len([p for p in participants if p['status'] == 'declined'])
            
            # 2. 새로운 임베드 생성
            embed = await self._create_updated_embed(recruitment, joined_count, declined_count)
            
            # 3. 원본 메시지 업데이트
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
    
    def _create_participation_bar(self, joined: int, declined: int, total_width: int = 10) -> str:
        """참가자 비율 시각화 바 (개선된 버전)"""
        if joined == 0 and declined == 0:
            return "⬜" * total_width + f" (0명)"
        
        total = joined + declined
        joined_width = int((joined / total) * total_width) if total > 0 else 0
        declined_width = total_width - joined_width
        
        bar = "🟢" * joined_width + "🔴" * declined_width
        if joined_width + declined_width < total_width:
            bar += "⬜" * (total_width - joined_width - declined_width)
        
        return f"{bar} (총 {total}명 응답)"

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

    @app_commands.command(name="내전모집등록", description="[관리자] 이번주 내전 모집을 등록합니다")
    @app_commands.describe(
        날짜="내전 날짜 (예: 2024-12-25)",
        시간="내전 시간 (예: 20:00)",
        제목="내전 제목 (예: 이번주 정기 내전)",
        내용="내전 상세 내용 (선택사항)",
        마감시간="모집 마감 시간 (예: 2024-12-24 18:00)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def register_scrim_recruitment(
        self,
        interaction: discord.Interaction,
        날짜: str,
        시간: str,
        제목: str,
        내용: str = None,
        마감시간: str = None
    ):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # 1. 날짜/시간 파싱 및 검증
            scrim_datetime = self._parse_datetime(날짜, 시간)
            if not scrim_datetime:
                await interaction.followup.send(
                    "❌ 날짜 또는 시간 형식이 올바르지 않습니다.\n"
                    "**올바른 형식:**\n"
                    "• 날짜: `2024-12-25` 또는 `12-25`\n"
                    "• 시간: `20:00` 또는 `8:00PM`",
                    ephemeral=True
                )
                return

            # 2. 마감시간 파싱 (선택사항)
            deadline_datetime = None
            if 마감시간:
                deadline_datetime = self._parse_full_datetime(마감시간)
                if not deadline_datetime:
                    await interaction.followup.send(
                        "❌ 마감시간 형식이 올바르지 않습니다.\n"
                        "**올바른 형식:** `2024-12-24 18:00`",
                        ephemeral=True
                    )
                    return
                
                # 마감시간이 내전시간보다 늦으면 안됨
                if deadline_datetime >= scrim_datetime:
                    await interaction.followup.send(
                        "❌ 모집 마감시간은 내전 시작시간보다 빨라야 합니다.",
                        ephemeral=True
                    )
                    return
            else:
                # 기본값: 내전 1시간 전
                deadline_datetime = scrim_datetime - timedelta(hours=1)

            # 3. 공지 채널 확인
            announcement_channel = await self._get_announcement_channel(interaction.guild_id)
            if not announcement_channel:
                await interaction.followup.send(
                    "❌ 공지 채널이 설정되지 않았습니다.\n"
                    "`/내전공지채널설정` 명령어를 먼저 실행해주세요.",
                    ephemeral=True
                )
                return

            # 4. 데이터베이스에 모집 정보 저장
            recruitment_id = await self.bot.db_manager.create_scrim_recruitment(
                guild_id=str(interaction.guild_id),
                title=제목,
                description=내용,
                scrim_date=scrim_datetime,
                deadline=deadline_datetime,
                created_by=str(interaction.user.id)
            )

            # 5. 공지 메시지 생성 및 전송
            embed, view = await self._create_recruitment_message(
                recruitment_id, 제목, 내용, scrim_datetime, deadline_datetime
            )
            
            message = await announcement_channel.send(
                content="@everyone", 
                embed=embed, 
                view=view
            )

            # 6. 메시지 ID 저장
            await self.bot.db_manager.update_recruitment_message_id(
                recruitment_id, str(message.id), str(announcement_channel.id)
            )

            # 7. 성공 메시지
            await interaction.followup.send(
                f"✅ **내전 모집이 성공적으로 등록되었습니다!**\n\n"
                f"📋 **모집 정보**\n"
                f"• **제목**: {제목}\n"
                f"• **일시**: {scrim_datetime.strftime('%Y년 %m월 %d일 %H:%M')}\n"
                f"• **마감**: {deadline_datetime.strftime('%Y년 %m월 %d일 %H:%M')}\n"
                f"• **공지 채널**: {announcement_channel.mention}\n\n"
                f"🎯 **모집 ID**: `{recruitment_id}`",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ 내전 모집 등록 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

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
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        try:
            await self.bot.db_manager.set_recruitment_channel(
                str(interaction.guild_id), str(채널.id)
            )

            embed = discord.Embed(
                title="✅ 내전 공지 채널 설정 완료",
                description=f"내전 모집 공지가 {채널.mention} 채널에 게시됩니다.",
                color=0x00ff88,
                timestamp=datetime.now()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ 채널 설정 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

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

        try:
            # 1. 모집 정보 확인
            recruitment = await self.bot.db_manager.get_recruitment_by_id(모집id)
            if not recruitment:
                await interaction.followup.send(
                    f"❌ 모집 ID `{모집id}`를 찾을 수 없습니다.", ephemeral=True
                )
                return

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
                            timestamp=datetime.now()
                        )
                        
                        scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
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
            
            await interaction.followup.send(
                f"✅ **내전 모집이 취소되었습니다.**\n\n"
                f"📋 **취소된 모집**: {recruitment['title']}\n"
                f"📅 **예정 일시**: {scrim_date.strftime('%Y년 %m월 %d일 %H:%M')}\n"
                f"👥 **참가 예정이었던 인원**: {joined_count}명\n"
                f"🆔 **모집 ID**: `{모집id}`",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ 모집 취소 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="내전모집통계", description="[관리자] 서버의 내전 모집 통계를 확인합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def recruitment_statistics(self, interaction: discord.Interaction):
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = str(interaction.guild_id)
            
            # 1. 기본 통계 조회
            stats = await self.bot.db_manager.get_recruitment_stats(guild_id)
            if not stats:
                await interaction.followup.send(
                    "❌ 통계 데이터를 불러올 수 없습니다.", ephemeral=True
                )
                return

            # 2. 시간대별 인기도 조회
            time_stats = await self.bot.db_manager.get_popular_participation_times(guild_id)

            # 3. 임베드 생성
            embed = discord.Embed(
                title="📊 내전 모집 통계",
                description=f"**{interaction.guild.name}** 서버의 내전 모집 현황",
                color=0x0099ff,
                timestamp=datetime.now()
            )

            # 기본 통계
            embed.add_field(
                name="📋 모집 현황",
                value=f"📊 **전체 모집**: {stats.get('total_recruitments', 0)}건\n"
                      f"🟢 **진행 중**: {stats.get('active_recruitments', 0)}건\n"
                      f"✅ **완료됨**: {stats.get('closed_recruitments', 0)}건\n"
                      f"❌ **취소됨**: {stats.get('cancelled_recruitments', 0)}건",
                inline=True
            )

            embed.add_field(
                name="👥 참가자 통계",
                value=f"👤 **고유 참가자**: {stats.get('unique_participants', 0)}명\n"
                      f"📈 **평균 참가률**: "
                      f"{round((stats.get('unique_participants', 0) / max(stats.get('total_recruitments', 1), 1)) * 100, 1)}%",
                inline=True
            )

            # 시간대별 통계
            if time_stats:
                time_analysis = []
                for period, data in sorted(time_stats.items()):
                    time_analysis.append(
                        f"**{period}**: 평균 {data['avg_participants']}명 "
                        f"({data['recruitment_count']}회)"
                    )
                
                embed.add_field(
                    name="🕐 시간대별 인기도",
                    value='\n'.join(time_analysis) if time_analysis else "데이터 없음",
                    inline=False
                )

            # 최근 활동
            recent_recruitments = await self.bot.db_manager.get_active_recruitments(guild_id)
            if recent_recruitments:
                embed.add_field(
                    name="🚀 현재 활성 모집",
                    value=f"{len(recent_recruitments)}건의 모집이 진행 중입니다.",
                    inline=True
                )

            embed.set_footer(text="RallyUp Bot | 내전 모집 통계")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                f"❌ 통계 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

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