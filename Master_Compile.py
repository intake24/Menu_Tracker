"""Run a validated MenuTracker collection wave from the scraper manifest."""

import argparse
from pathlib import Path

from define_collection_wave import create_collection
from run_parallel import DEFAULT_MANIFEST, run_scripts_parallel


ROOT = Path(__file__).resolve().parent


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run manifest-listed scrapers and validate their fresh outputs."
    )
    parser.add_argument(
        "collection",
        help="Collection folder name or absolute path, for example Aug_collection_2026",
    )
    parser.add_argument(
        "scripts",
        nargs="*",
        metavar="SCRIPT",
        help="Manifest script names to run; omit to run every manifest entry",
    )
    parser.add_argument("--workers", type=int, default=5, help="Concurrent scrapers (default: 5)")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "evidence")
    parser.add_argument(
        "--github-issues",
        action="store_true",
        help="On the trusted Mac, report repeated likely-code failures to GitHub",
    )
    parser.add_argument("--github-repository", help="GitHub owner/repository for repair issues")
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    return args


def main(argv=None):
    args = parse_args(argv)
    create_collection(args.collection)
    results = run_scripts_parallel(
        args.scripts or None,
        max_workers=args.workers,
        cwd=ROOT,
        manifest_path=args.manifest,
        evidence_dir=args.evidence_dir,
        enable_github_issues=args.github_issues,
        github_repository=args.github_repository,
    )
    failed = [result for result in results.values() if not result["ok"]]
    for result in failed:
        if result.get("evidence_bundle"):
            print(f"Evidence: {result['evidence_bundle']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
