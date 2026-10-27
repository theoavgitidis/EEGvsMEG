"""Download the reviewed REVE snapshots and verify every pinned file."""
import argparse
import json
from pathlib import Path
from huggingface_hub import snapshot_download
from analysis.ml_data import sha256


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', type=Path, default=Path('.ml-cache/reve-checkpoint.json'))
    args = parser.parse_args()
    pins = json.loads(Path(__file__).with_name('reve_pinned.json').read_text())
    for repo, entry in pins.items():
        path = Path(snapshot_download(repo, revision=entry['revision'], allow_patterns=list(entry['files'])))
        for name, digest in entry['files'].items():
            if sha256(path / name) != digest:
                raise ValueError(f'Checksum mismatch: {repo}/{name}')
        entry['path'] = str(path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pins, indent=2)+'\n')
    print(f'Verified snapshots: {args.output}')


if __name__ == '__main__':
    main()
