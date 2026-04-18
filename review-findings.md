## REVIEW CLEAN
## Multi-Persona Review: Evidence-Integrity-Guard
### Date: 2026-04-01
### Reviewers: Statistical Methodologist, Security Auditor, UX/Accessibility, Software Engineer, Domain Expert
### Summary: 17 P0, 25 P1, 18 P2 → ALL P0 FIXED, ALL P1 FIXED, 14/18 P2 FIXED
### Test suite: 86/86 pass (was 5/5)

---

#### P0 -- Critical (Must Fix Before Any Use)

##### Statistical / Mathematical

- **P0-1** [Stat+Domain]: Benford's Law threshold 6.7x too lenient -- nearly useless as detector (`scientific_integrity_forensics.py:63`)
  - MAD threshold of 10.0% vs Nigrini (2012) nonconformity cutoff of 1.5%. Heavily fabricated data (chi-sq=106) produces MAD=8.87% -- NOT flagged.
  - Suggested fix: Replace ad-hoc MAD with chi-square goodness-of-fit test (8 df). At minimum lower threshold to 1.5%.

- **P0-2** [Stat]: PlausibilityEngine uses normal CDF instead of t-CDF -- false accusations for small samples (`plausibility_engine.py:36`)
  - For n1=n2=5 (df~8), normal CDF gives p-values ~50-60% of true t-distribution values. Legitimate small-sample studies will be falsely flagged as IMPLAUSIBLE.
  - Suggested fix: Use scipy.stats.t.cdf or implement proper incomplete beta function. Also seed the RNG deterministically.

- **P0-3** [Stat+Domain]: Fabricated defaults (SD=5.0, N=50) fed to Carlisle fraud test (`fraud_lead_generator.py:95-96`)
  - When CT.gov data lacks "spread" or denominator fields (common), arbitrary defaults are silently substituted. The Carlisle test then produces "MANIFEST FRAUD" verdicts based on numbers the tool invented.
  - Suggested fix: Skip baseline variables where SD or N is missing. Never substitute defaults in a forensic pipeline.

- **P0-4** [Domain]: GRIM test applied to continuous data produces false positives (`scientific_integrity_forensics.py:13-38`)
  - GRIM only applies to integer-count data (Likert, binary). Applying it to blood pressure, heart rate, weight is methodologically invalid. The sample data bundles demonstrate this exact error (heart rate).
  - Suggested fix: Add mandatory `data_type` field; only run GRIM when `data_type == "integer_count"`. Return INCONCLUSIVE otherwise.

- **P0-5** [Domain]: P-curve analysis has no independence validation (`p_curve_analyzer.py:14-46`)
  - Simonsohn et al. (2014) requires p-values from INDEPENDENT tests. Tool accepts any list with no validation. Dependent p-values (correlated endpoints, multiple timepoints) violate the fundamental assumption.
  - Suggested fix: Add documentation requirement for independence; warn when p-values come from the same study.

- **P0-6** [Stat]: P-Curve 50% false positive rate under null (`p_curve_analyzer.py:31-35`)
  - The `high_count >= low_count` criterion has ~50% FPR under uniform H0. The 2-bin approach is not the published Simonsohn method.
  - Suggested fix: Add a binomial test at minimum; better: implement the formal pp-value method.

##### Language / Ethics

- **P0-7** [Domain]: "PROSECUTION: MANIFEST FRAUD" language constitutes defamation risk (`fraud_lead_generator.py:130,139`, `baseline_balance_engine.py:99`)
  - "PROSECUTION", "MANIFEST FRAUD", "MATHEMATICALLY IMPOSSIBLE" are legally conclusory terms. Statistical anomalies have multiple innocent explanations (adaptive randomization, stratification, transcription errors). Carlisle himself warns against standalone fraud determination.
  - Suggested fix: Replace with "Statistical anomaly requiring investigation", "Unusual baseline balance pattern". Remove all "prosecution"/"fraud" labels from automated output.

- **P0-8** [Domain]: No disclaimers about tool limitations anywhere in output
  - No HTML report, JSON bundle, letter, or README contains any disclaimer about false positive rates, requirement for expert human review, or the fact that statistical anomalies ≠ fraud.
  - Suggested fix: Add prominent disclaimer to every output: "This is a screening tool. Statistical anomalies do not indicate fraud. Expert human review is required."

- **P0-9** [Domain]: Automated accusatory letters generated without human gate (`inquiry_generator.py`, `openclaw_pipeline.py:163-166`)
  - Pipeline auto-generates and saves Letters to the Editor accusing researchers of reporting violations. No human review step between "anomaly detected" and "letter drafted." Violates COPE/ICMJE principles for handling misconduct allegations.
  - Suggested fix: Generate letters as DRAFTS requiring explicit human approval. Add prominent "DRAFT — NOT FOR SENDING WITHOUT EXPERT REVIEW" header.

- **P0-10** [Domain]: Author portfolio scanning = fishing expedition risk (`author_auditor.py`)
  - Searches by free-text name (not ORCID), returns trials by different people with same name, hardcodes real researcher names in `__main__`. No mechanism to confirm trial authorship.
  - Suggested fix: Require ORCID for author identification. Remove hardcoded real names. Add warnings about fishing expedition risks.

##### Security

- **P0-11** [Security]: CSS class injection via `rob_color` enables visual spoofing (`html_reporter.py:35-37`)
  - `rob_color` from JSON report can inject arbitrary Tailwind classes (e.g., making "High Risk" appear green/Low). `html.escape()` does not prevent space-separated class injection.
  - Suggested fix: Validate `rob_color` against allowlist: `{"green", "yellow", "red", "gray"}`.

- **P0-12** [Security]: Bare `except: pass` silently swallows all errors (`fraud_lead_generator.py:100`)
  - Swallows SystemExit, KeyboardInterrupt, MemoryError. Malformed data produces empty payload → fraudulent trial passes undetected.
  - Suggested fix: `except (ValueError, KeyError, TypeError) as e: logger.warning(...)`.

- **P0-13** [Security]: Infinite retry loop in mass scanner (`mass_scanner.py:61-64`)
  - On persistent network failure, loops forever with no retry limit. Catches all Exception types, hiding programming bugs.
  - Suggested fix: Add max retry counter (3-5), catch `requests.exceptions.RequestException` specifically.

##### Software / Architecture

- **P0-14** [SWE]: Non-deterministic PlausibilityEngine violates forensic reproducibility (`plausibility_engine.py:23-24`)
  - Uses unseeded `random.gauss()`. Same input produces different PLAUSIBLE/IMPLAUSIBLE verdicts on each run. Forensic results must be reproducible.
  - Suggested fix: Accept optional seed parameter; create `random.Random(seed)` instance; default to deterministic seed.

- **P0-15** [SWE]: Inconsistent `confidence` field across discrepancy types (`discrepancy_engine.py:80 vs 90`, `ai_reviewer.py:44`)
  - OUTCOME_ADDED has `confidence` key; OUTCOME_MISSING does not. Downstream modules default missing confidence to 1.0, biasing AI reviewer toward auto-CONFIRMED for missing outcomes and displaying "100%" in dashboards for items that never had a confidence score.
  - Suggested fix: Define a Discrepancy dataclass/TypedDict. Always set `confidence` explicitly.

- **P0-16** [SWE]: RoB assessment computed twice with state divergence (`openclaw_pipeline.py:139,170`)
  - First RoB call at line 139 goes into TruthCert bundle. Discrepancies are then mutated (reviews/consensus_status added). Second RoB call at line 170 goes into UI report. Results can differ.
  - Suggested fix: Compute RoB assessment once, after all mutations complete.

- **P0-17** [UX]: Stale sample HTML files contain `{len(discrepancies)}` literal text
  - Multiple shipped dashboard files display `{len(discrepancies)}` instead of the actual count. Immediately undermines credibility.
  - Suggested fix: Regenerate all sample HTML files with current code. Already caught by existing test.

---

#### P1 -- Important (Should Fix Before Release)

##### Statistical

- **P1-1** [Stat]: Baseline balance t-CDF approximation badly wrong for small df (`baseline_balance_engine.py:38-46`)
  - For df=1, p-values off by 2-8x. For df=2, off by 2-11x. Conservative direction (misses real fraud, won't produce false accusations).
  - Suggested fix: Use regularized incomplete beta function or scipy.stats.t.cdf.

- **P1-2** [Stat]: Baseline balance zero-SD with different means returns p=1.0 (`baseline_balance_engine.py:26-27`)
  - If sd1=sd2=0 but m1≠m2 (impossible data), code returns p=1.0 instead of flagging impossibility.
  - Suggested fix: If `se == 0` and `mean1 != mean2`, return `p = 1e-15`.

- **P1-3** [Stat+Domain]: Discrepancy engine 0.8 similarity threshold creates systematic false misses (`discrepancy_engine.py:72`)
  - "All-cause mortality" vs "Mortality (all causes)" → 0.44 similarity → FALSE MISS. "CV death" vs "Cardiovascular death" → 0.57 → FALSE MISS. All abbreviations (MACE, MI, OS, PFS) fail.
  - Suggested fix: Lower threshold to ~0.6; add medical abbreviation dictionary; use token-set similarity as complement.

- **P1-4** [Stat+Domain]: RoB mapper excludes DISPUTED status entirely from risk assessment (`rob_mapper.py:27`)
  - DISPUTED = reviewers disagree. Treating it as resolution (same as FALSE_POSITIVE) is overly generous. Cochrane convention: disagreement → at least "Some Concerns."
  - Suggested fix: Keep DISPUTED in active set weighted lower; floor at "Some Concerns" if any DISPUTED exist.

- **P1-5** [Domain]: Hard/surrogate endpoint lists severely incomplete (`discrepancy_engine.py:26-29`)
  - Missing: MACE, HF hospitalization, CV death, PFS, DFS, ORR, eGFR, NT-proBNP, LVEF, HbA1c, many more.
  - Suggested fix: Expand to top 50 endpoint families in cardiology/oncology.

- **P1-6** [Domain]: No timeframe comparison in outcome matching (`discrepancy_engine.py:49-100`)
  - "Overall Survival at 24 months" → "Overall Survival at 12 months" matches at >0.8 but the timeframe switch changes clinical interpretation fundamentally.

- **P1-7** [Domain]: Multi-arm trial data silently discarded (`fraud_lead_generator.py:88-99`)
  - Only compares first 2 measurement groups. Multi-arm trials have 3+ arms; pairwise comparisons missed.
  - Suggested fix: Generate all C(k,2) pairwise comparisons.

- **P1-8** [Domain]: Mass scanning with no multiple-testing correction (`mass_scanner.py`)
  - 500K+ trials × 0.1% FPR = ~500 false fraud accusations. No Bonferroni/FDR correction.
  - Suggested fix: Add FDR correction; report expected false positive count alongside results.

- **P1-9** [Domain]: All findings mapped only to RoB Domain 5 (`rob_mapper.py:6-7`)
  - Baseline anomalies → Domain 1. GRIM failures → Domain 4. Missing outcomes → Domain 3. P-curve → Domains 4+5.
  - Suggested fix: Route different forensic findings to appropriate RoB domains.

- **P1-10** [Domain]: P-curve minimum sample of 3 is too low (`p_curve_analyzer.py:21`)
  - Simonsohn et al. recommend ≥5-20 p-values. With n=3, false positive rate is unacceptable.
  - Suggested fix: Raise minimum to ≥5.

##### Security

- **P1-11** [Security]: No request timeouts in ct_history_fetcher.py (`ct_history_fetcher.py:22,43`)
  - All requests.get() calls have no timeout. Can hang indefinitely.
  - Suggested fix: Add `timeout=30` to all requests calls.

- **P1-12** [Security]: No request timeouts in fraud_lead_generator.py and author_auditor.py
  - Same issue as P1-11 in two additional files.

- **P1-13** [Security]: TruthCert signature is placeholder -- bundles forgeable (`truthcert_builder.py:49`)
  - Hardcoded `"SIG_RSA_SHA256_..."`. Any adversary can forge bundles.
  - Suggested fix: Compute HMAC over bundle contents at minimum.

- **P1-14** [Security]: TruthCert cert_id uses predictable timestamp (`truthcert_builder.py:13`)
  - Suggested fix: Use `secrets.token_hex(8)`.

- **P1-15** [Security]: NCT ID not validated before URL interpolation (`ct_history_fetcher.py:20,37`)
  - Suggested fix: Validate with `re.match(r'^NCT\d{8,11}$', nct_id)`.

- **P1-16** [Security]: No schema validation on loaded report.json (`review_tool.py`, `ai_reviewer.py`, `html_reporter.py`)
  - Malicious/corrupted JSON with unexpected types causes unhandled TypeError.
  - Suggested fix: Add lightweight schema check after loading.

##### Software / Architecture

- **P1-17** [SWE]: `ensure_parent_dir()` duplicated in main.py and openclaw_pipeline.py
  - Suggested fix: Extract to shared utils.py.

- **P1-18** [SWE]: `_update_consensus()` duplicated in review_tool.py and ai_reviewer.py
  - Divergence risk on consensus logic changes.
  - Suggested fix: Extract to shared module.

- **P1-19** [SWE]: No `__init__.py` -- 7 files use `sys.path.append` hacks
  - Suggested fix: Proper package structure with pyproject.toml.

- **P1-20** [SWE]: No requirements.txt or pyproject.toml
  - Suggested fix: Create with `requests>=2.28.0`, `pytest>=7.0.0`.

- **P1-21** [SWE]: openclaw_pipeline.py has no error handling on file load (line 40-44)
  - Crashes with unhelpful traceback on missing/invalid JSON.
  - Suggested fix: Wrap in try/except with specific error messages.

- **P1-22** [SWE]: main.py/openclaw_pipeline.py shell out to html_reporter.py via subprocess (`main.py:116`, `openclaw_pipeline.py:194`)
  - Fragile, loses tracebacks, unnecessary. HTMLReporter can be imported directly.
  - Suggested fix: `from html_reporter import HTMLReporter; HTMLReporter(path, html).generate()`.

- **P1-23** [SWE]: `type` field overloaded with "HARKING_RISK:" prefix (`main.py:78`)
  - Downstream `==` checks miss prefixed types; `in` checks work by accident.
  - Suggested fix: Add separate `"harking_risk": True` boolean field.

- **P1-24** [SWE]: Timestamps use `datetime.now()` everywhere -- non-reproducible outputs
  - Suggested fix: Accept optional timestamp parameter for deterministic mode.

- **P1-25** [SWE]: historical_validation.py is not a pytest file
  - Uses print/manual checking, not discovered by pytest.
  - Suggested fix: Convert to proper test_ prefixed functions with assert statements.

##### UX / Accessibility

See P2 section for UX items that were not P0.

---

#### P2 -- Minor (Nice to Fix)

- **P2-1** [UX]: RoB traffic light color-only, no ARIA labels (`html_reporter.py:78-82`)
  - Add `role="img"`, `aria-label`, sr-only text.

- **P2-2** [UX]: Status badges use jargon (FALSE_POSITIVE, IN_PROGRESS) (`html_reporter.py:116,144`)
  - Map to human-readable labels. IN_PROGRESS falls through to green badge (wrong color).

- **P2-3** [UX]: Emoji icons (✅❌⚠️) inaccessible to screen readers (`html_reporter.py:174`)
  - Wrap in `<span role="img" aria-label="...">`.

- **P2-4** [UX]: No landmark roles `<main>`, `<section>` (`html_reporter.py:53-189`)

- **P2-5** [UX]: Table lacks `scope`, `caption` (`html_reporter.py:94-124`)

- **P2-6** [UX]: CLI off-by-one: "Discrepancy 0/2" instead of "1 of 3" (`review_tool.py:30`)

- **P2-7** [UX]: Invalid CLI input silently maps to CONFIRMED (`review_tool.py:43-45`)
  - Typing "X" defaults to CONFIRMED. Add input validation loop.

- **P2-8** [UX]: Table not scrollable on mobile; 32px padding too wide (`html_reporter.py:92-125`)

- **P2-9** [UX]: Unconditional "..." truncation even for short outcome names (`html_reporter.py:113`)

- **P2-10** [UX]: `target="_blank"` without `rel="noopener noreferrer"` (`html_reporter.py:69`)

- **P2-11** [Stat]: Duplicate key in test data -- m2 defined twice, m1 missing (`baseline_balance_engine.py:114`)

- **P2-12** [Stat]: P-curve minimum 3 p-values too few for reliable conclusion

- **P2-13** [Stat]: Linguistic forensics single-word matching can't match multi-word phrases (`linguistic_forensics.py:35`)

- **P2-14** [Security]: AI reviewer opens files without `encoding='utf-8'` (`ai_reviewer.py:9,65`)

- **P2-15** [Security]: External CDN dependency with no SRI hash (`html_reporter.py:48`)

- **P2-16** [SWE]: Only 5 tests for 18 modules (~28% file coverage)

- **P2-17** [SWE]: `logging.basicConfig` at import time in library modules (`ct_history_fetcher.py:7`, `discrepancy_engine.py:7`)

- **P2-18** [Domain]: AI Reviewer blanket-dismisses adverse events as false positives (`ai_reviewer.py:46-48`)

#### False Positive Watch
- Fisher's method using `log(1-p)` in baseline_balance_engine.py:82 is CORRECT for detecting too-perfect balance (verified by Statistical Methodologist)
- GRIM tolerance formula `0.5 / (10^precision) * n` matches published Brown & Heathers (2017)
- Welch-Satterthwaite df formula is correctly computed
- Wilson-Hilferty chi-square approximation is adequate for typical df ranges (10-40)

---

### Recommended Fix Order

**Phase 1 -- Safety (before any use):**
1. P0-7: Replace all "PROSECUTION"/"FRAUD"/"IMPOSSIBLE" language with neutral scientific terms
2. P0-8: Add disclaimers to every output format
3. P0-9: Add human gate to letter generation
4. P0-3: Remove fabricated defaults (SD=5.0, N=50) -- skip missing data
5. P0-4: Add GRIM applicability guard (integer-count only)
6. P0-12: Replace bare `except: pass` with specific exception handling
7. P0-14: Seed the PlausibilityEngine RNG deterministically

**Phase 2 -- Correctness (before release):**
8. P0-1: Fix Benford's threshold (use chi-square test)
9. P0-2: Replace normal CDF with proper t-CDF in PlausibilityEngine
10. P0-5/P0-6: Fix p-curve (independence check, binomial test, raise minimum to 5)
11. P0-15: Define Discrepancy schema, always set confidence
12. P0-16: Compute RoB assessment once
13. P1-3: Improve outcome matching (lower threshold, synonym dictionary, abbreviation expansion)

**Phase 3 -- Infrastructure:**
14. P1-19/P1-20: Package structure + requirements.txt
15. P1-22: Import HTMLReporter instead of subprocess
16. P1-17/P1-18: Extract duplicated functions
17. P2-16: Expand test coverage to core analytical engines

**Phase 4 -- Hardening:**
18. All remaining P1 security items (timeouts, NCT validation, cert signing)
19. All P2 accessibility items
20. All remaining P2 items
