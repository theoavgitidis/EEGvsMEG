"""Shared movement feature contract; usable without scikit-learn or MNE."""
import numpy as np
from scipy.signal import butter, sosfilt, welch

from analysis.ml_data import CHANNELS

FS = 250
WARMUP = 125
WINDOW = 750
HISTORY = WARMUP + WINDOW
CONFIG = {
    "sampling_rate_hz": FS, "unit": "uV", "channel_order": CHANNELS,
    "history_samples": HISTORY, "warmup_samples": WARMUP, "feature_samples": WINDOW,
    "filter": "4th-order Butterworth 7-35 Hz; causal sosfilt; reset per window; subtract first sample",
    "bands_hz": [[8, 13], [13, 30]], "reference": "as recorded; no additional rereferencing",
    "features": "log Welch bandpower; nperseg=500; band-major, then recorded channel order",
    "classifier": "StandardScaler + balanced LogisticRegression(C=1, max_iter=2000, random_state=0)",
}


def window_features(history):
    """Use exactly 3.5 seconds of past EEG in uV; no future samples or fit state."""
    history = np.asarray(history, dtype=float)
    if history.shape != (HISTORY, len(CHANNELS)) or not np.isfinite(history).all():
        raise ValueError(f"Expected {HISTORY} finite samples x eight EEG channels in uV.")
    filtered = sosfilt(butter(4, [7, 35], fs=FS, btype="bandpass", output="sos"),
                       history - history[0], axis=0)[WARMUP:]
    frequency, psd = welch(filtered, fs=FS, nperseg=500, axis=0)
    return np.concatenate([
        np.log(np.maximum(np.trapezoid(psd[(frequency >= lo) & (frequency <= hi)],
            frequency[(frequency >= lo) & (frequency <= hi)], axis=0), 1e-20))
        for lo, hi in CONFIG["bands_hz"]
    ])
