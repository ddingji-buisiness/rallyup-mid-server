import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class TierChangeScheduler:
    """티어 변동 자동 감지 스케줄러"""
    
    def __init__(self, bot):
        self.bot = bot
        self.is_running = False
        self.scheduler_task = None
        self.check_interval = 3600 * 12  # 12시간마다 체크 (하루 2회)
    
    async def start(self):
        """스케줄러 시작"""
        if self.is_running:
            return
        
        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        print("📊 티어 변동 감지 스케줄러 시작")
    
    async def stop(self):
        """스케줄러 중지"""
        self.is_running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        print("🛑 티어 변동 감지 스케줄러 중지")
    
    async def _scheduler_loop(self):
        """스케줄러 메인 루프"""
        # 첫 실행 1시간 후 시작
        await asyncio.sleep(3600)
        
        while self.is_running:
            try:
                await self._check_all_tier_changes()
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ 티어 변동 감지 오류: {e}")
                print(traceback.format_exc())
                await asyncio.sleep(self.check_interval)
    
    async def _check_all_tier_changes(self):
        """모든 서버의 티어 변동 체크"""
        try:
            print("🔍 티어 변동 체크 시작...")
            
            total_checked = 0
            total_changes = 0
            
            # 모든 서버에서 티어 변동 로그가 활성화된 곳만 체크
            for guild in self.bot.guilds:
                guild_id = str(guild.id)
                
                # 로그 설정 확인
                settings = await self.bot.db_manager.get_battle_tag_log_settings(guild_id)
                
                if not settings or not settings['log_tier_change']:
                    continue  # 티어 변동 로그 비활성화된 서버 스킵
                
                # 해당 서버의 모든 배틀태그 체크
                changes_count = await self._check_guild_tier_changes(guild_id)
                total_changes += changes_count
                total_checked += 1
            
            print(f"✅ 티어 변동 체크 완료: {total_checked}개 서버, {total_changes}건 변동 감지")
            
        except Exception as e:
            print(f"❌ 티어 변동 체크 실패: {e}")
    
    async def _check_guild_tier_changes(self, guild_id: str) -> int:
        """특정 서버의 티어 변동 체크"""
        try:
            changes_count = 0
            
            # 모든 등록 유저의 배틀태그 조회
            users = await self.bot.db_manager.get_all_registered_users(guild_id)
            
            for user in users:
                user_id = user['user_id']
                username = user['username']
                
                # 유저의 모든 배틀태그 조회
                tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
                
                for tag in tags:
                    battle_tag = tag['battle_tag']
                    old_rank_info = tag.get('rank_info')
                    
                    # API로 최신 랭크 정보 조회
                    new_rank_info = await self.bot.db_manager.refresh_battle_tag_rank(
                        guild_id, user_id, battle_tag
                    )
                    
                    if not new_rank_info:
                        continue  # API 실패 시 스킵
                    
                    # 티어 변동 비교
                    changes = self._compare_ranks(old_rank_info, new_rank_info)
                    
                    if changes:
                        # 로그 전송
                        from utils.battle_tag_logger import BattleTagLogger
                        logger = BattleTagLogger(self.bot)
                        
                        await logger.log_tier_change(
                            guild_id, user_id, username, battle_tag, changes
                        )
                        
                        changes_count += 1
                    
                    # API 부하 방지
                    await asyncio.sleep(0.5)
            
            return changes_count
            
        except Exception as e:
            print(f"❌ 서버 {guild_id} 티어 변동 체크 실패: {e}")
            return 0
    
    def _compare_ranks(self, old_rank: Optional[Dict], new_rank: Dict) -> List[Dict]:
        """랭크 정보 비교 및 변동 추출"""
        try:
            if not old_rank or not old_rank.get('ratings'):
                return []  # 처음 등록 시에는 변동 아님
            
            if not new_rank or not new_rank.get('ratings'):
                return []
            
            changes = []
            
            # 역할별 티어 매핑
            old_tiers = {}
            for rating in old_rank.get('ratings', []):
                role = rating.get('role')
                group = rating.get('group')
                tier = rating.get('tier')
                
                if role and group and tier:
                    old_tiers[role] = f"{group} {tier}"
            
            new_tiers = {}
            for rating in new_rank.get('ratings', []):
                role = rating.get('role')
                group = rating.get('group')
                tier = rating.get('tier')
                
                if role and group and tier:
                    new_tiers[role] = f"{group} {tier}"
            
            # 변동 감지
            tier_order = {
                '브론즈 5': 1, '브론즈 4': 2, '브론즈 3': 3, '브론즈 2': 4, '브론즈 1': 5,
                '실버 5': 6, '실버 4': 7, '실버 3': 8, '실버 2': 9, '실버 1': 10,
                '골드 5': 11, '골드 4': 12, '골드 3': 13, '골드 2': 14, '골드 1': 15,
                '플레티넘 5': 16, '플레티넘 4': 17, '플레티넘 3': 18, '플레티넘 2': 19, '플레티넘 1': 20,
                '다이아 5': 21, '다이아 4': 22, '다이아 3': 23, '다이아 2': 24, '다이아 1': 25,
                '마스터 5': 26, '마스터 4': 27, '마스터 3': 28, '마스터 2': 29, '마스터 1': 30,
                '그마 5': 31, '그마 4': 32, '그마 3': 33, '그마 2': 34, '그마 1': 35,
                '챔피언 5': 36, '챔피언 4': 37, '챔피언 3': 38, '챔피언 2': 39, '챔피언 1': 40,
            }
            
            for role in set(old_tiers.keys()) | set(new_tiers.keys()):
                old_tier = old_tiers.get(role)
                new_tier = new_tiers.get(role)
                
                if old_tier != new_tier and old_tier and new_tier:
                    old_value = tier_order.get(old_tier, 0)
                    new_value = tier_order.get(new_tier, 0)
                    
                    if old_value != new_value:
                        changes.append({
                            'role': role,
                            'old_tier': old_tier,
                            'new_tier': new_tier,
                            'direction': 'up' if new_value > old_value else 'down'
                        })
            
            return changes
            
        except Exception as e:
            print(f"❌ 랭크 비교 오류: {e}")
            return []