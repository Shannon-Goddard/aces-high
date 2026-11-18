"""
build_coach_careers.py — One-time script to generate data/coach_playing_careers.csv

Sources:
  - data/nflverse_games.csv    (nflverse schedules — has home_coach/away_coach)
  - data/nflverse_players.csv  (nflverse players — has display_name, position, birth_date, draft)

Output:
  - data/coach_playing_careers.csv

Workflow:
  1. Extract all unique coach names from games.csv (179 coaches since 1999)
  2. Direct-match against players.csv by display_name (case-insensitive)
  3. Write CSV with confirmed NFL records auto-filled, misses left blank for manual entry
  4. You fill in the blanks once — coaches don't un-play football

Run once, then maintain manually when new coaches appear.
"""

import csv
import os

DATA_DIR     = os.path.join(os.path.dirname(__file__), '..', 'data')
GAMES_CSV    = os.path.join(DATA_DIR, 'nflverse_games.csv')
PLAYERS_CSV  = os.path.join(DATA_DIR, 'nflverse_players.csv')
OUTPUT_CSV   = os.path.join(DATA_DIR, 'coach_playing_careers.csv')

# Coaches confirmed to have played college but NOT NFL — pre-fill to avoid manual lookup
# (played before nflverse coverage window 1999+, or college-only)
KNOWN_COLLEGE_ONLY = {
    'Pete Carroll':    {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'DB',  'college': 'Pacific',          'birth_year': '1951'},
    'Mike Tomlin':     {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'WR',  'college': 'William & Mary',   'birth_year': '1972'},
    'Mike McCarthy':   {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'QB',  'college': 'Baker',            'birth_year': '1963'},
    'Nick Sirianni':   {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'WR',  'college': 'Mount Union',      'birth_year': '1981'},
    'Matt LaFleur':    {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'QB',  'college': 'Saginaw Valley',   'birth_year': '1979'},
    'Sean McVay':      {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'WR',  'college': 'Miami OH',         'birth_year': '1986'},
    'Kyle Shanahan':   {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'WR',  'college': 'Texas',            'birth_year': '1979'},
    'Dan Quinn':       {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'DL',  'college': 'Salisbury',        'birth_year': '1970'},
    'Raheem Morris':   {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'DB',  'college': 'Hofstra',          'birth_year': '1976'},
    'Dave Canales':    {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'WR',  'college': 'Cal State LA',     'birth_year': '1980'},
    'Zac Taylor':      {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'QB',  'college': 'Nebraska',         'birth_year': '1983'},
    'Liam Coen':       {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'QB',  'college': 'Maine',            'birth_year': '1986'},
    'Shane Steichen':  {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'QB',  'college': 'Montana',          'birth_year': '1986'},
    'Brian Callahan':  {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'QB',  'college': 'Washington',       'birth_year': '1988'},
    'Jonathan Gannon': {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'DB',  'college': 'Louisville',       'birth_year': '1981'},
    'Ben Johnson':     {'played_nfl': 'TRUE',  'played_college': 'TRUE',  'college_position': 'TE',  'college': 'Michigan',         'birth_year': '1986'},
    # Never played at any level
    'John Harbaugh':   {'played_nfl': 'FALSE', 'played_college': 'FALSE', 'college_position': '',    'college': 'Miami OH',         'birth_year': '1962'},
    'Kevin Stefanski': {'played_nfl': 'FALSE', 'played_college': 'FALSE', 'college_position': '',    'college': 'Penn',             'birth_year': '1982'},
    'Mike McDaniel':   {'played_nfl': 'FALSE', 'played_college': 'FALSE', 'college_position': '',    'college': 'Yale',             'birth_year': '1983'},
    'Mike Macdonald':  {'played_nfl': 'FALSE', 'played_college': 'FALSE', 'college_position': '',    'college': 'Cincinnati',       'birth_year': '1987'},
    'Brian Daboll':    {'played_nfl': 'FALSE', 'played_college': 'TRUE',  'college_position': 'WR',  'college': 'Rochester',        'birth_year': '1975'},
}

# Ben Johnson played in NFL (2006-2010, TE, Lions/Browns) — confirm via nflverse
# Andy Reid played college only (OL, BYU) — nflverse has him as RB 1976 which is wrong/different person
KNOWN_OVERRIDES = {
    'Andy Reid': {'played_nfl': 'FALSE', 'played_college': 'TRUE', 'college_position': 'OL', 'college': 'BYU', 'birth_year': '1958'},
}


def load_players(path):
    players = {}
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            name = row['display_name'].strip()
            birth = row.get('birth_date', '')
            # Only include players with a real birth date to avoid false matches
            if not birth:
                continue
            key = name.lower()
            # Keep the record with the most recent last_season (handles duplicate names)
            existing = players.get(key)
            if existing:
                try:
                    if int(row.get('last_season') or 0) > int(existing.get('last_season') or 0):
                        players[key] = row
                except ValueError:
                    pass
            else:
                players[key] = row
    return players


def load_coaches(path):
    coaches = {}  # name -> first_season, last_season
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            season = int(row.get('season') or 0)
            for side in ('away_coach', 'home_coach'):
                name = (row.get(side) or '').strip()
                if not name:
                    continue
                if name not in coaches:
                    coaches[name] = {'first_season': season, 'last_season': season}
                else:
                    coaches[name]['last_season'] = max(coaches[name]['last_season'], season)
                    coaches[name]['first_season'] = min(coaches[name]['first_season'], season)
    return coaches


def main():
    print('Loading nflverse data...')
    players = load_players(PLAYERS_CSV)
    coaches = load_coaches(GAMES_CSV)
    print(f'  {len(players)} players, {len(coaches)} coaches')

    rows = []
    matched = 0
    manual_needed = 0

    for coach_name in sorted(coaches):
        seasons = coaches[coach_name]
        key = coach_name.lower()

        # Check for known override first
        if coach_name in KNOWN_OVERRIDES:
            override = KNOWN_OVERRIDES[coach_name]
            rows.append({
                'coach_name':       coach_name,
                'coach_first_season': seasons['first_season'],
                'coach_last_season':  seasons['last_season'],
                'played_nfl':       override['played_nfl'],
                'played_college':   override['played_college'],
                'nfl_position':     '',
                'college_position': override['college_position'],
                'college':          override['college'],
                'birth_year':       override['birth_year'],
                'nfl_draft_year':   '',
                'nfl_draft_round':  '',
                'nfl_last_season':  '',
                'source':           'manual_override',
                'notes':            '',
            })
            matched += 1
            continue

        # Check known college-only / never-played
        if coach_name in KNOWN_COLLEGE_ONLY:
            known = KNOWN_COLLEGE_ONLY[coach_name]
            rows.append({
                'coach_name':       coach_name,
                'coach_first_season': seasons['first_season'],
                'coach_last_season':  seasons['last_season'],
                'played_nfl':       known['played_nfl'],
                'played_college':   known['played_college'],
                'nfl_position':     '',
                'college_position': known['college_position'],
                'college':          known['college'],
                'birth_year':       known['birth_year'],
                'nfl_draft_year':   '',
                'nfl_draft_round':  '',
                'nfl_last_season':  '',
                'source':           'manual_seed',
                'notes':            '',
            })
            matched += 1
            continue

        # Try direct nflverse player match
        player = players.get(key)
        if player:
            birth_year = (player.get('birth_date') or '')[:4]
            rows.append({
                'coach_name':       coach_name,
                'coach_first_season': seasons['first_season'],
                'coach_last_season':  seasons['last_season'],
                'played_nfl':       'TRUE',
                'played_college':   'TRUE',
                'nfl_position':     player.get('position', ''),
                'college_position': '',
                'college':          player.get('college_name', ''),
                'birth_year':       birth_year,
                'nfl_draft_year':   player.get('draft_year', ''),
                'nfl_draft_round':  player.get('draft_round', ''),
                'nfl_last_season':  player.get('last_season', ''),
                'source':           'nflverse_match',
                'notes':            '',
            })
            matched += 1
        else:
            # Leave blank for manual fill
            rows.append({
                'coach_name':       coach_name,
                'coach_first_season': seasons['first_season'],
                'coach_last_season':  seasons['last_season'],
                'played_nfl':       '',
                'played_college':   '',
                'nfl_position':     '',
                'college_position': '',
                'college':          '',
                'birth_year':       '',
                'nfl_draft_year':   '',
                'nfl_draft_round':  '',
                'nfl_last_season':  '',
                'source':           'needs_manual',
                'notes':            '',
            })
            manual_needed += 1

    fieldnames = [
        'coach_name', 'coach_first_season', 'coach_last_season',
        'played_nfl', 'played_college', 'nfl_position', 'college_position',
        'college', 'birth_year', 'nfl_draft_year', 'nfl_draft_round',
        'nfl_last_season', 'source', 'notes',
    ]

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'\nWrote {len(rows)} rows to coach_playing_careers.csv')
    print(f'  Auto-filled (nflverse match + manual seed): {matched}')
    print(f'  Needs manual fill (source=needs_manual):    {manual_needed}')
    print(f'\nOpen data/coach_playing_careers.csv and fill in the blank rows.')
    print('Fields to fill: played_nfl, played_college, nfl_position/college_position, college, birth_year')


if __name__ == '__main__':
    main()
