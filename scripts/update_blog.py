"""
update_blog.py — Blog enrichment utility

record_outcome.py writes the initial blog post when a bet closes.
This script lets you:
  - Add a YouTube video ID to a post
  - Edit the lesson on a post
  - Unpublish a post (set published: false)
  - List all posts

Usage:
  python scripts/update_blog.py list
  python scripts/update_blog.py youtube <bet_id> <youtube_id>
  python scripts/update_blog.py lesson  <bet_id> "New lesson text"
  python scripts/update_blog.py hide    <bet_id>
  python scripts/update_blog.py show    <bet_id>
"""

import json
import os
import sys

DATA_DIR  = os.path.join(os.path.dirname(__file__), '..', 'data')
BLOG_FILE = os.path.join(DATA_DIR, 'blog.json')


def load():
    with open(BLOG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save(data):
    with open(BLOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def find_post(posts, bet_id):
    for p in posts:
        if p['id'] == bet_id:
            return p
    return None


def cmd_list(posts):
    if not posts:
        print("No posts yet.")
        return
    print(f"{'ID':<30} {'Week':<6} {'Result':<8} {'YouTube':<14} {'Published'}")
    print("─" * 75)
    for p in sorted(posts, key=lambda x: x.get('date',''), reverse=True):
        yt  = p.get('youtube_id') or '—'
        pub = '✓' if p.get('published', True) else '✗ hidden'
        print(f"{p['id']:<30} {str(p.get('week','')):<6} {str(p.get('result','')):<8} {yt:<14} {pub}")


def cmd_youtube(posts, bet_id, youtube_id):
    post = find_post(posts, bet_id)
    if not post:
        print(f"Post not found: {bet_id}")
        sys.exit(1)
    post['youtube_id'] = youtube_id
    print(f"Set YouTube ID on '{bet_id}': {youtube_id}")


def cmd_lesson(posts, bet_id, lesson):
    post = find_post(posts, bet_id)
    if not post:
        print(f"Post not found: {bet_id}")
        sys.exit(1)
    post['lesson'] = lesson
    print(f"Updated lesson on '{bet_id}'")


def cmd_visibility(posts, bet_id, published):
    post = find_post(posts, bet_id)
    if not post:
        print(f"Post not found: {bet_id}")
        sys.exit(1)
    post['published'] = published
    print(f"{'Published' if published else 'Hidden'}: {bet_id}")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    data  = load()
    posts = data.get('posts', [])
    cmd   = args[0].lower()

    if cmd == 'list':
        cmd_list(posts)

    elif cmd == 'youtube':
        if len(args) < 3:
            print("Usage: update_blog.py youtube <bet_id> <youtube_id>")
            sys.exit(1)
        cmd_youtube(posts, args[1], args[2])
        save(data)

    elif cmd == 'lesson':
        if len(args) < 3:
            print("Usage: update_blog.py lesson <bet_id> \"lesson text\"")
            sys.exit(1)
        cmd_lesson(posts, args[1], ' '.join(args[2:]))
        save(data)

    elif cmd == 'hide':
        if len(args) < 2:
            print("Usage: update_blog.py hide <bet_id>")
            sys.exit(1)
        cmd_visibility(posts, args[1], False)
        save(data)

    elif cmd == 'show':
        if len(args) < 2:
            print("Usage: update_blog.py show <bet_id>")
            sys.exit(1)
        cmd_visibility(posts, args[1], True)
        save(data)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
