# Changelog

## v1.0 — Foundation
- PLAN.md — full 12 layer system designed
- Repo structure initialized
- data/ — all JSON files initialized
- scripts/fetch_news.py — daily 32 team news scanner, keyword scoring, silence bonus
- .github/workflows/daily_news.yml — 6AM PST daily automation

## v1.3 — Frontend
- assets/style.css — full dark theme design system, all components
- components/nav.js — single file controls all pages, hamburger, active state
- index.html — predictions grid, season summary tiles
- pages/teams.html — 32 team logo grid, click to expand, accordion roster by position group, player drill-down with body/skill scores, flags, headlines
- pages/ledger.html — dual tracking table, confidence calibration bars, full history
- pages/methodology.html — 12 layer system explained, accordion
- pages/legal.html — full disclaimer

## v1.2 — Paper Betting Ledger
- scripts/fetch_odds.py — The Odds API, twice weekly (Friday opening + Sunday closing), consensus line across DraftKings/FanDuel/BetMGM/Caesars, line movement delta calculated automatically
- scripts/record_outcome.py — closes bets, calculates flat + confidence weighted P&L, modifier accuracy tracking, confidence calibration buckets, blog entry generation
- data/ledger.json — full paper betting ledger with dual tracking (flat $100 vs confidence weighted)
- data/odds.json — initialized
- .github/workflows/fetch_odds.yml — Friday 12pm + Sunday 8am PST
- API key stored as GitHub secret ODDS_API_KEY — never in code
- Free tier strategy: 2 fetches/week = ~576 requests/season, under 500/month limit

## v1.1 — Layer 1 + 2 Ratings Engine
- scripts/update_ratings.py — pulls all nflverse datasets, builds Layer 1 (body) + Layer 2 (skill) scores for 3,215 active players
- Layer 1: age vs position peak curve, weight vs optimal, career longevity, snap trend
- Layer 2: EPA percentile ranked vs position peers (QB/RB/WR/TE/DEF/K)
- Draft profile with hunger_seed baseline baked in from round/pick
- Injury/practice status profile per player
- Combine athleticism profile per player
- Layer 3-5 placeholders preserved on merge — ratings update never overwrites mind/personality/relationship data
- requirements.txt — pandas + pyarrow added
- .github/workflows/weekly_ratings.yml — every Tuesday 8AM PST
