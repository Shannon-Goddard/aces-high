import json, os

path = os.path.join(os.path.dirname(__file__), '..', 'data', 'predictions.json')
d = json.load(open(path, encoding='utf-8'))
preds = d['predictions']

# Deduplicate — keep latest predicted_at per game_id
by_id = {}
for p in preds:
    gid = p['game_id']
    if gid not in by_id or p['predicted_at'] > by_id[gid]['predicted_at']:
        by_id[gid] = p

deduped = sorted(by_id.values(), key=lambda p: p['game_time'])
print(f"Before: {len(preds)}  After dedup: {len(deduped)}")

scores = []
for p in deduped:
    h = p['home_breakdown']['composite']
    a = p['away_breakdown']['composite']
    scores.extend([h, a])
    flag = 'BET' if p['confidence'] >= 40 else 'skip'
    print(f"  {flag} | {p['away_team'][:18]:18} @ {p['home_team']:22} | away={a:5.1f} home={h:5.1f} | conf={p['confidence']}")

print(f"\nComposite range: {min(scores):.1f} - {max(scores):.1f}  (was 22-28)")
print(f"Mean: {sum(scores)/len(scores):.1f}")
print(f"BET count: {sum(1 for p in deduped if p['confidence'] >= 40)}")

d['predictions'] = deduped
with open(path, 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2)
print("\nSaved deduped predictions.")
