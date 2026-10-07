# Study Design

## Background

The planned EEG study is inspired by the MEGBCI2020 project. The reference dataset was recorded with a high-density MEG system and contains motor imagery and cognitive imagery tasks intended for brain-computer-interface research.

Known reference-study properties:

- 17 healthy participants are included in the released dataset.
- Two recording sessions were recorded on separate days.
- MEG was recorded with 306 channels.
- The sampling frequency was 1 kHz.
- Four main mental imagery task classes were used:
  1. Both hand motor imagery
  2. Both feet motor imagery
  3. Word generation
  4. Mental subtraction

The reference processing and validation pipeline includes:

- an analysis window of approximately 0.5 to 3.5 seconds after cue onset
- resampling to 250 Hz
- CSP-based feature extraction, including filter-bank CSP variants
- evaluation of frequency bands in approximately the 8-30 Hz range
- pairwise classification between task classes
- session 1 used for training
- session 2 used for testing

No additional details should be assumed unless they are verified from the reference study, repository, or pilot implementation.

## Transfer from MEG to EEG

This study adapts the MEGBCI2020 paradigm to EEG. It is not an exact replication of the reference dataset.

The distinction is important because:

- MEG and EEG measure related but physically different signals.
- The available EEG headset has significantly fewer channels than the 306-channel MEG system.
- Spatial resolution, sensor placement, and signal characteristics differ between MEG and EEG.
- EEG and MEG differ in their susceptibility to artifacts.
- Direct numerical comparison of classification accuracy between this EEG study and the MEG reference results is limited.

The study therefore investigates whether the MEGBCI2020-style experimental paradigm can be transferred to a practical EEG setup, and which parts of the paradigm remain measurable with the available hardware.

## Research Questions

1. Can hand and foot motor imagery be distinguished using the available EEG headset?
2. Can cognitive tasks such as word generation and mental subtraction be distinguished using EEG?
3. Are physical motor movements easier to classify than motor imagery?
4. Is motor imagery easier to classify than cognitive tasks?
5. How reproducible are the EEG patterns across sessions?
6. Can a model trained on one session generalize to another session?

## Hypotheses

The following statements are hypotheses, not conclusions:

- Physical motor execution is expected to provide the strongest discriminative signal.
- Motor imagery is expected to provide weaker but still measurable differences.
- Cognitive task classification may be more difficult with the available EEG setup.
- Classification performance may decrease when training and testing are performed across different sessions.

These hypotheses must be evaluated experimentally. The study must not assume in advance that any task class will or will not be classified above chance level.

## Experimental Conditions

### Baseline / Resting State

The baseline condition provides a reference measurement and a signal-quality check. It may include:

- eyes-open resting EEG
- optional eyes-closed resting EEG

The baseline can be used to observe general signal quality, possible alpha activity, and differences between rest and task periods. It should not be treated as proof that later task classifications will succeed.

### Physical Motor Execution

Physical motor execution includes:

- bilateral hand movement
- bilateral foot movement

These conditions are included as reference conditions and as a comparison against motor imagery. They may produce stronger discriminative signals than imagery, but they also introduce important limitations:

- EMG artifacts from muscle activity
- movement artifacts
- electrode or cable movement
- possible changes in contact quality

Classification of physical motor execution must therefore not automatically be interpreted as pure cortical EEG classification. Artifact contribution must be documented during analysis.

### Motor Imagery

Motor imagery includes:

- bilateral hand motor imagery
- bilateral foot motor imagery

The participant should imagine the requested movement without actually performing it. Instructions must emphasize that no visible movement should occur during motor imagery trials.

### Cognitive Tasks

Cognitive task conditions include:

- word generation
- mental subtraction

A planned word-generation implementation is to display a letter or category and ask the participant to internally generate as many words as possible. A planned mental-subtraction implementation is to provide a starting number and ask the participant to repeatedly subtract 7 mentally.

These are planned examples, not final parameters. The exact cue format and difficulty level should be finalized after pilot testing.

## Trial Structure

A preliminary generic trial structure is:

```text
Baseline / fixation
    ->
Cue
    ->
Task execution / imagery
    ->
Rest
    ->
Next trial
```

Preliminary timing values:

- baseline / fixation: 2-3 seconds
- cue: approximately 1 second
- active task: approximately 3-5 seconds
- rest: approximately 2-4 seconds

These values are preliminary and should be fixed only after pilot testing. Rest intervals may be slightly randomized to reduce temporal expectancy effects. Randomization must not make the experiment confusing for the participant.

All event timestamps must be synchronized with the EEG recording. Event markers are essential because they define the epochs used for analysis and allow the classifier to align EEG data with the intended experimental condition.

The EEG dataset must later contain markers or metadata indicating at least:

- trial start
- cue onset
- task start
- task end
- condition / class
- session
- participant identifier

## Number of Trials

The preliminary target is:

- approximately 30-50 trials per condition
- multiple blocks rather than one long continuous run
- short breaks between blocks
- randomized or counterbalanced condition order

The exact trial count should be finalized based on:

- session duration
- participant fatigue
- EEG setup time
- signal quality
- statistical requirements
- pilot study results

## Sessions

Two sessions on different days are recommended, following the logic of the reference study.

This is important to:

- test reproducibility
- assess inter-session variability
- avoid measuring only within-session patterns
- evaluate whether a model trained on session 1 generalizes to session 2

The intended cross-session evaluation is:

```text
Session 1 -> Training
Session 2 -> Independent testing
```

Within-session cross-validation can be reported as an additional metric. It should not replace cross-session evaluation, because a random train/test split from the same recording is less informative about day-to-day robustness.

## Randomization and Counterbalancing

Trials should not always appear in the same order. The class order should be randomized, while long sequences of the same task should be avoided. Block order may be counterbalanced between participants if multiple participants are recorded.

Practice trials should be performed before the actual recording so that participants understand the cues and task expectations before data collection begins.

## Participant Instructions

Instructions must be standardized across participants.

The following should be kept consistent:

- wording of task instructions
- screen distance
- posture
- cue type
- task duration
- break structure

Participants should be instructed to:

- minimize unnecessary movement
- avoid talking during recording
- avoid excessive blinking during active epochs
- remain relaxed
- perform only the requested task

For motor imagery, the participant must be told explicitly that no actual movement should occur. Movements should only be imagined.

For physical motor execution, the exact movement must be defined before recording and kept standardized across participants.

## Proposed Analysis Pipeline

A preliminary processing pipeline is:

```text
Raw EEG
    ->
Signal quality inspection
    ->
Filtering
    ->
Artifact detection / rejection
    ->
Epoching based on event markers
    ->
Feature extraction
    ->
Classification
    ->
Statistical evaluation
```

Possible preprocessing steps:

- notch filtering around 50 Hz if required by the recording environment
- band-pass filtering
- bad-channel detection
- artifact handling
- epoch extraction using synchronized event markers

Final filter settings should not be fixed until pilot data and hardware characteristics are reviewed.

For motor imagery, frequency ranges of special interest include:

- alpha / mu range around 8-12 Hz
- beta range approximately 13-30 Hz

These ranges should be evaluated empirically rather than assumed to work equally well for every participant.

## Feature Extraction

Possible initial feature-extraction approaches:

- power spectral density
- band power
- CSP
- filter-bank CSP

The reference MEG implementation uses CSP-based approaches. For this EEG study, a classical signal-processing pipeline is preferred initially because it is easier to interpret than a deep-learning pipeline and better suited to early pilot analysis.

## Classification

Possible initial classifiers:

- LDA
- SVM

The initial focus should be pairwise classification. Planned comparisons include:

- physical hands vs. physical feet
- hand imagery vs. foot imagery
- physical hand movement vs. hand imagery
- physical foot movement vs. foot imagery
- hand imagery vs. word generation
- hand imagery vs. subtraction
- foot imagery vs. word generation
- foot imagery vs. subtraction
- word generation vs. subtraction

Multiclass classification can be evaluated later, but it should not replace pairwise analysis initially.

## Evaluation Metrics

The analysis should report:

- accuracy
- balanced accuracy
- confusion matrix
- precision
- recall
- F1-score

For binary classification, ROC-AUC may also be reported.

Chance level must be considered. Classification accuracy alone is not sufficient, especially if class balance is imperfect. Class imbalance should be avoided during experiment design or compensated for during analysis.

## Scientific Interpretation

The study should report both successful and unsuccessful classification results. Meaningful outcomes include:

- physical motor execution is clearly distinguishable
- motor imagery is only moderately distinguishable
- certain cognitive tasks cannot be classified above chance level
- classification works within one session but not across sessions
- participant-specific performance differs substantially

Unsuccessful classification must not be framed as a failed experiment. It can identify limitations of the available EEG headset, task design, participant strategy, preprocessing pipeline, or classifier.

## Expected Comparison

The conceptual expected hierarchy is:

```text
Physical motor execution
    ->
Motor imagery
    ->
Cognitive tasks
```

This hierarchy is only a hypothesis. It must not be presented as a confirmed result until evaluated experimentally.

## Limitations

Important limitations include:

- EEG has lower spatial resolution than MEG.
- The EEG headset has a limited channel count.
- EEG sensor locations differ from the MEG sensor layout in the reference study.
- Actual movement can introduce EMG contamination.
- Actual movement can introduce mechanical and electrode-movement artifacts.
- Eye movements and blinking can affect active epochs.
- Participant fatigue may affect task consistency.
- EEG patterns may vary substantially between participants.
- EEG patterns may vary between sessions for the same participant.
- Individual motor-imagery ability may differ.
- Learning effects may occur between sessions.
- Sample size may be limited.
- Direct numerical comparison against MEG results may not be valid.

## Metadata Requirements

Participant and session metadata must be stored consistently. At minimum, later experiment software should preserve:

- participant identifier
- session identifier
- recording date
- condition labels
- trial numbers
- event timestamps
- EEG channels used
- sampling rate
- preprocessing version
- known recording issues
- notes about artifacts, fatigue, or protocol deviations

## Reference

Main reference:

- [MEGBCI2020 repository](https://github.com/sagihaider/MEGBCI2020)

Associated paper:

- Rathee et al. (2021), "A magnetoencephalography dataset for motor and cognitive imagery-based brain-computer interface", Scientific Data.
