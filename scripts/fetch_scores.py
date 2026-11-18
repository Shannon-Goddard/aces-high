import json
import os
import re
import urllib.request
from datetime import datetime, timezone

DATA_DIR   = os.path.join(os.path.dirname(__file__), '..', 'data')
SCORES_FILE = os.path.join(DATA_DIR, 'scores.json')

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

# Map ESPN team abbreviations → our slugs
ESPN_SLUG_MAP = {
    'ARI': 'ari', 'ATL': 'atl', 'BAL': 'bal', 'BUF': 'buf',
    'CAR': 'car', 'CHI': 'chi', 'CIN': 'cin', 'CLE': 'cle',
    'DAL': 'dal', 'DEN': 'den', 'DET': 'det', 'GB':  'gb',
    'HOU': 'hou', 'IND': 'ind', 'JAX': 'jax', 'KC':  'kc',
    'LAC': 'lac', 'LAR': 'lar', 'LV':  'lv',  'MIA': 'mia',
    'MIN': 'min', 'NE':  'ne',  'NO':  'no',  'NYG': 'nyg',
    'NYJ': 'nyj', 'PHI': 'phi', 'PIT': 'pit', 'SEA': 'sea',
    'SF':  'sf',  'TB':  'tb',  'TEN': 'ten', 'WSH': 'wsh',
}

def fetch_url(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def parse_score(competitor):
    try:
        return int(competitor.get('score', 0))
    except (ValueError, TypeError):
        return 0

def fetch_scores():
    data = fetch_url(ESPN_SCOREBOARD)
    events = data.get('events', [])
    results = {}

    for event in events:
        status = event.get('status', {})
        state  = status.get('type', {}).get('state', '')  # pre / in / post

        comps = event.get('competitions', [{}])[0]
        competitors = comps.get('competitors', [])
        if len(competitors) < 2:
            continue

        # ESPN always has home/away in competitors
        home = next((c for c in competitors if c.get('homeAway') == 'home'), None)
        away = next((c for c in competitors if c.get('homeAway') == 'away'), None)
        if not home or not away:
            continue

        home_abbr = home.get('team', {}).get('abbreviation', '')
        away_abbr = away.get('team', {}).get('abbreviation', '')
        home_slug = ESPN_SLUG_MAP.get(home_abbr, home_abbr.lower())
        away_slug = ESPN_SLUG_MAP.get(away_abbr, away_abbr.lower())

        game_key = f"{away_slug}@{home_slug}"
        results[game_key] = {
            'home_slug':   home_slug,
            'away_slug':   away_slug,
            'home_team':   home.get('team', {}).get('displayName', ''),
            'away_team':   away.get('team', {}).get('displayName', ''),
            'home_score':  parse_score(home),
            'away_score':  parse_score(away),
            'state':       state,   # pre / in / post
            'game_time':   event.get('date', ''),
            'espn_id':     event.get('id', ''),
        }

    return results

def main():
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"fetch_scores.py — {now_str}")

    scores = fetch_scores()
    final  = {k: v for k, v in scores.items() if v['state'] == 'post'}
    live   = {k: v for k, v in scores.items() if v['state'] == 'in'}
    pre    = {k: v for k, v in scores.items() if v['state'] == 'pre'}

    print(f"  {len(final)} final  |  {len(live)} live  |  {len(pre)} upcoming")

    existing = load_json(SCORES_FILE)
    existing_games = existing.get('games', {})

    # Merge — never overwrite a final with a non-final
    for key, game in scores.items():
        if key in existing_games and existing_games[key].get('state') == 'post':
            continue  # already final, keep it
        existing_games[key] = game

    save_json(SCORES_FILE, {
        'fetched_at': now_str,
        'games': existing_games
    })
    print(f"  scores.json updated — {len(existing_games)} total games stored")

if __name__ == '__main__':
    main()
