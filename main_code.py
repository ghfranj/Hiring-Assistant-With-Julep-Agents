# recruitment_assistant_multi.py
import os, time, json
from julep import Julep

client = Julep(api_key=API_KEY)

# =========================
# 0) MULTI-AGENT SETUP
# =========================

# A) Extractor — focused on conservative evidence extraction
extractor = client.agents.create(
    name="ExtractorAgent",
    about="Extracts structured evidence from resumes: skills, experience, education, projects.",
    instructions="Be precise and conservative. Do not invent facts.",
    project="default",
)
print("ExtractorAgent:", extractor.id)

# B) Orchestrator — coordinates scoring/merging; stricter JSON

orchestrator = client.agents.create(
    name="OrchestratorAgent",
    about="Scores & ranks candidates, merges results to final JSON.",
    instructions="Return valid JSON. Be deterministic and auditable.",
    project="default",
    default_settings={
        "temperature": 0.2,
        "instructions": "Return valid JSON only; do not invent facts.",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "RecruitmentResult",
                "schema": {
                    "type": "object",
                    "properties": {
                        "ranked": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "score": {"type": "number"},
                                    "rationale": {"type": "string", "maxLength": 240}
                                },
                                "required": ["name", "score", "rationale"]
                            }
                        },
                        "top_n_questions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "questions": {
                                        "type": "array",
                                        "items": {"type": "string", "maxLength": 200},
                                        "maxItems": 5, "minItems": 1
                                    }
                                },
                                "required": ["name", "questions"]
                            }
                        },
                        "evidence": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "skills": {"type": "array", "items": {"type": "string"}},
                                    "experience": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "role": {"type": "string"},
                                                "years": {"type": "number"}
                                            },
                                            "required": ["role"]
                                        }
                                    },
                                    "education": {"type": "array", "items": {"type": "string"}},
                                    "projects": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["name"]
                            }
                        }
                    },
                    "required": ["ranked", "top_n_questions", "evidence"]
                }
            }
        }
    },
)


print("OrchestratorAgent:", orchestrator.id)

# C) Interviewer — crafts tailored questions
interviewer = client.agents.create(
    name="InterviewerAgent",
    about="Writes tailored interview questions that reference the candidate's background.",
    instructions="Ask concrete, specific, and technical questions tied to their evidence. No fluff.",
    project="default",
)
interviewer = client.agents.update(interviewer.id, default_settings={"temperature": 0.3})
print("InterviewerAgent:", interviewer.id)



# 1) FUNCTION TOOLS (LOCAL)

def normalize_term(s):
    mapping = {
        "postgres": "PostgreSQL",
        "postgresql": "PostgreSQL",
        "postgre": "PostgreSQL",
        "k8s": "Kubernetes",
        "js": "JavaScript",
        "ts": "TypeScript",
        "node": "Node.js",
    }
    key = (s or "").strip().lower()
    return mapping.get(key, s)

def compute_scores_locally(criteria, evidence_json, n):
    # evidence_json may be JSON string or dict
    if isinstance(evidence_json, str):
        try:
            evidence_obj = json.loads(evidence_json)
        except Exception:
            evidence_obj = {"evidence": []}
    else:
        evidence_obj = evidence_json or {"evidence": []}

    ev_list = evidence_obj.get("evidence", [])
    must = set(normalize_term(x) for x in criteria.get("must_haves", []))
    nice = set(normalize_term(x) for x in criteria.get("nice_to_haves", []))
    weights = criteria.get("weights", {"must_haves": 0.6, "nice_to_haves": 0.2, "experience": 0.2})

    ranked = []
    for item in ev_list:
        name = item.get("name") or "Unknown"
        skills = set(normalize_term(s) for s in item.get("skills", []))

        # simple experience tally
        exp_years = 0.0
        for e in item.get("experience", []):
            try:
                exp_years += float(e.get("years", 0))
            except Exception:
                pass

        # coverage
        must_cov = sum(1 for m in must if any(m.lower() == s.lower() for s in skills))
        must_need = max(1, len(must))
        must_score = must_cov / must_need

        nice_cov = sum(1 for h in nice if any(h.lower() == s.lower() for s in skills))
        nice_need = max(1, len(nice))
        nice_score = nice_cov / nice_need

        # cap at 8 years for normalization
        exp_score = min(exp_years, 8.0) / 8.0

        score = (
            weights.get("must_haves", 0.6) * must_score +
            weights.get("nice_to_haves", 0.2) * nice_score +
            weights.get("experience", 0.2) * exp_score
        )

        rationale_bits = []
        if len(must) > 0:
            rationale_bits.append(f"Must-haves: {must_cov}/{len(must)}")
        if len(nice) > 0:
            rationale_bits.append(f"Nice: {nice_cov}/{len(nice)}")
        rationale_bits.append(f"Exp: {exp_years:.0f}y")
        ranked.append({"name": name, "score": round(score, 4), "rationale": "; ".join(rationale_bits)})

    ranked.sort(key=lambda r: r["score"], reverse=True)
    top_n_names = [r["name"] for r in ranked[:max(1, int(n))]]
    return {"ranked": ranked, "top_n_names": top_n_names, "evidence": ev_list}

def dedupe_questions_locally(questions_json):
    # Input is a JSON str or dict with key "top_n_questions": [{name, questions: [...]},{"..."}]
    if isinstance(questions_json, str):
        try:
            qobj = json.loads(questions_json)
        except Exception:
            qobj = {}
    else:
        qobj = questions_json or {}

    items = qobj.get("top_n_questions", [])
    cleaned = []
    for item in items:
        name = item.get("name", "Unknown")
        qs = [q.strip() for q in item.get("questions", []) if isinstance(q, str)]
        # simple de-dup while preserving order
        seen = set()
        uniq = []
        for q in qs:
            key = q.lower()
            if key not in seen and q:
                uniq.append(q)
                seen.add(key)
        cleaned.append({"name": name, "questions": uniq[:5]})
    return {"top_n_questions": cleaned}

# ===================================
# 2) TASK A — EXTRACT EVIDENCE (LLM)
# ===================================
extract_task = {
    "name": "extract_evidence_task",
    "description": "Extract structured evidence from resumes",
    "input_schema": {
        "type": "object",
        "required": ["resumes"],
        "properties": {"resumes": {"type": "array"}}
    },
    "main": [
        {
            "prompt": [
                {
                    "role": "system",
                    "content": (
                        "Extract ONLY structured evidence from the resumes. "
                        "Do not score. Do not invent facts.\n\n"
                        "Return JSON with one key: evidence. "
                        "Each item includes:\n"
                        "- name: string\n"
                        "- skills: array of strings\n"
                        "- experience: array of objects with fields 'role' (string) and 'years' (number)\n"
                        "- education: array of strings\n"
                        "- projects: array of strings\n"
                        "Return JSON ONLY."
                    )
                },
                {"role": "user", "content": "$ f'''Resumes: {steps[0].input.resumes}'''"},
            ],
            "unwrap": True,
            "save_as": "evidence_json",
        },
        {"return": {"evidence_json": "$ steps[0].output"}},
    ],
}
extract_task_obj = client.tasks.create(agent_id=extractor.id, **extract_task)
print("Task A ready:", extract_task_obj.id, extract_task_obj.name)

# ==========================================================
# 3) TASK B — SCORE, QUESTIONS, DEDUPE, MERGE (LLM + TOOLS)
# ==========================================================
rank_task = {
    "name": "rank_and_questions_task",
    "description": "Score & rank via tool; draft questions; dedupe via tool; merge final JSON.",
    "tools": [
        {
            "name": "compute_scores",
            "type": "function",
            "function": {
                "description": "Compute scores and ranking using criteria and extracted evidence.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "criteria": {"type": "object"},
                        "evidence": {"type": "object"},
                        "n": {"type": "integer", "minimum": 1}
                    },
                    "required": ["criteria", "evidence", "n"],
                },
            },
        },
        {
            "name": "dedupe_questions",
            "type": "function",
            "function": {
                "description": "Deduplicate and trim interview questions per candidate to 5.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "questions": {"type": "object"}
                    },
                    "required": ["questions"],
                },
            },
        },
    ],
    "input_schema": {
        "type": "object",
        "required": ["criteria", "evidence_json", "n"],
        "properties": {
            "criteria": {"type": "object"},
            "evidence_json": {"type": "string"},  # string from Task A
            "n": {"type": "integer", "minimum": 1}
        }
    },
    "main": [
        # Step 0 — Call compute_scores (awaiting_input; resume from client)
        {
            "tool": "compute_scores",
            "arguments": {
                "criteria": "$ steps[0].input.criteria",
                "evidence": "$ steps[0].input.evidence_json",
                "n": "$ steps[0].input.n",
            },
            "save_as": "scored",
        },

        # Step 1 — Draft tailored questions (InterviewerAgent style via instructions in content)
        {
            "prompt": [
                {
                    "role": "system",
                    "content": (
                        "You are InterviewerAgent. Write tailored interview questions tied to each candidate's background. "
                        "Ask about specific technologies, projects, and experience they actually have. Be concrete. "
                        "Return JSON ONLY with key top_n_questions (an array of objects; each object has fields 'name' (string) and 'questions' (array of strings))."

                    )
                },
                {"role": "user", "content": "Evidence JSON:"},
                {"role": "user", "content": "$ f'''{steps[0].input.evidence_json}'''"},
                {"role": "user", "content": "Scoring result (ranked list & top_n_names):"},
                {"role": "user", "content": "$ f'''{steps[0].output}'''"},
            ],
            "unwrap": True,
            "save_as": "questions_json",
        },

        # Step 2 — Dedupe/clean questions via tool (awaiting_input; resume from client)
        {
            "tool": "dedupe_questions",
            "arguments": {
                "questions": "$ steps[1].output"
            },
            "save_as": "questions_clean",
        },

        # Step 3 — Merge into final object
        {
          "prompt": [
            {
              "role": "system",
              "content": (
                "You are InterviewerAgent. Write tailored interview questions tied to each candidate's background. "
                "Ask about specific technologies, projects, and experience they actually have. Be concrete. "
                "Return JSON ONLY with key top_n_questions (an array of objects; each object has fields 'name' (string) and 'questions' (array of strings))."
              )
            },
            {"role": "user", "content": "Evidence JSON:"},
            {"role": "user", "content": "$ f'''{steps[0].input.evidence_json}'''"},
            {"role": "user", "content": "Scoring result (ranked list & top_n_names):"},
            {"role": "user", "content": "$ f'''{steps[0].output}'''"},
          ],
          "unwrap": True,
          "save_as": "questions_json",
        },

        {"return": {"result_json": "$ steps[3].output"}},
    ],
}
rank_task_obj = client.tasks.create(agent_id=orchestrator.id, **rank_task)
print("Task B ready:", rank_task_obj.id, rank_task_obj.name)

# =========================
# 4) SAMPLE INPUTS
# =========================
criteria = {
    "role": "Senior Backend Engineer",
    "must_haves": ["Python", "Distributed systems", "PostgreSQL"],
    "nice_to_haves": ["Kubernetes", "AWS", "gRPC"],
    "weights": {"must_haves": 0.6, "nice_to_haves": 0.2, "experience": 0.2},
    "disqualifiers": [],
}
resumes = [
    {"name": "Alice Smith", "text": "Python, FastAPI, PostgreSQL, 5y backend, AWS, K8s, microservices..."},
    {"name": "Bob Lee", "text": "Java, Spring, MySQL, some Python, 3y backend, Kafka..."},
    {"name": "Carmen Diaz", "text": "Python, Django, Postgres, 7y backend, distributed systems, gRPC, AWS..."},
]
n = 2

# =========================
# 5) RUN — EXECUTE TASK A
# =========================
def exec_until_done(task_id, task_input, tool_handlers=None):
    exe = client.executions.create(task_id=task_id, input=task_input)
    print("Execution:", exe.id)
    while True:
        exe = client.executions.get(exe.id)
        print("Status:", exe.status)
        if exe.status == "awaiting_input":
            # we expect a function tool pause
            if not tool_handlers:
                raise RuntimeError("No tool_handlers provided for awaiting_input step.")
            # last saved outputs are in exe.output (dict of save_as keys if exposed)
            last_out = getattr(exe, "output", {}) or {}
            # Simple routing based on which step we just hit:
            if "scored" not in last_out and "questions_clean" not in last_out:
                # likely waiting on first tool in Task B: compute_scores
                handler = tool_handlers.get("compute_scores")
                payload = handler()
            elif "scored" in last_out and "questions_clean" not in last_out:
                # waiting on dedupe_questions step
                handler = tool_handlers.get("dedupe_questions")
                payload = handler()
            else:
                # fallback
                raise RuntimeError("Unexpected awaiting_input stage; cannot route tool handler.")
            client.executions.change_status(execution_id=exe.id, status="running", input=payload)
            print("Provided tool result and resumed.")
        elif exe.status in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(1)
    print("Final status:", exe.status)
    return exe

# Execute Task A (Extractor)
exe_a = exec_until_done(
    extract_task_obj.id,
    {"resumes": resumes},
)

# Collect evidence_json (string)
output_a = getattr(exe_a, "output", {}) or {}
evidence_json = output_a.get("evidence_json") or ""
# =========================
# 6) RUN — EXECUTE TASK B (robust)
# =========================
def safe_json_loads(maybe_str):
    if isinstance(maybe_str, str):
        try:
            return json.loads(maybe_str)
        except Exception:
            return None
    return maybe_str if isinstance(maybe_str, dict) else None

def print_failure(exe):
    print("Final status:", exe.status)
    print("Error:", getattr(exe, "error", None))
    print("Raw output:", getattr(exe, "output", None))

def tool_handler_compute_scores():
    return compute_scores_locally(criteria, evidence_json, n)

def tool_handler_dedupe_questions(current_exe_id):
    latest = client.executions.get(current_exe_id)
    latest_out = getattr(latest, "output", {}) or {}
    # "questions_json" might be a dict or a stringified JSON
    q_payload = latest_out.get("questions_json")
    q_obj = safe_json_loads(q_payload) or {"top_n_questions": []}
    return dedupe_questions_locally(q_obj)

# Start Task B
exe_b = client.executions.create(
    task_id=rank_task_obj.id,
    input={"criteria": criteria, "evidence_json": evidence_json, "n": n},
)
print("Execution (Task B):", exe_b.id)

while True:
    exe_b = client.executions.get(exe_b.id)
    print("Status B:", exe_b.status)

    if exe_b.status == "awaiting_input":
      outb = getattr(exe_b, "output", {}) or {}

      # If we already have questions_json but not questions_clean -> run dedupe
      if "questions_json" in outb and "questions_clean" not in outb:
          payload = tool_handler_dedupe_questions(exe_b.id)
          client.executions.change_status(execution_id=exe_b.id, status="running", input=payload)
          print("dedupe_questions -> resumed.")

      # If we don't even have 'scored' yet -> first pause is compute_scores
      elif "scored" not in outb:
          payload = tool_handler_compute_scores()
          client.executions.change_status(execution_id=exe_b.id, status="running", input=payload)
          print("compute_scores -> resumed.")

      else:
          # We have 'scored' but no 'questions_json' yet; that's a prompt step—just keep polling
          print("Waiting for questions_json to be produced...")

    elif exe_b.status in ("succeeded", "failed", "cancelled"):
        break

    time.sleep(1)

# =========================
# 7) RESULT (robust)
# =========================
if exe_b.status != "succeeded":
    print_failure(exe_b)
else:
    out_b = getattr(exe_b, "output", None)

    # Case A: output is a dict with result_json (string)
    if isinstance(out_b, dict) and "result_json" in out_b:
        result_json = out_b["result_json"]
        parsed = safe_json_loads(result_json)
        if parsed:
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        else:
            print("Raw result_json:", result_json)

    # Case B: output is already the final JSON string (no result_json wrapper)
    elif isinstance(out_b, str):
        parsed = safe_json_loads(out_b)
        if parsed:
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        else:
            print("Raw output string:", out_b)

    # Case C: output is a dict without result_json (rare), print it
    else:
        print("Raw output object:", out_b)


