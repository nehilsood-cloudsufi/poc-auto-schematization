# Session Guide for KT Presenter

## 1. Mindset

- KT is a conversation, not a lecture. Check understanding at every step.
- Your goal: the junior engineer should be productive independently within 3 weeks.
- Silence = confusion, not agreement. Ask "What questions do you have?" (open-ended), not "Do you have questions?" (closed).
- It's okay to say "I don't remember, let me look it up" -- this models good engineering behavior.
- Prepare less than you think. Your deep knowledge of the system will fill gaps. Over-preparing leads to information dumping.
- The junior's job is NOT to memorize -- it's to build mental models they can navigate with.

## 2. Session Structure (1-Hour Template)

| Time | Activity | Purpose |
|------|----------|---------|
| 0-5 min | **Recap** -- Junior summarizes the previous session in their own words | Reveals gaps and misconceptions |
| 5-10 min | **Frame** -- State today's goal. Show where we are in the learning path | Orientation |
| 10-50 min | **Core material** -- Alternate between showing code and having junior navigate. Use exercises as breakpoints | Active learning |
| 50-55 min | **Summary** -- Junior summarizes today's session in own words | Retention check |
| 55-60 min | **Next steps** -- Assign take-home exercise. Ask "What was the most confusing part?" | Feedback loop |

Tips:
- If the junior can't summarize, you went too fast. Back up.
- If you're running out of time, cut content -- never cut the summary.
- If the junior is clearly lost, stop and address it. Plowing through helps no one.

## 3. Checking Understanding

### Teach-Back
After explaining a concept, ask the junior to explain it back to you in different words. "How would you explain PVMAPs to another engineer?" This is the single most effective technique.

### Code Prediction
Show a function signature and docstring. Ask "What do you think this returns?" before showing the implementation. Works great for:
- `repair_pvmap()` -- "What kinds of fixes do you think this makes?"
- `pre_validate_pvmap()` -- "What would make a PVMAP invalid before we even run it?"
- `_compact_skeleton_for_feedback()` -- "Why would we want to make the skeleton smaller?"

### Trace Exercises
Give specific input, ask them to predict output. Example: "Given this raw CSV row and this PVMAP, what does `stat_var_processor` output?" This builds the mental model of data flow.

### Deliberate Errors
Show code with a subtle bug. Ask "Something is wrong here -- what is it?" Great for:
- A PVMAP key with wrong casing (case-sensitive matching!)
- `{Number}` in an LlmAgent instruction string (ADK resolves it as state variable)
- Running validation on sampled data instead of full data

## 4. Common Mistakes to Avoid

| Mistake | Why It's Bad | Instead |
|---------|-------------|---------|
| Speed through "easy" parts | Junior's "easy" differs from yours | Watch their face; if they're scribbling notes furiously, slow down |
| Live-code during KT | Wastes time, shifts focus to syntax, typos derail | Show pre-written code, explain line by line |
| Cover 5+ concepts per session | Nothing sticks | Max 2 new concepts per session; depth > breadth |
| Skip Document 01 (domain) | Engineers who don't understand PVMAPs can't understand the pipeline | Always start with domain context, even if it feels "too basic" |
| Assume pre-reading was done | It often isn't | Verify at session start: "What did you take away from the reading?" |
| Combine KT with code review | Context-switches kill learning | Keep sessions focused on KT only |
| Talk for 30 min straight | Attention drops after 10 min | Alternate: 10 min explain -> 5 min exercise -> 10 min explain |
| Answer your own questions | Robs the junior of thinking time | Ask, then wait. Count to 10 silently if needed |

## 5. Pre-Session Checklist

Before each session:
- [ ] Screen sharing ready with editor open to relevant files
- [ ] Terminal ready: `.venv` activated, `PYTHONPATH` set, in project root
- [ ] Today's demo dataset already processed (output files ready to show)
  - BIS dataset: `python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate`
- [ ] KT document for today open in separate tab
- [ ] Today's exercise tested -- you've run every command yourself
- [ ] Notes from previous session reviewed (what was confusing?)
- [ ] Have the pipeline architecture diagram visible (from `docs/kt/02-architecture-overview.md`)

## 6. Handling Difficult Moments

### "I don't understand"
Good! They're being honest. Say: "That's fine -- which part specifically?" Then re-explain with a different analogy.

### Complete silence after a question
They might need time. Say: "Take a moment to think about it" then wait. If still stuck after 15 seconds: "Let me rephrase..."

### Junior asks a question you can't answer
Say: "Great question -- I don't know off the top of my head. Let's look it up together." Then grep the codebase or read the code live. This is excellent modeling.

### Junior seems bored (already knows this)
Ask: "Is this review for you, or is this new?" If review, skip ahead. Respect their time.

### Junior is overwhelmed
Normal for complex systems. Say: "You don't need to understand all of this today. We'll come back to it." Prioritize the 20% that matters for 80% of tasks.

## 7. After the Last Session

- Schedule 30-minute weekly check-ins for 4 weeks
- Identify 2-3 starter tasks (low-risk, real work, not busywork):
  - Add a new dataset to the pipeline
  - Fix a minor bug in PVMAP repair
  - Add a unit test for an edge case
- Make yourself available on Slack for ad-hoc questions
- Tell them: "There is no dumb question. Asking early saves hours."
