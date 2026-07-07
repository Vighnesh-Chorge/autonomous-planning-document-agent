"""
main.py
-------
FastAPI entrypoint.

POST /agent
    Body: {"request": "natural language request here"}
    Flow:
        1. Basic request validation / guardrail (reject empty / too-short input)
        2. agent.run_agent() -> plans tasks, executes each, returns structured result
        3. doc_generator.generate_docx() -> writes the .docx to disk
        4. Response includes the task list, assumptions, and a download link
GET /download/{request_id}
    Serves the generated .docx file.
"""

import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from agent import run_agent
from doc_generator import generate_docx

app = FastAPI(title="Autonomous Document Agent")


class AgentRequest(BaseModel):
    request: str

    # ---- Guardrail: basic request validation ----
    @field_validator("request")
    @classmethod
    def request_must_be_meaningful(cls, v: str):
        if not v or not v.strip():
            raise ValueError("request cannot be empty")
        if len(v.strip()) < 5:
            raise ValueError("request is too short to act on")
        return v.strip()


@app.post("/agent")
def agent_endpoint(payload: AgentRequest):
    request_id = str(uuid.uuid4())[:8]

    try:
        result = run_agent(payload.request)
    except Exception as e:
        # Even with retries inside agent.py, this is a last-resort safety net
        # so the API never returns a raw 500 with a stack trace to the caller.
        raise HTTPException(status_code=500, detail=f"Agent failed unexpectedly: {e}")

    try:
        filepath = generate_docx(result, request_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document generation failed: {e}")

    return {
        "request_id": request_id,
        "document_type": result["document_type"],
        "title": result["title"],
        "assumptions_made": result["assumptions"],
        "agent_task_list": result["task_list"],
        "download_url": f"/download/{request_id}",
        "message": "Document generated successfully."
    }


@app.get("/download/{request_id}")
def download(request_id: str):
    filepath = f"generated_docs/{request_id}.docx"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{request_id}.docx",
    )


@app.get("/")
def root():
    return {"status": "Autonomous Document Agent is running. POST to /agent to use it."}
