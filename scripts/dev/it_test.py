"""Drive the VS Code IT on the test instance through the Galaxy API.

  python3 it_test.py start   -> launches the IT in a fresh history, waits until the
                               entry point is active, prints ids and the target URL
  python3 it_test.py stop <entry point id>  -> stops the IT
  python3 it_test.py history <history id>   -> lists history contents

GALAXY and KEY come from the environment.
"""
import os
import sys
import time

import requests

BASE = os.environ["GALAXY"].rstrip("/")
H = {"x-api-key": os.environ["KEY"]}


def api(method, path, **kw):
    r = requests.request(method, f"{BASE}/api/{path}", headers=H, timeout=60, **kw)
    r.raise_for_status()
    return r.json()


def start():
    hist = api("post", "histories", json={"name": f"vscode-it test {time.strftime('%H:%M:%S')}"})
    print("history:", hist["id"])
    # Seed a dataset so galaxy-get has something to fetch.
    up = api("post", "tools/fetch", json={
        "history_id": hist["id"],
        "targets": [{"destination": {"type": "hdas"}, "elements": [
            {"src": "pasted", "paste_content": "chr1\t10\t20\nchr2\t30\t40\n", "name": "regions.bed", "ext": "bed"}]}]})
    print("seeded:", [o["name"] for o in up["outputs"]])
    job = api("post", "tools", json={"tool_id": "interactive_tool_vscode", "history_id": hist["id"], "inputs": {
        "inputs": {"batch": False, "values": [{"src": "hda", "id": up["outputs"][0]["id"]}]}}})
    job_id = job["jobs"][0]["id"]
    print("job:", job_id)
    for _ in range(90):
        eps = [e for e in api("get", "entry_points", params={"running": "true"}) if e["job_id"] == job_id]
        if eps and eps[0]["active"]:
            print("entry point:", eps[0]["id"])
            print("target:", eps[0]["target"])
            return
        state = api("get", f"jobs/{job_id}")["state"]
        if state in ("error", "failed", "deleted"):
            sys.exit(f"job ended in state {state}")
        time.sleep(10)
    sys.exit("timed out waiting for the entry point")


def stop(ep_id):
    r = requests.delete(f"{BASE}/api/entry_points/{ep_id}", headers=H, timeout=60)
    print("stop:", r.status_code, r.text[:200])


def history(hist_id):
    for item in api("get", f"histories/{hist_id}/contents"):
        print(f"{item['hid']:>3} {item['history_content_type']:<19} {item['state'] if 'state' in item else item.get('populated_state')}  {item['name']}")


if __name__ == "__main__":
    {"start": start, "stop": stop, "history": history}[sys.argv[1]](*sys.argv[2:])
