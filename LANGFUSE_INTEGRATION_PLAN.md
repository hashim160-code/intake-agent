# Langfuse Integration Plan - ZScribe Intake System

## Executive Summary

This document outlines the implementation plan for integrating Langfuse observability platform into the ZScribe Intake system. The integration will provide comprehensive tracing, prompt management, and evaluation capabilities for both the LiveKit Intake Agent and the LangGraph Intake Notes Generator.

**Timeline:** 7-12 hours (split over 3 days)
**Complexity:** Medium
**Dependencies:** Langfuse Cloud account, API keys
**Team:** 1 developer (beginner-friendly with guided implementation)

---

## Table of Contents

1. [Integration Overview](#integration-overview)
2. [Langfuse Projects Structure](#langfuse-projects-structure)
3. [Phase-by-Phase Implementation](#phase-by-phase-implementation)
4. [Technical Requirements](#technical-requirements)
5. [Timeline & Resource Allocation](#timeline--resource-allocation)
6. [Deliverables](#deliverables)
7. [Success Criteria](#success-criteria)
8. [Risk Assessment](#risk-assessment)

---

## Integration Overview

### Components to Integrate

| Component | Type | Integration Method |
|-----------|------|-------------------|
| **Intake Agent** | LiveKit Voice Agent | Direct Langfuse SDK integration |
| **Intake Notes Generator** | LangGraph Workflow | LangGraph native Langfuse support |

### Langfuse Capabilities to Implement

#### 1. Tracing
- Capture complete conversation flows
- Track user IDs, organization IDs, session IDs
- Monitor latency, token usage, costs
- Debug agent behavior in production

#### 2. Prompt Management
- Version control for system prompts
- A/B testing different prompt variations
- Rollback capability for prompt changes
- Audit trail for all prompt modifications

#### 3. Evaluations
- **Template Adherence:** Verify agent follows intake template
- **Completeness Checks:** Ensure all required fields are collected
- **Quality Metrics:** Measure conversation quality
- **Custom Evals:** Business-specific quality checks

---

## Langfuse Projects Structure

### Project Architecture

```
ZScribe Langfuse Account
│
├── Project 1: "ZScribe - Intake Agent"
│   │
│   ├── Tracing
│   │   ├── Session ID: room_name (e.g., "intake-4ad8e0ec")
│   │   ├── User ID: patient_id
│   │   ├── Metadata: organization_id, template_id
│   │   └── Tags: ["production", "intake-call"]
│   │
│   ├── Prompts
│   │   ├── "intake-agent-system-prompt" (versioned)
│   │   ├── "greeting-prompt" (versioned)
│   │   └── "question-templates" (versioned)
│   │
│   └── Evaluations
│       ├── template_adherence_score
│       ├── completeness_score
│       ├── conversation_quality_score
│       └── response_time_check
│
└── Project 2: "ZScribe - Intake Notes Generator"
    │
    ├── Tracing
    │   ├── Session ID: transcript_id
    │   ├── User ID: patient_id
    │   ├── Metadata: organization_id, model_used
    │   └── Tags: ["production", "notes-generation"]
    │
    ├── Prompts
    │   ├── "intake-notes-generation-prompt" (versioned)
    │   └── "notes-template" (versioned)
    │
    └── Evaluations
        ├── notes_completeness_score
        ├── field_extraction_accuracy
        └── medical_terminology_check
```

### Why Two Projects?

| Aspect | Benefit |
|--------|---------|
| **Separation of Concerns** | Different systems, different metrics |
| **Independent Scaling** | Agent and notes have different usage patterns |
| **Clear Accountability** | Different teams can own different projects |
| **Better Analytics** | Easier to track performance per component |
| **Simplified Debugging** | Isolated traces don't mix concerns |

---

## Phase-by-Phase Implementation

### Phase 1: Setup & Configuration (Day 1 - Morning)

**Duration:** 30-45 minutes
**Complexity:** Low

#### Tasks:

1. **Create Langfuse Account**
   - Sign up at https://cloud.langfuse.com
   - Verify email and access dashboard

2. **Create Projects**
   - Project 1: "ZScribe - Intake Agent"
   - Project 2: "ZScribe - Intake Notes Generator"

3. **Obtain API Keys**
   - Generate API keys for both projects
   - Store securely in environment variables

4. **Install Dependencies**
   ```bash
   # For Intake Agent
   pip install langfuse

   # For Intake Notes (already has langchain dependencies)
   pip install langfuse
   ```

5. **Environment Configuration**
   ```bash
   # Add to .env
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com

   # For Notes Generator (separate keys)
   LANGFUSE_NOTES_SECRET_KEY=sk-lf-...
   LANGFUSE_NOTES_PUBLIC_KEY=pk-lf-...
   ```

#### Deliverables:
- ✅ Two active Langfuse projects
- ✅ API keys stored in `.env`
- ✅ Langfuse SDK installed

---

### Phase 2: Intake Agent Integration (Day 1 - Afternoon)

**Duration:** 2-3 hours
**Complexity:** Medium

#### 2.1 Basic Tracing Setup

**File:** `src/calling_agent.py`

**Tasks:**

1. **Initialize Langfuse Client**
   ```python
   from langfuse import Langfuse

   langfuse = Langfuse(
       secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
       public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
       host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
   )
   ```

2. **Create Trace for Each Call**
   ```python
   async def entrypoint(ctx: JobContext):
       # Start Langfuse trace
       trace = langfuse.trace(
           name="intake-call",
           session_id=ctx.room.name,
           user_id=patient_id,
           metadata={
               "organization_id": organization_id,
               "template_id": template_id,
               "job_id": ctx.job.id
           },
           tags=["production", "intake-agent"]
       )
   ```

3. **Add Spans for Key Operations**
   ```python
   # Span for loading instructions
   with trace.span(name="load-instructions") as span:
       instructions = await generate_instructions_from_api(...)
       span.end(metadata={"instructions_length": len(instructions)})

   # Span for agent session
   with trace.span(name="agent-session") as span:
       await session.start(agent=IntakeAgent(...), room=ctx.room)
       span.end()
   ```

4. **Track LLM Generations**
   ```python
   # This will be automatic with LiveKit + Langfuse callback
   # But we can add custom tracking
   generation = trace.generation(
       name="llm-response",
       model="moonshotai/kimi-k2-instruct",
       input=prompt,
       output=response,
       metadata={"provider": "baseten"}
   )
   ```

5. **Save Transcript with Trace Link**
   ```python
   async def save_transcript():
       trace.update(
           output=session.history.to_dict(),
           metadata={
               "call_duration": duration,
               "message_count": len(session.history)
           }
       )
   ```

#### 2.2 Custom Metadata Tracking

**Capture:**
- Patient demographics (non-PII)
- Call duration
- Number of questions asked
- Template completion percentage
- STT confidence scores
- LLM response times

#### Deliverables:
- ✅ All calls traced in Langfuse
- ✅ User/Org/Session IDs captured
- ✅ LLM calls tracked with token usage
- ✅ Real-time dashboard showing active calls

---

### Phase 3: Intake Notes Integration (Day 2 - Morning)

**Duration:** 1-2 hours
**Complexity:** Low (built-in support)

#### 3.1 LangGraph Configuration

**File:** `intake_notes/src/graph.py`

**Tasks:**

1. **Add Langfuse Callback**
   ```python
   from langfuse.callback import CallbackHandler

   langfuse_handler = CallbackHandler(
       secret_key=os.getenv("LANGFUSE_NOTES_SECRET_KEY"),
       public_key=os.getenv("LANGFUSE_NOTES_PUBLIC_KEY"),
       host=os.getenv("LANGFUSE_HOST")
   )
   ```

2. **Configure LLM with Callback**
   ```python
   from langchain_google_genai import ChatGoogleGenerativeAI

   llm = ChatGoogleGenerativeAI(
       model="gemini-2.0-flash-exp",
       callbacks=[langfuse_handler]
   )
   ```

3. **Add Trace Metadata**
   ```python
   def run_graph(input_data: Dict[str, Any]) -> Dict[str, Any]:
       # Set trace context
       langfuse_handler.trace(
           name="intake-notes-generation",
           session_id=input_data.get("transcript_id"),
           user_id=input_data.get("patient_id"),
           metadata={
               "model": "gemini-2.0-flash-exp",
               "transcript_length": len(input_data["transcript"])
           }
       )

       result = graph.invoke(initial_state)
       return result
   ```

#### Deliverables:
- ✅ Note generation runs traced
- ✅ LLM calls tracked with prompts/outputs
- ✅ Token usage and costs visible
- ✅ Link to original call trace (via transcript_id)

---

### Phase 4: Prompt Management (Day 2 - Afternoon)

**Duration:** 1-2 hours
**Complexity:** Medium

#### 4.1 Migrate Prompts to Langfuse

**Tasks:**

1. **Create Prompts in Langfuse Dashboard**
   - Navigate to Prompts section
   - Create prompt: "intake-agent-system-prompt"
   - Add variables: `{{patient_name}}`, `{{template_questions}}`
   - Set version: v1.0

2. **Update Agent to Fetch Prompts**
   ```python
   # In prompts.py
   async def generate_instructions_from_api(...):
       # Fetch prompt from Langfuse
       prompt = langfuse.get_prompt(
           name="intake-agent-system-prompt",
           version="production"  # or specific version
       )

       # Compile with variables
       instructions = prompt.compile(
           patient_name=patient_data["name"],
           template_questions=template_questions
       )

       return instructions
   ```

3. **Version Control Setup**
   - Tag current prompt as "v1.0"
   - Create "production" label
   - Set up prompt change approval workflow

#### 4.2 Prompt Testing & Rollback

**Create Test Suite:**
```python
def test_prompt_version(version: str):
    """Test prompt with sample data"""
    prompt = langfuse.get_prompt("intake-agent-system-prompt", version=version)

    # Test with sample inputs
    result = agent.run_with_prompt(prompt)

    # Evaluate quality
    assert result.completeness_score > 0.8
```

**Rollback Procedure:**
1. Identify issue in production
2. Check Langfuse audit log
3. Rollback to previous version
4. Verify improvement

#### Deliverables:
- ✅ All prompts managed in Langfuse
- ✅ Version control active
- ✅ Rollback capability tested
- ✅ Audit trail visible

---

### Phase 5: Evaluations Setup (Day 3)

**Duration:** 2-3 hours
**Complexity:** Medium-High

#### 5.1 Template Adherence Evaluation

**Purpose:** Ensure agent asks all required questions from template

**Implementation:**
```python
from langfuse import Langfuse

def evaluate_template_adherence(trace_id: str, template_id: str):
    """
    Check if agent covered all template questions
    """
    # Get trace
    trace = langfuse.get_trace(trace_id)

    # Get template questions
    template = get_template(template_id)
    required_questions = template.questions

    # Extract asked questions from transcript
    asked_questions = extract_questions_from_trace(trace)

    # Calculate coverage
    coverage = len(asked_questions & required_questions) / len(required_questions)

    # Score trace
    trace.score(
        name="template_adherence",
        value=coverage,
        comment=f"Covered {len(asked_questions)}/{len(required_questions)} questions"
    )

    return coverage
```

**Schedule:** Run after every call (via webhook)

#### 5.2 Completeness Check Evaluation

**Purpose:** Verify all required fields were collected

**Implementation:**
```python
def evaluate_completeness(trace_id: str, intake_notes: dict):
    """
    Check if all required fields have values
    """
    required_fields = [
        "chief_complaint",
        "allergies",
        "medications",
        "medical_history"
    ]

    collected_fields = [
        field for field in required_fields
        if intake_notes.get(field) is not None
    ]

    completeness = len(collected_fields) / len(required_fields)

    langfuse.score(
        trace_id=trace_id,
        name="completeness",
        value=completeness,
        comment=f"Collected {len(collected_fields)}/{len(required_fields)} fields"
    )

    return completeness
```

#### 5.3 Conversation Quality Evaluation

**Purpose:** Assess naturalness and professionalism

**Implementation (LLM-as-Judge):**
```python
def evaluate_conversation_quality(trace_id: str):
    """
    Use LLM to evaluate conversation quality
    """
    trace = langfuse.get_trace(trace_id)
    transcript = trace.output

    # Use evaluation LLM
    eval_prompt = f"""
    Evaluate this medical intake conversation on a scale of 0-1:

    Criteria:
    - Professionalism
    - Empathy
    - Clarity
    - Efficiency

    Transcript:
    {transcript}

    Return only a number between 0 and 1.
    """

    score = llm_evaluate(eval_prompt)

    langfuse.score(
        trace_id=trace_id,
        name="conversation_quality",
        value=float(score)
    )
```

#### 5.4 Automated Evaluation Pipeline

**Webhook Integration:**
```python
# In backend webhook handler
async def process_call_ended(data: dict):
    # 1. Save transcript
    transcript_id = await save_transcript(data)

    # 2. Generate notes
    notes = await generate_intake_notes(data["transcript"])

    # 3. Run evaluations (async)
    background_tasks.add_task(run_evaluations, {
        "trace_id": data["job_id"],
        "template_id": data["template_id"],
        "transcript": data["transcript"],
        "notes": notes
    })

async def run_evaluations(data: dict):
    """Run all evaluations"""
    # Template adherence
    adherence = evaluate_template_adherence(
        data["trace_id"],
        data["template_id"]
    )

    # Completeness
    completeness = evaluate_completeness(
        data["trace_id"],
        data["notes"]
    )

    # Quality
    quality = evaluate_conversation_quality(data["trace_id"])

    # Alert if scores are low
    if adherence < 0.7 or completeness < 0.8:
        await send_alert(data["trace_id"], {
            "adherence": adherence,
            "completeness": completeness
        })
```

#### Deliverables:
- ✅ Template adherence eval running
- ✅ Completeness check active
- ✅ Conversation quality scoring
- ✅ Automated eval pipeline
- ✅ Alerts for low scores

---

## Technical Requirements

### Dependencies

```toml
# Add to requirements.txt or pyproject.toml
langfuse>=2.0.0
opentelemetry-api>=1.20.0  # For tracing
opentelemetry-sdk>=1.20.0
```

### Environment Variables

```bash
# Intake Agent
LANGFUSE_SECRET_KEY=sk-lf-xxxxxx
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxx
LANGFUSE_HOST=https://cloud.langfuse.com

# Intake Notes Generator
LANGFUSE_NOTES_SECRET_KEY=sk-lf-yyyyyy
LANGFUSE_NOTES_PUBLIC_KEY=pk-lf-yyyyyy
```

### Infrastructure

| Component | Requirement |
|-----------|-------------|
| **Langfuse Hosting** | Cloud (recommended) or Self-hosted VM |
| **Network** | Outbound HTTPS to cloud.langfuse.com |
| **Storage** | ~100MB for SDK dependencies |
| **Performance** | Negligible overhead (async tracing) |

---

## Timeline & Resource Allocation

### Development Timeline

```
Week 1
├── Day 1 (4 hours)
│   ├── Morning: Phase 1 - Setup (30 min)
│   └── Afternoon: Phase 2 - Agent Integration (3.5 hours)
│
├── Day 2 (4 hours)
│   ├── Morning: Phase 3 - Notes Integration (2 hours)
│   └── Afternoon: Phase 4 - Prompt Management (2 hours)
│
└── Day 3 (4 hours)
    └── Phase 5 - Evaluations (3 hours)
    └── Testing & Documentation (1 hour)

Total: 12 hours over 3 days
```

### Resource Requirements

| Role | Hours | Tasks |
|------|-------|-------|
| **Developer** | 12 hours | Implementation, testing |
| **Manager** | 1 hour | Review, approval |
| **QA** | 2 hours | Testing evaluations |

---

## Deliverables

### Phase 1 Deliverables
- [ ] Langfuse account active
- [ ] Two projects created
- [ ] API keys generated and stored
- [ ] SDK installed

### Phase 2 Deliverables
- [ ] Agent traces visible in Langfuse
- [ ] User/Org/Session IDs captured
- [ ] LLM calls tracked
- [ ] Dashboard showing real-time calls

### Phase 3 Deliverables
- [ ] Notes generation traced
- [ ] Prompts/outputs visible
- [ ] Token usage tracked

### Phase 4 Deliverables
- [ ] Prompts in Langfuse
- [ ] Version control active
- [ ] Rollback tested
- [ ] Audit trail documented

### Phase 5 Deliverables
- [ ] Template adherence eval working
- [ ] Completeness check active
- [ ] Quality scoring implemented
- [ ] Automated pipeline running
- [ ] Alert system configured

### Final Deliverables
- [ ] Integration documentation
- [ ] Runbook for monitoring
- [ ] Evaluation playbook
- [ ] Training session for team

---

## Success Criteria

### Tracing Success Metrics

| Metric | Target |
|--------|--------|
| **Trace Capture Rate** | 100% of calls traced |
| **Trace Latency** | < 50ms overhead |
| **Metadata Completeness** | User/Org/Session in 100% of traces |
| **Trace Retention** | 90 days minimum |

### Prompt Management Success Metrics

| Metric | Target |
|--------|--------|
| **Prompt Version Control** | All prompts versioned |
| **Rollback Time** | < 5 minutes |
| **Audit Visibility** | 100% of changes logged |
| **A/B Test Capability** | 2+ variants testable |

### Evaluation Success Metrics

| Metric | Target |
|--------|--------|
| **Template Adherence** | Average > 0.85 |
| **Completeness Score** | Average > 0.90 |
| **Conversation Quality** | Average > 0.80 |
| **Eval Execution Time** | < 30 seconds per call |
| **Alert Response Time** | < 5 minutes for low scores |

---

## Risk Assessment

### Potential Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Performance Overhead** | Medium | Low | Async tracing, batch uploads |
| **API Key Exposure** | High | Low | Secure env vars, rotation policy |
| **Evaluation Accuracy** | Medium | Medium | Human validation loop |
| **Cost Overruns** | Low | Low | Monitor token usage, set budgets |
| **Integration Bugs** | Medium | Medium | Comprehensive testing, rollback plan |

### Rollback Plan

If integration causes issues:

1. **Immediate:** Disable Langfuse in env vars (set to empty)
2. **Short-term:** Remove callback handlers from code
3. **Long-term:** Revert to previous commit
4. **Data:** No data loss - Langfuse is observability only

---

## Monitoring & Maintenance

### Daily Monitoring

- Check Langfuse dashboard for failed traces
- Review evaluation scores for anomalies
- Monitor token usage and costs

### Weekly Review

- Analyze prompt performance across versions
- Review low-scoring calls
- Adjust evaluation thresholds if needed

### Monthly Maintenance

- Archive old traces (if self-hosted)
- Review and optimize evaluation logic
- Update prompt versions based on learnings

---

## Cost Estimate

### Langfuse Cloud Pricing

| Plan | Cost | Suitable For |
|------|------|--------------|
| **Free** | $0/month | Development, < 50k traces/month |
| **Pro** | $59/month | Production, < 500k traces/month |
| **Enterprise** | Custom | High volume, custom SLA |

**Estimated Usage:**
- Intake calls: ~1,000/month = 1,000 traces
- Note generations: ~1,000/month = 1,000 traces
- **Total:** ~2,000 traces/month

**Recommendation:** Start with **Free plan**, upgrade to Pro if needed.

---

## Next Steps

### Immediate Actions (This Week)

1. **Manager Approval** - Review and approve this plan
2. **Developer Assignment** - Assign developer to project
3. **Account Setup** - Create Langfuse account
4. **Kickoff Meeting** - Developer + Manager alignment

### Phase 1 Start (Next Week)

1. Developer begins Phase 1 (Setup)
2. Daily standup for progress updates
3. Documentation as you go

---

## Appendix

### Useful Resources

- **Langfuse Docs:** https://langfuse.com/docs
- **Tracing Guide:** https://langfuse.com/docs/tracing
- **Prompt Management:** https://langfuse.com/docs/prompts
- **Evaluations:** https://langfuse.com/docs/scores/model-based-evals
- **LangChain Integration:** https://langfuse.com/docs/integrations/langchain

### Sample Code Repository

All sample code will be provided in:
- `docs/langfuse-examples/agent-tracing.py`
- `docs/langfuse-examples/notes-tracing.py`
- `docs/langfuse-examples/evaluations.py`

---

## Document Information

**Version:** 1.0
**Created:** October 20, 2025
**Author:** Development Team
**Status:** Ready for Implementation
**Next Review:** After Phase 1 completion

---

## Sign-off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| **Developer** | _________ | _________ | __/__/__ |
| **Manager** | _________ | _________ | __/__/__ |
| **QA Lead** | _________ | _________ | __/__/__ |

---

**END OF DOCUMENT**
