"""
NBA Hall of Famer Betting Analysis - v2
- No odds API (removed)
- Player dropdowns auto-populate from team selection
- Stat projections for every selected player
"""

import os
import json
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from nba_data import (
    get_team_roster,
    get_team_season_stats,
    get_simplified_rotation,
    get_player_recent_averages,
    get_all_teams,
)
from claude_analyzer import analyze_game


app = FastAPI(title="NBA Hall of Famer v2")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


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
    """
    Return roster for a team (used by frontend JS to populate
    the player dropdowns when user picks a team).
    """
    roster = get_team_roster(team_id)
    return [{
        "id": p.get("PLAYER_ID"),
        "name": p.get("PLAYER"),
        "position": p.get("POSITION"),
    } for p in roster if p.get("PLAYER_ID")]


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    home_team_id: int = Form(...),
    away_team_id: int = Form(...),
    home_starters: str = Form(...),  # comma-separated player IDs
    away_starters: str = Form(...),
    home_extra_players: str = Form(""),  # extra players to project (optional)
    away_extra_players: str = Form(""),
    crew_chief: str = Form(...),
    referee: str = Form(...),
    umpire: str = Form(...),
):
    """
    Run the full analysis pipeline:
    1. Gather NBA data (rosters, stats, rotations)
    2. For every selected player: pull last-10-game averages
    3. Send everything to Claude
    4. Display projections + verdicts
    """
    
    try:
        # Get team info
        all_teams = get_all_teams()
        home_team = next((t for t in all_teams if t['id'] == home_team_id), None)
        away_team = next((t for t in all_teams if t['id'] == away_team_id), None)
        
        if not home_team or not away_team:
            raise HTTPException(status_code=400, detail="Invalid team selection")
        
        # Parse selected player IDs
        def parse_ids(s):
            return [int(x.strip()) for x in s.split(",") if x.strip().isdigit()]
        
        home_starter_ids = parse_ids(home_starters)
        away_starter_ids = parse_ids(away_starters)
        home_extra_ids = parse_ids(home_extra_players)
        away_extra_ids = parse_ids(away_extra_players)
        
        all_home_player_ids = home_starter_ids + home_extra_ids
        all_away_player_ids = away_starter_ids + away_extra_ids
        
        if not all_home_player_ids or not all_away_player_ids:
            raise HTTPException(
                status_code=400,
                detail="Must select at least one player for each team"
            )
        
        # Get rosters (for name lookups)
        home_roster = get_team_roster(home_team_id)
        away_roster = get_team_roster(away_team_id)
        home_id_to_name = {p['PLAYER_ID']: p['PLAYER'] for p in home_roster}
        away_id_to_name = {p['PLAYER_ID']: p['PLAYER'] for p in away_roster}
        
        # Get team-level data
        home_team_stats = get_team_season_stats(home_team_id)
        away_team_stats = get_team_season_stats(away_team_id)
        home_rotation = get_simplified_rotation(home_team_id, n_games=10)
        away_rotation = get_simplified_rotation(away_team_id, n_games=10)
        
        # For every selected player, pull recent averages (this is THE core data)
        home_player_data = []
        for pid in all_home_player_ids:
            name = home_id_to_name.get(pid, f"Player {pid}")
            recent = get_player_recent_averages(pid, n=10)
            home_player_data.append({
                "player_id": pid,
                "player_name": name,
                "is_starter": pid in home_starter_ids,
                "recent_averages_last_10": recent,
            })
        
        away_player_data = []
        for pid in all_away_player_ids:
            name = away_id_to_name.get(pid, f"Player {pid}")
            recent = get_player_recent_averages(pid, n=10)
            away_player_data.append({
                "player_id": pid,
                "player_name": name,
                "is_starter": pid in away_starter_ids,
                "recent_averages_last_10": recent,
            })
        
        # Build the analysis input — NO ODDS DATA
        game_data = {
            "meta": {
                "generated_at_utc": datetime.utcnow().isoformat(),
                "mode": "PRE_GAME",
                "version": "v2_no_odds",
            },
            "game": {
                "home_team": home_team['full_name'],
                "away_team": away_team['full_name'],
                "venue": home_team['city'],
            },
            "home_team_data": {
                "name": home_team['full_name'],
                "is_home": True,
                "season_stats": home_team_stats,
                "rotation_profile": home_rotation,
                "selected_players": home_player_data,
            },
            "away_team_data": {
                "name": away_team['full_name'],
                "is_home": False,
                "season_stats": away_team_stats,
                "rotation_profile": away_rotation,
                "selected_players": away_player_data,
            },
            "ref_crew": {
                "crew_chief": crew_chief,
                "referee": referee,
                "umpire": umpire,
                "note": "No historical aggregate data available — use league-average tendencies."
            },
            "user_state": {
                "bankroll_current": 1000,
                "kelly_fraction": 0.25,
            }
        }
        
        # Send to Claude
        analysis = analyze_game(game_data)
        
        # Render output
        return templates.TemplateResponse(request, "output.html", {
            "analysis": analysis,
            "home_team": home_team['full_name'],
            "away_team": away_team['full_name'],
            "total_players_analyzed": len(home_player_data) + len(away_player_data),
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
        "version": "v2_no_odds",
    }
