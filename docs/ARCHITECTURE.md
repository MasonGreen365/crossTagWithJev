# goTag Architecture

## Problem

Two satellites pass close together and are hard to tell apart from ground sensors. goTag ingests observation data and tags (labels) each object correctly during the close pass, using the observations themselves — not orbital propagation/TLE correlation.

## Pipeline

```
Sensors ──▶ Ingest ──▶ Process / Identify ──▶ Store / Catalog ──▶ Serve
```

### 1. Ingest

- **Kinesis Data Streams** — primary path for continuous sensor telemetry: az/el angle tracks, photometry (light-curve) samples, RF samples. Low-latency, handles bursty high-rate streams during a close pass.
- **AWS IoT Core** — only if sensors/telescopes are edge devices speaking MQTT; routes into Kinesis. Add later if/when a real edge sensor is in play — skip for now.
- **S3 (batch)** — file-based dumps (FITS imagery, raw RF capture) where near-real-time isn't needed.

**MVP: Kinesis only.** Add IoT Core and batch S3 ingestion when a real sensor integration demands it.

### 2. Process / Identify

- **Amazon Timestream** — stores and queries angle tracks and light curves as time series; built-in interpolation/aggregation denoises sensor jitter before it hits the identification logic.
- **Lambda** — event-driven glue triggered per observation batch; runs the lightweight tagging logic or invokes a model endpoint.
- **SageMaker** (custom endpoint, not JumpStart) — only once there's a real classifier/similarity model over light-curve or RF-signature features. Not needed for the first pass — start with a hand-written heuristic (e.g. feature-vector distance) in Lambda, promote to SageMaker once there's training data and the heuristic plateaus.

### 3. Store / Catalog

- **DynamoDB** — tag registry: object ID ↔ label ↔ confidence ↔ timestamp. Low-latency lookups for "which object is this."
- **S3 + Glue/Athena** — raw observation archive and historical batch analysis. **Defer** until there's enough historical data to justify it.

### 4. Serve

- Not yet designed — depends on consumer (dashboard? API for an external SSA system?). Revisit once ingest/identify is working end-to-end.

## Explicitly out of scope

- **AWS Ground Station** — antenna-as-a-service for commanding/downlinking *your own* satellite. Does not apply to passively observing/identifying *other* objects from the ground. Confirmed not a fit.
- **Rekognition** — tuned for natural image content (faces/objects/text), not point-source photometry. A custom model is needed instead if optical features are used.
- **Orbital propagation (SGP4/TLE correlation)** — explicitly not the chosen approach; this project disambiguates from observation data (photometry/angle/RF), not predicted trajectories.

## Reference points

- AWS's Aerospace & Satellite solutions material cites **LeoLabs** and **Kayhan Space** as real-world space-situational-awareness (SSA) companies running tracking/identification on AWS HPC/AI/ML — worth studying their public talks/case studies for sensor-fusion pattern ideas. No public AWS reference architecture diagram exists specifically for SSA object tagging.
- An "Electro-Optical Imagery Reference Architecture" exists but targets Earth-observation imagery processing, not object tracking — adjacent, not directly reusable.

## Build order (recommended)

1. Define the observation data model (`src/goTag/models`) — what a single sensor reading looks like per modality (optical photometry point, angle-track point, RF sample).
2. Stand up Kinesis ingest + a Lambda consumer that writes to Timestream, with synthetic/sample data first (no real sensor yet).
3. Write the first tagging heuristic in `src/goTag/identification` against Timestream data; register tags in DynamoDB.
4. Only then evaluate whether a SageMaker model is warranted.
