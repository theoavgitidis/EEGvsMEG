# Planned Experiments

The study will investigate how well different motor and cognitive tasks can be distinguished using an EEG headset. The experimental design is based on the tasks used in the MEGBCI2020 dataset.

## Reference Tasks

The original MEG study contains four main mental imagery tasks:

- Both hand motor imagery
- Both feet motor imagery
- Word generation
- Mental subtraction

The goal is to reproduce these task categories as closely as possible with the available EEG hardware.

## Experimental Conditions

In addition to the original mental imagery tasks, the motor tasks will also be physically executed.

The planned conditions are therefore:

1. Physical hand movement
2. Hand motor imagery
3. Physical feet movement
4. Feet motor imagery
5. Word generation
6. Mental subtraction

The physical motor conditions are added to provide a stronger reference signal and to compare actual movement with imagined movement.

## Main Goal

The main objective is to determine which of these task types can be reliably distinguished using the EEG headset.

The study should compare:

- Physical motor activity vs. motor imagery
- Hand-related vs. feet-related activity
- Motor imagery vs. cognitive imagery
- Word generation vs. mental subtraction
- Overall classification performance across all task categories

## Hypothesis

It is expected that the tasks will differ in how reliably they can be identified from EEG data.

The expected order is roughly:

1. Physical motor movements
2. Motor imagery
3. Cognitive imagery tasks

Physical movements are expected to produce the clearest measurable differences, while cognitive tasks such as word generation and mental subtraction may be more difficult to distinguish with the available EEG setup.

This is only a hypothesis and must be evaluated experimentally.

## Scientific Purpose

The study should not only demonstrate which tasks can be classified successfully, but also identify the limitations of the EEG system.

A relevant outcome would therefore also be that certain tasks cannot be reliably distinguished.

The experiments will be used to evaluate to what extent the MEGBCI2020 experimental paradigm can be transferred from MEG to a practical EEG setup.

## Planned Documentation

For every experiment, the following should later be documented:

- Task description
- Instructions given to the participant
- Trial structure
- Cue timing
- Task duration
- Rest duration
- Number of repetitions
- EEG channels used
- Sampling rate
- Preprocessing steps
- Artifact handling
- Feature extraction
- Classification method
- Evaluation metrics
- Results and limitations
