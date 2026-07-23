import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(command):
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
    )


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

    return approvers


def get_issue_comments(issue_number):
    result = run([
        "gh",
        "issue",
        "view",
        str(issue_number),
        "--json",
        "comments",
    ])

    data = json.loads(result.stdout)
    return data.get("comments", [])


def find_valid_approval_comment(issue_number, approval_hash, approvers):
    comments = get_issue_comments(issue_number)

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
        ["git", "commit", "-m", f"Mark approval executed {approval_id}"],
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
    args = parser.parse_args()

    approval_id = args.approval_id
    payload_path = Path("data") / "approvals" / f"{approval_id}.json"

    if not payload_path.exists():
        print(f"Missing approval payload: {payload_path}")
        sys.exit(1)

    payload = json.loads(payload_path.read_text())

    issue_number = payload.get("github_issue", {}).get("number")
    approval_hash = payload.get("approval_hash")

    if not issue_number:
        print("Payload is missing github_issue.number")
        sys.exit(1)

    if not approval_hash:
        print("Payload is missing approval_hash")
        sys.exit(1)

    if payload.get("status") in {"executed_test", "executed"}:
        print("Duplicate prevented: this approval was already executed.")

        comment_on_issue(
            issue_number,
            "⚠️ Duplicate prevented: this approval payload was already executed. "
            "No Salesforce update was made.",
        )

        return

    approvers = load_approvers()
    approval = find_valid_approval_comment(issue_number, approval_hash, approvers)

    if not approval:
        print("No valid approval comment found.")
        print("Executor will not proceed.")
        sys.exit(1)

    print("Valid approval found.")
    print(f"Approved by: {approval['approved_by']}")

    # Test-mode execution only.
    # This is where the real Salesforce update will go later.
    print("TEST MODE: Salesforce update would happen here.")
    print("No Salesforce update was made.")

    payload["status"] = "executed_test"
    payload["approval"] = {
        "approved_by": approval["approved_by"],
        "approved_at": approval["approved_at"],
        "approval_hash": approval_hash,
    }
    payload["execution"] = {
        "mode": "test",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "salesforce_update_performed": False,
        "message": "Approval handoff verified. Salesforce update was not performed.",
    }
    payload["duplicate_prevention"]["status"] = "simulated_passed"

    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    git_commit_and_push(payload_path, approval_id)

    comment_on_issue(
        issue_number,
        f"""✅ Test executor completed.

Approval ID: `{approval_id}`

Approved by: `{approval["approved_by"]}`

Result: approval was verified, payload was loaded, duplicate guard was checked, and the executor completed in test mode.

No Salesforce update was made yet.
""",
    )

    print("Execution complete.")


if __name__ == "__main__":
    main()
