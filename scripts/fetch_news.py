import requests
import json
import os
from datetime import datetime, timezone, timedelta

DATA_DIR   = os.path.join(os.path.dirname(__file__), '..', 'data')
NEWS_FILE  = os.path.join(DATA_DIR, 'news.json')
META_FILE  = os.path.join(DATA_DIR, 'metadata.json')

# All 32 NFL teams — ESPN slug : display name
NFL_TEAMS = {
    'buf': 'Buffalo Bills',       'mia': 'Miami Dolphins',
    'ne':  'New England Patriots','nyj': 'New York Jets',
    'bal': 'Baltimore Ravens',    'cin': 'Cincinnati Bengals',
    'cle': 'Cleveland Browns',    'pit': 'Pittsburgh Steelers',
    'hou': 'Houston Texans',      'ind': 'Indianapolis Colts',
    'jax': 'Jacksonville Jaguars','ten': 'Tennessee Titans',
    'den': 'Denver Broncos',      'kc':  'Kansas City Chiefs',
    'lv':  'Las Vegas Raiders',   'lac': 'Los Angeles Chargers',
    'dal': 'Dallas Cowboys',      'nyg': 'New York Giants',
    'phi': 'Philadelphia Eagles', 'wsh': 'Washington Commanders',
    'chi': 'Chicago Bears',       'det': 'Detroit Lions',
    'gb':  'Green Bay Packers',   'min': 'Minnesota Vikings',
    'atl': 'Atlanta Falcons',     'car': 'Carolina Panthers',
    'no':  'New Orleans Saints',  'tb':  'Tampa Bay Buccaneers',
    'ari': 'Arizona Cardinals',   'lar': 'Los Angeles Rams',
    'sf':  'San Francisco 49ers', 'sea': 'Seattle Seahawks'
}

# Keyword categories — each tracked independently for accuracy over time
HUNGER_KEYWORDS = [
    'prove', 'proving', 'undrafted', 'overlooked', 'comeback',
    'motivated', 'hungry', 'contract year', 'prove-it deal',
    'something to prove', 'chip on his shoulder', 'bounced back'
]

DISTRACTION_KEYWORDS = [
    'arrested', 'arrest', 'lawsuit', 'suspended', 'suspension',
    'trade request', 'wants out', 'holdout', 'fined', 'investigation',
    'divorce', 'domestic', 'altercation', 'fight', 'beef',
    'distracted', 'off field', 'incident', 'controversy'
]

INJURY_KEYWORDS = [
    'injured', 'injury', 'questionable', 'doubtful', 'out',
    'limited', 'did not practice', 'dnp', 'placed on ir',
    'surgery', 'sprain', 'strain', 'fracture', 'concussion',
    'hamstring', 'knee', 'ankle', 'shoulder', 'back', 'illness'
]

POSITIVE_KEYWORDS = [
    'extension', 'signed', 'record', 'career high', 'dominant',
    'locked in', 'focused', 'healthy', 'full practice', 'cleared',
    'promoted', 'named starter', 'chemistry', 'connection',
    'breakout', 'elite', 'mvp', 'pro bowl'
]

COACH_KEYWORDS = [
    'fired', 'hired', 'resigned', 'hot seat', 'interim',
    'coordinator change', 'scheme change', 'new system',
    'vote of confidence', 'extension', 'contract extension'
]

TRADE_KEYWORDS = [
    'traded', 'trade', 'released', 'cut', 'waived',
    'signed', 'free agent', 'acquired', 'deal', 'transaction'
]

ALL_KEYWORD_CATEGORIES = {
    'hunger':      HUNGER_KEYWORDS,
    'distraction': DISTRACTION_KEYWORDS,
    'injury':      INJURY_KEYWORDS,
    'positive':    POSITIVE_KEYWORDS,
    'coach':       COACH_KEYWORDS,
    'trade':       TRADE_KEYWORDS
}

ESPN_NEWS_URL = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/news'
ESPN_TEAM_URL = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{slug}/news'


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def fetch_team_news(slug):
    try:
        url = ESPN_TEAM_URL.format(slug=slug)
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        articles = data.get('articles', [])
        headlines = []
        for a in articles:
            headline = a.get('headline', '')
            description = a.get('description', '')
            published = a.get('published', '')
            if headline:
                headlines.append({
                    'headline':    headline,
                    'description': description,
                    'published':   published
                })
        return headlines
    except Exception as e:
        print(f"  News fetch failed for {slug}: {e}")
        return []

def score_headlines(headlines):
    text = ' '.join(
        (h['headline'] + ' ' + h.get('description', '')).lower()
        for h in headlines
    )
    found = {}
    for category, keywords in ALL_KEYWORD_CATEGORIES.items():
        matched = [kw for kw in keywords if kw in text]
        if matched:
            found[category] = matched
    return found

def flag_silence(headlines, last_scan_keywords):
    """
    Silence bonus — no news at all, or no negative keywords for 3+ days.
    The Ace gold: locked in, quiet, focused.
    """
    if not headlines:
        return True, 'no_headlines'
    negative = last_scan_keywords.get('distraction', []) + last_scan_keywords.get('injury', [])
    if not negative:
        return True, 'no_negative_keywords'
    return False, None

def build_team_entry(slug, team_name, headlines, keywords_found, now_str):
    silence, silence_reason = flag_silence(headlines, keywords_found)
    return {
        'team_slug':       slug,
        'team_name':       team_name,
        'scanned_at':      now_str,
        'headline_count':  len(headlines),
        'headlines':       headlines[:10],  # store top 10
        'keywords_found':  keywords_found,
        'silence_bonus':   silence,
        'silence_reason':  silence_reason if silence else None,
        'flags': {
            'injury':      bool(keywords_found.get('injury')),
            'distraction': bool(keywords_found.get('distraction')),
            'trade':       bool(keywords_found.get('trade')),
            'coach':       bool(keywords_found.get('coach')),
            'hunger':      bool(keywords_found.get('hunger')),
            'positive':    bool(keywords_found.get('positive'))
        }
    }

def main():
    now_utc  = datetime.now(timezone.utc)
    now_str  = now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')
    today    = now_utc.strftime('%Y-%m-%d')
    print(f"fetch_news.py — {now_str}")

    news_data = load_json(NEWS_FILE)
    metadata  = load_json(META_FILE)

    # Remove entries older than 30 days to keep file lean
    cutoff = (now_utc - timedelta(days=30)).strftime('%Y-%m-%d')
    news_data['news'] = [
        n for n in news_data['news']
        if n.get('scanned_at', '')[:10] >= cutoff
    ]

    new_entries  = []
    flags_summary = {
        'injury': [], 'distraction': [], 'trade': [],
        'coach': [], 'hunger': [], 'silence_bonus': []
    }

    for slug, team_name in NFL_TEAMS.items():
        print(f"  Scanning {team_name}...")
        headlines     = fetch_team_news(slug)
        keywords_found = score_headlines(headlines)
        entry         = build_team_entry(slug, team_name, headlines, keywords_found, now_str)
        new_entries.append(entry)

        # Build flags summary for metadata
        for flag in ['injury', 'distraction', 'trade', 'coach', 'hunger']:
            if entry['flags'][flag]:
                flags_summary[flag].append(slug)
        if entry['silence_bonus']:
            flags_summary['silence_bonus'].append(slug)

        kw_str = ', '.join(entry['keywords_found'].keys()) or 'none'
        silence_str = ' ** SILENCE BONUS' if entry['silence_bonus'] else ''
        print(f"    {len(headlines)} headlines | flags: {kw_str}{silence_str}")

    news_data['news'].extend(new_entries)
    news_data['last_updated'] = now_str
    save_json(NEWS_FILE, news_data)

    metadata['last_news_scan'] = now_str
    metadata['news_scan_summary'] = {
        'date':          today,
        'teams_scanned': len(NFL_TEAMS),
        'flags':         flags_summary
    }
    save_json(META_FILE, metadata)

    print(f"\nScan complete — {len(NFL_TEAMS)} teams")
    print(f"Injury flags:      {flags_summary['injury']}")
    print(f"Distraction flags: {flags_summary['distraction']}")
    print(f"Trade flags:       {flags_summary['trade']}")
    print(f"Coach flags:       {flags_summary['coach']}")
    print(f"Silence bonuses:   {flags_summary['silence_bonus']}")

if __name__ == '__main__':
    main()
