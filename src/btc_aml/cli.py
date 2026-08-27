import argparse

from .logging_config import setup_logging
from .maintenance import get_data_quality_summary, recompute_address_metrics, reset_database
from .neo4j_client import session
from .pipeline import (
    export_flows_to_csv,
    ingest_address,
    ingest_blocks,
    ingest_latest,
    ingest_tx,
    run_all,
)
from .schema import ensure_schema
from .state import get_pipeline_status


def main() -> None:
    setup_logging()

    parser = argparse.ArgumentParser(description="Bitcoin AML Graph CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("schema", help="Create schema constraints and indexes")

    p_ingest_blocks = subparsers.add_parser("ingest-blocks")
    p_ingest_blocks.add_argument("--start", type=int, required=True)
    p_ingest_blocks.add_argument("--end", type=int, required=True)

    p_ingest_latest = subparsers.add_parser("ingest-latest")
    p_ingest_latest.add_argument("--limit", type=int, default=10)

    p_ingest_tx = subparsers.add_parser("ingest-tx")
    p_ingest_tx.add_argument("--tx", required=True)

    p_ingest_address = subparsers.add_parser("ingest-address")
    p_ingest_address.add_argument("--address", required=True)
    p_ingest_address.add_argument("--limit", type=int, default=50)

    subparsers.add_parser("status", help="Show pipeline status")
    subparsers.add_parser("recompute", help="Recompute address metrics")

    p_export = subparsers.add_parser("export")
    p_export.add_argument("--path", default="./data/processed/flows.csv")

    p_reset = subparsers.add_parser("reset")
    p_reset.add_argument("--confirm", action="store_true")

    args = parser.parse_args()

    if args.command == "schema":
        ensure_schema()

    elif args.command == "ingest-blocks":
        ingest_blocks(start_height=args.start, end_height=args.end)

    elif args.command == "ingest-latest":
        ingest_latest(limit=args.limit)

    elif args.command == "ingest-tx":
        ingest_tx(args.tx)

    elif args.command == "ingest-address":
        ingest_address(args.address, limit=args.limit)

    elif args.command == "status":
        print(get_pipeline_status())
        print(get_data_quality_summary())

    elif args.command == "recompute":
        recompute_address_metrics()

    elif args.command == "export":
        export_flows_to_csv(args.path)

    elif args.command == "reset":
        with session() as s:
            reset_database(session=s, confirm=args.confirm)


if __name__ == "__main__":
    main()
