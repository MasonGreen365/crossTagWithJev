# goTag

Automates tagging (identification/disambiguation) of satellites when two objects pass close together and are difficult to tell apart.

## Approach

Observation-based identification: distinguish and tag closely-spaced objects using ground-sensor data (optical photometry / light curves, angle tracks, and/or RF signatures) rather than orbital propagation alone.

## Project layout

```
src/goTag/
├── ingestion/       # sensor data intake (optical, RF, angle tracks)
├── identification/  # disambiguation / tagging algorithms
├── models/          # data models (observations, tracks, tags)
└── api/             # external interface
tests/
docs/                # architecture notes, research
data/
├── raw/
└── processed/
```

## Status

Early scaffolding — architecture still being defined.
