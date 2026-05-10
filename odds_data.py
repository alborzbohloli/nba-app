"""
Odds data fetching from The Odds API.
Free tier: 500 requests/month at https://the-odds-api.com/
"""

import os
import requests
from typing import List, Dict, Optional


ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_nba"


def get_nba_games_with_odds() -> List[Dict]:
    """Get all NBA games with current odds (h2h, spreads, totals)."""
    if not ODDS_API_KEY:
        print("WARNING: No ODDS_API_KEY set")
        return []
    
    url = f"{ODDS_API_BASE}/sports/{SPORT_KEY}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching odds: {e}")
        return []


def get_player_props_for_game(game_id: str) -> Dict:
    """
    Get player props for a specific game.
    Note: free tier may have limited prop coverage.
    """
    if not ODDS_API_KEY:
        return {}
    
    # Player prop markets
    markets = "player_points,player_rebounds,player_assists,player_threes,player_blocks,player_steals,player_points_rebounds_assists"
    
    url = f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events/{game_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": markets,
        "oddsFormat": "american",
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching player props for {game_id}: {e}")
        return {}


def find_game_by_teams(home_team: str, away_team: str) -> Optional[Dict]:
    """
    Find a game in today's odds by team names.
    Returns the game dict or None.
    """
    games = get_nba_games_with_odds()
    home_lower = home_team.lower()
    away_lower = away_team.lower()
    
    for game in games:
        game_home = game.get('home_team', '').lower()
        game_away = game.get('away_team', '').lower()
        
        if (home_lower in game_home or game_home in home_lower) and \
           (away_lower in game_away or game_away in away_lower):
            return game
    
    return None


def parse_odds_for_prompt(game: Dict, player_props: Dict = None) -> Dict:
    """
    Parse odds data into a clean format for the AI prompt.
    """
    result = {
        'game_lines': {
            'spread': None,
            'total': None,
            'moneyline_home': None,
            'moneyline_away': None,
        },
        'player_props': []
    }
    
    if not game:
        return result
    
    # Use first bookmaker for simplicity
    bookmakers = game.get('bookmakers', [])
    if not bookmakers:
        return result
    
    book = bookmakers[0]
    home_team = game.get('home_team', '')
    away_team = game.get('away_team', '')
    
    for market in book.get('markets', []):
        market_key = market.get('key')
        outcomes = market.get('outcomes', [])
        
        if market_key == 'h2h':
            for o in outcomes:
                if o.get('name') == home_team:
                    result['game_lines']['moneyline_home'] = o.get('price')
                elif o.get('name') == away_team:
                    result['game_lines']['moneyline_away'] = o.get('price')
        elif market_key == 'spreads':
            for o in outcomes:
                if o.get('name') == home_team:
                    result['game_lines']['spread'] = {
                        'team': home_team,
                        'line': o.get('point'),
                        'odds': o.get('price'),
                    }
        elif market_key == 'totals':
            for o in outcomes:
                if o.get('name') == 'Over':
                    result['game_lines']['total'] = {
                        'line': o.get('point'),
                        'over_odds': o.get('price'),
                    }
                elif o.get('name') == 'Under':
                    if result['game_lines']['total']:
                        result['game_lines']['total']['under_odds'] = o.get('price')
    
    # Parse player props if provided
    if player_props and 'bookmakers' in player_props:
        prop_book = player_props['bookmakers'][0] if player_props['bookmakers'] else None
        if prop_book:
            for market in prop_book.get('markets', []):
                market_key = market.get('key')  # e.g., 'player_points'
                prop_type = market_key.replace('player_', '').replace('_', '_')
                
                for outcome in market.get('outcomes', []):
                    player_name = outcome.get('description', '')
                    line = outcome.get('point')
                    odds = outcome.get('price')
                    side = outcome.get('name', '').lower()  # 'over' or 'under'
                    
                    if player_name and line is not None:
                        result['player_props'].append({
                            'player_name': player_name,
                            'prop_type': prop_type,
                            'line': line,
                            'side': side,
                            'odds': odds,
                        })
    
    return result
