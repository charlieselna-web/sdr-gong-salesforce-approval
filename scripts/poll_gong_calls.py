import hashlib
import json
import subprocess
import textwrap
from datetime import datetime, timezone


def main():
    approval_id = "gong-test-001"

    payload = {
        "approval_id": approval_id,
        "status": "pending_approval",
        "gong_call_id": "test-gong-call-001",
        "sdr": "Charlie Selna",
        "company": "Acme Corp",
        "salesforce_match": {
            "account": "Acme Corp / 001TEST",
            "contact": "Jane Buyer / 003TEST",
            "lead": None,
            "opportunity": "Acme Initial Eval / 006TEST",
        },
        "nant_notes": {
            "need": "Prospect wants to improve knowledge discovery across internal tools.",
            "authority": "Jane Buyer is evaluating vendors and will involve IT leadership.",
            "negative_consequences": "Continued manual searching and duplicated work.",
            "timeline": "Initial evaluation this quarter.",
            "next_step": "Send follow-up and schedule technical discovery.",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    approval_hash = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()

    title = "TEST Approval needed: Acme Corp Gong call"

    body = textwrap.dedent(f"""
    ## Test Approval Request

    This is a fake test approval request. It does **not** write to Salesforce.

    ## Gong Call

    - Gong Call ID: `{payload["gong_call_id"]}`
    - SDR: {payload["sdr"]}
    - Company: {payload["company"]}

    ## Matched Salesforce Records

    - Account: {payload["salesforce_match"]["account"]}
    - Contact: {payload["salesforce_match"]["contact"]}
    - Lead: {payload["salesforce_match"]["lead"]}
    - Open S0 Opportunity: {payload["salesforce_match"]["opportunity"]}

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

    To approve later, you will comment:

    `/approve {approval_hash}`
    """)

    subprocess.run(
        ["gh", "issue", "create", "--title", title, "--body", body],
        check=True,
    )

    print(f"Created test approval issue for {approval_id}")


if __name__ == "__main__":
    main()
