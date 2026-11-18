"""
predict.py — Ace's High Prediction Engine
Runs on each odds fetch (Friday opening + Sunday closing).
Scores both teams across available layers, calculates confidence, picks a side.
"""

import json
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# NFL team name → slug mapping (matches news.json and ESPN CDN)
TEAM_SLUG = {
    "Arizona Cardinals": "ari", "Atlanta Falcons": "atl", "Baltimore Ravens": "bal",
    "Buffalo Bills": "buf", "Carolina Panthers": "car", "Chicago Bears": "chi",
    "Cincinnati Bengals": "cin", "Cleveland Browns": "cle", "Dallas Cowboys": "dal",
    "Denver Broncos": "den", "Detroit Lions": "det", "Green Bay Packers": "gb",
    "Houston Texans": "hou", "Indianapolis Colts": "ind", "Jacksonville Jaguars": "jax",
    "Kansas City Chiefs": "kc", "Las Vegas Raiders": "lv", "Los Angeles Chargers": "lac",
    "Los Angeles Rams": "lar", "Miami Dolphins": "mia", "Minnesota Vikings": "min",
    "New England Patriots": "ne", "New Orleans Saints": "no", "New York Giants": "nyg",
    "New York Jets": "nyj", "Philadelphia Eagles": "phi", "Pittsburgh Steelers": "pit",
    "San Francisco 49ers": "sf", "Seattle Seahawks": "sea", "Tampa Bay Buccaneers": "tb",
    "Tennessee Titans": "ten", "Washington Commanders": "wsh",
}

# nflverse team abbreviation → slug
ABBR_TO_SLUG = {
    "ARI": "ari", "ATL": "atl", "BAL": "bal", "BUF": "buf", "CAR": "car",
    "CHI": "chi", "CIN": "cin", "CLE": "cle", "DAL": "dal", "DEN": "den",
    "DET": "det", "GB": "gb", "HOU": "hou", "IND": "ind", "JAX": "jax",
    "KC": "kc", "LV": "lv", "LAC": "lac", "LA": "lar", "MIA": "mia",
    "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg", "NYJ": "nyj",
    "PHI": "phi", "PIT": "pit", "SF": "sf", "SEA": "sea", "TB": "tb",
    "TEN": "ten", "WAS": "wsh",
}

# Weights — all hypothesis until 10+ data points validate them
WEIGHTS = {
    "body":          0.20,
    "skill":         0.30,
    "hunger":        0.10,
    "silence_bonus": 0.10,
    "injury_flag":  -0.15,  # penalty
    "distraction":  -0.10,  # penalty (placeholder, 0 until layer 3 built)
    "line_value":    0.20,  # how much our score disagrees with the market
}


def load(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def build_team_index(players):
    """Build slug → list of players lookup."""
    index = {}
    for p in players:
        slug = ABBR_TO_SLUG.get(p.get('team', ''))
        if slug:
            index.setdefault(slug, []).append(p)
    return index


# Positions that anchor a team's performance — injuries here hurt most
KEY_POSITIONS = {'QB', 'WR', 'RB', 'TE', 'DL', 'LB', 'DB', 'DE', 'DT', 'CB', 'S'}
STARTER_SNAP_THRESHOLD = 0.40  # 40%+ snap share = meaningful contributor


def _starter_weight(p):
    """Weight a player by snap% — starters dominate, depth barely registers."""
    snap = (p.get('layer1_body') or {}).get('snap_pct') or 0.0
    return max(snap, 0.05)  # floor so everyone counts a little


def team_body_score(players_on_team):
    """Snap-weighted body score — starters dominate."""
    total_w, total_s = 0.0, 0.0
    for p in players_on_team:
        score = (p.get('layer1_body') or {}).get('body_score')
        if score is None:
            continue
        w = _starter_weight(p)
        total_s += score * w
        total_w += w
    return round(total_s / total_w, 1) if total_w else 50.0


def team_skill_score(players_on_team):
    """
    Snap-weighted skill score using only stat-derived scores for key positions.
    Fallback scores (ol_proxy, fallback) get half weight so they inform
    without drowning out real EPA/percentile data.
    """
    total_w, total_s = 0.0, 0.0
    for p in players_on_team:
        l2 = p.get('layer2_skill') or {}
        score = l2.get('skill_score')
        if score is None:
            continue
        source = l2.get('source', 'stat')  # 'fallback', 'ol_proxy', 'ls_proxy', or None
        w = _starter_weight(p)
        # Halve weight for proxy/fallback scores so real stats dominate
        if source in ('fallback', 'ol_proxy', 'ls_proxy'):
            w *= 0.5
        total_s += score * w
        total_w += w
    return round(total_s / total_w, 1) if total_w else 50.0


def team_hunger_score(players_on_team):
    """Snap-weighted hunger — starters' chip matters more than depth."""
    total_w, total_s = 0.0, 0.0
    for p in players_on_team:
        seed = (p.get('draft') or {}).get('hunger_seed')
        if seed is None:
            continue
        w = _starter_weight(p)
        total_s += seed * w
        total_w += w
    return round(total_s / total_w, 1) if total_w else 50.0


def team_injury_flag(players_on_team):
    """
    Weighted injury penalty 0-100 based on who is Out/Doubtful.
    QB out = massive hit. Backup LS out = barely registers.
    Returns a 0-100 penalty score (higher = worse injury situation).
    """
    penalty = 0.0
    for p in players_on_team:
        inj = p.get('injury') or {}
        status = (str(inj.get('report_status') or '')).lower()
        if status not in ('out', 'doubtful'):
            continue
        pos  = (p.get('position') or '').upper()
        snap = (p.get('layer1_body') or {}).get('snap_pct') or 0.0
        skill = ((p.get('layer2_skill') or {}).get('skill_score') or 50.0) / 100.0
        # Base penalty: snap% × skill level × position multiplier
        pos_mult = 2.5 if pos == 'QB' else 1.5 if pos in KEY_POSITIONS else 0.5
        penalty += snap * skill * pos_mult * 100.0
    # Cap at 100, normalize so a single star QB out ≈ 60-70 penalty
    return round(min(100.0, penalty), 1)


def get_news_modifiers(slug, news_index):
    """Returns (silence_bonus, distraction_flag) for a team slug."""
    team_news = news_index.get(slug, {})
    silence = 1 if team_news.get('silence_bonus') else 0
    distraction = 1 if (team_news.get('flags') or {}).get('distraction') else 0
    return silence, distraction


# Normalization bounds — set from first full run, updated each season
# These represent the realistic min/max composite before normalization
NORM_MIN = 20.0
NORM_MAX = 75.0


def normalize(score, lo=NORM_MIN, hi=NORM_MAX):
    """Stretch raw composite into full 0-100 range."""
    if hi == lo:
        return 50.0
    return round(max(0.0, min(100.0, (score - lo) / (hi - lo) * 100.0)), 1)


def raw_team_score(slug, team_index, news_index):
    """
    Compute a 0-100 normalized score for a team.
    Returns dict with component breakdown.
    """
    players = team_index.get(slug, [])
    body    = team_body_score(players)
    skill   = team_skill_score(players)
    hunger  = team_hunger_score(players)
    injury  = team_injury_flag(players)   # now 0-100 penalty score
    silence, distraction = get_news_modifiers(slug, news_index)

    # Weighted composite — injury is now a graduated 0-100 penalty
    raw = (
        body    * WEIGHTS['body'] +
        skill   * WEIGHTS['skill'] +
        hunger  * WEIGHTS['hunger'] +
        silence * 100 * WEIGHTS['silence_bonus'] +
        injury  * WEIGHTS['injury_flag'] +        # injury already 0-100, weight is negative
        distraction * 100 * WEIGHTS['distraction']
    )
    raw = max(0.0, min(100.0, raw))

    # Normalize to spread the field across full 0-100 range
    composite = normalize(raw)

    return {
        "composite":        round(composite, 1),
        "raw":              round(raw, 1),
        "body":             round(body, 1),
        "skill":            round(skill, 1),
        "hunger":           round(hunger, 1),
        "injury_penalty":   round(injury, 1),
        "silence_bonus":    bool(silence),
        "injury_flag":      injury > 0,
        "distraction_flag": bool(distraction),
        "player_count":     len(players),
    }


def spread_to_implied_edge(spread, home_score, away_score):
    """
    Compare our score differential to the market spread.
    Returns a line_value modifier: positive = we like the favorite more than market,
    negative = we like the underdog.
    """
    our_diff = home_score - away_score  # positive = home team better
    # Market spread: negative means home is favored by that many points
    # e.g. spread = -7.0 means home favored by 7
    market_diff = -spread  # convert to "home advantage in points"

    # Normalize: every 3 points of disagreement = ~10 points of edge score
    edge = (our_diff - market_diff) / 3.0 * 10.0
    return max(-30.0, min(30.0, edge))


def confidence_from_edge(edge):
    """Map edge score to confidence 0-100."""
    # Edge of 0 = 50 confidence (coin flip)
    # Edge of ±30 = 80 or 20 confidence
    return max(0, min(100, round(50 + edge)))


def pick_side(home_team, away_team, home_score, away_score, spread):
    """
    Decide which side to pick against the spread.
    Returns (pick_team, pick_type) where pick_type is 'favorite' or 'underdog'.
    """
    # spread < 0 means home is favored
    home_favored = spread <= 0
    our_home_edge = home_score - away_score

    if home_favored:
        if our_home_edge > 3:
            return home_team, "favorite"
        else:
            return away_team, "underdog"
    else:
        if our_home_edge < -3:
            return away_team, "favorite"
        else:
            return home_team, "underdog"


def predict_game(game, team_index, news_index):
    """Generate a prediction for a single game."""
    home = game['home_team']
    away = game['away_team']
    home_slug = TEAM_SLUG.get(home)
    away_slug = TEAM_SLUG.get(away)

    if not home_slug or not away_slug:
        return None

    home_data = raw_team_score(home_slug, team_index, news_index)
    away_data = raw_team_score(away_slug, team_index, news_index)

    spread = game['consensus'].get('spread') or 0.0
    edge = spread_to_implied_edge(spread, home_data['composite'], away_data['composite'])
    confidence = confidence_from_edge(edge)

    pick, pick_type = pick_side(home, away, home_data['composite'], away_data['composite'], spread)

    # Determine week from commence_time (rough: week 1 = Sep 4 2026)
    try:
        game_dt = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
        season_start = datetime(2026, 9, 3, tzinfo=timezone.utc)
        week = max(1, min(18, int((game_dt - season_start).days / 7) + 1))
    except Exception:
        week = 1

    return {
        "game_id": game['game_id'],
        "week": week,
        "home_team": home,
        "away_team": away,
        "home_slug": home_slug,
        "away_slug": away_slug,
        "game_time": game['commence_time'],
        "spread": spread,
        "total": game['consensus'].get('total'),
        "pick": pick,
        "pick_type": pick_type,
        "confidence": confidence,
        "edge_score": round(edge, 1),
        "home_score": home_data['composite'],
        "away_score": away_data['composite'],
        "home_breakdown": home_data,
        "away_breakdown": away_data,
        "snapshot_type": game.get('snapshot_type', 'opening'),
        "line_movement": game.get('line_movement'),
        "status": "open",
        "result": None,
        "lesson": None,
        "predicted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        # Placeholders for Phase 2 layers
        "modifiers_applied": {
            "practice_trajectory": None,
            "mbti_adjustment": None,
            "coach_compatibility": None,
            "relationship_web": None,
        }
    }


def main():
    import sys
    reset = '--reset' in sys.argv

    odds_data = load('odds.json')
    players_data = load('players.json')
    news_data = load('news.json')
    existing = load('predictions.json')
    metadata = load('metadata.json')

    # Build indexes
    team_index = build_team_index(players_data['players'])
    news_index = {t['team_slug']: t for t in news_data['news']}

    # Track existing game_ids to avoid duplicates (skip if reset)
    existing_ids = set() if reset else {p['game_id'] for p in existing.get('predictions', [])}
    base_predictions = [] if reset else existing.get('predictions', [])

    new_predictions = []
    for game in odds_data.get('games', []):
        if game['game_id'] in existing_ids:
            # Update line movement if closing snapshot
            if game.get('snapshot_type') == 'closing':
                for p in existing['predictions']:
                    if p['game_id'] == game['game_id']:
                        p['line_movement'] = game.get('line_movement')
                        p['closing_spread'] = game['consensus'].get('spread')
            continue

        pred = predict_game(game, team_index, news_index)
        if pred:
            new_predictions.append(pred)

    all_predictions = base_predictions + new_predictions

    save('predictions.json', {"predictions": all_predictions})

    # Update metadata
    metadata['last_prediction'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    metadata['week'] = new_predictions[0]['week'] if new_predictions else metadata.get('week')
    save('metadata.json', metadata)

    print(f"Generated {len(new_predictions)} new predictions. Total: {len(all_predictions)}")
    for p in new_predictions:
        flag = "BET" if p['confidence'] >= 40 else "skip"
        print(f"  {flag} | Week {p['week']} | {p['away_team']} @ {p['home_team']} | Pick: {p['pick']} | Conf: {p['confidence']}")


if __name__ == '__main__':
    main()
