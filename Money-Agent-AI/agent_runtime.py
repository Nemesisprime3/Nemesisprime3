"""Bounded orchestration and read-only EVM testnet monitoring.

Standard-library only. This module never creates keys, signs transactions, or sends funds.
Logical worker records are scheduler slots, not independent LLMs.
"""
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

_LOCK = threading.RLock()
_STATE_PATH = os.path.join(os.path.dirname(__file__), "agent_runtime_state.json")
MAX_WORKERS = max(1, min(int(os.environ.get("MONEY_AGENT_MAX_WORKERS", "4")), 8))
ALLOWED_ACTIONS = {"pause_workers", "resume_workers", "retry_task"}
STATE = {"agents": [], "actions": [], "updated_at": None}

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _persist():
    STATE["updated_at"] = _now()
    try:
        tmp = _STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(STATE, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _STATE_PATH)
    except OSError:
        pass

def load_state():
    with _LOCK:
        if os.path.isfile(_STATE_PATH):
            try:
                with open(_STATE_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    STATE["agents"] = saved.get("agents", []) if isinstance(saved.get("agents", []), list) else []
                    STATE["actions"] = saved.get("actions", []) if isinstance(saved.get("actions", []), list) else []
                    STATE["updated_at"] = saved.get("updated_at")
            except (OSError, ValueError):
                pass

def snapshot():
    with _LOCK:
        return json.loads(json.dumps(STATE))

def spawn_agent(role, purpose):
    role = str(role or "general")[:40].strip() or "general"
    purpose = str(purpose or "")[:240].strip()
    if not purpose:
        raise ValueError("Purpose is required.")
    with _LOCK:
        active = [a for a in STATE["agents"] if a.get("status") in ("idle", "working")]
        if len(active) >= MAX_WORKERS:
            raise ValueError("Worker limit reached; retire an idle worker before adding another.")
        agent = {"id": uuid.uuid4().hex[:10], "role": role, "purpose": purpose,
                 "status": "idle", "created_at": _now(),
                 "note": "Logical worker slot only; no independent AI model is connected."}
        STATE["agents"].append(agent)
        STATE["agents"] = STATE["agents"][-50:]
        _persist()
        return dict(agent)

def request_action(action_type, payload):
    action_type = str(action_type or "")
    if action_type not in ALLOWED_ACTIONS:
        raise ValueError("Action is not on the reversible-action allowlist.")
    payload = payload if isinstance(payload, dict) else {}
    if action_type == "retry_task":
        task_id = str(payload.get("task_id", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", task_id):
            raise ValueError("A valid task_id is required.")
        payload = {"task_id": task_id}
    else:
        payload = {}
    with _LOCK:
        item = {"id": uuid.uuid4().hex[:10], "type": action_type, "payload": payload,
                "status": "pending_approval", "created_at": _now(), "result": ""}
        STATE["actions"].append(item)
        STATE["actions"] = STATE["actions"][-100:]
        _persist()
        return dict(item)

def get_action(action_id):
    with _LOCK:
        return next((a for a in STATE["actions"] if a.get("id") == action_id), None)

def finish_action(action_id, status, result):
    with _LOCK:
        item = get_action(action_id)
        if not item:
            raise ValueError("Action request not found.")
        item["status"] = status
        item["result"] = str(result)[:500]
        item["updated_at"] = _now()
        _persist()
        return dict(item)

def score_opportunity(item):
    """Transparent heuristic score; never treats a listing as proof of payment."""
    item = item if isinstance(item, dict) else {}
    score = 0
    evidence = []
    if item.get("source_url", "").startswith("https://"):
        score += 15; evidence.append("HTTPS source supplied")
    if item.get("reward_amount") not in (None, "", 0, "0"):
        score += 25; evidence.append("reward amount stated; not independently verified")
    if item.get("payment_terms"):
        score += 20; evidence.append("payment terms supplied")
    if item.get("eligibility"):
        score += 15; evidence.append("eligibility supplied")
    if item.get("deadline"):
        score += 10; evidence.append("deadline supplied")
    if item.get("acceptance_criteria"):
        score += 15; evidence.append("acceptance criteria supplied")
    return {"score": min(100, score), "evidence": evidence,
            "decision": "manual_review_required",
            "warning": "Heuristic only. Verify the source, terms, and payer before doing work."}

def wallet_status(address):
    """Read native balance using a configured EVM testnet JSON-RPC endpoint."""
    address = str(address or "").strip()
    if not re.fullmatch(r"0x[a-fA-F0-9]{40}", address):
        raise ValueError("Enter a valid 0x-prefixed EVM address.")
    rpc = os.environ.get("MONEY_AGENT_TESTNET_RPC_URL", "").strip()
    if not rpc:
        return {"configured": False, "network": "testnet",
                "message": "Set MONEY_AGENT_TESTNET_RPC_URL to an EVM testnet RPC endpoint. No network request was made.",
                "address": address, "balance_wei": None, "balance_native": None}
    if not rpc.startswith("https://"):
        raise ValueError("For safety, the testnet RPC endpoint must use HTTPS.")
    body = json.dumps({"jsonrpc": "2.0", "method": "eth_getBalance",
                       "params": [address, "latest"], "id": 1}).encode("utf-8")
    req = Request(rpc, data=body, headers={"Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "MoneyAgentAI-readonly/1.0"})
    try:
        with urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Testnet balance request failed: " + str(exc)[:180])
    if data.get("error"):
        raise RuntimeError("RPC error: " + str(data["error"])[:180])
    raw = data.get("result")
    if not isinstance(raw, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", raw):
        raise RuntimeError("RPC returned an unexpected balance response.")
    wei = int(raw, 16)
    return {"configured": True, "network": "configured EVM testnet",
            "address": address, "balance_wei": str(wei),
            "balance_native": format(wei / 10**18, ".8f"),
            "read_only": True, "transaction_sent": False, "checked_at": _now()}

load_state()
