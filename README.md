# Recruitment Assistant (Julep Multi-Agent Demo)

Main_code.py demonstrates how to build a **multi-agent recruitment assistant** using the [Julep Python SDK](https://docs.julep.ai).
The workflow extracts evidence from resumes, scores and ranks candidates, and generates tailored interview questions.

## Features

* **ExtractorAgent**: Parses resumes into structured evidence (skills, experience, education, projects).
* **OrchestratorAgent**: Scores and ranks candidates, merges results into a strict JSON schema.
* **InterviewerAgent**: Crafts technical, candidate-specific interview questions.
* **Local Tools**:

  * `compute_scores_locally` – ranks candidates by must-have, nice-to-have, and experience weights.
  * `dedupe_questions_locally` – removes duplicate/overlong questions.

## Workflow

1. **Task A** – Extract structured evidence from resumes.
2. **Task B** – Score candidates, draft interview questions, deduplicate them, and merge into final results.
3. **Execution Loop** – Polls Julep executions, handles `awaiting_input` pauses by invoking local tools.
4. **Result** – Outputs valid JSON matching the schema:

   ```json
   {
     "ranked": [...],
     "top_n_questions": [...],
     "evidence": [...]
   }
   ```

## Sample Input

```python
criteria = {
    "role": "Senior Backend Engineer",
    "must_haves": ["Python", "Distributed systems", "PostgreSQL"],
    "nice_to_haves": ["Kubernetes", "AWS", "gRPC"],
    "weights": {"must_haves": 0.6, "nice_to_haves": 0.2, "experience": 0.2},
}
resumes = [
    {"name": "Alice Smith", "text": "Python, FastAPI, PostgreSQL, 5y backend, AWS, K8s..."},
    {"name": "Bob Lee", "text": "Java, Spring, MySQL, some Python, 3y backend..."},
]
```

## Requirements

* `pip install julep`

## Run

```bash
python main_code.py
```

The script prints execution status and the final JSON result.

---

# Solution witht the notebook 

This notebook builds a **multi-agent hiring assistant** using Julep platform. It:

1. creates a Julep **project**,
2. defines three **agents** (Extractor, Scorer/Ranker, Interviewer),
3. runs three **tasks** end-to-end: **extract → score/rank → interview questions**.

---

## What’s in the Notebook

### 0) Project setup

* Uses `Client(api_key=..., environment="production")` to create a **project** named “Hiring Assistant”.
* Prints basic project metadata.
* Variable `project_name` (e.g., `hiringAssistant__`) is used as the `project` for agents later.

### 1) Agents (temperature=0 for determinism)

* **ExtractorAgent1**: Produces structured profiles **verbatim** from resume text.

  * JSON schema enforced via `response_format`.
* **ScorerRankerAgent1**: Scores candidates against `criteria`, returns `ranked` + `top_n_ids` with an **explainable breakdown**.
* **InterviewerAgent1**: Generates **6–10 tailored interview questions** per top candidate, each with a short “why\_this\_question”.

### 2) Inputs

* `criteria`: role, must\_haves, nice\_to\_haves, weights, disqualifiers.
* `resumes`: list of objects with `candidate_id`, `name`, and `text`.
* `N`: how many top candidates to select after scoring.

### 3) Tasks & Execution Flow

**Task A — Extract Evidence**

* Sends all resumes and gets back `extracted_profiles` (array).
* Prints the extracted profiles.

**Task B — Score & Rank**

* Inputs: `criteria`, `extracted_profiles`, `N`.
* Output: `ranked` array (with `score_total` + `breakdown`) and `top_n_ids`.
* Prints the full ranking and the top-N IDs.

**Task C — Interview Questions**

* Inputs: `criteria`, and the **top profiles** (profiles whose IDs are in `top_n_ids`).
* Output: `interview_questions` array (per candidate, 6–10 questions with rationales).
* Prints the questions.

A small utility, `run_and_wait(task_id, input)`, polls until the execution finishes.

---

## How to Run (TL;DR)

1. **Install & configure**
  
   ```bash
   pip install -U julep pyyaml
   # create config.yaml with your key (see above)
   ```
2. **Open the notebook** and run cells in order:

   * Project creation
   * Agent definitions
   * Define `criteria`, `resumes`, `N`
   * Task A (extract)
   * Task B (score & rank)
   * Task C (interview questions)
3. **Review outputs**

   * `Extracted profiles:` JSON array
   * `Ranked:` scored candidates + `Top-N IDs`
   * `Interview questions:` per top candidate


