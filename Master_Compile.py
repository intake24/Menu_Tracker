"""Run a validated MenuTracker collection wave from the scraper manifest."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from collection_archive import build_run_summary, create_archive, upload_archive
from define_collection_wave import create_collection, resolve_collection
from run_parallel import DEFAULT_MANIFEST, filter_for_resume, load_manifest, run_scripts_parallel


ROOT = Path(__file__).resolve().parent


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run manifest-listed scrapers and validate their fresh outputs."
    )
    parser.add_argument(
        "collection",
        nargs="?",
        default=None,
        help="Collection folder name or absolute path, for example Aug_collection_2026. "
        "Required unless --resume is used.",
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
        default=2400,
        metavar="SECONDS",
        help="Kill and mark failed any scraper still running after this long (default: 2400s, 0 disables)",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an existing collection wave, skipping chains whose output "
        "already validates. Uses the collection named by the positional "
        "argument, or the most recently modified one if that's omitted -- "
        "but if you omit it while also restricting to specific SCRIPTs, the "
        "first SCRIPT name is misread as the collection name, so name the "
        "collection explicitly whenever SCRIPT args are given.",
    )
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
    # parse_args (not parse_intermixed_args) mis-splits SCRIPT args between the
    # optional `collection` positional and `scripts` when --resume sits between
    # them, on Python 3.11 (works fine on 3.14 -- an argparse version quirk).
    # parse_intermixed_args handles every ordering correctly.
    args = parser.parse_intermixed_args(argv)
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if args.timeout < 0:
        parser.error("--timeout must be at least 0")

    if args.resume:
        target = resolve_collection(args.collection)
        if target is None:
            what = f"Collection {args.collection!r}" if args.collection else "Latest collection"
            parser.error(f"{what} not found, please start without --resume")
        args.collection = target
    elif not args.collection:
        parser.error("collection is required unless --resume is used")

    # --resume derives a run-specific --evidence-dir on its own (the
    # collection's sibling *_evidence folder), so it satisfies the same
    # safety requirement --archive-gcs normally needs an explicit flag for.
    explicit_evidence_dir = args.evidence_dir is not None
    if args.archive_gcs and not explicit_evidence_dir and not args.resume:
        parser.error("--archive-gcs requires a run-specific --evidence-dir (or use --resume)")

    if args.evidence_dir is None:
        name = args.collection
        if args.resume and name.endswith("_collection"):
            name = name[: -len("_collection")]
            args.evidence_dir = ROOT / "collections" / f"{name}_evidence"
        else:
            args.evidence_dir = ROOT / "evidence"
    return args


def main(argv=None):
    args = parse_args(argv)
    collection = Path(create_collection(args.collection))

    scripts = args.scripts or None
    if args.resume:
        manifest = load_manifest(args.manifest)
        requested = args.scripts or list(manifest)
        scripts = filter_for_resume(collection, manifest, requested)
        skipped = len(requested) - len(scripts)
        if not scripts:
            print(f"Collection '{args.collection}' is already complete; nothing to resume.")
            return 0
        print(f"Resume: {skipped}/{len(requested)} already complete, skipping. Running {len(scripts)}.")

    results = run_scripts_parallel(
        scripts,
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
                print(f"Archive: {upload_archive(archive, args.archive_gcs, object_name, overwrite=args.resume)}")
        except Exception as error:
            print(f"Archive failed: {error}")
            return 2
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
