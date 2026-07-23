import hashlib
import json
import subprocess
import textwrap
from datetime import datetime, timezone
from pathlib import Path


def run(command):
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
    )


def git_commit_and_push(path, approval_id):
    run(["git", "config", "user.name", "github-actions[bot]"])
    run([
        "git",
        "config",
        "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
    ])

    run(["git", "add", str(path)])

    commit = subprocess.run(
        ["git", "commit", "-m", f"Add approval payload {approval_id}"],
        text=True,
        capture_output=True,
    )

    if commit.returncode != 0:
        output = commit.stdout + commit.stderr
        if "nothing to commit" in output:
            print("Nothing to commit.")
            return
        print(output)
        raise RuntimeError("git commit failed")

    push = run(["git", "push"])
    print(push.stdout)


def main():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    approval_id = f"gong-test-{timestamp}"

    payload = {
        "approval_id": approval_id,
        "status": "pending_approval",
        "gong_call_id": f"test-gong-call-{timestamp}",
        "sdr": "Charlie Selna",
        "company": "Acme Corp",
        "salesforce_match": {
            "account": {
                "name": "Acme Corp",
                "id": "001TEST",
                "confidence": "high",
            },
            "contact": {
                "name": "Jane Buyer",
                "id": "003TEST",
                "email": "jane.buyer@acme.example",
                "confidence": "high",
            },
            "lead": None,
            "opportunity": {
                "name": "Acme Initial Eval",
                "id": "006TEST",
                "stage": "S0",
                "is_open": True,
                "confidence": "high",
            },
        },
        "nant_notes": {
            "need": "Prospect wants to improve knowledge discovery across internal tools.",
            "authority": "Jane Buyer is evaluating vendors and will involve IT leadership.",
            "negative_consequences": "Continued manual searching and duplicated work.",
            "timeline": "Initial evaluation this quarter.",
            "next_step": "Send follow-up and schedule technical discovery.",
        },
        "proposed_salesforce_changes": [
            {
                "object": "Opportunity",
                "id": "006TEST",
                "fields": {
                    "NANT_Notes__c": (
                        "Need: Prospect wants to improve knowledge discovery across internal tools.\n"
                        "Authority: Jane Buyer is evaluating vendors and will involve IT leadership.\n"
                        "Negative consequences: Continued manual searching and duplicated work.\n"
                        "Timeline: Initial evaluation this quarter.\n"
                        "Next step: Send follow-up and schedule technical discovery."
                    ),
                    "NextStep": "Send follow-up and schedule technical discovery.",
                    "Last_Gong_Call_ID__c": f"test-gong-call-{timestamp}",
                },
            }
        ],
        "duplicate_prevention": {
            "idempotency_key": f"gong:test-gong-call-{timestamp}:sf:006TEST:nant:v1",
            "status": "not_checked_yet",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    approval_hash = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()

    payload["approval_hash"] = approval_hash

    title = f"TEST Approval needed: Acme Corp Gong call {timestamp}"

    body = textwrap.dedent(f"""
    ## Test Approval Request

    This is a fake test approval request. It does **not** write to Salesforce.

    ## Gong Call

    - Gong Call ID: `{payload["gong_call_id"]}`
    - SDR: {payload["sdr"]}
    - Company: {payload["company"]}

    ## Matched Salesforce Records

    - Account: {payload["salesforce_match"]["account"]["name"]} / `{payload["salesforce_match"]["account"]["id"]}`
    - Contact: {payload["salesforce_match"]["contact"]["name"]} / `{payload["salesforce_match"]["contact"]["id"]}`
    - Lead: {payload["salesforce_match"]["lead"]}
    - Open S0 Opportunity: {payload["salesforce_match"]["opportunity"]["name"]} / `{payload["salesforce_match"]["opportunity"]["id"]}`

    ## Proposed NANT Notes

    **Need:** {payload["nant_notes"]["need"]}

    **Authority:** {payload["nant_notes"]["authority"]}

    **Negative consequences:** {payload["nant_notes"]["negative_consequences"]}

    **Timeline:** {payload["nant_notes"]["timeline"]}

    **Next step:** {payload["nant_notes"]["next_step"]}

    ## Proposed Salesforce Change

    Object: `Opportunity`

    ID: `{payload["salesforce_match"]["opportunity"]["id"]}`

    Field: `NANT_Notes__c`

## Approval

Approval ID:

`{approval_id}`

Approval hash:

`{approval_hash}`

To approve, comment this exact line:

`/approve {approval_hash}`
""")

issue_result = run(
    ["gh", "issue", "create", "--title", title, "--body", body]
)

issue_url = issue_result.stdout.strip().splitlines()[-1]
issue_number = issue_url.rstrip("/").split("/")[-1]

payload["github_issue"] = {
    "number": issue_number,
    "url": issue_url,
}

payload_path = Path("data") / "approvals" / f"{approval_id}.json"
payload_path.parent.mkdir(parents=True, exist_ok=True)
payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

git_commit_and_push(payload_path, approval_id)

print(f"Created test approval issue for {approval_id}")
print(f"Issue: {issue_url}")
print(f"Payload: {payload_path}")
print(f"Approval hash: {approval_hash}")


if __name__ == "__main__":
main()
