"""
agent.py
--------
Core autonomous agent logic.

Flow:
    1. PLAN   -> ask the LLM to break the user's request into a concrete
                 task list (JSON) including the target document type.
    2. EXECUTE-> for each planned task, ask the LLM to produce the actual
                 content for that section.
    3. Both steps are wrapped in call_llm_with_retry(), which is the
       mandatory "engineering improvement" for this assignment:
       automatic retry with backoff + a deterministic fallback so the
       agent degrades gracefully instead of crashing when the LLM
       returns bad JSON, times out, or errors.
"""

import os
import json
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"  # free-tier Groq model


# ---------------------------------------------------------------------------
# ENGINEERING IMPROVEMENT: Retry & Fallback wrapper around every LLM call
# ---------------------------------------------------------------------------
def call_llm_with_retry(messages, max_retries=2, expect_json=False):
    """
    Calls the Groq LLM with automatic retry + exponential backoff.
    If every attempt fails (network error, API error, or malformed JSON
    when expect_json=True), returns None instead of raising, so callers
    can fall back to a safe default rather than crashing the whole agent.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.4,
                max_tokens=2000,
            )
            content = response.choices[0].message.content.strip()

            if expect_json:
                # Strip markdown code fences if the model adds them
                cleaned = content.replace("```json", "").replace("```", "").strip()
                return json.loads(cleaned)  # raises if malformed -> caught below
            return content

        except (json.JSONDecodeError, Exception) as e:
            last_error = e
            wait = 1.5 * (attempt + 1)
            print(f"[LLM call failed - attempt {attempt + 1}/{max_retries + 1}] {e}. "
                  f"Retrying in {wait}s..." if attempt < max_retries else f"[LLM call failed - giving up] {e}")
            if attempt < max_retries:
                time.sleep(wait)

    print(f"[call_llm_with_retry] All attempts failed. Last error: {last_error}")
    return None


# ---------------------------------------------------------------------------
# STEP 1: PLANNING - the agent decides its own task list
# ---------------------------------------------------------------------------
def generate_plan(user_request: str):
    """
    Asks the LLM to analyze the request and produce:
      - the type of business document to create
      - a title
      - an ordered list of sections/tasks needed to complete it
      - any assumptions it had to make (important for ambiguous requests)
    Falls back to a generic plan if the LLM fails entirely.
    """
    system_prompt = """You are an autonomous planning agent. Given a user's request,
decide what business document should be produced (choose one: proposal, meeting_minutes,
project_plan, business_report, technical_design, sop, product_spec).

If the request is ambiguous, missing information, or has conflicting requirements,
make reasonable professional assumptions and list them explicitly - do not ask
clarifying questions, since you must act autonomously.

Respond with ONLY valid JSON in this exact structure, no extra text:
{
  "document_type": "proposal",
  "title": "Document Title Here",
  "assumptions": ["assumption 1", "assumption 2"],
  "tasks": [
    {"step": 1, "section_title": "Executive Summary", "instructions": "what this section should cover"},
    {"step": 2, "section_title": "Scope of Work", "instructions": "what this section should cover"}
  ]
}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_request},
    ]

    plan = call_llm_with_retry(messages, expect_json=True)

    # ---- Guardrail / fallback: if planning failed or JSON is malformed,
    # use a safe generic plan so the agent still produces *something*.
    if not plan or "tasks" not in plan or not plan["tasks"]:
        print("[generate_plan] Falling back to default generic plan.")
        plan = {
            "document_type": "business_report",
            "title": "Generated Business Document",
            "assumptions": [
                "Original request could not be parsed into a structured plan; "
                "a generic business report structure was used instead."
            ],
            "tasks": [
                {"step": 1, "section_title": "Overview", "instructions": user_request},
                {"step": 2, "section_title": "Key Details", "instructions": user_request},
                {"step": 3, "section_title": "Next Steps", "instructions": "Suggest reasonable next steps."},
            ],
        }
    return plan


# ---------------------------------------------------------------------------
# STEP 2: EXECUTION - the agent carries out each planned task
# ---------------------------------------------------------------------------
def execute_task(task: dict, user_request: str, document_type: str):
    """
    Generates the actual written content for one section of the plan.
    Falls back to a placeholder paragraph if the LLM call fails, so one
    failed section never breaks the whole document.
    """
    system_prompt = f"""You are writing one section of a {document_type} document.
Write clear, professional business content for the section titled "{task['section_title']}".
Use the section instructions and the original user request as context.
Output plain text only (no markdown headers, the title is handled separately).
Keep it concise: 3-6 sentences or short bullet points where appropriate."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Original request: {user_request}\n\n"
                                     f"Section instructions: {task['instructions']}"},
    ]

    content = call_llm_with_retry(messages, expect_json=False)

    if not content:
        content = (f"[Content generation failed for this section after retries. "
                   f"Placeholder based on instructions: {task['instructions']}]")
    return content


# ---------------------------------------------------------------------------
# ORCHESTRATOR - ties planning + execution together
# ---------------------------------------------------------------------------
def run_agent(user_request: str):
    plan = generate_plan(user_request)

    executed_sections = []
    for task in plan["tasks"]:
        content = execute_task(task, user_request, plan["document_type"])
        executed_sections.append({
            "step": task["step"],
            "section_title": task["section_title"],
            "content": content,
        })

    return {
        "document_type": plan["document_type"],
        "title": plan["title"],
        "assumptions": plan.get("assumptions", []),
        "task_list": [
            {"step": t["step"], "section_title": t["section_title"]} for t in plan["tasks"]
        ],
        "sections": executed_sections,
    }
