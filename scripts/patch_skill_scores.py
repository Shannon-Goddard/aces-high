"""
patch_skill_scores.py
Applies fallback + OL/LS skill scores to players currently missing layer2_skill.
Runs against the existing players.json without needing nflverse.
"""
import json, os, re

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PATH     = os.path.join(DATA_DIR, 'players.json')

OL_POS = {'OL', 'T', 'G', 'C', 'OT', 'OG'}

def safe(val):
    try:
        v = float(val)
        return None if (v != v) else v  # NaN check
    except (TypeError, ValueError):
        return None

def fallback(layer1, draft):
    body_score  = (layer1 or {}).get('body_score') or 50.0
    snap_pct    = (layer1 or {}).get('snap_pct')   or 0.0
    hunger_seed = (draft  or {}).get('hunger_seed') or 50.0
    snap_trend  = (layer1 or {}).get('snap_trend', 'flat')
    snap_score  = min(100.0, snap_pct * 100.0)
    trend_mod   = 5.0 if snap_trend == 'rising' else -5.0 if snap_trend == 'falling' else 0.0
    score = round(body_score * 0.4 + snap_score * 0.4 + hunger_seed * 0.2 + trend_mod, 1)
    return {
        'skill_score':  max(0.0, min(100.0, score)),
        'body_proxy':   round(body_score, 1),
        'snap_proxy':   round(snap_score, 1),
        'hunger_proxy': hunger_seed,
        'source':       'fallback'
    }

def ol_score(layer1, draft):
    snap_pct   = (layer1 or {}).get('snap_pct')   or 0.0
    years_exp  = (layer1 or {}).get('years_exp')  or 0.0
    draft_round = (draft or {}).get('draft_round')
    snap_score = min(100.0, snap_pct * 100.0)
    draft_score = 75.0 if draft_round and draft_round <= 2 else \
                  55.0 if draft_round and draft_round <= 4 else 45.0
    longevity   = min(90.0, 40.0 + years_exp * 4.0)
    parts = [s for s in [snap_score, draft_score, longevity] if s is not None]
    score = round(sum(parts) / len(parts), 1) if parts else 50.0
    return {
        'skill_score':     max(0.0, min(100.0, score)),
        'snap_score':      round(snap_score, 1),
        'draft_score':     draft_score,
        'longevity_score': round(longevity, 1),
        'source':          'ol_proxy'
    }

def ls_score(layer1):
    snap_pct  = (layer1 or {}).get('snap_pct')  or 0.0
    years_exp = (layer1 or {}).get('years_exp') or 0.0
    score = round(50.0 + min(30.0, snap_pct * 30.0) + min(20.0, years_exp * 2.0), 1)
    return {
        'skill_score': max(0.0, min(100.0, score)),
        'snap_pct':    snap_pct,
        'years_exp':   years_exp,
        'source':      'ls_proxy'
    }

d = json.load(open(PATH, encoding='utf-8'))
players = d['players']

patched = 0
for p in players:
    if p.get('layer2_skill'):
        continue
    pos    = (p.get('position') or '').upper()
    layer1 = p.get('layer1_body') or {}
    draft  = p.get('draft') or {}

    if pos in OL_POS:
        p['layer2_skill'] = ol_score(layer1, draft)
    elif pos == 'LS':
        p['layer2_skill'] = ls_score(layer1)
    else:
        p['layer2_skill'] = fallback(layer1, draft)
    patched += 1

print(f"Patched {patched} players.")
print(f"Still missing: {sum(1 for p in players if not p.get('layer2_skill'))}")

# Sanitize NaN just in case
def sanitize(obj):
    if isinstance(obj, float) and obj != obj: return None
    if isinstance(obj, dict):  return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [sanitize(v) for v in obj]
    return obj

with open(PATH, 'w', encoding='utf-8') as f:
    json.dump(sanitize(d), f, indent=2)
print("Saved.")
