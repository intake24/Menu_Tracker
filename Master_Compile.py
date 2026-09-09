"""Run a validated MenuTracker collection wave from the scraper manifest."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from collection_archive import build_run_summary, create_archive, upload_archive
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
    parser.add_argument("--workers", type=int, default=1, help="Concurrent scrapers (default: 1)")
    parser.add_argument(
        "--timeout",
        type=int,
        default=1200,
        metavar="SECONDS",
        help="Kill and mark failed any scraper still running after this long (default: 1200s, 0 disables)",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument(
        "--archive-gcs",
        metavar="BUCKET_URI",
        help="Archive this completed wave to a bucket-only gs:// URI",
    )
    parser.add_argument(
        "--github-issues",
        action="store_true",
        help="On the trusted Mac, report repeated likely-code failures to GitHub",
    )
    parser.add_argument("--github-repository", help="GitHub owner/repository for repair issues")
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if args.timeout < 0:
        parser.error("--timeout must be at least 0")
    if args.archive_gcs and args.evidence_dir is None:
        parser.error("--archive-gcs requires a run-specific --evidence-dir")
    args.evidence_dir = args.evidence_dir or ROOT / "evidence"
    return args


def main(argv=None):
    args = parse_args(argv)
    collection = Path(create_collection(args.collection))
    results = run_scripts_parallel(
        args.scripts or None,
        max_workers=args.workers,
        cwd=ROOT,
        manifest_path=args.manifest,
        evidence_dir=args.evidence_dir,
        enable_github_issues=args.github_issues,
        github_repository=args.github_repository,
        timeout_seconds=args.timeout or None,
    )
    failed = [result for result in results.values() if not result["ok"]]
    for result in failed:
        if result.get("evidence_bundle"):
            print(f"Evidence: {result['evidence_bundle']}")
    if args.archive_gcs:
        archive_name = f"{collection.name}.zip"
        object_name = f"archives/{archive_name}"
        try:
            with TemporaryDirectory(prefix="menutracker-archive-") as directory:
                archive = create_archive(
                    collection,
                    args.evidence_dir,
                    args.manifest,
                    build_run_summary(results),
                    Path(directory) / archive_name,
                )
                print(f"Archive: {upload_archive(archive, args.archive_gcs, object_name)}")
        except Exception as error:
            print(f"Archive failed: {error}")
            return 2
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
