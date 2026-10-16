#!/usr/bin/env python3
"""Money Agent AI local task workflow; standard library only."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path
from datetime import datetime, timezone
import json, threading, time, uuid, re, os
import agent_runtime as AR
ROOT=Path(__file__).resolve().parent
STATE_FILE=ROOT/"money_agent_state.json"
HOST,PORT="127.0.0.1",int(os.environ.get("MONEY_AGENT_PORT","8765"))
LOCK=threading.RLock()
STATE={"tasks":[],"events":[],"payouts":[],"paused":False,"day_target_usd":5.0,"created_at":datetime.now(timezone.utc).isoformat(),"last_heartbeat":None,"uptime_started":time.time()}
def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def persist():
    try:
        data={k:v for k,v in STATE.items() if k!="uptime_started"}; tmp=STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(STATE_FILE)
    except Exception as e: print("State save error:",e,flush=True)
def event(agent,message,kind="activity"):
    with LOCK:
        STATE["events"].insert(0,{"id":uuid.uuid4().hex[:10],"time":now(),"agent":agent,"message":str(message)[:1000],"kind":kind})
        STATE["events"]=STATE["events"][:400]; persist()
def load():
    if STATE_FILE.exists():
        try:
            d=json.loads(STATE_FILE.read_text(encoding="utf-8"))
            for k in ("tasks","events","payouts","paused","day_target_usd","last_heartbeat","created_at"):
                if k in d: STATE[k]=d[k]
        except Exception as e: print("State load error:",e,flush=True)
def new_task(kind,title,data,source="manual",source_url=""):
    return {"id":uuid.uuid4().hex[:12],"kind":kind,"title":title[:240],"data":data,"source":source,"source_url":source_url,"processing_status":"queued","work_status":"opportunity","created_at":now(),"updated_at":now(),"result":"","error":"","attempts":0}
def process(t):
    with LOCK: t["processing_status"]="running"; t["attempts"]+=1; t["updated_at"]=now(); persist()
    event("Worker","Started local processing: "+t["title"])
    d=t.get("data") or {}; k=t["kind"]
    try:
        if k=="listing":
            result=f"DRAFT — {d.get('property_type','Property')} in {d.get('location','unspecified location')}\n\n{d.get('features','')}\nAsking price: {d.get('price','not supplied')}\n\nVerify authority, claims, price, photos and availability before publishing."
        elif k=="lead":
            budget=float(d.get("budget") or 0); area=bool(str(d.get("area","")).strip()); tl=d.get("timeline","unspecified")
            score=min(100,25+(20 if budget>0 else 0)+(15 if area else 0)+(25 if tl=="within_30_days" else 15 if tl=="1_to_3_months" else 5 if tl=="3_plus_months" else 0)+(10 if d.get("requirements") else 0))
            result=f"Rule-based lead priority: {score}/100. Budget: {budget:,.2f} {d.get('currency','NGN')}. Area supplied: {area}. Timeline: {tl}. Sorting aid only; not a sales or income prediction."
        elif k=="deal":
            value=float(d.get("deal_value") or 0); rate=float(d.get("fee_rate") or 0); costs=float(d.get("costs") or 0); prob=float(d.get("probability") or 0)
            gross=value*rate/100; net=gross-costs
            result=f"SCENARIO ONLY — NOT ACTUAL EARNINGS\nFee if completed: {gross:,.2f} {d.get('currency','USD')}\nNet before tax: {net:,.2f}\nProbability-weighted scenario: {net*prob/100:,.2f}\nPayout ledger unchanged."
        elif k=="github_issue":
            result=f"PUBLIC ISSUE REVIEW\nRepo: {d.get('repo','?')} · Issue #{d.get('number','?')}\n{t['title']}\nLabels: {', '.join(d.get('labels',[])) or 'none'}\n\n{str(d.get('body',''))[:1500]}\n\nPublic issues are not inherently paid. Check reward, eligibility, contribution rules and acceptance criteria. Nothing was submitted and no income is claimed."
        elif k=="custom":
            result=f"TASK BRIEF ORGANIZED LOCALLY\n{t['title']}\n\n{str(d.get('details',''))[:5000]}\n\nNo external AI model or paid-task platform is connected."
        else: raise ValueError("Unsupported task type")
        with LOCK: t["result"]=result; t["processing_status"]="completed"; t["updated_at"]=now(); t["error"]=""; persist()
        event("Worker",f"Completed local processing for {t['id']}; no external submission or income claimed.","success")
    except Exception as e:
        with LOCK: t["processing_status"]="failed"; t["error"]=str(e); t["updated_at"]=now(); persist()
        event("Recovery",f"Task {t['id']} failed: {e}; saved for retry.","error")
def worker():
    last=0
    while True:
        time.sleep(1); cur=time.time()
        with LOCK:
            STATE["last_heartbeat"]=now()
            task=next((t for t in STATE["tasks"] if t["processing_status"]=="queued"),None) if not STATE["paused"] else None
        if task: process(task)
        if cur-last>=5:
            event("Heartbeat",f"Backend alive; waiting={sum(t['processing_status']=='queued' for t in STATE['tasks'])}; completed={sum(t['processing_status']=='completed' for t in STATE['tasks'])}.","heartbeat"); last=cur
def github_issues(repo,limit):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}",repo): raise ValueError("Repository must be owner/repo.")
    limit=max(1,min(int(limit),30)); url=f"https://api.github.com/repos/{repo}/issues?state=open&per_page={limit}&sort=updated&direction=desc"
    req=Request(url,headers={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"MoneyAgentAI/1.0"})
    try:
        with urlopen(req,timeout=15) as r: raw=json.loads(r.read().decode()); status=r.status
    except HTTPError as e: raise RuntimeError(f"GitHub HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")
    except URLError as e: raise RuntimeError(f"Network request failed: {e.reason}")
    out=[{"number":x.get("number"),"title":x.get("title","(untitled)"),"body":x.get("body") or "","html_url":x.get("html_url",""),"updated_at":x.get("updated_at",""),"labels":[a.get("name","") for a in x.get("labels",[])],"repo":repo} for x in raw if isinstance(raw,list) and not x.get("pull_request")]
    event("GitHub API",f"Live request succeeded for {repo}: {len(out)} issues; HTTP {status}; no reward inferred.","success"); return out
class Handler(BaseHTTPRequestHandler):
    server_version="MoneyAgentAI/1.0"
    def log_message(self,fmt,*args): print("%s - %s"%(self.address_string(),fmt%args),flush=True)
    def send_json(self,obj,status=200):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(b)
    def body(self):
        n=min(int(self.headers.get("Content-Length","0")),1000000); return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
    def do_GET(self):
        u=urlparse(self.path)
        if u.path in ("/","/index.html"):
            b=(ROOT/"index.html").read_bytes(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
        if u.path=="/api/health": self.send_json({"ok":True,"server_time":now(),"python":os.sys.version.split()[0]}); return
        if u.path=="/api/state":
            with LOCK:
                out={k:v for k,v in STATE.items() if k!="uptime_started"}; out["uptime_seconds"]=int(time.time()-STATE["uptime_started"]); out["server_time"]=now()
            self.send_json(out); return
        if u.path=="/api/github/issues":
            q=parse_qs(u.query)
            try: self.send_json({"ok":True,"issues":github_issues((q.get("repo") or [""])[0],(q.get("limit") or ["20"])[0])})
            except Exception as e: event("GitHub API",str(e),"error"); self.send_json({"ok":False,"error":str(e)},400)
            return
        if u.path=="/api/agents":
            self.send_json({"ok":True,**AR.snapshot(),"max_workers":AR.MAX_WORKERS}); return
        if u.path=="/api/wallet/status":
            q=parse_qs(u.query)
            try: self.send_json({"ok":True,"wallet":AR.wallet_status((q.get("address") or [""])[0])})
            except Exception as e: self.send_json({"ok":False,"error":str(e)},400)
            return
        self.send_json({"error":"Not found"},404)
    def do_POST(self):
        u=urlparse(self.path)
        try: d=self.body()
        except Exception: self.send_json({"error":"Invalid JSON"},400); return
        if u.path=="/api/agents/spawn":
            try:
                agent=AR.spawn_agent(d.get("role","general"),d.get("purpose",""))
                event("Orchestrator","Registered bounded logical worker "+agent["id"]+"; no separate AI model started.")
                self.send_json({"ok":True,"agent":agent})
            except Exception as e: self.send_json({"ok":False,"error":str(e)},400)
            return
        if u.path=="/api/opportunities/score":
            try: self.send_json({"ok":True,"assessment":AR.score_opportunity(d)})
            except Exception as e: self.send_json({"ok":False,"error":str(e)},400)
            return
        if u.path=="/api/actions/request":
            try:
                action=AR.request_action(d.get("type"),d.get("payload") or {})
                event("Permissions","Action "+action["type"]+" requires explicit approval.")
                self.send_json({"ok":True,"action":action})
            except Exception as e: self.send_json({"ok":False,"error":str(e)},400)
            return
        if u.path=="/api/actions/approve":
            action_id=str(d.get("action_id","")).strip()
            action=AR.get_action(action_id)
            if not action: self.send_json({"ok":False,"error":"Action request not found"},404); return
            if action.get("status")!="pending_approval":
                self.send_json({"ok":False,"error":"Only pending actions can be approved"},400); return
            AR.finish_action(action_id,"approved","Approved by local operator.")
            try:
                kind=action["type"]; payload=action.get("payload") or {}
                if kind=="pause_workers":
                    with LOCK: STATE["paused"]=True; persist()
                    result="Workers paused."
                elif kind=="resume_workers":
                    with LOCK: STATE["paused"]=False; persist()
                    result="Workers resumed."
                elif kind=="retry_task":
                    with LOCK:
                        task=next((x for x in STATE["tasks"] if x["id"]==payload.get("task_id")),None)
                        if not task: raise ValueError("Task not found.")
                        if task["processing_status"] not in {"failed","completed"}: raise ValueError("Only completed or failed local tasks can be retried.")
                        task["processing_status"]="queued"; task["result"]=""; task["error"]=""; task["updated_at"]=now(); persist()
                    result="Task requeued for local processing."
                else:
                    raise ValueError("Action is not permitted.")
                final=AR.finish_action(action_id,"executed",result)
                event("Permissions","Approved action executed: "+kind,"success")
                self.send_json({"ok":True,"action":final})
            except Exception as e:
                final=AR.finish_action(action_id,"failed",str(e))
                event("Permissions","Approved action failed: "+str(e),"error")
                self.send_json({"ok":False,"error":str(e),"action":final},400)
            return
        if u.path=="/api/tasks":
            kind=str(d.get("kind","custom"))
            if kind not in {"listing","lead","deal","custom","github_issue"}: self.send_json({"error":"Unsupported task type"},400); return
            title=str(d.get("title","")).strip() or "General task"
            with LOCK:
                srcurl=str(d.get("source_url",""))
                if kind=="github_issue" and srcurl and any(t.get("source_url")==srcurl for t in STATE["tasks"]): self.send_json({"ok":True,"duplicate":True}); return
                t=new_task(kind,title,d.get("data") or {},str(d.get("source","manual")),srcurl); STATE["tasks"].insert(0,t); persist()
            event("Intake",f"Queued {kind} task {t['id']} from {t['source']}.","success"); self.send_json({"ok":True,"task":t}); return
        if u.path=="/api/control":
            with LOCK: STATE["paused"]=bool(d.get("paused",False)); persist()
            event("System","Workers "+("paused" if STATE["paused"] else "resumed")); self.send_json({"ok":True,"paused":STATE["paused"]}); return
        if u.path=="/api/target":
            try: val=float(d.get("target") or 5)
            except: val=-1
            if not 0<=val<=100000: self.send_json({"error":"Target must be 0 to 100000"},400); return
            with LOCK: STATE["day_target_usd"]=val; persist()
            event("System","Daily target set to $"+format(val,".2f")+"; goal is not earnings."); self.send_json({"ok":True,"target":val}); return
        if u.path=="/api/task-status":
            tid=str(d.get("id","")); status=str(d.get("work_status",""))
            if status not in {"opportunity","selected","in_progress","submitted_by_user","accepted","paid","rejected","not_suitable"}: self.send_json({"error":"Invalid status"},400); return
            with LOCK:
                t=next((x for x in STATE["tasks"] if x["id"]==tid),None)
                if not t: self.send_json({"error":"Task not found"},404); return
                t["work_status"]=status; t["updated_at"]=now(); persist()
            event("Work Tracker",f"Task {tid} status changed to {status}; external platform not changed."); self.send_json({"ok":True,"task":t}); return
        if u.path=="/api/retry":
            with LOCK:
                t=next((x for x in STATE["tasks"] if x["id"]==str(d.get("id",""))),None)
                if not t: self.send_json({"error":"Task not found"},404); return
                if t["processing_status"] not in {"failed","completed"}: self.send_json({"error":"Only completed/failed local tasks can retry"},400); return
                t["processing_status"]="queued"; t["result"]=""; t["error"]=""; t["updated_at"]=now(); persist()
            event("Recovery",f"Task {t['id']} requeued."); self.send_json({"ok":True}); return
        if u.path=="/api/payouts":
            try: amount=float(d.get("amount") or 0)
            except: amount=0
            evidence=str(d.get("evidence","")).strip(); currency=str(d.get("currency","USD"))
            if amount<=0 or not evidence: self.send_json({"error":"Positive amount and receipt/reference required"},400); return
            p={"id":uuid.uuid4().hex[:10],"amount":amount,"currency":currency,"evidence":evidence,"time":now(),"verification":"user_recorded_not_independently_verified"}
            with LOCK: STATE["payouts"].append(p); persist()
            event("Ledger",f"User-recorded {amount:.2f} {currency}; not independently verified.","warning"); self.send_json({"ok":True,"payout":p}); return
        self.send_json({"error":"Not found"},404)
if __name__=="__main__":
    load(); event("System","Backend started. Local worker active; GitHub public issues connector available. No paid platform connected.")
    threading.Thread(target=worker,daemon=True,name="money-agent-worker").start()
    print(f"Money Agent AI running at http://{HOST}:{PORT}\nLocal service only; keep this process running.",flush=True)
    try: ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
    except KeyboardInterrupt: print("\nStopping Money Agent AI...",flush=True)
