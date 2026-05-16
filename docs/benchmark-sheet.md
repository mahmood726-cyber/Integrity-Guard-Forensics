# Integrity Benchmark Sheet (v1.0)

This benchmark sheet is used to evaluate project adherence to the core rigor and integrity mandates defined in the `gemini-rigor-framework`.

## Evaluation Date: May 5, 2026
## Portfolio Snapshot: Q2 2026

| Project | Anti-Simulation & Data | Process & Multi-Agent | UI & Dashboard Rigor | Total Compliance |
| :--- | :---: | :---: | :---: | :---: |
| `OutcomeReportingBias` | [x] Pass | [x] Pass | [x] Pass | 100% |
| `OverlapDetector` | [x] Pass | [x] Pass | [x] Pass | 100% |
| `PredictionGap` | [x] Pass | [x] Pass | [x] Pass | 100% |
| `MetaReproducer` | [x] Pass | [x] Pass | [x] Pass | 100% |

---

## 1. Anti-Simulation & Data Integrity
*Mandate: Zero hardcoding and live evidence ingestion.*

- [ ] **Zero Hardcoding**: No research values (HRs, N, p-values) hardcoded in source files.
- [ ] **Live Bridge**: Programmatic ingestion from E156 workbook or data lakehouse.
- [ ] **Safe Arithmetic**: Use of null-safe transforms and explicit denominators.
- [ ] **Schema Integrity**: Logic tied to explicit metadata/headers, not magnitude guesses.

## 2. Process & Multi-Agent Safety
*Mandate: Stable execution in concurrent agent environments.*

- [ ] **Browser Rotation**: Uses `browser_rotator.py` or equivalent for all Selenium/Playwright tests.
- [ ] **No Global Kills**: Uses `driver.quit()` in `try/finally`; avoids `taskkill`.
- [ ] **Isolated Temp Dirs**: Projects use unique, non-colliding temporary directories.
- [ ] **Uptime Verification**: Servers use `Test-NetConnection` or similar before test execution.

## 3. UI & Dashboard Rigor
*Mandate: Resilient and state-aware visualization.*

- [ ] **State Scope**: Global data declarations before fetch/event listeners.
- [ ] **Event Delegation**: Listeners attached to stable parent elements for dynamic content.
- [ ] **Chart Lifecycle**: Proper destruction of Chart.js instances before reuse.
- [ ] **ID Audit**: Verified mapping between HTML identifiers and JS selectors.
