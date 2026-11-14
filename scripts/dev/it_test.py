"""Drive the VS Code IT on the test instance through the Galaxy API.

  python3 it_test.py start   -> launches the IT in a fresh history, waits until the
                               entry point is active, prints ids and the target URL
  python3 it_test.py stop <entry point id>  -> stops the IT
  python3 it_test.py history <history id>   -> lists history contents

GALAXY and KEY come from the environment. TOOL_ID selects the tool to launch and
defaults to interactive_tool_vscode, the id of a copy installed from this
repository (install.sh or the Helm overlay). A ToolShed install has a long id:

  TOOL_ID=toolshed    toolshed.g2.bx.psu.edu/repos/ksuderman/interactive_tool_vscode/interactive_tool_vscode/<version>
  TOOL_ID=testtoolshed    the same on testtoolshed.g2.bx.psu.edu
  TOOL_ID=<any id>    used as given

For the two shorthands the installed version is looked up on the Galaxy.
"""
import os
import sys
import time

import requests

BASE = os.environ["GALAXY"].rstrip("/")
H = {"x-api-key": os.environ["KEY"]}


SHEDS = {"toolshed": "toolshed.g2.bx.psu.edu", "testtoolshed": "testtoolshed.g2.bx.psu.edu"}


def tool_id():
    wanted = os.environ.get("TOOL_ID", "interactive_tool_vscode")
    if wanted not in SHEDS:
        return wanted
    prefix = f"{SHEDS[wanted]}/repos/ksuderman/interactive_tool_vscode/interactive_tool_vscode/"
    # in_panel=false returns a flat list of every loaded tool.
    found = sorted(t["id"] for t in api("get", "tools", params={"in_panel": "false"}) if t["id"].startswith(prefix))
    if not found:
        sys.exit(f"no tool with id {prefix}<version> is installed on {BASE}")
    return found[-1]


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
    tid = tool_id()
    print("tool:", tid)
    job = api("post", "tools", json={"tool_id": tid, "history_id": hist["id"], "inputs": {
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
