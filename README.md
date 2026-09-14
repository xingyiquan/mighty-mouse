# page-fetch-worker

A small runner for scheduled page-fetch jobs.

It holds no job logic. On each run it asks the configured API for a work plan,
runs the program that plan returns, and posts the outcome back over the same
authenticated connection.

## Setup

Repository secrets:

| Secret            | Value                          |
| ----------------- | ------------------------------ |
| `WORKER_API_BASE` | base URL of the API            |
| `WORKER_TOKEN`    | bearer token for that API      |

Then start a run from the Actions tab (or by API dispatch) with a task id.

## Files

- `worker/run.py` — the runner
- `worker/requirements.txt` — base packages
- `.github/workflows/run.yml` — manual-dispatch workflow
