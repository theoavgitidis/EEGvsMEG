# Planned EEG Experiments

This folder documents the planned experimental design for an EEG study inspired by the MEGBCI2020 project. The central scientific question is:

> To what extent can different motor and cognitive imagery tasks be reliably distinguished and classified using EEG signals?

The study does not claim to directly replicate the MEGBCI2020 dataset. Instead, it adapts the experimental paradigm from a high-density MEG setup to a practical EEG headset. Because MEG and EEG measure related but physically different signals, classification results should be interpreted as EEG-specific findings.

The main focus is to compare physical motor execution, motor imagery, and cognitive tasks. Physical motor movements are included as reference conditions so that executed movement can be compared with imagined movement. The study should also identify limitations of the EEG setup. A result where a task cannot be classified above chance level is still scientifically valid, because it helps define what the available system can and cannot measure reliably.

The exact trial timings, number of repetitions, and analysis parameters are preliminary. They should be adjusted after pilot measurements, signal-quality checks, and participant-fatigue assessment.

## Documentation Files

- [Study design](studyDesign.md)
- [Baseline / resting state](baseline.md)
- [Physical motor tasks](physicalMotorTasks.md)
- [Hand motor imagery](motorImageryHands.md)
- [Foot motor imagery](motorImageryFeet.md)
- [Word generation](wordGeneration.md)
- [Mental subtraction](mentalSubtraction.md)

## Condition Overview

| Condition | Type | Description |
|---|---|---|
| Baseline | Reference | Resting EEG, optionally eyes open / closed |
| Physical hand movement | Motor execution | Actual bilateral hand movement |
| Physical foot movement | Motor execution | Actual bilateral foot movement |
| Hand motor imagery | Motor imagery | Imagine bilateral hand movement without executing it |
| Foot motor imagery | Motor imagery | Imagine bilateral foot movement without executing it |
| Word generation | Cognitive task | Internally generate words |
| Mental subtraction | Cognitive task | Repeated subtraction from a starting value |

## Reference

The main reference is the [MEGBCI2020 repository](https://github.com/sagihaider/MEGBCI2020) and the associated paper:

Rathee et al. (2021), "A magnetoencephalography dataset for motor and cognitive imagery-based brain-computer interface", Scientific Data.
