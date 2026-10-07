# Mental Subtraction

## Objective

The mental-subtraction condition tests whether an internal calculation task can be distinguished from motor imagery and from word generation using EEG.

This condition adapts the subtraction imagery class from the MEGBCI2020 paradigm to the planned EEG setup.

## Possible Task Implementation

A planned implementation is:

- display a starting number
- ask the participant to repeatedly subtract 7 mentally
- continue the calculation silently until the task period ends

Example:

```text
Start at 843 and repeatedly subtract 7.
```

The exact starting-number range and subtraction step should be finalized after pilot testing so that the task is challenging but not frustrating.

## Participant Instructions

Suggested standardized instruction:

"When the subtraction cue appears, silently subtract 7 repeatedly from the starting number. Do not speak, whisper, move your lips, or use your fingers. Continue the internal calculation until the task period ends."

No verbal response is required during the trial. If accuracy needs to be checked, this should be done after the active period in a way that does not contaminate the EEG epoch.

## Cue and Trial Structure

Possible cue format:

- starting number shown on screen
- text label such as `Subtract`

Preliminary trial structure:

```text
Fixation: 2-3 seconds
Cue: approximately 1 second
Internal subtraction: approximately 3-5 seconds
Rest: approximately 2-4 seconds
```

All timings are preliminary and should be finalized after pilot measurements.

## Expected Challenges

Mental subtraction may create cognitive workload effects, but the EEG pattern may vary depending on strategy and difficulty. Some participants may count verbally in their head, some may visualize numbers, and some may lose track during the trial.

Potential challenges include:

- inconsistent cognitive strategy
- variation in arithmetic skill
- silent articulation or mouth-muscle activity
- frustration or fatigue
- changing difficulty across trials

These challenges should be documented rather than treated as failures.

## Possible Pairwise Comparisons

Planned comparisons include:

- mental subtraction vs. word generation
- mental subtraction vs. hand imagery
- mental subtraction vs. foot imagery

Classification results should be interpreted together with task difficulty, participant notes, and artifact review.
