"""
run_demo.py
-----------
Convenience script for local testing: starts the FastAPI server in the
background, waits for it to be ready, sends a test request, prints the
result, then shuts the server down. Only needs ONE terminal.

NOTE: The actual assignment still requires main.py to run as a real,
independently-running API (that's part of what's being graded - API
design). For your video demo, run uvicorn and client.py in two separate
terminals as usual, so it's clearly visible as a real client/server
setup. Use THIS script only for quick personal testing/iteration.

Usage:
    python run_demo.py "your request here"
"""

import sys
import time
import subprocess
import requests

BASE_URL = "http://127.0.0.1:8000"


def wait_for_server(timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(BASE_URL, timeout=1)
            if r.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)
    return False


def main():
    if len(sys.argv) < 2:
        print('Usage: python run_demo.py "your request here"')
        sys.exit(1)

    user_request = " ".join(sys.argv[1:])

    print("Starting server in the background...")
    server_process = subprocess.Popen(
        ["uvicorn", "main:app"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        print("Waiting for server to be ready...")
        if not wait_for_server():
            print("Server did not start in time. Check for errors by running "
                  "'uvicorn main:app --reload' manually.")
            return

        print(f"\nSending request:\n  \"{user_request}\"\n")
        response = requests.post(f"{BASE_URL}/agent", json={"request": user_request})
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

        download_resp = requests.get(f"{BASE_URL}{data['download_url']}")
        download_resp.raise_for_status()
        filename = f"{data['request_id']}.docx"
        with open(filename, "wb") as f:
            f.write(download_resp.content)

        print(f"\nDocument downloaded automatically as: {filename}\n")

    finally:
        print("Shutting down server...")
        server_process.terminate()
        server_process.wait()


if __name__ == "__main__":
    main()
