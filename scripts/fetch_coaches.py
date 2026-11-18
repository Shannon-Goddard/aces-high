"""
fetch_coaches.py — Build and maintain coaches.json

Sources:
  - data/coaches-data.csv  (Pro Football Reference — cite: https://www.pro-football-reference.com/coaches/)
  - ESPN news API          (coach change detection — fired/hired/interim keywords)
  - Hardcoded seed         (current 32 HCs + coordinators, updated when news flags a change)

Writes: data/coaches.json

Run: weekly (Tuesday) or any time a coaching change is suspected.
"""

import csv
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

DATA_DIR      = os.path.join(os.path.dirname(__file__), '..', 'data')
CSV_FILE      = os.path.join(DATA_DIR, 'coaches-data.csv')
CAREERS_FILE  = os.path.join(DATA_DIR, 'coach_playing_careers.csv')
COACHES_FILE  = os.path.join(DATA_DIR, 'coaches.json')
META_FILE     = os.path.join(DATA_DIR, 'metadata.json')

HEADERS = {'User-Agent': 'Mozilla/5.0'}

# ── CURRENT ROSTER SEED ───────────────────────────────────────────────────────
# HC + key coordinators per team. Update this when a coaching change is confirmed.
# Data source: Pro Football Reference https://www.pro-football-reference.com/coaches/
# "When using SR data, please cite us and provide a link and/or a mention."

CURRENT_STAFF = {
    'buf': {'hc': 'Sean McDermott',      'oc': 'Joe Brady',          'dc': 'Bobby Babich'},
    'mia': {'hc': 'Mike McDaniel',       'oc': 'Frank Smith',        'dc': 'Anthony Weaver'},
    'ne':  {'hc': 'Mike Vrabel',         'oc': 'Josh McDaniels',     'dc': 'DeMarcus Covington'},
    'nyj': {'hc': 'Aaron Glenn',         'oc': 'Tanner Engstrand',   'dc': 'Jeff Ulbrich'},
    'bal': {'hc': 'John Harbaugh',       'oc': 'Todd Monken',        'dc': 'Zach Orr'},
    'cin': {'hc': 'Zac Taylor',          'oc': 'Dan Pitcher',        'dc': 'Al Golden'},
    'cle': {'hc': 'Kevin Stefanski',     'oc': 'Tommy Rees',         'dc': 'Jim Schwartz'},
    'pit': {'hc': 'Mike Tomlin',         'oc': 'Arthur Smith',       'dc': 'Teryl Austin'},
    'hou': {'hc': 'DeMeco Ryans',        'oc': 'Bobby Slowik',       'dc': 'Matt Burke'},
    'ind': {'hc': 'Shane Steichen',      'oc': 'Scottie Montgomery', 'dc': 'Gus Bradley'},
    'jax': {'hc': 'Liam Coen',           'oc': 'Press Taylor',       'dc': 'Ryan Nielsen'},
    'ten': {'hc': 'Brian Callahan',      'oc': 'Nick Holz',          'dc': 'Dennard Wilson'},
    'den': {'hc': 'Sean Payton',         'oc': 'Joe Lombardi',       'dc': 'Vance Joseph'},
    'kc':  {'hc': 'Andy Reid',           'oc': 'Matt Nagy',          'dc': 'Steve Spagnuolo'},
    'lv':  {'hc': 'Pete Carroll',        'oc': 'Scott Turner',       'dc': 'Patrick Graham'},
    'lac': {'hc': 'Jim Harbaugh',        'oc': 'Greg Roman',         'dc': 'Jesse Minter'},
    'dal': {'hc': 'Mike McCarthy',       'oc': 'Brian Schottenheimer','dc': 'Mike Zimmer'},
    'nyg': {'hc': 'Brian Daboll',        'oc': 'Mike Kafka',         'dc': 'Shane Bowen'},
    'phi': {'hc': 'Nick Sirianni',       'oc': 'Kellen Moore',       'dc': 'Vic Fangio'},
    'wsh': {'hc': 'Dan Quinn',           'oc': 'Klint Kubiak',       'dc': 'Joe Whitt Jr.'},
    'chi': {'hc': 'Ben Johnson',         'oc': 'Thomas Brown',       'dc': 'Dennis Allen'},
    'det': {'hc': 'Dan Campbell',        'oc': 'John Morton',        'dc': 'Aaron Glenn'},
    'gb':  {'hc': 'Matt LaFleur',        'oc': 'Adam Stenavich',     'dc': 'Jeff Hafley'},
    'min': {'hc': 'Kevin O\'Connell',    'oc': 'Wes Phillips',       'dc': 'Brian Flores'},
    'atl': {'hc': 'Raheem Morris',       'oc': 'Zac Robinson',       'dc': 'Jimmy Lake'},
    'car': {'hc': 'Dave Canales',        'oc': 'Brad Idzik',         'dc': 'Ejiro Evero'},
    'no':  {'hc': 'Kellen Moore',        'oc': 'Klint Kubiak',       'dc': 'Joe Woods'},
    'tb':  {'hc': 'Todd Bowles',         'oc': 'Liam Coen',          'dc': 'Kacy Rodgers'},
    'ari': {'hc': 'Jonathan Gannon',     'oc': 'Drew Petzing',       'dc': 'Nick Rallis'},
    'lar': {'hc': 'Sean McVay',          'oc': 'Mike LaFleur',       'dc': 'Chris Shula'},
    'sf':  {'hc': 'Kyle Shanahan',       'oc': 'Mike McDaniel',      'dc': 'Nick Sorensen'},
    'sea': {'hc': 'Mike Macdonald',      'oc': 'Ryan Grubb',         'dc': 'Aden Durde'},
}

ROLE_LABELS = {'hc': 'Head Coach', 'oc': 'Offensive Coordinator', 'dc': 'Defensive Coordinator'}

# ── MARKET PRESSURE TABLE ─────────────────────────────────────────────────────
# 1-10 scale: media intensity × market size × ownership volatility.
# High = NY/DAL/CHI/PHI/SF. Low = KC/GB/NE/PIT/SEA.
# An introverted HC in a high-pressure market pays a structural energy tax.
# Sources: market size (Nielsen DMA), ownership stability (tenure/firings history),
# media scrutiny (beat reporter count, national coverage frequency).
MARKET_PRESSURE = {
    'buf': 4, 'mia': 5, 'ne':  4, 'nyj': 9,
    'bal': 5, 'cin': 4, 'cle': 6, 'pit': 6,
    'hou': 5, 'ind': 4, 'jax': 3, 'ten': 4,
    'den': 6, 'kc':  3, 'lv':  5, 'lac': 6,
    'dal': 10,'nyg': 9, 'phi': 8, 'wsh': 7,
    'chi': 8, 'det': 5, 'gb':  3, 'min': 5,
    'atl': 5, 'car': 4, 'no':  5, 'tb':  5,
    'ari': 4, 'lar': 7, 'sf':  7, 'sea': 5,
}

# Keywords that signal a coaching change in headlines
CHANGE_KEYWORDS = ['fired', 'hired', 'interim', 'named head coach', 'named offensive coordinator',
                   'named defensive coordinator', 'parts ways', 'relieved of duties', 'steps down',
                   'resigns', 'new head coach', 'new offensive coordinator', 'new defensive coordinator']


# ── PLAYING CAREER LOADER ────────────────────────────────────────────────────

def load_playing_careers(path):
    """
    Load coach_playing_careers.csv.
    Returns dict: coach_name -> career dict.
    Rows with source=needs_manual and empty played_nfl are incomplete — still included,
    fetch_coaches.py will note them as unverified.
    """
    careers = {}
    if not os.path.exists(path):
        print(f'  WARNING: {path} not found — playing career data unavailable')
        return careers
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            name = row['coach_name'].strip()
            careers[name] = {
                'played_nfl':       row.get('played_nfl', '').upper() == 'TRUE',
                'played_college':   row.get('played_college', '').upper() == 'TRUE',
                'nfl_position':     row.get('nfl_position', '') or None,
                'college_position': row.get('college_position', '') or None,
                'college':          row.get('college', '') or None,
                'birth_year':       int(row['birth_year']) if row.get('birth_year') else None,
                'nfl_draft_year':   int(row['nfl_draft_year']) if row.get('nfl_draft_year') else None,
                'nfl_draft_round':  int(row['nfl_draft_round']) if row.get('nfl_draft_round') else None,
                'career_source':    row.get('source', 'unknown'),
            }
    verified = sum(1 for v in careers.values() if v['career_source'] != 'needs_manual')
    print(f'  Loaded {len(careers)} coach career rows ({verified} verified, {len(careers)-verified} need manual fill)')
    return careers


# ── CSV PARSER ────────────────────────────────────────────────────────────────

def load_pfr_records(csv_path):
    """
    Parse coaches-data.csv from Pro Football Reference.
    Returns dict: normalized_name -> career record dict.
    Source: https://www.pro-football-reference.com/coaches/
    """
    records = {}
    if not os.path.exists(csv_path):
        print(f'  WARNING: {csv_path} not found — career records unavailable')
        return records

    with open(csv_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip merged header rows, parse from the actual column header line
    lines = [l for l in content.split('\n')
             if l.strip() and not l.startswith(',,,,Reg') and not l.startswith('Rk,Coach,From')]

    # Re-insert the header
    header = 'Rk,Coach,From,To,Yrs,G,W,L,T,W-L%,G > .500,Yrs,G,W,L,W-L%,G,W,L,T,W-L%,AvRk,BstRk,Chmp,SBwl,Conf'
    reader = csv.DictReader([header] + lines)

    for row in reader:
        name = (row.get('Coach') or '').replace('+', '').strip()
        if not name or name == 'Coach':
            continue
        key = _normalize_name(name)
        try:
            records[key] = {
                'name':         name,
                'pfr_from':     int(row.get('From') or 0),
                'pfr_to':       int(row.get('To') or 0),
                'pfr_yrs':      int(row.get('Yrs') or 0),
                'reg_wins':     int(row.get('W') or 0),
                'reg_losses':   int(row.get('L') or 0),
                'reg_wl_pct':   float(row.get('W-L%') or 0),
                'playoff_wins': int(row.get('W') or 0),   # second W col = playoff W
                'super_bowls':  _int_or_zero(row.get('SBwl')),
                'conf_titles':  _int_or_zero(row.get('Conf')),
                'championships':_int_or_zero(row.get('Chmp')),
            }
        except Exception:
            pass

    print(f'  Loaded {len(records)} career records from PFR CSV')
    return records


def _normalize_name(name):
    """Lowercase, strip punctuation for fuzzy matching."""
    return re.sub(r"[^a-z ]", '', name.lower()).strip()


def _int_or_zero(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


# ── NEWS SCAN ─────────────────────────────────────────────────────────────────

def fetch_headlines():
    url = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=100'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        r   = urllib.request.urlopen(req, timeout=15)
        d   = json.loads(r.read())
        return [a.get('headline', '') + ' ' + (a.get('description') or '')
                for a in d.get('articles', [])]
    except Exception as e:
        print(f'  ESPN news fetch error: {e}')
        return []


def detect_changes(headlines, current_staff):
    """
    Scan headlines for coaching change keywords.
    Returns list of (team_slug, role, coach_name, keyword) tuples where a change may have occurred.
    """
    flags = []
    all_coaches = {}
    for slug, staff in current_staff.items():
        for role, name in staff.items():
            all_coaches[name.lower()] = (slug, role)

    for headline in headlines:
        hl_lower = headline.lower()
        if not any(kw in hl_lower for kw in CHANGE_KEYWORDS):
            continue
        # Check if any current coach name appears in this headline
        for coach_name, (slug, role) in all_coaches.items():
            last_name = coach_name.split()[-1]
            if last_name in hl_lower:
                flags.append({
                    'team':    slug,
                    'role':    role,
                    'coach':   coach_name,
                    'headline': headline[:120],
                })
    return flags


# ── MBTI SIGNAL INFERENCE ─────────────────────────────────────────────────────

def infer_mbti_signals(name, pfr_rec, role, career=None):
    """
    Infer MBTI axis signals from available data.
    Returns dict of signals — not a final type, just directional evidence.
    I/E and T/F are most reliable from career data.
    S/N and J/P need press conference data (marked as accumulating).
    """
    signals = {
        'ie': None,   # 'I' or 'E' or None
        'tf': None,   # 'T' or 'F' or None
        'sn': None,   # accumulating
        'jp': None,   # accumulating
        'ie_evidence': [],
        'tf_evidence': [],
        'sn_evidence': ['Accumulating — needs week-by-week stat variance data'],
        'jp_evidence': ['Accumulating — needs press conference language patterns'],
        'confidence':  'low',
    }

    # ── Playing career signals ───────────────────────────────────────────────
    if career:
        if career.get('played_nfl'):
            signals['ie_evidence'].append('Played in NFL — understands physical demands from inside the game')
            signals['tf_evidence'].append('NFL playing experience — analytical understanding of player reality')
        elif career.get('played_college'):
            pos = career.get('college_position') or career.get('nfl_position') or ''
            signals['ie_evidence'].append(f'Played college football ({pos}) — competitive playing background')
        else:
            signals['ie_evidence'].append('No playing background — pure schemer/analyst path')
            signals['tf_evidence'].append('No playing experience — may over-index on scheme vs player welfare')

    if not pfr_rec:
        return signals

    wins    = pfr_rec.get('reg_wins', 0)
    losses  = pfr_rec.get('reg_losses', 0)
    yrs     = pfr_rec.get('pfr_yrs', 0)
    wl_pct  = pfr_rec.get('reg_wl_pct', 0)
    sbs     = pfr_rec.get('super_bowls', 0)
    confs   = pfr_rec.get('conf_titles', 0)
    total   = wins + losses

    # ── I/E signals ──────────────────────────────────────────────────────────
    # Longevity + consistency = introvert grinder signal
    # Short tenures + high variance = extrovert / emotional signal
    if yrs >= 15 and wl_pct >= 0.55:
        signals['ie'] = 'I'
        signals['ie_evidence'].append(f'{yrs} years, {wl_pct:.3f} W-L% — sustained excellence suggests internal drive over external validation')
    elif yrs >= 10 and wl_pct >= 0.50:
        signals['ie'] = 'I'
        signals['ie_evidence'].append(f'{yrs} years at .500+ — consistency over flash')
    elif yrs <= 3 and total >= 20:
        signals['ie'] = 'E'
        signals['ie_evidence'].append('Early career — insufficient data for I/E inference')

    # ── T/F signals ──────────────────────────────────────────────────────────
    # High W-L% with multiple playoff runs = analytical/systematic (T)
    # Volatile record, short tenures, multiple firings = emotional/reactive (F)
    pfr_from = pfr_rec.get('pfr_from', 0)
    pfr_to   = pfr_rec.get('pfr_to', 0)
    tenures  = _count_tenures(pfr_from, pfr_to, yrs)

    if wl_pct >= 0.600 and confs >= 1:
        signals['tf'] = 'T'
        signals['tf_evidence'].append(f'{wl_pct:.3f} W-L%, {confs} conf title(s) — systematic approach, results-driven')
    elif wl_pct >= 0.550 and yrs >= 8:
        signals['tf'] = 'T'
        signals['tf_evidence'].append(f'{wl_pct:.3f} W-L% over {yrs} years — analytical consistency')
    elif wl_pct < 0.450 and yrs >= 5:
        signals['tf'] = 'F'
        signals['tf_evidence'].append(f'{wl_pct:.3f} W-L% — may prioritize relationships over results, or reactive under pressure')
    elif tenures > 2 and yrs < 10:
        signals['tf'] = 'F'
        signals['tf_evidence'].append(f'Multiple short tenures — possible emotional volatility or poor fit pattern')

    if sbs >= 1:
        signals['tf'] = 'T'
        signals['tf_evidence'].append(f'{sbs} Super Bowl win(s) — elite systematic execution under pressure')

    # Playing career boosts T confidence if already leaning T
    if career and career.get('played_nfl') and signals['tf'] == 'T':
        signals['tf_evidence'].append('NFL playing career + analytical record = strong T signal')

    # Confidence: both axes inferred = medium, one = low
    if signals['ie'] and signals['tf']:
        signals['confidence'] = 'medium'
    elif signals['ie'] or signals['tf']:
        signals['confidence'] = 'low'

    return signals


def _count_tenures(pfr_from, pfr_to, yrs):
    """Rough estimate of number of separate stints."""
    span = (pfr_to - pfr_from + 1) if pfr_to > pfr_from else 1
    if span <= 0 or yrs <= 0:
        return 1
    # If years coached << span, they had gaps = multiple tenures
    gap_ratio = (span - yrs) / span
    if gap_ratio > 0.3:
        return 3
    elif gap_ratio > 0.1:
        return 2
    return 1


def inferred_type(signals):
    """Build best-guess type string from available signals."""
    ie = signals.get('ie') or '?'
    tf = signals.get('tf') or '?'
    sn = signals.get('sn') or '?'
    jp = signals.get('jp') or '?'
    # Standard MBTI order: E/I, S/N, T/F, J/P
    return f"{ie}{sn}{tf}{jp}"


# ── ROLE FIT SCORE ────────────────────────────────────────────────────────────

def role_fit_score(signals, role, pfr_rec):
    """
    Score 0-100 how well inferred personality fits the role.
    HC: needs T + I (systematic, internal drive)
    OC: needs N + E (creative, communicative)
    DC: needs T + J (analytical, structured)
    """
    score    = 50  # baseline
    evidence = []

    ie = signals.get('ie')
    tf = signals.get('tf')
    pfr_rec = pfr_rec or {}
    wl_pct  = pfr_rec.get('reg_wl_pct', 0)
    sbs     = pfr_rec.get('super_bowls', 0)
    confs   = pfr_rec.get('conf_titles', 0)
    yrs     = pfr_rec.get('pfr_yrs', 0)

    if role == 'hc':
        if tf == 'T':
            score += 20
            evidence.append('Analytical profile fits HC decision-making demands')
        if ie == 'I':
            score += 10
            evidence.append('Internal drive — less susceptible to media/crowd pressure')
        if wl_pct >= 0.600:
            score += 15
            evidence.append(f'Elite W-L% ({wl_pct:.3f}) — proven results')
        elif wl_pct >= 0.500:
            score += 5
        if sbs >= 1:
            score += 10
            evidence.append(f'{sbs} Super Bowl(s) — peak performance validated')
        if confs >= 2:
            score += 5
        if yrs >= 10:
            score += 5
            evidence.append(f'{yrs} years experience — battle-tested')
        if tf == 'F' and yrs >= 5:
            score -= 10
            evidence.append('Feeling profile may struggle with cold analytical decisions under pressure')

    elif role == 'oc':
        if ie == 'E':
            score += 15
            evidence.append('Extrovert profile — communicates scheme to QB and skill players effectively')
        if tf == 'T':
            score += 10
            evidence.append('Analytical — scheme design and play-calling under pressure')
        if wl_pct >= 0.550:
            score += 10
            evidence.append('Winning pedigree as HC — understands full game context')

    elif role == 'dc':
        if tf == 'T':
            score += 20
            evidence.append('Analytical profile — scheme recognition and in-game adjustments')
        if ie == 'I':
            score += 10
            evidence.append('Internal focus — preparation over reaction')
        if wl_pct >= 0.550:
            score += 10
            evidence.append('Winning pedigree — understands what it takes to win')

    score = max(0, min(100, score))
    return score, evidence


# ── COACH MARKET FIT ─────────────────────────────────────────────────────────

def coach_market_fit(slug, signals, pfr_rec, avg_roster_compat=None):
    """
    Score 0-100 how well an HC's personality fits their market environment.
    Three inputs:
      1. I/E vs market pressure — introvert in high-pressure market = structural drain
      2. Tenure as ownership stability proxy — longer = more stable environment
      3. Roster compat avg — HC surrounded by compatible players = lower friction

    Returns (score 0-100, evidence list).
    Max effect on team score: ±3% (subtle but real — nobody else tracks this).
    """
    pressure = MARKET_PRESSURE.get(slug, 5)  # default mid-pressure
    ie       = signals.get('ie')
    pfr_rec  = pfr_rec or {}
    yrs      = pfr_rec.get('pfr_yrs', 0)

    score    = 50
    evidence = []

    # ── I/E vs market pressure ────────────────────────────────────────────────
    # Introvert in high-pressure market (8+) = energy drain
    # Extrovert in high-pressure market = natural fit
    # Introvert in low-pressure market (<=4) = optimal environment
    if ie == 'I':
        if pressure >= 8:
            score -= 15
            evidence.append(
                f'Introvert HC in high-pressure market ({slug.upper()}, pressure={pressure}/10) '
                f'— structural energy drain, media demands conflict with internal processing style'
            )
        elif pressure <= 4:
            score += 10
            evidence.append(
                f'Introvert HC in low-pressure market ({slug.upper()}, pressure={pressure}/10) '
                f'— optimal environment, internal drive unimpeded by external noise'
            )
        else:
            evidence.append(
                f'Introvert HC in mid-pressure market ({slug.upper()}, pressure={pressure}/10) '
                f'— manageable friction'
            )
    elif ie == 'E':
        if pressure >= 8:
            score += 10
            evidence.append(
                f'Extrovert HC in high-pressure market ({slug.upper()}, pressure={pressure}/10) '
                f'— thrives on external energy, media demands are fuel not friction'
            )
        elif pressure <= 4:
            score -= 5
            evidence.append(
                f'Extrovert HC in low-pressure market ({slug.upper()}, pressure={pressure}/10) '
                f'— may seek external validation the market doesn\'t provide'
            )
    else:
        evidence.append(f'I/E not yet inferred — market fit score is partial ({slug.upper()}, pressure={pressure}/10)')

    # ── Tenure as ownership stability proxy ───────────────────────────────────
    # Long tenure = ownership trusts the coach = stable environment
    # Short tenure = volatile situation regardless of market
    if yrs >= 10:
        score += 15
        evidence.append(f'{yrs} years tenure — ownership stability confirmed, long-term trust established')
    elif yrs >= 6:
        score += 8
        evidence.append(f'{yrs} years tenure — established relationship with ownership')
    elif yrs >= 3:
        score += 3
        evidence.append(f'{yrs} years tenure — building stability')
    elif yrs > 0:
        score -= 8
        evidence.append(f'{yrs} year(s) tenure — early, ownership relationship unproven')

    # ── Roster compat avg ─────────────────────────────────────────────────────
    # HC surrounded by compatible players = lower daily friction = more energy for game prep
    if avg_roster_compat is not None:
        if avg_roster_compat >= 65:
            score += 10
            evidence.append(
                f'High roster compat avg ({avg_roster_compat:.0f}) — HC personality aligns with key players, '
                f'communication friction low'
            )
        elif avg_roster_compat >= 50:
            score += 3
            evidence.append(f'Adequate roster compat avg ({avg_roster_compat:.0f})')
        else:
            score -= 8
            evidence.append(
                f'Low roster compat avg ({avg_roster_compat:.0f}) — HC personality misaligned with key players, '
                f'daily friction compounds market pressure'
            )

    score = max(0, min(100, score))
    return score, evidence


# ── MAIN ──────────────────────────────────────────────────────────────────────

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def main():
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f'fetch_coaches.py — {now_str}')
    print(f'Data source: Pro Football Reference https://www.pro-football-reference.com/coaches/')

    pfr_records     = load_pfr_records(CSV_FILE)
    playing_careers = load_playing_careers(CAREERS_FILE)

    # Load players.json for roster compat avg (HC market fit input)
    players_path = os.path.join(DATA_DIR, 'players.json')
    players_data = load_json(players_path)
    players_list = players_data.get('players', []) if isinstance(players_data, dict) else []

    # Build slug → avg team_compat_score for HC players (starters only)
    ABBR_TO_SLUG_LOCAL = {
        'BUF':'buf','MIA':'mia','NE':'ne','NYJ':'nyj','BAL':'bal','CIN':'cin',
        'CLE':'cle','PIT':'pit','HOU':'hou','IND':'ind','JAX':'jax','TEN':'ten',
        'DEN':'den','KC':'kc','LV':'lv','LAC':'lac','DAL':'dal','NYG':'nyg',
        'PHI':'phi','WAS':'wsh','CHI':'chi','DET':'det','GB':'gb','MIN':'min',
        'ATL':'atl','CAR':'car','NO':'no','TB':'tb','ARI':'ari','LA':'lar',
        'SF':'sf','SEA':'sea',
    }
    roster_compat_by_slug = {}
    for p in players_list:
        slug = ABBR_TO_SLUG_LOCAL.get((p.get('team') or '').upper())
        snap = (p.get('layer1_body') or {}).get('snap_pct') or 0
        cs   = (p.get('layer4_personality') or {}).get('team_compat_score')
        if slug and snap >= 0.40 and cs is not None:
            roster_compat_by_slug.setdefault(slug, []).append(cs)
    avg_compat_by_slug = {
        slug: round(sum(scores) / len(scores), 1)
        for slug, scores in roster_compat_by_slug.items() if scores
    }

    # Scan news for coaching changes
    print('\nScanning ESPN news for coaching changes...')
    headlines = fetch_headlines()
    changes   = detect_changes(headlines, CURRENT_STAFF)
    if changes:
        print(f'  ⚠ {len(changes)} potential coaching change headline(s) detected:')
        for c in changes:
            print(f'    [{c["team"].upper()}] {c["coach"]} ({c["role"]}): {c["headline"]}')
        print('  → Review and update CURRENT_STAFF in fetch_coaches.py if confirmed.')
    else:
        print('  No coaching change headlines detected.')

    # Build coaches.json
    coaches_out = []
    for slug, staff in CURRENT_STAFF.items():
        for role, coach_name in staff.items():
            key     = _normalize_name(coach_name)
            pfr_rec = pfr_records.get(key)

            # Fuzzy fallback — try last name only
            if not pfr_rec:
                last = coach_name.split()[-1].lower()
                for k, v in pfr_records.items():
                    if k.endswith(last):
                        pfr_rec = v
                        break

            career    = playing_careers.get(coach_name)
            signals   = infer_mbti_signals(coach_name, pfr_rec, role, career)
            fit, fit_ev = role_fit_score(signals, role, pfr_rec)
            mbti_type = inferred_type(signals)

            # Coach market fit — HC only
            mf_score, mf_ev = (None, [])  # default for OC/DC
            if role == 'hc':
                avg_rc   = avg_compat_by_slug.get(slug)
                mf_score, mf_ev = coach_market_fit(slug, signals, pfr_rec, avg_rc)

            entry = {
                'name':                    coach_name,
                'team_slug':               slug,
                'role':                    role,
                'role_label':              ROLE_LABELS[role],
                'playing_career':          career,
                'pfr_record':              pfr_rec,
                'mbti_signals':            signals,
                'mbti_type':               mbti_type,
                'role_fit_score':          fit,
                'role_fit_evidence':       fit_ev,
                'coach_market_fit_score':  mf_score,
                'coach_market_fit_evidence': mf_ev,
                'market_pressure':         MARKET_PRESSURE.get(slug) if role == 'hc' else None,
                'last_updated':            now_str,
                'pfr_source':              'https://www.pro-football-reference.com/coaches/',
            }
            coaches_out.append(entry)

            status = f'{mbti_type} fit={fit}'
            if role == 'hc' and mf_score is not None:
                status += f' mktfit={mf_score}'
            pfr_str = f'{pfr_rec["reg_wins"]}-{pfr_rec["reg_losses"]} ({pfr_rec["reg_wl_pct"]:.3f})' if pfr_rec else 'no PFR record'
            print(f'  [{slug.upper():3}] {coach_name:<28} {ROLE_LABELS[role]:<25} {pfr_str:<20} {status}')

    # ── COORDINATOR CHANGE DETECTION ─────────────────────────────────────────
    # Compare new staff against previous coaches.json to detect OC/DC changes.
    # Writes coordinator_changes list — consumed by infer_personality.py.
    prev_coaches = load_json(COACHES_FILE)
    prev_by_key  = {(c['team_slug'], c['role']): c['name'] for c in prev_coaches.get('coaches', [])}

    metadata     = load_json(META_FILE)
    current_week = metadata.get('week', 1)

    # Carry forward uncleared changes from previous run
    prev_coord_changes = prev_coaches.get('coordinator_changes', [])

    new_coord_changes = []
    for slug, staff in CURRENT_STAFF.items():
        for role in ('oc', 'dc'):
            new_name  = staff.get(role)
            prev_name = prev_by_key.get((slug, role))
            if prev_name and new_name and prev_name != new_name:
                new_coord_changes.append({
                    'team_slug':    slug,
                    'role':         role,
                    'old_name':     prev_name,
                    'new_name':     new_name,
                    'week_detected': current_week,
                })
                print(f'  ⚠ COORDINATOR CHANGE [{slug.upper()}] {role.upper()}: {prev_name} → {new_name} (week {current_week})')

    # Merge: keep prior changes not yet expired (expiry handled in infer_personality.py)
    # Deduplicate by (team_slug, role) — new change wins
    merged_changes = {(c['team_slug'], c['role']): c for c in prev_coord_changes}
    for c in new_coord_changes:
        merged_changes[(c['team_slug'], c['role'])] = c
    coordinator_changes = list(merged_changes.values())

    if not new_coord_changes:
        print('  No coordinator changes detected.')

    save_json(COACHES_FILE, {
        'last_updated':        now_str,
        'pfr_source':          'https://www.pro-football-reference.com/coaches/',
        'pfr_citation':        'When using SR data, please cite us and provide a link and/or a mention.',
        'change_flags':        changes,
        'coordinator_changes': coordinator_changes,
        'coaches':             coaches_out,
    })

    metadata['last_coaches_fetch'] = now_str
    save_json(META_FILE, metadata)

    hcs = [c for c in coaches_out if c['role'] == 'hc']
    pfr_matched = sum(1 for c in coaches_out if c['pfr_record'])
    print(f'\n  coaches.json written — {len(coaches_out)} coaches ({len(hcs)} HCs), {pfr_matched} PFR records matched')
    print(f'  Change flags: {len(changes)}')


if __name__ == '__main__':
    main()
