import hashlib
import json
import subprocess
import sys
import textwrap
from datetime import datetime, timezone


def run(command):
    print(f"Running: {' '.join(command)}")

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print("STDOUT:")
        print(result.stdout)

    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)

    return result


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
                "confidence": "high"
            },
            "contact": {
                "name": "Jane Buyer",
                "id": "003TEST",
                "email": "jane.buyer@acme.example",
                "confidence": "high"
            },
            "lead": None,
            "opportunity": {
                "name": "Acme Initial Eval",
                "id": "006TEST",
                "stage": "S0",
                "is_open": True,
                "confidence": "high"
            }
        },
        "nant_notes": {
            "need": "Prospect wants to improve knowledge discovery across internal tools.",
            "authority": "Jane Buyer is evaluating vendors and will involve IT leadership.",
            "negative_consequences": "Continued manual searching and duplicated work.",
            "timeline": "Initial evaluation this quarter.",
            "next_step": "Send follow-up and schedule technical discovery."
        },
        "proposed_salesforce_changes": [
            {
                "object": "Opportunity",
                "id": "006TEST",
                "fields": {
                    "NANT_Notes__c": "Need: Prospect wants to improve knowledge discovery across internal tools.\nAuthority: Jane Buyer is evaluating vendors and will involve IT leadership.\nNegative consequences: Continued manual searching and duplicated work.\nTimeline: Initial evaluation this quarter.\nNext step: Send follow-up and schedule technical discovery.",
                    "NextStep": "Send follow-up and schedule technical discovery.",
                    "Last_Gong_Call_ID__c": f"test-gong-call-{timestamp}"
                }
            }
        ],
        "duplicate_prevention": {
            "idempotency_key": f"gong:test-gong-call-{timestamp}:sf:006TEST:nant:v1",
            "status": "not_checked_yet"
        },
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    approval_hash = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()

    payload["approval_hash"] = approval_hash

    payload_json = json.dumps(payload, indent=2, sort_keys=True)

    title = f"TEST Approval needed: Acme Corp Gong call {timestamp}"

    body = textwrap.dedent(f"""
    ## Test Approval Request

    This is a fake test approval request. It does not write to Salesforce.

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

    ## Approval

    Approval ID:

    `{approval_id}`

    Approval hash:

    `{approval_hash}`

    To approve, comment this exact line:

    `/approve {approval_hash}`

    ## Machine Payload

    Do not edit this section.

    <details>
    <summary>payload</summary>

    PAYLOAD_JSON_START
    {payload_json}
    PAYLOAD_JSON_END

    </details>
    """)

    issue_result = run(
        ["gh", "issue", "create", "--title", title, "--body", body]
    )

    issue_url = issue_result.stdout.strip().splitlines()[-1]

    print(f"Created test approval issue for {approval_id}")
    print(f"Issue: {issue_url}")
    print(f"Approval hash: {approval_hash}")


if __name__ == "__main__":
    main()
