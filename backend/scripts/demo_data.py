"""Run from root with uv run --project backend python backend/scripts/demo_data.py seed."""

import argparse
import json

from bizmate.config import Settings
from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import MERCHANTS, demo_context
from bizmate.services.mock_models import FailureControl
from bizmate.services.mock_store import SQLiteMockStore
from bizmate.services.mocks import MockServices


def main():
    parser = argparse.ArgumentParser(description="Manage merchant-scoped synthetic BM-04 data")
    parser.add_argument("command", choices=["seed", "reset", "clock", "advance", "fail"])
    parser.add_argument("--merchant", choices=list(MERCHANTS))
    parser.add_argument("--seconds", type=int, default=86400)
    parser.add_argument("--operation", default="get_settlement_report")
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()
    settings = Settings()
    services = MockServices(
        SQLiteMockStore(settings.database_file),
        SQLiteTaskRepository(settings.database_file),
        controls_enabled=settings.demo_controls_enabled,
    )
    context = demo_context(args.merchant or settings.demo_merchant_id)
    if args.command == "reset":
        services.reset(context)
    elif args.command == "advance":
        services.advance(context, args.seconds)
    elif args.command == "fail":
        services.inject_failure(context, FailureControl(operation=args.operation, count=args.count))
    print(
        json.dumps(
            {
                "merchant_id": context.merchant_id,
                "command": args.command,
                "current_time": services.clock(context).isoformat(),
                "simulated": True,
            }
        )
    )


if __name__ == "__main__":
    main()
