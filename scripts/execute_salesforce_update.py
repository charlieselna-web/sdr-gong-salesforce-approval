import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


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


def load_approvers():
    path = Path("config/approvers.yml")

    if not path.exists():
        print("Missing config/approvers.yml")
        sys.exit(1)

    approvers = set()

    for line in path.read_text().splitlines():
        line = line.strip()
        match = re.search(r"(?:^-\s*)?github_username\s*:\s*([A-Za-z0-9-]+)", line)

        if match:
            approvers.add(match.group(1).strip().lower())

    if not approvers:
        print("No approvers found in config/approvers.yml")
        sys.exit(1)

    print(f"Loaded approvers: {sorted(approvers)}")
    return approvers


def get_issue(issue_number):
    result = run([
        "gh",
        "issue",
        "view",
        str(issue_number),
        "--json",
        "body,comments,title,state",
    ])

    return json.loads(result.stdout)


def extract_payload_from_issue_body(body):
    match = re.search(
        r"PAYLOAD_JSON_START\s*(.*?)\s*PAYLOAD_JSON_END",
        body,
        re.DOTALL,
    )

    if not match:
        print("Could not find machine payload in issue body.")
        sys.exit(1)

    payload_text = match.group(1).strip()

    try:
        return json.loads(payload_text)
    except json.JSONDecodeError as error:
        print("Could not parse payload JSON from issue body.")
        print(error)
        sys.exit(1)


def already_executed(comments):
    for comment in comments:
        body = comment.get("body", "")
        if "✅ Test executor completed" in body:
            return True

    return False


def find_valid_approval_comment(comments, approval_hash, approvers):
    for comment in comments:
        body = comment.get("body", "").strip()
        author = comment.get("author", {}).get("login", "").lower()

        if not body.startswith("/approve"):
            continue

        parts = body.split()

        if len(parts) < 2:
            continue

        submitted_hash = parts[1].strip()

        if submitted_hash == approval_hash and author in approvers:
            return {
                "approved_by": author,
                "approved_at": comment.get("createdAt"),
                "comment_body": body,
            }

    return None


def comment_on_issue(issue_number, body):
    run([
        "gh",
        "issue",
        "comment",
        str(issue_number),
        "--body",
        body,
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approval-id", required=True)
    parser.add_argument("--issue-number", required=True)

    args = parser.parse_args()

    issue = get_issue(args.issue_number)
    body = issue["body"]
    comments = issue.get("comments", [])

    payload = extract_payload_from_issue_body(body)

    if payload.get("approval_id") != args.approval_id:
        print("Approval ID mismatch.")
        print(f"Workflow approval ID: {args.approval_id}")
        print(f"Payload approval ID:  {payload.get('approval_id')}")
        sys.exit(1)

    approval_hash = payload.get("approval_hash")

    if not approval_hash:
        print("Payload is missing approval_hash.")
        sys.exit(1)

    if already_executed(comments):
        print("Duplicate prevented: this issue already has a completed executor comment.")

        comment_on_issue(
            args.issue_number,
            "⚠️ Duplicate prevented: this approval was already executed in test mode. No Salesforce update was made.",
        )

        return

    approvers = load_approvers()

    approval = find_valid_approval_comment(
        comments=comments,
        approval_hash=approval_hash,
        approvers=approvers,
    )

    if not approval:
        print("No valid approval comment found.")
        print("Executor will not proceed.")
        sys.exit(1)

    print("Valid approval found.")
    print(f"Approved by: {approval['approved_by']}")

    print("Loaded payload:")
    print(json.dumps(payload, indent=2, sort_keys=True))

    print("TEST MODE: Salesforce update would happen here.")
    print("No Salesforce update was made.")

    executed_at = datetime.now(timezone.utc).isoformat()

    comment_on_issue(
        args.issue_number,
        f"""✅ Test executor completed.

Approval ID: `{args.approval_id}`

Approved by: `{approval["approved_by"]}`

Executed at: `{executed_at}`

Result: approval was verified, the machine payload was loaded from the Issue, duplicate protection was checked, and the executor completed in test mode.

No Salesforce update was made yet.
""",
    )

    print("Execution complete.")


if __name__ == "__main__":
    main()
