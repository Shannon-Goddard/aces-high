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

## The Data We OWN (our original research)
We do not collect what nflverse already collects.
We collect everything else and timestamp all of it.

```
data/
├── predictions.json       — every game prediction, full reasoning, confidence, blind spots
├── outcomes.json          — actual results + why we were wrong + what we learned
├── news.json              — daily headline archive per team/player with timestamps
├── weather.json           — game location weather per matchup per week
├── modifiers.json         — all modifier values applied per prediction
├── players.json           — our collected layer 3-5 data per player
├── teams.json             — our collected layer 6 data per team
├── relationships.json     — player relationship web (friend/rival/beef/mentor)
├── coaches.json           — coach score data per coach
├── stats.json             — our accuracy over time, which modifiers actually work
└── blog.json              — auto-generated articles from predictions + outcomes
```

---

## The 12 Layer System

### Layer 1 — BODY (nflverse, objective floor)
```
Age
Height
Weight vs position optimal (we calculate from historical nflverse data)
Age vs position peak curve (we build these curves from nflverse history)
  RB:  peaks 22-24, cliff at 27
  WR:  peaks 24-27, longer tail
  QB:  peaks 28-32, outliers to 35+
  OL:  peaks 26-30, most durable
  CB:  peaks 24-27, speed dependent
  K:   peaks 26-32, mental game extends career
Years in vs average career length by position
Snap count trend (last 4 weeks — rising/falling/flat)
Practice participation trajectory (Wed/Thu/Fri — we collect this)
  DNP Wednesday = concerning
  DNP Wed + Thu  = serious
  Full all week → surprise DNP Friday = something just happened
  Wed limited → Thu full → Fri full = trending right
Official injury designation (Questionable/Doubtful/Out)
Combine athleticism baseline (40 time, position drills)
```

### Layer 2 — SKILL (nflverse, ranked vs peers at same position)
```
Raw stats mean nothing — everything ranked vs position peers

QB:
  EPA per play
  Completion % over expectation (adjusted for difficulty, not raw %)
  Time to throw
  Performance under pressure vs clean pocket (split)
  Red zone efficiency
  Off script play rate (intuitive vs sensing proxy)
  Big game performance history (primetime, playoffs)

RB:
  Yards after contact
  EPA per carry
  Receiving out of backfield
  Fumble rate
  Yards before contact (OL credit vs player credit separator)

WR/TE:
  Yards per route run
  Catch % vs targets
  Separation metrics
  YAC vs peers
  Target share trend
  Red zone target share

Defense (individual):
  Pressure rate (pass rushers)
  Coverage grade (DBs)
  Tackle efficiency
  Missed tackle rate
  Yards allowed per coverage snap

Special Teams:
  Kicker: field goal % by distance + weather splits
  Punter: net average + hang time
  Returner: yards per return vs peers
```

### Layer 3 — MIND (we collect)

**Hunger Index** *(the chip on his shoulder)*
```
Draft position / undrafted                    → + hunger
Hometown zip code median income (census)      → low income = + hunger
Prove-it contract vs guaranteed money         → prove-it = + hunger
Came back from career-threatening injury      → + hunger
First in family to make it                    → + hunger
Years of being overlooked / passed over       → + hunger
Playing against team that cut/traded him      → + hunger spike
Contract year with nothing guaranteed after   → + hunger

Comfort variables (reduce hunger score):
  Massive guaranteed contract recently signed → - hunger
  5th+ year, comfortable starter              → - hunger
  Top recruit since 15, never been told no    → - hunger
  Just got paid, nothing to prove yet         → - hunger
```

**Distraction Index** *(what's pulling his head away)*
```
Tangible / Visible:
  New contract just signed                    → flag
  Visible wealth flex (house, car, public)    → flag
  Entourage growing — new money new problems  → flag
  Legal trouble (arrest, lawsuit)             → - major
  Trade request / wants out                   → - major
  Public beef with teammate or coach          → - major

Mental / Emotional:
  Relationship drama in headlines             → - moderate
  New baby / pregnant partner                 → flag (could go either way)
  Family health crisis                        → - moderate
  Death in family or close circle             → - major
  Divorce / breakup public                    → - moderate

Invisible (the Ace gold — POSITIVE signals):
  NO NEWS AT ALL — locked in, quiet, focused  → + bonus
  Low key offseason, no clubs, no drama       → + bonus
  Seen at extra film sessions                 → + bonus
  Practice reports glowing                    → + bonus
  Quietly rehabbing, no complaints            → + bonus
```

### Layer 4 — PERSONALITY (inferred MBTI, we collect from behavioral data)
```
We do not quiz players. We infer from:
  Press conference language patterns
  Social media behavior (frequency, content, spontaneity)
  Post game interviews after wins vs losses
  Body language on sideline
  Performance consistency patterns
  Off script play rate
  Conflict resolution history
  Career trajectory variance

The four axes:
  I/E — Introvert vs Extrovert
    Extrovert: feeds off crowd, big stage amplifier
    Introvert: goes internal, ice cold OR laser focused
    Neither is better — knowing which predicts hostile environment performance

  S/N — Sensing vs Intuition
    Sensing: scheme follower, consistent, reliable
    Intuitive: improvises, unpredictable, high ceiling high variance
    Sensing QB + Intuitive WR = timing route breakdowns
    Intuitive QB + Intuitive WR = magic OR chaos

  T/F — Thinking vs Feeling
    Thinking: processes criticism analytically, bounces back faster
    Feeling: deeply affected by chemistry, coach relationship, crowd
    Feeling player + public callout coach = disaster
    Feeling player + private accountability coach = outperforms skill score

  J/P — Judging vs Perceiving
    Judging: structured, consistent, hates uncertainty, thrives in systems
    Perceiving: adaptable, thrives in chaos, boom or bust
    Judging QB in no-huddle = thrives
    Perceiving QB in rigid system = frustrated

Compatibility Matrix:
  QB/WR personality match                     → +/- chemistry modifier
  Player/Coach personality match              → +/- performance modifier
  Unit cohesion (OL, secondary, receiving)    → +/- unit modifier
  Feeling player + public callout             → performance crater flag
  Thinking player + public callout            → possible fuel flag
```

### Layer 5 — RELATIONSHIPS (we collect, timestamped)
```
data/relationships.json structure:
  player_a, player_b, relationship_type, source, timestamp, notes

Relationship types:
  friend         → same team: possible distraction / opposite team: possible softness
  rival          → same team: competition boost OR locker room bomb
  mentor         → same team: multiplier effect / opposite team: student proving himself
  beef           → same team: BOMB — flag + watch practice reports
                   opposite team: + hunger for both
  former_teammate → familiarity cuts both ways — know each other's tendencies
  college_bond   → deep trust, scheme familiarity
  agent_shared   → sometimes matters more than people think

Same team beef modifier:
  Could increase individual performance (outshine each other)
  OR implode on big stage when trust breaks down
  → flag as directional uncertainty, watch practice reports for resolution

Opposite team beef modifier:
  Almost always + hunger for both players
  → elevate both individual ratings for this matchup

Revenge game flags:
  Playing against former team                 → + hunger spike
  Playing in hometown                         → + motivation
  Playing against team that cut him           → + hunger major
  Playing against coach who drafted then traded him → + hunger major
  Playing against his mentor                  → + proving himself
```

### Layer 6 — TEAM CHEMISTRY (we collect)
```
data/teams.json + data/coaches.json

Roster Continuity:
  Same core for 3+ years                      → + chemistry
  Rebuilt every offseason                     → - chemistry
  Coordinator changes this season             → - adjustment period
  How many offensive systems on this roster   → too many voices = -

Coach Score:
  Credibility:
    Played the game at high level             → + credibility
    Coached multiple positions                → + credibility
    Won in different systems                  → + credibility
    Calls plays himself vs trusts coordinators → context dependent

  Psychological Safety:
    Players publicly defend him               → + trust
    Players take accountability in press      → + (coach handled it right privately)
    Press conferences honest vs corporate     → + signal
    Players return to visit after leaving     → + real tell
    Former players speak positively           → + culture signal

  Private vs Public Accountability:
    Sideline screaming incidents (on camera)  → - major
    Press conference player callouts          → - major
    Player embarrassed publicly               → performance crater next 3 games
    Post loss no drama — players accountable  → + private accountability culture
    Player says "coach and I talked, we're good" → + handled right

  Fairness Standard:
    Star player exceptions documented         → - locker room poison
    Same standard applied to all             → + trust multiplier
    Role player benched for mistake star gets away with → - flag

  The "In It With Them" Score:
    Coach works harder than his players       → + wall running
    Coach shares his own mistakes publicly    → + psychological safety
    Coach celebrates wins publicly, credits players → + culture
    Coach takes blame publicly, protects players → + loyalty
    Coach goes to bat in contract negotiations → + loyalty
    Coach protects injured players from rush back → + trust

  Autonomy Score:
    Lets coordinators coordinate              → + trust
    Trusts veterans to adjust at line         → + autonomy
    Pulls players after one mistake           → - fear culture
    Clock management — panic vs trust         → measurable

  Hindsight Culture:
    Same mistakes repeated                    → no learning loop
    Halftime adjustment rate                  → coordinators trusted
    Performance better second half of season  → culture compounds
    Year over year improvement same roster    → culture building works

  Coach Score Metrics:
    Playing/coaching experience breadth       → +
    Tenure with current roster                → +
    Coordinator stability under him           → +
    Player retention rate                     → +
    Halftime adjustment rate                  → +
    Year over year improvement same roster    → +
    Public player criticism incidents         → -
    Coordinator turnover rate                 → -
    Trade requests under him                  → -
```

### Layer 7 — MATCHUP (all layers colliding)
```
Direct Position Matchups:
  This WR's route running vs this CB's coverage — head to head not team averages
  This pass rusher's pressure rate vs this QB's under pressure performance
  This RB's yards after contact vs this LB's missed tackle rate
  Every direct matchup scored individually then rolled up

Scheme Matchup:
  Does this offense attack exactly where this defense is weakest
  Has this DC faced this exact scheme before — and what happened
  New scheme vs veteran defense — learning curve is measurable
  Coordinator vs coordinator historical record

Historical Head to Head:
  Not just team records — coordinator matchup travels with them
  This QB's stats vs this specific DC (regardless of team)
  This pass rusher vs this specific LT — every time they've lined up
  This kicker in this specific stadium
  This coach's record as underdog vs favorite

Situational Context:
  Divisional game — scheme advantages shrink, emotion rises
  Playoff implications — who needs this more right now
  Back to back divisional — fatigue plus familiarity
  First meeting vs second meeting same season — adjustments made
  Revenge game at team level (not just individual)
  International game hangover — London game teams underperform following week

Momentum Collision:
  Winning streak vs losing streak
  Recent coordinator firing — sometimes spark not flag
  Coming off bye — rested but potentially cold
  Short week — tired legs but possible chip on shoulder

Weather vs Scheme:
  Wind >20mph → passing rating × 0.75
  Rain/snow → passing rating × 0.85
  Temp <20°F → kicker rating × 0.80
  Dome team playing outdoors in December → measurable drop
  West coast team, 10am East coast kickoff → body clocks say 7am
  Away team >2 time zones traveled → team rating × 0.95
  Cold weather team hosting dome team in January → home field amplified

Home Field:
  Stadium noise rating (some genuinely affect play)
  Opposing QB historical performance in loud stadiums
  Rookie QB first road game in hostile environment
  Team coming off home loss — crowd dynamic complicated
  Neutral site — home field erased entirely

Vegas Line as Signal (not as bet):
  Line movement with no obvious news → someone knows something
  Public % vs sharp % divergence → signal
  Historical performance of this team as home favorite vs road underdog
  We never bet against Vegas — we use it as a data point
```

### Layer 8 — PREDICTION (output)
```
predictions.json structure per game:
  game_id
  date + timestamp
  home_team / away_team
  week / season

  team_ratings:
    home: { body_score, skill_score, mind_score, chemistry_score }
    away: { body_score, skill_score, mind_score, chemistry_score }

  modifiers_applied:
    weather: { conditions, impact, confidence }
    injuries: { flags, trajectory, confidence }
    hunger_delta: { home, away }
    distraction_flags: { home, away }
    chemistry_score: { home, away }
    matchup_advantages: { unit, scheme, historical }
    momentum: { home, away }
    personality_compatibility: { key_matchups }
    relationship_flags: { active_beefs, revenge_games }
    vegas_signal: { line, movement, sharp_vs_public }

  prediction:
    spread_pick: team + confidence 1-100
    over_under_pick: over/under + confidence 1-100
    moneyline_pick: team + confidence 1-100
    primary_reasoning: [ top 3 factors that moved the needle ]
    hypothesis_modifiers: [ modifiers applied but not yet validated ]

  blind_spots:
    [ list of what we don't know yet that could flip this ]

  flip_conditions:
    [ exactly what new information would change our prediction before kickoff ]

  modifier_status:
    [ validated modifiers vs hypothesis modifiers — clearly labeled ]
```

### Layer 9 — OUTCOME (what actually happened)
```
outcomes.json structure per game:
  game_id
  final_score
  spread_result: win/loss/push
  over_under_result: win/loss/push
  moneyline_result: win/loss/push

  post_mortem:
    what_we_got_right: []
    what_we_got_wrong: []
    which_modifiers_fired: []
    which_modifiers_missed: []
    surprise_variables: [ things that happened we didn't have in our model ]
    lesson: one sentence — what does this teach the system

  keyword_outcomes:
    { keyword: fired/missed } — same as stocks keyword accuracy tracker
```

### Layer 10 — LEARNING (system gets smarter)
```
stats.json — updated after every game closes

Overall accuracy:
  Total predictions, win rate, confidence calibration
  (did our 80% confidence picks win 80% of the time?)

By modifier:
  Each modifier tracked independently
  Validated: fired correctly X% of the time over N games
  Hypothesis: not enough data yet — minimum 10 data points before weighting

By variable type:
  Weather modifiers accuracy
  Hunger Index accuracy
  Distraction Index accuracy
  Personality compatibility accuracy
  Relationship web accuracy
  Coach score accuracy
  Vegas signal accuracy

By situation:
  Divisional game accuracy
  Underdog accuracy
  Short week accuracy
  Dome team outdoors accuracy

Modifier weight adjustment rules:
  Minimum 10 data points before adjusting weight
  Minimum 5 data points before removing a modifier
  Never adjust weight based on one game — recency bias protection
```

### Layer 11 — HUMILITY (we show our blind spots)
```
Every prediction includes:
  Uncertainty flags:
    Injury report incomplete — waiting on Friday practice
    News scan returned nothing — silence unconfirmed
    First meeting this roster — no head to head data
    Weather forecast within 48hrs of kickoff — reprice
    Line moved with no news — someone knows something we don't
    Modifier applied but not yet validated — hypothesis only

Confidence score rules:
  High confidence (70-100): multiple validated modifiers pointing same direction
  Medium confidence (40-69): mix of validated and hypothesis modifiers
  Low confidence (1-39): mostly hypothesis, significant unknowns
  No prediction: unknowns too high to model responsibly
```

### Layer 12 — ANTI-BIAS (narrative trap + recency bias protection)
```
Narrative Trap Detector:
  Is this modifier weighted because data supports it
  OR because the story is compelling → flag as hypothesis
  Are we ignoring a counter signal because it doesn't fit → force document it
  Is confidence driven by data OR by how good the story sounds → require data citation

Recency Bias Check:
  Rating spike supported by underlying metrics OR just last week's box score
  Recent performance above career baseline → flag as regression candidate
  Season average weighted more heavily than last 3 games
  Minimum 5 data points before adjusting any modifier weight
  System should be harder to move than our gut feeling
```

---

## Automated Daily Flow (GitHub Actions, free)

```
Daily (year round):
  fetch_news.py         — scan all 32 teams + key players for headlines
                          timestamp everything, score keywords, update news.json

Weekly (Tuesday, new week opens):
  update_ratings.py     — pull nflverse stats, recalculate base ratings
                          update players.json + teams.json layer 1 + 2 scores

Wednesday-Friday (in season):
  fetch_practice.py     — scrape practice participation reports
                          log Wed/Thu/Fri trajectory per player

Game week (Thursday/Sunday morning):
  fetch_weather.py      — pull Open-Meteo forecast for each game location
  fetch_lines.py        — pull current Vegas lines + movement from Odds API
  predict.py            — run all layers, generate prediction, write predictions.json

Post game (Sunday night / Monday):
  record_outcome.py     — log actual result, run post mortem, update stats.json
  update_blog.py        — generate blog entry from prediction + outcome
```

---

## Site Structure

### Pages
```
index.html                → this week's predictions grid, confidence scores, top flags
pages/predictions.html    → full prediction detail per game, all modifiers shown
pages/ledger.html         → full prediction history, win/loss record, all-time accuracy
pages/stats.html          → analytics dashboard — which modifiers actually work
pages/players.html        → individual player cards, all 12 layers displayed
pages/teams.html          → team chemistry scores, coach scores, roster continuity
pages/blog.html           → auto-generated articles from predictions + outcomes
pages/methodology.html    → the full 12 layer system explained
pages/findings.html       → validated findings vs active hypotheses
pages/legal.html          → not financial advice, not betting advice, research only
```

### Navigation
```
Single components/nav.js — same pattern as stocks
Home | Predictions | Ledger | Stats | Players | Teams | Blog | Methodology
```

---

## JSON Data Structures

### players.json (our data, not nflverse)
```json
{
  "player_id": "nflverse_id",
  "name": "",
  "team": "",
  "position": "",
  "last_updated": "",
  "layer3_mind": {
    "hunger_index": 0,
    "hunger_factors": [],
    "distraction_index": 0,
    "distraction_flags": [],
    "silence_bonus": false
  },
  "layer4_personality": {
    "inferred_mbti": "",
    "confidence": "",
    "behavioral_signals": [],
    "last_updated": ""
  },
  "layer5_relationships": [],
  "practice_log": [],
  "news_log": []
}
```

### predictions.json
```json
{
  "predictions": [{
    "game_id": "",
    "date": "",
    "week": 0,
    "season": 0,
    "home_team": "",
    "away_team": "",
    "modifiers_applied": {},
    "prediction": {
      "spread_pick": "",
      "over_under_pick": "",
      "moneyline_pick": "",
      "confidence": 0,
      "primary_reasoning": [],
      "hypothesis_modifiers": [],
      "blind_spots": [],
      "flip_conditions": []
    },
    "outcome": null,
    "post_mortem": null
  }]
}
```

### relationships.json
```json
{
  "relationships": [{
    "player_a": "",
    "player_b": "",
    "type": "friend|rival|mentor|beef|former_teammate|college_bond",
    "same_team": false,
    "source": "",
    "timestamp": "",
    "notes": "",
    "matchup_modifier": 0
  }]
}
```

---

## Modifier Weight Table (starting hypotheses — all unvalidated until data proves otherwise)

| Modifier | Starting Weight | Status | Min Data Points |
|----------|----------------|--------|-----------------|
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

---

## Phase Roadmap

### Phase 1 — Foundation
- [ ] GitHub repo
- [x] requirements.txt
- [x] data/ folder + all JSON files initialized
- [x] scripts/fetch_news.py — daily team + player news scan
- [x] scripts/update_ratings.py — nflverse base ratings layer 1 + 2
- [x] scripts/fetch_odds.py — twice weekly odds + line movement
- [x] scripts/record_outcome.py — close bets, P&L, modifier accuracy
- [x] data/ledger.json — dual tracking flat + confidence weighted
- [x] .github/workflows/daily_news.yml
- [x] .github/workflows/weekly_ratings.yml
- [x] .github/workflows/fetch_odds.yml
- [ ] index.html — predictions grid
- [ ] components/nav.js
- [ ] pages/methodology.html
- [ ] pages/legal.html

### Phase 2 — Player Intelligence
- [ ] scripts/fetch_practice.py — practice report scraper
- [ ] scripts/fetch_weather.py — Open-Meteo per game location
- [ ] scripts/fetch_lines.py — Odds API Vegas lines
- [ ] players.json populated with layer 3 + 4 + 5 data
- [ ] pages/players.html — individual player cards
- [ ] pages/teams.html — team chemistry dashboard

### Phase 3 — Prediction Engine
- [ ] scripts/predict.py — full 12 layer prediction generator
- [ ] scripts/record_outcome.py — post game logging + post mortem
- [ ] predictions.json live
- [ ] outcomes.json live
- [ ] pages/predictions.html — full prediction detail
- [ ] pages/ledger.html — full history
- [ ] .github/workflows/game_week.yml
- [ ] .github/workflows/post_game.yml

### Phase 4 — Analytics + Learning
- [ ] stats.json populated by record_outcome.py
- [ ] Modifier accuracy tracking live
- [ ] scripts/update_blog.py
- [ ] components/blog-engine.js
- [ ] pages/stats.html — which modifiers actually work
- [ ] pages/findings.html — validated vs hypothesis
- [ ] pages/blog.html

### Phase 5 — README + Launch
- [ ] README.md — origin story, full methodology summary
- [ ] CHANGELOG.md
- [ ] Open questions resolved or documented

---

## Open Questions
- [ ] Practice report source — DECIDED: ESPN injury API (free, JSON) as primary, NFL.com via Bright Data as secondary when ESPN breaks, Pro Football Reference as fallback. Bright Data setup deferred to Phase 2 when fetch_practice.py is being built.
- [ ] Best free source for roster relationship data (beat reporters, social media)
- [ ] nflreadpy vs direct parquet download — which is faster for weekly pulls
- [ ] Personality inference confidence threshold — when do we have enough behavioral data
- [ ] How do we handle mid-season trades — player carries his scores to new team
- [ ] Preseason data — include or exclude from base ratings
- [ ] How do we score expansion of a player's role (new OC, new scheme fit)

---

## Contributions This System Makes
1. Hunger Index — adversity as a quantified performance modifier
2. Distraction Index — life events as performance predictors
3. Silence bonus — absence of news as a positive signal
4. Personality compatibility matrix — inferred MBTI applied to unit chemistry
5. Relationship web — personal connections indexed and applied to matchups
6. Private vs public accountability as coach scoring variable
7. Practice report trajectory (Wed/Thu/Fri) as more predictive than final designation
8. Flip conditions — what would change our prediction before kickoff
9. Modifier validation framework — hypothesis vs evidence, minimum data points
10. Humility layer — blind spots documented in every prediction
11. Anti-bias checks — narrative trap detector + recency bias protection
12. Year one as research dataset — wrong predictions with reasoning are the product

---

*"He'd be workin' on this shit day and night. There was nothin' about a game he was gonna bet that he didn't know."*

*Last updated: PLAN.md v1.0 — 12 layer system defined, ready to build*
*Next: Phase 1 — Foundation*
