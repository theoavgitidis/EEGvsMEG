"""Fetch only PhysioNet EEGMMIDB executed left/right fist runs, with SHA-256 checks."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.request import urlopen

BASE_URL = "https://physionet.org/files/eegmmidb/1.0.0/"
DATASET_URL = "https://physionet.org/content/eegmmidb/1.0.0/"
CHECKSUM_SHA256 = "7f5d16957d8ee7bce86cc7ccba0e5994f63f33781607eb3f838392d49311a208"
DEFAULT_ROOT = Path.home() / ".cache/eegvsmeg/physionet-eegmmidb-1.0.0"
RUNS = (3, 7, 11)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_files(subjects):
    subjects = sorted(set(subjects))
    if not subjects or any(not 1 <= s <= 109 for s in subjects):
        raise ValueError("Subjects must be integers in 1..109.")
    return [f"S{s:03d}/S{s:03d}R{r:02d}.edf{suffix}"
            for s in subjects for r in RUNS for suffix in ("", ".event")]


def read_checksums(path):
    if sha256(path) != CHECKSUM_SHA256:
        raise ValueError("Official SHA256SUMS.txt differs from the pinned version.")
    result = {}
    for line in path.read_text(encoding="ascii").splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid source checksum.")
        if name in result:
            raise ValueError("Duplicate source checksum.")
        result[name] = digest
    return result


def fetch_file(source, relative, expected, offline=False):
    """Never replace existing originals; publish new downloads only after verification."""
    path = source / relative
    if path.exists():
        if sha256(path) != expected:
            raise ValueError(f"Existing file has wrong checksum; left unchanged: {path}")
        return {"file": relative, "sha256": expected, "bytes": path.stat().st_size}
    if offline:
        raise FileNotFoundError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as out:
                temporary = Path(out.name)
                with urlopen(BASE_URL + relative, timeout=60) as response:
                    for chunk in iter(lambda: response.read(1024 * 1024), b""):
                        out.write(chunk)
            if sha256(temporary) != expected:
                raise ValueError(f"Downloaded checksum mismatch: {relative}")
            # Exclusive publication also prevents concurrent runs from overwriting originals.
            os.link(temporary, path)
            return {"file": relative, "sha256": expected, "bytes": path.stat().st_size}
        except FileExistsError:
            if sha256(path) == expected:
                return {"file": relative, "sha256": expected, "bytes": path.stat().st_size}
            raise
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def download(root, subjects, workers=4, offline=False):
    files = selected_files(subjects)
    if not 1 <= workers <= 8:
        raise ValueError("Use 1..8 download workers.")
    source = Path(root) / "source"
    source.mkdir(parents=True, exist_ok=True)
    fetch_file(source, "SHA256SUMS.txt", CHECKSUM_SHA256, offline)
    checksums = read_checksums(source / "SHA256SUMS.txt")
    files += ["RECORDS", "ANNOTATORS", "wfdbcal"]
    missing = set(files) - checksums.keys()
    if missing:
        raise ValueError(f"Files absent from official checksums: {sorted(missing)}")
    entries = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_file, source, name, checksums[name], offline) for name in files]
        for future in as_completed(futures):
            entries.append(future.result())
            if len(entries) % 25 == 0 or len(entries) == len(files):
                print(f"Verified {len(entries)}/{len(files)} files", flush=True)
    manifest = {"dataset": "PhysioNet EEGMMIDB", "version": "1.0.0",
        "source_url": DATASET_URL, "file_base_url": BASE_URL,
        "doi": "10.13026/C28G6P", "license": "ODC-By-1.0",
        "license_url": "https://physionet.org/content/eegmmidb/view-license/1.0.0/",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "checksum_manifest_sha256": CHECKSUM_SHA256,
        "subjects": sorted(set(subjects)), "runs": list(RUNS),
        "selection": "executed unilateral left/right fist opening and closing",
        "files": sorted(entries, key=lambda entry: entry["file"])}
    (Path(root) / "download-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 110)))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--verify-only", action="store_true", help="Verify locally; no network access")
    args = parser.parse_args(argv)
    manifest = download(args.root.expanduser(), args.subjects, args.workers, args.verify_only)
    print(f"Complete: {len(manifest['files'])} files; {args.root / 'download-manifest.json'}")


if __name__ == "__main__":
    main()
