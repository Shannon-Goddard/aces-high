"""
infer_personality.py — Infer layer4_personality for all players in players.json

Axes inferred from available data:
  I/E — career longevity + snap consistency (grinder vs volatile)
  T/F — draft slot vs current performance (outperforming = T drive; underperforming = F distraction)
  S/N — position archetype (detail/execution roles vs pattern/vision roles)
  J/P — practice trajectory consistency (steady Wed→Thu→Fri = J; volatile = P)

Writes layer4_personality block to each player. Does NOT overwrite layers 1-3 or 5.

Run: after update_ratings.py (needs layer1_body + layer2_skill populated)
"""

import json
import os
from datetime import datetime, timezone

DATA_DIR      = os.path.join(os.path.dirname(__file__), '..', 'data')
PLAYERS_FILE  = os.path.join(DATA_DIR, 'players.json')
COACHES_FILE  = os.path.join(DATA_DIR, 'coaches.json')
META_FILE     = os.path.join(DATA_DIR, 'metadata.json')

# ── COMMUNICATION MAP (mirrors players.html) ─────────────────────────────────
COMM_MAP = {
    'QB':  ['WR', 'TE', 'RB', 'OL'],
    'WR':  ['QB'],
    'TE':  ['QB'],
    'RB':  ['QB', 'OL'],
    'OL':  ['QB', 'RB'],
    'LB':  ['DL', 'DB'],
    'DB':  ['LB', 'DB'],
    'DL':  ['LB'],
}
COACH_MAP  = {
    'QB': 'oc', 'WR': 'oc', 'TE': 'oc', 'RB': 'oc', 'OL': 'oc',
    'LB': 'dc', 'DB': 'dc', 'DL': 'dc',
}
HC_DIRECT = {'QB', 'LB'}   # HC talks directly to these position groups

# ── POSITION ARCHETYPES ───────────────────────────────────────────────────────
# S = Sensing (detail, execution, physical, present-focused)
# N = iNtuition (pattern recognition, vision, creative, future-focused)
# Hybrid = both signals present, lean based on role demands

POS_SN = {
    # Strong S — execution, technique, physical dominance
    'OL': 'S', 'T': 'S', 'G': 'S', 'C': 'S', 'OT': 'S', 'OG': 'S',
    'DL': 'S', 'DT': 'S', 'DE': 'S',
    'LB': 'S', 'FB': 'S', 'LS': 'S',
    # Strong N — reads, pattern recognition, vision
    'QB': 'N', 'WR': 'N', 'TE': 'N',
    # Hybrid lean S — reactive, instinct-based
    'CB': 'S', 'S': 'S', 'DB': 'S',
    # Hybrid lean N — field vision, coverage reads
    'RB': 'N',
    # Specialists — execution-focused
    'K': 'S', 'P': 'S',
}

# ── COLLEGE PROGRAM SIGNALS ───────────────────────────────────────────────────
# Elite system programs = more likely S (execute the system)
# Small school / non-power = more likely N (had to figure it out themselves)
ELITE_PROGRAMS = {
    'alabama', 'ohio state', 'georgia', 'clemson', 'lsu', 'louisiana state',
    'michigan', 'notre dame', 'oklahoma', 'penn state', 'florida', 'florida state',
    'texas', 'usc', 'oregon', 'auburn', 'tennessee', 'miami', 'pittsburgh',
    'texas a&m', 'wisconsin', 'iowa', 'nebraska', 'washington', 'stanford',
}


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ── COMPAT SCORING (mirrors players.html compatScore) ─────────────────────────
def compat_score(type_a, type_b):
    """Return 0-100 compat score between two MBTI type strings."""
    if not type_a or not type_b:
        return 50
    def parse(t):
        return {
            'ie': t[0] if t[0] != '?' else None,
            'sn': t[1] if t[1] != '?' else None,
            'tf': t[2] if t[2] != '?' else None,
            'jp': t[3] if t[3] != '?' else None,
        }
    a, b = parse(type_a), parse(type_b)
    score = 50
    if a['ie'] and b['ie']:
        score += 5 if a['ie'] == b['ie'] else 0
    if a['sn'] and b['sn']:
        score += 10 if a['sn'] == b['sn'] else -10
    if a['tf'] and b['tf']:
        if   a['tf'] == 'T' and b['tf'] == 'F': score -= 15
        elif a['tf'] == 'F' and b['tf'] == 'T': score -= 5
        else:                                    score += 10
    if a['jp'] and b['jp']:
        if   a['jp'] == 'J' and b['jp'] == 'P': score -= 10
        elif a['jp'] == a['jp']:                 score += 5
    return max(0, min(100, score))


# ── ROLE FIT (position demands vs player MBTI) ───────────────────────────────
# Each position has ideal axis values. Per axis: match=+1, poor_fit=-1, neutral/unknown=0.
# Raw -4..+4 normalized to 0-100.
POS_DEMANDS = {
    #         ie      sn    tf    jp
    'QB':  (None,   'N',  'T',  'J'),   # reads (N), cold decisions (T), structured prep (J)
    'WR':  ('E',    'N',  None, 'P'),   # external energy (E), route creativity (N), adaptive (P)
    'TE':  (None,   'N',  'T',  'J'),   # hybrid blocker/receiver — reads + structure
    'RB':  ('E',    None, 'T',  'P'),   # explosive reactive (P/E), cold instinct (T)
    'FB':  ('E',    'S',  'T',  'J'),   # lead blocker — physical execution, structure
    'OL':  ('I',    'S',  'T',  'J'),   # technique grind (S/I/J), cold accountability (T)
    'OT':  ('I',    'S',  'T',  'J'),
    'OG':  ('I',    'S',  'T',  'J'),
    'C':   ('I',    'S',  'T',  'J'),
    'T':   ('I',    'S',  'T',  'J'),
    'G':   ('I',    'S',  'T',  'J'),
    'DL':  ('E',    'S',  'T',  'P'),   # explosive reactive (E/P), physical dominance (S/T)
    'DT':  ('E',    'S',  'T',  'P'),
    'DE':  ('E',    'S',  'T',  'P'),
    'LB':  (None,   'S',  'T',  'J'),   # gap discipline (S/J), cold pursuit (T)
    'DB':  ('E',    None, 'T',  'P'),   # coverage reactive (E/P), cold reads (T)
    'CB':  ('E',    None, 'T',  'P'),
    'S':   ('E',    None, 'T',  'P'),
    'K':   ('I',    'S',  'T',  'J'),   # isolated execution, routine-driven, cold under pressure
    'P':   ('I',    'S',  'T',  'J'),
    'LS':  ('I',    'S',  'T',  'J'),
}

# Human-readable axis labels for evidence
_AXIS_LABELS = {
    'ie': {'I': 'internal drive suits isolated execution',
           'E': 'external energy suits high-communication role'},
    'sn': {'S': 'detail/execution orientation suits physical role demands',
           'N': 'pattern recognition suits reads and vision demands'},
    'tf': {'T': 'cold analytical decision-making under pressure',
           'F': 'emotionally-driven — friction with cold accountability demands'},
    'jp': {'J': 'structured preparation suits disciplined role',
           'P': 'adaptive reactivity suits instinct-driven role'},
}
_POOR_LABELS = {
    'ie': {'I': 'introversion may limit high-communication role energy',
           'E': 'external energy may disrupt isolated execution focus'},
    'sn': {'S': 'execution focus may limit pattern-reading demands',
           'N': 'vision orientation may conflict with pure execution role'},
    'tf': {'T': 'cold logic may conflict with team-feel role',
           'F': 'emotional processing under pressure — poor fit for cold-decision role'},
    'jp': {'J': 'rigid structure may limit reactive instinct role',
           'P': 'adaptive style may conflict with disciplined structure role'},
}


def compute_role_fit(player):
    """
    Score how well a player's MBTI type matches their position's demands.
    Returns (score 0-100, label, evidence list).
    """
    pos    = (player.get('position') or '').upper()
    l4     = player.get('layer4_personality') or {}
    demands = POS_DEMANDS.get(pos)
    if not demands:
        return None, None, []

    d_ie, d_sn, d_tf, d_jp = demands
    p_ie = l4.get('ie')
    p_sn = l4.get('sn')
    p_tf = l4.get('tf')
    p_jp = l4.get('jp')

    raw      = 0
    possible = 0
    evidence = []

    for axis, demand, player_val in [
        ('ie', d_ie, p_ie),
        ('sn', d_sn, p_sn),
        ('tf', d_tf, p_tf),
        ('jp', d_jp, p_jp),
    ]:
        if demand is None or player_val is None:
            continue   # axis not demanded or not inferred — neutral
        possible += 1
        if player_val == demand:
            raw += 1
            evidence.append(f'{axis.upper()} match ({player_val}): {_AXIS_LABELS[axis][player_val]}')
        else:
            raw -= 1
            evidence.append(f'{axis.upper()} mismatch ({player_val} vs {demand} ideal): {_POOR_LABELS[axis][player_val]}')

    if possible == 0:
        return None, None, []

    # Normalize raw (-possible..+possible) → 0-100
    score = round((raw + possible) / (2 * possible) * 100)
    score = max(0, min(100, score))
    label = 'Best Fit' if score >= 70 else 'Adequate' if score >= 45 else 'Poor Fit'
    return score, label, evidence


def compute_team_compat(player, team_players, coaches_by_slug):
    """
    Weighted compat score for a player within their communication chain.
    HC (if direct) × 0.35 + coordinator × 0.25 + position partners × 0.40
    Returns 0-100 float, or None if no data available.
    """
    pos      = (player.get('position') or '').upper()
    my_type  = (player.get('layer4_personality') or {}).get('mbti_type')
    if not my_type:
        return None

    abbr     = (player.get('team') or '').upper()
    slug_map = {
        'BUF':'buf','MIA':'mia','NE':'ne','NYJ':'nyj','BAL':'bal','CIN':'cin',
        'CLE':'cle','PIT':'pit','HOU':'hou','IND':'ind','JAX':'jax','TEN':'ten',
        'DEN':'den','KC':'kc','LV':'lv','LAC':'lac','DAL':'dal','NYG':'nyg',
        'PHI':'phi','WAS':'wsh','CHI':'chi','DET':'det','GB':'gb','MIN':'min',
        'ATL':'atl','CAR':'car','NO':'no','TB':'tb','ARI':'ari','LA':'lar',
        'SF':'sf','SEA':'sea',
    }
    slug     = slug_map.get(abbr)
    coaches  = coaches_by_slug.get(slug, []) if slug else []
    hc       = next((c for c in coaches if c.get('role') == 'hc'), None)
    coord_role = COACH_MAP.get(pos)
    coord    = next((c for c in coaches if c.get('role') == coord_role), None) if coord_role else None

    scores, weights = [], []

    # HC — direct authority link (higher weight for QB/LB, still present for others)
    if hc and hc.get('mbti_type'):
        hc_w = 0.35 if pos in HC_DIRECT else 0.20
        scores.append(compat_score(hc.get('mbti_type'), my_type))
        weights.append(hc_w)

    # Coordinator — direct play-caller
    if coord and coord.get('mbti_type') and coord is not hc:
        scores.append(compat_score(coord.get('mbti_type'), my_type))
        weights.append(0.25)

    # Position communication partners
    comm_positions = COMM_MAP.get(pos, [])
    if comm_positions:
        partner_scores = [
            compat_score(my_type, (p.get('layer4_personality') or {}).get('mbti_type'))
            for p in team_players
            if p.get('name') != player.get('name')
            and (p.get('position') or '').upper() in comm_positions
            and (p.get('layer4_personality') or {}).get('mbti_type')
        ]
        if partner_scores:
            scores.append(sum(partner_scores) / len(partner_scores))
            weights.append(0.40)

    if not scores:
        return None

    total_w = sum(weights)
    return round(sum(s * w for s, w in zip(scores, weights)) / total_w, 1)


def save_json(path, data):
    def sanitize(obj):
        import math
        if isinstance(obj, float) and math.isnan(obj):
            return None
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(v) for v in obj]
        return obj
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(sanitize(data), f, indent=2)


# ── AXIS INFERENCE ────────────────────────────────────────────────────────────

def infer_ie(player):
    """
    I/E from career longevity + snap consistency.
    Long career + steady snaps = I (internal drive, consistent).
    Short career + volatile snaps = E (external energy, reactive).
    """
    evidence = []
    signal = None

    l1 = player.get('layer1_body') or {}
    years_exp   = l1.get('years_exp') or 0
    snap_trend  = l1.get('snap_trend') or 'flat'
    career_label = l1.get('career_label') or ''
    snap_pct    = l1.get('snap_pct') or 0

    # Longevity signal
    if years_exp >= 8:
        signal = 'I'
        evidence.append(f'{int(years_exp)} years experience — sustained career suggests internal drive')
    elif years_exp >= 5:
        signal = 'I'
        evidence.append(f'{int(years_exp)} years — mid-career consistency signal')
    elif years_exp <= 2:
        signal = 'E'
        evidence.append('Early career — insufficient data, defaulting to E')

    # Snap consistency modifier
    if snap_trend == 'rising' and snap_pct and snap_pct > 60:
        if signal != 'I':
            signal = 'I'
        evidence.append(f'Rising snap% ({snap_pct:.0f}%) — earning role through performance')
    elif snap_trend == 'falling':
        evidence.append('Falling snap% — role volatility, possible external pressure response')
        if signal == 'I' and years_exp < 6:
            signal = 'E'

    # Career stage
    if career_label == 'end_of_career' and years_exp >= 10:
        signal = 'I'
        evidence.append('End-of-career veteran — survived this long through internal discipline')

    return signal, evidence


def infer_tf(player):
    """
    T/F from draft slot vs current performance delta.
    Outperforming draft slot = T (analytical, self-driven improvement).
    Underperforming = F (possible distraction, emotional, or circumstantial).
    Also: hunger_seed as proxy — high hunger (late round) + high skill = T grinder.
    """
    evidence = []
    signal = None

    draft = player.get('draft') or {}
    l2    = player.get('layer2_skill') or {}
    l1    = player.get('layer1_body') or {}

    draft_round  = draft.get('draft_round')
    hunger_seed  = draft.get('hunger_seed') or 50
    skill_score  = l2.get('skill_score') or 50
    snap_trend   = l1.get('snap_trend') or 'flat'

    # Draft slot vs performance delta
    if draft_round is not None:
        # Expected skill floor by round
        expected = {1: 65, 2: 55, 3: 45, 4: 40, 5: 35, 6: 30, 7: 25}
        floor = expected.get(min(draft_round, 7), 25)
        delta = skill_score - floor

        if delta >= 20:
            signal = 'T'
            evidence.append(
                f'Round {draft_round} pick outperforming by {delta:.0f} pts — '
                f'analytical self-improvement drive'
            )
        elif delta >= 10:
            signal = 'T'
            evidence.append(f'Round {draft_round} pick performing above draft slot — consistent T signal')
        elif delta <= -20:
            signal = 'F'
            evidence.append(
                f'Round {draft_round} pick underperforming by {abs(delta):.0f} pts — '
                f'possible distraction or emotional volatility'
            )
        elif delta <= -10:
            signal = 'F'
            evidence.append(f'Round {draft_round} pick below expected floor — F signal')
    else:
        # Undrafted — high hunger seed, if performing = strong T
        if skill_score >= 60:
            signal = 'T'
            evidence.append('Undrafted + performing — maximum T drive signal (earned everything)')
        elif skill_score >= 45:
            signal = 'T'
            evidence.append('Undrafted + holding roster spot — T persistence signal')
        else:
            signal = 'F'
            evidence.append('Undrafted + below average performance — F or circumstantial')

    # Hunger seed reinforcement
    if hunger_seed >= 70 and signal == 'T':
        evidence.append(f'High hunger seed ({hunger_seed}) confirms T drive — adversity as fuel')
    elif hunger_seed <= 30 and signal == 'F':
        evidence.append(f'Low hunger seed ({hunger_seed}) + underperformance — F pattern consistent')

    return signal, evidence


def infer_sn(player):
    """
    S/N from position archetype + college program.
    Position is the primary signal. College program is a secondary modifier.
    """
    evidence = []

    pos     = (player.get('position') or '').upper()
    college = (player.get('college') or '').lower().strip()

    signal = POS_SN.get(pos)

    if signal == 'S':
        evidence.append(f'{pos} — execution/technique role, detail-oriented (S)')
    elif signal == 'N':
        evidence.append(f'{pos} — pattern recognition/vision role (N)')
    else:
        signal = 'S'  # default to S if unknown position
        evidence.append(f'{pos} — unknown position, defaulting to S')

    # College modifier — small school players had to figure it out (N lean)
    if college and not any(elite in college for elite in ELITE_PROGRAMS):
        if signal == 'S':
            evidence.append(f'Non-elite program ({player.get("college")}) — self-made path, slight N modifier')
            # Don't flip S→N, just note it
        else:
            evidence.append(f'Non-elite program ({player.get("college")}) — reinforces N (had to read the game, not just execute a system)')
    elif college and any(elite in college for elite in ELITE_PROGRAMS):
        evidence.append(f'Elite program ({player.get("college")}) — system execution background reinforces {signal}')

    return signal, evidence


def infer_jp(player):
    """
    J/P from practice trajectory consistency.
    Steady Wed→Thu→Fri trajectory = J (structured, planned).
    Volatile or missing = P (adaptive, reactive, or insufficient data).
    Uses practice.json data if available via player injury block,
    otherwise falls back to snap_trend as proxy.
    """
    evidence = []
    signal = None

    l1 = player.get('layer1_body') or {}
    snap_trend  = l1.get('snap_trend') or 'flat'
    career_label = l1.get('career_label') or ''
    years_exp   = l1.get('years_exp') or 0

    # Snap trend as J/P proxy — consistent snap% = J, volatile = P
    if snap_trend == 'flat' and years_exp >= 3:
        signal = 'J'
        evidence.append('Consistent snap% over recent weeks — structured, reliable (J)')
    elif snap_trend == 'rising':
        signal = 'J'
        evidence.append('Rising snap% — disciplined improvement trajectory (J)')
    elif snap_trend == 'falling':
        signal = 'P'
        evidence.append('Falling snap% — role volatility, adaptive/reactive pattern (P)')
    else:
        signal = 'P'
        evidence.append('Insufficient snap data — defaulting to P (accumulating)')

    # Veterans with long careers lean J regardless of recent snap trend
    if years_exp >= 10 and career_label in ('late_career', 'end_of_career'):
        signal = 'J'
        evidence.append(f'{int(years_exp)}-year veteran — survived through structure and discipline (J)')

    return signal, evidence


def infer_type_string(ie, tf, sn, jp):
    """Standard MBTI order: E/I, S/N, T/F, J/P."""
    return f"{ie or '?'}{sn or '?'}{tf or '?'}{jp or '?'}"


def confidence_level(ie, tf, sn, jp):
    """How many axes are inferred vs unknown."""
    filled = sum(1 for x in [ie, tf, sn, jp] if x)
    if filled == 4:
        return 'medium'   # all inferred but from proxy data — never 'high' without behavioral data
    elif filled >= 2:
        return 'low'
    return 'minimal'


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f'infer_personality.py — {now_str}')

    data    = load_json(PLAYERS_FILE)
    players = data.get('players', [])
    print(f'  {len(players)} players loaded')

    # Load coaches for compat scoring
    coaches_data = load_json(COACHES_FILE) if os.path.exists(COACHES_FILE) else {}
    coaches_by_slug = {}
    for c in coaches_data.get('coaches', []):
        slug = c.get('team_slug')
        if slug:
            coaches_by_slug.setdefault(slug, []).append(c)

    # Index players by team for partner lookups
    players_by_team = {}
    for p in players:
        abbr = (p.get('team') or '').upper()
        players_by_team.setdefault(abbr, []).append(p)

    updated = 0
    type_counts = {}

    # Pass 1 — infer MBTI axes for all players first
    for player in players:
        ie, ie_ev = infer_ie(player)
        tf, tf_ev = infer_tf(player)
        sn, sn_ev = infer_sn(player)
        jp, jp_ev = infer_jp(player)

        mbti_type  = infer_type_string(ie, tf, sn, jp)
        confidence = confidence_level(ie, tf, sn, jp)

        player['layer4_personality'] = {
            'mbti_type':         mbti_type,
            'ie':                ie,
            'sn':                sn,
            'tf':                tf,
            'jp':                jp,
            'ie_evidence':       ie_ev,
            'sn_evidence':       sn_ev,
            'tf_evidence':       tf_ev,
            'jp_evidence':       jp_ev,
            'confidence':        confidence,
            'method':            'statistical_inference',
            'last_updated':      now_str,
        }

        # Role fit — position demands vs inferred type
        rf_score, rf_label, rf_ev = compute_role_fit(player)
        if rf_score is not None:
            player['layer4_personality']['role_fit_score'] = rf_score
            player['layer4_personality']['role_fit_label'] = rf_label
            player['layer4_personality']['role_fit_evidence'] = rf_ev

        type_counts[mbti_type] = type_counts.get(mbti_type, 0) + 1
        updated += 1

    # Pass 2 — compute team_compat_score now that all types are set
    compat_computed = 0
    for player in players:
        abbr        = (player.get('team') or '').upper()
        team_players = players_by_team.get(abbr, [])
        score = compute_team_compat(player, team_players, coaches_by_slug)
        if score is not None:
            player['layer4_personality']['team_compat_score'] = score
            compat_computed += 1

    data['players']      = players
    data['last_updated'] = now_str
    save_json(PLAYERS_FILE, data)

    # Update metadata
    meta = load_json(META_FILE)
    meta['last_personality_inference'] = now_str
    meta['personality_summary'] = {
        'total_players':    updated,
        'compat_computed':  compat_computed,
        'type_distribution': dict(sorted(type_counts.items(), key=lambda x: -x[1])[:10]),
    }
    save_json(META_FILE, meta)

    print(f'  layer4_personality written for {updated} players')
    print(f'  team_compat_score computed for {compat_computed} players')
    print(f'  Top types: {dict(sorted(type_counts.items(), key=lambda x: -x[1])[:8])}')


if __name__ == '__main__':
    main()
