# Forex Historical Replay — August 2026

## Purpose

Exercise the existing production-intended Forex Shadow pipeline causally for EURUSD and USDJPY over `2026-08-01T00:00:00Z <= available_at < 2026-09-01T00:00:00Z`. The accepted run used direct IFCMarkets-Demo MT5 history, no fallback, and disposable SQLite, dataset, model, source, and log storage.

This is an operational historical replay. It is not new independent ML research, a production quality gate, or evidence of expected future accuracy. No target, feature, Random Forest, decision policy, retrain cadence, Shadow contract, session authority, production gate, promotion path, activation path, or trading path was changed.

## Previous July/August Attempt

The previous July/August replay stopped correctly before training with `INITIAL_H1_SESSION_EVIDENCE_OUTSIDE_AUTHORITY_WINDOW`. Its July 1 initial 2000-H1 window reached before the IFC quote-session authority effective boundary and therefore could not classify every gap. It produced zero models, predictions, and outcomes.

The first August execution exposed a separate deterministic replay adapter defect after successful preflight and training: the Shadow CSV adapter filters the first three H1 candles following a gap, while the replay attempted prediction on every newly revealed raw H1 candle. During those filtered candles the prediction feature frame still ended at the preceding eligible candle. A later H4 context update could then produce a different score for that same candle/model ID, causing fail-closed `PersistenceConflictError: conflicting shadow prediction evidence: direction_score`.

Regression coverage was added first. The replay now records those raw H1 events as ineligible and invokes the unchanged Shadow prediction primitive only when the adapter's latest eligible H1 timestamp equals the newly revealed H1 timestamp. Target, features, filtering, decision policy, and cadence remain unchanged.

## Why August Was Selected

At the August 1 replay clock, the latest 2000 closed H1 candles begin at `2026-04-06T04:00:00Z`, equivalent to `2026-04-06T06:00:00+02:00 Europe/Berlin`. This lies wholly after the existing authority boundary `2026-03-29T00:00:00+01:00 Europe/Berlin`. No earlier session behavior was inferred and the authority window was not widened.

## Authority Preflight

The replay constructs and verifies all six initial rolling datasets before either symbol is trained. The canonical registry readiness contract is evaluated against each persisted temporary CSV. Every dataset had exactly 2000 rows, valid provenance, no blocking gap, and no readiness warning or reason.

Both H1 earliest timestamps passed the explicit authority-boundary comparison. `authority_preflight_pass=true`.

## Real-State Isolation

The accepted replay executed under `TemporaryDirectory` with a temporary SQLite database, six temporary rolling CSVs, frozen source files, temporary Shadow model storage, and a temporary log. Before capture, the CLI snapshotted the real SQLite file, six canonical datasets, two real Shadow envelopes, lifecycle evidence, live canaries, production aliases, and quarantine files. After replay and outcome maturation, `changed_paths=[]`.

The structured lifecycle/canary fingerprint was identical before and after: `e9bb567d5ab8488c119100f332d6c90f872e12ad3d2fd5e5514a292c1e8ec633`.

## Source Acquisition

The accepted run acquired all six requested sources directly through `MT5Provider` from `IFCMarkets-Demo`:

- EURUSD: H1 3600, H4 2400, D1 2100 captured rows.
- USDJPY: H1 3600, H4 2400, D1 2100 captured rows.
- Provider: MT5.
- Fallback: no.
- Yahoo, OANDA, synthetic candles, and forward fill: not used.

The accepted run captured once before preflight and did not refetch based on intermediate or predictive results. Bounding retained 3587 H1 rows per symbol, including only the minimum post-window H1 allowance; 2394 H4 and 2099 D1 rows remained before the exclusive end.

Frozen source SHA-256 values were:

- EURUSD H1 `e10734918ecabe758e49d5a9f654801ac8765e1b6f1306e95746b627a875b656`
- EURUSD H4 `584f1309da9ccccb8c7ffc06b447e1da5a01eace3f90cb31c954964a21e8951b`
- EURUSD D1 `c710f6c06f3c09b4612d3e7ab90ec1b47abbe5227a572b39c9960d486e12e853`
- USDJPY H1 `7a9087a88c1c9ad2b4f3409527f55c7684ce7ba8e2cd0115f9311d34d6248204`
- USDJPY H4 `a47ae151881153fccf7c75959560546cae01817350fd228518c879b02a0e1480`
- USDJPY D1 `7c5fb04a68d3ba5a750b64e3f62eb18e8b64b952bb107970ab25e5979c71fd89`

## Initial Six Datasets

- EURUSD H1: 2000 rows, `2026-04-06T04:00:00Z` through `2026-07-31T19:00:00Z`, ready.
- EURUSD H4: 2000 rows, `2025-04-17T10:00:00Z` through `2026-07-31T18:00:00Z`, ready.
- EURUSD D1: 2000 rows, `2018-11-13T23:00:00Z` through `2026-07-30T22:00:00Z`, ready.
- USDJPY H1: 2000 rows, `2026-04-06T04:00:00Z` through `2026-07-31T19:00:00Z`, ready.
- USDJPY H4: 2000 rows, `2025-04-17T10:00:00Z` through `2026-07-31T18:00:00Z`, ready.
- USDJPY D1: 2000 rows, `2018-11-13T23:00:00Z` through `2026-07-30T22:00:00Z`, ready.

All six passed before generation-1 training began.

## Causal Clock

Candle availability remained open timestamp plus one hour for H1, four hours for H4, and one day for D1. Equal availability instants were ordered D1, H4, then H1, with symbol as the final deterministic key. The event queue contained positions and timestamps, not future OHLC values.

All three training generations for each symbol (six total) recorded maximum feature and terminal-target timestamps at or before their replay clocks. `lookahead_violations=0`.

## EURUSD Initial Training

Generation 1 trained at `2026-08-01T00:00:00Z` using 1891 labeled rows. Its maximum feature timestamp was `2026-07-31T07:00:00Z`, its maximum terminal-target timestamp was `2026-07-31T19:00:00Z`, and its training cutoff was `2026-07-31T19:00:00Z`.

Initial model identity: `shadow_EURUSD_g0001_2ee34c9afb8e2152`.

## USDJPY Initial Training

Generation 1 trained at `2026-08-01T00:00:00Z` using 1891 labeled rows. Its maximum feature timestamp was `2026-07-31T07:00:00Z`, its maximum terminal-target timestamp was `2026-07-31T19:00:00Z`, and its training cutoff was `2026-07-31T19:00:00Z`.

Initial model identity: `shadow_USDJPY_g0001_6c21c4edb54e8e79`.

## August Event Loop

Each symbol processed 497 H1, 126 H4, and 21 D1 events. H4 and D1 updated context only. Of the 497 raw H1 events per symbol, 482 were eligible under the existing Shadow post-gap filter and produced exactly 482 persisted predictions; 15 were explicitly ineligible because the adapter filtered them. Eligible plus ineligible equals every H1 event.

At H1 the loop revealed the candle, atomically updated the rolling dataset and registry, matured eligible outcomes, applied the unchanged 168-new-H1 retrain decision, then predicted and persisted once if the current candle remained eligible. `duplicate_predictions=0` and cross-symbol source checks passed.

## Model Generations

Each symbol produced three generations: one initial generation and two cadence-driven retrains.

- Generation 1 cutoff: `2026-07-31T19:00:00Z`.
- Generation 2 cutoff: `2026-08-11T23:00:00Z`, trained at `2026-08-12T00:00:00Z` after exactly 168 new H1 candles.
- Generation 3 cutoff: `2026-08-21T01:00:00Z`, trained at `2026-08-21T02:00:00Z` after the next 168 new H1 candles.

Retraining was cadence-only, not performance-driven. Prediction records retained their original model identity and generation.

## Outcome Maturation

All August directional predictions matured at the existing terminal direction target after 12 closed H1 candles. The post-window phase revealed three H1 event rows in total, solely until no directional prediction remained pending. It generated no prediction and triggered no retraining. Pending directional outcomes at completion: zero for both symbols.

## EURUSD Results

- Total predictions: 482
- BUY / SELL / HOLD: 81 / 188 / 213
- Directional coverage: 55.8091%
- Matured BUY/SELL: 269
- Correct / incorrect: 117 / 152
- Directional accuracy: 43.4944%
- BUY precision: 35.8025%
- SELL precision: 46.8085%
- Average future return after BUY: -0.046266%
- Average future return after SELL: 0.056312%
- Median future return after BUY: -0.036043%
- Median future return after SELL: 0.006487%
- Informational sanity label: `AT_OR_BELOW_50_REFERENCE`

## USDJPY Results

- Total predictions: 482
- BUY / SELL / HOLD: 215 / 12 / 255
- Directional coverage: 47.0954%
- Matured BUY/SELL: 227
- Correct / incorrect: 153 / 74
- Directional accuracy: 67.4009%
- BUY precision: 69.7674%
- SELL precision: 25.0000%
- Average future return after BUY: 0.055553%
- Average future return after SELL: 0.179434%
- Median future return after BUY: 0.064048%
- Median future return after SELL: 0.114804%
- Informational sanity label: `ABOVE_50_REFERENCE`

## Functional Integrity

- All-six preflight: passed.
- Generation-1 training for both symbols: passed.
- Lookahead violations: 0.
- Cross-symbol contamination: 0 observed; all six sources passed symbol isolation.
- Duplicate predictions: 0.
- Eligible prediction cardinality: 482/482 for each symbol.
- t+12 maturation: all 496 directional predictions resolved; zero pending.
- Retrain cadence: two retrains per symbol at the unchanged 168-H1 boundary.
- Model identities: preserved by generation.
- Focused replay and Shadow suite: 68 passed, 0 failed.
- Full suite: 975 passed, 10 expected skips, 0 failed, 23 subtests passed.
- Warnings: 2417 pre-existing deprecation warnings; no test errors.

Operational replay: PASS. Predictive accuracy was not part of this decision.

## Predictive Descriptive Summary

EURUSD was below the 50% directional reference during this one causal month; USDJPY was above it. These are descriptive historical observations only. In particular, USDJPY directional accuracy of 67.4009% means that 153 of 227 emitted BUY/SELL actions in this replay matched the terminal direction 12 closed H1 candles later. It is not an estimate or promise of future accuracy and does not replace live Shadow observation.

The small USDJPY SELL sample (12) makes its separate SELL precision especially weak evidence. Neither symbol's replay result changes production eligibility or any quality gate.

## Real-State Postcheck

The replay's byte snapshots reported no changed path. Current canonical dataset SHA-256 values remain:

- EURUSD H1 `868eb4a92006de5c42fdd6465d923284f5d56a2448e740b1df38a9edc45d8f67`
- EURUSD H4 `9d805c070c3a3119efdd1c1823e16e732beff7d927037e7a6aa56c653ef4f66b`
- EURUSD D1 `1913093a055bfe0746b16d87305c23a5f688970538f2fab6c43240c859b49bdf`
- USDJPY H1 `b56077727c6d83199ff8e0fb9b8cf946a6002b5f5c440d5d793cda59577840a3`
- USDJPY H4 `242be7e3f4b10f3a6378dec79e6a99390e05476458a3171676a1e5562a51244d`
- USDJPY D1 `73377d27ab968e798cfe1a5806e51150cc8ee0725425fe10f229aa028d2b3506`

Real Shadow envelope hashes remain EURUSD `01308a78264c937be20ba972710be94fd67b6a4e964033a40877e24254f5edc3` and USDJPY `f1cf66ff2e1538f8566d482a18f460f53529641d8378c444e313aa88228f175c`. Live canaries and lifecycle rows were unchanged. `latest_EURUSD.pkl` and `latest_USDJPY.pkl` remain absent.

Promotion executed: no. Activation executed: no. Trading executed: no.

## Windows VM Readiness

The Windows VM is ready for the separately controlled live Shadow deployment step for EURUSD and USDJPY from an operational replay perspective. This conclusion covers pipeline causality, temporary isolation, source and symbol integrity, initial training, event processing, persistence, cadence retraining, and outcome maturation. It does not promote either model, authorize trading, or establish production predictive quality.

Remaining work is operational: deploy/observe Shadow under its existing authorization and collect genuinely forward live evidence. No ML threshold or gate change is justified by this replay.

## Decision

`FOREX HISTORICAL REPLAY PASS — WINDOWS VM SHADOW DEPLOYMENT READY`
