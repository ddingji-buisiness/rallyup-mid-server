import itertools
import random
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

class BalancingMode(Enum):
    QUICK = "quick"
    PRECISE = "precise" 
    EXPERIMENTAL = "experimental"

@dataclass
class PlayerSkillData:
    """플레이어 스킬 데이터"""
    user_id: str
    username: str
    main_position: str
    
    # 기본 통계
    total_games: int
    total_wins: int
    
    # 포지션별 통계
    tank_games: int
    tank_wins: int
    dps_games: int
    dps_wins: int
    support_games: int
    support_wins: int
    
    # 계산된 스킬 점수 (0.0 ~ 1.0)
    tank_skill: float = 0.0
    dps_skill: float = 0.0
    support_skill: float = 0.0
    overall_skill: float = 0.0
    
    # 추가 정보
    current_tier: Optional[str] = None
    recent_winrate: float = 0.0

@dataclass
class TeamComposition:
    """팀 구성 정보"""
    tank: PlayerSkillData
    dps1: PlayerSkillData
    dps2: PlayerSkillData
    support1: PlayerSkillData
    support2: PlayerSkillData
    
    # 계산된 팀 점수
    total_skill: float = 0.0
    position_balance: float = 0.0
    synergy_bonus: float = 0.0

@dataclass
class BalanceResult:
    """밸런싱 결과"""
    team_a: TeamComposition
    team_b: TeamComposition
    
    balance_score: float  # 0.0(불균형) ~ 1.0(완벽균형)
    skill_difference: float
    predicted_winrate_a: float  # A팀 기준 예상 승률
    
    reasoning: Dict[str, str]  # 밸런싱 근거 설명

class TeamBalancer:
    """팀 밸런싱 메인 클래스"""
    
    def __init__(self, mode: BalancingMode = BalancingMode.PRECISE):
        self.mode = mode
        self.min_games_for_reliability = 5
        self.position_weights = {
            'tank': 0.3,    # 탱커의 중요도
            'dps': 0.4,     # 딜러의 중요도 (2명이므로 각각 0.2)
            'support': 0.3  # 힐러의 중요도
        }
    
    def calculate_position_skill_score(self, games: int, wins: int, total_games: int, total_wins: int) -> float:
        """
        포지션별 스킬 점수 계산
        
        Args:
            games: 해당 포지션 게임 수
            wins: 해당 포지션 승리 수
            total_games: 전체 게임 수
            total_wins: 전체 승리 수
            
        Returns:
            0.0 ~ 1.0 사이의 스킬 점수
        """
        if games == 0:
            # 포지션 경험이 없으면 전체 승률의 80%로 추정
            if total_games == 0:
                return 0.5
            return (total_wins / total_games) * 0.8
        
        # 기본 승률 계산
        base_winrate = wins / games
        
        # 경험치 보정 (게임 수가 적으면 신뢰도 감소)
        if games < 3:
            experience_factor = 0.6
        elif games < 5:
            experience_factor = 0.75
        elif games < 10:
            experience_factor = 0.9
        else:
            experience_factor = 1.0
        
        # 데이터가 부족한 경우 전체 승률로 보정
        if games < 5 and total_games > 0:
            overall_winrate = total_wins / total_games
            # 포지션 데이터 30% + 전체 데이터 70%
            adjusted_winrate = (base_winrate * 0.3) + (overall_winrate * 0.7)
        else:
            adjusted_winrate = base_winrate
        
        # 최종 점수 = 조정된 승률 * 경험치 보정
        final_score = adjusted_winrate * experience_factor
        
        # 0.0 ~ 1.0 범위로 제한
        return max(0.0, min(1.0, final_score))
    
    def calculate_player_skills(self, player_data: Dict) -> PlayerSkillData:
        """
        플레이어의 모든 포지션 스킬 점수 계산
        """
        player = PlayerSkillData(
            user_id=player_data['user_id'],
            username=player_data['username'],
            main_position=player_data.get('main_position', '미설정'),
            total_games=player_data.get('total_games', 0),
            total_wins=player_data.get('total_wins', 0),
            tank_games=player_data.get('tank_games', 0),
            tank_wins=player_data.get('tank_wins', 0),
            dps_games=player_data.get('dps_games', 0),
            dps_wins=player_data.get('dps_wins', 0),
            support_games=player_data.get('support_games', 0),
            support_wins=player_data.get('support_wins', 0),
            current_tier=player_data.get('current_tier'),
            recent_winrate=player_data.get('recent_winrate', 0.0)
        )
        
        # 각 포지션별 스킬 점수 계산
        player.tank_skill = self.calculate_position_skill_score(
            player.tank_games, player.tank_wins, player.total_games, player.total_wins
        )
        
        player.dps_skill = self.calculate_position_skill_score(
            player.dps_games, player.dps_wins, player.total_games, player.total_wins
        )
        
        player.support_skill = self.calculate_position_skill_score(
            player.support_games, player.support_wins, player.total_games, player.total_wins
        )
        
        # 전체 스킬 점수 (주포지션 가중 평균)
        position_scores = {
            '탱커': player.tank_skill,
            '딜러': player.dps_skill,
            '힐러': player.support_skill
        }
        
        # 주포지션 60% + 나머지 포지션 40%
        main_pos_korean = player.main_position
        if main_pos_korean in position_scores:
            main_score = position_scores[main_pos_korean]
            other_scores = [score for pos, score in position_scores.items() if pos != main_pos_korean]
            other_avg = sum(other_scores) / len(other_scores) if other_scores else 0.5
            player.overall_skill = (main_score * 0.6) + (other_avg * 0.4)
        else:
            # 주포지션이 명확하지 않으면 평균
            player.overall_skill = sum(position_scores.values()) / len(position_scores)
        
        return player
    
    def get_player_best_position(self, player: PlayerSkillData) -> str:
        """플레이어의 최적 포지션 결정"""
        position_scores = {
            '탱커': player.tank_skill,
            '딜러': player.dps_skill,
            '힐러': player.support_skill
        }
        
        return max(position_scores, key=position_scores.get)
    
    def calculate_team_score(self, composition: TeamComposition) -> float:
        """팀 구성의 총 점수 계산"""
        # 각 포지션별 최적 스킬 점수 사용
        tank_score = composition.tank.tank_skill
        dps_score = (composition.dps1.dps_skill + composition.dps2.dps_skill) / 2
        support_score = (composition.support1.support_skill + composition.support2.support_skill) / 2
        
        # 가중 평균으로 팀 점수 계산
        team_score = (
            tank_score * self.position_weights['tank'] +
            dps_score * self.position_weights['dps'] +
            support_score * self.position_weights['support']
        )
        
        composition.total_skill = team_score
        return team_score
    
    def evaluate_position_balance(self, composition: TeamComposition) -> float:
        """포지션 밸런스 평가 (선수들이 자신의 주포지션에 배치되었는지)"""
        balance_score = 0.0
        
        # 각 포지션에 배치된 선수가 해당 포지션을 얼마나 잘하는지
        positions = [
            (composition.tank, '탱커', composition.tank.tank_skill),
            (composition.dps1, '딜러', composition.dps1.dps_skill),
            (composition.dps2, '딜러', composition.dps2.dps_skill),
            (composition.support1, '힐러', composition.support1.support_skill),
            (composition.support2, '힐러', composition.support2.support_skill)
        ]
        
        for player, assigned_pos, skill_at_pos in positions:
            # 주포지션 일치도 보너스
            if player.main_position == assigned_pos:
                balance_score += 0.2
            
            # 해당 포지션 숙련도 점수
            balance_score += skill_at_pos * 0.16  # 5명이므로 1/5 = 0.2, 그 중 80%
        
        composition.position_balance = balance_score
        return balance_score
    
    def generate_all_combinations(self, players: List[PlayerSkillData]) -> List[Tuple[TeamComposition, TeamComposition]]:
        """모든 가능한 팀 조합 생성"""
        if len(players) != 10:
            raise ValueError("정확히 10명의 플레이어가 필요합니다")
        
        valid_combinations = []
        
        # A팀으로 5명을 선택하는 모든 조합
        for team_a_indices in itertools.combinations(range(10), 5):
            team_a_players = [players[i] for i in team_a_indices]
            team_b_players = [players[i] for i in range(10) if i not in team_a_indices]
            
            # 각 팀에서 가능한 포지션 배치 시도
            team_a_compositions = self.generate_position_assignments(team_a_players)
            team_b_compositions = self.generate_position_assignments(team_b_players)
            
            # 유효한 배치가 있는 경우만 추가
            if team_a_compositions and team_b_compositions:
                # 각 팀의 최적 배치 선택
                best_a = max(team_a_compositions, key=lambda comp: self.calculate_team_score(comp) + self.evaluate_position_balance(comp))
                best_b = max(team_b_compositions, key=lambda comp: self.calculate_team_score(comp) + self.evaluate_position_balance(comp))
                
                valid_combinations.append((best_a, best_b))
        
        return valid_combinations
    
    def generate_position_assignments(self, team_players: List[PlayerSkillData]) -> List[TeamComposition]:
        """5명의 선수를 탱1딜2힐2로 배치하는 모든 경우의 수 생성"""
        if len(team_players) != 5:
            return []
        
        compositions = []
        
        # 탱커 1명 선택
        for tank_idx in range(5):
            tank = team_players[tank_idx]
            remaining = [p for i, p in enumerate(team_players) if i != tank_idx]
            
            # 나머지 4명 중 딜러 2명 선택
            for dps_indices in itertools.combinations(range(4), 2):
                dps1 = remaining[dps_indices[0]]
                dps2 = remaining[dps_indices[1]]
                
                # 나머지 2명은 자동으로 힐러
                supports = [remaining[i] for i in range(4) if i not in dps_indices]
                support1, support2 = supports[0], supports[1]
                
                composition = TeamComposition(
                    tank=tank,
                    dps1=dps1,
                    dps2=dps2,
                    support1=support1,
                    support2=support2
                )
                
                compositions.append(composition)
        
        return compositions
    
    def calculate_balance_score(self, team_a: TeamComposition, team_b: TeamComposition) -> float:
        """두 팀 간의 밸런스 점수 계산 (1.0에 가까울수록 균형)"""
        team_a_total = self.calculate_team_score(team_a)
        team_b_total = self.calculate_team_score(team_b)
        
        # 핵심: 두 팀의 스킬 점수 차이를 최소화하는 것이 목표
        score_difference = abs(team_a_total - team_b_total)
        
        # 이론적 최대 차이 (0.0 ~ 1.0 범위에서)
        max_possible_difference = 1.0
        
        # 차이가 적을수록 높은 점수 (1.0 = 완벽 균형, 0.0 = 최대 불균형)
        balance_score = 1.0 - (score_difference / max_possible_difference)
        return max(0.0, min(1.0, balance_score))
    
    def find_optimal_balance(self, players: List[Dict]) -> List[BalanceResult]:
        """최적의 팀 밸런스 찾기 - 50:50 승률 목표"""
        # 플레이어 스킬 데이터 계산
        player_skills = [self.calculate_player_skills(player) for player in players]
        
        if self.mode == BalancingMode.QUICK:
            # 빠른 모드: 제한적 조합만 시도
            combinations = self.generate_quick_combinations(player_skills)
        elif self.mode == BalancingMode.EXPERIMENTAL:
            # 실험적 모드: 랜덤 조합 포함
            combinations = self.generate_experimental_combinations(player_skills)
        else:
            # 정밀 모드: 모든 조합 시도 (시간이 오래 걸릴 수 있음)
            combinations = self.generate_all_combinations(player_skills)
        
        # 각 조합 평가
        results = []
        for team_a, team_b in combinations:
            # 팀 점수 계산
            team_a_score = self.calculate_team_score(team_a)
            team_b_score = self.calculate_team_score(team_b)
            
            # 포지션 밸런스 점수 추가
            team_a_pos_balance = self.evaluate_position_balance(team_a)
            team_b_pos_balance = self.evaluate_position_balance(team_b)
            
            # 최종 팀 점수 (스킬 + 포지션 밸런스)
            final_team_a_score = team_a_score * 0.8 + team_a_pos_balance * 0.2
            final_team_b_score = team_b_score * 0.8 + team_b_pos_balance * 0.2
            
            # 스킬 차이 계산
            skill_difference = abs(final_team_a_score - final_team_b_score)
            
            # 예상 승률 계산 (50:50에 가까워야 함)
            score_diff = final_team_a_score - final_team_b_score
            # 더 완만한 로지스틱 함수 사용 (계수를 10에서 5로 줄임)
            predicted_winrate_a = 1 / (1 + pow(10, -score_diff * 5))
            
            # 균형 점수: 50:50에서 얼마나 벗어났는지 측정
            winrate_deviation = abs(predicted_winrate_a - 0.5)  # 0.5(50%)에서 얼마나 벗어났는지
            balance_score = 1.0 - (winrate_deviation * 2)  # 편차가 클수록 점수 낮음
            balance_score = max(0.0, min(1.0, balance_score))
            
            # 밸런싱 근거 생성
            reasoning = self.generate_reasoning(team_a, team_b, balance_score, predicted_winrate_a)
            
            result = BalanceResult(
                team_a=team_a,
                team_b=team_b,
                balance_score=balance_score,
                skill_difference=skill_difference,
                predicted_winrate_a=predicted_winrate_a,
                reasoning=reasoning
            )
            
            results.append(result)
        
        # 황금 밸런스 기준으로 정렬: 50:50에 가장 가까운 것부터
        results.sort(key=lambda x: (
            -x.balance_score,  # 밸런스 점수 높은 순
            x.skill_difference,  # 스킬 차이 적은 순
            abs(x.predicted_winrate_a - 0.5)  # 50:50에서 편차 적은 순
        ))
        
        # 상위 5개 결과만 반환
        return results[:5]
    
    def generate_quick_combinations(self, players: List[PlayerSkillData]) -> List[Tuple[TeamComposition, TeamComposition]]:
        """빠른 모드: 스킬 기반 균형잡힌 조합"""
        combinations = []
        
        # 전체 스킬 기반으로 정렬
        sorted_by_skill = sorted(players, key=lambda p: p.overall_skill, reverse=True)
        
        # 방법 1: 스킬 기반 교대 배치 (가장 균형잡힌 방법)
        team_a_alt = [sorted_by_skill[i] for i in range(0, 10, 2)]  # 1, 3, 5, 7, 9등
        team_b_alt = [sorted_by_skill[i] for i in range(1, 10, 2)]  # 2, 4, 6, 8, 10등
        
        team_a_comps = self.generate_position_assignments(team_a_alt)
        team_b_comps = self.generate_position_assignments(team_b_alt)
        
        if team_a_comps and team_b_comps:
            best_a = max(team_a_comps, key=lambda comp: self.calculate_team_score(comp))
            best_b = max(team_b_comps, key=lambda comp: self.calculate_team_score(comp))
            combinations.append((best_a, best_b))
        
        # 방법 2: 상위 선수들을 양팀에 분산
        # 상위 2명을 각 팀에 1명씩, 3-4등을 각 팀에 1명씩, 나머지 분산
        top_players = sorted_by_skill[:4]
        remaining_players = sorted_by_skill[4:]
        
        for i in range(3):  # 3가지 다른 분배 방식 시도
            team_a_balanced = [top_players[0], top_players[3]]  # 1등, 4등
            team_b_balanced = [top_players[1], top_players[2]]  # 2등, 3등
            
            # 나머지 선수들 분배 (순환 방식)
            for j, player in enumerate(remaining_players):
                if (j + i) % 2 == 0:
                    team_a_balanced.append(player)
                else:
                    team_b_balanced.append(player)
            
            # 각 팀이 정확히 5명인지 확인
            if len(team_a_balanced) == 5 and len(team_b_balanced) == 5:
                team_a_comps = self.generate_position_assignments(team_a_balanced)
                team_b_comps = self.generate_position_assignments(team_b_balanced)
                
                if team_a_comps and team_b_comps:
                    best_a = max(team_a_comps, key=lambda comp: self.calculate_team_score(comp))
                    best_b = max(team_b_comps, key=lambda comp: self.calculate_team_score(comp))
                    combinations.append((best_a, best_b))
        
        return combinations[:5]  # 최대 5개 조합만
    
    def generate_experimental_combinations(self, players: List[PlayerSkillData]) -> List[Tuple[TeamComposition, TeamComposition]]:
        """실험적 모드: 다양한 균형 조합 시도"""
        combinations = []
        
        # 먼저 빠른 모드의 균형잡힌 조합들 포함
        combinations.extend(self.generate_quick_combinations(players))
        
        # 포지션별 실력 기반 분배
        tanks = sorted([p for p in players], key=lambda p: p.tank_skill, reverse=True)
        dps_players = sorted([p for p in players], key=lambda p: p.dps_skill, reverse=True)
        supports = sorted([p for p in players], key=lambda p: p.support_skill, reverse=True)
        
        # 각 포지션 최고 선수들을 양팀에 분산하는 조합 시도
        for attempt in range(5):
            team_a_experimental = []
            team_b_experimental = []
            used_players = set()
            
            # 탱커 최고 선수들을 각 팀에 1명씩
            tank_candidates = [p for p in tanks if p.user_id not in used_players][:2]
            if len(tank_candidates) >= 2:
                team_a_experimental.append(tank_candidates[0])
                team_b_experimental.append(tank_candidates[1])
                used_players.update([p.user_id for p in tank_candidates])
            
            # 딜러 상위 선수들을 분산
            dps_candidates = [p for p in dps_players if p.user_id not in used_players][:4]
            if len(dps_candidates) >= 4:
                team_a_experimental.extend(dps_candidates[:2])
                team_b_experimental.extend(dps_candidates[2:])
                used_players.update([p.user_id for p in dps_candidates])
            
            # 힐러 상위 선수들을 분산
            support_candidates = [p for p in supports if p.user_id not in used_players][:4]
            if len(support_candidates) >= 4:
                team_a_experimental.extend(support_candidates[:2])
                team_b_experimental.extend(support_candidates[2:])
                used_players.update([p.user_id for p in support_candidates])
            
            # 팀이 정확히 5명인지 확인
            if len(team_a_experimental) == 5 and len(team_b_experimental) == 5:
                team_a_comps = self.generate_position_assignments(team_a_experimental)
                team_b_comps = self.generate_position_assignments(team_b_experimental)
                
                if team_a_comps and team_b_comps:
                    best_a = max(team_a_comps, key=lambda comp: self.calculate_team_score(comp))
                    best_b = max(team_b_comps, key=lambda comp: self.calculate_team_score(comp))
                    combinations.append((best_a, best_b))
        
        # 완전 랜덤 조합들 추가 (기존 코드 유지하되 수 줄임)
        for _ in range(10):  # 20에서 10으로 줄임
            shuffled = players.copy()
            random.shuffle(shuffled)
            team_a_random = shuffled[:5]
            team_b_random = shuffled[5:]
            
            team_a_comps = self.generate_position_assignments(team_a_random)
            team_b_comps = self.generate_position_assignments(team_b_random)
            
            if team_a_comps and team_b_comps:
                best_a = max(team_a_comps, key=lambda comp: self.calculate_team_score(comp))
                best_b = max(team_b_comps, key=lambda comp: self.calculate_team_score(comp))
                combinations.append((best_a, best_b))
        
        return combinations
    
    def generate_reasoning(self, team_a: TeamComposition, team_b: TeamComposition, balance_score: float, predicted_winrate_a: float) -> Dict[str, str]:
        """밸런싱 근거 설명 생성"""
        reasoning = {}
        
        # 전체 밸런스 평가 - 50:50 기준으로 평가
        winrate_diff = abs(predicted_winrate_a - 0.5)
        
        if winrate_diff <= 0.05:  # 45-55% 범위
            reasoning['balance'] = "황금 밸런스! 매우 균등한 팀 구성"
        elif winrate_diff <= 0.1:  # 40-60% 범위
            reasoning['balance'] = "양호한 밸런스"
        elif winrate_diff <= 0.15:  # 35-65% 범위
            reasoning['balance'] = "보통 수준의 밸런스"
        elif winrate_diff <= 0.2:  # 30-70% 범위
            reasoning['balance'] = "다소 불균형한 구성"
        else:  # 30% 미만 또는 70% 초과
            reasoning['balance'] = "심각한 불균형 - 재조정 권장"
        
        # 포지션 분석
        a_tank_skill = team_a.tank.tank_skill
        b_tank_skill = team_b.tank.tank_skill
        tank_diff = abs(a_tank_skill - b_tank_skill)
        
        if tank_diff < 0.05:
            reasoning['tank'] = "탱커 실력 균등"
        elif a_tank_skill > b_tank_skill:
            reasoning['tank'] = f"A팀 탱커 우세 (+{tank_diff:.1%})"
        else:
            reasoning['tank'] = f"B팀 탱커 우세 (+{tank_diff:.1%})"
        
        # 딜러 분석
        a_dps_avg = (team_a.dps1.dps_skill + team_a.dps2.dps_skill) / 2
        b_dps_avg = (team_b.dps1.dps_skill + team_b.dps2.dps_skill) / 2
        dps_diff = abs(a_dps_avg - b_dps_avg)
        
        if dps_diff < 0.05:
            reasoning['dps'] = "딜러 화력 균등"
        elif a_dps_avg > b_dps_avg:
            reasoning['dps'] = f"A팀 화력 우세 (+{dps_diff:.1%})"
        else:
            reasoning['dps'] = f"B팀 화력 우세 (+{dps_diff:.1%})"
        
        # 힐러 분석
        a_sup_avg = (team_a.support1.support_skill + team_a.support2.support_skill) / 2
        b_sup_avg = (team_b.support1.support_skill + team_b.support2.support_skill) / 2
        sup_diff = abs(a_sup_avg - b_sup_avg)
        
        if sup_diff < 0.05:
            reasoning['support'] = "힐러 실력 균등"
        elif a_sup_avg > b_sup_avg:
            reasoning['support'] = f"A팀 힐링 우세 (+{sup_diff:.1%})"
        else:
            reasoning['support'] = f"B팀 힐링 우세 (+{sup_diff:.1%})"
        
        return reasoning