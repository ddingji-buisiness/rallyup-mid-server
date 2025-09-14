import asyncio
import discord
from datetime import datetime, timedelta
from typing import Dict, List
import traceback

class RecruitmentScheduler:
    """내전 모집 자동 마감 및 관리 스케줄러"""
    
    def __init__(self, bot):
        self.bot = bot
        self.is_running = False
        self.scheduler_task = None
        self.check_interval = 60  # 1분마다 체크
        
    async def start(self):
        """스케줄러 시작"""
        if self.is_running:
            return
            
        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        print("🕐 내전 모집 스케줄러 시작")
        
    async def stop(self):
        """스케줄러 중지"""
        self.is_running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        print("🛑 내전 모집 스케줄러 중지")
        
    async def _scheduler_loop(self):
        """스케줄러 메인 루프"""
        while self.is_running:
            try:
                await self._check_expired_recruitments()
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ 모집 스케줄러 오류: {e}")
                print(f"❌ 스택트레이스: {traceback.format_exc()}")
                await asyncio.sleep(self.check_interval)
                
    async def _check_expired_recruitments(self):
        """만료된 모집들 체크 및 처리"""
        try:
            # 1. 만료된 모집들 조회
            expired_recruitments = await self.bot.db_manager.get_expired_recruitments()
            
            if not expired_recruitments:
                return
                
            print(f"🕐 {len(expired_recruitments)}개의 만료된 모집 발견")
            
            # 2. 각 모집별로 마감 처리
            for recruitment in expired_recruitments:
                await self._process_expired_recruitment(recruitment)
                
        except Exception as e:
            print(f"❌ 만료된 모집 체크 실패: {e}")
            
    async def _process_expired_recruitment(self, recruitment: Dict):
        """개별 모집 마감 처리"""
        try:
            recruitment_id = recruitment['id']
            guild_id = recruitment['guild_id']
            
            print(f"🎯 모집 마감 처리 시작: {recruitment['title']} (ID: {recruitment_id})")
            
            # 1. 모집 상태를 'closed'로 변경
            success = await self.bot.db_manager.close_recruitment(recruitment_id)
            if not success:
                print(f"❌ 모집 마감 처리 실패: {recruitment_id}")
                return
                
            # 2. 참가자 정보 조회
            participants = await self.bot.db_manager.get_recruitment_participants(recruitment_id)
            joined_users = [p for p in participants if p['status'] == 'joined']
            declined_users = [p for p in participants if p['status'] == 'declined']
            
            # 3. 원본 모집 메시지 업데이트
            await self._update_closed_recruitment_message(recruitment, joined_users, declined_users)
            
            # 4. 관리자에게 마감 결과 알림
            await self._notify_admin_recruitment_closed(recruitment, joined_users, declined_users)

            # 5. 참가자들에게 DM 알림 발송
            await self._notify_participants_recruitment_closed(recruitment, joined_users, declined_users)

            print(f"✅ 모집 마감 처리 완료: {recruitment['title']} - 참가자 {len(joined_users)}명")
            
        except Exception as e:
            print(f"❌ 모집 마감 처리 중 오류: {recruitment_id} - {e}")

    async def _notify_participants_recruitment_closed(self, recruitment: Dict,
                                                    joined_users: List[Dict], declined_users: List[Dict]):
        """참가자들에게 모집 마감 알림 발송"""
        try:
            guild_id = recruitment['guild_id']
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return

            # 1. 참가자들에게 내전 확정 알림
            if joined_users:
                await self._send_confirmation_dms(recruitment, joined_users, guild)
            
            # 2. 불참자들에게 모집 마감 알림 (선택적)
            if declined_users:
                await self._send_closure_dms(recruitment, declined_users, guild)
                
        except Exception as e:
            print(f"❌ 참가자 알림 발송 실패: {e}")
            
    async def _send_confirmation_dms(self, recruitment: Dict, joined_users: List[Dict], guild: discord.Guild):
        """참가 확정자들에게 DM 발송"""
        try:
            scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
            
            # 참가 확정 임베드 생성
            embed = discord.Embed(
                title="🎉 내전 참가 확정!",
                description=f"**{recruitment['title']}** 모집이 마감되어 참가가 확정되었습니다!",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="🎮 내전 정보",
                value=f"**서버**: {guild.name}\n"
                      f"**일시**: {scrim_date.strftime('%Y년 %m월 %d일 (%A) %H:%M')}\n"
                      f"**최종 참가자**: {len(joined_users)}명",
                inline=False
            )
            
            embed.add_field(
                name="📋 준비사항",
                value="• 내전 시작 10분 전까지 음성채널 입장\n"
                      "• 오버워치 게임 실행 및 준비\n"
                      "• 디스코드 음성 테스트 확인",
                inline=False
            )
            
            embed.add_field(
                name="⚠️ 중요 안내",
                value="• 참가 불가 시 미리 관리자에게 연락\n"
                      "• 무단 불참 시 향후 모집에서 제외될 수 있음\n"
                      "• 문의사항은 관리자에게 DM",
                inline=False
            )
            
            # 내전까지 남은 시간 계산
            time_until_scrim = scrim_date - datetime.now()
            if time_until_scrim.total_seconds() > 0:
                if time_until_scrim.days > 0:
                    time_str = f"{time_until_scrim.days}일 {time_until_scrim.seconds//3600}시간"
                else:
                    hours = time_until_scrim.seconds // 3600
                    minutes = (time_until_scrim.seconds % 3600) // 60
                    time_str = f"{hours}시간 {minutes}분"
                
                embed.add_field(
                    name="⏰ 남은 시간",
                    value=f"내전 시작까지: **{time_str}**",
                    inline=True
                )
            
            embed.set_footer(text=f"모집 ID: {recruitment['id']} | {guild.name}")
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            
            # 각 참가자에게 개별 DM 발송
            success_count = 0
            failed_users = []
            
            for user_data in joined_users:
                try:
                    member = guild.get_member(int(user_data['user_id']))
                    if member:
                        # 개인화된 메시지 추가
                        personal_embed = embed.copy()
                        personal_embed.description = f"안녕하세요 **{member.display_name}**님!\n\n" + personal_embed.description
                        
                        await member.send(embed=personal_embed)
                        success_count += 1
                        
                        # 서버 부하 방지
                        await asyncio.sleep(0.5)
                    else:
                        failed_users.append(f"{user_data['username']} (멤버 없음)")
                        
                except discord.Forbidden:
                    failed_users.append(f"{user_data['username']} (DM 차단)")
                except Exception as e:
                    failed_users.append(f"{user_data['username']} (오류: {str(e)[:20]})")

            print(f"✅ 참가 확정 DM 발송 완료: {success_count}/{len(joined_users)}명 성공")

            if failed_users:
                print(f"⚠️ DM 발송 실패: {', '.join(failed_users[:5])}" + 
                      (f" 외 {len(failed_users)-5}명" if len(failed_users) > 5 else ""))

        except Exception as e:
            print(f"❌ 참가 확정 DM 발송 실패: {e}")

    async def _send_closure_dms(self, recruitment: Dict, declined_users: List[Dict], guild: discord.Guild):
        """불참자들에게 모집 마감 알림 발송 (간단한 버전)"""
        try:
            scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
            
            # 불참자용 간단한 임베드
            embed = discord.Embed(
                title="📢 내전 모집 마감 알림",
                description=f"**{recruitment['title']}** 모집이 마감되었습니다.",
                color=0x666666,  # 회색
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📊 최종 현황",
                value=f"**일시**: {scrim_date.strftime('%Y년 %m월 %d일 %H:%M')}\n"
                      f"**서버**: {guild.name}\n"
                      f"**참가 확정**: {len([p for p in declined_users if p != declined_users[0]])}명",  # 참가자 수는 별도 계산
                inline=False
            )
            
            embed.add_field(
                name="💡 다음 기회에!",
                value="다음 내전 모집에서 만나요!\n"
                      "정기 모집 알림을 받고 싶다면 관리자에게 문의하세요.",
                inline=False
            )
            
            embed.set_footer(text=f"{guild.name} | 다음 모집을 기대해주세요!")
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            
            # 불참자들에게 DM 발송 (실패해도 무시)
            success_count = 0
            
            for user_data in declined_users[:10]:  # 최대 10명까지만 (부하 방지)
                try:
                    member = guild.get_member(int(user_data['user_id']))
                    if member:
                        await member.send(embed=embed)
                        success_count += 1
                        await asyncio.sleep(0.3)  # 짧은 대기
                        
                except:
                    continue  # 실패해도 계속 진행
            
            if success_count > 0:
                print(f"✅ 불참자 DM 발송 완료: {success_count}/{len(declined_users)}명 성공")
                
        except Exception as e:
            print(f"❌ 불참자 DM 발송 실패: {e}")

    async def _update_closed_recruitment_message(self, recruitment: Dict, 
                                               joined_users: List[Dict], declined_users: List[Dict]):
        """마감된 모집 메시지 업데이트"""
        try:
            if not recruitment['message_id'] or not recruitment['channel_id']:
                return
                
            # 1. 채널과 메시지 조회
            channel = self.bot.get_channel(int(recruitment['channel_id']))
            if not channel:
                return
                
            try:
                message = await channel.fetch_message(int(recruitment['message_id']))
            except discord.NotFound:
                print(f"⚠️ 모집 메시지를 찾을 수 없음: {recruitment['message_id']}")
                return
                
            # 2. 마감된 임베드 생성
            closed_embed = await self._create_closed_embed(recruitment, joined_users, declined_users)
            
            # 3. 메시지 업데이트 (버튼 제거)
            await message.edit(embed=closed_embed, view=None)
            
        except Exception as e:
            print(f"❌ 마감 메시지 업데이트 실패: {e}")
            
    async def _create_closed_embed(self, recruitment: Dict, 
                                 joined_users: List[Dict], declined_users: List[Dict]):
        """마감된 모집 임베드 생성"""
        scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
        deadline = datetime.fromisoformat(recruitment['deadline'])
        
        embed = discord.Embed(
            title=f"🔒 [마감] {recruitment['title']}",
            description=f"**모집이 마감되었습니다!**\n\n{recruitment['description'] or '이번주 정기 내전'}",
            color=0x666666,  # 회색
            timestamp=datetime.now()
        )
        
        # 한국어 요일
        weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        korean_weekday = weekdays[scrim_date.weekday()]
        
        embed.add_field(
            name="📅 내전 일시",
            value=f"{scrim_date.strftime('%Y년 %m월 %d일')} ({korean_weekday}) {scrim_date.strftime('%H:%M')}",
            inline=True
        )
        
        embed.add_field(
            name="⏰ 마감 시간",
            value=deadline.strftime('%Y년 %m월 %d일 %H:%M'),
            inline=True
        )
        
        embed.add_field(
            name="📊 최종 현황",
            value="🔒 모집 완료",
            inline=True
        )
        
        # 최종 참가자 현황
        embed.add_field(
            name="👥 최종 참가 현황",
            value=f"✅ **참가 확정**: {len(joined_users)}명\n"
                  f"❌ **불참**: {len(declined_users)}명\n"
                  f"📊 **총 응답**: {len(joined_users) + len(declined_users)}명",
            inline=False
        )
        
        # 참가자 명단 (최대 10명까지 표시)
        if joined_users:
            participant_list = []
            for i, user in enumerate(joined_users[:10], 1):
                participant_list.append(f"{i}. {user['username']}")
            
            participant_text = '\n'.join(participant_list)
            if len(joined_users) > 10:
                participant_text += f"\n... 외 {len(joined_users) - 10}명"
                
            embed.add_field(
                name="✅ 참가 확정자",
                value=participant_text,
                inline=False
            )
        else:
            embed.add_field(
                name="✅ 참가 확정자",
                value="참가자가 없습니다.",
                inline=False
            )
            
        embed.add_field(
            name="📝 다음 단계",
            value="관리자가 참가자들에게 별도 연락할 예정입니다.\n"
                  "참가자 분들은 내전 시간에 맞춰 준비해주세요!",
            inline=False
        )
        
        embed.set_footer(text=f"모집 ID: {recruitment['id']} | 자동 마감 처리")
        
        return embed
        
    async def _notify_admin_recruitment_closed(self, recruitment: Dict,
                                             joined_users: List[Dict], declined_users: List[Dict]):
        """관리자에게 모집 마감 알림"""
        try:
            guild_id = recruitment['guild_id']
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return
                
            # 1. 모집 생성자에게 알림
            creator_id = recruitment['created_by']
            creator = guild.get_member(int(creator_id))
            
            # 2. 알림 임베드 생성
            notification_embed = await self._create_admin_notification_embed(
                recruitment, joined_users, declined_users, guild
            )
            
            # 3. 생성자에게 DM 발송
            if creator:
                try:
                    await creator.send(embed=notification_embed)
                    print(f"✅ 생성자 {creator.display_name}에게 마감 알림 발송")
                except discord.Forbidden:
                    print(f"⚠️ {creator.display_name}에게 DM 발송 실패 (DM 차단)")
                    
            # 4. 관리자들에게도 알림 (선택적)
            await self._notify_server_admins(guild_id, notification_embed)
            
        except Exception as e:
            print(f"❌ 관리자 알림 발송 실패: {e}")
            
    async def _create_admin_notification_embed(self, recruitment: Dict,
                                             joined_users: List[Dict], declined_users: List[Dict],
                                             guild: discord.Guild):
        """관리자용 알림 임베드 생성"""
        scrim_date = datetime.fromisoformat(recruitment['scrim_date'])
        
        embed = discord.Embed(
            title="📢 내전 모집 자동 마감 알림",
            description=f"**{recruitment['title']}** 모집이 자동으로 마감되었습니다.",
            color=0x00ff88,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🎮 내전 정보",
            value=f"**서버**: {guild.name}\n"
                  f"**일시**: {scrim_date.strftime('%Y년 %m월 %d일 %H:%M')}\n"
                  f"**모집 ID**: `{recruitment['id']}`",
            inline=False
        )
        
        embed.add_field(
            name="📊 최종 결과",
            value=f"✅ **참가 확정**: {len(joined_users)}명\n"
                  f"❌ **불참**: {len(declined_users)}명\n"
                  f"📈 **응답률**: {len(joined_users) + len(declined_users)}명 응답",
            inline=True
        )
        
        # 참가자 목록
        if joined_users:
            participant_list = []
            for user in joined_users:
                # 실제 멤버 정보 가져오기
                member = guild.get_member(int(user['user_id']))
                display_name = member.display_name if member else user['username']
                participant_list.append(f"• {display_name}")
            
            embed.add_field(
                name="👥 참가 확정자 명단",
                value='\n'.join(participant_list) if len(participant_list) <= 20 else 
                      '\n'.join(participant_list[:20]) + f"\n... 외 {len(participant_list) - 20}명",
                inline=False
            )
        else:
            embed.add_field(
                name="👥 참가 확정자 명단",
                value="아무도 참가하지 않았습니다.",
                inline=False
            )
            
        embed.add_field(
            name="🔧 다음 할 일",
            value="• 참가자들에게 내전 준비 안내\n"
                  "• 음성채널 및 게임 방 준비\n"
                  "• 필요시 `/내전시작` 명령어로 세션 시작",
            inline=False
        )
        
        embed.set_footer(text="RallyUp Bot | 자동 마감 시스템")
        
        return embed
        
    async def _notify_server_admins(self, guild_id: str, embed: discord.Embed):
        """서버 관리자들에게 알림 발송"""
        try:
            # 등록된 관리자들 조회
            admins = await self.bot.db_manager.get_server_admins(guild_id)
            guild = self.bot.get_guild(int(guild_id))
            
            if not guild or not admins:
                return
                
            notification_count = 0
            for admin in admins:
                try:
                    admin_member = guild.get_member(int(admin['user_id']))
                    if admin_member:
                        await admin_member.send(embed=embed)
                        notification_count += 1
                except discord.Forbidden:
                    continue  # DM 차단된 경우 무시
                except Exception:
                    continue  # 기타 오류 무시
                    
            if notification_count > 0:
                print(f"✅ {notification_count}명의 관리자에게 마감 알림 발송")
                
        except Exception as e:
            print(f"❌ 서버 관리자 알림 발송 실패: {e}")

    async def force_check_recruitments(self):
        """수동으로 모집 마감 체크 실행 (디버깅용)"""
        print("🔍 수동 모집 마감 체크 실행")
        await self._check_expired_recruitments()
        
    def get_status(self) -> Dict:
        """스케줄러 상태 조회"""
        return {
            'is_running': self.is_running,
            'check_interval': self.check_interval,
            'task_status': 'running' if self.scheduler_task and not self.scheduler_task.done() else 'stopped'
        }