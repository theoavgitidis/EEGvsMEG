# Baseline / Resting-State Recording

## Purpose

The baseline condition provides a reference recording before or between task blocks. It is intended for signal-quality validation and for comparison against active task conditions.

The baseline may help identify:

- noisy channels
- unstable electrode contact
- excessive muscle activity
- eye-blink or eye-movement artifacts
- resting alpha activity, especially in eyes-closed recordings

Baseline effects should not be overstated. A clear resting pattern does not guarantee that task classification will be successful.

## Planned Conditions

The baseline recording may include:

| Condition | Status | Purpose |
|---|---|---|
| Eyes open | Planned | Reference state with visual fixation |
| Eyes closed | Optional | Additional reference state for alpha activity observation |

For the eyes-open condition, the participant should look at a fixation point on the screen while staying relaxed. For the optional eyes-closed condition, the participant should keep the eyes closed without falling asleep or moving.

## Participant Instructions

Suggested standardized instruction:

"Please sit still and relax. Keep your body relaxed, avoid talking, and avoid unnecessary movement. During the eyes-open phase, look at the fixation point on the screen. During the eyes-closed phase, keep your eyes closed until the next instruction."

The exact wording should be finalized before data collection and then kept identical across participants.

## Preliminary Duration

A preliminary duration is:

- eyes open: approximately 1-3 minutes
- eyes closed: approximately 1-3 minutes, if used

The final duration should be adjusted after pilot testing, based on signal quality, session length, and participant comfort.

## Expected Observations

Eyes-closed resting EEG may show stronger alpha activity than eyes-open resting EEG in some participants. This is an expected possibility, not a guaranteed result. Alpha visibility depends on participant state, channel placement, hardware quality, and preprocessing.

## Artifacts to Avoid

The participant should avoid:

- jaw tension
- speaking
- unnecessary hand or foot movement
- large eye movements
- repeated blinking
- posture changes

Short natural blinks are unavoidable, but excessive blinking should be minimized during marked analysis periods.

## Recorded Metadata

The baseline recording should store:

- participant identifier
- session identifier
- condition label, such as `baseline_eyes_open` or `baseline_eyes_closed`
- start and end markers
- EEG channels used
- sampling rate
- notes about electrode contact or signal quality
- notes about visible artifacts or participant movement
