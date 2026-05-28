#!/usr/bin/env python3
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


REPOSITORY = "extlight00-svg/new-chat"
PRIMARY_WORKFLOW = "morning-news.yml"


def github_api(path, token):
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "morning-news-backup-check",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    token = os.environ.get("GITHUB_TOKEN")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")
    if not output_path:
        raise RuntimeError("GITHUB_OUTPUT is required")

    now = datetime.now(timezone.utc)
    window_start = now.replace(hour=21, minute=5, second=0, microsecond=0)
    if now < window_start:
        window_start -= timedelta(days=1)

    query = urllib.parse.urlencode({"event": "schedule", "per_page": "20"})
    payload = github_api(
        f"/repos/{REPOSITORY}/actions/workflows/{PRIMARY_WORKFLOW}/runs?{query}",
        token,
    )

    found_success = False
    for run in payload.get("workflow_runs", []):
        created_at = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        if created_at < window_start:
            continue
        if run.get("status") == "completed" and run.get("conclusion") == "success":
            found_success = True
            print(f"Primary briefing already succeeded: {run.get('html_url')}")
            break

    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"should_send={'false' if found_success else 'true'}\n")

    if found_success:
        print("Backup send skipped.")
    else:
        print("No successful primary scheduled run found. Backup send should proceed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Backup check failed: {exc}", file=sys.stderr)
        raise
