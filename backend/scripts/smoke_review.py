"""Exercise BM-14 campaign review or BM-15 human handoff against a local backend."""

import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--workflow", choices=["campaign", "handoff"], default="campaign")
    parser.add_argument("--edit-message", help="Edit the campaign before approving it")
    parser.add_argument("--approve", action="store_true", help="Approve this synthetic action")
    args = parser.parse_args()
    if args.edit_message and args.workflow != "campaign":
        parser.error("--edit-message applies to campaign review")

    def call(method, route, data=None):
        request = Request(
            args.base_url.rstrip("/") + route,
            method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as error:
            raise SystemExit(error.read().decode()) from None

    message = (
        'Send inactive customers message="Come back for 10% off"'
        if args.workflow == "campaign"
        else "Change my registered bank account"
    )
    task = call("POST", "/api/v1/tasks", {"message": message})
    root = "/api/v1/tasks/" + task["task_id"]
    if args.edit_message:
        task = call(
            "PATCH",
            root + "/campaign",
            {"expected_revision": task["revision"], "message": args.edit_message},
        )
    print(task["next_action"])
    if args.approve and task["approvals"]:
        approval = task["approvals"][-1]
        call(
            "POST",
            root + "/approvals/" + approval["approval_id"],
            {"decision": "approve", "input_hash": approval["input_hash"]},
        )
        task = call("POST", root + "/resume")
    review = call("GET", root + "/" + args.workflow)
    print(
        json.dumps(
            {"status": task["status"], "next_action": task["next_action"], "review": review},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
