# Multi-Agent Area Surveillance System
## 5-Week Sprint Plan (re-scoped, implementable)

### Project Objective
Build a distributed multi-agent surveillance system where multiple camera-agents each
analyze a different point-of-view on a shared physical area, publish structured
observations, and fuse them into a single, continuously-updated **area summary**.

This builds directly on the existing **OpenClaw Vision Agent** (`core/` pipeline:
`analyze_image` → structured `VisionAnalysis`). Each camera-agent is a headless wrapper
around that same, already-tested pipeline.

### Scope decisions (what makes this 5 weeks instead of 12 months)
- **Inputs, easy → hard:** start with periodic **still frames sampled from recorded
  clips**, then recorded video files, then **live RTSP** as a stretch goal (Week 5).
- **Fusion, easy → hard:** start with **zone/location-level** fusion (Version A — "what
  is happening in each area"), then build toward **cross-camera identity tracking**
  (Version B — "track this specific person/vehicle across cameras").
- **Scale:** the real target is a convincing **5–10 feed** demo. ~100 feeds is a stretch
  target, not a hard requirement.

### Honest risk note
The hard, research-grade part is **cross-camera re-identification** (Week 4). It is
deliberately sequenced *after* a shippable zone-level product (Weeks 1–3) so the project
has a demonstrable result even if re-ID accuracy is limited.

### Technology choices (pinned)
| Concern | Choice | Why |
|---|---|---|
| Local Kubernetes | **k3d** (k3s in Docker) | Lightweight, free, fast to tear down/rebuild locally |
| Message bus | **NATS** (Helm chart) | Single lightweight binary, trivial pub/sub; Kafka's durability not needed yet |
| Per-frame perception | existing **`core.analyze_image`** (Gemini) | Already built and tested (41 tests) |
| Shared state / fusion store | **PostgreSQL** (state) + **Redis** (live snapshot) | SQL for history/queries, Redis for the fast "current area" snapshot |
| Cross-camera re-ID (Week 4) | **Torchreid / OSNet** embeddings | Purpose-built for re-ID; do NOT ask the multimodal model to re-identify people |
| Monitoring | **Prometheus + Grafana** | Standard, Helm-installable |
| Live ingest (Week 5) | **RTSP → frame sampler** | Reuses the same frame-based agent contract |

---

# Week 1: Infrastructure Foundation

## Goals
- Local Kubernetes cluster running
- Reusable headless **agent container** wrapping the existing `core/` pipeline
- NATS message bus for publishing/consuming observations
- Secrets and config managed by Kubernetes (no hardcoded credentials)

## Tasks
- Refactor the agent into a headless worker (`agent/worker.py`): subscribe to a job
  subject, call `analyze_image`, publish the structured result. Reuse `core/` as-is.
- Write a `Dockerfile` for the worker; build into the k3d local registry.
- `k3d cluster create`; install NATS via Helm.
- Deploy the agent `Deployment` with `replicas: 3`.
- Move `GEMINI_API_KEY` from `.env` into a Kubernetes `Secret`; non-secret tuning
  (model name, NATS URL, frame interval, max image size) into a `ConfigMap`.
- Add a `/healthz` endpoint; wire `livenessProbe` / `readinessProbe` (readiness also
  checks the NATS connection).

## Deliverables
- k3d cluster operational
- Single agent Docker image, run as N replicas, configured purely by env vars
- NATS message bus reachable in-cluster
- Secret + ConfigMap wired into the Deployment

## Acceptance Criteria
- `kubectl get pods` → all agent pods `Running`, probes passing
- Publishing a test message to `jobs.images` results in an observation on `observations`
  (verify with the `nats sub` CLI)
- `grep` of image/manifests confirms the API key comes only from the Secret

## Realistic effort
3–5 focused days for someone comfortable with Docker + K8s; a full week if K8s is new.
Biggest hidden cost: the first clean Docker build of a Pillow + Google-SDK Python image.

---

# Week 2: Observations & Zone-Level Fusion (Version A)

## Goals
- Define a shared **observation schema**
- Each agent samples frames from its assigned clip and publishes observations
- A **fusion service** maintains a live, per-zone area summary

## Tasks
- Define the observation schema (Pydantic + JSON on the wire):
  `camera_id`, `zone`, `timestamp`, `objects[]`, `risks[]`, `bbox[]`, `confidence`.
- Agent: sample one frame every N seconds from a clip, run `analyze_image`, publish.
- Fusion service: subscribe to `observations`, write history to **Postgres**, maintain a
  per-zone current snapshot in **Redis**.
- Minimal read API (FastAPI): `GET /area` (whole-area summary), `GET /zone/{id}`.

## Deliverables
- Versioned observation schema (shared module)
- Postgres history table + Redis live snapshot
- Query API returning a single fused area summary

## Acceptance Criteria
- Multiple agents publish observations that land in Postgres
- `GET /area` returns a fused, per-zone summary that updates as agents report
  (e.g. *"Loading dock: 2 people, 1 forklift, spill detected. Lobby: quiet."*)
- Schema validation rejects malformed observations

---

# Week 3: Multi-Feed Demo & Reliability

## Goals
- Run 5–10 feeds simultaneously (each a different POV on the area)
- Add fault tolerance and monitoring
- Produce a convincing area-awareness demo (this is the real-goal milestone)

## Tasks
- Provision 5–10 recorded clips as 5–10 agent deployments, one zone each.
- Add retries / dead-letter handling for failed `analyze_image` calls and API rate limits.
- Install Prometheus + Grafana; dashboard for observation throughput, error rate,
  per-agent liveness, end-to-end latency.
- Run a short stability test (≈1 hour) and record observation delivery rate.

## Deliverables
- Stable 5–10 agent deployment
- Retry / recovery handling for API and network failures
- Grafana monitoring dashboard
- Recorded multi-camera area-summary demo

## Acceptance Criteria
- ≈1-hour run completes with no manual intervention
- Observation delivery rate measured and reported (target >95% on the demo set)
- A single screen shows unified area understanding fused from all feeds

## Stretch
- Push replica count toward ~100 to characterize cost and rate-limit behavior (expect
  this to surface the API-cost ceiling — document it rather than fight it).

---

# Week 4: Cross-Camera Identity (Version B — Prototype)

## Goals
Begin tracking specific individuals/vehicles across cameras — starting with the easy cases.

## Tasks
- Add an appearance-embedding step (**Torchreid / OSNet**) producing a vector per
  detected person/vehicle crop.
- Associate across cameras using the *tractable* signals first:
  - overlapping camera fields of view, and
  - time + zone adjacency ("left dock 10:02 → appeared in lot 10:03").
- Store tracks (entity_id → observations over time) in Postgres.
- Surface a simple per-entity timeline in the API.

## Deliverables
- Re-ID embedding step in the agent pipeline
- Cross-camera association for adjacent/overlapping cameras
- Per-entity track timeline

## Acceptance Criteria
- Some individuals linked across 2–3 cameras
- Association accuracy reported honestly on a labeled mini-set (no inflated claims)
- Duplicate detections of the same entity reduced in the area summary

## Honest risk note
This is the most likely week to slip. General re-ID across **non-overlapping** cameras is
an open research problem; success here means "works on adjacent cameras with decent
accuracy," not "solved."

---

# Week 5: Live Video & World-Model Polish (Ambitious)

## Goals
Move one or two feeds to live video and build the area "world model" view.

## Tasks
- Add an RTSP ingest path that samples frames into the same agent contract (so live and
  recorded feeds are interchangeable).
- Build a knowledge-graph / timeline view of entities and events
  (Person X → entered → Vehicle Y → moved to → Zone Z).
- Add basic anomaly flags (e.g. entity in a restricted zone, loitering) — rule-based
  first, not learned prediction.

## Deliverables
- At least one live RTSP feed flowing through the same pipeline as recorded feeds
- Entity/event timeline ("world model") view
- Rule-based anomaly alerts

## Acceptance Criteria
- A live feed and recorded feeds appear in one unified area summary
- The timeline reconstructs a multi-camera journey for at least one tracked entity
- At least one anomaly rule fires correctly on the demo footage

## Explicitly out of scope (deferred, honestly)
- Learned movement **prediction** / risk **forecasting** (research-grade; multi-quarter)
- Fully **autonomous planning / negotiation** between agents (north-star, not 5 weeks)
- Robust re-ID across **non-overlapping** cameras at scale

---

# Final Vision (north star)

A Kubernetes-managed set of camera-agents that:
- Observe independent points-of-view on a shared area
- Publish structured observations to a common bus
- Fuse into one continuously-updated area summary (by zone first, by identity later)
- Track entities across adjacent cameras over time
- Flag anomalies and reconstruct multi-camera timelines

Weeks 1–3 deliver a shippable, demonstrable product. Weeks 4–5 push toward identity-level
awareness and live video. Prediction, negotiation, and large-scale non-overlapping re-ID
remain the longer-term roadmap beyond this sprint.
