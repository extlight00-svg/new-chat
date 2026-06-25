# External Scheduler for Morning Telegram News

Use Google Apps Script to call the existing GitHub Actions `workflow_dispatch` endpoint every morning.
This avoids relying on GitHub's native scheduled trigger.

## GitHub PAT

Create a fine-grained GitHub personal access token for `extlight00-svg/new-chat`.

Required repository permission:

- Actions: Read and write

Store the token only in Google Apps Script script properties.

## Google Apps Script

1. Open https://script.google.com/
2. Create a new project.
3. Paste the contents of `scheduler/google_apps_script_dispatch.js`.
4. Open Project Settings.
5. Add a script property:

```text
GITHUB_PAT=your_fine_grained_github_token
```

## Trigger

Create a time-driven trigger:

- Function: `triggerMorningNewsWorkflow`
- Event source: Time-driven
- Type: Day timer
- Time: 6am to 7am

Google Apps Script does not guarantee exact minute execution. If exact 6:55 KST is required, use cron-job.org with the same GitHub API endpoint instead.

## Cron-job.org Alternative

Create a daily job at 21:55 UTC.

Request:

```text
POST https://api.github.com/repos/extlight00-svg/new-chat/actions/workflows/morning-news.yml/dispatches
```

Headers:

```text
Accept: application/vnd.github+json
Authorization: Bearer YOUR_GITHUB_PAT
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
```

Body:

```json
{"ref":"main"}
```
