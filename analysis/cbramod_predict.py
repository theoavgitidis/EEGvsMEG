"""Apply a saved full-session research model to known windows of another session.

This is offline, event-guided inference; it is not continuous task detection.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from analysis.cbramod_benchmark import Classifier, cached_trunk, load_pretrained, metrics
from analysis.ml_data import load_recording


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--checkpoint-manifest", type=Path, default=Path(".ml-cache/checkpoint.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    torch.set_num_threads(4)
    base, provenance = load_pretrained(args.checkpoint_manifest)
    state = torch.load(args.model, map_location="cpu", weights_only=True)
    if state["upstream_checkpoint_sha256"] != provenance["sha256"]:
        raise ValueError("Model and base checkpoint differ.")
    model = Classifier(base.encoder.layers[-1], len(state["classes"]), state["tune"])
    model.load_state_dict(state["state_dict"], strict=True)
    model.eval()
    rows, x, _, _, _ = load_recording(args.recording)
    keep = (rows.run == state["run"]).to_numpy()
    rows = rows[keep].copy()
    if not len(rows):
        raise ValueError("No windows for this model's run.")
    with torch.no_grad():
        p = model(cached_trunk(base, x[keep])).softmax(1).numpy()
    rows["prediction"] = [state["classes"][i] for i in p.argmax(1)]
    for i, label in enumerate(state["classes"]):
        rows[f"uncalibrated_probability_{label}"] = p[:, i]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(args.output, index=False)
    print("Predictions saved. Validity as a new-session test depends on using data absent from training.")
    truth = np.array([state["classes"].index(v) for v in rows.label])
    print(json.dumps(metrics(truth, p.argmax(1), state["classes"]), indent=2))


if __name__ == "__main__":
    main()
