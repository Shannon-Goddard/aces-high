"""
backtest.py — retroactive prediction test across multiple seasons.
Uses current players.json (2024 rosters) + nflreadpy historical schedules.
Runs the full modifier stack, picks a winner, closes immediately against actual scores.
News/injury flags default to neutral — labeled as such in output.
Writes data/backtest.json keyed by season.

Usage:
  python scripts/backtest.py              # runs all SEASONS
  python scripts/backtest.py 2023 2024    # runs specific seasons only
"""

import json
import os
import sys
import nflreadpy as nfl

sys.path.insert(0, os.path.dirname(__file__))
from predict import (
    build_team_index, raw_team_score, pick_side,
    spread_to_implied_edge, confidence_from_edge,
    apply_divisional_modifier, get_divisional_flags,
    ABBR_TO_SLUG, TEAM_SLUG,
)

DATA_DIR      = os.path.join(os.path.dirname(__file__), '..', 'data')
SLUG_TO_NAME  = {v: k for k, v in TEAM_SLUG.items()}
NFLVERSE_ABBR = {**ABBR_TO_SLUG, "WAS": "wsh", "LA": "lar"}
SEASONS       = [2020, 2021, 2022, 2023, 2024]


def load(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def abbr_to_full(abbr):
    slug = NFLVERSE_ABBR.get(abbr.upper())
    return SLUG_TO_NAME.get(slug, abbr) if slug else abbr


def determine_result(pick, home_team, away_team, home_score, away_score, spread):
    actual_winner = home_team if home_score > away_score else away_team
    straight_up   = (pick == actual_winner)
    if spread is not None:
        home_covered   = (home_score + spread) > away_score
        spread_correct = home_covered if pick == home_team else not home_covered
    else:
        spread_correct = None
    return straight_up, spread_correct, actual_winner


def run_season(season, reg, team_index, news_index, hc_index):
    results      = []
    skipped      = 0
    season_games = reg[reg['season'] == season]

    for _, row in season_games.iterrows():
        home_abbr = str(row['home_team'])
        away_abbr = str(row['away_team'])
        home_slug = NFLVERSE_ABBR.get(home_abbr.upper())
        away_slug = NFLVERSE_ABBR.get(away_abbr.upper())

        if not home_slug or not away_slug:
            skipped += 1
            continue

        home_name  = abbr_to_full(home_abbr)
        away_name  = abbr_to_full(away_abbr)
        home_score = int(row['home_score'])
        away_score = int(row['away_score'])
        spread     = float(row['spread_line']) if row['spread_line'] is not None else None
        week       = int(row['week'])
        game_id    = str(row['game_id'])
        gameday    = str(row['gameday'])

        home_data = raw_team_score(home_slug, team_index, news_index, hc_index=hc_index)
        away_data = raw_team_score(away_slug, team_index, news_index, hc_index=hc_index)

        use_spread = spread if spread is not None else 0.0
        edge       = spread_to_implied_edge(use_spread, home_data['composite'], away_data['composite'])
        confidence = confidence_from_edge(edge)

        pick, pick_type = pick_side(
            home_name, away_name,
            home_data['composite'], away_data['composite'],
            use_spread
        )

        divisional, rematch = get_divisional_flags(home_slug, away_slug, results, game_id)
        edge, _    = apply_divisional_modifier(edge, pick_type, divisional, rematch)
        confidence = confidence_from_edge(edge)

        su_correct, spread_correct, actual_winner = determine_result(
            pick, home_name, away_name, home_score, away_score, spread
        )

        results.append({
            "game_id":        game_id,
            "season":         season,
            "week":           week,
            "gameday":        gameday,
            "home_team":      home_name,
            "away_team":      away_name,
            "home_slug":      home_slug,
            "away_slug":      away_slug,
            "home_score":     home_score,
            "away_score":     away_score,
            "spread":         spread,
            "pick":           pick,
            "pick_type":      pick_type,
            "confidence":     confidence,
            "edge_score":     round(edge, 1),
            "home_composite": home_data['composite'],
            "away_composite": away_data['composite'],
            "actual_winner":  actual_winner,
            "su_correct":     su_correct,
            "spread_correct": spread_correct,
            "divisional":     divisional,
            "rematch":        rematch,
        })

    return results, skipped


def build_summary(season, results, skipped):
    total      = len(results)
    su_wins    = sum(1 for r in results if r['su_correct'])
    sp_results = [r for r in results if r['spread_correct'] is not None]
    sp_wins    = sum(1 for r in sp_results if r['spread_correct'])

    tiers = {
        'high':   [r for r in results if r['confidence'] >= 70],
        'medium': [r for r in results if 50 <= r['confidence'] < 70],
        'low':    [r for r in results if r['confidence'] < 50],
    }
    tier_stats = {}
    for name, tier in tiers.items():
        t_su   = sum(1 for r in tier if r['su_correct'])
        t_sp   = [r for r in tier if r['spread_correct'] is not None]
        t_sp_w = sum(1 for r in t_sp if r['spread_correct'])
        tier_stats[name] = {
            "games":         len(tier),
            "su_wins":       t_su,
            "su_losses":     len(tier) - t_su,
            "su_pct":        round(t_su / len(tier) * 100, 1) if tier else 0,
            "spread_wins":   t_sp_w,
            "spread_losses": len(t_sp) - t_sp_w,
            "spread_games":  len(t_sp),
            "spread_pct":    round(t_sp_w / len(t_sp) * 100, 1) if t_sp else 0,
        }

    return {
        "season":        season,
        "total_games":   total,
        "skipped":       skipped,
        "su_wins":       su_wins,
        "su_losses":     total - su_wins,
        "su_pct":        round(su_wins / total * 100, 1) if total else 0,
        "spread_wins":   sp_wins,
        "spread_losses": len(sp_results) - sp_wins,
        "spread_pct":    round(sp_wins / len(sp_results) * 100, 1) if sp_results else 0,
        "by_confidence": tier_stats,
        "caveats": [
            "2024 roster used for all seasons — not the actual roster for each year",
            "No injury or news flags applied — all teams treated as healthy/neutral",
            "2026 personality/compat scores applied retroactively to historical games",
        ]
    }


def main():
    seasons_arg = [int(a) for a in sys.argv[1:] if a.isdigit()] or SEASONS
    print(f"backtest.py — seasons: {seasons_arg}")

    players_data = load('players.json')
    coaches_data = load('coaches.json')
    team_index   = build_team_index(players_data.get('players', []))
    hc_index     = {
        c['team_slug']: c
        for c in coaches_data.get('coaches', [])
        if c.get('role') == 'hc'
    }
    news_index = {}  # neutral — no flags

    print(f"Loading schedules from nflreadpy...")
    schedule = nfl.load_schedules(seasons=seasons_arg).to_pandas()
    reg = schedule[
        (schedule['game_type'] == 'REG') &
        schedule['home_score'].notna() &
        schedule['away_score'].notna()
    ].copy()
    print(f"  {len(reg)} completed regular season games across {len(seasons_arg)} season(s)")

    existing     = load('backtest.json')
    seasons_data = existing.get('seasons', {})

    for season in seasons_arg:
        print(f"\nRunning {season}...")
        results, skipped = run_season(season, reg, team_index, news_index, hc_index)
        summary = build_summary(season, results, skipped)
        seasons_data[str(season)] = {"summary": summary, "games": results}

        su  = summary['su_wins']
        tot = summary['total_games']
        sp  = summary['spread_wins']
        spl = summary['spread_losses']
        print(f"  {season}: {su}-{tot-su} SU ({summary['su_pct']}%)  |  {sp}-{spl} spread ({summary['spread_pct']}%)")
        for tier, s in summary['by_confidence'].items():
            print(f"    {tier:8s}: {s['su_wins']}-{s['su_losses']} SU ({s['su_pct']}%)  |  {s['spread_wins']}-{s['spread_losses']} spread ({s['spread_pct']}%)")

    save('backtest.json', {"seasons": seasons_data})
    print(f"\nbacktest.json written — {len(seasons_data)} season(s).")


if __name__ == '__main__':
    main()
