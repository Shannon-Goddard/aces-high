import nflreadpy as nfl
import json
import os
import math
import warnings
from datetime import datetime, timezone

warnings.filterwarnings('ignore')

DATA_DIR      = os.path.join(os.path.dirname(__file__), '..', 'data')
PLAYERS_FILE  = os.path.join(DATA_DIR, 'players.json')
TEAMS_FILE    = os.path.join(DATA_DIR, 'teams.json')
META_FILE     = os.path.join(DATA_DIR, 'metadata.json')

CURRENT_SEASON = 2024
SNAP_WEEKS     = 4   # trend window for snap count direction

# ── Position peak age curves (from historical nflverse data)
# Format: (peak_start, peak_end, typical_retirement)
POSITION_PEAKS = {
    'QB':  (28, 32, 38), 'RB':  (22, 24, 28), 'WR':  (24, 27, 32),
    'TE':  (25, 28, 33), 'OL':  (26, 30, 35), 'T':   (26, 30, 35),
    'G':   (26, 30, 35), 'C':   (26, 30, 35), 'DL':  (24, 28, 33),
    'DE':  (24, 28, 33), 'DT':  (24, 28, 33), 'LB':  (24, 28, 32),
    'CB':  (24, 27, 30), 'S':   (25, 28, 32),  'K':  (26, 32, 40),
    'P':   (26, 32, 40)
}

# ── Optimal weight ranges by position (lbs) — outside range = flag
POSITION_WEIGHT = {
    'QB':  (210, 240), 'RB':  (195, 225), 'WR':  (175, 215),
    'TE':  (240, 265), 'OL':  (295, 330), 'T':   (295, 330),
    'G':   (295, 320), 'C':   (285, 315), 'DL':  (280, 320),
    'DE':  (255, 285), 'DT':  (295, 330), 'LB':  (225, 255),
    'CB':  (175, 205), 'S':   (195, 220),  'K':  (175, 210),
    'P':   (185, 215)
}

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    # Use allow_nan=False to catch NaN early, but first sanitize via re-encode
    import math
    def sanitize(obj):
        if isinstance(obj, float) and math.isnan(obj):
            return None
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(v) for v in obj]
        return obj
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(sanitize(data), f, indent=2)

def safe_float(val):
    try:
        v = float(val)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None

def calc_age(birth_date_str):
    if not birth_date_str:
        return None
    try:
        bd = datetime.strptime(str(birth_date_str)[:10], '%Y-%m-%d')
        today = datetime.now()
        return (today - bd).days / 365.25
    except Exception:
        return None

# ── LAYER 1: BODY SCORE ────────────────────────────────────────────────────

def score_age_vs_peak(age, position):
    """
    How close is this player to his position peak?
    Returns score 0-100 and a label.
    100 = dead center of peak window
    """
    peaks = POSITION_PEAKS.get(position)
    if not age or not peaks:
        return None, 'unknown'
    peak_start, peak_end, retirement = peaks
    peak_mid = (peak_start + peak_end) / 2

    if age < peak_start:
        # Pre-peak — ascending, how close to peak start
        years_out = peak_start - age
        score = max(0, 100 - (years_out * 12))
        label = 'pre_peak'
    elif peak_start <= age <= peak_end:
        # In peak window
        dist_from_mid = abs(age - peak_mid)
        score = max(80, 100 - (dist_from_mid * 5))
        label = 'peak'
    elif age <= retirement:
        # Post peak, pre retirement
        years_past = age - peak_end
        total_window = retirement - peak_end
        score = max(20, 80 - ((years_past / total_window) * 60))
        label = 'post_peak'
    else:
        # Past typical retirement age
        score = max(0, 20 - ((age - retirement) * 10))
        label = 'retirement_risk'

    return round(score, 1), label

def score_weight(weight, position):
    """Is this player in optimal weight range for their position?"""
    optimal = POSITION_WEIGHT.get(position)
    if not weight or not optimal:
        return None, 'unknown'
    low, high = optimal
    mid = (low + high) / 2
    if low <= weight <= high:
        dist = abs(weight - mid) / ((high - low) / 2)
        score = round(100 - (dist * 20), 1)
        label = 'optimal'
    elif weight < low:
        delta = low - weight
        score = max(40, 100 - (delta * 3))
        label = 'underweight'
    else:
        delta = weight - high
        score = max(40, 100 - (delta * 3))
        label = 'overweight'
    return round(score, 1), label

def score_career_longevity(years_exp, position):
    """How far through average career length is this player?"""
    peaks = POSITION_PEAKS.get(position)
    if not years_exp or not peaks:
        return None, 'unknown'
    _, _, retirement_age = peaks
    # Approximate career length from typical entry age ~22
    avg_career = retirement_age - 22
    pct = years_exp / avg_career
    if pct < 0.4:
        return round(100 - (pct * 20), 1), 'early_career'
    elif pct < 0.7:
        return round(90 - (pct * 15), 1), 'mid_career'
    elif pct < 0.9:
        return round(70 - (pct * 30), 1), 'late_career'
    else:
        return round(max(20, 40 - (pct * 20)), 1), 'end_of_career'

def calc_snap_trend(snap_rows):
    """
    Given last N weeks of snap pct, return trend direction and score.
    Rising = good, Falling = flag, Flat = neutral.
    """
    if not snap_rows or len(snap_rows) < 2:
        return None, 'insufficient_data'
    pcts = [r for r in snap_rows if r is not None]
    if len(pcts) < 2:
        return None, 'insufficient_data'
    avg_first_half = sum(pcts[:len(pcts)//2]) / (len(pcts)//2)
    avg_second_half = sum(pcts[len(pcts)//2:]) / (len(pcts) - len(pcts)//2)
    delta = avg_second_half - avg_first_half
    if delta > 5:
        return round(avg_second_half, 1), 'rising'
    elif delta < -5:
        return round(avg_second_half, 1), 'falling'
    else:
        return round(avg_second_half, 1), 'flat'


def compute_momentum(snap_pcts_recent):
    """
    Rolling 3-week weighted snap% momentum.
    Weights: week N×0.5, N-1×0.3, N-2×0.2 (most recent first).
    Returns (momentum_score 0-100, momentum_direction).
    Snap% is 0-100 scale (multiply raw 0-1 values by 100).
    """
    # snap_pcts_recent is ordered most-recent-first, raw 0-1 values
    vals = [v * 100.0 for v in snap_pcts_recent if v is not None]
    if not vals:
        return None, 'unknown'

    weights = [0.5, 0.3, 0.2]
    weighted_sum, weight_total = 0.0, 0.0
    for i, w in enumerate(weights):
        if i >= len(vals):
            break
        weighted_sum += vals[i] * w
        weight_total += w

    momentum_score = round(weighted_sum / weight_total, 1) if weight_total else None

    # Direction: compare weighted recent vs simple average of older weeks
    if len(vals) >= 2:
        recent = vals[0]
        older_avg = sum(vals[1:]) / len(vals[1:])
        delta = recent - older_avg
        direction = 'up' if delta > 5 else 'down' if delta < -5 else 'flat'
    else:
        direction = 'flat'

    return momentum_score, direction

def build_layer1(player_row, snap_pcts, age):
    pos = str(player_row.get('position', '') or '').upper()
    weight = safe_float(player_row.get('weight'))
    years_exp = safe_float(player_row.get('years_exp') or player_row.get('years_of_experience'))

    age_score, age_label         = score_age_vs_peak(age, pos)
    weight_score, weight_label   = score_weight(weight, pos)
    longevity_score, career_label = score_career_longevity(years_exp, pos)
    snap_pct, snap_trend         = calc_snap_trend(snap_pcts)

    # Composite body score — weighted average of available components
    components = [s for s in [age_score, weight_score, longevity_score] if s is not None]
    body_score = round(sum(components) / len(components), 1) if components else None

    return {
        'body_score':      body_score,
        'age':             round(age, 1) if age else None,
        'age_score':       age_score,
        'age_label':       age_label,
        'weight':          weight,
        'weight_score':    weight_score,
        'weight_label':    weight_label,
        'years_exp':       years_exp,
        'longevity_score': longevity_score,
        'career_label':    career_label,
        'snap_pct':        snap_pct,
        'snap_trend':      snap_trend
    }

# ── LAYER 2: SKILL SCORE ───────────────────────────────────────────────────

def percentile_rank(value, all_values):
    """Where does this value rank among peers? Returns 0-100."""
    if value is None or not all_values:
        return None
    valid = [v for v in all_values if v is not None]
    if not valid:
        return None
    below = sum(1 for v in valid if v < value)
    return round((below / len(valid)) * 100, 1)

def build_layer2_qb(stats_row, peer_stats):
    passing_epa  = safe_float(stats_row.get('passing_epa'))
    cpoe         = safe_float(stats_row.get('passing_cpoe'))
    attempts     = safe_float(stats_row.get('attempts')) or 0

    if attempts < 100:  # not enough sample
        return None

    peer_epa  = [safe_float(r.get('passing_epa'))  for r in peer_stats]
    peer_cpoe = [safe_float(r.get('passing_cpoe')) for r in peer_stats]

    epa_pct  = percentile_rank(passing_epa, peer_epa)
    cpoe_pct = percentile_rank(cpoe, peer_cpoe)

    components = [s for s in [epa_pct, cpoe_pct] if s is not None]
    skill_score = round(sum(components) / len(components), 1) if components else None

    return {
        'skill_score':  skill_score,
        'passing_epa':  passing_epa,
        'epa_pct':      epa_pct,
        'cpoe':         cpoe,
        'cpoe_pct':     cpoe_pct,
        'attempts':     int(attempts)
    }

def build_layer2_rb(stats_row, peer_stats):
    rushing_epa = safe_float(stats_row.get('rushing_epa'))
    carries     = safe_float(stats_row.get('carries')) or 0

    if carries < 50:
        return None

    peer_epa = [safe_float(r.get('rushing_epa')) for r in peer_stats]
    epa_pct  = percentile_rank(rushing_epa, peer_epa)

    return {
        'skill_score': epa_pct,
        'rushing_epa': rushing_epa,
        'epa_pct':     epa_pct,
        'carries':     int(carries)
    }

def build_layer2_wr_te(stats_row, peer_stats):
    receiving_epa = safe_float(stats_row.get('receiving_epa'))
    target_share  = safe_float(stats_row.get('target_share'))
    wopr          = safe_float(stats_row.get('wopr'))
    targets       = safe_float(stats_row.get('targets')) or 0

    if targets < 30:
        return None

    peer_epa    = [safe_float(r.get('receiving_epa'))  for r in peer_stats]
    peer_wopr   = [safe_float(r.get('wopr'))           for r in peer_stats]

    epa_pct  = percentile_rank(receiving_epa, peer_epa)
    wopr_pct = percentile_rank(wopr, peer_wopr)

    components = [s for s in [epa_pct, wopr_pct] if s is not None]
    skill_score = round(sum(components) / len(components), 1) if components else None

    return {
        'skill_score':    skill_score,
        'receiving_epa':  receiving_epa,
        'epa_pct':        epa_pct,
        'target_share':   target_share,
        'wopr':           wopr,
        'wopr_pct':       wopr_pct,
        'targets':        int(targets)
    }

def build_layer2_def(stats_row, peer_stats):
    sacks    = safe_float(stats_row.get('def_sacks')) or 0
    tackles  = safe_float(stats_row.get('def_tackles_solo')) or 0
    ints     = safe_float(stats_row.get('def_interceptions')) or 0
    defended = safe_float(stats_row.get('def_pass_defended')) or 0

    if sacks + tackles + ints + defended < 5:
        return None

    peer_sacks   = [safe_float(r.get('def_sacks'))          for r in peer_stats]
    peer_tackles = [safe_float(r.get('def_tackles_solo'))   for r in peer_stats]

    sack_pct   = percentile_rank(sacks, peer_sacks)
    tackle_pct = percentile_rank(tackles, peer_tackles)

    components = [s for s in [sack_pct, tackle_pct] if s is not None]
    skill_score = round(sum(components) / len(components), 1) if components else None

    return {
        'skill_score': skill_score,
        'sacks':       sacks,
        'sack_pct':    sack_pct,
        'tackles':     tackles,
        'tackle_pct':  tackle_pct,
        'interceptions': ints,
        'pass_defended': defended
    }

def build_layer2_k(stats_row, peer_stats):
    fg_pct  = safe_float(stats_row.get('fg_pct'))
    fg_att  = safe_float(stats_row.get('fg_att')) or 0
    fg_long = safe_float(stats_row.get('fg_long'))

    if fg_att < 10:
        return None

    peer_pct  = [safe_float(r.get('fg_pct'))  for r in peer_stats]
    peer_long = [safe_float(r.get('fg_long')) for r in peer_stats]

    pct_rank  = percentile_rank(fg_pct, peer_pct)
    long_rank = percentile_rank(fg_long, peer_long)

    components = [s for s in [pct_rank, long_rank] if s is not None]
    skill_score = round(sum(components) / len(components), 1) if components else None

    return {
        'skill_score': skill_score,
        'fg_pct':      fg_pct,
        'fg_pct_rank': pct_rank,
        'fg_long':     fg_long,
        'fg_long_rank': long_rank,
        'fg_att':      int(fg_att)
    }

def build_layer2_ol(snap_pct, years_exp, draft_round, peer_snaps):
    """OL: snap% vs peers + draft pedigree + longevity. No EPA available."""
    snap_rank = percentile_rank(snap_pct, [s for s in peer_snaps if s is not None]) if snap_pct else None
    # Draft pedigree: round 1-2 = high floor, round 5+ = earned their spot
    draft_score = None
    if draft_round is not None:
        if draft_round <= 2:   draft_score = 75.0
        elif draft_round <= 4: draft_score = 55.0
        else:                  draft_score = 45.0
    else:
        draft_score = 40.0  # undrafted — lowest floor for OL
    # Longevity: OL who stick around are good
    longevity_score = None
    if years_exp is not None:
        longevity_score = min(90.0, 40.0 + years_exp * 4.0)
    components = [s for s in [snap_rank, draft_score, longevity_score] if s is not None]
    skill_score = round(sum(components) / len(components), 1) if components else None
    return {
        'skill_score':     skill_score,
        'snap_rank':       snap_rank,
        'draft_score':     draft_score,
        'longevity_score': longevity_score,
        'source':          'ol_proxy'
    }

def build_layer2_p(stats_row, peer_stats):
    """Punters: net yards per punt percentile vs peers."""
    net_avg = safe_float(stats_row.get('punting_net_yds_per_punt'))
    punts   = safe_float(stats_row.get('punts')) or 0
    if punts < 10 or net_avg is None:
        return None
    peer_net = [safe_float(r.get('punting_net_yds_per_punt')) for r in peer_stats]
    net_rank = percentile_rank(net_avg, peer_net)
    return {
        'skill_score':   net_rank,
        'net_yds_avg':   net_avg,
        'net_yds_rank':  net_rank,
        'punts':         int(punts)
    }

def build_layer2_ls(snap_pct, years_exp):
    """Long snappers: presence + longevity = competence. No stats tracked."""
    # If they're on the roster and snapping, they're doing their job
    base = 50.0
    snap_bonus = min(30.0, (snap_pct or 0) * 30.0)  # snap_pct is 0-1
    exp_bonus  = min(20.0, (years_exp or 0) * 2.0)
    skill_score = round(base + snap_bonus + exp_bonus, 1)
    return {
        'skill_score': skill_score,
        'snap_pct':    snap_pct,
        'years_exp':   years_exp,
        'source':      'ls_proxy'
    }

def build_layer2_fallback(layer1, draft):
    """
    Fallback for depth players below stat thresholds.
    Uses body score + snap% + hunger seed as proxy.
    Labeled so we know it's estimated, not stat-derived.
    """
    body_score   = (layer1 or {}).get('body_score') or 50.0
    snap_pct     = (layer1 or {}).get('snap_pct') or 0.0
    hunger_seed  = (draft  or {}).get('hunger_seed') or 50.0
    snap_trend   = (layer1 or {}).get('snap_trend', 'flat')

    # Snap% is 0-1, scale to 0-100
    snap_score = min(100.0, snap_pct * 100.0)

    # Trend modifier: rising players get a bump, falling get a penalty
    trend_mod = 5.0 if snap_trend == 'rising' else -5.0 if snap_trend == 'falling' else 0.0

    components = [body_score * 0.4, snap_score * 0.4, hunger_seed * 0.2]
    skill_score = round(sum(components) + trend_mod, 1)
    skill_score = max(0.0, min(100.0, skill_score))

    return {
        'skill_score': skill_score,
        'body_proxy':  round(body_score, 1),
        'snap_proxy':  round(snap_score, 1),
        'hunger_proxy': hunger_seed,
        'source':      'fallback'
    }

def build_layer2(stats_row, position, peer_stats, layer1=None, draft=None,
                 snap_pct=None, years_exp=None, draft_round=None, peer_snaps=None):
    pos = position.upper()
    result = None

    if pos == 'QB':
        result = build_layer2_qb(stats_row, peer_stats)
    elif pos == 'RB':
        result = build_layer2_rb(stats_row, peer_stats)
    elif pos in ('WR', 'TE'):
        result = build_layer2_wr_te(stats_row, peer_stats)
    elif pos in ('DL', 'DE', 'DT', 'LB', 'CB', 'S', 'DB'):
        result = build_layer2_def(stats_row, peer_stats)
    elif pos == 'K':
        result = build_layer2_k(stats_row, peer_stats)
    elif pos in ('OL', 'T', 'G', 'C', 'OT', 'OG'):
        result = build_layer2_ol(snap_pct, years_exp, draft_round, peer_snaps or [])
    elif pos == 'P':
        result = build_layer2_p(stats_row, peer_stats)
    elif pos == 'LS':
        result = build_layer2_ls(snap_pct, years_exp)

    # Fallback for any position that returned None (below stat threshold)
    if result is None:
        result = build_layer2_fallback(layer1, draft)

    return result

# ── COMBINE / DRAFT HUNGER SEEDS ──────────────────────────────────────────

def build_combine_profile(combine_row):
    if combine_row is None:
        return None
    return {
        'forty':      safe_float(combine_row.get('forty')),
        'vertical':   safe_float(combine_row.get('vertical')),
        'broad_jump': safe_float(combine_row.get('broad_jump')),
        'bench':      safe_float(combine_row.get('bench')),
        'cone':       safe_float(combine_row.get('cone')),
        'shuttle':    safe_float(combine_row.get('shuttle'))
    }

def build_draft_profile(draft_row):
    if draft_row is None:
        return None
    rd = safe_float(draft_row.get('round') or draft_row.get('draft_round'))
    pk = safe_float(draft_row.get('pick')  or draft_row.get('draft_pick') or draft_row.get('draft_ovr'))
    # Hunger seed — late round and undrafted players start with higher hunger baseline
    if rd is None:
        hunger_seed = 80   # undrafted — maximum chip
    elif rd >= 5:
        hunger_seed = 70
    elif rd >= 3:
        hunger_seed = 55
    elif rd == 2:
        hunger_seed = 45
    else:
        hunger_seed = 30   # round 1 — handed everything, lower baseline hunger
    return {
        'draft_round':  int(rd) if rd else None,
        'draft_pick':   int(pk) if pk else None,
        'hunger_seed':  hunger_seed
    }

# ── INJURY / PRACTICE STATUS ──────────────────────────────────────────────

def build_injury_profile(injury_rows):
    """
    Build practice trajectory from most recent injury report entries.
    Wed → Thu → Fri trajectory is more predictive than final designation.
    """
    if not injury_rows:
        return None
    latest = sorted(injury_rows, key=lambda r: str(r.get('date_modified', '')), reverse=True)
    most_recent = latest[0]
    return {
        'report_status':            most_recent.get('report_status'),
        'practice_status':          most_recent.get('practice_status'),
        'primary_injury':           most_recent.get('report_primary_injury'),
        'secondary_injury':         most_recent.get('report_secondary_injury'),
        'practice_primary_injury':  most_recent.get('practice_primary_injury'),
        'date_modified':            str(most_recent.get('date_modified', ''))
    }

# ── MAIN ──────────────────────────────────────────────────────────────────

def main():
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"update_ratings.py — {now_str}")
    print(f"Season: {CURRENT_SEASON}")

    # ── Load all nflverse datasets
    print("\nLoading nflverse data...")
    print("  players...")
    players_df    = nfl.load_players()
    print("  rosters...")
    rosters_df    = nfl.load_rosters(seasons=[CURRENT_SEASON])
    print("  player stats...")
    stats_df      = nfl.load_player_stats(seasons=[CURRENT_SEASON])
    print("  snap counts...")
    snaps_df      = nfl.load_snap_counts(seasons=[CURRENT_SEASON])
    print("  injuries...")
    injuries_df   = nfl.load_injuries(seasons=[CURRENT_SEASON])
    print("  combine...")
    combine_df    = nfl.load_combine()
    print("  draft picks...")
    draft_df      = nfl.load_draft_picks()
    print("  Done.")

    # ── Convert Polars dataframes to pandas for familiar indexing
    print("Converting to pandas...")
    players_df  = players_df.to_pandas()
    rosters_df  = rosters_df.to_pandas()
    stats_df    = stats_df.to_pandas()
    snaps_df    = snaps_df.to_pandas()
    injuries_df = injuries_df.to_pandas()
    combine_df  = combine_df.to_pandas()
    draft_df    = draft_df.to_pandas()

    # ── Build lookup dicts for fast access
    # Aggregate stats to season level per player
    stat_cols = [
        'player_id', 'position',
        'passing_epa', 'passing_cpoe', 'attempts',
        'rushing_epa', 'carries',
        'receiving_epa', 'target_share', 'wopr', 'targets',
        'def_sacks', 'def_tackles_solo', 'def_interceptions', 'def_pass_defended',
        'fg_pct', 'fg_att', 'fg_long',
        'punting_net_yds_per_punt', 'punts'
    ]
    available_stat_cols = [c for c in stat_cols if c in stats_df.columns]
    reg_stats = stats_df[stats_df['season_type'] == 'REG'][available_stat_cols]

    # Rate stats need mean, counting stats need sum
    rate_cols  = ['passing_cpoe', 'target_share', 'wopr', 'fg_pct']
    count_cols = [c for c in available_stat_cols if c not in rate_cols + ['player_id', 'position']]

    sum_stats  = reg_stats.groupby('player_id')[count_cols].sum(numeric_only=True)
    mean_stats = reg_stats.groupby('player_id')[rate_cols].mean(numeric_only=True)
    pos_stats  = reg_stats.groupby('player_id')['position'].first()

    season_stats = sum_stats.join(mean_stats).join(pos_stats).reset_index()
    stats_by_id = {
        str(row['player_id']): row.to_dict()
        for _, row in season_stats.iterrows()
    }

    # Snap count trend per player — last SNAP_WEEKS weeks
    snaps_by_id = {}
    if not snaps_df.empty:
        recent_snaps = snaps_df[snaps_df['season'] == CURRENT_SEASON].copy()
        for pid, grp in recent_snaps.groupby('pfr_player_id'):
            grp_sorted = grp.sort_values('week', ascending=False).head(SNAP_WEEKS)
            off_pcts = grp_sorted['offense_pct'].tolist()
            def_pcts = grp_sorted['defense_pct'].tolist()
            snaps_by_id[str(pid)] = {
                'offense': [safe_float(v) for v in off_pcts],
                'defense': [safe_float(v) for v in def_pcts]
            }

    # Injury lookup by gsis_id
    injuries_by_id = {}
    if not injuries_df.empty:
        for pid, grp in injuries_df.groupby('gsis_id'):
            injuries_by_id[str(pid)] = grp.to_dict('records')

    # Combine lookup by player name (best available join)
    combine_by_name = {}
    if not combine_df.empty:
        for _, row in combine_df.iterrows():
            combine_by_name[str(row.get('player_name', '')).lower()] = row.to_dict()

    # Draft lookup by gsis_id
    draft_by_id = {}
    if not draft_df.empty:
        for _, row in draft_df.iterrows():
            gid = str(row.get('gsis_id', ''))
            if gid:
                draft_by_id[gid] = row.to_dict()

    # Peer stats by position for percentile ranking
    peer_stats_by_pos = {}
    for _, row in season_stats.iterrows():
        pos = str(row.get('position', '')).upper()
        if pos not in peer_stats_by_pos:
            peer_stats_by_pos[pos] = []
        peer_stats_by_pos[pos].append(row.to_dict())

    # ── Get active roster — deduplicate to latest week per player
    active_roster = (
        rosters_df[rosters_df['season'] == CURRENT_SEASON]
        .sort_values('week', ascending=False)
        .drop_duplicates(subset='gsis_id', keep='first')
    )

    # ── Build player records
    print(f"\nBuilding player ratings for {len(active_roster)} active players...")
    player_records = []
    positions_seen = {}

    for _, roster_row in active_roster.iterrows():
        gsis_id  = str(roster_row.get('gsis_id', '') or '')
        name     = str(roster_row.get('full_name', '') or '')
        position = str(roster_row.get('position', '') or '').upper()
        team     = str(roster_row.get('team', '') or '')

        if not gsis_id or not name or not position:
            continue

        # Get matching players row for bio data
        player_bio = players_df[players_df['gsis_id'] == gsis_id]
        bio = player_bio.iloc[0].to_dict() if not player_bio.empty else {}

        age = calc_age(
            roster_row.get('birth_date') or bio.get('birth_date')
        )

        # Snap trend
        snap_data  = snaps_by_id.get(str(roster_row.get('pfr_id', '') or ''), {})
        is_offense = position in ('QB', 'RB', 'WR', 'TE', 'OL', 'T', 'G', 'C', 'FB')
        snap_pcts  = snap_data.get('offense' if is_offense else 'defense', [])

        # Layer 1 — Body
        layer1 = build_layer1({
            'position':   position,
            'weight':     roster_row.get('weight') or bio.get('weight'),
            'years_exp':  roster_row.get('years_exp') or bio.get('years_of_experience')
        }, snap_pcts, age)

        # Layer 2 — Skill
        stats_row   = stats_by_id.get(gsis_id, {})
        peer_stats  = peer_stats_by_pos.get(position, [])
        ol_positions = ('OL', 'T', 'G', 'C', 'OT', 'OG')
        peer_snaps  = [
            safe_float(snaps_by_id.get(str(r.get('pfr_id','') or ''), {}).get('offense', [None])[0])
            for _, r in active_roster[active_roster['position'].str.upper().isin(ol_positions)].iterrows()
        ] if position.upper() in ol_positions else []
        layer2 = build_layer2(
            stats_row, position, peer_stats,
            layer1=layer1,
            draft=draft,
            snap_pct=(layer1 or {}).get('snap_pct'),
            years_exp=(layer1 or {}).get('years_exp'),
            draft_round=(draft or {}).get('draft_round'),
            peer_snaps=peer_snaps
        )

        # Momentum — rolling 3-week weighted snap% score
        if layer2 is not None:
            momentum_score, momentum_direction = compute_momentum(snap_pcts)
            layer2['momentum_score']     = momentum_score
            layer2['momentum_direction'] = momentum_direction

        # Combine profile
        combine_row = combine_by_name.get(name.lower())
        combine     = build_combine_profile(combine_row)

        # Draft profile + hunger seed
        draft_row = draft_by_id.get(gsis_id) or {
            'draft_round': bio.get('draft_round'),
            'draft_pick':  bio.get('draft_pick')
        }
        draft = build_draft_profile(draft_row)

        # Injury / practice status
        injury = build_injury_profile(injuries_by_id.get(gsis_id))

        # Track position counts for summary
        positions_seen[position] = positions_seen.get(position, 0) + 1

        player_records.append({
            'gsis_id':    gsis_id,
            'name':       name,
            'team':       team,
            'position':   position,
            'headshot':   str(roster_row.get('headshot_url') or bio.get('headshot') or ''),
            'college':    str(roster_row.get('college') or bio.get('college_name') or ''),
            'college_conference': str(bio.get('college_conference') or ''),
            'last_updated': now_str,

            # Layer 1 — Body
            'layer1_body': layer1,

            # Layer 2 — Skill (percentile ranked vs position peers)
            'layer2_skill': layer2,

            # Seeds for Layer 3 (Hunger/Distraction built by separate process)
            'combine':    combine,
            'draft':      draft,
            'injury':     injury,

            # Layer 3-5 placeholders — populated by other scripts
            'layer3_mind':        None,
            'layer4_personality': None,
            'layer5_relationships': []
        })

    # ── Save
    players_data = load_json(PLAYERS_FILE)

    # Merge — update existing, append new
    existing_by_id = {p['gsis_id']: p for p in players_data.get('players', [])}
    for record in player_records:
        pid = record['gsis_id']
        if pid in existing_by_id:
            # Preserve layer 3-5 data, update layers 1-2
            existing = existing_by_id[pid]
            record['layer3_mind']          = existing.get('layer3_mind')
            record['layer4_personality']   = existing.get('layer4_personality')
            record['layer5_relationships'] = existing.get('layer5_relationships', [])
        existing_by_id[pid] = record

    players_data['players']      = list(existing_by_id.values())
    players_data['last_updated'] = now_str
    save_json(PLAYERS_FILE, players_data)

    # ── Update metadata
    metadata = load_json(META_FILE)
    metadata['last_ratings_update'] = now_str
    metadata['ratings_summary'] = {
        'season':          CURRENT_SEASON,
        'total_players':   len(player_records),
        'by_position':     positions_seen,
        'layer1_complete': True,
        'layer2_complete': True
    }
    save_json(META_FILE, metadata)

    print(f"\nDone. {len(player_records)} players rated.")
    print(f"Positions: {positions_seen}")
    print(f"players.json updated.")

if __name__ == '__main__':
    main()
