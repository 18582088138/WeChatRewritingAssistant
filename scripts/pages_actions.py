"""Verify exact-commit workflow results via the API or GitHub's public Actions page."""

import json

from bs4 import BeautifulSoup


def read_runs(client, repo):
    response = client.get(
        "https://api.github.com/repos/" + repo + "/actions/runs?per_page=30"
    )
    if response.status_code not in {403, 429}:
        response.raise_for_status()
        return response.json()["workflow_runs"], "github_rest_api"
    # Anonymous requests behind a shared proxy can exhaust the public API quota.
    response = client.get("https://github.com/" + repo + "/actions")
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    data = soup.select_one('script[data-target="react-app.embeddedData"]')
    assert data, "GitHub Actions page did not contain structured run data"
    runs = json.loads(data.string)["payload"]["allWorkflowRunsRoute"]["workflowRuns"]
    return [
        dict(
            name=r["workflowName"],
            head_sha=r["description"]["linkUrl"].split("/")[-1],
            conclusion=(r["state"].get("conclusion") or "")
            .removeprefix("WORKFLOW_RUN_CONCLUSION_")
            .lower(),
            status=r["state"]["status"].removeprefix("WORKFLOW_RUN_STATUS_").lower(),
            html_url=r["runUrl"],
        )
        for r in runs
    ], "github_actions_page"


def check_workflows(client, repo, sha):
    runs, source = read_runs(client, repo)
    checked = []
    for name in ["Test", "Deploy frontend to GitHub Pages"]:
        matching = [
            run for run in runs if run["head_sha"] == sha and run["name"] == name
        ]
        assert matching, "No workflow run for current commit: " + name
        run = matching[0]
        assert run["conclusion"] == "success", name + ": " + str(run["conclusion"])
        checked.append(
            dict(
                name=name,
                sha=sha,
                conclusion=run["conclusion"],
                url=run["html_url"],
                evidence_source=source,
            )
        )
    return checked
