"""
update_blog.py — Generate blog.json from closed bets + predictions.

Reads:  data/ledger.json, data/predictions.json
Writes: data/blog.json

Run: after record_outcome.py, or any time to regenerate all posts.
Safe to re-run — rebuilds from scratch each time.
"""

import json
import os
from datetime import datetime, timezone

DATA_DIR         = os.path.join(os.path.dirname(__file__), '..', 'data')
LEDGER_FILE      = os.path.join(DATA_DIR, 'ledger.json')
PREDICTIONS_FILE = os.path.join(DATA_DIR, 'predictions.json')
BLOG_FILE        = os.path.join(DATA_DIR, 'blog.json')
META_FILE        = os.path.join(DATA_DIR, 'metadata.json')


def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


# ── MODIFIER DISPLAY NAMES ────────────────────────────────────────────────────
# Maps the short strings written by auto_lesson() to readable labels.
MOD_LABELS = {
    'injury flag':       'Injury flag fired',
    'silence bonus':     'Silence bonus — no news, locked in',
    'distraction flag':  'Distraction flag fired',
    'wind flag':         'Wind >20mph — passing game hit',
    'precip flag':       'Rain/snow — passing game hit',
    'cold flag':         'Extreme cold — kicker risk',
    'divisional game':   'Divisional game — favorite edge trimmed ×0.97',
    'rematch':           'Rematch — favorite edge trimmed ×0.95',
    'scheme transition': 'Scheme transition — role fit suspended',
}


def _parse_fired_modifiers(lesson_text):
    """
    Extract the fired modifiers list from the auto_lesson() text.
    Returns list of display strings, or [] if none found.
    """
    if not lesson_text:
        return []
    marker = 'Modifiers fired: '
    idx = lesson_text.find(marker)
    if idx == -1:
        return []
    segment = lesson_text[idx + len(marker):]
    # Ends at the next period
    end = segment.find('.')
    if end != -1:
        segment = segment[:end]
    raw = [m.strip() for m in segment.split(',') if m.strip()]
    return [MOD_LABELS.get(m, m) for m in raw]


def _result_sentence(bet, spread_result):
    """One-sentence result summary."""
    pick_side = bet.get('spread_pick', '')
    home      = bet['home_team']
    away      = bet['away_team']
    pick_team = home if pick_side == 'home' else away
    conf      = bet.get('confidence', 50)
    score     = bet.get('actual_score', '')
    pnl       = bet.get('flat_net_pnl', 0)
    pnl_str   = f"${abs(pnl):.0f} {'profit' if pnl > 0 else 'loss' if pnl < 0 else 'push'}"

    if spread_result == 'win':
        return f"{pick_team} covered. {pnl_str} at confidence {conf}. Final: {score}."
    elif spread_result == 'loss':
        return f"{pick_team} did not cover. {pnl_str} at confidence {conf}. Final: {score}."
    elif spread_result == 'push':
        return f"Push on the spread. Confidence was {conf}. Final: {score}."
    return f"Final: {score}."


def _score_delta_sentence(bet, prediction):
    """How far off our composite scores were from the actual result."""
    if not prediction:
        return None
    our_home = prediction.get('home_score', 0)
    our_away = prediction.get('away_score', 0)
    our_diff = round(our_home - our_away, 1)
    actual   = bet.get('actual_spread', 0)
    delta    = round(actual - our_diff, 1)
    sign     = '+' if our_diff >= 0 else ''
    asign    = '+' if actual >= 0 else ''
    if abs(delta) <= 3:
        return f"Score model was close — predicted home {sign}{our_diff}, actual {asign}{actual} (off by {abs(delta):.1f} pts)."
    direction = 'overestimated home' if delta < 0 else 'underestimated home'
    return f"Score model {direction} — predicted {sign}{our_diff}, actual {asign}{actual} (off by {abs(delta):.1f} pts)."


def _lesson_sentence(lesson_text):
    """
    Extract just the lesson/miss sentence from auto_lesson() output,
    stripping the result and score delta sentences already shown separately.
    """
    if not lesson_text:
        return None
    # The lesson is the HIGH CONFIDENCE MISS or moderate miss sentence at the end
    for marker in ('HIGH CONFIDENCE MISS', 'Moderate confidence miss'):
        if marker in lesson_text:
            idx = lesson_text.find(marker)
            return lesson_text[idx:].strip()
    return None


def build_post(bet, prediction):
    """
    Build a rich blog post dict from a closed bet + its prediction.
    Called by both update_blog.py and record_outcome.py.
    """
    home         = bet['home_team']
    away         = bet['away_team']
    pnl          = bet.get('flat_net_pnl', 0)
    result_str   = 'Won' if pnl > 0 else 'Lost' if pnl < 0 else 'Push'
    spread_result = bet.get('spread_result') or bet.get('spread_result_cached')
    lesson_text  = bet.get('lesson', '')

    # Narrative blocks
    result_line  = _result_sentence(bet, spread_result)
    delta_line   = _score_delta_sentence(bet, prediction)
    lesson_line  = _lesson_sentence(lesson_text)
    fired_mods   = _parse_fired_modifiers(lesson_text)

    # Pick type label
    pick_type    = prediction.get('pick_type', '') if prediction else ''
    pick_label   = f"{prediction.get('pick', '')} ({pick_type})" if prediction else bet.get('pick_team', '')

    # Breakdown scores for context
    home_score_comp = (prediction.get('home_breakdown') or {}).get('composite') if prediction else None
    away_score_comp = (prediction.get('away_breakdown') or {}).get('composite') if prediction else None

    return {
        'id':              bet['bet_id'],
        'date':            bet.get('game_date', ''),
        'week':            bet.get('week', 0),
        'season':          bet.get('season', 2026),
        'matchup':         f"{away} @ {home}",
        'home_team':       home,
        'away_team':       away,
        'home_slug':       bet.get('home_slug', ''),
        'away_slug':       bet.get('away_slug', ''),
        'title':           f"{away} @ {home} — Week {bet.get('week', '?')}: We {result_str} ${abs(pnl):.0f}",
        'result':          result_str,
        'spread_result':   spread_result,
        'confidence':      bet.get('confidence'),
        'pick':            pick_label,
        'pick_type':       pick_type,
        'edge_score':      prediction.get('edge_score') if prediction else None,
        'spread':          prediction.get('spread') if prediction else None,
        'actual_score':    bet.get('actual_score', ''),
        'flat_pnl':        pnl,
        'weighted_pnl':    bet.get('weighted_net_pnl', 0),
        # Narrative
        'result_line':     result_line,
        'delta_line':      delta_line,
        'lesson_line':     lesson_line,
        'fired_modifiers': fired_mods,
        # Composite scores for context
        'home_composite':  home_score_comp,
        'away_composite':  away_score_comp,
        # Raw lesson text (kept for record_outcome.py compatibility)
        'lesson':          lesson_text,
        'youtube_id':      None,
        'published':       True,
        'generated_at':    datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
    }


def main():
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f'update_blog.py — {now_str}')

    ledger      = load_json(LEDGER_FILE)
    predictions = load_json(PREDICTIONS_FILE)

    closed_bets  = [b for b in ledger.get('bets', []) if b.get('status') == 'closed']
    pred_by_game = {p['game_id']: p for p in predictions.get('predictions', [])}

    if not closed_bets:
        print('  No closed bets — blog.json unchanged.')
        # Write empty shell so blog.html has something to load
        save_json(BLOG_FILE, {'last_updated': now_str, 'posts': []})
        return

    posts = []
    for bet in sorted(closed_bets, key=lambda b: b.get('game_date', ''), reverse=True):
        prediction = pred_by_game.get(bet.get('game_id', ''))
        posts.append(build_post(bet, prediction))

    save_json(BLOG_FILE, {'last_updated': now_str, 'posts': posts})

    meta = load_json(META_FILE)
    meta['last_blog_update'] = now_str
    save_json(META_FILE, meta)

    wins   = sum(1 for p in posts if p['result'] == 'Won')
    losses = sum(1 for p in posts if p['result'] == 'Lost')
    print(f'  {len(posts)} posts written ({wins}W {losses}L)')
    for p in posts[:5]:
        print(f'    Week {p["week"]} | {p["matchup"]} | {p["result"]} | conf {p["confidence"]}')


if __name__ == '__main__':
    main()
