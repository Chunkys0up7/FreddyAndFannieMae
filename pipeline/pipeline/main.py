"""Pipeline CLI entry point."""
from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .ingest.bulletin_monitor import monitor_bulletins
from .ingest.fannie_html import ingest_fannie_guide
from .ingest.freddie_pdf import ingest_freddie_guide
from .manifest.run_manifest import RunManifest
from .store.chroma_client import ChromaVectorStore
from .store.state_store import StateStore


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )


def _build_args() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pipeline", description="GSE Copilot ingestion pipeline")
    p.add_argument("--fannie", action="store_true", help="Run Fannie Mae HTML ingestion")
    p.add_argument("--freddie", action="store_true", help="Run Freddie Mac PDF ingestion")
    p.add_argument("--bulletins", action="store_true", help="Run bulletin detection")
    p.add_argument("--all", action="store_true", help="Run all tracks")
    p.add_argument("--dry-run", action="store_true", help="Skip vector store writes")
    p.add_argument("--schedule", action="store_true", help="Run on a recurring schedule")
    return p


def _run_once(args: argparse.Namespace) -> RunManifest:
    cfg = load_config()
    store = ChromaVectorStore(cfg.chroma, cfg.embedding)
    state = StateStore(cfg.sqlite_path)
    manifest = RunManifest()

    do_fannie = args.fannie or args.all
    do_freddie = args.freddie or args.all
    do_bulletins = args.bulletins or args.all

    if do_fannie:
        try:
            manifest.add_result("fannie", ingest_fannie_guide(cfg, store, state, args.dry_run))
        except Exception as exc:  # pragma: no cover
            logging.exception("Fannie track failed")
            manifest.add_error("fannie", exc)

    if do_freddie:
        try:
            manifest.add_result("freddie", ingest_freddie_guide(cfg, store, state, args.dry_run))
        except Exception as exc:  # pragma: no cover
            logging.exception("Freddie track failed")
            manifest.add_error("freddie", exc)

    if do_bulletins:
        try:
            manifest.add_result("bulletins", monitor_bulletins(cfg, store, state, args.dry_run))
        except Exception as exc:  # pragma: no cover
            logging.exception("Bulletin track failed")
            manifest.add_error("bulletins", exc)

    out = manifest.finalize(cfg.manifest_dir)
    logging.info("Run manifest written → %s", out)
    return manifest


def _run_scheduler(args: argparse.Namespace) -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler

    cfg = load_config()
    scheduler = BlockingScheduler()

    bulletin_args = argparse.Namespace(
        fannie=False, freddie=False, bulletins=True, all=False, dry_run=args.dry_run, schedule=False
    )
    guide_args = argparse.Namespace(
        fannie=True, freddie=True, bulletins=False, all=False, dry_run=args.dry_run, schedule=False
    )

    scheduler.add_job(
        _run_once,
        trigger="interval",
        hours=cfg.schedule.bulletin_poll_hours,
        args=[bulletin_args],
        id="bulletin-monitor",
        next_run_time=None,
    )
    scheduler.add_job(
        _run_once,
        trigger="interval",
        days=cfg.schedule.guide_refresh_days,
        args=[guide_args],
        id="guide-refresh",
        next_run_time=None,
    )
    logging.info(
        "Scheduler started — bulletins every %dh, guides every %dd",
        cfg.schedule.bulletin_poll_hours,
        cfg.schedule.guide_refresh_days,
    )
    scheduler.start()


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    parser = _build_args()
    args = parser.parse_args(argv)
    if not (args.fannie or args.freddie or args.bulletins or args.all or args.schedule):
        parser.print_help()
        return 1
    if args.schedule:
        _run_scheduler(args)
        return 0
    _run_once(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
