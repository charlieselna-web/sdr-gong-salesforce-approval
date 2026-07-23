import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


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


def get_issue_body(issue_number):
    result = subprocess.run(
        ["gh", "issue", "view", str(issue_number), "--json", "body"],
        check=True,
        text=True,
        capture_output=True,
    )

    return json.loads(result.stdout)["body"]


def extract_backtick_value(label, body):
    pattern = rf"{re.escape(label)}\s*:\s*(?:\r?\n\s*)*`([^`]+)`"
    match = re.search(pattern, body, re.IGNORECASE)

    if match:
        return match.group(1).strip()

    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-number", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--comment", required=True)

    args = parser.parse_args()

    approvers = load_approvers()
    actor = args.actor.strip().lower()

    if actor not in approvers:
        print(f"Actor {args.actor} is not an approved approver.")
        print(f"Allowed approvers: {sorted(approvers)}")
        sys.exit(1)

    comment = args.comment.strip()

    if not comment.startswith("/approve"):
        print("Comment is not an approval command.")
        sys.exit(1)

    parts = comment.split()

    if len(parts) < 2:
        print("Approval command must include hash, like: /approve sha256:abc123")
        sys.exit(1)

    submitted_hash = parts[1].strip()

    issue_body = get_issue_body(args.issue_number)

    approval_id = extract_backtick_value("Approval ID", issue_body)
    expected_hash = extract_backtick_value("Approval hash", issue_body)

    if not approval_id:
        print("Could not find Approval ID in issue body.")
        sys.exit(1)

    if not expected_hash:
        print("Could not find Approval hash in issue body.")
        sys.exit(1)

    if submitted_hash != expected_hash:
        print("Submitted approval hash does not match expected hash.")
        print(f"Submitted: {submitted_hash}")
        print(f"Expected:  {expected_hash}")
        sys.exit(1)

    Path("approval_id.txt").write_text(approval_id)

    print("Approval validated.")
    print(f"Approver: {args.actor}")
    print(f"Approval ID: {approval_id}")


if __name__ == "__main__":
    main()
