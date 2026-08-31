# EURUSD Nested WFV Tuning

## Baseline

The controlled run started from branch
`fix/wfv-aligned-hyperparameter-tuning` at source HEAD
`0e48c27c0e0608f9d005d703816df08e7b9a2ce1`, with a clean tracked working
tree. UTF-8 strict mode was active for stdout and stderr, and the required
Unicode smoke test passed.

EURUSD started and ended as `qualified`. `latest_EURUSD.pkl` was absent,
model provenance, retrain runs, and H1 model-quality rows were all zero.
No provider fetch, prediction, activation, trading, scheduler cycle, or
canonical update was executed.

The exact training matrix contained 1,756 rows, 1,756 targets, and 87
features, including 10 `h4_*` and 9 `d1_*` features. The existing horizon 12
and risk/reward ratio 1.0 were unchanged.

## Snapshot

`capture_training_snapshot("EURUSD")` and the validation performed both
before and immediately after acquiring the H1/H4/D1 locks reproduced the
authorized SHA-256:

`f4e77d47ab061f72a65ceb0d7733ba6d026422795119566eb5433180c5b1a3d2`

The snapshot lock covered dataset loading, feature/target construction, and
the complete inner search. The run stopped at the inner gate, so no
before-promotion revalidation was applicable.

## Tuning Isolation

Exactly one `tune_wfv_aligned()` invocation was made with 50 trials,
`timeout=None`, `persist=False`, and `use_cache=False`. The legacy `tune()` API
was not called. Seed 42 was used.

The geometry was computed from the current 1,756-row matrix and cross-checked
against `WalkForwardValidator.split_positions()`. The tuning pool was
`[0,980)`. Outer validation rows `[1020,1320)` and `[1320,1620)` were reserved
and were never used by the inner search.

## Inner Geometry

The dynamically returned inner folds were:

- fold 1: train `[0,480)`, validation `[520,720)`
- fold 2: train `[200,680)`, validation `[720,920)`

Each validation contained 200 rows and therefore required at least 20
directional signals. Every trial produced zero signals in fold 2. Consequently
all 50 trials were evidence-insufficient, regardless of fold-1 performance.

## Optuna Search

All 50 requested trials completed. The lines below contain only the safe
per-trial summary; no complete non-selected parameter dictionary is recorded.
`evidence` and `pass` refer to inner evidence sufficiency and inner WFV.

```text
00 sha=dad9e16ef9805686802b893238a29d36c51d130bd243229ee5c104ad969d7831 obj=-1.000000 f1(sig=129 prec=39.534884% acc=45.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
01 sha=d11eccc0826358d0dcc08d8a1c8fd981d4f92cbefe35f042600ca3ffe5e436ef obj=-1.000000 f1(sig=82 prec=39.024390% acc=50.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
02 sha=cb0c7bc1dc1d5d75c49438d512895dd27f216c7ba1e6d911f5b867d31fce855f obj=-1.000000 f1(sig=70 prec=40.000000% acc=52.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
03 sha=73798e4dcbb9556edda1e65f65b8c544b4b34a8ce6f542027af2fa069b15e164 obj=-1.000000 f1(sig=78 prec=39.743590% acc=51.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
04 sha=5c47a4fe34e1b808e3f78cd315bf6899e07a3125a4c52a8b6b54e4de7b425d01 obj=-1.000000 f1(sig=134 prec=42.537313% acc=49.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
05 sha=c14b007448f02c37cf7dcdd59aa2b61821ad3fc5b82a0dd4d9f5820578e56309 obj=-1.000000 f1(sig=94 prec=45.744681% acc=55.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
06 sha=001ad8fdf94831c3ff5e0aceaf4f67e16f7553de491e99f5522a3e0be6888b1d obj=-1.000000 f1(sig=74 prec=37.837838% acc=50.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
07 sha=3093401932ab9ed330b35fd4db03f67a8c7bc24fba6d060fe97239a8e58f36f1 obj=-1.000000 f1(sig=102 prec=39.215686% acc=48.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
08 sha=a6e2b947163313e5b394c5fae56ae51451604ffd9ebd3a32f4d52bc78007658c obj=-1.000000 f1(sig=99 prec=37.373737% acc=46.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
09 sha=500be6ce45e32c4edadb13be641a6d50329d671b442cdffe0f9ef1b75257a651 obj=-1.000000 f1(sig=132 prec=42.424242% acc=49.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
10 sha=30e4ac118a0e43edca0ab589ee1151986ec32aabd7eba19608ad5c6bd91cd826 obj=-1.000000 f1(sig=73 prec=39.726027% acc=51.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
11 sha=c448dec3a6d68351b0b7832c4c57d70d300b47683e885e9e48b7ff0936352f47 obj=-1.000000 f1(sig=56 prec=41.071429% acc=54.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
12 sha=0681f231619ce601097087a27c11bcf70dc7922b4c5d27ecc6812ba7673d62dd obj=-1.000000 f1(sig=126 prec=42.063492% acc=49.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
13 sha=17ba6f6d3e33dbdc257502e12516981e166ef3e9217a5f2e3e2140595938407d obj=-1.000000 f1(sig=56 prec=41.071429% acc=54.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
14 sha=336ad4f33cf62330c050e20212ade8575076500b06bb72293d804831861607b2 obj=-1.000000 f1(sig=80 prec=40.000000% acc=51.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
15 sha=c09f09bb1ee47228f0f36d555a9790671673edf19b54a323da8eb20ad3901a5f obj=-1.000000 f1(sig=64 prec=40.625000% acc=53.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
16 sha=933aff7c4e185ea9a34aeeaa5c4219486e7613aadd787a033c03554887c86b99 obj=-1.000000 f1(sig=141 prec=43.971631% acc=50.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
17 sha=1b74dcc89967b2684fa3d0ed1a40da1dc33d74938c02d8513d75d4f02896bf3e obj=-1.000000 f1(sig=88 prec=37.500000% acc=48.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
18 sha=6bd7555ef32c7f340293417bd8d5e047bb1111c93787fa8f196fb7693e2b8d47 obj=-1.000000 f1(sig=96 prec=38.541667% acc=48.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
19 sha=02ebe1fc6552311bbd20cdc1aa548cbb2b157011e62d35024633062d2828e576 obj=-1.000000 f1(sig=79 prec=36.708861% acc=48.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
20 sha=5ac1f3dc507d0290586499d39aa564b8cd2a445fdfc17d7928b7b0d896bc0fc2 obj=-1.000000 f1(sig=72 prec=41.666667% acc=53.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
21 sha=680da962a9754adcca1bf8c1a21d3d0835424e719517022d0a4892ec3c636207 obj=-1.000000 f1(sig=97 prec=42.268041% acc=51.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
22 sha=ce3c64ebaf2d2d3f5ab3a831920ddd091bb202840e9572dd4e9690fb901e48dc obj=-1.000000 f1(sig=101 prec=42.574257% acc=51.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
23 sha=4b2708ce31d3c0b6785caa9cc58e5f45e986fe91e0b934e50150c69775577d6c obj=-1.000000 f1(sig=91 prec=43.956044% acc=53.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
24 sha=f92a719a64321ae169cbdc8ef2eb6f43ee514769eda9dec9c52d19bda70ecd5e obj=-1.000000 f1(sig=119 prec=39.495798% acc=46.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
25 sha=c7c69f589349d6cb90bc60522f25129c43b933a8cb676a8425d4150ce5061f7a obj=-1.000000 f1(sig=127 prec=38.582677% acc=44.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
26 sha=0306a2e4fc9b1052c2dc737ad8eb1c0bbd77fb96356fb51650cbc0492e871ca7 obj=-1.000000 f1(sig=92 prec=39.130435% acc=49.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
27 sha=f4f0275fe46aed3eac1a4541737da17e3941a9c026abe2b773bf8c6f25cff9c3 obj=-1.000000 f1(sig=114 prec=41.228070% acc=49.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
28 sha=aa4ec58bea983fa152ed5d8ce5751b1a9cc110bb8efae0378390cc5873fbbc22 obj=-1.000000 f1(sig=105 prec=43.809524% acc=52.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
29 sha=8c60e9fc6d89fdffce5562cad285a6e751d2a39ce3184dab51271a7c2ecfec1c obj=-1.000000 f1(sig=89 prec=38.202247% acc=48.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
30 sha=33f16f4e3a0ddd1352dc90fb00e3e338d38fe47052a55bbe52c510b66b84a374 obj=-1.000000 f1(sig=70 prec=38.571429% acc=51.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
31 sha=19e9b908dfc4f88b81f1b8ce78b2fd4b93f032b29ae5a6a860d2a165c70fc100 obj=-1.000000 f1(sig=122 prec=40.983607% acc=48.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
32 sha=7986c41c1bc43f61dfb279c4ceabad1c310e0e448e815a54a9a2358c9e221b36 obj=-1.000000 f1(sig=99 prec=37.373737% acc=46.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
33 sha=134019747cfaf3211f7365325fa89d80ccf0169bf81b6d61043b2c108c03c63f obj=-1.000000 f1(sig=90 prec=36.666667% acc=47.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
34 sha=143f664db20b7d86b9814270b0de46242de05ba64a828cc6d2127a4b8a64dab8 obj=-1.000000 f1(sig=97 prec=40.206186% acc=49.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
35 sha=3dac15bb029238b1dec04aa7671642286cbf6163d281eba6e843f6f35fcf3e5d obj=-1.000000 f1(sig=126 prec=42.063492% acc=49.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
36 sha=abde87022365cb10f4f974e8b558efbd0b35bd6b32bca29736a6a7447a850825 obj=-1.000000 f1(sig=87 prec=39.080460% acc=49.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
37 sha=dfcaeaa7974baf833055e79e79f4955419f1aba6129515ea31d5f5b4937149b3 obj=-1.000000 f1(sig=65 prec=38.461538% acc=51.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
38 sha=eb00591ddb58e2a2f6299da67c67c283911df94971d473261ef3fc49041932a9 obj=-1.000000 f1(sig=101 prec=39.603960% acc=48.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
39 sha=2a470e83011fda0adabf32daeaeb78bdf30872a8c93c0ddd3b84f4223c2ddf45 obj=-1.000000 f1(sig=119 prec=38.655462% acc=45.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
40 sha=961e6a000d4dd0c932c44e716ec7b98005390e2f00640880ca7547b2d1f6168c obj=-1.000000 f1(sig=145 prec=42.758621% acc=48.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
41 sha=48ce3a764380b9cf459a83699fc90dab1188f2a7ca97651bcb0ac3ca81a2221f obj=-1.000000 f1(sig=105 prec=39.047619% acc=47.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
42 sha=2d9dadd18047cb612d11cefd94e9084b5702cbce26a305223a8cabbbc03e1b45 obj=-1.000000 f1(sig=112 prec=39.285714% acc=47.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
43 sha=65e4b735a09e354e65f8fff36c49fccd1bc832055fe55aa7d6aa92f289b63f30 obj=-1.000000 f1(sig=137 prec=43.065693% acc=49.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
44 sha=4723b4d9269f7b957886d13bf3b67f6221652ed77e8662151a43140a7d47eb30 obj=-1.000000 f1(sig=137 prec=43.065693% acc=49.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
45 sha=dd8586d83c5532bc36568ad4c1fed4acbcbf21b00164e8c4c1a16540c12157f8 obj=-1.000000 f1(sig=132 prec=41.666667% acc=48.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
46 sha=67141a1763a39389d05885f0b6f3e9cd447d688bd22cc29121fe5bce7c3e5619 obj=-1.000000 f1(sig=82 prec=35.365854% acc=47.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
47 sha=5bc662798efa7978831375cca72635b6ca1ba5f4504292a73b74e32d9f1eca27 obj=-1.000000 f1(sig=76 prec=39.473684% acc=51.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
48 sha=df43608088d38bd57fc0fa129bb2816718bb5ebf5ae1a23ac5b752275f8ac324 obj=-1.000000 f1(sig=68 prec=39.705882% acc=52.000000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
49 sha=9975fb3a700eefb9627eb3703d8523b96efbb1a5fb4f4b57383f64a5d39c93db obj=-1.000000 f1(sig=117 prec=41.880342% acc=49.500000%) f2(sig=0 prec=0.000000% acc=55.500000%) evidence=false pass=false
```

Evidence-sufficient trial count: 0. Inner-WFV-passing trial count: 0.

## Selected Candidate

No candidate was selected. The tuner returned
`NO_INNER_EVIDENCE_SUFFICIENT_CANDIDATE`, exposed an empty selected-parameters
mapping, and retained any diagnostic parameters separately. Those diagnostic
parameters were not used or recorded.

The returned diagnostic evidence summary, which is not a selected candidate,
had fold precisions 45.744681% and 0.000000%, signals 94 and 0, average and
median precision 22.872340%, pooled precision 45.744681%, total signals 94,
and objective -1.0. Evidence sufficiency and inner WFV were both false.

## Selected Parameters

None. There is no selected trial, selected parameter SHA, XGB parameter set,
or LightGBM parameter set. No diagnostic parameter dictionary is included.

## Hyperparameter Provenance

The run stopped before enriching candidate provenance because no eligible
parameter set existed. No candidate or model metadata consumed the diagnostic
configuration. Tuner persistence remained false.

## Outer Certification

Not executed. No outer metric was exposed to Optuna and outer evidence was not
consumed. There was no retuning, trial-count increase, manual parameter change,
or second candidate call.

## Quality Gate

Not executed for a tuned candidate because the inner gate failed first. The
previous score was not reused as current evidence.

## Calibration

Not executed for a tuned candidate.

## Validation

Not executed for a tuned candidate. `model_valid` is not applicable.

## Promotion

Not executed. No retrain run was created and `latest_EURUSD.pkl` remains
absent.

## Artifact

No artifact was staged or promoted. Artifact SHA, alias SHA comparison, and
stored feature names are not applicable.

## DB Provenance

Post-run counts remained zero model-provenance rows, zero retrain-run rows,
and zero H1 model-quality rows. There are no `PENDING`, `RUNNING`, `VALIDATED`,
`FAILED`, or duplicate promotion records from this run.

## Eligibility

No production audit was run because no model exists. Eligibility remains
unestablished and the remaining gate is sufficient inner WFV evidence.

## Persistence Safety

The legacy `best_params_EURUSD.json` remains unchanged at SHA-256
`3c4d6147c9647f2f5e19db7b94384306caabece0c5e62cabe9cb5af0c5148961`.
The complete params-directory fingerprint is unchanged. The hyperparameter
cache and its sidecar set are unchanged; the cache file remains at SHA-256
`8bc7a425ed891eae40995084a3f8c692e9a56804c621a2de8c7b82c7635a96ca`.
No tuned params file was created or overwritten.

## Canonical Safety

The canonical files remained unchanged:

- H1: `868eb4a92006de5c42fdd6465d923284f5d56a2448e740b1df38a9edc45d8f67`
- H4: `9d805c070c3a3119efdd1c1823e16e732beff7d927037e7a6aa56c653ef4f66b`
- D1: `1913093a055bfe0746b16d87305c23a5f688970538f2fab6c43240c859b49bdf`

The complete EURUSD registry remained unchanged. Qualification evidence
remains unchanged at SHA-256
`9c6e6c0a08d048044f2fa8b707b567332626dabfb44219d707b59b91a8a9e59a`.

## Lifecycle

EURUSD remains `qualified`. Activation, prediction, and trading were not
executed.

## Statistical Interpretation

The search did not produce robust evidence even on the internal selection
folds. Fold 2 emitted no BUY signal for every tested parameter set, so no trial
met the 20-signal-per-fold contract. The correct fail-closed action is to stop
before outer certification. Future work should use more independent historical
data, a different feature/model hypothesis, or a future snapshot—not optimize
against the reserved outer folds.

## Decision

**EURUSD TUNING REJECTED — NO INNER EVIDENCE**
