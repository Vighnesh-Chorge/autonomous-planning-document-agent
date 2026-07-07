# Autonomous Document Agent

An autonomous AI agent that takes a natural language request, plans its own
task list, executes each task through an LLM, and produces a polished
Microsoft Word (`.docx`) business document as the final output — built with
FastAPI, Groq (Llama 3.3 70B), and python-docx.

## How it works

```
Request → POST /agent → agent.py
                           ├─ generate_plan()   → LLM decides document type + task list
                           └─ execute_task() ×N → LLM writes each planned section
                         → doc_generator.py → renders a real .docx file
                         → response: task list + assumptions + download link
```

1. **Plan** — the request is sent to the LLM, which decides the document
   type (proposal, project plan, business report, etc.), a title, any
   assumptions it needs to make, and a task list of sections. Nothing here
   is hardcoded — the structure is generated per request.
2. **Execute** — the agent loops through that task list and makes a
   separate LLM call per section to write its actual content.
3. **Generate** — the finished content is assembled into a real `.docx`
   file using `python-docx`, with proper headings and bullet formatting.
4. **Respond** — the API returns the task list, any assumptions made, and
   a link to download the generated document.

## Engineering improvement: Retry & Fallback logic

Every LLM call in the system is wrapped in a single retry function
(`call_llm_with_retry` in `agent.py`):

- Automatically retries up to 2 times with backoff on network errors or
  malformed JSON (LLMs occasionally wrap JSON in markdown code fences,
  which breaks a strict parser — this is handled explicitly).
- If planning still fails after all retries, the agent falls back to a
  generic document plan instead of crashing.
- If a single section's content generation fails, only that section gets
  a placeholder — the rest of the document still completes.

This was chosen because LLM APIs are inherently unreliable (rate limits,
transient network issues, non-deterministic output formatting), and a
production-facing agent should degrade gracefully rather than fail
outright on a single bad response.

Basic **request validation** is also implemented via Pydantic in
`main.py`, rejecting empty or too-short requests before they reach the LLM.

## Tech stack

| Component | Choice | Why |
|---|---|---|
| API framework | FastAPI | Async, automatic request validation, built-in interactive docs |
| LLM | Groq — Llama 3.3 70B (free tier) | Fast inference, important since one request triggers multiple sequential LLM calls |
| Document generation | python-docx | Direct control over headings, paragraphs, and bullet formatting |
| Validation | Pydantic | Type-safe request parsing and guardrails |

## Project structure

```
agent_project/
├── main.py              # FastAPI app: POST /agent, GET /download/{id}, request validation
├── agent.py              # Planning + execution logic, retry/fallback wrapper
├── doc_generator.py       # Converts agent output into a polished .docx
├── client.py              # One-command test client: sends a request, auto-downloads the result
├── run_demo.py            # Single-terminal convenience script (starts server, tests, shuts down)
├── requirements.txt
├── .env.example           # Template — copy to .env and add your own Groq key
└── README.md
```

## Setup

```bash
git clone <this-repo-url>
cd agent_project

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate.bat

pip install -r requirements.txt

cp .env.example .env
# open .env and paste your own Groq API key into GROQ_API_KEY=
```

Get a free Groq API key at [console.groq.com](https://console.groq.com) —
no credit card required.

## Running

**Option A — two terminals (recommended for seeing the live API in action)**

Terminal 1:
```bash
uvicorn main:app --reload
```

Terminal 2:
```bash
python client.py "Create a project plan for launching a new mobile banking app, including timeline and key milestones"
```

This prints the agent's generated task list and assumptions, and
automatically downloads the resulting `.docx` file into the project folder.

**Option B — one terminal, fully automated**

```bash
python run_demo.py "Create a project plan for launching a new mobile banking app, including timeline and key milestones"
```

Starts the server in the background, sends the request, downloads the
file, then shuts the server down automatically.

**Option C — interactive Swagger UI**

With the server running, open `http://127.0.0.1:8000/docs` in a browser
to try the API by hand.

## Example requests

**Standard request:**
```bash
python client.py "Create a project plan for launching a new mobile banking app, including timeline and key milestones"
```

**Ambiguous / complex request** (missing information, conflicting
requirements — the agent makes and states its own assumptions):
```bash
python client.py "We need some kind of document for a client meeting next week, not sure if they want a proposal or a technical breakdown, budget still isnt finalized, just make something that works"
```

## Example response

```json
{
  "request_id": "a1b2c3d4",
  "document_type": "proposal",
  "title": "Preliminary Project Overview for Client Meeting",
  "assumptions_made": [
    "The client meeting is for introductory purposes and to discuss project scope",
    "A detailed technical breakdown and finalized budget will be provided in a future document"
  ],
  "agent_task_list": [
    { "step": 1, "section_title": "Introduction and Project Overview" },
    { "step": 2, "section_title": "Scope of Work" }
  ],
  "download_url": "/download/a1b2c3d4",
  "message": "Document generated successfully."
}
```

## Notes

- `.env` is intentionally excluded from this repo via `.gitignore` — you
  need your own free Groq API key to run this project.
- Generated `.docx` files and the `generated_docs/` folder are also
  excluded, since they're runtime output, not source code.
