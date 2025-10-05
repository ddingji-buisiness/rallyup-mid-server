import aiohttp
import asyncio
from typing import Optional, Dict
from utils.helpers import parse_battle_tag_for_api

class OverwatchAPI:
    """Overwatch API 클라이언트"""
    
    BASE_URL = "https://ow-api.com/v1/stats"
    DEFAULT_PLATFORM = "pc"
    DEFAULT_REGION = "asia"
    TIMEOUT = 10  # 초
    
    @staticmethod
    async def fetch_profile(battle_tag: str, platform: str = None, region: str = None) -> Optional[Dict]:
        try:
            platform = platform or OverwatchAPI.DEFAULT_PLATFORM
            region = region or OverwatchAPI.DEFAULT_REGION
            
            # 배틀태그 형식 변환 (이름#1234 → 이름-1234)
            api_battle_tag = parse_battle_tag_for_api(battle_tag)
            
            url = f"{OverwatchAPI.BASE_URL}/{platform}/{region}/{api_battle_tag}/profile"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=OverwatchAPI.TIMEOUT)) as response:
                    
                    # 응답 확인
                    if response.status != 200:
                        print(f"⚠️ API 응답 실패: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    print(f"\n{'='*50}")
                    print(f"[DEBUG] API 응답 for {battle_tag}:")
                    import json
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    print(f"{'='*50}\n")

                    # 에러 응답 체크
                    if 'error' in data:
                        error_msg = data.get('error', 'Unknown error')
                        if 'Player not found' in error_msg or 'PROFILE_PRIVATE' in error_msg:
                            print(f"ℹ️ {battle_tag}: {error_msg} (비공개 또는 없는 계정)")
                        else:
                            print(f"⚠️ API 에러: {error_msg}")
                        return None
                    
                    # 정상 응답 처리
                    return data
                    
        except asyncio.TimeoutError:
            print(f"⏱️ API 타임아웃: {battle_tag}")
            return None
        except aiohttp.ClientError as e:
            print(f"🌐 네트워크 오류: {e}")
            return None
        except Exception as e:
            print(f"❌ API 호출 중 오류: {e}")
            return None
    
    @staticmethod
    async def fetch_complete_stats(battle_tag: str, platform: str = None, region: str = None) -> Optional[Dict]:
        """
        오버워치 상세 통계 조회 (영웅별, 모드별)
        
        Args:
            battle_tag: 배틀태그
            platform: 플랫폼 (기본: pc)
            region: 지역 (기본: asia)
            
        Returns:
            상세 통계 dict 또는 None
        """
        try:
            platform = platform or OverwatchAPI.DEFAULT_PLATFORM
            region = region or OverwatchAPI.DEFAULT_REGION
            
            api_battle_tag = parse_battle_tag_for_api(battle_tag)
            
            url = f"{OverwatchAPI.BASE_URL}/{platform}/{region}/{api_battle_tag}/complete"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=OverwatchAPI.TIMEOUT)) as response:
                    
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    
                    if 'error' in data:
                        return None
                    
                    return data
                    
        except Exception as e:
            print(f"❌ 상세 통계 조회 실패: {e}")
            return None
    
    @staticmethod
    def parse_rank_info(profile_data: Dict) -> Optional[Dict]:
        """프로필 데이터에서 랭크 정보 추출"""
        if not profile_data:
            return None
        
        try:
            result = {
                'username': profile_data.get('username'),
                'ratings': []
            }
            
            # 경쟁전 랭크 정보
            ratings = profile_data.get('ratings', [])

            print(f"[DEBUG] ratings 배열: {ratings}")
            
            for rating in ratings:
                role = rating.get('role')  # tank, offense/damage, support
                tier = rating.get('tier')  # 숫자 (5, 4, 2 등)
                group = rating.get('group')  # Diamond, Master 등
                rank_icon = rating.get('rankIcon')
                
                result['ratings'].append({
                    'role': role,
                    'tier': tier,
                    'group': group,  # 🆕 group 추가
                    'rank_icon': rank_icon
                })
            
            print(f"[DEBUG] 파싱 결과: {result}")
            return result if result['ratings'] else result
            
        except Exception as e:
            print(f"❌ 랭크 정보 파싱 실패: {e}")
            return None

    @staticmethod
    def format_rank_display(rank_info: Dict) -> str:
        """랭크 정보를 Discord Embed용 텍스트로 포맷팅"""
        if not rank_info:
            return "랭크 정보 없음"
        
        ratings = rank_info.get('ratings', [])
        if not ratings:
            return "경쟁전 배치 안함"
        
        # 역할 한글 매핑
        role_name_kr = {
            'tank': '탱커',
            'offense': '딜러',
            'damage': '딜러',
            'support': '힐러'
        }
        
        # 티어 한글 매핑
        tier_name_kr = {
            'Bronze': '브론즈',
            'Silver': '실버',
            'Gold': '골드',
            'Platinum': '플래티넘',
            'Diamond': '다이아',
            'Master': '마스터',
            'Grandmaster': '그랜드마스터',
            'Champion': '챔피언',
            'Top 500': '탑500'
        }
        
        rank_parts = []
        for rating in ratings:
            role = rating.get('role')
            group = rating.get('group', '')
            tier = rating.get('tier', '')
            
            role_kr = role_name_kr.get(role, role)
            
            # 티어 한글화
            group_kr = tier_name_kr.get(group, group)
            
            if group and tier:
                # "탱커: 다이아 5" 형식
                rank_parts.append(f"{role_kr}: {group_kr} {tier}")
            elif group:
                # tier 없이 group만 있는 경우
                rank_parts.append(f"{role_kr}: {group_kr}")
            else:
                # 배치 안함
                rank_parts.append(f"{role_kr}: 배치 안함")
        
        result = "**경쟁전 랭크**:\n" + " • ".join(rank_parts)
        
        return result

    @staticmethod
    def get_highest_rank(rank_info: Dict) -> Optional[str]:
        """가장 높은 랭크 반환 (닉네임 표시용)"""
        if not rank_info:
            return None
        
        ratings = rank_info.get('ratings', [])
        if not ratings:
            return None
        
        # 티어 우선순위
        tier_priority = {
            'Bronze': 1,
            'Silver': 2,
            'Gold': 3,
            'Platinum': 4,
            'Diamond': 5,
            'Master': 6,
            'Grandmaster': 7,
            'Top 500': 8,
            'Champion': 8
        }
        
        highest_group = None  # 🆕 tier → group으로 변경
        highest_priority = 0
        
        for rating in ratings:
            group = rating.get('group')  # 🆕 tier → group
            if group:
                priority = tier_priority.get(group, 0)
                if priority > highest_priority:
                    highest_priority = priority
                    highest_group = group
        
        return highest_group