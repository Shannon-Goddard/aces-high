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
    if not os.path.exists(path):
        return {}
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


def team_compat_score(players_on_team):
    """
    Snap-weighted team compat score from layer4_personality.team_compat_score.
    QB compat gets double weight — QB↔HC is the most predictive link.
    Returns 0-100, defaults to 50 (neutral) if no data.
    """
    total_w, total_s = 0.0, 0.0
    for p in players_on_team:
        score = (p.get('layer4_personality') or {}).get('team_compat_score')
        if score is None:
            continue
        w = _starter_weight(p)
        if (p.get('position') or '').upper() == 'QB':
            w *= 2.0   # QB↔HC is the anchor relationship
        total_s += score * w
        total_w += w
    return round(total_s / total_w, 1) if total_w else 50.0



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


def team_injury_flag(players_on_team, practice_index=None):
    """
    Weighted injury penalty 0-100 using practice trajectory when available,
    falling back to report_status from players.json.
    Concern < 25 (trending full / healthy) = no penalty applied.
    """
    if practice_index is None:
        practice_index = {}

    STATUS_FALLBACK = {'out': 85, 'doubtful': 70, 'questionable': 40, 'probable': 15}

    penalty = 0.0
    for p in players_on_team:
        team_slug = ABBR_TO_SLUG.get(p.get('team', ''), '')
        name      = p.get('name', '')
        key       = f"{team_slug}:{name}"

        practice = practice_index.get(key)
        if practice:
            concern = practice.get('practice_score', 0)
        else:
            inj     = p.get('injury') or {}
            status  = (str(inj.get('report_status') or '')).lower()
            concern = STATUS_FALLBACK.get(status, 0)

        if concern < 25:
            continue

        pos   = (p.get('position') or '').upper()
        snap  = (p.get('layer1_body') or {}).get('snap_pct') or 0.0
        skill = ((p.get('layer2_skill') or {}).get('skill_score') or 50.0) / 100.0

        concern_mult = concern / 100.0
        pos_mult     = 2.5 if pos == 'QB' else 1.5 if pos in KEY_POSITIONS else 0.5
        penalty     += snap * skill * pos_mult * concern_mult * 100.0

    return round(min(100.0, penalty), 1)


def get_news_modifiers(slug, news_index):
    """Returns (silence_bonus, distraction_flag) for a team slug."""
    team_news = news_index.get(slug, {})
    silence = 1 if team_news.get('silence_bonus') else 0
    distraction = 1 if (team_news.get('flags') or {}).get('distraction') else 0
    return silence, distraction


def get_weather_modifiers(game_id, weather_index):
    """
    Returns weather modifier dict for a game.
    Defaults to no impact if weather not available.
    """
    entry = weather_index.get(game_id, {})
    mods  = entry.get('modifiers', {})
    return {
        'dome':            mods.get('dome', False),
        'passing_mult':    mods.get('passing_mult', 1.0),
        'kicker_mult':     mods.get('kicker_mult', 1.0),
        'wind_flag':       mods.get('wind_flag', False),
        'precip_flag':     mods.get('precip_flag', False),
        'cold_flag':       mods.get('cold_flag', False),
        'cold_joint_flag': mods.get('cold_joint_flag', False),
        'notes':           mods.get('notes', []),
        'weather':         entry.get('weather'),
    }


def team_chronic_joint_penalty(players_on_team, cold_joint_flag):
    """
    Extra skill penalty for players with chronic_joint_issue=True in cold weather.
    Triggers at temp < 40F. Hypothesis modifier — capped at 50 (less severe than full injury).
    QB with bad shoulder in cold = significant. Depth OL = minimal.
    """
    if not cold_joint_flag:
        return 0.0
    penalty = 0.0
    for p in players_on_team:
        if not p.get('chronic_joint_issue'):
            continue
        pos   = (p.get('position') or '').upper()
        snap  = (p.get('layer1_body') or {}).get('snap_pct') or 0.0
        skill = ((p.get('layer2_skill') or {}).get('skill_score') or 50.0) / 100.0
        pos_mult = 2.0 if pos == 'QB' else 1.3 if pos in KEY_POSITIONS else 0.4
        penalty += snap * skill * pos_mult * 100.0
    return round(min(50.0, penalty), 1)


# Normalization bounds — set from first full run, updated each season
# These represent the realistic min/max composite before normalization
NORM_MIN = 20.0
NORM_MAX = 75.0


def normalize(score, lo=NORM_MIN, hi=NORM_MAX):
    """Stretch raw composite into full 0-100 range."""
    if hi == lo:
        return 50.0
    return round(max(0.0, min(100.0, (score - lo) / (hi - lo) * 100.0)), 1)


def raw_team_score(slug, team_index, news_index, weather_mods=None, practice_index=None):
    """
    Compute a 0-100 normalized score for a team.
    weather_mods:   dict from get_weather_modifiers()
    practice_index: dict from practice.json players keyed by 'slug:name'
    Returns dict with component breakdown.
    """
    if weather_mods is None:
        weather_mods = {'passing_mult': 1.0, 'kicker_mult': 1.0, 'dome': False, 'cold_joint_flag': False}
    if practice_index is None:
        practice_index = {}

    players      = team_index.get(slug, [])
    body         = team_body_score(players)
    skill        = team_skill_score(players)
    hunger       = team_hunger_score(players)
    compat       = team_compat_score(players)
    injury       = team_injury_flag(players, practice_index)
    joint_pen    = team_chronic_joint_penalty(players, weather_mods.get('cold_joint_flag', False))
    silence, distraction = get_news_modifiers(slug, news_index)

    # Weather: passing game takes the hit from wind/precip
    weather_skill_penalty = skill * (1.0 - weather_mods['passing_mult'])
    # Chronic joint: additional skill reduction for flagged players in cold
    adjusted_skill = skill - weather_skill_penalty - (joint_pen * 0.3)
    adjusted_skill = max(0.0, adjusted_skill)

    # Personality compat modifier: (compat - 50) / 500 = ±10% max on raw score
    # Only meaningful when compat deviates from neutral (50)
    compat_mult = 1.0 + (compat - 50.0) / 500.0

    raw = (
        body              * WEIGHTS['body'] +
        adjusted_skill    * WEIGHTS['skill'] +
        hunger            * WEIGHTS['hunger'] +
        silence * 100     * WEIGHTS['silence_bonus'] +
        injury            * WEIGHTS['injury_flag'] +
        distraction * 100 * WEIGHTS['distraction']
    ) * compat_mult
    raw = max(0.0, min(100.0, raw))
    composite = normalize(raw)

    return {
        "composite":          round(composite, 1),
        "raw":                round(raw, 1),
        "body":               round(body, 1),
        "skill":              round(skill, 1),
        "adjusted_skill":     round(adjusted_skill, 1),
        "hunger":             round(hunger, 1),
        "compat":             round(compat, 1),
        "compat_mult":        round(compat_mult, 4),
        "injury_penalty":     round(injury, 1),
        "joint_penalty":      round(joint_pen, 1),
        "silence_bonus":      bool(silence),
        "injury_flag":        injury > 0,
        "distraction_flag":   bool(distraction),
        "weather_notes":      weather_mods.get('notes', []),
        "player_count":       len(players),
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


def apply_line_movement(confidence, edge, pick, home_team, line_movement):
    """
    Adjust confidence based on closing line movement.
    Sharp money moves lines — if the line moves against our pick, reduce confidence.
    If it moves with our pick, small boost.
    Threshold: 2+ point move is meaningful. 3+ is a sharp signal.
    Returns (adjusted_confidence, sharp_signal) where sharp_signal is
    'with_pick', 'against_pick', or None.
    """
    if not line_movement:
        return confidence, None

    move = line_movement.get('spread_move')  # positive = home team got worse (line moved up)
    if move is None:
        return confidence, None

    # Our pick direction: home pick = we want home to cover = negative spread is good for us
    # If spread moves more negative (home favored more), line moved WITH home pick
    # If spread moves more positive (home favored less), line moved AGAINST home pick
    picking_home = (pick == home_team)

    # move < 0 means home became more favored (spread went from -3 to -5 = move of -2)
    # move > 0 means home became less favored (spread went from -5 to -3 = move of +2)
    line_with_home = move < 0

    if picking_home:
        line_with_pick    = line_with_home
        line_against_pick = not line_with_home
    else:
        line_with_pick    = not line_with_home
        line_against_pick = line_with_home

    abs_move = abs(move)
    sharp_signal = None

    if abs_move >= 2:
        if line_against_pick:
            # Sharp money disagrees — penalize confidence
            penalty = 10 if abs_move >= 3 else 5
            confidence = max(20, confidence - penalty)
            sharp_signal = 'against_pick'
        elif line_with_pick:
            # Sharp money agrees — small boost
            boost = 5 if abs_move >= 3 else 3
            confidence = min(95, confidence + boost)
            sharp_signal = 'with_pick'

    return confidence, sharp_signal


def predict_game(game, team_index, news_index, weather_index=None, practice_index=None):
    """Generate a prediction for a single game."""
    if weather_index is None:
        weather_index = {}
    if practice_index is None:
        practice_index = {}

    home = game['home_team']
    away = game['away_team']
    home_slug = TEAM_SLUG.get(home)
    away_slug = TEAM_SLUG.get(away)

    if not home_slug or not away_slug:
        return None

    weather_mods = get_weather_modifiers(game['game_id'], weather_index)
    home_data = raw_team_score(home_slug, team_index, news_index, weather_mods, practice_index)
    away_data = raw_team_score(away_slug, team_index, news_index, weather_mods, practice_index)

    spread = game['consensus'].get('spread') or 0.0
    edge = spread_to_implied_edge(spread, home_data['composite'], away_data['composite'])
    confidence = confidence_from_edge(edge)

    pick, pick_type = pick_side(home, away, home_data['composite'], away_data['composite'], spread)

    # Apply line movement modifier on closing snapshot
    line_movement = game.get('line_movement')
    confidence, sharp_signal = apply_line_movement(confidence, edge, pick, home, line_movement)
    if line_movement and sharp_signal:
        line_movement['sharp_signal'] = sharp_signal

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
        "line_movement": line_movement,
        "status": "open",
        "result": None,
        "lesson": None,
        "predicted_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        # Placeholders for Phase 2 layers
        "modifiers_applied": {
            "weather": {
                "dome":            weather_mods.get('dome'),
                "passing_mult":    weather_mods.get('passing_mult'),
                "kicker_mult":     weather_mods.get('kicker_mult'),
                "wind_flag":       weather_mods.get('wind_flag'),
                "precip_flag":     weather_mods.get('precip_flag'),
                "cold_flag":       weather_mods.get('cold_flag'),
                "cold_joint_flag": weather_mods.get('cold_joint_flag'),
                "conditions":      weather_mods.get('weather'),
                "notes":           weather_mods.get('notes'),
            },
            "practice_trajectory": {
                "home": practice_index.get(f"{home_slug}:{home}", {}).get('trajectory'),
                "away": practice_index.get(f"{away_slug}:{away}", {}).get('trajectory'),
            },
            "mbti_adjustment":     None,
            "coach_compatibility": None,
            "relationship_web":    None,
        }
    }


def main():
    import sys
    reset = '--reset' in sys.argv

    odds_data      = load('odds.json')
    players_data   = load('players.json')
    news_data      = load('news.json')
    weather_data   = load('weather.json')
    practice_data  = load('practice.json')
    existing       = load('predictions.json')
    metadata       = load('metadata.json')

    # Build indexes
    team_index     = build_team_index(players_data['players'])
    news_index     = {t['team_slug']: t for t in news_data.get('news', [])}
    weather_index  = weather_data.get('games', {})
    practice_index = practice_data.get('players', {})

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

        pred = predict_game(game, team_index, news_index, weather_index, practice_index)
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
