# ADK Retry Loop - Improvement Plan

## Issues Identified

### 1. SamplingAgentWrapper Infinite Loop (Critical)
**Problem:** Forced tool calling mode (`FunctionCallingConfigMode.ANY`) with no iteration limit causes infinite API calls.

**Fix:** Add max_llm_calls limit to the inner Runner.

### 2. Error Feedback May Not Propagate (High Priority)
**Problem:** The FeedbackAgent uses `output_key="error_feedback"` but we need to verify ADK actually persists this to session state between LoopAgent iterations.

**Symptoms:** Generator kept making the same mistakes despite feedback.

**Fix:** Add explicit state logging in StatePreparationAgent to verify feedback is present.

### 3. Placeholder Syntax Confusion (Medium Priority)
**Problem:** Using `PASSTHROUGH_DATA`/`PASSTHROUGH_NUMBER` is confusing. The FeedbackAgent even got confused about it (see iteration 3 feedback mentioning both syntaxes).

**Fix Options:**
- Option A: Use `[DATA]` and `[NUMBER]` instead (less likely to conflict with ADK templating)
- Option B: Move examples into state variables that get injected
- Option C: Use raw string blocks in instruction

### 4. Generator Not Learning from Feedback (Medium Priority)
**Problem:** Despite clear feedback about key mismatches, the Generator repeated the same errors.

**Fix:**
- Add more explicit "PREVIOUS ATTEMPT FAILED" section at the TOP of instruction
- Include the specific failed keys from previous attempt
- Make error feedback more structured (JSON format)

### 5. Missing Validation for Structured Output (Low Priority)
**Problem:** ValidationAgent assumes `pvmap_output` is a dict, but doesn't handle edge cases.

**Fix:** Add better error handling and type checking.

---

## Proposed Changes

### Fix 1: SamplingAgentWrapper Iteration Limit

```python
# In sampling_agent.py, add timeout and max iterations
async def _run_async_impl(self, ctx: InvocationContext):
    # ... existing code ...

    # Create runner with iteration limit
    runner = Runner(
        app_name="sampling",
        agent=sampling_llm,
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    # Run with timeout
    import asyncio
    max_iterations = 15
    iteration = 0

    for event in runner.run(...):
        iteration += 1
        if iteration > max_iterations:
            yield self._create_event("Max iterations reached, stopping sampling")
            break
        # ... process event ...
```

### Fix 2: Verify Error Feedback Propagation

```python
# In StatePreparationAgent, add logging
async def _run_async_impl(self, ctx: InvocationContext):
    # ... existing code ...

    # Log current error_feedback state for debugging
    existing_feedback = ctx.session.state.get("error_feedback", "")
    if existing_feedback:
        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"Error feedback from previous attempt ({len(existing_feedback)} chars)")
            ])
        )
```

### Fix 3: Structured Error Feedback

```python
# In feedback_agent.py, use output_schema for structured feedback
class ErrorFeedback(BaseModel):
    root_cause: str
    affected_keys: List[str]
    specific_fixes: List[str]
    is_systematic: bool

def create_feedback_agent():
    return LlmAgent(
        name="Feedback",
        model=model,
        instruction=FEEDBACK_INSTRUCTION,
        output_schema=ErrorFeedback,  # Structured feedback
        output_key="error_feedback_structured"
    )
```

### Fix 4: Better Placeholder Syntax

Replace `PASSTHROUGH_DATA` with `[DATA]` or `<DATA>`:
- Less verbose
- Clearer semantics
- Won't conflict with any templating

---

## Testing Checklist

After implementing fixes:

- [ ] Run with `--force-resample` to test sampling limit
- [ ] Verify error_feedback appears in Generator instruction on retry
- [ ] Test with a dataset that should succeed (e.g., pre-formatted data)
- [ ] Verify LoopAgent exits early on validation success
- [ ] Check that evaluation runs after loop completion

## Quick Test Commands

```bash
# Test structured output with skip-sampling
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --structured-output --skip-sampling

# Test with a simpler dataset
python src/run_pipeline.py --dataset=<pre-formatted-dataset> --structured-output --skip-sampling

# Test sampling with iteration limit (after fix)
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --structured-output --force-resample
```
