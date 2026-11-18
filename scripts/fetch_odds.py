import requests
import json
import os
from datetime import datetime, timezone

DATA_DIR   = os.path.join(os.path.dirname(__file__), '..', 'data')
ODDS_FILE  = os.path.join(DATA_DIR, 'odds.json')
META_FILE  = os.path.join(DATA_DIR, 'metadata.json')

# Free tier: 500 requests/month
# We fetch twice per week: Friday (opening) + Sunday morning (closing)
# ~32 requests/week, ~576/season — stays under free limit
API_KEY    = os.environ.get('ODDS_API_KEY', '')
BASE_URL   = 'https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds'
BOOKMAKERS = 'draftkings,fanduel,betmgm,caesars'
MARKETS    = 'spreads,totals,h2h'

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def fetch_odds():
    if not API_KEY:
        print("ERROR: ODDS_API_KEY not set in environment")
        return None
    params = {
        'apiKey':     API_KEY,
        'regions':    'us',
        'markets':    MARKETS,
        'bookmakers': BOOKMAKERS,
        'oddsFormat': 'american'
    }
    try:
        r = requests.get(BASE_URL, params=params, timeout=15)
        remaining = r.headers.get('x-requests-remaining', 'unknown')
        used      = r.headers.get('x-requests-used', 'unknown')
        print(f"  API requests used: {used} | remaining: {remaining}")
        if r.status_code != 200:
            print(f"  API error: {r.status_code} — {r.text[:200]}")
            return None
        return r.json(), remaining
    except Exception as e:
        print(f"  Fetch failed: {e}")
        return None, None

def consensus_line(bookmakers, market_key, home_team=None):
    """
    Average the line across all bookmakers for a consensus number.
    For spreads: only use the home team's point (negative = home favored).
    For totals: only use the Over point.
    For h2h: only use the home team's price.
    Returns consensus value and juice.
    """
    values = []
    juices = []
    for bm in bookmakers:
        for market in bm.get('markets', []):
            if market.get('key') != market_key:
                continue
            outcomes = market.get('outcomes', [])
            for o in outcomes:
                price = o.get('price')
                point = o.get('point')
                name  = o.get('name', '')

                if market_key == 'spreads':
                    # Only take home team side to get signed spread
                    if home_team and name != home_team:
                        continue
                    if point is not None:
                        values.append(point)
                    if price is not None:
                        juices.append(price)

                elif market_key == 'totals':
                    # Only take Over to get the total number
                    if name != 'Over':
                        continue
                    if point is not None:
                        values.append(point)
                    if price is not None:
                        juices.append(price)

                elif market_key == 'h2h':
                    # Only take home team ML
                    if home_team and name != home_team:
                        continue
                    if price is not None:
                        values.append(price)

    if not values:
        return None, None
    avg = round(sum(values) / len(values), 1)
    avg_juice = round(sum(juices) / len(juices), 1) if juices else None
    return avg, avg_juice

def build_game_entry(raw_game, snapshot_type, fetched_at):
    game_id      = raw_game.get('id', '')
    home         = raw_game.get('home_team', '')
    away         = raw_game.get('away_team', '')
    commence     = raw_game.get('commence_time', '')
    bookmakers   = raw_game.get('bookmakers', [])

    spread, spread_juice   = consensus_line(bookmakers, 'spreads', home)
    total, total_juice     = consensus_line(bookmakers, 'totals', home)
    home_ml, _             = consensus_line(bookmakers, 'h2h', home)

    # Per bookmaker breakdown
    books = {}
    for bm in bookmakers:
        bk = bm.get('key', '')
        books[bk] = {}
        for market in bm.get('markets', []):
            mk = market.get('key', '')
            books[bk][mk] = [
                {'name': o.get('name'), 'price': o.get('price'), 'point': o.get('point')}
                for o in market.get('outcomes', [])
            ]

    return {
        'game_id':      game_id,
        'home_team':    home,
        'away_team':    away,
        'commence_time': commence,
        'snapshot_type': snapshot_type,   # 'opening' or 'closing'
        'fetched_at':   fetched_at,
        'consensus': {
            'spread':       spread,
            'spread_juice': spread_juice,
            'total':        total,
            'total_juice':  total_juice,
            'home_ml':      home_ml
        },
        'bookmakers': books
    }

def detect_snapshot_type():
    """
    Friday fetch = opening line
    Sunday fetch = closing line
    """
    day = datetime.now(timezone.utc).weekday()
    # 4 = Friday, 6 = Sunday
    if day == 6:
        return 'closing'
    return 'opening'

def calc_line_movement(odds_data, game_id):
    """
    Find opening and closing snapshots for a game and calculate movement.
    Returns delta dict or None if both snapshots not yet available.
    """
    game_snaps = [
        g for g in odds_data.get('games', [])
        if g['game_id'] == game_id
    ]
    opening = next((g for g in game_snaps if g['snapshot_type'] == 'opening'), None)
    closing = next((g for g in game_snaps if g['snapshot_type'] == 'closing'), None)

    if not opening or not closing:
        return None

    spread_open  = opening['consensus'].get('spread')
    spread_close = closing['consensus'].get('spread')
    total_open   = opening['consensus'].get('total')
    total_close  = closing['consensus'].get('total')

    return {
        'spread_open':   spread_open,
        'spread_close':  spread_close,
        'spread_move':   round(spread_close - spread_open, 1) if spread_open and spread_close else None,
        'total_open':    total_open,
        'total_close':   total_close,
        'total_move':    round(total_close - total_open, 1) if total_open and total_close else None,
        'sharp_signal':  None   # populated by predict.py when movement diverges from our pick
    }

def main():
    now_utc    = datetime.now(timezone.utc)
    fetched_at = now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')
    snapshot   = detect_snapshot_type()
    print(f"fetch_odds.py — {fetched_at} [{snapshot}]")

    if not API_KEY:
        print("ODDS_API_KEY not set — skipping. Set secret in GitHub repo settings.")
        return

    result = fetch_odds()
    if result is None or result[0] is None:
        return
    raw_games, remaining = result

    odds_data = load_json(ODDS_FILE)
    if 'games' not in odds_data:
        odds_data['games'] = []

    new_entries = []
    for raw in raw_games:
        entry = build_game_entry(raw, snapshot, fetched_at)
        new_entries.append(entry)

        # Calculate line movement if both snapshots now exist
        movement = calc_line_movement(odds_data, entry['game_id'])
        if movement:
            entry['line_movement'] = movement
            print(f"  {entry['away_team']} @ {entry['home_team']} — "
                  f"spread moved {movement['spread_move']:+.1f} | "
                  f"total moved {movement['total_move']:+.1f}")
        else:
            entry['line_movement'] = None
            print(f"  {entry['away_team']} @ {entry['home_team']} — "
                  f"spread {entry['consensus']['spread']} | "
                  f"total {entry['consensus']['total']} [{snapshot}]")

    odds_data['games'].extend(new_entries)
    odds_data['last_updated'] = fetched_at
    odds_data['api_remaining'] = remaining
    save_json(ODDS_FILE, odds_data)

    metadata = load_json(META_FILE)
    metadata['last_odds_fetch'] = fetched_at
    metadata['odds_snapshot']   = snapshot
    metadata['api_remaining']   = remaining
    save_json(META_FILE, metadata)

    print(f"\nDone. {len(new_entries)} games stored [{snapshot}]")

if __name__ == '__main__':
    main()
