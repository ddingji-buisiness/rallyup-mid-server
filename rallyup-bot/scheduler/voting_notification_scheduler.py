import discord
from discord.ext import tasks
import asyncio
from datetime import datetime, timedelta
from typing import Optional

class VotingNotificationScheduler:
    """투표 방식 내전 알림 스케줄러"""
    
    def __init__(self, bot):
        self.bot = bot
        self.check_interval = 60  # 1분마다 체크
    
    def start(self):
        """스케줄러 시작"""
        self.check_deadlines.start()
        self.check_notifications.start()
        print("✅ 투표 알림 스케줄러 시작됨")
    
    def stop(self):
        """스케줄러 중지"""
        self.check_deadlines.cancel()
        self.check_notifications.cancel()
        print("⏹️ 투표 알림 스케줄러 중지됨")
    
    @tasks.loop(seconds=60)
    async def check_deadlines(self):
        """마감 시간 체크 및 자동 종료 처리"""
        try:
            # 마감 시간이 지난 투표 모집 조회
            pending_recruitments = await self.bot.db_manager.get_pending_voting_recruitments()
            
            for recruitment in pending_recruitments:
                await self._process_deadline_recruitment(recruitment)
                
        except Exception as e:
            print(f"❌ 마감 체크 오류: {e}")
    
    @tasks.loop(seconds=60)
    async def check_notifications(self):
        """10분 전 알림 체크"""
        try:
            # 알림이 필요한 확정된 모집 조회
            recruitments = await self.bot.db_manager.get_confirmed_recruitments_for_notification(
                minutes_before=10
            )
            
            for recruitment in recruitments:
                await self._send_start_notification(recruitment)
                
        except Exception as e:
            print(f"❌ 알림 체크 오류: {e}")
    
    @check_deadlines.before_loop
    async def before_check_deadlines(self):
        """스케줄러 시작 전 봇 준비 대기"""
        await self.bot.wait_until_ready()
    
    @check_notifications.before_loop
    async def before_check_notifications(self):
        """스케줄러 시작 전 봇 준비 대기"""
        await self.bot.wait_until_ready()
    
    async def _process_deadline_recruitment(self, recruitment: dict):
        """마감된 모집 처리"""
        try:
            recruitment_id = recruitment['id']
            
            # 자동 종료 처리
            result = await self.bot.db_manager.close_voting_recruitment_on_deadline(recruitment_id)
            
            # 채널에 결과 메시지 발송
            channel_id = recruitment.get('channel_id')
            message_id = recruitment.get('message_id')
            
            if not channel_id:
                return
            
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                return
            
            if result == 'confirmed':
                # 확정됨
                confirmed_time = recruitment.get('confirmed_time')
                
                # 기존 메시지 업데이트
                if message_id:
                    try:
                        message = await channel.fetch_message(int(message_id))
                        
                        embed = discord.Embed(
                            title=f"✅ {recruitment['title']} - 시간 확정!",
                            description=f"{recruitment['description']}\n\n"
                                       f"**🎉 투표가 마감되어 {confirmed_time}에 내전이 확정되었습니다!**",
                            color=0x00ff00
                        )
                        
                        # 확정된 시간대의 투표자 조회
                        voters = await self.bot.db_manager.get_time_slot_voters(
                            recruitment_id, confirmed_time
                        )
                        
                        embed.add_field(
                            name="🕐 확정 시간",
                            value=confirmed_time,
                            inline=True
                        )
                        
                        embed.add_field(
                            name="👥 참가 확정 인원",
                            value=f"{len(voters)}명",
                            inline=True
                        )
                        
                        embed.set_footer(text=f"모집 ID: {recruitment_id} | 확정 완료")
                        
                        await message.edit(embed=embed, view=None)
                        
                        # 참가자 멘션
                        mentions = ' '.join([f"<@{voter_id}>" for voter_id in voters])
                        await channel.send(
                            f"🎉 **투표가 마감되었습니다!**\n\n"
                            f"🕐 확정 시간: **{confirmed_time}**\n"
                            f"👥 참가 인원: {len(voters)}명\n\n"
                            f"{mentions}\n\n"
                            f"내전 10분 전에 다시 알림드리겠습니다!"
                        )
                        
                    except discord.NotFound:
                        print(f"⚠️ 메시지를 찾을 수 없음: {message_id}")
                    except Exception as e:
                        print(f"❌ 메시지 업데이트 오류: {e}")
                
            elif result == 'closed':
                # 인원 미달로 종료
                if message_id:
                    try:
                        message = await channel.fetch_message(int(message_id))
                        
                        embed = discord.Embed(
                            title=f"❌ {recruitment['title']} - 모집 마감",
                            description=f"{recruitment['description']}\n\n"
                                       f"**최소 인원이 모이지 않아 모집이 마감되었습니다.**",
                            color=0xff0000
                        )
                        
                        embed.add_field(
                            name="📊 최종 결과",
                            value=f"최소 {recruitment['min_participants']}명이 필요했으나 달성하지 못했습니다.",
                            inline=False
                        )
                        
                        embed.set_footer(text=f"모집 ID: {recruitment_id} | 마감됨")
                        
                        await message.edit(embed=embed, view=None)
                        
                        await channel.send(
                            f"⚠️ **{recruitment['title']} 모집이 마감되었습니다.**\n\n"
                            f"최소 인원이 모이지 않아 이번 내전은 진행되지 않습니다."
                        )
                        
                    except discord.NotFound:
                        print(f"⚠️ 메시지를 찾을 수 없음: {message_id}")
                    except Exception as e:
                        print(f"❌ 메시지 업데이트 오류: {e}")
            
        except Exception as e:
            print(f"❌ 마감 모집 처리 오류: {e}")
    
    async def _send_start_notification(self, recruitment: dict):
        """내전 시작 10분 전 알림 발송"""
        try:
            recruitment_id = recruitment['id']
            confirmed_time = recruitment['confirmed_time']
            scrim_datetime = recruitment['scrim_datetime']
            
            # 채널 조회
            channel_id = recruitment.get('channel_id')
            if not channel_id:
                return
            
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                return
            
            # 확정된 시간대의 투표자 조회
            voters = await self.bot.db_manager.get_time_slot_voters(
                recruitment_id, confirmed_time
            )
            
            if not voters:
                return
            
            # 멘션 생성
            mentions = ' '.join([f"<@{voter_id}>" for voter_id in voters])
            
            # 알림 발송
            embed = discord.Embed(
                title=f"🔔 {recruitment['title']} - 곧 시작합니다!",
                description=f"**10분 후 내전이 시작됩니다!**",
                color=0xffa500
            )
            
            embed.add_field(
                name="🕐 시작 시간",
                value=scrim_datetime.strftime('%Y년 %m월 %d일 %H:%M'),
                inline=True
            )
            
            embed.add_field(
                name="👥 참가 인원",
                value=f"{len(voters)}명",
                inline=True
            )
            
            embed.add_field(
                name="📢 안내",
                value="참가자 여러분은 준비해주세요!",
                inline=False
            )
            
            await channel.send(
                content=mentions,
                embed=embed
            )
            
            # 알림 발송 표시
            await self.bot.db_manager.mark_notification_sent(recruitment_id)
            
            print(f"✅ 시작 알림 발송 완료: {recruitment_id}")
            
        except Exception as e:
            print(f"❌ 시작 알림 발송 오류: {e}")