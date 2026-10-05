"""Run the retrieval benchmark from the CLI.

Usage:
    python scripts/run_benchmark.py            # compute and print
    python scripts/run_benchmark.py --persist  # store for the Evaluation page
"""

from __future__ import annotations

import argparse
import json

from app.db.session import SessionLocal
from app.evaluation.benchmark import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="TalentGraph retrieval benchmark")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--strategies", nargs="*", default=None)
    args = parser.parse_args()

    with SessionLocal() as db:
        result = run_benchmark(db, k=args.k, persist=args.persist, strategy_keys=args.strategies)
        print(
            json.dumps(
                {
                    "metrics": result["metrics"],
                    "k": result["k"],
                    "dataset_size": result["dataset_size"],
                    "duration_ms": result["duration_ms"],
                },
                indent=2,
            )
        )
        if args.persist:
            print(f"persisted benchmark run #{result.get('benchmark_run_id')}")


if __name__ == "__main__":
    main()
