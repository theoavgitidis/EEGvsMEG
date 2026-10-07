# Word Generation

## Objective

The word-generation condition tests whether an internal cognitive task can be distinguished from motor imagery and from mental subtraction using EEG.

This condition adapts the word-generation imagery class from the MEGBCI2020 paradigm to the planned EEG setup.

## Possible Task Implementation

A planned implementation is:

- display a letter or semantic category as a cue
- ask the participant to internally generate as many matching words as possible
- keep generation silent and internal

Examples:

- letter cue: `B`
- category cue: `animals`

The exact cue type, language, and difficulty should be finalized after pilot testing.

## Participant Instructions

Suggested standardized instruction:

"When the word-generation cue appears, silently generate as many words as possible that match the cue. Do not speak, whisper, move your lips, or count on your fingers. Continue the internal word-generation task until the task period ends."

Participants should avoid overt speech and visible mouth movement because these can introduce muscle artifacts.

## Cue and Trial Structure

Possible cue format:

- one displayed letter
- one displayed category
- text label such as `Words`

Preliminary trial structure:

```text
Fixation: 2-3 seconds
Cue: approximately 1 second
Internal word generation: approximately 3-5 seconds
Rest: approximately 2-4 seconds
```

All timings are preliminary and should be finalized after pilot measurements.

## Expected Challenges

Word generation may be harder to classify than physical movement and may also be harder than some motor imagery contrasts. This is a hypothesis, not a conclusion.

Potential challenges include:

- variable participant strategies
- different levels of language fluency
- silent articulation or mouth-muscle activity
- inconsistent task difficulty across cues
- weaker or less spatially specific EEG patterns with the available headset

## Possible Pairwise Comparisons

Planned comparisons include:

- word generation vs. mental subtraction
- word generation vs. hand imagery
- word generation vs. foot imagery

Unsuccessful classification above chance level would still be a meaningful result and should be reported as a limitation or boundary of the current setup.
