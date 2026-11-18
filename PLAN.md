# aces-high — Project Plan
> "He'd find out the kind of inside stuff nobody else knew, and that's what he'd put his money on." — Nicky, Casino
> Living document — updated as we build

---

## The Mission
Build a human performance intelligence system that happens to use NFL football as its dataset.
Layer 1 and 2 everyone has. Layers 3-12 are ours.
Free to build. Free to use. Gets smarter every single week.

---

## The Philosophy
- Every wrong prediction with honest reasoning attached is more valuable than a lucky right one
- Every modifier starts as a hypothesis — it earns its weight through outcomes or gets cut
- We show our blind spots — never present a prediction without showing what we don't know
- The goal in year one is not to win — the goal is to document everything so year two is smarter
- This is our first crew

---

## The Stack (All Free)
| Layer | Tool |
|-------|------|
| Base stats | nflverse (nflreadpy) — we reference, we don't archive |
| News scans | Yahoo Finance (yfinance) + headline scraping |
| Weather | Open-Meteo API (free, no key required) |
| Vegas lines | The Odds API (free tier) |
| Scheduling | GitHub Actions |
| Hosting | GitHub Pages |
| Frontend | Vanilla JS, no framework |
| Domain | TBD |

---

## Current State — Season 2026, Week 12

### What's Live
- 3,216 players tracked across all 32 teams
- Layer 1 (Body) + Layer 2 (Skill) complete for all players
- Layer 3 (Hunger via draft seed) live in predictions
- Practice reports running Wed/Thu/Fri via GitHub Actions
- Daily news scan running — injury/distraction/silence flags per team
- Odds fetch running — opening + closing lines, line movement, sharp signal
- Predictions generating for all games each week
- Outcomes recorder built — waiting on first closed bets to populate
- Ledger tracking open/closed bets with P&L
- All 9 pages live on GitHub Pages

### Data Files — Current Status
```
data/
├── predictions.json    — live, Week 12 predictions generated
├── outcomes.json       — built, empty (no closed bets yet — first week live)
├── news.json           — live, daily scans running
├── weather.json        — live
├── modifiers.json      — live
├── players.json        — live, 3,216 players, L1+L2 complete
├── practice.json       — live, Wed/Thu/Fri trajectory per player
├── teams.json          — initialized
├── coaches.json        — initialized
├── relationships.json  — initialized
├── stats.json          — built, empty (populates from outcomes)
├── blog.json           — built, empty (populates from outcomes)
├── odds.json           — live
├── ledger.json         — live, open bets tracked
├── scores.json         — live
└── metadata.json       — live, week/season/scan timestamps
```

### Scripts — Current Status
```
scripts/
├── fetch_news.py       — live, daily
├── fetch_odds.py       — live, twice weekly
├── fetch_practice.py   — live, Wed/Thu/Fri in season
├── fetch_weather.py    — live
├── fetch_scores.py     — live
├── predict.py          — live, full L1+L2+L3+modifiers
├── record_outcome.py   — live, closes bets + updates stats.json
├── update_ratings.py   — live, weekly nflverse pull
├── patch_skill_scores.py — utility, run as needed
├── seed_ledger.py      — utility, run once
└── show_scores.py      — utility, debug/inspect
```

### GitHub Actions — Current Status
```
.github/workflows/
├── daily_news.yml      — live
├── weekly_ratings.yml  — live
├── fetch_odds.yml      — live
├── practice_reports.yml — live
└── record_outcomes.yml — live
```

### Pages — Current Status
```
pages/
├── predictions.html    — live, accordion per game, clickable drill-down modals
├── edge-report.html    — live, best bets / active bets / stay away / skip
├── teams.html          — live, 32-team grid, detail panel, clickable stat modals
├── players.html        — live, player cards with L1+L2 data
├── ledger.html         — live, open/closed bets, P&L tracking
├── stats.html          — EXISTS but empty shell — needs outcome data + charts
├── blog.html           — EXISTS but empty shell — needs blog.json populated
├── methodology.html    — live
└── legal.html          — live
```

---

## The 12 Layer System — Build Status

| Layer | Name | Status |
|-------|------|--------|
| 1 | Body | ✅ Live — age, weight, snap%, career stage, combine |
| 2 | Skill | ✅ Live — position-ranked stats, proxy for OL/special teams |
| 3 | Mind / Hunger | ✅ Live — draft seed as hunger proxy, UDFA flag |
| 3 | Mind / Distraction | ✅ Live — news scan flags distraction/injury/silence |
| 4 | Personality | ⬜ Not started — needs behavioral inference engine |
| 5 | Relationships | ⬜ Not started — relationships.json initialized, empty |
| 6 | Team Chemistry | ⬜ Not started — coaches.json initialized, empty |
| 7 | Matchup | ⬜ Not started — direct position matchup scoring |
| 8 | Prediction | ✅ Live — L1+L2+L3+weather+practice+odds modifiers |
| 9 | Outcome | ✅ Built — record_outcome.py live, awaiting first closed games |
| 10 | Learning | ⬜ Waiting — stats.json populates after outcomes accumulate |
| 11 | Humility | ✅ Live — blind spots + flip conditions in every prediction |
| 12 | Anti-Bias | ⬜ Not started — narrative trap detector not built |

---

## What's Left — Prioritized

### Immediate (next session)
- [ ] `pages/stats.html` — modifier accuracy dashboard
  - Win rate by confidence tier (are our 70+ picks actually winning 70%?)
  - Which modifiers fired correctly vs missed
  - Calibration chart — confidence score vs actual win rate
  - By situation: divisional, underdog, short week, dome outdoors
  - *Blocked on outcomes — build the shell now, data fills it in*

### Soon
- [ ] `scripts/update_blog.py` — generate blog posts from prediction + outcome pairs
- [ ] `pages/blog.html` — render blog.json posts (shell exists, needs content logic)
- [ ] `pages/findings.html` — validated modifiers vs active hypotheses tracker

### Later (Layer expansion)
- [ ] Layer 4 — Personality inference (press conference language, social behavior)
- [ ] Layer 5 — Relationships web (beat reporter scraping, social media)
- [ ] Layer 6 — Coach scores (coaches.json population)
- [ ] Layer 7 — Direct position matchup scoring
- [ ] Layer 12 — Anti-bias narrative trap detector

### Launch
- [ ] `README.md` — origin story, full methodology summary, how to read the system
- [ ] Custom domain setup
- [ ] Update PLAN.md modifier weight table with actual outcome data once it accumulates

---

## Modifier Weight Table (all unvalidated — 0 outcomes recorded yet)

| Modifier | Starting Weight | Status | Data Points |
|----------|----------------|--------|-------------|
| Wind >20mph on passing game | ×0.75 | Hypothesis | 0/10 |
| Rain/snow on passing game | ×0.85 | Hypothesis | 0/10 |
| Temp <20°F on kicker | ×0.80 | Hypothesis | 0/10 |
| Dome team outdoors December | ×0.90 | Hypothesis | 0/10 |
| West coast team 10am ET kickoff | ×0.95 | Hypothesis | 0/10 |
| Away team >2 time zones | ×0.95 | Hypothesis | 0/10 |
| Hunger Index high | ×1.10 | Hypothesis | 0/10 |
| Distraction Index high | ×0.85 | Hypothesis | 0/10 |
| Silence bonus (no news, locked in) | ×1.05 | Hypothesis | 0/10 |
| Revenge game | ×1.10 | Hypothesis | 0/10 |
| Same team beef unresolved | ×0.90 | Hypothesis | 0/10 |
| Opposite team beef | ×1.10 | Hypothesis | 0/10 |
| Public callout — feeling type | ×0.80 | Hypothesis | 0/10 |
| Public callout — thinking type | ×1.05 | Hypothesis | 0/10 |
| London game hangover next week | ×0.92 | Hypothesis | 0/10 |
| Short week (Thursday game) | ×0.93 | Hypothesis | 0/10 |
| Coming off bye | ×1.03 | Hypothesis | 0/10 |
| Coach public callout incident | ×0.85 | Hypothesis | 0/10 |
| Star player exception documented | ×0.90 | Hypothesis | 0/10 |
| Vegas sharp vs public divergence | signal only | Hypothesis | 0/10 |

---

## Key Decisions Log
| Decision | Reason | Date |
|----------|--------|------|
| Reference nflverse, don't archive it | They maintain it better than we can, we focus on what they don't have | 2025 |
| All modifiers start as hypothesis | Opinion becomes evidence through outcomes or gets cut | 2025 |
| Minimum 10 data points before validating modifier | Prevents recency bias from corrupting weights | 2025 |
| Show blind spots in every prediction | Humility layer — we never know everything, Ace knew what he didn't know | 2025 |
| Flip conditions required in every prediction | Forces us to think about what would change our mind before kickoff | 2025 |
| Personality inferred not surveyed | We have behavioral data, we don't have access to players | 2025 |
| Hunger Index as individual modifier | Adversity and motivation are real and measurable through outcomes | 2025 |
| Private vs public accountability tracked | Most predictive coaching variable, nobody else is tracking it | 2025 |
| Relationship web as data layer | Personal connections cross team lines and affect performance | 2025 |
| Vegas line as signal not as bet | Smart money movement tells us what we don't know | 2025 |
| Year one goal is documentation not winning | First crew teaches second crew — system compounds | 2025 |
| Draft seed as hunger proxy (L3) | Real hunger data (income, contract type) not yet scraped — seed is directionally correct | 2026 |
| edge-report.html added outside original plan | Best bets / stay away / sharp warnings deserved their own surface | 2026 |
| Clickable drill-down modals on predictions + teams | Numbers mean nothing without the player data behind them | 2026 |

---

## Open Questions
- [ ] Practice report source reliability — ESPN injury API occasionally stale, need fallback
- [ ] Best free source for roster relationship data (beat reporters, social media)
- [ ] Personality inference confidence threshold — when do we have enough behavioral data
- [ ] How do we handle mid-season trades — player carries his scores to new team
- [ ] How do we score expansion of a player's role (new OC, new scheme fit)
- [ ] stats.html — what's the right chart library (Chart.js? pure canvas? pure CSS bars?)
- [ ] When outcomes accumulate — which modifiers get cut first vs promoted to validated

---

## Contributions This System Makes
1. Hunger Index — adversity as a quantified performance modifier
2. Distraction Index — life events as performance predictors
3. Silence bonus — absence of news as a positive signal
4. Practice trajectory (Wed/Thu/Fri) as more predictive than final designation
5. Personality compatibility matrix — inferred MBTI applied to unit chemistry *(planned)*
6. Relationship web — personal connections indexed and applied to matchups *(planned)*
7. Private vs public accountability as coach scoring variable *(planned)*
8. Flip conditions — what would change our prediction before kickoff
9. Modifier validation framework — hypothesis vs evidence, minimum data points
10. Humility layer — blind spots documented in every prediction
11. Anti-bias checks — narrative trap detector + recency bias protection *(planned)*
12. Year one as research dataset — wrong predictions with reasoning are the product

---

*"He'd be workin' on this shit day and night. There was nothin' about a game he was gonna bet that he didn't know."*

*Last updated: Season 2026 Week 12 — L1+L2+L3 live, all pages built, awaiting first outcomes*
*Next: pages/stats.html — the page that proves whether any of this actually works*
