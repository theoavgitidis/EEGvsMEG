# Hand Motor Imagery

## Objective

The hand motor imagery condition tests whether imagined bilateral hand movement can be detected and distinguished using the available EEG headset.

This condition adapts the hand imagery class from the MEGBCI2020 paradigm to EEG.

## Participant Instructions

The participant should imagine moving both hands without performing any physical movement.

Suggested standardized instruction:

"When the hand imagery cue appears, imagine repeatedly opening and closing both hands. Do not move your hands, arms, fingers, feet, jaw, or other body parts. Continue imagining the movement until the task period ends."

The exact imagery strategy should be practiced before recording and then kept consistent.

## Cue and Trial Structure

Possible cue format:

- text label such as `Hands`
- hand icon
- color-coded condition cue

Preliminary trial structure:

```text
Fixation: 2-3 seconds
Cue: approximately 1 second
Hand motor imagery: approximately 3-5 seconds
Rest: approximately 2-4 seconds
```

All timings are preliminary and should be finalized after pilot measurements.

## Trial Count

The preliminary target is approximately 30-50 hand imagery trials per session. Trials should be distributed across blocks to reduce fatigue.

## Relevant Frequency Ranges

For motor imagery, frequency ranges of interest include:

- alpha / mu range around 8-12 Hz
- beta range approximately 13-30 Hz

These ranges should be evaluated for each participant rather than assumed to work equally well for everyone.

## Important Artifacts

The following artifacts are especially important:

- actual hand or finger movement
- arm tension
- jaw tension
- blinking during active imagery
- posture changes

If visible movement occurs during a trial, the trial should be marked for later review and possible exclusion.

## Possible Pairwise Comparisons

Planned comparisons include:

- hand imagery vs. foot imagery
- hand imagery vs. physical hand movement
- hand imagery vs. word generation
- hand imagery vs. mental subtraction

The interpretation should distinguish motor imagery from physical motor execution and from cognitive tasks.
