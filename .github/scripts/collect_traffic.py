#!/usr/bin/env python3
"""Collect GitHub traffic stats (clones and views) for my public repos.

GitHub only exposes the last 14 days of traffic data, so this script runs
weekly and merges each new window into per-repo JSON files under traffic/,
building a permanent history before the data expires.
"""

import json
import os
import urllib.error
import urllib.request
from datetime import date

OWNER = "andresleecom"
REPOS = [
    "map",
    "claude-handoff",
    "kube-guard",
    "mcp-lean",
    "speech",
    "brauo",
    "sonosctl",
    "x-cli",
]
OUT_DIR = "traffic"


def fetch(repo, kind):
    url = f"https://api.github.com/repos/{OWNER}/{repo}/traffic/{kind}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + os.environ["TRAFFIC_TOKEN"],
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def merge(existing, incoming):
    """Merge daily entries, deduping by timestamp.

    When both sides have an entry for the same day, keep the one with the
    higher count: numbers late in the 14-day window settle upward.
    """
    by_timestamp = {entry["timestamp"]: entry for entry in existing}
    for entry in incoming:
        current = by_timestamp.get(entry["timestamp"])
        if current is None or entry["count"] > current["count"]:
            by_timestamp[entry["timestamp"]] = {
                "timestamp": entry["timestamp"],
                "count": entry["count"],
                "uniques": entry["uniques"],
            }
    return [by_timestamp[timestamp] for timestamp in sorted(by_timestamp)]


def load_history(path):
    if not os.path.exists(path):
        return {"clones": [], "views": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("history", {"clones": [], "views": []})


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for repo in REPOS:
        try:
            clones = fetch(repo, "clones")
            views = fetch(repo, "views")
        except urllib.error.HTTPError as error:
            print(f"warning: skipping {repo}: HTTP {error.code} {error.reason}")
            continue
        except urllib.error.URLError as error:
            print(f"warning: skipping {repo}: {error.reason}")
            continue

        path = os.path.join(OUT_DIR, f"{repo}.json")
        history = load_history(path)
        merged_clones = merge(history.get("clones", []), clones.get("clones", []))
        merged_views = merge(history.get("views", []), views.get("views", []))

        data = {
            "total_clones": sum(e["count"] for e in merged_clones),
            "total_clone_uniques": sum(e["uniques"] for e in merged_clones),
            "total_views": sum(e["count"] for e in merged_views),
            "total_view_uniques": sum(e["uniques"] for e in merged_views),
            "updated": date.today().isoformat(),
            "history": {"clones": merged_clones, "views": merged_views},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        print(f"{repo}: {data['total_clones']} clones, {data['total_views']} views")


if __name__ == "__main__":
    main()
