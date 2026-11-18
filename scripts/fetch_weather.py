"""
fetch_weather.py — Pull game-time weather for every scheduled game.
Uses Open-Meteo (free, no API key). Reads odds.json for game times/locations.
Writes data/weather.json.
"""

import json
import os
import urllib.request
from datetime import datetime, timezone

DATA_DIR     = os.path.join(os.path.dirname(__file__), '..', 'data')
ODDS_FILE    = os.path.join(DATA_DIR, 'odds.json')
WEATHER_FILE = os.path.join(DATA_DIR, 'weather.json')

# Stadium coordinates + dome flag per home team slug
# Dome = retractable or fixed roof — no weather impact
STADIUMS = {
    'ari': {'lat': 33.5277,  'lng': -112.2626, 'dome': True,  'name': 'State Farm Stadium'},
    'atl': {'lat': 33.7554,  'lng': -84.4008,  'dome': True,  'name': 'Mercedes-Benz Stadium'},
    'bal': {'lat': 39.2780,  'lng': -76.6227,  'dome': False, 'name': 'M&T Bank Stadium'},
    'buf': {'lat': 42.7738,  'lng': -78.7870,  'dome': False, 'name': 'Highmark Stadium'},
    'car': {'lat': 35.2258,  'lng': -80.8528,  'dome': False, 'name': 'Bank of America Stadium'},
    'chi': {'lat': 41.8623,  'lng': -87.6167,  'dome': False, 'name': 'Soldier Field'},
    'cin': {'lat': 39.0955,  'lng': -84.5160,  'dome': False, 'name': 'Paycor Stadium'},
    'cle': {'lat': 41.5061,  'lng': -81.6995,  'dome': False, 'name': 'Huntington Bank Field'},
    'dal': {'lat': 32.7473,  'lng': -97.0945,  'dome': True,  'name': 'AT&T Stadium'},
    'den': {'lat': 39.7439,  'lng': -105.0201, 'dome': False, 'name': 'Empower Field'},
    'det': {'lat': 42.3400,  'lng': -83.0456,  'dome': True,  'name': 'Ford Field'},
    'gb':  {'lat': 44.5013,  'lng': -88.0622,  'dome': False, 'name': 'Lambeau Field'},
    'hou': {'lat': 29.6847,  'lng': -95.4107,  'dome': True,  'name': 'NRG Stadium'},
    'ind': {'lat': 39.7601,  'lng': -86.1639,  'dome': True,  'name': 'Lucas Oil Stadium'},
    'jax': {'lat': 30.3239,  'lng': -81.6373,  'dome': False, 'name': 'EverBank Stadium'},
    'kc':  {'lat': 39.0489,  'lng': -94.4839,  'dome': False, 'name': 'GEHA Field'},
    'lac': {'lat': 33.9535,  'lng': -118.3392, 'dome': True,  'name': 'SoFi Stadium'},
    'lar': {'lat': 33.9535,  'lng': -118.3392, 'dome': True,  'name': 'SoFi Stadium'},
    'lv':  {'lat': 36.0909,  'lng': -115.1833, 'dome': True,  'name': 'Allegiant Stadium'},
    'mia': {'lat': 25.9580,  'lng': -80.2389,  'dome': False, 'name': 'Hard Rock Stadium'},
    'min': {'lat': 44.9736,  'lng': -93.2575,  'dome': True,  'name': 'U.S. Bank Stadium'},
    'ne':  {'lat': 42.0909,  'lng': -71.2643,  'dome': False, 'name': 'Gillette Stadium'},
    'no':  {'lat': 29.9511,  'lng': -90.0812,  'dome': True,  'name': 'Caesars Superdome'},
    'nyg': {'lat': 40.8135,  'lng': -74.0745,  'dome': False, 'name': 'MetLife Stadium'},
    'nyj': {'lat': 40.8135,  'lng': -74.0745,  'dome': False, 'name': 'MetLife Stadium'},
    'phi': {'lat': 39.9008,  'lng': -75.1675,  'dome': False, 'name': 'Lincoln Financial Field'},
    'pit': {'lat': 40.4468,  'lng': -80.0158,  'dome': False, 'name': 'Acrisure Stadium'},
    'sf':  {'lat': 37.4033,  'lng': -121.9694, 'dome': False, 'name': "Levi's Stadium"},
    'sea': {'lat': 47.5952,  'lng': -122.3316, 'dome': False, 'name': 'Lumen Field'},
    'tb':  {'lat': 27.9759,  'lng': -82.5033,  'dome': False, 'name': 'Raymond James Stadium'},
    'ten': {'lat': 36.1665,  'lng': -86.7713,  'dome': False, 'name': 'Nissan Stadium'},
    'wsh': {'lat': 38.9078,  'lng': -76.8645,  'dome': False, 'name': 'Northwest Stadium'},
}

# Team name → slug (matches predict.py)
TEAM_SLUG = {
    "Arizona Cardinals": "ari", "Atlanta Falcons": "atl", "Baltimore Ravens": "bal",
    "Buffalo Bills": "buf", "Carolina Panthers": "car", "Chicago Bears": "chi",
    "Cincinnati Bengals": "cin", "Cleveland Browns": "cle", "Dallas Cowboys": "dal",
    "Denver Broncos": "den", "Detroit Lions": "det", "Green Bay Packers": "gb",
    "Houston Texans": "hou", "Indianapolis Colts": "ind", "Jacksonville Jaguars": "jax",
    "Kansas City Chiefs": "kc", "Las Vegas Raiders": "lv", "Los Angeles Chargers": "lac",
    "Los Angeles Rams": "lar", "Miami Dolphins": "mia", "Minnesota Vikings": "min",
    "New England Patriots": "ne", "New Orleans Saints": "no", "New York Giants": "nyg",
    "New York Jets": "nyj", "Philadelphia Eagles": "phi", "Pittsburgh Steelers": "pit",
    "San Francisco 49ers": "sf", "Seattle Seahawks": "sea", "Tampa Bay Buccaneers": "tb",
    "Tennessee Titans": "ten", "Washington Commanders": "wsh",
}


def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def fetch_url(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def get_weather_at_gametime(lat, lng, game_iso):
    """
    Fetch hourly forecast from Open-Meteo for the game's hour.
    Returns dict with temp_f, wind_mph, precip_mm, condition label.
    """
    # Open-Meteo uses ISO date prefix for forecast range
    date_str = game_iso[:10]  # YYYY-MM-DD
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lng}"
        f"&hourly=temperature_2m,precipitation,windspeed_10m,weathercode"
        f"&temperature_unit=fahrenheit"
        f"&windspeed_unit=mph"
        f"&precipitation_unit=inch"
        f"&timezone=UTC"
        f"&start_date={date_str}&end_date={date_str}"
    )
    data = fetch_url(url)
    hourly = data.get('hourly', {})
    times  = hourly.get('time', [])

    # Match the game hour
    game_hour = game_iso[:13]  # "YYYY-MM-DDTHH"
    idx = next((i for i, t in enumerate(times) if t.startswith(game_hour)), None)

    if idx is None:
        # Fallback: use noon
        idx = 12 if len(times) > 12 else 0

    temp_f    = hourly.get('temperature_2m', [None])[idx]
    wind_mph  = hourly.get('windspeed_10m', [None])[idx]
    precip_in = hourly.get('precipitation', [None])[idx]
    wcode     = hourly.get('weathercode', [None])[idx]

    condition = weather_label(wcode, precip_in)

    return {
        'temp_f':     round(temp_f, 1) if temp_f is not None else None,
        'wind_mph':   round(wind_mph, 1) if wind_mph is not None else None,
        'precip_in':  round(precip_in, 2) if precip_in is not None else None,
        'condition':  condition,
        'wmo_code':   wcode,
    }


def weather_label(wcode, precip_in):
    """Map WMO weather code to a human label."""
    if wcode is None:
        return 'unknown'
    if wcode == 0:
        return 'clear'
    if wcode in (1, 2, 3):
        return 'partly_cloudy'
    if wcode in (45, 48):
        return 'fog'
    if wcode in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return 'rain'
    if wcode in (71, 73, 75, 77, 85, 86):
        return 'snow'
    if wcode in (95, 96, 99):
        return 'thunderstorm'
    return 'cloudy'


def build_modifiers(stadium, weather):
    """
    Apply PLAN.md modifier weights to weather conditions.
    Returns modifier dict with multipliers and flags.
    All hypothesis — not yet validated.
    """
    if stadium['dome']:
        return {
            'dome':            True,
            'passing_mult':    1.0,
            'kicker_mult':     1.0,
            'wind_flag':       False,
            'precip_flag':     False,
            'cold_flag':       False,
            'cold_joint_flag': False,
            'notes':           ['dome — no weather impact'],
        }

    notes = []
    passing_mult = 1.0
    kicker_mult  = 1.0

    wind_mph  = weather.get('wind_mph') or 0.0
    temp_f    = weather.get('temp_f') or 50.0
    precip_in = weather.get('precip_in') or 0.0
    condition = weather.get('condition', 'clear')

    wind_flag       = wind_mph > 20
    precip_flag     = condition in ('rain', 'snow', 'thunderstorm') or precip_in > 0.1
    cold_flag       = temp_f < 20
    cold_joint_flag = temp_f < 40   # chronic joint issues start below 40°F

    if wind_flag:
        passing_mult *= 0.75
        notes.append(f'wind {wind_mph:.0f}mph → passing ×0.75')

    if precip_flag:
        passing_mult *= 0.85
        notes.append(f'{condition} → passing ×0.85')

    if cold_flag:
        kicker_mult *= 0.80
        notes.append(f'temp {temp_f:.0f}°F → kicker ×0.80')

    if cold_joint_flag and not cold_flag:
        notes.append(f'temp {temp_f:.0f}°F → chronic joint flag active')

    if not notes:
        notes.append('no significant weather impact')

    return {
        'dome':           False,
        'passing_mult':   round(passing_mult, 4),
        'kicker_mult':    round(kicker_mult, 4),
        'wind_flag':      wind_flag,
        'precip_flag':    precip_flag,
        'cold_flag':      cold_flag,
        'cold_joint_flag': cold_joint_flag,
        'notes':          notes,
    }


def main():
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"fetch_weather.py — {now_str}")

    odds_data = load_json(ODDS_FILE)
    games     = odds_data.get('games', [])

    # Deduplicate by game_id — only need one entry per game
    seen     = set()
    unique   = []
    for g in games:
        if g['game_id'] not in seen:
            seen.add(g['game_id'])
            unique.append(g)

    weather_out = {}
    for game in unique:
        home_slug = TEAM_SLUG.get(game['home_team'])
        if not home_slug:
            continue

        stadium = STADIUMS.get(home_slug)
        if not stadium:
            continue

        game_time = game.get('commence_time', '')
        game_id   = game['game_id']

        if stadium['dome']:
            weather_out[game_id] = {
                'game_id':    game_id,
                'home_team':  game['home_team'],
                'away_team':  game['away_team'],
                'game_time':  game_time,
                'stadium':    stadium['name'],
                'dome':       True,
                'weather':    None,
                'modifiers':  build_modifiers(stadium, {}),
                'fetched_at': now_str,
            }
            print(f"  {game['away_team']} @ {game['home_team']} — DOME, no weather")
            continue

        try:
            weather = get_weather_at_gametime(stadium['lat'], stadium['lng'], game_time)
            mods    = build_modifiers(stadium, weather)
            weather_out[game_id] = {
                'game_id':    game_id,
                'home_team':  game['home_team'],
                'away_team':  game['away_team'],
                'game_time':  game_time,
                'stadium':    stadium['name'],
                'dome':       False,
                'weather':    weather,
                'modifiers':  mods,
                'fetched_at': now_str,
            }
            flag_str = ' | '.join(mods['notes'])
            print(f"  {game['away_team']} @ {game['home_team']} — "
                  f"{weather['temp_f']}°F, {weather['wind_mph']}mph, "
                  f"{weather['condition']} — {flag_str}")
        except Exception as e:
            print(f"  {game['away_team']} @ {game['home_team']} — weather fetch failed: {e}")

    save_json(WEATHER_FILE, {
        'fetched_at': now_str,
        'games': weather_out,
    })
    print(f"\nweather.json updated — {len(weather_out)} games")


if __name__ == '__main__':
    main()
