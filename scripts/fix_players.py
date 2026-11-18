import re, json, os

path = os.path.join(os.path.dirname(__file__), '..', 'data', 'players.json')

with open(path, 'r', encoding='utf-8') as f:
    raw = f.read()

nan_count = raw.count('NaN')
print(f"NaN before: {nan_count}")

fixed = re.sub(r'\bNaN\b', 'null', raw)
print(f"NaN after:  {fixed.count('NaN')}")

# Verify it parses
d = json.loads(fixed)
print(f"Players: {len(d.get('players', []))}")

with open(path, 'w', encoding='utf-8') as f:
    f.write(fixed)

print("Saved.")
