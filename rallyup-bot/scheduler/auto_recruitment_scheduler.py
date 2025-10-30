import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Optional
import discord

logger = logging.getLogger(__name__)

class AutoRecruitmentScheduler:
    """정기 내전 자동 등록 스케줄러"""
    
    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self.task = None
        self.check_hour = 6  # 매일 오전 6시에 체크
        self.check_minute = 0
    
    async def start(self):
        """스케줄러 시작"""
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._check_loop())
            logger.info("✅ 정기 내전 자동 등록 스케줄러 시작")
    
    async def stop(self):
        """스케줄러 종료"""
        if self.running:
            self.running = False
            if self.task:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            logger.info("🛑 정기 내전 자동 등록 스케줄러 종료")
    
    async def _check_loop(self):
        """메인 체크 루프"""
        await self.bot.wait_until_ready()
        logger.info("🔄 자동 등록 스케줄러 대기 중...")
        
        while not self.bot.is_closed() and self.running:
            try:
                now = datetime.now()
                
                # 매일 설정된 시간(기본: 오전 6시)에 실행
                if now.hour == self.check_hour and now.minute == self.check_minute:
                    logger.info(f"⏰ 자동 스케줄 체크 시작: {now.strftime('%Y-%m-%d %H:%M')}")
                    await self._process_daily_schedules()
                    
                    # 같은 분에 중복 실행 방지 (1분 대기)
                    await asyncio.sleep(60)
                else:
                    # 30초마다 체크
                    await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                logger.info("🛑 자동 등록 스케줄러 루프 취소됨")
                break
            except Exception as e:
                logger.error(f"❌ 자동 등록 체크 루프 오류: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(60)  # 오류 시 1분 대기
    
    async def _process_daily_schedules(self):
        """오늘 생성해야 할 스케줄 처리"""
        today = datetime.now()
        today_weekday = today.weekday()  # 0=월요일, 6=일요일
        today_date_str = today.strftime('%Y-%m-%d')
        
        logger.info(f"📅 오늘: {today_date_str} ({['월','화','수','목','금','토','일'][today_weekday]}요일)")
        
        try:
            # 오늘 요일에 해당하는 모든 활성 스케줄 조회
            schedules = await self.bot.db_manager.get_active_auto_schedules(
                day_of_week=today_weekday
            )
            
            if not schedules:
                logger.info(f"ℹ️ 오늘({['월','화','수','목','금','토','일'][today_weekday]}요일) 실행할 스케줄이 없습니다.")
                return
            
            logger.info(f"🎯 처리할 스케줄 {len(schedules)}개 발견")
            
            success_count = 0
            skip_count = 0
            fail_count = 0
            
            for schedule in schedules:
                try:
                    # 반복 주기 체크
                    if not self._should_run_today(schedule, today):
                        logger.info(f"⏭️ 건너뛰기: {schedule['schedule_name']} (이번 주기 아님)")
                        skip_count += 1
                        continue

                    # 이미 오늘 생성했는지 확인
                    if schedule['last_created_date'] == today_date_str:
                        logger.info(f"⏭️ 건너뛰기: {schedule['schedule_name']} (이미 생성됨)")
                        skip_count += 1
                        continue
                    
                    # 내전 모집 자동 생성
                    result = await self._create_recruitment_from_schedule(schedule, today)
                    
                    if result:
                        # 마지막 생성 날짜 업데이트
                        await self.bot.db_manager.update_schedule_last_created(
                            schedule['id'], 
                            today_date_str
                        )
                        success_count += 1
                        logger.info(f"✅ 생성 성공: {schedule['schedule_name']}")
                    else:
                        fail_count += 1
                        logger.error(f"❌ 생성 실패: {schedule['schedule_name']}")
                    
                    # API 부하 방지 (스케줄 간 1초 대기)
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    fail_count += 1
                    logger.error(f"❌ 스케줄 처리 실패 [{schedule['schedule_name']}]: {e}")
                    import traceback
                    traceback.print_exc()
            
            logger.info(
                f"📊 자동 생성 완료: "
                f"성공 {success_count}개, 건너뛰기 {skip_count}개, 실패 {fail_count}개"
            )
            
        except Exception as e:
            logger.error(f"❌ 일일 스케줄 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()

    def _should_run_today(self, schedule: dict, today: datetime) -> bool:
        """오늘 실행해야 하는 스케줄인지 체크 (반복 주기 고려)"""
        
        recurrence_interval = schedule.get('recurrence_interval', 1)
        post_days_before = schedule.get('post_days_before', 0)
        
        # 매주인 경우 항상 실행
        if recurrence_interval == 1:
            return True
        
        # 마지막 생성 날짜가 없으면 첫 실행
        if not schedule.get('last_created_date'):
            return True
        
        try:
            last_created = datetime.strptime(schedule['last_created_date'], '%Y-%m-%d')
            
            # 마지막 생성일로부터 경과 주수 계산
            days_since_last = (today - last_created).days
            
            # post_days_before를 고려한 실제 내전 간격
            # 예: 격주 + 1일 전 등록이면, 14일 간격이어야 함
            expected_interval_days = recurrence_interval * 7
            
            # 오차 범위 ±1일 (스케줄러 실행 시간 차이 고려)
            return abs(days_since_last - expected_interval_days) <= 1
            
        except Exception as e:
            logger.error(f"⚠️ 반복 주기 체크 오류: {e}")
            return True  # 오류 시 실행
    
    async def _create_recruitment_from_schedule(
        self, 
        schedule: dict, 
        today: datetime
    ) -> bool:
        """스케줄 정보로부터 내전 모집 생성"""
        try:
            guild_id = schedule['guild_id']
            
            # 길드 조회
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                logger.error(f"❌ 길드를 찾을 수 없음: {guild_id}")
                return False
            
            # 채널 조회
            channel = self.bot.get_channel(int(schedule['channel_id']))
            if not channel:
                logger.error(f"❌ 채널을 찾을 수 없음: {schedule['channel_id']}")
                return False
            
            # 채널 권한 확인
            bot_permissions = channel.permissions_for(guild.me)
            if not (bot_permissions.view_channel and bot_permissions.send_messages):
                logger.error(
                    f"❌ 채널 권한 부족: {channel.name} "
                    f"(view: {bot_permissions.view_channel}, send: {bot_permissions.send_messages})"
                )
                return False
            
            # 내전 일시 계산
            scrim_datetime = self._calculate_scrim_datetime(
                today, 
                schedule['scrim_time']
            )
            
            # 마감 시간 계산
            deadline_datetime = self._calculate_deadline_datetime(
                scrim_datetime,
                schedule['deadline_type'],
                schedule['deadline_value']
            )
            
            # 유효성 검증
            if scrim_datetime <= datetime.now():
                logger.error(f"❌ 내전 시간이 현재보다 과거: {scrim_datetime}")
                return False
            
            if deadline_datetime >= scrim_datetime:
                logger.error(f"❌ 마감시간이 내전시간보다 늦음")
                return False
            
            # 데이터베이스에 모집 생성
            recruitment_id = await self.bot.db_manager.create_scrim_recruitment(
                guild_id=guild_id,
                title=schedule['recruitment_title'],
                description=schedule['recruitment_description'],
                scrim_date=scrim_datetime,
                deadline=deadline_datetime,
                created_by="AUTO_SCHEDULER"
            )
            
            if not recruitment_id:
                logger.error("❌ DB 모집 생성 실패")
                return False
            
            # 공지 메시지 생성 및 전송
            embed, view = await self._create_announcement(
                schedule,
                recruitment_id,
                scrim_datetime,
                deadline_datetime
            )
            
            try:
                message = await channel.send(embed=embed, view=view)
                
                # 메시지 정보 업데이트
                await self.bot.db_manager.update_recruitment_message_info(
                    recruitment_id, 
                    str(message.id), 
                    str(channel.id)
                )
                
                # View 등록 (버튼 동작을 위해)
                self.bot.add_view(view)
                
                logger.info(f"✅ 공지 전송 완료: {channel.name}")
                
            except discord.Forbidden as e:
                logger.error(f"❌ 메시지 전송 권한 없음: {e}")
                return False
            except discord.HTTPException as e:
                logger.error(f"❌ 메시지 전송 HTTP 오류: {e}")
                return False
            
            # DM 알림 전송 (설정에 따라)
            if schedule['send_dm_notification']:
                try:
                    await self._send_dm_notifications(
                        guild, 
                        embed, 
                        scrim_datetime
                    )
                except Exception as e:
                    logger.warning(f"⚠️ DM 알림 전송 실패 (무시): {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 모집 생성 중 예외: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _calculate_scrim_datetime(self, base_date: datetime, time_str: str) -> datetime:
        """내전 일시 계산"""
        hour, minute = map(int, time_str.split(':'))
        return base_date.replace(
            hour=hour, 
            minute=minute, 
            second=0, 
            microsecond=0
        )
    
    def _calculate_deadline_datetime(
        self, 
        scrim_datetime: datetime,
        deadline_type: str,
        deadline_value: str
    ) -> datetime:
        """마감 시간 계산"""
        
        if deadline_type == "relative":
            # 상대적 마감시간
            deadline_map = {
                "10min_before": timedelta(minutes=10),
                "30min_before": timedelta(minutes=30),
                "1hour_before": timedelta(hours=1),
                "2hour_before": timedelta(hours=2),
                "3hour_before": timedelta(hours=3),
                "6hour_before": timedelta(hours=6),
                "12hour_before": timedelta(hours=12),
                "1day_before": timedelta(days=1),
            }
            
            # 당일 고정 시간
            if deadline_value in ["same_day_3pm", "same_day_4pm", "same_day_5pm", "same_day_6pm"]:
                hour_map = {
                    "same_day_3pm": 15,
                    "same_day_4pm": 16,
                    "same_day_5pm": 17,
                    "same_day_6pm": 18
                }
                hour = hour_map[deadline_value]
                return datetime.combine(
                    scrim_datetime.date(), 
                    time(hour=hour, minute=0)
                )
            
            delta = deadline_map.get(deadline_value, timedelta(hours=1))
            return scrim_datetime - delta
        
        else:
            # 절대 시간 (추후 확장)
            return scrim_datetime - timedelta(hours=1)
    
    async def _create_announcement(
        self,
        schedule: dict,
        recruitment_id: str,
        scrim_datetime: datetime,
        deadline_datetime: datetime
    ):
        """공지 임베드 및 View 생성"""
        from commands.scrim_recruitment import RecruitmentView
        
        weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        weekday = weekdays[scrim_datetime.weekday()]
        
        embed = discord.Embed(
            title=f"🎮 {schedule['recruitment_title']}",
            description=schedule['recruitment_description'],
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📅 내전 일시",
            value=f"{scrim_datetime.strftime('%Y년 %m월 %d일')} ({weekday}) {scrim_datetime.strftime('%H:%M')}",
            inline=True
        )
        
        embed.add_field(
            name="⏰ 모집 마감",
            value=deadline_datetime.strftime('%Y년 %m월 %d일 %H:%M'),
            inline=True
        )
        
        # 마감까지 남은 시간
        time_left = deadline_datetime - datetime.now()
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
            name="📢 참가 방법",
            value="🔽 **아래 버튼을 눌러 참가 의사를 표시해주세요!**\n"
                  "• 언제든 참가 ↔ 불참 변경 가능합니다\n"
                  "• 참가자 목록 버튼으로 현황 확인 가능합니다",
            inline=False
        )
        
        embed.set_footer(
            text=f"🤖 자동 생성된 모집 | 모집 ID: {recruitment_id}"
        )
        
        view = RecruitmentView(self.bot, recruitment_id)
        
        return embed, view
    
    async def _send_dm_notifications(
        self,
        guild: discord.Guild,
        embed: discord.Embed,
        scrim_datetime: datetime
    ):
        """DM 알림 전송"""
        success = 0
        failed = 0
        
        members = [m for m in guild.members if not m.bot]
        
        # DM용 임베드 (간소화)
        dm_embed = discord.Embed(
            title="🔔 새로운 정기 내전 모집 알림",
            description=f"**{guild.name}** 서버에서 정기 내전 모집이 자동으로 등록되었습니다!",
            color=0x00ff88,
            timestamp=datetime.utcnow()
        )
        
        dm_embed.add_field(
            name="📅 내전 일시",
            value=scrim_datetime.strftime('%Y년 %m월 %d일 (%A) %H:%M'),
            inline=False
        )
        
        dm_embed.add_field(
            name="🎯 참여 방법",
            value=f"**{guild.name}** 서버의 내전 채널로 이동해서\n모집 공지의 버튼을 클릭하여 참가를 표시해주세요!",
            inline=False
        )
        
        dm_embed.set_footer(
            text=f"{guild.name} | RallyUp 자동 알림",
            icon_url=guild.icon.url if guild.icon else None
        )
        
        for member in members:
            try:
                await member.send(embed=dm_embed)
                success += 1
                await asyncio.sleep(0.1)  # Rate limit 방지
            except discord.Forbidden:
                failed += 1
            except Exception:
                failed += 1
        
        logger.info(f"📢 DM 알림: 성공 {success}명, 실패 {failed}명")
    
    async def manual_trigger(self) -> dict:
        """수동 실행 (테스트용)"""
        logger.info("🔧 수동 트리거 실행")
        await self._process_daily_schedules()
        return {"status": "completed"}