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

DATA_DIR     = os.path.join(os.path.dirname(__file__), '..', 'data')
PLAYERS_FILE = os.path.join(DATA_DIR, 'players.json')
META_FILE    = os.path.join(DATA_DIR, 'metadata.json')

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

    updated = 0
    type_counts = {}

    for player in players:
        ie, ie_ev = infer_ie(player)
        tf, tf_ev = infer_tf(player)
        sn, sn_ev = infer_sn(player)
        jp, jp_ev = infer_jp(player)

        mbti_type = infer_type_string(ie, tf, sn, jp)
        confidence = confidence_level(ie, tf, sn, jp)

        player['layer4_personality'] = {
            'mbti_type':    mbti_type,
            'ie':           ie,
            'sn':           sn,
            'tf':           tf,
            'jp':           jp,
            'ie_evidence':  ie_ev,
            'sn_evidence':  sn_ev,
            'tf_evidence':  tf_ev,
            'jp_evidence':  jp_ev,
            'confidence':   confidence,
            'method':       'statistical_inference',
            'last_updated': now_str,
        }

        type_counts[mbti_type] = type_counts.get(mbti_type, 0) + 1
        updated += 1

    data['players']      = players
    data['last_updated'] = now_str
    save_json(PLAYERS_FILE, data)

    # Update metadata
    meta = load_json(META_FILE)
    meta['last_personality_inference'] = now_str
    meta['personality_summary'] = {
        'total_players': updated,
        'type_distribution': dict(sorted(type_counts.items(), key=lambda x: -x[1])[:10]),
    }
    save_json(META_FILE, meta)

    print(f'  layer4_personality written for {updated} players')
    print(f'  Top types: {dict(sorted(type_counts.items(), key=lambda x: -x[1])[:8])}')


if __name__ == '__main__':
    main()
