"""Protocol-specific labels and predefined contrasts; never pool legacy tasks."""
import numpy as np


LEGACY = "eeg-session-1.0"
CURRENT = "eeg-session-2.0"
LEGACY_RUNS = {"Motorik": {"arms", "legs", "blink"},
               "Imagery": {"imagine_arms", "imagine_legs"},
               "Kognitiv": {"mental_arithmetic"}}
CURRENT_RUNS = {
    "Motorik": {"me_hand_left", "me_hand_right", "me_foot_left", "me_foot_right"},
    "Imagery": {"mi_hand_left", "mi_hand_right", "mi_foot_left", "mi_foot_right",
                "mi_hands_bilateral", "mi_feet_bilateral", "word_generation", "mental_subtraction_single"},
}
CONTRASTS = {
    "ME_HandSide": {"me_hand_left", "me_hand_right"},
    "ME_FootSide": {"me_foot_left", "me_foot_right"},
    "ME_FourClass": CURRENT_RUNS["Motorik"],
    "MI_HandSide": {"mi_hand_left", "mi_hand_right"},
    "MI_FootSide": {"mi_foot_left", "mi_foot_right"},
    "MI_FourClass": {"mi_hand_left", "mi_hand_right", "mi_foot_left", "mi_foot_right"},
    "MI_Bilateral": {"mi_hands_bilateral", "mi_feet_bilateral"},
    "Cognitive": {"word_generation", "mental_subtraction_single"},
}
EVALUATIONS = [*LEGACY_RUNS, *CONTRASTS]


def protocol_for_events(events, declared=None):
    """Prefer recorded versions; infer only unambiguous old/new label families."""
    versions = set()
    if "protocol_version" in events:
        versions = {str(v) for v in events.protocol_version if str(v) not in ("", "nan")}
    if declared:
        versions.add(declared)
    if len(versions) > 1:
        raise ValueError("Mixed or conflicting session protocol versions.")
    labels = set(events.condition) - {""}
    if not versions:
        if labels <= set.union(*CURRENT_RUNS.values()) and labels:
            versions = {CURRENT}
        elif labels <= set.union(*LEGACY_RUNS.values()):
            versions = {LEGACY}
        else:
            raise ValueError("Unknown or mixed legacy/current condition labels.")
    version = versions.pop()
    if version not in (LEGACY, CURRENT):
        raise ValueError(f"Unsupported protocol: {version}")
    runs = CURRENT_RUNS if version == CURRENT else LEGACY_RUNS
    if not labels <= set.union(*runs.values()):
        raise ValueError(f"Conditions do not match protocol {version}.")
    return version, runs


def select_evaluations(rows, protocol, names=None):
    """Return indices for comparable contrasts, retaining original trial/block IDs."""
    if protocol not in (LEGACY, CURRENT):
        raise ValueError(f"Unsupported protocol: {protocol}")
    available = CONTRASTS if protocol == CURRENT else {
        **LEGACY_RUNS, "Kognitiv": {"mental_arithmetic", "rest"}}
    selected = []
    for name in names if names is not None else available:
        if name not in available:
            raise ValueError(f"Evaluation {name} is not defined for {protocol}; choose {', '.join(available)}.")
        labels = available[name]
        indices = np.flatnonzero(rows.label.isin(labels).to_numpy())
        if not len(indices) and names is None:
            continue
        if set(rows.iloc[indices].label) != labels:
            raise ValueError(f"Evaluation {name} needs complete classes: {sorted(labels)}")
        selected.append((name, indices))
    if not selected:
        raise ValueError("No complete evaluation contrasts.")
    return selected


def prediction_indices(rows, protocol, state):
    """Old saved models default to their original protocol, never to new tasks."""
    if state.get("protocol_version", LEGACY) != protocol:
        raise ValueError("Saved model and recording use different session protocols.")
    _, indices = select_evaluations(rows, protocol, [state["run"]])[0]
    if set(rows.iloc[indices].label) != set(state["classes"]):
        raise ValueError("Saved model classes do not match the evaluation contrast.")
    return indices
