"""Command-line interface for Promo Finder.

Entry point: ``python -m promo_finder run --input <dir> [--config <yaml>]``
and ``python -m promo_finder inspect --input <dir>``.
"""

from __future__ import annotations

import argparse
import os
import sys
import dotenv
dotenv.load_dotenv()
from typing import Optional, Sequence

from promo_finder.config import load_config
from promo_finder.ingestion.loader import load_episodes
from promo_finder.ingestion.parsers.registry import build_default_registry
from promo_finder.ingestion.validators import validate_episode
from promo_finder.logging_setup import get_logger, setup_logging
from promo_finder.pipeline import run as run_pipeline
from promo_finder.preprocess.normalizer import normalise

logger = get_logger("promo_finder.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promo_finder",
        description="Find the best promo clips in screenplay transcripts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the promo discovery pipeline.")
    run_p.add_argument("--input", required=True, help="Directory of .txt transcripts")
    run_p.add_argument("--config", default="config/default.yaml", help="YAML config path")
    run_p.add_argument(
        "--no-llm",
        action="store_true",
        help="Force heuristic-only mode (no LLM calls).",
    )
    run_p.add_argument(
        "--max-episodes",
        type=int,
        default=None,
        help="Maximum number of episodes to process (default: all).",
    )
    run_p.add_argument("--provider", default=None, help="LLM provider override")
    run_p.add_argument("--model", default=None, help="LLM model override")
    run_p.add_argument("--output-dir", default=None, help="Output directory override")

    insp = sub.add_parser("inspect", help="Inspect parsed transcripts (debug table).")
    insp.add_argument("--input", required=True, help="Directory of .txt transcripts")
    insp.add_argument("--config", default="config/default.yaml", help="YAML config path")

    return parser


def cmd_run(args: argparse.Namespace) -> int:
    setup_logging()
    logger.info("Loading config from %s", args.config)
    try:
        cfg = load_config(args.config)
    except Exception as exc:  # noqa: BLE001 - surface cleanly to user
        logger.error("Failed to load config: %s", exc)
        return 2

    if args.no_llm:
        logger.info("Heuristic-only mode requested (--no-llm)")
    if args.provider:
        logger.info("Provider override: %s", args.provider)
    if args.model:
        logger.info("Model override: %s", args.model)

    logger.info("Setup OK. Input=%s output_dir=%s top_n=%d",
                args.input, cfg.output_dir, cfg.top_n)
    logger.info("Running pipeline (heuristic-only=%s)...", args.no_llm)
    try:
        result = run_pipeline(args.input, cfg, no_llm=args.no_llm,
                              output_dir=args.output_dir,
                              max_episodes=args.max_episodes)
    except Exception as exc:  # noqa: BLE001 - surface cleanly
        logger.error("Pipeline failed: %s", exc)
        return 2
    logger.info("Pipeline complete. Stages: %s",
                ", ".join(f"{s.name}={s.count}" for s in result.stage_results))
    logger.info("Outputs written to %s", result.output_dir)
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    setup_logging()
    logger.info("Loading config from %s", args.config)
    try:
        load_config(args.config)
    except Exception as exc:  # noqa: BLE001 - surface cleanly to user
        logger.error("Failed to load config: %s", exc)
        return 2

    registry = build_default_registry()
    try:
        episodes = load_episodes(args.input)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load episodes from %s: %s", args.input, exc)
        return 2

    if not episodes:
        logger.warning("No transcript files found in %s", args.input)
        return 0

    # Header.
    header = (
        f"{'Ep':>4} {'Source':<24} {'Scenes':>6} {'Ev':>4} "
        f"{'CAM':>4} {'ACT':>4} {'SFX':>4} {'DIA':>4} {'LastEnd':>8} {'Warns':>5}"
    )
    print(header)
    print("-" * len(header))

    for raw in episodes:
        text = open(raw.path, "r", encoding="utf-8").read()
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        try:
            ep, parse_warns = registry.parse(
                type("Raw", (), {"path": raw.path, "text": text})()
            )
        except Exception as exc:  # noqa: BLE001 - report per-episode, continue (R16)
            logger.warning("Failed to parse %s: %s", raw.path, exc)
            print(f"{'?':>4} {os.path.basename(raw.path):<24} {'-':>6} "
                  f"{'-':>4} {'-':>4} {'-':>4} {'-':>4} {'-':>4} {'-':>8} {'1':>5}")
            continue

        ep.warnings.extend(parse_warns)
        ep.warnings.extend(validate_episode(ep))

        cam = sum(1 for e in ep.events if e.kind.value == "camera")
        act = sum(1 for e in ep.events if e.kind.value == "action")
        sfx = sum(1 for e in ep.events if e.kind.value == "sfx")
        dia = sum(1 for e in ep.events if e.kind.value == "dialogue")
        last_end = f"{ep.duration:.2f}"
        print(
            f"{ep.number:>4} {os.path.basename(raw.path):<24} "
            f"{len(ep.scenes):>6} {len(ep.events):>4} "
            f"{cam:>4} {act:>4} {sfx:>4} {dia:>4} {last_end:>8} "
            f"{len(ep.warnings):>5}"
        )

    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "inspect":
        return cmd_inspect(args)
    parser.error("Unknown command")
    return 2  # pragma: no cover
