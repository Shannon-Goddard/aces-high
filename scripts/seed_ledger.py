"""
seed_ledger.py
Reads predictions.json and seeds ledger.bets with open entries for every
BET-eligible prediction (confidence >= 40) not already in the ledger.
Run after predict.py.
"""
import json, os
from datetime import datetime, timezone

DATA_DIR         = os.path.join(os.path.dirname(__file__), '..', 'data')
PREDICTIONS_FILE = os.path.join(DATA_DIR, 'predictions.json')
LEDGER_FILE      = os.path.join(DATA_DIR, 'ledger.json')
ODDS_FILE        = os.path.join(DATA_DIR, 'odds.json')

CONFIDENCE_THRESHOLD = 40

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def get_consensus_ml(odds_data, game_id, home_team):
    """Pull consensus moneyline odds for the picked side from odds.json."""
    for game in odds_data.get('games', []):
        if game.get('id') != game_id:
            continue
        for bm in game.get('bookmakers', []):
            for market in bm.get('markets', []):
                if market.get('key') != 'h2h':
                    continue
                for outcome in market.get('outcomes', []):
                    if outcome.get('name') == home_team:
                        return outcome.get('price')
    return -110  # default juice

def build_bet_entry(p, odds_data):
    """Convert a prediction into a ledger bet entry."""
    is_home_pick = p['pick'] == p['home_team']
    spread_value = p['spread'] if is_home_pick else -p['spread']
    ml_odds      = get_consensus_ml(odds_data, p['game_id'], p['pick'])

    game_date = p['game_time'][:10] if p.get('game_time') else None

    return {
        'bet_id':          p['game_id'],
        'game_id':         p['game_id'],
        'week':            p['week'],
        'game_date':       game_date,
        'home_team':       p['home_team'],
        'away_team':       p['away_team'],
        'home_slug':       p.get('home_slug', ''),
        'away_slug':       p.get('away_slug', ''),
        'confidence':      p['confidence'],
        'edge_score':      p['edge_score'],
        'pick_team':       p['pick'],
        'pick_side':       'home' if is_home_pick else 'away',
        'pick_type':       p.get('pick_type', ''),
        # Spread bet
        'spread_pick':     'home' if is_home_pick else 'away',
        'spread_value':    spread_value,
        'spread_odds':     -110,
        'spread_result':   None,
        # Moneyline bet
        'moneyline_pick':  'home' if is_home_pick else 'away',
        'moneyline_value': None,
        'moneyline_odds':  ml_odds,
        'moneyline_result': None,
        # No over/under bet by default (spread-only system for now)
        'over_under_pick':  None,
        'over_under_value': None,
        'over_under_odds':  None,
        'over_under_result': None,
        # Modifiers snapshot
        'modifiers_applied': p.get('modifiers_applied', {}),
        # Lifecycle
        'status':      'open',
        'opened_at':   datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'closed_at':   None,
        'actual_score':  None,
        'actual_spread': None,
        'actual_total':  None,
        'lesson':        None,
    }

def main():
    predictions = load_json(PREDICTIONS_FILE)
    ledger      = load_json(LEDGER_FILE)
    odds_data   = load_json(ODDS_FILE) if os.path.exists(ODDS_FILE) else {'games': []}

    existing_ids = {b['game_id'] for b in ledger['bets']}
    added = 0

    for p in predictions.get('predictions', []):
        if p['confidence'] < CONFIDENCE_THRESHOLD:
            continue
        if p['game_id'] in existing_ids:
            continue
        ledger['bets'].append(build_bet_entry(p, odds_data))
        existing_ids.add(p['game_id'])
        added += 1
        print(f"  Seeded: {p['away_team']} @ {p['home_team']} | pick={p['pick']} | conf={p['confidence']}")

    save_json(LEDGER_FILE, ledger)
    print(f"seed_ledger.py done — {added} new bet(s) seeded, {len(existing_ids)} total open.")

if __name__ == '__main__':
    main()
