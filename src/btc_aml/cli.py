import argparse

from .analytics.coinjoin import detect_and_alert_coinjoins
from .analytics.entity_resolution import run_global_entity_resolution
from .analytics.ofac import (
    load_ofac_csv,
    screen_ofac_for_alert_addresses,
    screen_ofac_for_top_addresses,
)
from .analytics.peel_chain import detect_and_alert_peel_chains
from .analytics.risk_score import compute_risk_scores
from .analytics.smurfing import detect_and_alert_smurfing_cycles
from .logging_config import setup_logging
from .maintenance import (
    get_data_quality_summary,
    recompute_address_metrics,
    reset_database,
)
from .monitor import run_monitor
from .neo4j_client import session
from .pipeline import (
    export_flows_to_csv,
    ingest_address,
    ingest_blocks,
    ingest_latest,
    ingest_tx,
    run_all,
    run_analytics,
)
from .schema import ensure_schema
from .state import get_pipeline_status, set_last_block_height


def main() -> None:
    setup_logging()

    parser = argparse.ArgumentParser(description="Bitcoin AML Graph CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Core commands
    subparsers.add_parser("schema", help="Create schema constraints and indexes")

    p_ingest_blocks = subparsers.add_parser("ingest-blocks")
    p_ingest_blocks.add_argument("--start", type=int, required=True)
    p_ingest_blocks.add_argument("--end", type=int, required=True)
    p_ingest_blocks.add_argument(
        "--allow-historical",
        action="store_true",
        help="Allow ingesting blocks at or below the current checkpoint.",
    )

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

    # Analytics commands
    p_coinjoin = subparsers.add_parser("detect-coinjoin")
    p_coinjoin.add_argument("--min-participants", type=int, default=50)
    p_coinjoin.add_argument("--max-asymmetry", type=float, default=0.20)
    p_coinjoin.add_argument("--anon-ratio", type=float, default=0.35)
    p_coinjoin.add_argument("--bucket-sats", type=int, default=10_000)

    subparsers.add_parser("resolve-entities")

    p_peel = subparsers.add_parser("detect-peel")
    p_peel.add_argument("--min-start-btc", type=float, default=1.0)
    p_peel.add_argument("--min-hops", type=int, default=4)
    p_peel.add_argument("--max-hops", type=int, default=14)
    p_peel.add_argument("--min-peel", type=float, default=0.05)

    p_smurf = subparsers.add_parser("detect-smurf")
    p_smurf.add_argument("--out-degree", type=int, default=50)
    p_smurf.add_argument("--in-degree", type=int, default=50)
    p_smurf.add_argument("--required-paths", type=int, default=3)
    p_smurf.add_argument("--max-depth", type=int, default=6)
    p_smurf.add_argument("--max-pairs", type=int, default=200)

    p_ofac_load = subparsers.add_parser("load-ofac")
    p_ofac_load.add_argument("--csv", default="data/ofac/sdn_advanced.csv")

    p_ofac_screen = subparsers.add_parser("screen-ofac")
    p_ofac_screen.add_argument("--limit", type=int, default=2000)
    p_ofac_screen.add_argument("--alert-addresses", action="store_true")

    subparsers.add_parser("compute-risk")

    p_analytics = subparsers.add_parser("run-analytics")
    p_analytics.add_argument("--ofac-csv", default=None)
    p_analytics.add_argument("--no-peel", action="store_true")
    p_analytics.add_argument("--no-smurf", action="store_true")
    p_analytics.add_argument("--screen-limit", type=int, default=2000)
    p_analytics.add_argument("--max-smurf-pairs", type=int, default=200)

    # Monitor / operations commands
    p_monitor = subparsers.add_parser("monitor")
    p_monitor.add_argument(
        "--interval",
        type=int,
        default=600,
        help="Seconds between monitor iterations.",
    )
    p_monitor.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of new blocks to fetch per iteration.",
    )
    p_monitor.add_argument(
        "--analytics-every",
        type=int,
        default=100,
        help="Rerun analytics every N newly ingested blocks. Use 0 to disable.",
    )
    p_monitor.add_argument(
        "--max-iterations",
        type=int,
        default=0,
        help="Stop after N iterations. Use 0 to run forever.",
    )

    p_set_last = subparsers.add_parser("set-last-height")
    p_set_last.add_argument("--height", type=int, required=True)
    p_set_last.add_argument(
        "--force",
        action="store_true",
        help="Allow decreasing the checkpoint. Use carefully.",
    )

    args = parser.parse_args()

    # Core commands
    if args.command == "schema":
        ensure_schema()

    elif args.command == "ingest-blocks":
        ingest_blocks(
            start_height=args.start,
            end_height=args.end,
            allow_historical=args.allow_historical,
        )

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

    # Analytics commands
    elif args.command == "detect-coinjoin":
        detect_and_alert_coinjoins(
            min_participants=args.min_participants,
            max_asymmetry_ratio=args.max_asymmetry,
            anon_set_ratio=args.anon_ratio,
            value_bucket_satoshi=args.bucket_sats,
        )

    elif args.command == "resolve-entities":
        run_global_entity_resolution()

    elif args.command == "detect-peel":
        detect_and_alert_peel_chains(
            min_starting_btc=args.min_start_btc,
            min_hops=args.min_hops,
            max_hops=args.max_hops,
            min_peel_amount=args.min_peel,
        )

    elif args.command == "detect-smurf":
        detect_and_alert_smurfing_cycles(
            out_degree_thresh=args.out_degree,
            in_degree_thresh=args.in_degree,
            required_paths=args.required_paths,
            max_smurf_depth=args.max_depth,
            max_pairs=args.max_pairs,
        )

    elif args.command == "load-ofac":
        load_ofac_csv(args.csv)

    elif args.command == "screen-ofac":
        if args.alert_addresses:
            screen_ofac_for_alert_addresses()
        else:
            screen_ofac_for_top_addresses(limit=args.limit)

    elif args.command == "compute-risk":
        compute_risk_scores()

    elif args.command == "run-analytics":
        run_analytics(
            ofac_csv=args.ofac_csv,
            run_peel=not args.no_peel,
            run_smurf=not args.no_smurf,
            screen_ofac_limit=args.screen_limit,
            max_smurf_pairs=args.max_smurf_pairs,
        )

    # Monitor / operations commands
    elif args.command == "monitor":
        run_monitor(
            interval_seconds=args.interval,
            limit=args.limit,
            analytics_every=args.analytics_every,
            max_iterations=args.max_iterations,
        )

    elif args.command == "set-last-height":
        set_last_block_height(args.height, force=args.force)


if __name__ == "__main__":
    main()
