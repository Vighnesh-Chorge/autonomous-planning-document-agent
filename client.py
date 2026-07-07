"""
client.py
---------
One-shot test client: sends a request to the running agent API and
automatically downloads the generated Word document. No manual clicking
through Swagger UI required.

Usage:
    python client.py "Create a project plan for launching a mobile banking app"
"""

import sys
import requests

BASE_URL = "http://127.0.0.1:8000"


def run(request_text: str):
    print(f"\nSending request to agent:\n  \"{request_text}\"\n")

    response = requests.post(f"{BASE_URL}/agent", json={"request": request_text})
    response.raise_for_status()
    data = response.json()

    print(f"Document type : {data['document_type']}")
    print(f"Title         : {data['title']}")
    print(f"\nAssumptions made by the agent:")
    for a in data["assumptions_made"]:
        print(f"  - {a}")

    print(f"\nAgent-generated task list:")
    for task in data["agent_task_list"]:
        print(f"  {task['step']}. {task['section_title']}")

    # --- Automatically download the generated .docx ---
    download_resp = requests.get(f"{BASE_URL}{data['download_url']}")
    download_resp.raise_for_status()

    filename = f"{data['request_id']}.docx"
    with open(filename, "wb") as f:
        f.write(download_resp.content)

    print(f"\nDocument downloaded automatically as: {filename}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python client.py "your request here"')
        sys.exit(1)

    user_request = " ".join(sys.argv[1:])
    run(user_request)
