import discord
from typing import List, Tuple, Dict
import random

def validate_positions(positions: str) -> bool:
    """포지션 문자열 검증"""
    valid_chars = {'탱', '딜', '힐'}
    
    # 길이 체크 (5자리)
    if len(positions) != 5:
        return False
    
    # 유효한 문자 체크
    for char in positions:
        if char not in valid_chars:
            return False
    
    # 최소 구성 체크 (탱 1개, 힐 1개 이상)
    tank_count = positions.count('탱')
    support_count = positions.count('힐')
    
    if tank_count < 1 or support_count < 1:
        return False
    
    return True

def split_voice_channel_users(members: List[discord.Member]) -> Tuple[List[discord.Member], List[discord.Member]]:
    """음성채널 유저들을 두 팀으로 분할"""
    if len(members) != 10:
        raise ValueError("음성채널에 정확히 10명이 있어야 합니다")
    
    # 봇 제외
    human_members = [m for m in members if not m.bot]
    
    if len(human_members) != 10:
        raise ValueError("봇을 제외하고 정확히 10명이 있어야 합니다")
    
    # 첫 5명이 1팀, 나머지 5명이 2팀
    team1 = human_members[:5]
    team2 = human_members[5:]
    
    return team1, team2

def assign_teams_random(members: List[discord.Member]) -> Tuple[List[discord.Member], List[discord.Member]]:
    """랜덤 팀 배정"""
    if len(members) != 10:
        raise ValueError("정확히 10명이 필요합니다")
    
    shuffled = members.copy()
    random.shuffle(shuffled)
    
    return shuffled[:5], shuffled[5:]

def calculate_win_rate(wins: int, total_games: int) -> float:
    """승률 계산"""
    if total_games == 0:
        return 0.0
    return round((wins / total_games) * 100, 1)

def format_user_stats(user) -> Dict[str, str]:
    """사용자 통계를 보기 좋게 포맷팅"""
    total_wr = calculate_win_rate(user.total_wins, user.total_games)
    tank_wr = calculate_win_rate(user.tank_wins, user.tank_games)
    dps_wr = calculate_win_rate(user.dps_wins, user.dps_games)
    support_wr = calculate_win_rate(user.support_wins, user.support_games)
    
    return {
        'total': f"{user.total_wins}승 {user.total_games - user.total_wins}패 ({total_wr}%)",
        'tank': f"{user.tank_wins}승 {user.tank_games - user.tank_wins}패 ({tank_wr}%)",
        'dps': f"{user.dps_wins}승 {user.dps_games - user.dps_wins}패 ({dps_wr}%)",
        'support': f"{user.support_wins}승 {user.support_games - user.support_wins}패 ({support_wr}%)",
        'score': str(user.score)
    }