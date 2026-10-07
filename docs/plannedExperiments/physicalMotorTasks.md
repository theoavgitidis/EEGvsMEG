# Physical Motor Tasks

## Purpose

Physical motor execution tasks are included as reference conditions. They allow comparison between actual movement and motor imagery for similar body parts.

These conditions may produce strong discriminative signals. However, physical movement can also produce EMG and mechanical artifacts, so classification results must be interpreted carefully.

## Hand Movement

The planned hand task is a simple standardized bilateral movement.

Possible implementation:

- repeated opening and closing of both hands during the active period

The exact movement is subject to final experimental decision. Once selected, it must be kept consistent across participants and sessions.

## Foot Movement

The planned foot task is a simple standardized bilateral movement that can be performed while seated.

Possible implementations:

- dorsiflexion / plantar flexion of both feet
- another simple bilateral foot movement that does not require posture changes

The exact movement is subject to final experimental decision. The selected movement should minimize full-body motion and electrode movement.

## Standardization Requirements

Physical movements must be standardized as much as possible:

- same movement description for every participant
- same active period duration
- similar movement amplitude
- controlled movement frequency
- seated posture kept constant
- no additional body movement beyond the requested movement

A metronome or visual rhythm cue may be considered if movement frequency needs to be controlled. This should be tested during pilot measurements because rhythmic cues may also influence EEG responses.

## Artifact Considerations

Physical motor execution can introduce:

- EMG artifacts from muscle activation
- cable movement
- electrode movement
- changes in electrode contact
- posture-related artifacts

Therefore, physical motor trials serve partly as comparison and reference conditions. They must not automatically be interpreted as pure cortical EEG decoding.

## Preliminary Trial Parameters

Planned parameters:

- baseline / fixation: 2-3 seconds
- cue: approximately 1 second
- active movement: approximately 3-5 seconds
- rest: approximately 2-4 seconds
- trials per condition: approximately 30-50

These values are preliminary and should be finalized after pilot testing.

## Pairwise Comparisons

Physical motor tasks support comparisons such as:

- physical hands vs. physical feet
- physical hand movement vs. hand motor imagery
- physical foot movement vs. foot motor imagery

These comparisons should document whether the classifier may be using cortical EEG patterns, artifact-related signals, or a mixture of both.
