import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta
try:
    import xml.etree.ElementTree as ET
except ImportError:
    ET = None

DATA_DIR   = os.path.join(os.path.dirname(__file__), '..', 'data')
NEWS_FILE  = os.path.join(DATA_DIR, 'news.json')
META_FILE  = os.path.join(DATA_DIR, 'metadata.json')

# All 32 NFL teams
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

# Search terms per team — name variants that appear in headlines
TEAM_SEARCH_TERMS = {
    'buf': ['bills', 'buffalo'],
    'mia': ['dolphins', 'miami'],
    'ne':  ['patriots', 'new england'],
    'nyj': ['jets', 'new york jets'],
    'bal': ['ravens', 'baltimore'],
    'cin': ['bengals', 'cincinnati'],
    'cle': ['browns', 'cleveland'],
    'pit': ['steelers', 'pittsburgh'],
    'hou': ['texans', 'houston'],
    'ind': ['colts', 'indianapolis'],
    'jax': ['jaguars', 'jacksonville'],
    'ten': ['titans', 'tennessee'],
    'den': ['broncos', 'denver'],
    'kc':  ['chiefs', 'kansas city'],
    'lv':  ['raiders', 'las vegas'],
    'lac': ['chargers', 'los angeles chargers', 'la chargers'],
    'dal': ['cowboys', 'dallas'],
    'nyg': ['giants', 'new york giants'],
    'phi': ['eagles', 'philadelphia'],
    'wsh': ['commanders', 'washington'],
    'chi': ['bears', 'chicago'],
    'det': ['lions', 'detroit'],
    'gb':  ['packers', 'green bay'],
    'min': ['vikings', 'minnesota'],
    'atl': ['falcons', 'atlanta'],
    'car': ['panthers', 'carolina'],
    'no':  ['saints', 'new orleans'],
    'tb':  ['buccaneers', 'bucs', 'tampa bay'],
    'ari': ['cardinals', 'arizona'],
    'lar': ['rams', 'los angeles rams', 'la rams'],
    'sf':  ['49ers', 'san francisco', 'niners'],
    'sea': ['seahawks', 'seattle'],
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

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

PLAYERS_FILE       = os.path.join(DATA_DIR, 'players.json')
RELATIONSHIPS_FILE = os.path.join(DATA_DIR, 'relationships.json')

# Which keyword categories update relationship sentiment, and in which direction
# trade/distraction → negative (tension, uncertainty on edges involving that player)
# positive/hunger   → positive (chemistry, motivation signal)
SENTIMENT_TRIGGERS = {
    'trade':       'negative',
    'distraction': 'negative',
    'positive':    'positive',
    'hunger':      'positive',
}

# Sources — all free, no API key needed
ESPN_NFL_NEWS  = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=100'
NFL_RSS_FEEDS  = [
    'https://www.espn.com/espn/rss/nfl/news',
    'https://feeds.a.dj.com/rss/RSSMarketsMain.xml',  # fallback
]


def fetch_all_headlines():
    """Fetch all available NFL headlines from ESPN API + RSS."""
    articles = []

    # ESPN JSON API — global NFL news
    try:
        r = requests.get(ESPN_NFL_NEWS, timeout=15, headers=HEADERS)
        if r.status_code == 200:
            for a in r.json().get('articles', []):
                headline    = a.get('headline', '')
                description = a.get('description', '') or ''
                published   = a.get('published', '')
                if headline:
                    articles.append({
                        'headline':    headline,
                        'description': description,
                        'published':   published,
                        'source':      'espn'
                    })
    except Exception as e:
        print(f'  ESPN API error: {e}')

    # ESPN RSS feed
    try:
        r = requests.get(NFL_RSS_FEEDS[0], timeout=15, headers=HEADERS)
        if r.status_code == 200 and ET:
            root = ET.fromstring(r.text)
            for item in root.iter('item'):
                title = item.findtext('title') or ''
                desc  = item.findtext('description') or ''
                pub   = item.findtext('pubDate') or ''
                if title:
                    articles.append({
                        'headline':    title,
                        'description': desc,
                        'published':   pub,
                        'source':      'espn_rss'
                    })
    except Exception as e:
        print(f'  ESPN RSS error: {e}')

    print(f'  Fetched {len(articles)} total headlines')
    return articles


def filter_for_team(slug, all_articles):
    """Return articles that mention this team."""
    terms = TEAM_SEARCH_TERMS.get(slug, [])
    matched = []
    for a in all_articles:
        text = (a['headline'] + ' ' + a.get('description', '')).lower()
        if any(term in text for term in terms):
            matched.append(a)
    return matched

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

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def update_relationship_sentiment(flagged_teams, now_str):
    """
    For each team with a sentiment-triggering keyword flag:
      - Find all players on that team in players.json
      - Walk their layer5_relationships IDs
      - Update sentiment on matching edges in relationships.json

    Only overwrites neutral sentiment — preserves manually set or
    previously news-updated sentiment (same logic as preserve_sentiment).
    """
    try:
        players_data = load_json(PLAYERS_FILE)
        rel_data     = load_json(RELATIONSHIPS_FILE)
    except (FileNotFoundError, json.JSONDecodeError):
        return  # relationships not built yet — skip silently

    if not rel_data.get('relationships'):
        return

    # Build rel_id → edge index for O(1) lookup
    rel_index = {r['id']: r for r in rel_data['relationships']}

    # Build team_slug → [player gsis_ids] from players.json
    # players.json uses 'team' field (slug)
    team_to_players = {}
    for p in players_data.get('players', []):
        slug = p.get('team', '')
        gsis = p.get('gsis_id', '')
        if slug and gsis:
            team_to_players.setdefault(slug, []).append(p)

    updated_count = 0
    today = now_str[:10]

    for slug, triggered_categories in flagged_teams.items():
        # Determine net sentiment direction for this team's flags
        # If both positive and negative fire, negative wins (conservative)
        directions = [SENTIMENT_TRIGGERS[c] for c in triggered_categories if c in SENTIMENT_TRIGGERS]
        if not directions:
            continue
        sentiment = 'negative' if 'negative' in directions else 'positive'

        for player in team_to_players.get(slug, []):
            for rel_id in player.get('layer5_relationships', []):
                edge = rel_index.get(rel_id)
                if not edge:
                    continue
                # Only overwrite neutral — preserve prior news/manual updates
                if edge.get('sentiment', 'neutral') == 'neutral':
                    edge['sentiment']    = sentiment
                    edge['last_updated'] = today
                    updated_count += 1

    if updated_count:
        rel_data['last_updated'] = now_str
        save_json(RELATIONSHIPS_FILE, rel_data)
        print(f"  Relationship sentiment updated: {updated_count} edges")

def main():
    now_utc = datetime.now(timezone.utc)
    now_str = now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')
    today   = now_utc.strftime('%Y-%m-%d')
    print(f"fetch_news.py — {now_str}")

    news_data = load_json(NEWS_FILE)
    metadata  = load_json(META_FILE)

    # Remove entries older than 30 days
    cutoff = (now_utc - timedelta(days=30)).strftime('%Y-%m-%d')
    news_data['news'] = [
        n for n in news_data['news']
        if n.get('scanned_at', '')[:10] >= cutoff
    ]

    # Fetch all headlines once, then filter per team
    print('Fetching headlines...')
    all_articles = fetch_all_headlines()

    new_entries   = []
    flags_summary = {
        'injury': [], 'distraction': [], 'trade': [],
        'coach': [], 'hunger': [], 'silence_bonus': []
    }

    for slug, team_name in NFL_TEAMS.items():
        headlines      = filter_for_team(slug, all_articles)
        keywords_found = score_headlines(headlines)
        entry          = build_team_entry(slug, team_name, headlines, keywords_found, now_str)
        new_entries.append(entry)

        for flag in ['injury', 'distraction', 'trade', 'coach', 'hunger']:
            if entry['flags'][flag]:
                flags_summary[flag].append(slug)
        if entry['silence_bonus']:
            flags_summary['silence_bonus'].append(slug)

        if headlines:
            kw_str = ', '.join(entry['keywords_found'].keys()) or 'none'
            silence_str = ' SILENCE' if entry['silence_bonus'] else ''
            print(f"  {team_name}: {len(headlines)} headlines | {kw_str}{silence_str}")

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

    teams_with_news = sum(1 for e in new_entries if e['headline_count'] > 0)
    print(f"\nScan complete — {teams_with_news}/32 teams have headlines")
    print(f"Injury:      {flags_summary['injury']}")
    print(f"Distraction: {flags_summary['distraction']}")
    print(f"Trade:       {flags_summary['trade']}")
    print(f"Coach:       {flags_summary['coach']}")
    print(f"Silence:     {flags_summary['silence_bonus']}")

    # Relationship sentiment overlay — update edges for flagged teams
    print("\nUpdating relationship sentiment...")
    flagged_teams = {}
    for entry in new_entries:
        triggered = [c for c in SENTIMENT_TRIGGERS if entry['flags'].get(c)]
        if triggered:
            flagged_teams[entry['team_slug']] = triggered
    update_relationship_sentiment(flagged_teams, now_str)

if __name__ == '__main__':
    main()
