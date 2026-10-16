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


## Bounded agent runtime upgrade

The feature branch `feature/agent-runtime-wallet-monitor` adds a standard-library runtime module and HTTP endpoints for:
- A bounded registry of logical worker slots (default maximum 4; configurable up to 8 with `MONEY_AGENT_MAX_WORKERS`). These records are **not** independent AI models.
- A transparent opportunity completeness score. It is a triage aid only and never verifies a payer or guarantees revenue.
- A reversible-action allowlist with explicit local approval for pause/resume and retry of completed or failed local tasks.
- Read-only EVM testnet native-balance checks. No private key is generated or stored, no transaction is signed, and no funds are sent.

### Optional read-only testnet balance monitor

1. Set `MONEY_AGENT_TESTNET_RPC_URL` to an HTTPS RPC endpoint for the test network you choose.
2. Restart the local server.
3. Enter only the public EVM address in the dashboard's wallet monitor. If no RPC endpoint is configured, the endpoint reports that no request was made.

Never paste seed phrases or private keys into the app, task notes, or source code. The wallet monitor calls only `eth_getBalance`; it does not submit transactions.

### New API routes
- `GET /api/agents` — logical worker registry and pending action records.
- `GET /api/wallet/status?address=0x...` — read-only balance monitor; needs the optional HTTPS RPC setting.
- `POST /api/agents/spawn` — register a bounded logical worker slot.
- `POST /api/agents/retire` — retire an idle logical worker slot.
- `POST /api/opportunities/score` — score supplied opportunity metadata.
- `POST /api/actions/request` — request an allowlisted action; starts in `pending_approval`.
- `POST /api/actions/approve` — execute a pending allowlisted action after the operator approves it.

### Tests
Run from this folder with Python 3.9+:
```bash
python -m unittest -v test_agent_runtime.py
```

The local server binds to loopback only by default. The new features do not connect a paid-task marketplace or AI model and do not claim that any income has been earned.
