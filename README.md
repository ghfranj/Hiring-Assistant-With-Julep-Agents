# Hiring Assistant (Julep)

This notebook builds a **multi-agent hiring assistant** using Julep platform. It:

1. creates a Julep **project**,
2. defines three **agents** (Extractor, Scorer/Ranker, Interviewer),
3. runs three **tasks** end-to-end: **extract → score/rank → interview questions**.

---

## Prerequisites

* Python 3.9+
* Packages:

  ```bash
  pip install -U julep pyyaml
  ```
* A valid Julep API key.

Create `config.yaml` at the repo root:

```yaml
julep:
  api_key: "YOUR_JULEP_API_KEY"
```
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


