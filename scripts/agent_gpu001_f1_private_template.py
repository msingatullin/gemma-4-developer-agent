#!/usr/bin/env python3
"""F1 real E4B 3-arm tool-mediated pilot. Custom safe bridge, NOT official ADK."""
import base64, datetime, hashlib, importlib.metadata, json, os, pathlib, re, shlex, signal, subprocess, sys, time
DATA=json.loads(base64.b64decode("__INPUT_B64__"))
OUT=pathlib.Path("/kaggle/working/GPU001_F1.json")
TIMER=pathlib.Path("/kaggle/working/GPU001_F1.timer")
ROOT=pathlib.Path("/kaggle/working/GPU001_F1_sources")
PIN="6995257cf470d2143ad1683824962de4071c0eb7"
TREE="5e87fec76a0ead331441eaf05a1510c6c6efe6cf"
MODEL="gemma-4-e4b-it-qat-w4a16-ct"
CAP=1950
ARM_MAX=340
MAX_TOOLS=10
def sha(b):return hashlib.sha256(b).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def run(cmd,cwd=None,timeout=80):return subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=timeout)
def save(obj):
 p=OUT.with_suffix(".tmp");p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n");os.replace(p,OUT)
def free(t0):return CAP-(time.time()-t0)
def source():
 ROOT.mkdir()
 repo=ROOT/"original";repo.mkdir()
 for args in [["git","init","-q"],["git","remote","add","origin","https://github.com/pytest-dev/pytest.git"],
 ["git","fetch","-q","--depth","1","origin",PIN],["git","checkout","-q","--detach","FETCH_HEAD"]]:
  p=run(args,repo,100)
  if p.returncode:raise RuntimeError("PUBLIC_PIN_FETCH_ERROR "+p.stderr[:450])
 tree=run(["git","rev-parse","HEAD^{tree}"],repo).stdout.strip()
 pin=run(["git","rev-parse","HEAD"],repo).stdout.strip()
 if tree!=TREE or pin!=PIN:raise RuntimeError("WRONG_PIN_TREE")
 return repo
def gpu():
 import torch
 cards=[torch.cuda.get_device_properties(i).name for i in range(torch.cuda.device_count())]
 if len(cards)!=2 or any("T4" not in s for s in cards):raise RuntimeError("REQUIRE_FREE_TWO_T4")
 return cards
def weights():
 c=[p.parent for p in pathlib.Path("/kaggle/input").rglob("config.json")
 if MODEL in str(p.parent).lower() and list(p.parent.glob("*.safetensors"))]
 if len(c)!=1:raise RuntimeError("OFFICIAL_MODEL_MOUNT_MISSING_OR_DUPLICATE")
 return c[0]
def bootstrap(t0):
 from packaging.version import Version
 try:v=importlib.metadata.version("vllm")
 except importlib.metadata.PackageNotFoundError:v=None
 if v is not None and Version(v)>=Version("0.29.0"):return
 if free(t0)<820:raise TimeoutError("NO_BOOTSTRAP_BUDGET")
 subprocess.run([sys.executable,"-m","pip","install","-q","--disable-pip-version-check","--no-input","vllm>=0.29.0,<0.31.0"],check=True,timeout=460)
 os.execv(sys.executable,[sys.executable,str(pathlib.Path(__file__).resolve()),"--after-bootstrap"])
def t4fix():
 import sysconfig
 p=pathlib.Path(sysconfig.get_path("purelib"))/"vllm/v1/attention/ops/triton_unified_attention.py"
 if not p.is_file():return "MISSING"
 t=p.read_text()
 old="    # Default behavior\n    if is_prefill:\n        return 32\n"
 line="    launch_kwargs: dict[str, int] = {}\n"
 if t.count(old)!=1 or t.count(line)!=1:return "NOT_APPLICABLE"
 t=t.replace(old,"    # Default behavior\n    if is_prefill:\n        return 16  # T4\n",1)
 t=t.replace(line,'    launch_kwargs: dict[str, int] = {"num_stages": 1}\n',1)
 compile(t,str(p),"exec");p.write_text(t);return "APPLIED"
def secure_path(repo,raw,write=False):
 if not isinstance(raw,str) or not raw:raise ValueError("INVALID_PATH")
 if raw.startswith("/workspace/"):raw=raw[len("/workspace/"):]
 p=(repo/raw).resolve()
 if not p.is_relative_to(repo.resolve()):raise ValueError("PATH_TRAVERSAL")
 r=p.relative_to(repo.resolve()).as_posix()
 if write and (not r.endswith(".py") or r.startswith(("testing/","tests/","docs/")) or
 p.name.startswith("test_") or p.name.endswith("_test.py")):raise ValueError("PROTECTED_FILE")
 return p,r
def valid_command(cmd):
 if not isinstance(cmd,str) or not cmd or len(cmd)>1400:raise ValueError("BAD_SHELL")
 if any(q in cmd for q in [";","&&","||","$(", "\n","\r",">","<","sudo","curl","wget","pip ","ssh ","/kaggle/","/root/"]):
  raise ValueError("UNSAFE_SHELL")
 lex=shlex.shlex(cmd,posix=True,punctuation_chars="|;&<>");lex.whitespace_split=True
 parts=[];part=[]
 for x in list(lex):
  if x=="|":
   if not part:raise ValueError("EMPTY_PIPE")
   parts.append(part);part=[]
  elif x in (";","&",">","<"):raise ValueError("SHELL_WRITE")
  else:part.append(x)
 if part:parts.append(part)
 for x in parts:
  if not x or x[0] not in ("git","grep","head","tail","sed","ls","pwd","cat","wc","find"):
   raise ValueError("UNSUPPORTED_COMMAND")
  if x[0]=="git" and (len(x)<2 or x[1] not in ("grep","ls-files","status","diff","rev-parse")):
   raise ValueError("GIT_WRITE_FORBIDDEN")
  if x[0]=="find" and any(a in x for a in ("-exec","-delete")):raise ValueError("FIND_WRITE")
 return cmd
def tool(repo,obj,count,start):
 tool=obj.get("tool");a=obj.get("args") or {}
 if not isinstance(a,dict):raise ValueError("ARGS_NOT_OBJECT")
 if tool=="run_command":
  cmd=valid_command(a.get("command",""))
  p=run(["bash","-c",cmd],repo,15)
  return {"status":"ok" if p.returncode==0 else "error","exit_code":p.returncode,
          "stdout":p.stdout[-6500:],"stderr":p.stderr[-1000:]},False
 if tool=="read_file":
  p,rel=secure_path(repo,a.get("filepath",a.get("path","")))
  if not p.is_file():return {"status":"error","message":"NO_FILE"},False
  lo=int(a.get("start_line",1));hi=int(a.get("end_line",lo+80))
  if lo<1 or hi<lo or hi-lo>119:raise ValueError("MAX_120_LINES")
  lines=p.read_text(errors="replace").splitlines()
  return {"status":"ok","file":rel,"content":"\n".join(str(i+1)+": "+lines[i] for i in range(lo-1,min(hi,len(lines))))[:8000]},False
 if tool=="edit_file":
  p,rel=secure_path(repo,a.get("filepath",""),True)
  old=a.get("old_string");new=a.get("new_string")
  if not p.is_file() or not isinstance(old,str) or not old or not isinstance(new,str) or old==new:raise ValueError("BAD_EDIT")
  s=p.read_text()
  if s.count(old)!=1:raise ValueError("OLD_STRING_MUST_MATCH_ONCE")
  p.write_text(s.replace(old,new,1))
  return {"status":"ok","edited":rel},False
 if tool=="write_file":
  p,rel=secure_path(repo,a.get("filepath",""),True)
  content=a.get("content")
  if p.exists() or not isinstance(content,str) or len(content)>18000:raise ValueError("BAD_NEW_FILE")
  p.parent.mkdir(exist_ok=True,parents=True);p.write_text(content)
  return {"status":"ok","created":rel},False
 if tool=="get_status":return {"status":"ok","calls_left":MAX_TOOLS-count,"seconds_left":round(ARM_MAX-(time.monotonic()-start),1)},False
 if tool=="submit_patch":return {"status":"ok","patch_stored":True},True
 raise ValueError("UNKNOWN_TOOL")
def parse(s):
 s=s.strip()
 # Extract first JSON action object; no executable model output is accepted.
 options=[s]
 if "{" in s and "}" in s:options.append(s[s.find("{"):s.rfind("}")+1])
 for q in options:
  try:
   x=json.loads(q)
   if isinstance(x,dict) and isinstance(x.get("tool"),str):return x
  except Exception:pass
 return None
TRANSPORT='''Tool transport: each answer must be ONLY JSON of the form
{"tool":"run_command","args":{"command":"git grep -n ..."}}
or {"tool":"read_file","args":{"filepath":"...","start_line":1,"end_line":80}}
or {"tool":"edit_file","args":{"filepath":"...","old_string":"EXACT","new_string":"NEW"}}
or {"tool":"get_status","args":{}} or {"tool":"submit_patch","args":{}}.
No markdown or narration. At most ten calls. Make one source edit and submit_patch.
'''
def arm(llm,SamplingParams,src,name,t0):
 repo=ROOT/name
 cp=run(["cp","-a",str(src),str(repo)],timeout=60)
 if cp.returncode:raise RuntimeError("SOURCE_COPY_FAILED")
 prompt=DATA["prompts"][name]
 if sha(prompt.encode())!=DATA["prompt_sha"][name]:raise RuntimeError("PROMPT_SHA_MISMATCH")
 messages=[{"role":"system","content":prompt+"\n"+TRANSPORT},
           {"role":"user","content":DATA["issue"]+"\n\nRepository in /workspace; use tools to fix the source."}]
 start=time.monotonic()
 row={"arm":name,"start":utc(),"prompt_sha256":DATA["prompt_sha"][name],"events":[],"status":"STARTED"}
 for i in range(MAX_TOOLS):
  if free(t0)<150 or time.monotonic()-start>ARM_MAX:
   row["status"]="TIMEOUT";break
  ts=time.monotonic()
  outputs=llm.chat(messages,SamplingParams(temperature=0.2,top_p=0.95,top_k=64,max_tokens=500),use_tqdm=False)
  text=outputs[0].outputs[0].text
  evt={"step":i+1,"model_text":text[:3600],"tokens":len(outputs[0].outputs[0].token_ids),
       "model_seconds":round(time.monotonic()-ts,2)}
  action=parse(text);evt["action"]=action
  if action is None:
   evt["tool_result"]={"status":"error","message":"not JSON tool call"}
   row["events"].append(evt);row["status"]="UNPARSEABLE";break
  try:res,done=tool(repo,action,i+1,start)
  except Exception as e:res={"status":"error","message":str(e)[:350]};done=False
  evt["tool_result"]=res;row["events"].append(evt)
  messages.append({"role":"assistant","content":text})
  messages.append({"role":"user","content":"TOOL_RESULT "+json.dumps(res,ensure_ascii=False)[:9000]+"\nNext JSON tool call."})
  if done:row["status"]="SUBMITTED";break
 if row["status"]=="STARTED":row["status"]="CALL_LIMIT"
 q=run(["git","diff","--binary","HEAD"],repo,20)
 if q.returncode:raise RuntimeError("DIFF_FAILED")
 patch=pathlib.Path("/kaggle/working")/("GPU001_F1_"+name+".diff")
 if patch.exists():raise FileExistsError("EXISTING_PATCH")
 patch.write_text(q.stdout)
 row.update({"end":utc(),"duration_seconds":round(time.monotonic()-start,2),
             "patch_sha256":sha(q.stdout.encode()),"patch_bytes":len(q.stdout.encode()),
             "model_generated_patch":bool(q.stdout.strip()),"patch_file":patch.name,
             "model_calls":len(row["events"]),"git_status":run(["git","status","--short"],repo).stdout[:800]})
 print("ARM",name,row["status"],row["patch_bytes"],flush=True)
 return row
def main():
 if TIMER.exists():t0=float(TIMER.read_text())
 else:t0=time.time();TIMER.write_text(str(t0))
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError("F1 hard wall cap")))
 signal.alarm(max(1,int(free(t0))))
 report={"id":"EXP-AGENT-GPU-001-F1","status":"STARTED","model":"true local Gemma E4B",
         "harness":"custom safe JSON tool bridge, NOT official ADK","model_gold_access":False,
         "kaggle_submission":False,"paid_api":False,"is_private":True,"start":utc(),"arms":[]}
 try:
  if OUT.exists():raise FileExistsError("PREVIOUS_RUN_RESULT")
  report["gpus"]=gpu()
  model=weights()
  report["model_config_sha256"]=sha((model/"config.json").read_bytes())
  if free(t0)<850:raise RuntimeError("NO_GPU_BUDGET")
  if "--after-bootstrap" not in sys.argv:bootstrap(t0)
  from vllm import LLM,SamplingParams
  import vllm
  report["vllm_version"]=vllm.__version__
  report["ephemeral_T4_fix"]=t4fix()
  s=source()
  check=run(["git","rev-parse","HEAD^{tree}"],s)
  report["verified_historical_tree"]=check.stdout.strip()
  tick=time.monotonic()
  llm=LLM(model=str(model),tokenizer=str(model),tensor_parallel_size=2,
          dtype="float16",max_model_len=8192,max_num_seqs=1,
          gpu_memory_utilization=0.88,enforce_eager=True,trust_remote_code=False,disable_log_stats=True)
  report["model_load_seconds"]=round(time.monotonic()-tick,2)
  for n in ("v15","exp002_quote_only","exp001a_search_rewrite"):
   if free(t0)<ARM_MAX+95:report["cutoff_before"]=n;break
   report["arms"].append(arm(llm,SamplingParams,s,n,t0));save(report)
  report["status"]="THREE_ARMS_COMPLETED" if len(report["arms"])==3 else "PARTIAL_NOT_PAIRED"
 except Exception as e:
  report["status"]="BLOCKED_OR_PARTIAL";report["error"]=type(e).__name__+" "+str(e)[:1000]
  print("F1_ERROR",report["error"],flush=True)
 finally:
  report["end"]=utc();report["wall_seconds"]=round(time.time()-t0,2);save(report)
  print("F1_FINAL",report["status"],sha(OUT.read_bytes()),flush=True)
if __name__=="__main__":main()
