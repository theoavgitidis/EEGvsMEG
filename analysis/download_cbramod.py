"""Download the pinned authors' checkpoint and verify its content before use."""
import argparse
import json
from pathlib import Path

from huggingface_hub import hf_hub_download

from analysis.ml_data import sha256

REPO = "weighting666/CBraMod"
REVISION = "500543c7e30bda1b22bfd51a49301b238dee21fd"
SHA256 = "0792cb808c14e6b7a2bb2ce1dff379bc47bc54c49a779825bdfeb33bf8157178"


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(".ml-cache/checkpoint.json"))
    args = parser.parse_args()
    path = hf_hub_download(REPO, "pretrained_weights.pth", revision=REVISION)
    if sha256(path) != SHA256:
        raise ValueError("Downloaded checkpoint did not match the pinned hash.")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps({"repository": REPO, "revision": REVISION,
        "filename": "pretrained_weights.pth", "path": path, "sha256": SHA256}, indent=2) + "\n")
    print(args.manifest)


if __name__ == "__main__":
    main()
