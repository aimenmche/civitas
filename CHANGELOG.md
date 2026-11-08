# Changelog

All notable changes to CIVITAS are recorded here. The project follows [Semantic Versioning](https://semver.org/).

## [0.3.0] — 2026-11-08

### Added

- **Emergence detector** (`GET /api/runs/{id}/emergence`): structural firsts and statistical anomalies read only from persisted `RunEvent` and `RunMetric` rows, with measured day-over-day differences and causal readings labelled as hypotheses.
- **Emergence page**: filterable findings, evidence rows, measured blocks, coverage panel and an explicit rescan.
- **Diplomacy page**: relations matrix between living polities, agreement and conflict summary, pair dossier and linked events.
- **Multiverse page**: all worlds and branches in one ancestry-indented timeline with snapshots, branch-from-snapshot and cross-run comparison.
- **Device-pixel canvas map**: terrain drawn directly to a `<canvas>` sized in device pixels, with SVG used only for markers and labels. Verified sharp at 3840×2160 with DPR 2.
- **Repository tooling**: MIT license, GitHub Actions CI (backend tests, frontend typecheck and build), screenshot gallery and `backend/.env.example`.

### Changed

- `_metric_at` in the emergence scanner now uses binary search over stored metric days (cold scan ~1.4 s, warm ~0.6 s on a 9,000-day world).
- Project version is now consistent at `0.3.0` across the API, the frontend package and the in-app engine badge.
- README quick start uses portable clone and virtual-environment commands instead of absolute Windows paths.

### Verified

- Deterministic replay, world generation, long-run survival, snapshot restore equivalence, emergence calendar rules and the main REST flow are covered by 10 passing backend tests.
- Frontend `tsc --noEmit` and `vite build` are clean, and CI runs both jobs on every push to `main`.

### Known gaps

- SQLite is the only storage backend verified end-to-end. PostgreSQL is accepted by the ORM but untested here; Redis, pgvector, Docker, Alembic migrations and a job queue are not implemented.
- The UI is desktop-first; map interaction is observation (pan, zoom, overlays, selection), not god-mode control.

[0.3.0]: https://github.com/aimenmche/civitas/releases/tag/v0.3.0
