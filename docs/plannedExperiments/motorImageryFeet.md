# Foot Motor Imagery

## Objective

The foot motor imagery condition tests whether imagined bilateral foot movement can be detected and distinguished using the available EEG headset.

This condition adapts the foot imagery class from the MEGBCI2020 paradigm to EEG.

## Participant Instructions

The participant should imagine moving both feet without performing any physical movement.

Suggested standardized instruction:

"When the foot imagery cue appears, imagine repeatedly moving both feet, for example by flexing them up and down. Do not move your feet, legs, hands, jaw, or other body parts. Continue imagining the movement until the task period ends."

The exact imagery strategy should be practiced before recording and then kept consistent.

## Cue and Trial Structure

Possible cue format:

- text label such as `Feet`
- foot icon
- color-coded condition cue

Preliminary trial structure:

```text
Fixation: 2-3 seconds
Cue: approximately 1 second
Foot motor imagery: approximately 3-5 seconds
Rest: approximately 2-4 seconds
```

All timings are preliminary and should be finalized after pilot measurements.

## Trial Count

The preliminary target is approximately 30-50 foot imagery trials per session. Trials should be distributed across blocks to reduce fatigue.

## Relevant Frequency Ranges

For motor imagery, frequency ranges of interest include:

- alpha / mu range around 8-12 Hz
- beta range approximately 13-30 Hz

These ranges should be evaluated for each participant rather than assumed to work equally well for everyone.

## Important Artifacts

The following artifacts are especially important:

- actual foot or leg movement
- lower-body tension
- hand movement
- blinking during active imagery
- posture changes

If visible movement occurs during a trial, the trial should be marked for later review and possible exclusion.

## Possible Pairwise Comparisons

Planned comparisons include:

- foot imagery vs. hand imagery
- foot imagery vs. physical foot movement
- foot imagery vs. word generation
- foot imagery vs. mental subtraction

The interpretation should distinguish motor imagery from physical motor execution and from cognitive tasks.
