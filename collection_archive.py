"""Create and upload self-contained collection-wave archives."""

import json
from pathlib import Path
import zipfile


SUMMARY_FIELDS = (
    "script",
    "ok",
    "returncode",
    "seconds",
    "run_id",
    "failure_class",
    "evidence_bundle",
)


def parse_bucket_uri(uri: str) -> str:
    """Return the bucket name from a bucket-only gs:// URI."""
    prefix = "gs://"
    bucket = uri[len(prefix):] if uri.startswith(prefix) else ""
    if not bucket or "/" in bucket:
        raise ValueError("Archive bucket must be a bucket-only gs:// URI")
    return bucket


def build_run_summary(results: dict[str, dict]) -> dict:
    """Return serializable result metadata without captured process logs."""
    summary = []
    for script, result in sorted(results.items()):
        item = {field: result.get(field) for field in SUMMARY_FIELDS}
        item["script"] = script
        summary.append(item)
    return {"results": summary}


def _write_tree(archive: zipfile.ZipFile, root: Path, prefix: str) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            archive.write(path, Path(prefix) / path.relative_to(root))


def create_archive(
    collection: Path,
    evidence_dir: Path,
    manifest: Path,
    summary: dict,
    destination: Path,
) -> Path:
    """Write collection data, evidence, manifest, and summary into ``destination``."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        _write_tree(archive, collection, "collection")
        _write_tree(archive, evidence_dir, "evidence")
        archive.write(manifest, "metadata/scraper_manifest.json")
        archive.writestr("metadata/run-summary.json", json.dumps(summary, indent=2))
    return destination


def upload_archive(archive: Path, bucket_uri: str, object_name: str, client=None, overwrite: bool = False) -> str:
    """Upload an archive.

    By default this refuses to replace an existing object at the same path
    (protects a fresh wave from accidentally colliding with an unrelated
    upload). Pass overwrite=True for a resumed wave, where re-uploading a
    more-complete archive over an earlier partial one at the same path is
    expected, not an error.
    """
    if client is None:
        try:
            from google.cloud import storage
        except ImportError as error:
            raise RuntimeError("Install google-cloud-storage to upload collection archives") from error
        client = storage.Client()
    bucket_name = parse_bucket_uri(bucket_uri)
    kwargs = {} if overwrite else {"if_generation_match": 0}
    client.bucket(bucket_name).blob(object_name).upload_from_filename(str(archive), **kwargs)
    return f"gs://{bucket_name}/{object_name}"
