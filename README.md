# NBA Hall of Famer Betting Analysis — Setup Guide

This is a complete, deployable web app. Follow these steps and you'll have a working website on your phone in about 30-45 minutes.

---

## WHAT THIS DOES

You open the website on your phone. Pick tonight's NBA game. Type in the 5 starters per team and the 3 referees. Hit "Run Hall of Famer Analysis." 30-60 seconds later you get:

- A predicted game winner with confidence tier
- 3-5 SAFE player prop picks with calibrated probabilities, base rates, and Kelly Criterion bet sizing
- An avoid list of 5-10 props with specific reasons
- Full 12-layer breakdown (collapsible)

Backend automatically pulls rosters, season stats, last 10 games of rotation data, current betting lines, and computes base rates for every prop before sending everything to Claude for analysis.

---

## WHAT'S IN THIS FOLDER

```
nba_app/
├── main.py                  # The web app (FastAPI)
├── nba_data.py              # Pulls NBA stats, rosters, rotations
├── odds_data.py             # Pulls betting lines from The Odds API
├── claude_analyzer.py       # Sends data to Claude, parses response
├── requirements.txt         # Python dependencies
├── Procfile                 # Tells Railway how to run the app
├── runtime.txt              # Python version
├── .env.example             # Template for your API keys
├── templates/
│   ├── input.html           # The form
│   ├── output.html          # The results page
│   └── error.html           # Error page
└── static/
    └── style.css            # Mobile-friendly dark theme
```

---

## STEP 1 — GET YOUR API KEYS (10 MINUTES)

You need two API keys before deploying. Both have free tiers.

### A. Anthropic API key (for Claude)

1. Go to https://console.anthropic.com/
2. Sign up with email
3. Click "API Keys" in the sidebar
4. Click "Create Key" — give it any name (e.g., "nba-app")
5. Copy the key (starts with `sk-ant-...`) — you can only see it once
6. Add credit: Click "Plans & Billing" → add $5-10. That's enough for ~30-50 analyses.

### B. The Odds API key (for betting lines)

1. Go to https://the-odds-api.com/
2. Click "Get API Key"
3. Sign up (free tier: 500 requests/month — plenty for 1-3 games per day)
4. Copy your API key from the dashboard

Save both keys somewhere safe for the next step.

---

## STEP 2 — DEPLOY TO RAILWAY (15 MINUTES)

Railway is a hosting service that's free for small apps like this.

### A. Sign up

1. Go to https://railway.app/
2. Click "Login" → sign in with GitHub (easiest) or email
3. Verify your account

### B. Get the code onto Railway

You have two options:

**OPTION 1 — Upload via GitHub (recommended):**

1. Go to https://github.com/ and create a free account if you don't have one
2. Create a new repository (call it `nba-betting-app`, mark as Private)
3. Upload all files from this `nba_app` folder (drag and drop on GitHub web)
4. In Railway, click "New Project" → "Deploy from GitHub repo"
5. Select your `nba-betting-app` repo
6. Railway auto-detects it's a Python app and starts deploying

**OPTION 2 — Direct upload via Railway CLI (if your friend prefers this):**

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# From the nba_app folder
cd nba_app
railway init
railway up
```

### C. Add environment variables

In Railway, go to your project → Variables tab → click "New Variable" for each:

| Variable Name | Value |
|---------------|-------|
| `ANTHROPIC_API_KEY` | (paste the key from Step 1A) |
| `ODDS_API_KEY` | (paste the key from Step 1B) |
| `APP_PASSWORD` | (any password you want, e.g., `myhouse2026`) |

The `APP_PASSWORD` is optional — it adds a basic password prompt so randoms can't use your site if they find the URL.

### D. Generate a public URL

In Railway → Settings → Networking → click "Generate Domain"

You'll get a URL like `nba-betting-app-production.up.railway.app`. That's your website. Open it on your phone.

---

## STEP 3 — TEST IT (5 MINUTES)

1. Open your Railway URL on your phone
2. Pick a real NBA game happening tonight (or in the next few days)
3. Look up the expected starters (Google "[team] starting lineup tonight")
4. Look up the referees (https://official.nba.com/referee-assignments/) — usually posted ~2 hours before tip
5. Fill in the form, hit submit
6. Wait 30-60 seconds — the analysis should appear

If you see an error:
- Check the Railway logs (Railway dashboard → Deployments → latest → View logs)
- Most common issues:
  - API key typo → re-paste in Variables
  - "Insufficient credit" on Anthropic → add more in Anthropic console
  - "Rate limit" on Odds API → wait an hour

---

## STEP 4 — ADD TO YOUR PHONE HOME SCREEN

So it feels like a real app:

**iPhone:**
1. Open the URL in Safari
2. Tap the Share button (square with arrow)
3. Scroll down → "Add to Home Screen"
4. Name it "NBA HOF" or whatever you want

**Android:**
1. Open in Chrome
2. Tap the 3-dot menu → "Add to Home screen"

Now it has its own icon. Looks and feels like a native app.

---

## RUNNING IT LOCALLY (OPTIONAL — FOR TESTING)

If you want to test before deploying:

```bash
# 1. Install Python 3.11+
# (download from python.org)

# 2. From the nba_app folder, install dependencies
pip install -r requirements.txt

# 3. Copy .env.example to .env and fill in your keys
cp .env.example .env
# (edit .env with your real keys)

# 4. Run it
uvicorn main:app --reload

# 5. Open http://localhost:8000 in your browser
```

---

## MONTHLY COST

| Item | Cost |
|------|------|
| Railway hosting | $0-5/month (you get $5 free credit) |
| Anthropic API (~50 analyses/month) | $10-20/month |
| The Odds API (free tier) | $0 |
| NBA Stats API | $0 |
| **Total** | **~$10-25/month** |

---

## WHAT THIS VERSION DOES NOT YET INCLUDE

This is the **MVP version**. It works end-to-end and gives real analysis. But these features from the full spec are NOT yet built:

- ❌ Database (no pick logging yet — every analysis is fresh, no learning over time)
- ❌ Calibration system (no track record being built)
- ❌ Weekly diagnostic loop
- ❌ Post-game review
- ❌ Bankroll tracking and daily caps
- ❌ Line history polling
- ❌ Referee crew historical aggregates (Claude uses general knowledge for now)
- ❌ Nightly rotation profile job (computes on-demand instead — slower per request)

**Why not?** These features add 20-30 hours of build time. The MVP version takes 30-45 minutes to deploy and gets you a working, useful tool today.

Once you've used it for 2-3 weeks and confirmed you actually want it, your programmer adds the database and learning systems on top. That's the path the full spec describes.

---

## TROUBLESHOOTING

### "Application failed to respond" on Railway
- Check logs (Deployments tab → latest → View logs)
- Usually means missing env variable or Python error
- Make sure all 3 env variables are set

### Analysis takes forever / times out
- NBA API can be slow (it's an unofficial API)
- The simplified rotation profile fetches 10 boxscores which is the slowest step
- If it consistently fails, your friend can add caching to nba_data.py

### "No odds data found"
- The Odds API free tier has limited prop coverage
- Game lines (spread/total/moneyline) usually work
- Player props sometimes only available on the paid tier
- Analysis still runs but with fewer props to evaluate

### Claude returns garbled JSON
- Rare, but happens. Hit refresh and try again.
- If persistent, your friend can add a JSON-repair step in claude_analyzer.py

### "Rate limited" from NBA
- Wait 5-10 minutes
- Or your friend can add rate limit handling with longer backoff

---

## FOR YOUR PROGRAMMER

When she's ready to extend this to the full spec from the build document:

1. **Add Postgres database** (Supabase free tier, connection string into env vars)
2. **Run the CREATE TABLE statements** from the spec document Section 5
3. **Add picks_history logging** to `claude_analyzer.py` after every analysis
4. **Add nightly cron jobs** using APScheduler (rotation profiles, outcome logging, calibration)
5. **Add weekly diagnostic** — Monday 6 AM, queries picks_history for patterns
6. **Add post-game review UI** — page that shows hits/misses for completed games

The MVP code is structured so adding these is additive — nothing needs to be rewritten.

---

## QUESTIONS?

If something breaks or doesn't work, the issue is usually:
1. Missing/typo'd API key (90% of issues)
2. NBA API temporarily down
3. The Odds API rate limit hit
4. Anthropic credit ran out

Check Railway logs first — they'll tell you exactly what failed.
