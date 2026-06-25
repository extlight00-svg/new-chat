const OWNER = 'extlight00-svg';
const REPO = 'new-chat';
const WORKFLOW_FILE = 'morning-news.yml';
const REF = 'main';

function triggerMorningNewsWorkflow() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_PAT');
  if (!token) {
    throw new Error('GITHUB_PAT script property is required.');
  }

  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`;
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    muteHttpExceptions: true,
    contentType: 'application/json',
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'X-GitHub-Api-Version': '2022-11-28',
    },
    payload: JSON.stringify({ ref: REF }),
  });

  const status = response.getResponseCode();
  if (status !== 204) {
    throw new Error(`GitHub workflow dispatch failed: ${status} ${response.getContentText()}`);
  }
}
