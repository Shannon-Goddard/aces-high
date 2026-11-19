"""
fetch_relationships.py — Layer 5 Relationships Web
Builds relationships.json from nflverse roster history.

Three relationship types:
  former_pro_teammate  — same team, overlapping seasons (3yr window), same unit
  former_college_teammate — same college, entry year within 3 years
  facing_former_team   — derived flag, written to player record at prediction time

Sentiment starts neutral for all nflverse-derived relationships.
News scan overlay (fetch_news.py) updates sentiment when keywords fire.

Run: python scripts/fetch_relationships.py
Safe to re-run — rebuilds from scratch, preserves manual/news-updated sentiment.
"""

import csv
import json
import os
from datetime import datetime, timezone
from itertools import combinations

DATA_DIR        = os.path.join(os.path.dirname(__file__), '..', 'data')
PLAYERS_CSV     = os.path.join(DATA_DIR, 'nflverse_players.csv')
PLAYERS_JSON    = os.path.join(DATA_DIR, 'players.json')
RELATIONSHIPS   = os.path.join(DATA_DIR, 'relationships.json')

# How many seasons back a pro teammate connection stays active
PRO_LOOKBACK    = 3

# Max entry-year gap for college teammates to count
COLLEGE_WINDOW  = 3

# Active roster statuses — only build edges where at least one player is active
ACTIVE_STATUSES = {'ACT', 'DEV'}

# Unit grouping by position_group — keeps offense/defense edges meaningful
OFFENSE_GROUPS  = {'QB', 'RB', 'WR', 'TE', 'OL', 'FB', 'SPEC'}
DEFENSE_GROUPS  = {'DL', 'LB', 'DB', 'CB', 'S', 'DE', 'DT'}

# Colleges too large to produce meaningful connections without overlap filter
# (the filter handles this — listed here for documentation)
HIGH_VOLUME_SCHOOLS = {'Alabama', 'Ohio State', 'Georgia', 'LSU', 'Clemson'}


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def load_csv_players():
    """Load nflverse_players.csv — source of truth for career history."""
    players = []
    with open(PLAYERS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            players.append(row)
    return players


def get_unit(position_group):
    """Map position_group to offense/defense/special."""
    pg = (position_group or '').upper()
    if pg in OFFENSE_GROUPS:
        return 'offense'
    if pg in DEFENSE_GROUPS:
        return 'defense'
    return 'special'


def safe_int(val, default=None):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def build_rel_id(id_a, id_b, rel_type):
    """Stable relationship ID — always smaller ID first so A/B order doesn't matter."""
    a, b = sorted([id_a, id_b])
    slug = rel_type[:3]
    return f"rel_{a}_{b}_{slug}"


def compute_strength(seasons_together, same_unit, college_bonus):
    """
    Strength 0-100:
      Base 40 for any former teammate
      +5 per season together (max +25 at 5 seasons)
      +10 same unit (offense/defense — shared meeting room)
      +10 college teammates (pre-draft bond)
    """
    base        = 40
    season_pts  = min(25, len(seasons_together) * 5)
    unit_pts    = 10 if same_unit else 0
    college_pts = 10 if college_bonus else 0
    return min(100, base + season_pts + unit_pts + college_pts)


def build_pro_teammate_edges(csv_players, current_season):
    """
    Join players on (team, season) overlap within PRO_LOOKBACK seasons.
    Only builds edges where at least one player has an active status.
    Returns list of relationship dicts.
    """
    print(f"  Building pro teammate edges (lookback {PRO_LOOKBACK} seasons)...")

    # Build per-team-season roster: {(team, season): [player_dict, ...]}
    team_season_roster = {}
    lookback_start = current_season - PRO_LOOKBACK

    for p in csv_players:
        rookie  = safe_int(p.get('rookie_season'))
        last    = safe_int(p.get('last_season'))
        team    = (p.get('latest_team') or '').strip()
        gsis_id = (p.get('gsis_id') or '').strip()

        if not gsis_id or not team or not rookie or not last:
            continue

        # Seasons this player was on this team — approximate from rookie/last
        # nflverse doesn't give per-season team history in this CSV,
        # so we use latest_team + season range as the best available proxy
        for season in range(max(rookie, lookback_start), last + 1):
            key = (team, season)
            team_season_roster.setdefault(key, []).append(p)

    # For each team-season, generate all pairs
    edges = {}  # rel_id → edge dict (deduplicates across seasons)

    for (team, season), roster in team_season_roster.items():
        if season < lookback_start:
            continue

        # Only process if at least one active player on this roster
        active_ids = {
            p['gsis_id'] for p in roster
            if p.get('status', '') in ACTIVE_STATUSES
        }
        if not active_ids:
            continue

        for p_a, p_b in combinations(roster, 2):
            id_a = p_a['gsis_id']
            id_b = p_b['gsis_id']

            # At least one must be currently active
            if id_a not in active_ids and id_b not in active_ids:
                continue

            # Same unit filter — QB/WR share a meeting room, QB/DL don't
            unit_a = get_unit(p_a.get('position_group'))
            unit_b = get_unit(p_b.get('position_group'))
            same_unit = (unit_a == unit_b) and (unit_a != 'special')
            if not same_unit:
                continue  # cross-unit edges are noise at this stage

            rel_id = build_rel_id(id_a, id_b, 'former_pro_teammate')

            if rel_id not in edges:
                edges[rel_id] = {
                    'id':                 rel_id,
                    'player_a_id':        id_a,
                    'player_a_name':      p_a.get('display_name', ''),
                    'player_b_id':        id_b,
                    'player_b_name':      p_b.get('display_name', ''),
                    'relationship_type':  'former_pro_teammate',
                    'subtype':            None,
                    'unit':               unit_a,
                    'seasons_together':   [season],
                    'strength':           0,
                    'sentiment':          'neutral',
                    'source':             'nflverse',
                    'notes':              None,
                    'last_updated':       None,
                }
            else:
                if season not in edges[rel_id]['seasons_together']:
                    edges[rel_id]['seasons_together'].append(season)

    # Compute final strength now that seasons_together is complete
    result = []
    for edge in edges.values():
        edge['seasons_together'] = sorted(edge['seasons_together'])
        edge['strength'] = compute_strength(
            edge['seasons_together'],
            same_unit=True,   # all edges here passed the same_unit filter
            college_bonus=False
        )
        result.append(edge)

    print(f"    {len(result)} pro teammate edges")
    return result


def build_college_teammate_edges(csv_players, current_season):
    """
    Join players on (college_name) where entry years are within COLLEGE_WINDOW.
    Only builds edges where at least one player is currently active.
    Skips blank/NO COLLEGE entries.
    """
    print(f"  Building college teammate edges (window ±{COLLEGE_WINDOW} years)...")

    # Group by college
    by_college = {}
    for p in csv_players:
        college = (p.get('college_name') or '').strip()
        gsis_id = (p.get('gsis_id') or '').strip()
        rookie  = safe_int(p.get('rookie_season'))

        if not college or not gsis_id or not rookie:
            continue
        if college in ('NO COLLEGE', ''):
            continue

        by_college.setdefault(college, []).append(p)

    active_ids = {
        p['gsis_id'] for p in csv_players
        if p.get('status', '') in ACTIVE_STATUSES and p.get('gsis_id')
    }

    edges = {}

    for college, roster in by_college.items():
        if len(roster) < 2:
            continue

        for p_a, p_b in combinations(roster, 2):
            id_a    = p_a['gsis_id']
            id_b    = p_b['gsis_id']
            entry_a = safe_int(p_a.get('rookie_season'))
            entry_b = safe_int(p_b.get('rookie_season'))

            if not entry_a or not entry_b:
                continue

            # At least one currently active
            if id_a not in active_ids and id_b not in active_ids:
                continue

            # Entry year overlap — prevents Alabama 2010 connecting to Alabama 2026
            if abs(entry_a - entry_b) > COLLEGE_WINDOW:
                continue

            rel_id = build_rel_id(id_a, id_b, 'former_college_teammate')

            if rel_id not in edges:
                unit_a = get_unit(p_a.get('position_group'))
                unit_b = get_unit(p_b.get('position_group'))
                same_unit = (unit_a == unit_b) and (unit_a != 'special')

                edges[rel_id] = {
                    'id':                 rel_id,
                    'player_a_id':        id_a,
                    'player_a_name':      p_a.get('display_name', ''),
                    'player_b_id':        id_b,
                    'player_b_name':      p_b.get('display_name', ''),
                    'relationship_type':  'former_college_teammate',
                    'subtype':            None,
                    'unit':               unit_a if same_unit else 'mixed',
                    'seasons_together':   [],  # college — no season data
                    'strength':           compute_strength([], same_unit, college_bonus=True),
                    'sentiment':          'neutral',
                    'source':             'nflverse',
                    'notes':              college,
                    'last_updated':       None,
                }

    result = list(edges.values())
    print(f"    {len(result)} college teammate edges")
    return result


def preserve_sentiment(existing_rels, new_rels):
    """
    Re-run safety: preserve any sentiment that was manually set or
    updated by the news scan overlay. neutral → neutral is fine to overwrite,
    but positive/negative sentiment is kept.
    """
    sentiment_map = {
        r['id']: r['sentiment']
        for r in existing_rels
        if r.get('sentiment') and r['sentiment'] != 'neutral'
    }
    for rel in new_rels:
        if rel['id'] in sentiment_map:
            rel['sentiment'] = sentiment_map[rel['id']]
    return new_rels


# Position groups that form meaningful units — cohesion is real within these groups
UNIT_GROUPS = {
    'OL':        {'OL', 'FB'},
    'secondary': {'DB', 'CB', 'S'},
    'lb_corps':  {'LB'},
    'wr_corps':  {'WR'},
    'dl_corps':  {'DL', 'DE', 'DT'},
}


def build_unit_cohesion_scores(csv_players, current_season):
    """
    For each team, score each unit group (OL, secondary, LB corps, WR corps, DL corps)
    by how long the players in that group have been together.

    cohesion_score 0-100:
      Base 40 for any unit with 2+ players
      +6 per average seasons together (max +30 at 5 seasons)
      +10 if 3+ players have been together 2+ seasons (core stability bonus)
      +20 if 4+ players have been together 3+ seasons (elite cohesion)

    Returns: {team: {group_name: cohesion_score}}
    Also returns: {gsis_id: {unit_cohesion_score, unit_cohesion_group}}
    """
    print(f"  Building unit cohesion scores...")

    lookback_start = current_season - PRO_LOOKBACK
    active_ids = {
        p['gsis_id'] for p in csv_players
        if p.get('status', '') in ACTIVE_STATUSES and p.get('gsis_id')
    }

    # Build team → group → [players]
    team_units = {}  # team → group_name → [player]
    for p in csv_players:
        gsis  = (p.get('gsis_id') or '').strip()
        team  = (p.get('latest_team') or '').strip()
        pg    = (p.get('position_group') or '').upper()
        last  = safe_int(p.get('last_season'))

        if not gsis or not team or not pg or not last:
            continue
        if gsis not in active_ids:
            continue
        if last < lookback_start:
            continue

        for group_name, positions in UNIT_GROUPS.items():
            if pg in positions:
                team_units.setdefault(team, {}).setdefault(group_name, []).append(p)
                break

    # For each team+group, compute pairwise seasons together
    team_cohesion  = {}  # team → group → score
    player_cohesion = {}  # gsis_id → {score, group}

    for team, groups in team_units.items():
        team_cohesion[team] = {}
        for group_name, members in groups.items():
            if len(members) < 2:
                team_cohesion[team][group_name] = 40  # single player, base only
                for m in members:
                    player_cohesion[m['gsis_id']] = {'unit_cohesion_score': 40, 'unit_cohesion_group': group_name}
                continue

            # Count overlapping seasons per pair
            pair_seasons = []
            for p_a, p_b in combinations(members, 2):
                rookie_a = safe_int(p_a.get('rookie_season')) or lookback_start
                last_a   = safe_int(p_a.get('last_season'))   or current_season
                rookie_b = safe_int(p_b.get('rookie_season')) or lookback_start
                last_b   = safe_int(p_b.get('last_season'))   or current_season

                overlap_start = max(rookie_a, rookie_b, lookback_start)
                overlap_end   = min(last_a, last_b, current_season)
                seasons = max(0, overlap_end - overlap_start + 1)
                pair_seasons.append(seasons)

            avg_seasons = sum(pair_seasons) / len(pair_seasons) if pair_seasons else 0

            # Core stability: how many players have 2+ seasons with at least one other member
            # Approximate: count members whose last_season >= lookback_start + 1
            core_members = sum(
                1 for m in members
                if (safe_int(m.get('last_season')) or 0) >= lookback_start + 1
                and (safe_int(m.get('rookie_season')) or current_season) <= lookback_start + 1
            )
            elite_members = sum(
                1 for m in members
                if (safe_int(m.get('last_season')) or 0) >= lookback_start + 2
                and (safe_int(m.get('rookie_season')) or current_season) <= lookback_start
            )

            score = 40
            score += min(30, round(avg_seasons * 6))
            if core_members >= 3:
                score += 10
            if elite_members >= 4:
                score += 20
            score = min(100, score)

            team_cohesion[team][group_name] = score
            for m in members:
                player_cohesion[m['gsis_id']] = {
                    'unit_cohesion_score': score,
                    'unit_cohesion_group': group_name,
                }

    # Summary
    total_players = len(player_cohesion)
    avg_score = round(sum(v['unit_cohesion_score'] for v in player_cohesion.values()) / total_players, 1) if total_players else 0
    print(f"    {total_players} players scored | avg cohesion: {avg_score}")
    return player_cohesion


def write_unit_cohesion(players_data, player_cohesion):
    """Write layer6_chemistry block to each player record."""
    updated = 0
    for player in players_data.get('players', []):
        gsis = player.get('gsis_id', '')
        data = player_cohesion.get(gsis)
        existing = player.get('layer6_chemistry')
        new_val = data if data else {'unit_cohesion_score': None, 'unit_cohesion_group': None}
        if existing != new_val:
            player['layer6_chemistry'] = new_val
            updated += 1
    print(f"  Updated layer6_chemistry on {updated} player records")
    return players_data


def write_player_rel_ids(players_data, all_rels):
    """
    Write relationship IDs to each player's layer5_relationships list.
    Replaces the existing list — source of truth is relationships.json.
    """
    # Build player_id → [rel_ids] index
    rel_index = {}
    for rel in all_rels:
        for pid in (rel['player_a_id'], rel['player_b_id']):
            rel_index.setdefault(pid, []).append(rel['id'])

    updated = 0
    for player in players_data.get('players', []):
        pid = player.get('gsis_id', '')
        ids = rel_index.get(pid, [])
        if player.get('layer5_relationships') != ids:
            player['layer5_relationships'] = ids
            updated += 1

    print(f"  Updated layer5_relationships on {updated} player records")
    return players_data


def main():
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"fetch_relationships.py — {now_str}")

    # Determine current season from players.json metadata
    players_data   = load_json(PLAYERS_JSON)
    existing_rels  = load_json(RELATIONSHIPS)
    csv_players    = load_csv_players()

    # Use the most recent last_season value as current season proxy
    seasons = [
        safe_int(p.get('last_season'))
        for p in csv_players
        if safe_int(p.get('last_season'))
    ]
    current_season = max(seasons) if seasons else 2026
    print(f"  Current season: {current_season}")
    print(f"  CSV players loaded: {len(csv_players)}")

    # Build edges
    pro_edges     = build_pro_teammate_edges(csv_players, current_season)
    college_edges = build_college_teammate_edges(csv_players, current_season)
    all_rels      = pro_edges + college_edges

    # Preserve any non-neutral sentiment from previous runs
    all_rels = preserve_sentiment(existing_rels.get('relationships', []), all_rels)

    # Stamp last_updated on new/changed records
    for rel in all_rels:
        if not rel.get('last_updated'):
            rel['last_updated'] = now_str[:10]

    # Write relationships.json
    save_json(RELATIONSHIPS, {
        'last_updated':  now_str,
        'total':         len(all_rels),
        'relationships': all_rels,
    })
    print(f"  relationships.json — {len(all_rels)} total edges")

    # Write rel IDs back to players.json
    players_data = write_player_rel_ids(players_data, all_rels)

    # Build + write unit cohesion scores (Layer 6)
    player_cohesion = build_unit_cohesion_scores(csv_players, current_season)
    players_data    = write_unit_cohesion(players_data, player_cohesion)

    players_data['last_updated'] = now_str
    save_json(PLAYERS_JSON, players_data)
    print(f"  players.json updated")

    # Summary
    pro_count     = sum(1 for r in all_rels if r['relationship_type'] == 'former_pro_teammate')
    college_count = sum(1 for r in all_rels if r['relationship_type'] == 'former_college_teammate')
    print(f"\nDone.")
    print(f"  Pro teammate edges:     {pro_count}")
    print(f"  College teammate edges: {college_count}")
    print(f"  Total:                  {len(all_rels)}")


if __name__ == '__main__':
    main()
