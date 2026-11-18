import json
import os
from datetime import datetime, timezone

DATA_DIR         = os.path.join(os.path.dirname(__file__), '..', 'data')
LEDGER_FILE      = os.path.join(DATA_DIR, 'ledger.json')
PREDICTIONS_FILE = os.path.join(DATA_DIR, 'predictions.json')
SCORES_FILE      = os.path.join(DATA_DIR, 'scores.json')
STATS_FILE       = os.path.join(DATA_DIR, 'stats.json')
BLOG_FILE        = os.path.join(DATA_DIR, 'blog.json')
META_FILE        = os.path.join(DATA_DIR, 'metadata.json')

FLAT_BET = 100.0

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

# ── PAYOUT ─────────────────────────────────────────────────────────────────

def american_to_payout(odds, wager):
    if odds is None:
        odds = -110
    if odds < 0:
        profit = wager * (100 / abs(odds))
    else:
        profit = wager * (odds / 100)
    return round(wager + profit, 2)

def confidence_to_wager(confidence, flat_bet=FLAT_BET, threshold=40):
    if confidence < threshold:
        return 0
    return round(flat_bet * (confidence / 100), 2)

# ── RESULT CALC ────────────────────────────────────────────────────────────

def calc_result(pick, actual_spread, actual_total, bet_type, pick_value):
    if bet_type == 'spread':
        covered = (actual_spread + pick_value) if pick == 'home' else (-actual_spread + pick_value)
        if covered > 0:   return 'win'
        elif covered < 0: return 'loss'
        else:             return 'push'
    elif bet_type == 'over_under':
        if pick == 'over':
            return 'win' if actual_total > pick_value else ('loss' if actual_total < pick_value else 'push')
        else:
            return 'win' if actual_total < pick_value else ('loss' if actual_total > pick_value else 'push')
    elif bet_type == 'moneyline':
        if pick == 'home':
            return 'win' if actual_spread > 0 else 'loss'
        else:
            return 'win' if actual_spread < 0 else 'loss'
    return None

# ── CALIBRATION ────────────────────────────────────────────────────────────

def get_confidence_bucket(confidence):
    if confidence < 50:   return '40_49'
    elif confidence < 60: return '50_59'
    elif confidence < 70: return '60_69'
    elif confidence < 80: return '70_79'
    elif confidence < 90: return '80_89'
    else:                 return '90_100'

def update_modifier_accuracy(stats, modifiers_applied, result):
    if 'modifier_accuracy' not in stats:
        stats['modifier_accuracy'] = {}
    for mod_name, mod_value in modifiers_applied.items():
        if mod_name not in stats['modifier_accuracy']:
            stats['modifier_accuracy'][mod_name] = {
                'data_points': 0, 'correct': 0, 'accuracy': None,
                'status': 'hypothesis', 'note': 'Minimum 10 data points before validation'
            }
        entry = stats['modifier_accuracy'][mod_name]
        entry['data_points'] += 1
        if result == 'win':
            entry['correct'] += 1
        if entry['data_points'] >= 10:
            entry['accuracy'] = round(entry['correct'] / entry['data_points'] * 100, 1)
            entry['status']   = 'validated' if entry['accuracy'] >= 55 else 'weak'

# ── SUMMARY ────────────────────────────────────────────────────────────────

def update_summary(ledger):
    flat     = {'total_bets': 0, 'wins': 0, 'losses': 0, 'pushes': 0,
                'total_wagered': 0.0, 'total_returned': 0.0, 'net_pnl': 0.0, 'roi_pct': 0.0}
    weighted = {'total_bets': 0, 'wins': 0, 'losses': 0, 'pushes': 0,
                'total_wagered': 0.0, 'total_returned': 0.0, 'net_pnl': 0.0, 'roi_pct': 0.0}
    by_type  = {
        'spread':     {'wins': 0, 'losses': 0, 'pushes': 0},
        'over_under': {'wins': 0, 'losses': 0, 'pushes': 0},
        'moneyline':  {'wins': 0, 'losses': 0}
    }
    calibration = ledger['summary']['confidence_calibration']['buckets']

    for bet in ledger['bets']:
        if bet['status'] != 'closed':
            continue
        confidence = bet.get('confidence', 50)
        bucket     = get_confidence_bucket(confidence)

        for bet_type in ('spread', 'over_under', 'moneyline'):
            result = bet.get(f'{bet_type}_result')
            if result is None:
                continue
            flat['total_bets']     += 1
            flat['total_wagered']  += FLAT_BET
            flat[f'{result}s']     += 1
            flat['total_returned'] += bet.get(f'flat_{bet_type}_returned', 0)

            wager = bet.get('confidence_wager', 0)
            if wager > 0:
                weighted['total_bets']     += 1
                weighted['total_wagered']  += wager
                weighted[f'{result}s']     += 1
                weighted['total_returned'] += bet.get(f'weighted_{bet_type}_returned', 0)

            if bet_type in by_type and result in by_type[bet_type]:
                by_type[bet_type][f'{result}s'] += 1

            if bucket in calibration:
                calibration[bucket]['bets'] += 1
                if result == 'win':
                    calibration[bucket]['wins'] += 1

    for d in (flat, weighted):
        d['net_pnl'] = round(d['total_returned'] - d['total_wagered'], 2)
        d['roi_pct'] = round((d['net_pnl'] / d['total_wagered'] * 100) if d['total_wagered'] > 0 else 0, 2)

    delta_note = None
    if flat['roi_pct'] != 0 or weighted['roi_pct'] != 0:
        if weighted['roi_pct'] > flat['roi_pct']:
            delta_note = 'confidence_weighted'
        elif flat['roi_pct'] > weighted['roi_pct']:
            delta_note = 'flat'
        else:
            delta_note = 'tied'

    ledger['summary']['flat']                = flat
    ledger['summary']['confidence_weighted'] = weighted
    ledger['summary']['by_bet_type']         = by_type
    ledger['summary']['delta'] = {
        'which_outperforms':      delta_note,
        'flat_roi':               flat['roi_pct'],
        'weighted_roi':           weighted['roi_pct'],
        'confidence_score_value': (
            'earning its weight' if weighted['roi_pct'] > flat['roi_pct']
            else 'not yet validated' if delta_note else None
        )
    }

# ── AUTO LESSON ──────────────────────────────────────────────────────────────────────

def auto_lesson(bet, spread_result, ml_result, prediction=None):
    """
    Generate a meaningful lesson from a closed bet.
    Captures: result, score delta vs our prediction, which modifiers fired,
    and what the system missed. This is the learning layer.
    """
    home       = bet['home_team']
    away       = bet['away_team']
    pick_side  = bet.get('spread_pick', '')
    pick_team  = home if pick_side == 'home' else away
    score      = bet.get('actual_score', '')
    confidence = bet.get('confidence', 50)
    result     = spread_result or ml_result

    parts = []

    # Result
    if result == 'win':
        parts.append(f"{pick_team} covered as predicted (conf {confidence}). Final: {score}.")
    elif result == 'loss':
        parts.append(f"{pick_team} failed to cover (conf {confidence}). Final: {score}.")
    elif result == 'push':
        parts.append(f"Push on the spread (conf {confidence}). Final: {score}.")
    else:
        parts.append(f"Game complete. Final: {score}.")

    # Score delta vs our prediction
    if prediction:
        our_home = prediction.get('home_score', 0)
        our_away = prediction.get('away_score', 0)
        our_diff = round(our_home - our_away, 1)
        actual   = bet.get('actual_spread', 0)
        delta    = round(actual - our_diff, 1)
        direction = 'overestimated home' if delta < -3 else 'underestimated home' if delta > 3 else 'close to predicted'
        parts.append(
            f"Score delta: predicted home {'+' if our_diff >= 0 else ''}{our_diff}, "
            f"actual home {'+' if actual >= 0 else ''}{actual} "
            f"({direction}, off by {abs(delta):.1f} pts)."
        )

        # Which modifiers fired
        bd    = prediction.get('home_breakdown') or {}
        fired = []
        if bd.get('injury_flag'):      fired.append('injury flag')
        if bd.get('silence_bonus'):    fired.append('silence bonus')
        if bd.get('distraction_flag'): fired.append('distraction flag')
        wx = (prediction.get('modifiers_applied') or {}).get('weather') or {}
        if wx.get('wind_flag'):        fired.append('wind flag')
        if wx.get('precip_flag'):      fired.append('precip flag')
        if wx.get('cold_flag'):        fired.append('cold flag')
        compat = bd.get('compat')
        rf     = bd.get('role_fit_mult')
        hcmf   = bd.get('hc_market_mult')
        if compat is not None and abs(compat - 50) > 10:
            fired.append(f"compat {compat:.0f}")
        if rf is not None and abs(rf - 1.0) > 0.02:
            fired.append(f"role fit {rf:.3f}")
        if hcmf is not None and abs(hcmf - 1.0) > 0.005:
            fired.append(f"hc market fit {hcmf:.3f}")
        if prediction.get('divisional_game'):
            fired.append('divisional game')
        if prediction.get('rematch'):
            fired.append('rematch')
        # Scheme transition: check if any player on home team was in transition
        home_bd = prediction.get('home_breakdown') or {}
        if home_bd.get('scheme_transition_active'):
            fired.append('scheme transition')
        if fired:
            parts.append(f"Modifiers fired: {', '.join(fired)}.")

    # Flag high-confidence misses — most valuable lessons
    if result == 'loss' and confidence >= 70:
        parts.append("HIGH CONFIDENCE MISS — review what the system didn't see.")
    elif result == 'loss' and confidence >= 55:
        parts.append("Moderate confidence miss — check if a modifier was absent or misfired.")

    return ' '.join(parts)

# ── BLOG ───────────────────────────────────────────────────────────────────

def build_blog_entry(bet, prediction):
    home       = bet['home_team']
    away       = bet['away_team']
    pnl        = bet.get('flat_net_pnl', 0)
    result_str = 'Won' if pnl > 0 else 'Lost' if pnl < 0 else 'Push'
    return {
        'id':           bet['bet_id'],
        'date':         bet['game_date'],
        'week':         bet['week'],
        'matchup':      f"{away} @ {home}",
        'title':        f"{away} @ {home} — Week {bet['week']}: We {result_str} ${abs(pnl):.0f}",
        'result':       result_str,
        'confidence':   bet.get('confidence'),
        'pick':         prediction.get('pick', ''),
        'edge_score':   prediction.get('edge_score'),
        'lesson':       bet.get('lesson', ''),
        'actual_score': bet.get('actual_score', ''),
        'youtube_id':   None,
        'published':    True
    }

# ── MATCH BET → SCORE ──────────────────────────────────────────────────────

def find_score(bet, scores_games):
    """Try to match a bet to a score entry by slug pair."""
    home_slug = bet.get('home_slug', '')
    away_slug = bet.get('away_slug', '')

    # Primary key: away@home
    key = f"{away_slug}@{home_slug}"
    if key in scores_games:
        return scores_games[key]

    # Fallback: scan all games for matching slugs
    for game in scores_games.values():
        if game.get('home_slug') == home_slug and game.get('away_slug') == away_slug:
            return game

    return None

# ── MAIN ───────────────────────────────────────────────────────────────────

def main():
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"record_outcome.py — {now_str}")

    ledger      = load_json(LEDGER_FILE)
    predictions = load_json(PREDICTIONS_FILE)
    scores_data = load_json(SCORES_FILE)
    stats       = load_json(STATS_FILE)
    blog        = load_json(BLOG_FILE)

    scores_games = scores_data.get('games', {})
    open_bets    = [b for b in ledger['bets'] if b['status'] == 'open']

    if not open_bets:
        print("No open bets to close.")
        return

    pred_by_game = {p['game_id']: p for p in predictions.get('predictions', [])}
    closed_count = 0
    skipped      = []

    for bet in open_bets:
        score = find_score(bet, scores_games)

        if not score or score.get('state') != 'post':
            skipped.append(f"{bet.get('away_team')} @ {bet.get('home_team')}")
            continue

        home_score    = score['home_score']
        away_score    = score['away_score']
        actual_spread = home_score - away_score
        actual_total  = home_score + away_score

        bet['actual_score']  = f"{bet['away_team']} {away_score} @ {bet['home_team']} {home_score}"
        bet['actual_spread'] = actual_spread
        bet['actual_total']  = actual_total

        confidence       = bet.get('confidence', 50)
        confidence_wager = confidence_to_wager(confidence)
        bet['confidence_wager'] = confidence_wager

        spread_result = None
        for bet_type in ('spread', 'over_under', 'moneyline'):
            pick       = bet.get(f'{bet_type}_pick')
            pick_value = bet.get(f'{bet_type}_value')
            odds       = bet.get(f'{bet_type}_odds', -110)

            if not pick:
                continue

            result = calc_result(pick, actual_spread, actual_total, bet_type, pick_value)
            bet[f'{bet_type}_result'] = result
            if bet_type == 'spread':
                spread_result = result

            if result == 'win':
                flat_returned = american_to_payout(odds, FLAT_BET)
            elif result == 'push':
                flat_returned = FLAT_BET
            else:
                flat_returned = 0.0
            bet[f'flat_{bet_type}_returned'] = flat_returned
            bet[f'flat_{bet_type}_pnl']      = round(flat_returned - FLAT_BET, 2)

            if confidence_wager > 0:
                if result == 'win':
                    weighted_returned = american_to_payout(odds, confidence_wager)
                elif result == 'push':
                    weighted_returned = confidence_wager
                else:
                    weighted_returned = 0.0
                bet[f'weighted_{bet_type}_returned'] = weighted_returned
                bet[f'weighted_{bet_type}_pnl']      = round(weighted_returned - confidence_wager, 2)

        bet['flat_net_pnl'] = round(sum(
            bet.get(f'flat_{bt}_pnl', 0) for bt in ('spread', 'over_under', 'moneyline')
        ), 2)
        bet['weighted_net_pnl'] = round(sum(
            bet.get(f'weighted_{bt}_pnl', 0) for bt in ('spread', 'over_under', 'moneyline')
        ), 2)

        ml_result      = bet.get('moneyline_result')
        prediction     = pred_by_game.get(bet['game_id'], {})
        bet['lesson']  = auto_lesson(bet, spread_result, ml_result, prediction)
        bet['closed_at'] = now_str
        bet['status']    = 'closed'

        modifiers = bet.get('modifiers_applied', {})
        primary   = spread_result or ml_result
        if primary and modifiers:
            update_modifier_accuracy(stats, modifiers, primary)

        prediction = pred_by_game.get(bet['game_id'], {})
        blog['posts'].append(build_blog_entry(bet, prediction))

        pnl_str = f"${bet['flat_net_pnl']:+.2f}"
        print(f"  CLOSED  {bet['actual_score']}  |  spread={spread_result}  |  flat P&L {pnl_str}")
        closed_count += 1

    if skipped:
        print(f"\n  SKIPPED (not final yet): {', '.join(skipped)}")

    if closed_count == 0:
        print("No bets closed — no matching final scores found.")
        return

    update_summary(ledger)

    closed = [b for b in ledger['bets'] if b['status'] == 'closed']
    if closed and not ledger.get('first_bet_date'):
        ledger['first_bet_date'] = min(b['game_date'] for b in closed)

    save_json(LEDGER_FILE, ledger)
    save_json(STATS_FILE, stats)
    save_json(BLOG_FILE, blog)

    metadata = load_json(META_FILE)
    metadata['last_outcome_recorded'] = now_str
    save_json(META_FILE, metadata)

    s = ledger['summary']
    print(f"\n── SUMMARY ──────────────────────────────────────")
    print(f"Flat:     {s['flat']['wins']}W {s['flat']['losses']}L | ROI: {s['flat']['roi_pct']:+.1f}% | Net: ${s['flat']['net_pnl']:+.2f}")
    print(f"Weighted: {s['confidence_weighted']['wins']}W {s['confidence_weighted']['losses']}L | ROI: {s['confidence_weighted']['roi_pct']:+.1f}% | Net: ${s['confidence_weighted']['net_pnl']:+.2f}")
    print(f"Outperforming: {s['delta']['which_outperforms']}")

if __name__ == '__main__':
    main()
