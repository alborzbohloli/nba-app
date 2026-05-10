"""
NBA Hall of Famer Betting Analysis - Main FastAPI app.

Run locally: uvicorn main:app --reload
Deploy on Railway: handled by Procfile
"""

import os
import json
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

from nba_data import (
    get_team_by_name,
    get_team_roster,
    get_team_season_stats,
    get_simplified_rotation,
    compute_base_rate,
    get_player_last_n_games,
    get_games_today,
    get_all_teams,
)
from odds_data import (
    get_nba_games_with_odds,
    find_game_by_teams,
    get_player_props_for_game,
    parse_odds_for_prompt,
)
from claude_analyzer import analyze_game


app = FastAPI(title="NBA Hall of Famer")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Optional simple password protection
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
security = HTTPBasic() if APP_PASSWORD else None


def check_auth(credentials: Optional[HTTPBasicCredentials] = None):
    """Optional basic auth check. Skipped if APP_PASSWORD not set."""
    if not APP_PASSWORD:
        return True
    if not credentials or credentials.password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Show the input form."""
    teams = get_all_teams()
    teams_sorted = sorted(teams, key=lambda t: t['full_name'])
    return templates.TemplateResponse(request, "input.html", {
        "teams": teams_sorted,
    })


@app.get("/api/roster/{team_id}")
async def api_get_roster(team_id: int):
    """Return roster for team (used by frontend to populate starter dropdowns)."""
    roster = get_team_roster(team_id)
    return [{
        "id": p.get("PLAYER_ID"),
        "name": p.get("PLAYER"),
        "position": p.get("POSITION"),
    } for p in roster]


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    home_team_id: int = Form(...),
    away_team_id: int = Form(...),
    home_starters: str = Form(...),  # comma-separated names
    away_starters: str = Form(...),
    crew_chief: str = Form(...),
    referee: str = Form(...),
    umpire: str = Form(...),
):
    """
    Run the full analysis pipeline:
    1. Gather NBA data (rosters, stats, rotations)
    2. Gather odds data (lines, props)
    3. Compute base rates for each prop
    4. Send to Claude
    5. Display results
    """
    
    try:
        # Step 1: Get team info
        all_teams = get_all_teams()
        home_team = next((t for t in all_teams if t['id'] == home_team_id), None)
        away_team = next((t for t in all_teams if t['id'] == away_team_id), None)
        
        if not home_team or not away_team:
            raise HTTPException(status_code=400, detail="Invalid team selection")
        
        # Step 2: Get rosters
        home_roster = get_team_roster(home_team_id)
        away_roster = get_team_roster(away_team_id)
        
        # Step 3: Get team season stats
        home_team_stats = get_team_season_stats(home_team_id)
        away_team_stats = get_team_season_stats(away_team_id)
        
        # Step 4: Get simplified rotation profiles
        home_rotation = get_simplified_rotation(home_team_id, n_games=10)
        away_rotation = get_simplified_rotation(away_team_id, n_games=10)
        
        # Step 5: Find game in odds API
        odds_game = find_game_by_teams(home_team['nickname'], away_team['nickname'])
        
        game_lines = {}
        player_props = []
        
        if odds_game:
            # Get player props
            player_props_data = get_player_props_for_game(odds_game.get('id'))
            parsed = parse_odds_for_prompt(odds_game, player_props_data)
            game_lines = parsed['game_lines']
            player_props = parsed['player_props']
        
        # Step 6: Compute base rates for each player prop
        # Build a lookup of player_name -> player_id from rosters
        all_players = home_roster + away_roster
        name_to_id = {p.get('PLAYER', '').lower(): p.get('PLAYER_ID') for p in all_players}
        
        for prop in player_props:
            player_name_lower = prop['player_name'].lower()
            player_id = name_to_id.get(player_name_lower)
            if not player_id:
                # Try partial match
                for name, pid in name_to_id.items():
                    if player_name_lower in name or name in player_name_lower:
                        player_id = pid
                        break
            
            if player_id:
                base_rate = compute_base_rate(
                    player_id=player_id,
                    prop_type=prop['prop_type'],
                    line_value=prop['line'],
                    n_games=30,
                )
                prop['base_rate'] = base_rate
            else:
                prop['base_rate'] = None
        
        # Step 7: Build the game_analysis_input for Claude
        game_data = {
            "meta": {
                "generated_at_utc": datetime.utcnow().isoformat(),
                "mode": "PRE_GAME",
            },
            "game": {
                "home_team": home_team['full_name'],
                "away_team": away_team['full_name'],
                "venue": f"{home_team['city']}",
            },
            "home_team_data": {
                "name": home_team['full_name'],
                "season_stats": home_team_stats,
                "confirmed_starters": [s.strip() for s in home_starters.split(",")],
                "rotation_profile": home_rotation,
                "roster_summary": [
                    {"name": p.get('PLAYER'), "position": p.get('POSITION'), "id": p.get('PLAYER_ID')}
                    for p in home_roster
                ],
            },
            "away_team_data": {
                "name": away_team['full_name'],
                "season_stats": away_team_stats,
                "confirmed_starters": [s.strip() for s in away_starters.split(",")],
                "rotation_profile": away_rotation,
                "roster_summary": [
                    {"name": p.get('PLAYER'), "position": p.get('POSITION'), "id": p.get('PLAYER_ID')}
                    for p in away_roster
                ],
            },
            "ref_crew": {
                "crew_chief": crew_chief,
                "referee": referee,
                "umpire": umpire,
                "note": "No historical aggregate data available in v1 — use league average tendencies."
            },
            "game_lines": game_lines,
            "available_player_props": player_props,
            "calibration_adjustments": {
                "note": "No calibration data yet (system in initial use)."
            },
            "user_state": {
                "bankroll_current": 1000,  # default; can be made configurable
                "kelly_fraction": 0.25,
                "daily_bets_remaining": 4,
            }
        }
        
        # Step 8: Send to Claude
        analysis = analyze_game(game_data)
        
        # Step 9: Render output page
        return templates.TemplateResponse(request, "output.html", {
            "analysis": analysis,
            "game_data": game_data,
            "home_team": home_team['full_name'],
            "away_team": away_team['full_name'],
            "props_count": len(player_props),
            "has_odds": bool(odds_game),
        })
        
    except Exception as e:
        return templates.TemplateResponse(request, "error.html", {
            "error": str(e),
        })


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "odds_api_configured": bool(os.getenv("ODDS_API_KEY")),
    }
