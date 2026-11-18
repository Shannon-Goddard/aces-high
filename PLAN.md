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
- Layer 4 (Personality) complete — MBTI inferred for all 3,216 players
  - I/E from career longevity + snap consistency
  - S/N from position archetype + college program
  - T/F from draft slot vs performance delta
  - J/P from snap trend consistency
- Team compat scoring — each player scored against their communication chain
  - HC (×0.35 if QB/LB, ×0.20 otherwise) + coordinator (×0.25) + position partners (×0.40)
  - QB↔HC weighted double in team-level compat score
- Role fit scoring — position demands vs player MBTI per axis
  - Best Fit / Adequate / Poor Fit badge on every player card
  - Evidence breakdown per axis in expanded panel
- Veteran drain modifier — Poor Fit compounds over career length
  - `drain_mult = 1.0 + min(0.5, years_exp / 20)` — max 1.5x at 10+ years
  - Best Fit veterans get the same compounding boost (mastery deepens)
- Coaches page live — 32-team grid, HC/OC/DC staff panel, HC↔player compat web
  - Playing career badge (NFL/College/Never) per coach
  - MBTI evidence popup per coach
  - Avg compat score per team header
- Player cards — inline click-to-expand compat panel
  - Coach chain first (HC always, OC/DC where applicable)
  - Communication partners by position map, sorted by compat score
  - Role fit score + axis evidence at top of panel
- Practice reports running Wed/Thu/Fri via GitHub Actions
- Daily news scan running — injury/distraction/silence flags per team
- Odds fetch running — opening + closing lines, line movement, sharp signal
- Predictions generating for all games each week with full personality modifier stack
- Outcomes recorder built — waiting on first closed bets to populate
- Ledger tracking open/closed bets with P&L
- All 10 pages live on GitHub Pages

### Data Files — Current Status
```
data/
├── predictions.json       — live, Week 12 predictions with compat + role fit multipliers
├── outcomes.json          — built, empty (no closed bets yet)
├── news.json              — live, daily scans running
├── weather.json           — live
├── modifiers.json         — live
├── players.json           — live, 3,216 players, L1+L2+L4 complete
│                            layer4_personality: mbti_type, ie/sn/tf/jp,
│                            evidence per axis, team_compat_score,
│                            role_fit_score, role_fit_label, role_fit_evidence
├── coaches.json           — live, 96 coaches (32 HC + OC/DC per team)
│                            playing_career block, mbti_type, mbti_signals,
│                            role_fit_score, pfr_record
├── coach_playing_careers.csv — 179 historical coaches, 71 verified
├── practice.json          — live, Wed/Thu/Fri trajectory per player
├── teams.json             — initialized
├── relationships.json     — initialized
├── stats.json             — built, empty (populates from outcomes)
├── blog.json              — built, empty (populates from outcomes)
├── odds.json              — live
├── ledger.json            — live, open bets tracked
├── scores.json            — live
└── metadata.json          — live, week/season/scan timestamps
```

### Scripts — Current Status
```
scripts/
├── fetch_news.py          — live, daily
├── fetch_odds.py          — live, twice weekly
├── fetch_practice.py      — live, Wed/Thu/Fri in season
├── fetch_weather.py       — live
├── fetch_scores.py        — live
├── fetch_coaches.py       — live, PFR record + MBTI inference + playing career
├── predict.py             — live, L1+L2+L3+L4+weather+practice+odds modifiers
│                            team_compat_score() + team_role_fit_score() both wired
│                            role_fit_mult uses veteran drain multiplier
├── infer_personality.py   — live, weekly (after update_ratings.py)
│                            Pass 1: MBTI inference for all 3,216 players
│                            Pass 2: team_compat_score per player
│                            compute_role_fit() per player (POS_DEMANDS table)
├── build_coach_careers.py — utility, one-time nflverse join for coach playing data
├── record_outcome.py      — live, closes bets + updates stats.json + triggers blog
├── update_blog.py         — live, regenerates blog.json from all closed bets (safe to re-run)
├── update_ratings.py      — live, weekly nflverse pull
├── patch_skill_scores.py  — utility, run as needed
├── seed_ledger.py         — utility, run once
└── show_scores.py         — utility, debug/inspect
```

### GitHub Actions — Current Status
```
.github/workflows/
├── daily_news.yml         — live
├── weekly_ratings.yml     — live (update_ratings → infer_personality → fetch_coaches)
├── fetch_odds.yml         — live
├── practice_reports.yml   — live
└── record_outcomes.yml    — live
```

### Pages — Current Status
```
pages/
├── predictions.html       — live, accordion per game, clickable drill-down modals
├── edge-report.html       — live, best bets / active bets / stay away / skip
├── teams.html             — live, 32-team grid, detail panel, clickable stat modals
├── coaches.html           — live, 32-team grid, staff panel, HC↔player compat web
│                            played badge, MBTI evidence popup, avg compat score
├── players.html           — live, player cards with L1+L2+L4 data
│                            compat bar (4th bar), role fit badge, click-to-expand panel
│                            coach chain + communication partners + role fit evidence
├── ledger.html            — live, open/closed bets, P&L tracking
├── stats.html             — live shell — wires up automatically when outcomes accumulate
├── findings.html          — live, 23 modifiers tracked, layer status current
├── blog.html              — live, week/result/type filters, modifier story per post
├── methodology.html       — live
└── legal.html             — live
```

---

## The 12 Layer System — Build Status

| Layer | Name | Status |
|-------|------|--------|
| 1 | Body | ✅ Live — age, weight, snap%, career stage, combine |
| 2 | Skill | ✅ Live — position-ranked stats, proxy for OL/special teams |
| 3 | Mind / Hunger | ✅ Live — draft seed as hunger proxy, UDFA flag |
| 3 | Mind / Distraction | ✅ Live — news scan flags distraction/injury/silence |
| 4 | Personality | ✅ Live — MBTI inferred for all 3,216 players + coaches |
| 4 | Personality / Compat | ✅ Live — team_compat_score per player, affects predictions |
| 4 | Personality / Role Fit | ✅ Live — position demand scoring, veteran drain modifier |
| 5 | Relationships | ⬜ Not started — relationships.json initialized, empty |
| 6 | Team Chemistry | 🔶 Partial — coach↔player compat live, unit chemistry pending |
| 7 | Matchup | ⬜ Not started — direct position matchup scoring |
| 8 | Prediction | ✅ Live — L1+L2+L3+L4+weather+practice+odds modifiers |
| 9 | Outcome | ✅ Built — record_outcome.py live, awaiting first closed games |
| 10 | Learning | ✅ Live — update_blog.py + blog.html wired, populates as outcomes close |
| 11 | Humility | ✅ Live — blind spots + flip conditions in every prediction |
| 12 | Anti-Bias | ⬜ Not started — narrative trap detector not built |

---

## Personality Modifier Stack (in predict.py)

Both multipliers applied together on the raw team score before normalization:

```
raw_score * compat_mult * role_fit_mult
```

| Modifier | Formula | Range | Notes |
|----------|---------|-------|-------|
| compat_mult | `1 + (team_compat - 50) / 500` | ×0.90 – ×1.10 | QB↔HC double-weighted |
| role_fit_mult | `1 + avg(base_mod × drain_mult)` | ×0.90 – ×1.10 | QB double-weighted |
| base_mod | `(role_fit_score - 50) / 1000` | ±0.05 per player | Best Fit=+5%, Poor Fit=-5% |
| drain_mult | `1.0 + min(0.5, years_exp / 20)` | 1.0 – 1.5x | Compounds at 10+ years |

**Example — KC 2026:**
- Mahomes (QB, 7yr, rf:100): drain 1.35x → mod +0.0675
- Kelce (TE, 11yr, rf:100): drain 1.50x → mod +0.0750 (mastery compounds)
- J. Reid (DB, 6yr, rf:0): drain 1.30x → mod -0.0650 (6 years of energy tax)
- KC combined mult: 1.0402 (+4% on raw score)

---

## Communication Chain (Position Map)

Who directly communicates with whom — drives compat scoring and expanded player panels:

| Position | Talks to | Coach chain |
|----------|----------|-------------|
| QB | WR, TE, RB, OL | HC (direct) + OC |
| WR | QB | OC |
| TE | QB | OC |
| RB | QB, OL | OC |
| OL | QB, RB | OC |
| LB | DL, DB | HC (direct) + DC |
| DB | LB, DB | DC |
| DL | LB | DC |
| K/P/LS | — | — |

---

## Build Queue — Ordered by Impact

Ordering logic: accountability before expansion. The system needs to be able to measure
itself before we add more signals. Wrong order = we build on sand.

---

### 1. `pages/stats.html` — Calibration Dashboard
*Makes the system accountable to itself. Without this, year two isn't smarter than year one.*
- Win rate by confidence tier — are our 70+ picks actually winning 70%?
- Which modifiers fired correctly vs missed (weather, compat, role fit, hunger, silence)
- Calibration chart — predicted confidence vs actual win rate
- By situation: divisional, underdog, short week, dome outdoors, Thursday game
- Shell exists — data fills in as outcomes accumulate
- **Blocked on:** first closed outcomes (record_outcome.py needs to run on completed games)
- **Build now:** full shell with empty state messaging, wires up automatically when data arrives

---

### 2. Blind Spot / Lesson Auto-Population
*The learning layer. Every wrong prediction with honest reasoning is more valuable than a lucky right one — but only if we capture the reasoning.*
- `record_outcome.py` already closes bets and writes to `outcomes.json`
- Add `lesson` auto-population: when a prediction closes wrong, compare what fired vs what the actual game showed
- Fields to auto-write: `lesson`, `what_we_missed`, `modifier_that_fired`, `modifier_that_should_have_fired`
- `predictions.json` already has `lesson: null` placeholder on every prediction — just needs population
- Feeds directly into `stats.html` modifier accuracy and `findings.html` validated vs hypothesis tracker
- **Dependency:** needs at least one closed outcome to test against

---

### 3. Momentum Scoring (Layer 2 Extension)
*Highest direct impact on prediction accuracy of anything not yet built.*
- Season-aggregate skill score misses form — a team that's won 4 straight plays differently than a 4-8 team
- Rolling 3-week weighted skill score: last week ×0.5, 2 weeks ago ×0.3, 3 weeks ago ×0.2
- Store as `layer2_skill.momentum_score` alongside existing `skill_score`
- `predict.py` blends: `effective_skill = skill_score * 0.7 + momentum_score * 0.3`
- Data already exists in nflverse weekly stats — `update_ratings.py` just needs a rolling window
- Show momentum arrow (↑↓→) on player cards and team detail
- **No new data source needed** — pure calculation change in `update_ratings.py`

---

### 4. Contract Year Flag (Layer 3 Extension)
*Clean data, real signal, slots directly into existing hunger layer.*
- Players in final year of contract historically outperform — hunger spike
- Players who just signed a big extension historically dip 6-12 months — comfort plateau
- Source: Spotrac (publicly scrapable) or Over The Cap API
- Add `contract_year: true/false` and `extension_year: true/false` to player draft/hunger block
- Hunger seed modifier: contract year +15, extension year (yr 1) -10
- Show contract status badge on player card alongside existing hunger bar
- **New data source needed:** Spotrac scraper or manual seed for starters
- **Dependency:** none — can build alongside anything else

---

### 5. Snap% Drop as Early Injury Warning
*The data is already there — we're just not using it as an injury signal yet.*
- A player whose snap% drops 15%+ over 3 weeks without an injury report is hiding something
- Currently flagged only as a J/P personality signal — needs a second read as injury early warning
- Add `snap_drop_flag: true` to `layer1_body` when: snap% falls >15pts over 3 weeks AND no injury report
- `predict.py` treats `snap_drop_flag` same as `questionable` in injury penalty calculation
- Surfaces on player card as a subtle warning indicator
- **No new data source needed** — snap data already in `layer1_body.snap_trend`
- **Build note:** this is a 20-line change in `update_ratings.py` + small UI addition

---

### 6. Divisional Familiarity Modifier
*Small modifier, real edge — the market underprices rematch tightening.*
- Teams that play each other twice a year have full film on each other
- Second matchup historically tightens — underdog covers more often in rematches
- Two signals: (a) same division = familiarity penalty on favorite, (b) rematch within same season = tighter line
- Add `divisional_game: true/false` and `rematch: true/false` to prediction output
- Modifier: divisional game ×0.97 on favorite's edge, rematch ×0.95
- Schedule data already in nflverse — simple lookup
- **No new data source needed**

---

### 7. Coordinator Change Tracker
*One of the most disruptive mid-season events — currently invisible to the system.*
- New OC or DC mid-season = players running a new scheme, role fit score temporarily invalid
- `coaches.json` already has OC/DC per team — need change detection between weekly fetches
- When coordinator changes: flag affected players' `role_fit_score` as `scheme_transition: true`
- `predict.py` treats `scheme_transition` players as Adequate (50) regardless of computed role fit
- Clears after 3 weeks (enough time to learn the new scheme)
- Show "New scheme" indicator on affected player cards
- **Dependency:** `fetch_coaches.py` needs a previous-state comparison

---

### 8. Coach Market Fit (The INFJ Problem Applied to HCs)
*Most original contribution in the pipeline. Nobody else is tracking this.*
- An introverted HC in a high-media market pays the same energy tax an INFJ manager does
- Reid in KC: low media pressure, stable ownership, long tenure = optimal environment
- A Belichick-type I in NY or Dallas = structural drain regardless of talent
- Score each HC on: market size (media pressure), ownership stability, tenure length, roster compat avg
- `coach_market_fit_score` stored on HC entry in `coaches.json`
- Feeds into `predict.py` as a small HC modifier on team score (±3% max — it's real but subtle)
- Show on coaches page alongside existing role fit score
- **Data needed:** market size lookup (static table), ownership stability (manual seed), tenure from PFR (already have)
- **Dependency:** coach MBTI needs S/N and J/P filled in — currently most HCs are `I?T?`

---

### 9. `pages/findings.html` — Validated Modifiers Tracker
*The page that separates hypothesis from evidence.*
- Two columns: Validated (10+ data points, modifier confirmed) vs Active Hypothesis
- Each modifier card: what it predicts, data points collected, win rate when fired, current status
- Auto-populates from `stats.json` as outcomes accumulate
- Shell exists — needs content logic wired to outcome data
- **Dependency:** needs outcome data from stats.html calibration work

---

### 10. `scripts/update_blog.py` + `pages/blog.html`
*Turns the system's reasoning into readable content.*
- Auto-generate blog posts from prediction + outcome pairs
- Each post: what we predicted, why, what happened, what we learned
- Tone matches the system — honest about misses, specific about reasoning
- Shell exists for both — needs content generation logic
- **Dependency:** needs closed outcomes to have anything to write about

---

### 11. Layer 5 — Relationships Web
*The layer that captures what happens off the field.*
- Beat reporter scraping for relationship signals (feuds, friendships, mentor/mentee)
- Social media cross-team connection indexing
- `relationships.json` initialized and empty — waiting on scraping strategy
- Real signal: a WR traded to face his former team, a QB mentoring his backup who just got traded away
- **Hardest data problem in the system** — no clean free source, requires scraping strategy

---

### 12. Layer 6 — Unit Chemistry (OL Cohesion)
*The missing piece of team chemistry beyond coach↔player.*
- OL units that have played together 3+ years outperform shuffled lines significantly
- Track years together per unit: OL group, secondary group, LB corps
- `unit_cohesion_score` per position group, feeds into team skill modifier
- Data source: nflverse roster history — years on same team per player pair

---

### 13. Layer 7 — Direct Position Matchup Scoring
*The head-to-head layer.*
- QB skill score vs opposing DB skill score — direct matchup delta
- WR1 vs CB1, OL pass protection vs DL pass rush
- Currently team scores are independent — matchup scoring makes them interact
- Significant architecture change to `predict.py` — save for after calibration data exists

---

### 14. Layer 12 — Anti-Bias Narrative Trap Detector
*The system that keeps us honest about our own reasoning.*
- Detect when a prediction is driven by narrative rather than data
- Flags: "team on revenge game" without supporting score delta, "hot team" without momentum data
- Recency bias check: are we overweighting last week's result?
- Public narrative divergence: when our pick matches the public narrative, reduce confidence slightly

---

### Launch Checklist
- [ ] `README.md` — origin story, full methodology, how to read the system
- [ ] Custom domain setup
- [ ] Update modifier weight table with actual outcome data once it accumulates
- [ ] Accessibility pass on all pages

---

## Modifier Weight Table

| Modifier | Weight/Formula | Status | Data Points |
|----------|---------------|--------|-------------|
| Wind >20mph on passing game | ×0.75 | Hypothesis | 0/10 |
| Rain/snow on passing game | ×0.85 | Hypothesis | 0/10 |
| Temp <20°F on kicker | ×0.80 | Hypothesis | 0/10 |
| Dome team outdoors December | ×0.90 | Hypothesis | 0/10 |
| West coast team 10am ET kickoff | ×0.95 | Hypothesis | 0/10 |
| Away team >2 time zones | ×0.95 | Hypothesis | 0/10 |
| Hunger Index high | ×1.10 | Hypothesis | 0/10 |
| Distraction Index high | ×0.85 | Hypothesis | 0/10 |
| Silence bonus (no news, locked in) | ×1.05 | Hypothesis | 0/10 |
| Personality compat (team) | ×0.90–1.10 | Hypothesis | 0/10 |
| Role fit — Best Fit veteran | up to ×1.075 | Hypothesis | 0/10 |
| Role fit — Poor Fit veteran | down to ×0.925 | Hypothesis | 0/10 |
| Momentum score (last 3 weeks weighted) | skill×0.7 + momentum×0.3 | Hypothesis | 0/10 |
| Contract year (final year) | hunger +15 | Hypothesis | 0/10 |
| Extension year (yr 1 post-signing) | hunger -10 | Hypothesis | 0/10 |
| Snap% drop >15pts, no injury report | early injury warning | Hypothesis | 0/10 |
| Divisional game | ×0.97 on favorite edge | Hypothesis | 0/10 |
| Rematch within same season | ×0.95 on favorite edge | Hypothesis | 0/10 |
| Coordinator change (scheme transition) | role fit → 50 for 3 weeks | Hypothesis | 0/10 |
| Coach market fit (I/E vs market size) | ±3% on team score | Hypothesis | 0/10 |
| Revenge game | ×1.10 | Hypothesis | 0/10 |
| Public callout — feeling type | ×0.80 | Hypothesis | 0/10 |
| Public callout — thinking type | ×1.05 | Hypothesis | 0/10 |
| London game hangover next week | ×0.92 | Hypothesis | 0/10 |
| Short week (Thursday game) | ×0.93 | Hypothesis | 0/10 |
| Coming off bye | ×1.03 | Hypothesis | 0/10 |
| Coach public callout incident | ×0.85 | Hypothesis | 0/10 |
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
| MBTI inferred from career stats not surveys | 3,216 players — behavioral inference at scale is the only viable path | 2026 |
| Two-pass personality inference | Pass 1 sets all types, Pass 2 computes compat — order matters for partner lookups | 2026 |
| Compat as multiplier not additive | Personality doesn't replace talent, it modifies how talent expresses under pressure | 2026 |
| Role fit as sustainability signal not ability signal | An INFJ can manage — but it costs more. Poor Fit players run at higher burn rate | 2026 |
| Veteran drain multiplier on role fit | Misfit compounds over time — year 8 in the wrong role shows in the numbers | 2026 |
| QB↔HC double-weighted in compat | The play-calling philosophy relationship is the highest-leverage link on any roster | 2026 |
| Coach playing career tracked | Played vs never played is a real signal — Vrabel vs Harbaugh (John) contrast is visible | 2026 |
| Communication chain drives compat partners | QB talks to WR/TE/RB/OL — not to the DC. Chain mirrors real football structure | 2026 |
| Momentum over season aggregate | A 4-8 team and a team on a 4-game win streak have the same season stats but play completely differently | 2026 |
| Contract year as hunger spike | Final year players are playing for their next contract — real, measurable, underpriced by the market | 2026 |
| Contract year proxy via draft round + years_exp | No contracts API yet — swap `is_contract_year()` with real data when one is added, all downstream logic stays the same | 2026 |
| Snap% drop as early injury signal | A player losing snaps without an injury report is hiding something — the data knows before the report does | 2026 |
| Divisional familiarity as favorite penalty | Second matchup tightens — the underdog has film now, the market doesn't fully price this | 2026 |
| Rematch detection via predictions.json scan | No schedule API needed — if we predicted the same matchup earlier this season, it's a rematch | 2026 |
| Coordinator change invalidates role fit | A player's role fit score is scheme-specific — new OC means new demands, 3-week reset is honest | 2026 |
| Coordinator change detection via staff diff | No external API needed — diff CURRENT_STAFF against previous coaches.json on each weekly run | 2026 |
| Coach market fit as structural drain | An introverted HC in a high-media market pays the same energy tax an INFJ manager does — it's real and nobody tracks it | 2026 |
| Market pressure as static table | Nielsen DMA + ownership volatility + media scrutiny seeded manually — swap with live data when available | 2026 |
| Blind spot auto-population on wrong predictions | A wrong prediction with captured reasoning is the most valuable data point in the system | 2026 |

---

## Open Questions
- [ ] Practice report source reliability — ESPN injury API occasionally stale, need fallback
- [ ] Best free source for roster relationship data (beat reporters, social media)
- [ ] Personality inference confidence threshold — when do we have enough behavioral data
- [ ] How do we handle mid-season trades — player carries his scores to new team (compat auto-updates on next infer_personality.py run — already handled)
- [ ] How do we score expansion of a player's role (new OC, new scheme fit)
- [ ] stats.html — what's the right chart library (Chart.js? pure canvas? pure CSS bars?)
- [ ] When outcomes accumulate — which modifiers get cut first vs promoted to validated
- [ ] Coach MBTI confidence — most HCs have 2 known axes (I?T? pattern) — needs press conference language scraping to fill S/N and J/P

---

## Contributions This System Makes
1. Hunger Index — adversity as a quantified performance modifier
2. Distraction Index — life events as performance predictors
3. Silence bonus — absence of news as a positive signal
4. Practice trajectory (Wed/Thu/Fri) as more predictive than final designation
5. Personality compatibility matrix — inferred MBTI applied to unit chemistry ✅ Live
6. Role fit scoring — position demands vs player type, Best Fit / Adequate / Poor Fit ✅ Live
7. Veteran drain modifier — misfit compounds over career length ✅ Live
8. Communication chain compat — QB↔WR, LB↔DB, coach chain all scored ✅ Live
9. Momentum scoring — rolling 3-week weighted skill, form matters as much as season aggregate ✅ Live
10. Contract year flag — final year hunger spike, extension year comfort plateau ✅ Live
11. Snap% drop early warning — losing snaps without a report is a signal ✅ Live
12. Divisional familiarity modifier — second matchup tightens, underdog covers more ✅ Live
13. Coordinator change tracker — scheme transition resets role fit for 3 weeks ✅ Live
14. Coach market fit — introvert HC in high-media market pays structural energy tax ✅ Live
15. Relationship web — personal connections indexed and applied to matchups *(planned)*
16. Private vs public accountability as coach scoring variable *(planned)*
17. Flip conditions — what would change our prediction before kickoff
18. Modifier validation framework — hypothesis vs evidence, minimum data points
19. Humility layer — blind spots documented in every prediction
20. Anti-bias checks — narrative trap detector + recency bias protection *(planned)*
21. Year one as research dataset — wrong predictions with reasoning are the product

---

*"He'd be workin' on this shit day and night. There was nothin' about a game he was gonna bet that he didn't know."*

*Last updated: Season 2026 Week 12 — L1+L2+L3+L4 live, coaches page live, personality modifier stack complete*
*Build queue: 14 items ordered by impact — stats.html calibration first, momentum second, blind spot learning third*
