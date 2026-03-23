# KT Schedule: 9 Sessions Over 3 Weeks

---

## Pre-Work (Before Week 1)

Assign before the first session:

- [ ] Read `docs/SETUP.md` and complete environment setup
- [ ] Read `docs/kt/01-domain-primer.md`
- [ ] Run the BIS dataset once: `python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate`
- [ ] Skim `docs/USAGE.md`

---

## Week 1: Foundation

| Session | Day | Topic | KT Docs | Exercises | Pre-Reading for Next Session |
|---------|-----|-------|---------|-----------|------------------------------|
| 1 | Mon | Domain concepts + Architecture overview | 01, 02 | Ex 1 (setup & run), Ex 2 (trace PVMAP) | Doc 03 (Phases 1-2) |
| 2 | Wed | Discovery + Sampling deep dive | 03 (Ph 1-2) | Ex 6 (trace sampling pipeline) | Doc 03 (Phase 2.5) |
| 3 | Fri | Schema Selection + Prompt anatomy | 03 (Ph 2.5), prompt file | Ex 7 (read & modify prompt) | Doc 03 (Phase 3) |

**Week 1 goal:** Junior can explain what a PVMAP is, how data flows through the first 3 phases, and run the pipeline independently.

---

## Week 2: Core Pipeline

| Session | Day | Topic | KT Docs | Exercises | Pre-Reading for Next Session |
|---------|-----|-------|---------|-----------|------------------------------|
| 4 | Mon | Retry Loop Part 1: Generation + Validation | 03 (Ph 3), 04 (patterns 1-2) | Ex 4 (break & fix PVMAP) | Doc 04 (patterns 3-6) |
| 5 | Wed | Retry Loop Part 2: Feedback + Quality + Exit | 03 (Ph 3), 04 (patterns 3-6) | Ex 3 (identify all agents in loop) | Doc 03 (Phase 5), Doc 04 |
| 6 | Fri | Evaluation + Schema.org + MCP overview | 03 (Ph 5), 04 | Ex 5 (add new dataset) | Doc 05 |

**Week 2 goal:** Junior can trace a PVMAP through the retry loop, understand validation, and explain exit conditions.

---

## Week 3: Independence

| Session | Day | Topic | KT Docs | Exercises | Pre-Reading for Next Session |
|---------|-----|-------|---------|-----------|------------------------------|
| 7 | Mon | Testing + Debugging workflows | 05 | Ex 8 (write a test) | -- |
| 8 | Wed | `run_pipeline.py` end-to-end + Streamlit UI + State management | 02, 05 | -- | Review all KT docs |
| 9 | Fri | **Reverse KT** -- Junior presents the pipeline walkthrough | All | -- | -- |

**Week 3 goal:** Junior can debug failures independently, write tests, and explain the full system.

---

## Session Details

### Sessions 1-3: Building the Mental Model

These sessions focus on "what" and "why." The junior should leave each session able to draw the data flow for the phases covered. Use the BIS dataset as the running example throughout -- it is small, fast, and has clear ground truth.

Session 1 is the most important. If the junior does not understand PVMAPs and the Data Commons vocabulary after session 1, everything else will be confusing. Spend extra time on Exercise 2 (trace a PVMAP) if needed.

### Sessions 4-6: Understanding the Machinery

These sessions focus on "how." The retry loop is the hardest part of the codebase to understand because it involves 10+ agents, state management, and silent failure modes. Use Exercise 3 (read the retry loop) as the anchor -- have the junior walk through the code with you, not just read it.

Session 4 should include a live demo of breaking and fixing a PVMAP (Exercise 4). Seeing validation fail and then watching repair fix the problems builds intuition faster than reading about it.

### Sessions 7-9: Building Confidence

Session 7 is practical: the junior writes a real test and runs it. Session 8 is a tour of the full `run_pipeline.py` file and the Streamlit UI -- this ties together everything from the previous two weeks.

Session 9 is the reverse KT. See details below.

---

## Session 9: Reverse KT

The junior presents the pipeline to you (or another engineer). This is the best test of understanding.

- Allocate 30 min for presentation, 15 min for Q&A, 15 min for feedback
- Encourage them to use diagrams or a whiteboard
- Do not interrupt during the presentation -- note gaps and discuss after
- This is not a test. It is a learning tool. Frame it as practice for explaining systems to stakeholders.

**What to look for:**
- Can they explain the 5 pipeline phases without notes?
- Do they understand why validation runs on full data, not sampled data?
- Can they describe what happens when a retry fails?
- Do they know where to look when something breaks?

---

## Post-KT Plan

### Weeks 4-7: Supervised Independence

- 30-minute weekly check-in for 4 weeks
- Assign 2-3 starter tasks:
  1. **Add a new dataset to the pipeline** (low risk, high learning -- forces them to understand input structure, sampling, and validation)
  2. **Fix a minor bug or improve error messaging in PVMAP repair** (teaches them the validation/repair code path)
  3. **Add unit tests for an uncovered edge case** (reinforces testing habits)
- Be available for ad-hoc questions on Slack
- Review their first few PRs thoroughly with explanatory comments

### After Week 7

The junior should be able to:
- Debug pipeline failures without assistance
- Make small to medium changes to agents, prompts, or validation logic
- Add new datasets and verify correctness
- Write tests for their changes

If they are not there yet, extend the weekly check-ins. The most common gap is not understanding the retry loop state flow -- revisit Sessions 4-5 material if needed.
