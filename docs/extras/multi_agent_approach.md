# Multi-Agent Approach for Computer-Vision Projects

**Status:** Approach v0.1 (doc-only — implementation in a future repo)
**Audience:** Anyone shipping or auditing a CV project that follows the
canonical template at `standardize-cv-template/`.
**Last updated:** 2026-05-01

---

## 1. Purpose (TL;DR)

Every CV project we ship has the same shape: docs → ingestion →
preprocessing + CV → decision logic + integration → output → tests.
What changes is the algorithm, not the layout.

Build a small team of **reusable agents**, each one owning a phase of
that shape. One orchestrator coordinates them. The shared context is
the file system itself — every agent owns a specific folder in the
canonical template.

Same 7 agents work on every CV project. Reusability is structural, not
prompt-engineered.

---

## 2. The Pattern

Borrowed from the standard multi-agent design pattern:

```
                              ┌──────────────────┐
        User / problem ─────▶ │   Orchestrator   │  routes work, keeps layout canonical
                              └────────┬─────────┘
                                       │
   ┌───────────┬───────────┬───────────┼───────────┬───────────┐
   ▼           ▼           ▼           ▼           ▼           ▼
┌──────┐  ┌────────┐  ┌─────────┐  ┌────────┐  ┌─────────┐  ┌────┐
│ Docs │  │Ingest- │  │ Vision  │  │  Core  │  │ Output  │  │ QA │
│      │  │ ion    │  │Pipeline │  │ Algo-  │  │ Handler │  │    │
│      │  │        │  │         │  │ rithm  │  │         │  │    │
└──────┘  └────────┘  └─────────┘  └────────┘  └─────────┘  └────┘
   │          │           │            │            │          │
   ▼          ▼           ▼            ▼            ▼          ▼
docs/    src/.../    src/.../     src/.../     frontend/   tests/
         ingestion/  processing/  logic/                   edge_cases/
         data/       configs/     api/                     reports/
                     algo_params/ persistence/
                                  workers/
```

Three rules:
- **One orchestrator, many specialists.** No agent tries to do
  everything.
- **Single responsibility, single folder.** Each specialist owns one
  folder; that folder is its inputs and outputs.
- **The file system is the blackboard.** No separate state store. The
  next agent reads what the previous agent committed.

---

## 3. The Roster (7 agents)

| # | Agent | Owns (canonical folder) | Single responsibility |
|---|-------|-------------------------|----------------------|
| 1 | **Orchestrator** | repo-wide | Routes work, ensures docs↔code stay consistent, refuses any artifact that lands outside the canonical layout |
| 2 | **Docs Agent** | `docs/` | Translates problem statement into BRD → PRD → TRD → ALGO_CARD → RUNBOOK; keeps them cross-consistent; opens ADRs when decisions are made |
| 3 | **Data Ingestion Agent** | `src/<pkg>/ingestion/`, `data/`, `tests/fixtures/` | File / stream readers, filename parsers, image validators (dim, blur, exposure, truncation), fixture curation, edge-case sample collection |
| 4 | **Vision Pipeline Agent** | `src/<pkg>/processing/`, `configs/algo_params/` | Preprocessing (blur, threshold, normalization) + the core CV algorithm (detection / measurement / classification — classical or ML). Tunes parameters. Versions each algo as `algo-X.Y.Z.yaml` |
| 5 | **Core Algorithm Agent** | `src/<pkg>/{logic, api, persistence, workers}/` | The decision brain. Takes vision outputs → applies business rules → persists → exposes via FastAPI + workers/SSE. The "connect-the-dots" layer between vision and the world |
| 6 | **Output Handler Agent** | `frontend/` (and any export sink: file, queue, email, MQTT) | Surfaces results to humans or downstream systems. Web dashboards, operator decision flows, real-time updates, exports |
| 7 | **QA Agent** | `tests/`, `edge_cases/`, `reports/` | Unit + integration + benchmark tests; edge-case catalog; runs `make bench`; produces uniform reports under `reports/benchmark/` |

Note on naming: **Core Algorithm** is the *decision* algorithm, not the
CV algorithm. The CV algorithm lives in **Vision Pipeline**. Core
Algorithm is what turns "I detected X" into "therefore do Y, persist Z,
notify W".

---

## 4. Handoff Contracts

Agents talk by reading each other's committed code. The contracts below
are the only thing that has to be standard across projects.

### 4.1 Docs → Everyone
- `docs/PRD.md`: acceptance criteria (FR-* and NFR-* IDs).
- `docs/ALGO_CARD.md`: parameter table + version pin.
- `docs/TRD.md` §4: module graph + sequence diagram.

### 4.2 Ingestion → Vision Pipeline
A typed object representing a validated input:

```python
@dataclass(frozen=True)
class Frame:
    image: np.ndarray            # decoded BGR / grayscale
    source_id: str               # camera / file / stream identifier
    captured_at: datetime        # UTC
    metadata: dict[str, Any]     # calibration ref, original filename, etc.
```

Ingestion guarantees: validated, decoded, in expected dimensions, free
of truncation. Vision Pipeline never has to re-validate.

### 4.3 Vision Pipeline → Core Algorithm
A typed result with full provenance:

```python
@dataclass(frozen=True)
class DetectionResult:
    frame_id: str
    detections: list[Detection]  # boxes / circles / measurements / classes
    confidence: float
    algo_version: str            # e.g. "algo-1.3.0"
    calibration_version: str
    debug: dict[str, Any]        # optional — for annotated images, masks
```

Vision Pipeline guarantees: deterministic given (frame, algo_version,
calibration). No I/O.

### 4.4 Core Algorithm → Output Handler
Two channels:

1. **REST**: OpenAPI schema generated by FastAPI. Pydantic models in
   `src/<pkg>/api/schemas.py` are the source of truth.
2. **Stream** (if needed): SSE / WebSocket events with stable type
   names. Documented in `docs/TRD.md` §5.

### 4.5 Everyone → QA
Every public dataclass / Pydantic model is importable. QA writes
fixtures and assertions against these types — never against private
internals.

---

## 5. Workflow for a NEW project

Linear, with feedback loops only when an upstream agent's output is
insufficient.

```
1. Orchestrator      → clones standardize-cv-template, renames package
2. Docs Agent        → drafts BRD/PRD/TRD/ALGO_CARD/RUNBOOK from problem statement
   --- HUMAN APPROVAL GATE: Algorithm Validation ---
   Reviewer reads ALGO_CARD + TRD §4, validates the algorithm choice,
   approves explicitly via `docs/decisions/ADR-001-algorithm-choice.md`
   (status: Accepted). Implementation does NOT begin until this ADR is
   accepted.
3. Ingestion Agent   → reads PRD inputs section + sample data → builds ingestion + validators
4. Vision Pipeline   → reads ALGO_CARD + ingestion contract → builds preprocessing + CV core
5. Core Algorithm    → reads PRD acceptance + vision output type → builds rules + API + persistence
6. Output Handler    → reads OpenAPI schema → builds dashboard / export pipeline
7. QA Agent          → runs alongside steps 3-6, writes tests + edge cases + benchmark
8. Orchestrator      → final consistency pass (docs ↔ code), opens release PR
```

Anti-patterns the orchestrator must reject:
- A new top-level folder that isn't in the canonical template.
- Code in `notebooks/`.
- A script not wired into Makefile or CI in `scripts/`.
- A doc outside the 5 canonical names (those go to `docs/extras/`).
- An algorithm change without a new `algo-X.Y.Z.yaml` and ADR.
- Any implementation work before the Algorithm Validation ADR is Accepted.

---

## 6. Workflow for a PAST project (validation)

This is how we apply the agents to repos that are already done (IAC,
agentic_ta) to prove reusability and surface gaps.

For each agent:
1. Read its assigned folder.
2. Score it against the canonical template:
   - Are the expected files present?
   - Do they match the contract for the next agent?
   - Are there gaps (HIGH / MED / LOW)?
3. Write a one-page report to `reports/audits/<agent>-<UTC>.md`.

The Orchestrator compiles all reports into a single scorecard:
`reports/audits/scorecard-<UTC>.md`.

If the *same* agent prompts produce a valid scorecard on both IAC and
agentic_ta with no project-specific tweaks, reusability is proven. If
not, the canonical template — not the agent — is the thing to fix.

---

## 7. Speed, Quality, Reusability — measurement

Captured in the scorecard each run.

| Metric | How it's measured | Target |
|--------|-------------------|--------|
| **Speed** | Wall-clock per agent + total | Full pass < 5 min on a clean repo |
| **Quality** | Gap count by severity, summed across agents; benchmark MAE / pass-rate vs prior run; coverage delta | HIGH-severity gaps = 0 before release |
| **Reusability** | Same agent definitions produce valid output on N projects without modification | Pass = ≥2 projects with zero diffs to agent prompts |

Quality is *not* a single number. It's the gap-count + benchmark-delta
combo. The intent is to spot regressions, not to compute a vanity score.

---

## 8. Why this works (and why the standardization step had to come first)

Reusability is structural, not prompt-engineered. The agents are
reusable *because* every CV project has the same folder layout, the
same 5 canonical docs, the same `src/<pkg>/processing/` slot for the CV
core, and the same uniform `reports/benchmark/TEMPLATE.md`.

Without `standardize-cv-template`, each project would need its own
agent prompts. With it, the same 7 agents work everywhere — you swap
the contents of `src/<pkg>/processing/` and the docs, and the agents
re-bind without changes.

This is the move from one-off solutions → reusable systems.

---

## 9. Where this doc lives

- **Primary**: workspace root (this file). Source of truth.
- **Canonical template**: `standardize-cv-template/docs/extras/multi_agent_approach.md` (so every new project inherits the approach).
- **Past projects**: `IAC-Microstop-System/docs/extras/multi_agent_approach.md` and `agentic_ta/docs/extras/multi_agent_approach.md`, dropped on branch `feat/multi-agent-approach`.

It lives in `docs/extras/` (not as a canonical doc) because it is
*supplemental* — the project still ships even if no one ever runs the
agents. Once the multi-agent system is implemented and routinely used
in CI, promote it to a canonical doc.

---

## 10. What's NOT in this round (next steps)

This doc is approach-only. The actual system is a separate repo:

```
multi-agent-cv/                       (future repo)
├── README.md
├── agents/
│   ├── orchestrator.md               (Claude Code agent definition)
│   ├── docs_agent.md
│   ├── data_ingestion_agent.md
│   ├── vision_pipeline_agent.md
│   ├── core_algorithm_agent.md
│   ├── output_handler_agent.md
│   └── qa_agent.md
├── orchestrator/
│   └── run.py                        (CLI: `python -m multi_agent_cv <repo>`)
├── contracts/
│   └── types.py                      (Frame, DetectionResult, etc.)
└── tests/
    └── test_on_canonical_template.py (sanity: agents work on the template)
```

The approach doc is the contract that repo will implement.

---

## Appendix A — Anti-patterns to reject

- **A god-agent that does docs + ingestion + vision** — collapses
  responsibility, kills reusability.
- **An agent that owns code outside its assigned folder** — breaks the
  blackboard rule.
- **A new top-level folder for a one-off concern** — fork the canonical
  template instead and propose a structural change.
- **An agent that depends on running another agent first via shared
  Python state** — handoff is via committed code only.
- **A scoring rubric that requires manual interpretation** — agents
  must produce machine-readable output (severity tags, metric numbers).

## Appendix B — Quick reference: which agent owns which folder

| Folder in canonical template | Agent |
|------------------------------|-------|
| `docs/` (BRD, PRD, TRD, RUNBOOK, ALGO_CARD, ADRs) | Docs |
| `data/` | Ingestion |
| `edge_cases/` | QA |
| `configs/algo_params/` | Vision Pipeline |
| `configs/calibration/` | Vision Pipeline (read-only) + Ingestion (loads at session start) |
| `src/<pkg>/ingestion/` | Ingestion |
| `src/<pkg>/processing/` | Vision Pipeline |
| `src/<pkg>/logic/` | Core Algorithm |
| `src/<pkg>/api/` | Core Algorithm |
| `src/<pkg>/persistence/` | Core Algorithm |
| `src/<pkg>/workers/` | Core Algorithm |
| `frontend/` | Output Handler |
| `tests/unit/` `tests/integration/` `tests/benchmark/` `tests/fixtures/` | QA |
| `reports/` | QA writes; Orchestrator compiles scorecard |
| `scripts/`, `Makefile`, `pyproject.toml`, CI | Orchestrator |
| `_archive/` | Orchestrator (only ever touched during migrations) |
