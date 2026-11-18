"""
fetch_practice.py — Pull injury/practice status for all 32 NFL teams.
Uses ESPN injuries API (free, no key). Runs Wed/Thu/Fri during game week.
Writes data/practice.json with per-player trajectory scores.

Trajectory scoring (0-100, higher = more concerning):
  DNP all week reported          → 90
  DNP Wed + Thu                  → 75
  DNP Wed only / limited Thu     → 55
  Limited participation          → 35
  Full participation             → 5
  Surprise DNP (was full, now out) → 85  (caught by status=Out + full comment)
  Trending full (limited→full)   → 10
  No report / Active             → 0
"""

import json
import os
import re
import urllib.request
from datetime import datetime, timezone

DATA_DIR      = os.path.join(os.path.dirname(__file__), '..', 'data')
PRACTICE_FILE = os.path.join(DATA_DIR, 'practice.json')

ESPN_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"

# ESPN team abbreviation → our slug
ESPN_ABBR_MAP = {
    'ARI': 'ari', 'ATL': 'atl', 'BAL': 'bal', 'BUF': 'buf', 'CAR': 'car',
    'CHI': 'chi', 'CIN': 'cin', 'CLE': 'cle', 'DAL': 'dal', 'DEN': 'den',
    'DET': 'det',  'GB': 'gb',  'HOU': 'hou', 'IND': 'ind', 'JAX': 'jax',
    'KC':  'kc',   'LV': 'lv',  'LAC': 'lac',  'LA': 'lar', 'MIA': 'mia',
    'MIN': 'min',  'NE': 'ne',   'NO': 'no',  'NYG': 'nyg', 'NYJ': 'nyj',
    'PHI': 'phi', 'PIT': 'pit',  'SF': 'sf',  'SEA': 'sea',  'TB': 'tb',
    'TEN': 'ten', 'WSH': 'wsh', 'WAS': 'wsh',
}

# Status strings from ESPN → base concern level
STATUS_SCORE = {
    'injured reserve':  95,
    'out':              85,
    'doubtful':         70,
    'questionable':     40,
    'probable':         15,
    'active':            0,
}

# Practice participation keywords in shortComment / longComment
# Ordered most-to-least severe so first match wins
PRACTICE_PATTERNS = [
    # DNP signals
    (r'\bdid not practice\b',                    80),
    (r'\bdnp\b',                                 80),
    (r'\bnot practice\b',                        80),
    (r'\bmissed practice\b',                     75),
    (r'\bsat out\b',                             70),
    # Trending bad
    (r'\blimited.*practice\b',                   45),
    (r'\brestricted.*practice\b',                45),
    (r'\bpartial.*practice\b',                   40),
    # Trending good
    (r'\breturned.*practice\b',                  20),
    (r'\bback.*practice\b',                      20),
    (r'\bfull.*practice\b',                       5),
    (r'\bfull participation\b',                   5),
    (r'\bpracticed fully\b',                      5),
    # Surprise DNP — was fine, now out
    (r'\bsurprise.*scratch\b',                   88),
    (r'\bunexpected.*scratch\b',                 88),
    (r'\blast.minute.*scratch\b',                88),
]

# Injury types that amplify cold-weather concern (for chronic_joint_issue flagging)
JOINT_INJURY_KEYWORDS = [
    'knee', 'ankle', 'shoulder', 'elbow', 'wrist', 'hip', 'finger',
    'arthritis', 'joint', 'cartilage', 'tendon', 'ligament',
]


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


def parse_practice_score(status_str, short_comment, long_comment):
    """
    Derive a 0-100 concern score from status + comment text.
    Higher = more likely to miss or be limited game day.
    """
    status_lower   = (status_str or '').lower().strip()
    comment_lower  = (short_comment or '').lower() + ' ' + (long_comment or '').lower()

    # Base from official status
    base = STATUS_SCORE.get(status_lower, 0)

    # Scan comment for practice participation signals
    comment_score = None
    for pattern, score in PRACTICE_PATTERNS:
        if re.search(pattern, comment_lower):
            comment_score = score
            break

    # Blend: status is the floor, comment can push it up or down
    if comment_score is not None:
        # If comment says full practice but status is Questionable → trending right
        if comment_score <= 10 and base >= 40:
            return max(10, base - 25)   # reduce concern — trending full
        # If comment says DNP but status is Active → surprise flag
        if comment_score >= 75 and base == 0:
            return 85
        return max(base, comment_score)

    return base


def has_joint_injury(short_comment, long_comment, primary_injury):
    """Check if injury type suggests chronic joint issue potential."""
    text = ' '.join([
        (short_comment or ''),
        (long_comment or ''),
        (primary_injury or ''),
    ]).lower()
    return any(kw in text for kw in JOINT_INJURY_KEYWORDS)


def trajectory_label(score):
    if score >= 85:  return 'out'
    if score >= 70:  return 'doubtful'
    if score >= 50:  return 'limited'
    if score >= 25:  return 'questionable'
    if score >= 10:  return 'trending_full'
    return 'full'


def main():
    now_str  = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    today    = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    weekday  = datetime.now(timezone.utc).strftime('%A')  # Wednesday / Thursday / Friday
    print(f"fetch_practice.py — {now_str} [{weekday}]")

    data  = fetch_url(ESPN_INJURIES)
    teams = data.get('injuries', [])
    print(f"  {len(teams)} teams returned from ESPN")

    existing    = load_json(PRACTICE_FILE)
    players_out = existing.get('players', {})
    flagged     = 0

    for team_entry in teams:
        team_abbr = team_entry.get('id', '')
        # ESPN uses numeric IDs here — get abbr from athlete.team.abbreviation instead
        injuries = team_entry.get('injuries', [])

        for inj in injuries:
            athlete       = inj.get('athlete', {})
            name          = athlete.get('displayName', '')
            position      = (athlete.get('position') or {}).get('abbreviation', '')
            team_abbr_raw = (athlete.get('team') or {}).get('abbreviation', '')
            team_slug     = ESPN_ABBR_MAP.get(team_abbr_raw, team_abbr_raw.lower())

            status        = inj.get('status', 'Active')
            short_comment = inj.get('shortComment', '')
            long_comment  = inj.get('longComment', '')
            primary_inj   = (inj.get('type') or {}).get('description', '')
            inj_date      = inj.get('date', '')

            score = parse_practice_score(status, short_comment, long_comment)
            label = trajectory_label(score)
            joint = has_joint_injury(short_comment, long_comment, primary_inj)

            player_key = f"{team_slug}:{name}"

            # Build trajectory log — append today's reading
            existing_entry = players_out.get(player_key, {})
            trajectory_log = existing_entry.get('trajectory_log', [])

            # Only append if we don't already have today's entry
            if not trajectory_log or trajectory_log[-1].get('date') != today:
                trajectory_log.append({
                    'date':    today,
                    'weekday': weekday,
                    'score':   score,
                    'label':   label,
                    'status':  status,
                    'comment': short_comment[:120] if short_comment else '',
                })

            # Keep last 5 days of trajectory
            trajectory_log = trajectory_log[-5:]

            players_out[player_key] = {
                'name':           name,
                'team_slug':      team_slug,
                'position':       position,
                'status':         status,
                'practice_score': score,
                'trajectory':     label,
                'joint_injury':   joint,
                'primary_injury': primary_inj,
                'short_comment':  short_comment[:200] if short_comment else '',
                'trajectory_log': trajectory_log,
                'last_updated':   now_str,
            }

            if score >= 40:
                flagged += 1
                print(f"  [{label.upper():12}] {name} ({position}, {team_slug}) — {status} — {short_comment[:80]}")

    save_json(PRACTICE_FILE, {
        'fetched_at': now_str,
        'weekday':    weekday,
        'players':    players_out,
    })

    total = len(players_out)
    print(f"\n  practice.json updated — {total} players tracked, {flagged} flagged this run")


if __name__ == '__main__':
    main()
