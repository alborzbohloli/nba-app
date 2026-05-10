"""
NBA data fetching functions.
Uses the unofficial nba_api package (free, no API key).
"""

from nba_api.stats.endpoints import (
    commonteamroster,
    leaguegamefinder,
    playergamelog,
    leaguedashteamstats,
    leaguedashplayerstats,
    teamgamelog,
    boxscoretraditionalv2,
    scoreboardv2,
)
from nba_api.stats.static import teams as static_teams
from nba_api.stats.static import players as static_players
import time
from typing import List, Dict, Optional


# Custom headers to avoid being blocked
NBA_API_HEADERS = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Connection': 'keep-alive',
    'Referer': 'https://stats.nba.com/',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
}


def get_all_teams() -> List[Dict]:
    """Returns list of all 30 NBA teams."""
    return static_teams.get_teams()


def get_team_by_name(name: str) -> Optional[Dict]:
    """Find team by partial name match (case insensitive)."""
    name = name.lower().strip()
    teams = get_all_teams()
    
    for team in teams:
        if team['nickname'].lower() == name or team['full_name'].lower() == name:
            return team
    
    for team in teams:
        if name in team['full_name'].lower() or name in team['nickname'].lower():
            return team
    
    for team in teams:
        if team['abbreviation'].lower() == name:
            return team
    
    return None


def get_team_roster(team_id: int) -> List[Dict]:
    """Get current roster for a team."""
    try:
        roster = commonteamroster.CommonTeamRoster(
            team_id=team_id,
            headers=NBA_API_HEADERS,
            timeout=30
        )
        df = roster.get_data_frames()[0]
        return df.to_dict('records')
    except Exception as e:
        print(f"Error fetching roster for team {team_id}: {e}")
        return []


def get_player_season_stats(player_id: int) -> Optional[Dict]:
    """Get current season stats for a player."""
    try:
        from nba_api.stats.endpoints import playerprofilev2
        profile = playerprofilev2.PlayerProfileV2(
            player_id=player_id,
            headers=NBA_API_HEADERS,
            timeout=30
        )
        df = profile.get_data_frames()[0]
        if len(df) > 0:
            current = df.iloc[-1].to_dict()
            return current
        return None
    except Exception as e:
        print(f"Error fetching stats for player {player_id}: {e}")
        return None


def get_player_last_n_games(player_id: int, n: int = 30) -> List[Dict]:
    """Get last N games for a player."""
    try:
        log = playergamelog.PlayerGameLog(
            player_id=player_id,
            headers=NBA_API_HEADERS,
            timeout=30
        )
        df = log.get_data_frames()[0]
        if len(df) > n:
            df = df.head(n)
        return df.to_dict('records')
    except Exception as e:
        print(f"Error fetching games for player {player_id}: {e}")
        return []


def get_player_recent_averages(player_id: int, n: int = 10) -> Dict:
    """
    Get recent averages for a player across last N games.
    Returns averages for all major stats — this is what the
    AI uses to make stat projections.
    """
    games = get_player_last_n_games(player_id, n=n)
    if not games:
        return {}
    
    def avg(field):
        vals = [g.get(field, 0) or 0 for g in games]
        return round(sum(vals) / len(vals), 2) if vals else 0
    
    def median(field):
        vals = sorted([g.get(field, 0) or 0 for g in games])
        return vals[len(vals) // 2] if vals else 0
    
    def min_max(field):
        vals = [g.get(field, 0) or 0 for g in games]
        return {'min': min(vals), 'max': max(vals)} if vals else {'min': 0, 'max': 0}
    
    return {
        'sample_size': len(games),
        'minutes': {'avg': avg('MIN'), 'median': median('MIN'), **min_max('MIN')},
        'points': {'avg': avg('PTS'), 'median': median('PTS'), **min_max('PTS')},
        'rebounds': {'avg': avg('REB'), 'median': median('REB'), **min_max('REB')},
        'assists': {'avg': avg('AST'), 'median': median('AST'), **min_max('AST')},
        'steals': {'avg': avg('STL'), 'median': median('STL'), **min_max('STL')},
        'blocks': {'avg': avg('BLK'), 'median': median('BLK'), **min_max('BLK')},
        'threes_made': {'avg': avg('FG3M'), 'median': median('FG3M'), **min_max('FG3M')},
        'fg_pct': avg('FG_PCT'),
        'three_pct': avg('FG3_PCT'),
        'ft_pct': avg('FT_PCT'),
        'ftas': {'avg': avg('FTA'), 'median': median('FTA')},
        'turnovers': {'avg': avg('TOV'), 'median': median('TOV')},
        'plus_minus': avg('PLUS_MINUS'),
        'recent_games_summary': [
            {
                'date': g.get('GAME_DATE'),
                'matchup': g.get('MATCHUP'),
                'min': g.get('MIN'),
                'pts': g.get('PTS'),
                'reb': g.get('REB'),
                'ast': g.get('AST'),
                'fg3m': g.get('FG3M'),
            } for g in games[:10]
        ]
    }


def get_team_last_n_games(team_id: int, n: int = 10) -> List[Dict]:
    """Get last N games for a team."""
    try:
        log = teamgamelog.TeamGameLog(
            team_id=team_id,
            headers=NBA_API_HEADERS,
            timeout=30
        )
        df = log.get_data_frames()[0]
        if len(df) > n:
            df = df.head(n)
        return df.to_dict('records')
    except Exception as e:
        print(f"Error fetching games for team {team_id}: {e}")
        return []


def get_team_season_stats(team_id: int) -> Optional[Dict]:
    """Get team's season stats including pace and defensive rating."""
    try:
        stats = leaguedashteamstats.LeagueDashTeamStats(
            measure_type_detailed_defense='Advanced',
            headers=NBA_API_HEADERS,
            timeout=30
        )
        df = stats.get_data_frames()[0]
        team_row = df[df['TEAM_ID'] == team_id]
        if len(team_row) > 0:
            return team_row.iloc[0].to_dict()
        return None
    except Exception as e:
        print(f"Error fetching team stats for {team_id}: {e}")
        return None


def get_simplified_rotation(team_id: int, n_games: int = 10) -> Dict:
    """
    Build a simplified rotation profile from last N team games.
    Returns minutes distribution per player.
    """
    games = get_team_last_n_games(team_id, n=n_games)
    if not games:
        return {'sample_size_games': 0, 'minutes_distribution': {}, 'is_simplified': True}
    
    player_minutes = {}
    player_names = {}
    
    for game in games[:n_games]:
        game_id = game.get('Game_ID')
        if not game_id:
            continue
        try:
            time.sleep(0.5)
            box = boxscoretraditionalv2.BoxScoreTraditionalV2(
                game_id=game_id,
                headers=NBA_API_HEADERS,
                timeout=30
            )
            df = box.get_data_frames()[0]
            team_df = df[df['TEAM_ID'] == team_id]
            
            for _, row in team_df.iterrows():
                pid = row['PLAYER_ID']
                pname = row['PLAYER_NAME']
                minutes = row.get('MIN', '0')
                mins_value = parse_minutes(minutes)
                
                if pid not in player_minutes:
                    player_minutes[pid] = []
                    player_names[pid] = pname
                player_minutes[pid].append(mins_value)
        except Exception as e:
            print(f"Error fetching boxscore for {game_id}: {e}")
            continue
    
    distribution = {}
    for pid, mins_list in player_minutes.items():
        if not mins_list:
            continue
        sorted_mins = sorted(mins_list)
        avg = sum(mins_list) / len(mins_list)
        median = sorted_mins[len(sorted_mins) // 2]
        floor = sorted_mins[0] if len(sorted_mins) <= 3 else sorted_mins[1]
        
        distribution[pid] = {
            'player_name': player_names[pid],
            'avg_minutes': round(avg, 1),
            'median_minutes': round(median, 1),
            'minutes_floor': round(floor, 1),
            'minutes_ceiling': round(sorted_mins[-1], 1),
            'games_played': len(mins_list),
        }
    
    top_players = sorted(distribution.items(), key=lambda x: x[1]['avg_minutes'], reverse=True)[:10]
    
    return {
        'sample_size_games': len(games),
        'is_simplified': True,
        'top_rotation_players': dict(top_players),
    }


def parse_minutes(min_value) -> float:
    """Parse minutes from NBA format (MM:SS, MM, or float)."""
    if min_value is None or min_value == '':
        return 0.0
    if isinstance(min_value, (int, float)):
        return float(min_value)
    if isinstance(min_value, str):
        if ':' in min_value:
            parts = min_value.split(':')
            return float(parts[0]) + float(parts[1]) / 60
        try:
            return float(min_value)
        except ValueError:
            return 0.0
    return 0.0


def get_games_today() -> List[Dict]:
    """Get list of NBA games scheduled for today."""
    try:
        from datetime import datetime
        today = datetime.now().strftime('%m/%d/%Y')
        sb = scoreboardv2.ScoreboardV2(
            game_date=today,
            headers=NBA_API_HEADERS,
            timeout=30
        )
        df = sb.get_data_frames()[0]
        return df.to_dict('records')
    except Exception as e:
        print(f"Error fetching today's games: {e}")
        return []
