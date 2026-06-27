# External Scheduler for Morning Telegram News

Use Google Apps Script to call the existing GitHub Actions `workflow_dispatch` endpoint every morning.
This avoids relying on GitHub's native scheduled trigger.

## Recommended: cron-job.org

Use cron-job.org when the briefing should arrive close to an exact minute.
The job calls GitHub Actions' manual dispatch endpoint at 06:55 KST every day.

### 1. Create GitHub PAT

Create a fine-grained GitHub personal access token for `extlight00-svg/new-chat`.

Required repository permission:

- Actions: Read and write

Do not commit this token and do not paste it into chat. Store it only in cron-job.org.

### 2. Create Cron Job

Create a new cron-job.org job with these values:

```text
Title: Morning Telegram News Briefing
URL: https://api.github.com/repos/extlight00-svg/new-chat/actions/workflows/morning-news.yml/dispatches
Method: POST
Schedule timezone: Asia/Seoul
Schedule: Every day at 06:55
```

Headers:

```text
Accept: application/vnd.github+json
Authorization: Bearer YOUR_GITHUB_PAT
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
User-Agent: cron-job-org-morning-news
```

Request body:

```json
{"ref":"main"}
```

Expected HTTP response:

```text
204 No Content
```

If cron-job.org receives `204`, GitHub accepted the workflow run request.
The Telegram message is then sent by GitHub Actions.

### 3. Recommended GitHub Schedule Cleanup

After cron-job.org is verified for one or two mornings, remove GitHub's native `schedule` triggers or keep only one fallback.
This prevents late GitHub schedule runs from creating confusing execution history.

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
