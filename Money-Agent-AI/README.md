# Money Agent AI — Unified local build

A low-resource local task workflow dashboard designed for Android/Pydroid 3 or desktop Python. It includes a live local worker, task queue, task processing, GitHub public issue lookup, work-status tracking, recovery, and a user-entered payout ledger.

## Run on Android
1. Download or clone this repository.
2. Open `Money-Agent-AI/server.py` in Pydroid 3 and press Run.
3. Keep the Python process running.
4. Open Chrome at http://127.0.0.1:8765.

## Run on desktop
Requires Python 3.9+; standard library only:
```bash
python server.py
```
Then visit http://127.0.0.1:8765.

## Important limitations
- This is a task workflow tool, not a guaranteed income generator. The $5–$10/day goal is not guaranteed.
- Public GitHub issues are not necessarily paid work. Verify reward, eligibility, and terms before doing work.
- It does not submit code, message clients, or change third-party platforms.
- Payouts are manually recorded by the user and are not independently verified.
- Zillow scraping is not included; use only expressly authorized APIs and access.
- The worker runs only while the local Python process remains alive. Android may suspend background processes.
- Do not store passwords, bank credentials, private keys, or other secrets in task notes.

## Workflow
1. Discover an opportunity from an authorized source or enter a task.
2. Check the source, reward evidence, terms, eligibility, and deadline.
3. Queue and process supported local tasks.
4. Review output and submit real work yourself through the platform under its rules.
5. Update work status only when the real status changes.
6. Record a payout only after you actually receive it, with a reference.

Official reference: https://docs.github.com/en/rest/issues
