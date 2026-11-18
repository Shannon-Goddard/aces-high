import json
import os
import math
from datetime import datetime, timezone

DATA_DIR        = os.path.join(os.path.dirname(__file__), '..', 'data')
LEDGER_FILE     = os.path.join(DATA_DIR, 'ledger.json')
PREDICTIONS_FILE = os.path.join(DATA_DIR, 'predictions.json')
STATS_FILE      = os.path.join(DATA_DIR, 'stats.json')
BLOG_FILE       = os.path.join(DATA_DIR, 'blog.json')
META_FILE       = os.path.join(DATA_DIR, 'metadata.json')

FLAT_BET        = 100.0   # flat bet amount per game

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

# ── PAYOUT CALCULATIONS ────────────────────────────────────────────────────

def american_to_payout(odds, wager):
    """
    Convert American odds + wager to total payout (wager + profit).
    -110 on $100 = $190.91 total returned
    +150 on $100 = $250.00 total returned
    """
    if odds is None:
        odds = -110   # default juice if not available
    if odds < 0:
        profit = wager * (100 / abs(odds))
    else:
        profit = wager * (odds / 100)
    return round(wager + profit, 2)

def confidence_to_wager(confidence, flat_bet=FLAT_BET, threshold=40):
    """
    Map confidence score to bet size.
    Below threshold = no bet.
    At threshold (40) = $40
    At 100 = $100
    Linear scale between threshold and 100.
    """
    if confidence < threshold:
        return 0
    return round(flat_bet * (confidence / 100), 2)

def calc_result(pick, actual_spread, actual_total, bet_type, pick_value):
    """
    Determine win/loss/push for a given bet.
    pick:       'home' or 'away' for spread/ml, 'over' or 'under' for total
    bet_type:   'spread', 'over_under', 'moneyline'
    pick_value: the spread or total we bet on
    actual_spread: final score difference (home - away)
    actual_total:  final combined score
    """
    if bet_type == 'spread':
        # pick_value is the spread given to the team we picked
        # e.g. pick='home', pick_value=-3.5 means home -3.5
        if pick == 'home':
            covered = actual_spread + pick_value
        else:
            covered = -(actual_spread) + pick_value
        if covered > 0:   return 'win'
        elif covered < 0: return 'loss'
        else:             return 'push'

    elif bet_type == 'over_under':
        if pick == 'over':
            if actual_total > pick_value:   return 'win'
            elif actual_total < pick_value: return 'loss'
            else:                           return 'push'
        else:
            if actual_total < pick_value:   return 'win'
            elif actual_total > pick_value: return 'loss'
            else:                           return 'push'

    elif bet_type == 'moneyline':
        # actual_spread > 0 means home won
        if pick == 'home':
            return 'win' if actual_spread > 0 else 'loss'
        else:
            return 'win' if actual_spread < 0 else 'loss'

    return None

# ── CONFIDENCE CALIBRATION ─────────────────────────────────────────────────

def get_confidence_bucket(confidence):
    if confidence < 50:   return '40_49'
    elif confidence < 60: return '50_59'
    elif confidence < 70: return '60_69'
    elif confidence < 80: return '70_79'
    elif confidence < 90: return '80_89'
    else:                 return '90_100'

# ── MODIFIER ACCURACY ──────────────────────────────────────────────────────

def update_modifier_accuracy(stats, modifiers_applied, result):
    """
    Track each modifier's accuracy independently.
    After 10 data points a modifier moves from hypothesis to validated.
    """
    if 'modifier_accuracy' not in stats:
        stats['modifier_accuracy'] = {}

    for mod_name, mod_value in modifiers_applied.items():
        if mod_name not in stats['modifier_accuracy']:
            stats['modifier_accuracy'][mod_name] = {
                'data_points': 0,
                'correct':     0,
                'accuracy':    None,
                'status':      'hypothesis',
                'note':        'Minimum 10 data points before validation'
            }
        entry = stats['modifier_accuracy'][mod_name]
        entry['data_points'] += 1
        if result in ('win',):
            entry['correct'] += 1
        if entry['data_points'] >= 10:
            entry['accuracy'] = round(entry['correct'] / entry['data_points'] * 100, 1)
            entry['status']   = 'validated' if entry['accuracy'] >= 55 else 'weak'

# ── SUMMARY UPDATER ────────────────────────────────────────────────────────

def update_summary(ledger):
    """Recalculate all summary stats from the full bets list."""
    flat = {
        'total_bets': 0, 'wins': 0, 'losses': 0, 'pushes': 0,
        'total_wagered': 0.0, 'total_returned': 0.0, 'net_pnl': 0.0, 'roi_pct': 0.0
    }
    weighted = {
        'total_bets': 0, 'wins': 0, 'losses': 0, 'pushes': 0,
        'total_wagered': 0.0, 'total_returned': 0.0, 'net_pnl': 0.0, 'roi_pct': 0.0
    }
    by_type = {
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

            # Flat
            flat['total_bets']     += 1
            flat['total_wagered']  += FLAT_BET
            flat[f"{result}s"]     += 1
            flat['total_returned'] += bet.get(f'flat_{bet_type}_returned', 0)

            # Confidence weighted
            wager = bet.get('confidence_wager', 0)
            if wager > 0:
                weighted['total_bets']     += 1
                weighted['total_wagered']  += wager
                weighted[f"{result}s"]     += 1
                weighted['total_returned'] += bet.get(f'weighted_{bet_type}_returned', 0)

            # By type
            if bet_type in by_type and result in by_type[bet_type]:
                by_type[bet_type][f"{result}s"] += 1

            # Calibration
            if bucket in calibration:
                calibration[bucket]['bets'] += 1
                if result == 'win':
                    calibration[bucket]['wins'] += 1

    # ROI
    for d in (flat, weighted):
        d['net_pnl'] = round(d['total_returned'] - d['total_wagered'], 2)
        d['roi_pct'] = round(
            (d['net_pnl'] / d['total_wagered'] * 100) if d['total_wagered'] > 0 else 0, 2
        )

    # Delta — which method is outperforming
    delta_note = None
    if flat['roi_pct'] != 0 or weighted['roi_pct'] != 0:
        if weighted['roi_pct'] > flat['roi_pct']:
            delta_note = 'confidence_weighted'
        elif flat['roi_pct'] > weighted['roi_pct']:
            delta_note = 'flat'
        else:
            delta_note = 'tied'

    ledger['summary']['flat']               = flat
    ledger['summary']['confidence_weighted'] = weighted
    ledger['summary']['by_bet_type']         = by_type
    ledger['summary']['delta'] = {
        'which_outperforms':    delta_note,
        'flat_roi':             flat['roi_pct'],
        'weighted_roi':         weighted['roi_pct'],
        'confidence_score_value': (
            'earning its weight' if weighted['roi_pct'] > flat['roi_pct']
            else 'not yet validated' if delta_note else None
        )
    }

# ── BLOG ENTRY ─────────────────────────────────────────────────────────────

def build_blog_entry(bet, prediction):
    home  = bet['home_team']
    away  = bet['away_team']
    pnl   = bet.get('flat_net_pnl', 0)
    result_str = 'Won' if pnl > 0 else 'Lost' if pnl < 0 else 'Push'
    return {
        'id':          bet['bet_id'],
        'date':        bet['game_date'],
        'week':        bet['week'],
        'matchup':     f"{away} @ {home}",
        'title':       f"{away} @ {home} — Week {bet['week']}: We {result_str} ${abs(pnl):.0f}",
        'result':      result_str,
        'confidence':  bet.get('confidence'),
        'pick':        prediction.get('pick', ''),
        'edge_score':  prediction.get('edge_score'),
        'lesson':      bet.get('lesson', ''),
        'actual_score': bet.get('actual_score', ''),
        'youtube_id':  None,
        'published':   True
    }

# ── MAIN ──────────────────────────────────────────────────────────────────

def main():
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"record_outcome.py — {now_str}")

    ledger      = load_json(LEDGER_FILE)
    predictions = load_json(PREDICTIONS_FILE)
    stats       = load_json(STATS_FILE)
    blog        = load_json(BLOG_FILE)

    open_bets = [b for b in ledger['bets'] if b['status'] == 'open']
    if not open_bets:
        print("No open bets to close.")
        return

    print(f"\n{len(open_bets)} open bet(s) to close.")
    print("Enter actual results for each game:\n")

    pred_by_game = {p['game_id']: p for p in predictions.get('predictions', [])}

    for bet in open_bets:
        game_id   = bet['game_id']
        home      = bet['home_team']
        away      = bet['away_team']
        print(f"  {away} @ {home} (Week {bet['week']})")

        # Collect actual scores
        try:
            home_score = int(input(f"    Home score ({home}): "))
            away_score = int(input(f"    Away score ({away}): "))
        except (ValueError, EOFError):
            print("    Skipping — invalid input")
            continue

        actual_spread = home_score - away_score   # positive = home won
        actual_total  = home_score + away_score

        bet['actual_score']  = f"{away} {away_score} @ {home} {home_score}"
        bet['actual_spread'] = actual_spread
        bet['actual_total']  = actual_total

        confidence       = bet.get('confidence', 50)
        confidence_wager = confidence_to_wager(confidence)
        bet['confidence_wager'] = confidence_wager

        # Score each bet type
        for bet_type in ('spread', 'over_under', 'moneyline'):
            pick       = bet.get(f'{bet_type}_pick')
            pick_value = bet.get(f'{bet_type}_value')
            odds       = bet.get(f'{bet_type}_odds', -110)

            if not pick:
                continue

            result = calc_result(pick, actual_spread, actual_total, bet_type, pick_value)
            bet[f'{bet_type}_result'] = result

            # Flat bet payout
            if result == 'win':
                flat_returned = american_to_payout(odds, FLAT_BET)
            elif result == 'push':
                flat_returned = FLAT_BET
            else:
                flat_returned = 0.0
            bet[f'flat_{bet_type}_returned'] = flat_returned
            bet[f'flat_{bet_type}_pnl']      = round(flat_returned - FLAT_BET, 2)

            # Confidence weighted payout
            if confidence_wager > 0:
                if result == 'win':
                    weighted_returned = american_to_payout(odds, confidence_wager)
                elif result == 'push':
                    weighted_returned = confidence_wager
                else:
                    weighted_returned = 0.0
                bet[f'weighted_{bet_type}_returned'] = weighted_returned
                bet[f'weighted_{bet_type}_pnl']      = round(weighted_returned - confidence_wager, 2)

            print(f"    {bet_type}: {pick} {pick_value} → {result.upper()} "
                  f"| flat P&L: ${bet[f'flat_{bet_type}_pnl']:+.2f} "
                  f"| weighted P&L: ${bet.get(f'weighted_{bet_type}_pnl', 0):+.2f}")

        # Flat net P&L across all bet types this game
        bet['flat_net_pnl'] = round(sum(
            bet.get(f'flat_{bt}_pnl', 0) for bt in ('spread', 'over_under', 'moneyline')
        ), 2)
        bet['weighted_net_pnl'] = round(sum(
            bet.get(f'weighted_{bt}_pnl', 0) for bt in ('spread', 'over_under', 'moneyline')
        ), 2)

        # Post mortem
        lesson = input(f"    One sentence lesson from this game: ").strip()
        bet['lesson']       = lesson
        bet['closed_at']    = now_str
        bet['status']       = 'closed'

        # Update modifier accuracy
        modifiers = bet.get('modifiers_applied', {})
        primary_result = bet.get('spread_result') or bet.get('moneyline_result')
        if primary_result and modifiers:
            update_modifier_accuracy(stats, modifiers, primary_result)

        # Build blog entry
        prediction = pred_by_game.get(game_id, {})
        blog_entry = build_blog_entry(bet, prediction)
        blog['posts'].append(blog_entry)

        print(f"    Closed. Flat P&L: ${bet['flat_net_pnl']:+.2f} | "
              f"Weighted P&L: ${bet['weighted_net_pnl']:+.2f}\n")

    # Recalculate all summary stats
    update_summary(ledger)

    # Set first bet date
    closed = [b for b in ledger['bets'] if b['status'] == 'closed']
    if closed and not ledger.get('first_bet_date'):
        ledger['first_bet_date'] = min(b['game_date'] for b in closed)

    save_json(LEDGER_FILE, ledger)
    save_json(STATS_FILE, stats)
    save_json(BLOG_FILE, blog)

    metadata = load_json(META_FILE)
    metadata['last_outcome_recorded'] = now_str
    save_json(META_FILE, metadata)

    # Print summary
    s = ledger['summary']
    print("\n── UPDATED SUMMARY ──────────────────────────────")
    print(f"Flat:     {s['flat']['wins']}W {s['flat']['losses']}L "
          f"| ROI: {s['flat']['roi_pct']:+.1f}% "
          f"| Net: ${s['flat']['net_pnl']:+.2f}")
    print(f"Weighted: {s['confidence_weighted']['wins']}W "
          f"{s['confidence_weighted']['losses']}L "
          f"| ROI: {s['confidence_weighted']['roi_pct']:+.1f}% "
          f"| Net: ${s['confidence_weighted']['net_pnl']:+.2f}")
    print(f"Outperforming: {s['delta']['which_outperforms']}")
    print(f"Confidence score: {s['delta']['confidence_score_value']}")

if __name__ == '__main__':
    main()
