"""Run a synthetic BM-07/08 API flow against a running local backend."""

import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--workflow", choices=["settlement", "campaign"], default="settlement")
    parser.add_argument(
        "--approve", action="store_true", help="Approve this exact synthetic action"
    )
    parser.add_argument("--report-timeouts", type=int, default=0)
    parser.add_argument("--write-timeout", action="store_true")
    args = parser.parse_args()

    def post(route, data=None):
        request = Request(
            args.base_url.rstrip("/") + route,
            method="POST",
            data=json.dumps(data).encode() if data is not None else b"",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as error:
            raise SystemExit(error.read().decode()) from None

    if args.report_timeouts:
        post(
            "/api/v1/demo/failures",
            {"operation": "get_settlement_report", "count": args.report_timeouts},
        )
    if args.write_timeout:
        post(
            "/api/v1/demo/failures",
            {
                "operation": "ticket_after_write"
                if args.workflow == "settlement"
                else "campaign_after_write",
                "count": 1,
            },
        )
    message = (
        "Why is my settlement short?"
        if args.workflow == "settlement"
        else 'Send inactive customers message="Come back for 10% off"'
    )
    task = post("/api/v1/tasks", {"message": message})
    route = "/api/v1/tasks/" + task["task_id"]
    if task["approvals"]:
        approval = task["approvals"][-1]
        print(task["next_action"])
        if args.approve:
            post(
                route + "/approvals/" + approval["approval_id"],
                {"decision": "approve", "input_hash": approval["input_hash"]},
            )
            task = post(route + "/resume")
    print(
        json.dumps(
            {
                "task_id": task["task_id"],
                "status": task["status"],
                "next_action": task["next_action"],
                "checkpoint_id": task["checkpoint_id"],
                "receipts": task["receipts"],
                "verifications": task["verifications"],
                "events_url": args.base_url.rstrip("/") + route + "/events",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
