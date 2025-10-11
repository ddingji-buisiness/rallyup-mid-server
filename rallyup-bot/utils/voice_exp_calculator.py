import math
import logging
from typing import List, Dict, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VoiceExpCalculator:
    """EXP 계산 및 레벨링 로직"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def calculate_decay_multiplier(self, total_hours: float) -> float:
        """
        로그 감소 곡선 계산
        
        목표:
        - 0시간:   120% (신규 인연 보너스)
        - 10시간:  70%
        - 50시간:  40%
        - 100시간: 30% (최소값)
        
        Args:
            total_hours: 함께한 총 시간
            
        Returns:
            배율 (0.30 ~ 1.20)
        """
        # 첫 1시간은 보너스
        if total_hours < 1.0:
            return 1.20
        
        # 로그 감소 공식
        # multiplier = 1.0 - (0.7 * log(hours + 1) / log(101))
        # 이렇게 하면 100시간에 약 30%까지 감소
        
        try:
            # log 계산
            multiplier = 1.20 - (0.90 * math.log(total_hours + 1) / math.log(101))
            
            # 최소값 제한 (30%)
            multiplier = max(0.30, multiplier)
            
            # 최대값 제한 (120%)
            multiplier = min(1.20, multiplier)
            
            return round(multiplier, 3)
        
        except Exception as e:
            logger.error(f"Error calculating decay multiplier: {e}")
            return 1.0
    
    async def calculate_relationship_multipliers(
        self, 
        guild_id: str, 
        user_id: str, 
        partner_ids: List[str]
    ) -> Dict[str, float]:
        """
        각 파트너와의 관계 배율 계산
        
        Args:
            guild_id: 서버 ID
            user_id: 대상 유저 ID
            partner_ids: 함께 있던 파트너들 ID 리스트
            
        Returns:
            {partner_id: multiplier} 딕셔너리
        """
        multipliers = {}
        
        for partner_id in partner_ids:
            # 관계 조회
            relationship = await self.db.get_relationship(guild_id, user_id, partner_id)
            
            if relationship:
                total_seconds = relationship['total_time_seconds']
                total_hours = total_seconds / 3600.0
            else:
                # 처음 만나는 경우
                total_hours = 0.0
            
            # 감소 곡선 적용
            multiplier = self.calculate_decay_multiplier(total_hours)
            multipliers[partner_id] = multiplier
        
        return multipliers
    
    def calculate_average_multiplier(self, multipliers: Dict[str, float]) -> float:
        """
        여러 파트너와의 평균 배율 계산
        
        Args:
            multipliers: {partner_id: multiplier}
            
        Returns:
            평균 배율
        """
        if not multipliers:
            return 1.0
        
        total = sum(multipliers.values())
        average = total / len(multipliers)
        
        return round(average, 3)
    
    async def calculate_exp_for_session(
        self,
        guild_id: str,
        user_id: str,
        duration_seconds: int,
        partner_ids: List[str],
        base_exp_per_minute: float = 10.0
    ) -> Tuple[int, Dict]:
        """
        세션에 대한 EXP 계산
        
        Args:
            guild_id: 서버 ID
            user_id: 유저 ID
            duration_seconds: 세션 시간 (초)
            partner_ids: 함께 있던 파트너들
            base_exp_per_minute: 기본 exp/분
            
        Returns:
            (최종 exp, 상세 정보 딕셔너리)
        """
        # 파트너가 없으면 exp 없음 (혼자서는 안됨)
        if not partner_ids:
            return 0, {
                'reason': 'no_partners',
                'base_exp': 0,
                'multiplier': 0,
                'final_exp': 0
            }
        
        # 기본 exp 계산
        duration_minutes = duration_seconds / 60.0
        base_exp = duration_minutes * base_exp_per_minute
        
        # 각 파트너와의 관계 배율 계산
        multipliers = await self.calculate_relationship_multipliers(
            guild_id, user_id, partner_ids
        )
        
        # 평균 배율
        avg_multiplier = self.calculate_average_multiplier(multipliers)
        
        # 최종 exp
        final_exp = int(base_exp * avg_multiplier)
        
        return final_exp, {
            'base_exp': round(base_exp, 1),
            'multiplier': avg_multiplier,
            'final_exp': final_exp,
            'partners': len(partner_ids),
            'individual_multipliers': multipliers
        }
    
    async def add_exp_and_check_levelup(
        self,
        guild_id: str,
        user_id: str,
        exp_to_add: int
    ) -> Dict:
        """
        EXP 추가 및 레벨업 체크
        
        Returns:
            {
                'leveled_up': bool,
                'old_level': int,
                'new_level': int,
                'levels_gained': int,
                'current_exp': int,
                'exp_added': int,
                'daily_limit_reached': bool
            }
        """
        # 유저 레벨 정보 조회 또는 생성
        user_level = await self.db.get_user_level(guild_id, user_id)
        
        if not user_level:
            # 새로운 유저 생성
            await self.db.create_user_level(guild_id, user_id)
            user_level = await self.db.get_user_level(guild_id, user_id)
        
        # 일일 상한선 체크
        settings = await self.db.get_voice_level_settings(guild_id)
        daily_limit = settings.get('daily_exp_limit', 5000)
        
        # 일일 리셋 체크
        user_level = await self._check_and_reset_daily(user_level)
        
        # 일일 상한 도달 체크
        if user_level['daily_exp_gained'] >= daily_limit:
            return {
                'leveled_up': False,
                'old_level': user_level['current_level'],
                'new_level': user_level['current_level'],
                'levels_gained': 0,
                'current_exp': user_level['current_exp'],
                'exp_added': 0,
                'daily_limit_reached': True
            }
        
        # 일일 상한 고려하여 exp 조정
        remaining_daily = daily_limit - user_level['daily_exp_gained']
        actual_exp_added = min(exp_to_add, remaining_daily)
        
        # EXP 추가
        old_level = user_level['current_level']
        new_current_exp = user_level['current_exp'] + actual_exp_added
        new_total_exp = user_level['total_exp'] + actual_exp_added
        new_daily_exp = user_level['daily_exp_gained'] + actual_exp_added
        
        # 레벨업 체크
        current_level = old_level
        levels_gained = 0
        
        while True:
            required_exp = self.get_required_exp(current_level + 1)
            
            if new_current_exp >= required_exp:
                new_current_exp -= required_exp
                current_level += 1
                levels_gained += 1
            else:
                break
        
        # DB 업데이트
        await self.db.update_user_level(
            guild_id=guild_id,
            user_id=user_id,
            current_level=current_level,
            current_exp=new_current_exp,
            total_exp=new_total_exp,
            daily_exp_gained=new_daily_exp
        )
        
        return {
            'leveled_up': levels_gained > 0,
            'old_level': old_level,
            'new_level': current_level,
            'levels_gained': levels_gained,
            'current_exp': new_current_exp,
            'exp_added': actual_exp_added,
            'daily_limit_reached': new_daily_exp >= daily_limit
        }
    
    async def _check_and_reset_daily(self, user_level: Dict) -> Dict:
        """일일 리셋 체크 및 처리"""
        if not user_level.get('last_daily_reset'):
            # 리셋 정보가 없으면 현재 시간으로 설정
            await self.db.reset_daily_exp(
                user_level['guild_id'],
                user_level['user_id']
            )
            user_level['daily_exp_gained'] = 0
            user_level['last_daily_reset'] = datetime.utcnow().isoformat()
            return user_level
        
        # 마지막 리셋 시간
        last_reset = datetime.fromisoformat(user_level['last_daily_reset'])
        now = datetime.utcnow()
        
        # 하루가 지났는지 체크 (UTC 기준 00:00)
        last_reset_date = last_reset.date()
        current_date = now.date()
        
        if current_date > last_reset_date:
            # 일일 리셋
            await self.db.reset_daily_exp(
                user_level['guild_id'],
                user_level['user_id']
            )
            user_level['daily_exp_gained'] = 0
            user_level['last_daily_reset'] = now.isoformat()
        
        return user_level
    
    @staticmethod
    def get_required_exp(level: int) -> int:
        """
        특정 레벨에 필요한 경험치 계산
        
        공식: Level N = 1,000 × (N + 1)
        
        Args:
            level: 목표 레벨
            
        Returns:
            필요 경험치
        """
        return 1000 * (level + 1)
    
    @staticmethod
    def get_cumulative_exp(level: int) -> int:
        """
        특정 레벨까지의 누적 경험치 계산
        
        Args:
            level: 레벨
            
        Returns:
            누적 경험치
        """
        # 1 + 2 + 3 + ... + N = N × (N + 1) / 2
        # 1000 × (1 + 2 + ... + N) = 1000 × N × (N + 1) / 2
        return 1000 * level * (level + 1) // 2
    
    @staticmethod
    def estimate_play_time_for_level(level: int, avg_multiplier: float = 0.70) -> int:
        """
        특정 레벨 도달에 필요한 예상 플레이 시간 (분)
        
        Args:
            level: 목표 레벨
            avg_multiplier: 평균 배율 (기본 70%)
            
        Returns:
            예상 플레이 시간 (분)
        """
        cumulative_exp = VoiceExpCalculator.get_cumulative_exp(level)
        
        # 기본 exp/분 = 10
        # 실제 exp/분 = 10 × avg_multiplier
        actual_exp_per_minute = 10 * avg_multiplier
        
        # 필요 시간 (분)
        required_minutes = cumulative_exp / actual_exp_per_minute
        
        return int(required_minutes)