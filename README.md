![](assets/img/grey.gif)
> *"He'd find out the kind of inside stuff nobody else knew, and that's what he'd put his money on."*
> — Nicky, Casino

A human performance intelligence system that uses NFL football as its dataset.

Layer 1 and 2 everyone has. Layers 3–12 are ours.
Free to build. Free to use. Gets smarter every single week.

**[Live Site →](https://shannon-goddard.github.io/aces-high/)**

---

## What Is This

Aces High is not a picks site. It's not a stats aggregator. It's a structured attempt to quantify the soft signals that Vegas doesn't price in — personality compatibility, role fit, unit cohesion, relationship webs, coach market fit, hunger, distraction, silence.

The thesis: the market prices talent well. It prices human dynamics poorly. That's the edge.

Every modifier starts as a hypothesis. It earns its weight through outcomes or gets cut. Year one is not about winning — it's about documenting everything so year two is smarter. Wrong predictions with honest reasoning attached are more valuable than lucky right ones.

---

## The 12-Layer System

The architecture is a layered intelligence stack. Each layer adds a dimension of signal. Lower layers are objective (body, stats). Higher layers are behavioral and relational. The system is designed so layers can be validated independently — a modifier that doesn't move the needle gets cut.

| Layer | Name | Status | What It Measures |
|-------|------|--------|-----------------|
| 1 | Body | ✅ Live | Age, weight, snap%, career stage, combine athleticism |
| 2 | Skill | ✅ Live | Position-ranked stats, EPA, momentum (rolling 3-week) |
| 3 | Mind / Hunger | ✅ Live | Draft seed as adversity proxy, UDFA flag, contract year |
| 3 | Mind / Distraction | ✅ Live | News scan flags — injury, distraction, silence bonus |
| 4 | Personality | ✅ Live | MBTI inferred for all 3,216 players + 96 coaches |
| 4 | Personality / Compat | ✅ Live | Team compat score — QB↔HC double-weighted |
| 4 | Personality / Role Fit | ✅ Live | Position demand scoring, veteran drain multiplier |
| 5 | Relationships | ✅ Live | Former pro + college teammate edges, sentiment overlay |
| 6 | Unit Chemistry | ✅ Live | OL/secondary/LB/WR/DL cohesion scored by seasons together |
| 7 | Matchup | ⬜ Next Season | Direct position matchup scoring (QB vs DB, OL vs DL) |
| 8 | Prediction | ✅ Live | Full modifier stack → confidence score → pick |
| 9 | Outcome | ✅ Built | record_outcome.py closes bets, writes to outcomes.json |
| 10 | Learning | ✅ Live | Auto-blog from prediction + outcome pairs |
| 11 | Humility | ✅ Live | Blind spots + flip conditions in every prediction |
| 12 | Anti-Bias | ⬜ Next Season | Narrative trap detector, recency bias protection |

---

## How The Score Is Built

Every prediction runs both teams through `raw_team_score()` in `predict.py`. Here's the exact formula:

```
raw = (
    body_score          × 0.15  +
    adjusted_skill      × 0.20  +
    momentum_score      × 0.10  +
    hunger_score        × 0.10  +
    silence_bonus       × 0.10  +
    injury_penalty      × -0.15 +
    distraction_flag    × -0.10
) × compat_mult × role_fit_mult × cohesion_mult × hc_market_mult
```

The four personality multipliers stack multiplicatively — they don't replace talent, they modify how talent expresses under pressure.

### The Multiplier Stack

| Multiplier | Formula | Range | What It Captures |
|------------|---------|-------|-----------------|
| `compat_mult` | `1 + (team_compat - 50) / 500` | ×0.90 – ×1.10 | MBTI compatibility across the communication chain |
| `role_fit_mult` | `1 + avg(base_mod × drain_mult)` | ×0.90 – ×1.10 | Position demands vs player personality type |
| `cohesion_mult` | `1 + (avg_cohesion - 50) / 1000` | ×0.95 – ×1.05 | Unit cohesion by seasons together |
| `hc_market_mult` | `1 + (market_fit - 50) / 1667` | ×0.97 – ×1.03 | Introvert HC in high-media market pays structural drain |

### The Veteran Drain Multiplier

This is one of the most original pieces in the system. A Poor Fit player *can* perform — but it costs more energy, and that cost compounds over time.

```python
base_mod   = (role_fit_score - 50.0) / 1000.0   # ±5% max per player
drain_mult = 1.0 + min(0.5, years_exp / 20.0)   # scales to 1.5× at 10+ years
player_mod = base_mod * drain_mult
```

A year-1 Poor Fit QB takes a small penalty. A year-8 Poor Fit QB takes a 1.4× amplified penalty. The same compounding applies in reverse for Best Fit veterans — mastery deepens.

**Example — KC 2026:**
- Mahomes (QB, 7yr, role fit: 100) → drain 1.35× → mod +0.0675
- Kelce (TE, 11yr, role fit: 100) → drain 1.50× → mod +0.0750
- J. Reid (DB, 6yr, role fit: 0) → drain 1.30× → mod −0.0650
- KC combined mult: **1.0402** (+4% on raw score)

---

## Personality Layer (L4)

3,216 players. No surveys. Pure behavioral inference from career data.

### MBTI Inference Method

| Axis | Signal Source |
|------|--------------|
| I/E | Career longevity + snap consistency — introverts sustain longer, extroverts peak early |
| S/N | Position archetype + college program type — system players vs playmakers |
| T/F | Draft slot vs performance delta — overperformers trend T, underperformers trend F |
| J/P | Snap trend consistency — steady J, volatile P |

Same method applied to all 96 coaches (32 HC + OC/DC per team) using PFR records and press conference behavioral signals.

### Communication Chain

Compat scoring follows the actual communication structure of football — not just "same team":

| Position | Talks To | Coach Chain |
|----------|----------|-------------|
| QB | WR, TE, RB, OL | HC (direct) + OC |
| WR / TE / RB | QB | OC |
| OL | QB, RB | OC |
| LB | DL, DB | HC (direct) + DC |
| DB | LB, DB | DC |
| DL | LB | DC |

QB↔HC is double-weighted in the team compat score. It's the highest-leverage relationship on any roster.

---

## Relationship Web (L5)

`relationships.json` is the source of truth. `players.json` holds IDs only.

Edges are built from nflverse — no external API needed:

- **Pro teammate edges**: same team + overlapping seasons (3-year window) + same unit (offense/defense)
- **College teammate edges**: same college + entry year within ±3 years (prevents Alabama 2010 connecting to Alabama 2026)
- **Same-draft-class dropped**: 250 guys drafted the same year is structural noise, not signal

**Strength scoring**: `40 base + 5/season together (max 25) + 10 same unit + 10 college bonus`

**Sentiment overlay**: starts neutral. Daily news scan flips edges to positive/negative when keywords fire on a team. Team-level granularity is the current conservative approach — player-level targeting is next season once the signal proves out.

**Facing former team**: derived at prediction time in `predict.py`, not stored as a static edge. Avoids stale data.

---

## Unit Chemistry (L6)

Groups active players by team + position unit. Scores each unit 0–100:

```
unit_score = 40 (base)
           + avg seasons together × 3 (max +30)
           + core stability bonus (+10 if 3+ players with 2+ seasons, +20 if 5+)
```

Units scored: OL, secondary (DB/CB/S), LB corps, WR corps, DL corps.

The cohesion multiplier is capped at ±5% — smaller than compat/role fit (±10%) because unit cohesion is real but subtle. It earns a larger weight when outcomes validate it.

---

## The Automated Pipeline

The system runs itself. No manual intervention required during the season.

```
.github/workflows/
├── daily_news.yml         — runs every day, scans ESPN RSS for all 32 teams
├── weekly_ratings.yml     — runs weekly:
│                            update_ratings.py → infer_personality.py
│                            → fetch_coaches.py → fetch_relationships.py
├── fetch_odds.yml         — runs twice weekly (opening + closing lines)
├── practice_reports.yml   — runs Wed/Thu/Fri in season
└── record_outcomes.yml    — closes bets, writes outcomes, triggers blog
```

### Data Flow

```
nflverse CSV → update_ratings.py → players.json (L1 + L2)
                                 → infer_personality.py → players.json (L4)
                                 → fetch_relationships.py → relationships.json (L5 + L6)

ESPN RSS → fetch_news.py → news.json (flags + sentiment overlay)

The Odds API → fetch_odds.py → odds.json → predict.py → predictions.json

Open-Meteo → fetch_weather.py → weather.json → predict.py

Practice reports → fetch_practice.py → practice.json → predict.py
```

---

## Project Structure

```
aces-high/
├── scripts/
│   ├── predict.py              — the engine: full modifier stack, picks, confidence
│   ├── fetch_news.py           — daily ESPN RSS scan, keyword flags, sentiment overlay
│   ├── fetch_relationships.py  — L5 relationship edges + L6 unit cohesion scores
│   ├── infer_personality.py    — L4 MBTI inference for all 3,216 players
│   ├── fetch_coaches.py        — 96 coaches, PFR records, MBTI, playing career
│   ├── update_ratings.py       — weekly nflverse pull, L1 + L2 + momentum
│   ├── fetch_odds.py           — opening + closing lines, line movement
│   ├── fetch_practice.py       — Wed/Thu/Fri practice reports
│   ├── fetch_weather.py        — Open-Meteo, passing/kicker modifiers
│   ├── fetch_scores.py         — game scores
│   ├── record_outcome.py       — closes bets, writes outcomes + lessons
│   ├── update_blog.py          — auto-generates blog posts from closed predictions
│   └── backtest.py             — retroactive predictions across 2020–2024, writes backtest.json
│
├── data/
│   ├── players.json            — 3,216 players, L1+L2+L4+L5+L6 complete
│   ├── coaches.json            — 96 coaches, MBTI + playing career + market fit
│   ├── relationships.json      — all pro + college teammate edges
│   ├── predictions.json        — live predictions with full breakdown
│   ├── news.json               — daily scans, flags per team
│   ├── practice.json           — Wed/Thu/Fri trajectory per player
│   ├── odds.json               — opening + closing lines
│   ├── weather.json            — game-level weather modifiers
│   ├── outcomes.json           — closed bets (populates as season progresses)
│   ├── ledger.json             — open/closed bets, P&L
│   ├── modifiers.json          — modifier weights + hypothesis status
│   ├── backtest.json           — 2020–2024 retroactive results, 1,343 games
│   └── metadata.json           — week, season, scan timestamps
│
├── pages/
│   ├── predictions.html        — accordion per game, clickable drill-down modals
│   ├── edge-report.html        — best bets / active bets / stay away / skip
│   ├── players.html            — player cards: L1+L2+L4+L6, compat panel, role fit
│   ├── coaches.html            — 32-team grid, HC↔player compat web
│   ├── teams.html              — 32-team grid, detail panel, stat modals
│   ├── ledger.html             — open/closed bets, P&L tracking
│   ├── findings.html           — 22+ modifiers tracked, hypothesis vs validated
│   ├── methodology.html        — full system explanation
│   ├── stats.html              — calibration dashboard (populates with outcomes)
│   ├── backtest.html           — 2020–2024 retroactive results, year selector, game-by-game
│   └── blog.html               — auto-generated posts from closed predictions
│
├── .github/workflows/          — 5 automated GitHub Actions
├── assets/                     — styles, images
├── PLAN.md                     — living architecture document
└── CHANGELOG.md
```

---

## The Stack (All Free)

| Tool | Purpose |
|------|---------|
| nflverse (nflreadpy) | Base player stats — referenced, not archived |
| ESPN RSS | Daily news headlines for all 32 teams |
| Open-Meteo API | Weather — no key required |
| The Odds API (free tier) | Vegas lines, opening + closing |
| GitHub Actions | Full pipeline automation |
| GitHub Pages | Hosting |
| Vanilla JS | Frontend — no framework |

Zero paid APIs. Zero frameworks. The whole system runs on free infrastructure.

---

## Modifier Validation Framework

Every modifier in the system has a status: **Hypothesis** or **Validated**.

A modifier needs 10+ data points before it can be promoted to Validated. This prevents recency bias from corrupting weights. The goal in year one is not to win — it's to document everything so year two is smarter.

Current status: all 22+ modifiers are Hypothesis. First closed outcomes will start moving the needle.

The `findings.html` page tracks every modifier: what it predicts, data points collected, win rate when fired, current status. It auto-populates from `stats.json` as outcomes accumulate.

---

## What Makes This Different

Most prediction systems stop at talent. This one goes further:

1. **Hunger Index** — adversity as a quantified performance modifier (draft seed, UDFA flag, contract year)
2. **Distraction Index** — life events as performance predictors, not just injury reports
3. **Silence bonus** — absence of news as a positive signal (locked in, no drama)
4. **Practice trajectory** — Wed/Thu/Fri arc is more predictive than the final designation
5. **Personality compatibility** — inferred MBTI applied to the actual communication chain
6. **Role fit sustainability** — position demands vs player type, not just talent vs talent
7. **Veteran drain** — misfit compounds over career length, mastery compounds too
8. **Coach market fit** — an introverted HC in a high-media market pays a structural energy tax
9. **Unit cohesion** — OL/secondary/LB groups scored by seasons together, not just personnel
10. **Relationship web** — former pro/college teammate edges cross team lines and affect performance
11. **Divisional familiarity** — second matchup tightens, the underdog has film now
12. **Scheme transition** — new coordinator means role fit score is temporarily invalid
13. **Snap% drop early warning** — losing snaps without a report is a signal the data knows first
14. **Flip conditions** — every prediction documents what would change our mind before kickoff
15. **Humility layer** — blind spots documented in every prediction, never hidden

---

## Philosophy

> *Every wrong prediction with honest reasoning attached is more valuable than a lucky right one.*

The system is designed to be wrong in useful ways. When a prediction closes wrong, `record_outcome.py` captures what fired vs what the game actually showed. That lesson feeds back into the modifier validation framework. The system gets smarter by being honest about its misses.

Year one is the research dataset. Year two is where it starts to compound.

---

## What's Next

These are ready to build but blocked on outcome data:

- **Layer 7 — Direct Position Matchup Scoring**: QB skill vs opposing DB, OL pass protection vs DL pass rush. Significant architecture change to `predict.py` — needs a calibration baseline first.
- **Layer 12 — Anti-Bias Narrative Trap Detector**: Flags when a prediction is driven by narrative rather than data. Needs 50+ closed predictions to see where narrative traps appear in our own misses.
- **Player Name Extraction**: Upgrade team-level sentiment targeting to player-level. Blocked on outcome data showing whether team-level sentiment is moving the needle at all.
- **Backtest year-over-year trend analysis**: The 2020–2024 backtest shows consistent improvement each season (63% → 72% SU). Once live 2026 outcomes accumulate, compare live accuracy against the backtest baseline to validate whether the system is performing as expected or drifting.

---

## Built With

This project was built in close collaboration with **[Amazon Q Developer](https://aws.amazon.com/q/developer/)** — AWS's AI coding assistant, running directly in the IDE.

This wasn't "AI generated code." It was a genuine back-and-forth architecture session. Amazon Q contributed:

- **Layer architecture decisions** — the 12-layer framework, what belongs in each layer, what order to build them, why the wrong order means building on sand
- **Scoring formula design** — the multiplicative vs additive decision for personality modifiers, why compat doesn't replace talent but modifies how it expresses under pressure
- **The veteran drain multiplier** — the insight that misfit compounds over time, and that the same compounding applies in reverse for Best Fit veterans
- **Communication chain structure** — mapping compat scoring to the actual football communication structure (QB talks to WR/TE/RB/OL, not to the DC)
- **Relationship web architecture** — Option B design (relationships.json as source of truth, players.json holds IDs only), the college entry-year window fix, why same-draft-class is noise
- **Unit cohesion scoring formula** — base + seasons together + stability bonus, why it's capped at ±5% until outcomes validate it
- **The sentiment overlay approach** — why team-level granularity is the correct conservative starting point, what player-level targeting requires before it's worth building
- **Pipeline sequencing** — why `update_ratings → infer_personality → fetch_coaches → fetch_relationships` is the only correct order
- **The humility layer** — blind spots and flip conditions as first-class data, not afterthoughts
- **Every script, every data structure, every GitHub Actions workflow** — written together, line by line
- **The backtest** — the idea to run the full modifier stack against 5 seasons of historical data came out of a live session. 1,343 games. The trend line (63% → 72% SU, improving every year) wasn't expected — it emerged from the data and reframed what the personality/compat layer is actually doing. That conversation is documented in the commit history.

The human brought the vision, the football knowledge, the "inside stuff" philosophy, and the stories. Amazon Q brought the architecture, the code, and the discipline to build it right.

That's the real stack.

---

*"He'd be workin' on this shit day and night. There was nothin' about a game he was gonna bet that he didn't know."*

*Season 2026 — L1+L2+L3+L4+L5+L6 live. Pipeline runs itself. Backtest shows 63%→72% SU improvement across 2020–2024. Next real build session starts after the first few weeks of closed outcomes.*
<p align="center">
  <img src="assets\img\a-h-gold.png" alt="logo" width="100">
</p>  
