"""Reproducible offline comparison: bandpower, frozen CBraMod, last-block tuning.

Run from the project root with python -m analysis.cbramod_benchmark --help.
"""
import argparse
import copy
import importlib.metadata
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.linear_model import RidgeClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn

from analysis.ml_data import load_recording, sha256, splits
from analysis.vendor.cbramod.cbramod import CBraMod


def write_json(path, value):
    temp = Path(str(path) + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temp.replace(path)


def load_pretrained(manifest_path):
    manifest = json.loads(Path(manifest_path).read_text())
    if sha256(manifest["path"]) != manifest["sha256"]:
        raise ValueError("Checkpoint SHA256 mismatch.")
    state = torch.load(manifest["path"], map_location="cpu", weights_only=True)
    model = CBraMod()
    # Strict loading is essential: a random/mismatched encoder must never be evaluated as pretrained.
    model.load_state_dict(state, strict=True)
    model.eval().requires_grad_(False)
    return model, manifest


@torch.no_grad()
def cached_trunk(model, x, batch_size=16):
    """Only fixed, per-example operations; safe to cache without fitting test data."""
    chunks = []
    for start in range(0, len(x), batch_size):
        h = model.patch_embedding(torch.from_numpy(x[start:start + batch_size]))
        for layer in model.encoder.layers[:-1]:
            h = layer(h)
        chunks.append(h.cpu())
    return torch.cat(chunks)


class Classifier(nn.Module):
    def __init__(self, last_block, n_classes, tune=False):
        super().__init__()
        self.last_block = copy.deepcopy(last_block)
        self.last_block.requires_grad_(tune)
        self.tune = tune
        # Per-example layer normalization; no statistics from other examples.
        self.norm = nn.LayerNorm(200, elementwise_affine=False)
        self.head = nn.Linear(8 * 200, n_classes)

    def train(self, mode=True):
        super().train(mode)
        if not self.tune:
            self.last_block.eval()
        return self

    def forward(self, h):
        h = self.last_block(h)
        h = self.norm(h.mean(dim=2)).flatten(1)  # Preserve channel-specific information.
        return self.head(h)


def train_model(last_block, h, y, train_idx, val_idx, *, tune, seed, epochs,
                head_lr=.001, encoder_lr=.00001, batch_size=16):
    """Select duration on inner validation only; caller refits on all outer training data."""
    torch.manual_seed(seed)
    model = Classifier(last_block, int(y.max()) + 1, tune)
    groups = [{"params": model.head.parameters(), "lr": head_lr}]
    if tune:
        groups.append({"params": model.last_block.parameters(), "lr": encoder_lr})
    optimizer = torch.optim.AdamW(groups, weight_decay=.01)
    generator = torch.Generator().manual_seed(seed)
    train_idx = torch.as_tensor(train_idx, dtype=torch.long)
    val_idx = torch.as_tensor(val_idx, dtype=torch.long)
    history, best_epoch, best_loss = [], epochs, float("inf")
    for epoch in range(1, epochs + 1):
        model.train()
        order = train_idx[torch.randperm(len(train_idx), generator=generator)]
        for batch in order.split(batch_size):
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.cross_entropy(model(h[batch]), y[batch])
            if not torch.isfinite(loss):
                raise ValueError("Non-finite training loss.")
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
        if len(val_idx):
            model.eval()
            with torch.no_grad():
                logits = model(h[val_idx])
                val_loss = nn.functional.cross_entropy(logits, y[val_idx]).item()
            history.append({"epoch": epoch, "validation_loss": val_loss})
            if val_loss < best_loss:
                best_loss, best_epoch = val_loss, epoch
    model.eval()
    return model, best_epoch, history


def metrics(y, predicted, classes):
    return {"balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
            "macro_f1": float(f1_score(y, predicted, average="macro")),
            "confusion_true_rows": confusion_matrix(y, predicted, labels=np.arange(len(classes))).tolist(),
            "classes": classes, "n_windows": len(y)}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--signal", choices=["auto", "raw", "oscar"], default="auto")
    parser.add_argument("recording", type=Path)
    parser.add_argument("--checkpoint-manifest", type=Path, default=Path(".ml-cache/checkpoint.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[11, 22, 33])
    parser.add_argument("--max-epochs", type=int, default=20)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--runs", nargs="+", choices=["Motorik", "Imagery", "Kognitiv"],
                        default=["Motorik", "Imagery", "Kognitiv"])
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new output directory; prior experiments are never overwritten.")
    if args.max_epochs < 1 or len(set(args.seeds)) != len(args.seeds):
        raise ValueError("Use positive epochs and unique seeds.")
    args.output.mkdir(parents=True)
    (args.output / "checkpoints").mkdir()
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    started = time.monotonic()
    rows, x, old_features, matched_features, data_info = load_recording(args.recording, signal=args.signal)
    rows.to_csv(args.output / "epochs.csv", index_label="epoch_index")
    model, checkpoint_info = load_pretrained(args.checkpoint_manifest)
    config = {"data": data_info, "checkpoint": checkpoint_info,
              "upstream": json.loads(Path("analysis/vendor/cbramod/provenance.json").read_text()),
              "code_sha256": {str(p): sha256(p) for p in [Path(__file__), Path("analysis/ml_data.py"),
                  Path("analysis/ml_feasibility.py"), *Path("analysis/vendor/cbramod").glob("*.py")]},
              "arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              "versions": {name: importlib.metadata.version(name) for name in ["torch", "numpy", "scipy", "pandas", "scikit-learn"]},
              "device": "cpu", "encoder_parameters": sum(p.numel() for p in model.parameters()),
              "head_lr": .001, "encoder_lr": .00001, "weight_decay": .01, "batch_size": 16,
              "selection": "minimum cross-entropy on cyclic inner validation block; refit fresh on all outer training blocks for selected epoch count",
              "limitations": ["one person/session", "exploratory", "offline noncausal filter",
                  "3 training seeds are not independent test cohorts", "same held-out blocks reused across predefined candidates",
                  "no amplitude-based artifact rejection", "montage assumed from project configuration"]}
    write_json(args.output / "config.json", config)  # Written before model evaluation.
    print(f"Loaded strict checkpoint; {len(rows)} windows, shape {x.shape}.", flush=True)
    trunk = cached_trunk(model, x)
    with torch.no_grad():
        full = model.encoder(model.patch_embedding(torch.from_numpy(x[:2])) )
        cached = model.encoder.layers[-1](trunk[:2])
        torch.testing.assert_close(full, cached, rtol=1e-4, atol=1e-4)
    print(f"Frozen trunk cached and checked against full encoder ({time.monotonic()-started:.1f}s).", flush=True)
    report, predictions, folds_log = {}, [], []
    for run in args.runs:
        indices = np.flatnonzero((rows.run == run).to_numpy())
        sub = rows.iloc[indices].reset_index(drop=True)
        classes = sorted(sub.label.unique())
        y_np = np.array([classes.index(v) for v in sub.label])
        y, h = torch.from_numpy(y_np), trunk[indices]
        fold_definitions = list(splits(sub))
        run_report = {}
        for variant, feat in [("bandpower_original", old_features), ("bandpower_matched", matched_features)]:
            predicted = np.full(len(sub), -1)
            fold_scores = []
            for test_block, val_block, train, val, test, outer in fold_definitions:
                clf = make_pipeline(StandardScaler(), RidgeClassifier(alpha=10))
                clf.fit(feat[indices[outer]], y_np[outer])
                p = clf.predict(feat[indices[test]])
                predicted[test] = p
                fold_scores.append({"test_block": test_block, **metrics(y_np[test], p, classes)})
            run_report[variant] = {**metrics(y_np, predicted, classes), "folds": fold_scores}
            for i, p in enumerate(predicted):
                predictions.append({"epoch_index": int(indices[i]), "run": run, "variant": variant,
                                    "seed": None, "true": classes[y_np[i]], "predicted": classes[p]})
        for tune in [False, True]:
            variant = "finetune_last_block" if tune else "frozen_encoder"
            results = []
            for seed in args.seeds:
                predicted = np.full(len(sub), -1)
                selected_epochs, fold_scores = [], []
                for test_block, val_block, train, val, test, outer in fold_definitions:
                    _, selected, history = train_model(model.encoder.layers[-1], h, y, train, val,
                        tune=tune, seed=seed, epochs=args.max_epochs)
                    fitted, _, _ = train_model(model.encoder.layers[-1], h, y, outer, [],
                        tune=tune, seed=seed, epochs=selected)
                    delta = sum((a.detach() - b.detach()).square().sum().item()
                                for a, b in zip(fitted.last_block.parameters(), model.encoder.layers[-1].parameters())) ** .5
                    if (tune and delta == 0) or (not tune and delta != 0):
                        raise AssertionError("Encoder update did not match requested training regime.")
                    with torch.no_grad():
                        p = fitted(h[test]).argmax(1).numpy()
                    predicted[test] = p
                    score = metrics(y_np[test], p, classes)
                    fold_scores.append({"test_block": test_block, **score})
                    selected_epochs.append(selected)
                    folds_log.append({"run": run, "variant": variant, "seed": seed,
                        "test_block": test_block, "validation_block": val_block,
                        "inner_train_epoch_indices": indices[train].tolist(),
                        "validation_epoch_indices": indices[val].tolist(), "test_epoch_indices": indices[test].tolist(),
                        "refit_epoch_indices": indices[outer].tolist(), "selected_epochs": selected,
                        "validation_history": history, "encoder_weight_change_l2": delta,
                        "trainable_parameters": sum(p.numel() for p in fitted.parameters() if p.requires_grad)})
                    print(f"{run} {variant} seed={seed} block={test_block}: {score['balanced_accuracy']:.3f} ({selected} epochs)", flush=True)
                    write_json(args.output / "folds.json", folds_log)
                seed_result = {"seed": seed, **metrics(y_np, predicted, classes), "folds": fold_scores,
                               "selected_epochs": selected_epochs}
                results.append(seed_result)
                for i, p in enumerate(predicted):
                    predictions.append({"epoch_index": int(indices[i]), "run": run, "variant": variant,
                        "seed": seed, "true": classes[y_np[i]], "predicted": classes[p]})
                # Full-session research model for later external validation; not used for reported test scores.
                final_epochs = max(1, int(np.median(selected_epochs)))
                final, _, _ = train_model(model.encoder.layers[-1], h, y, np.arange(len(sub)), [],
                    tune=tune, seed=seed, epochs=final_epochs)
                torch.save({"state_dict": final.state_dict(), "classes": classes, "tune": tune,
                    "run": run, "seed": seed, "epochs": final_epochs,
                    "upstream_checkpoint_sha256": checkpoint_info["sha256"],
                    "warning": "trained on complete session; evaluate on a genuinely new session"},
                    args.output / "checkpoints" / f"{run}_{variant}_seed{seed}.pt")
            scores = [r["balanced_accuracy"] for r in results]
            run_report[variant] = {"mean_balanced_accuracy": float(np.mean(scores)),
                "min_balanced_accuracy": float(min(scores)), "max_balanced_accuracy": float(max(scores)),
                "seeds": results}
        report[run] = run_report
        write_json(args.output / "results.json", report)
        pd.DataFrame(predictions).to_csv(args.output / "predictions.csv", index=False)
    write_json(args.output / "completion.json", {"complete": True, "elapsed_seconds": time.monotonic()-started})
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
