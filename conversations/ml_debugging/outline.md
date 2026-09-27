# `ml_debugging`: outline

**Domain:** an ML engineer (Sam) debugs **LeafScan**, a plant-disease image classifier that scores
94% on validation but about 61% in the field app. Hypotheses are proposed, tested and refuted one by one.
**50 turns**, 2026-03-02 → 2026-03-20.

**Why this corpus:** the densest natural source of `contradicts`, since experiments routinely refute
the assistant's hypotheses. Each hypothesis is an `open_question` state node, so the corpus
exercises epistemic status changes (open → contested → superseded/resolved) more than any other.

## Domain config

| Type | Description |
|---|---|
| `model` | A named ML model or checkpoint (e.g. LeafScan-v3, ResNet-50). |
| `dataset` | A named dataset or data split. |
| `experiment` | A named experiment/run id (e.g. exp-12-dedup). |
| `hyperparameter` | A named training/preprocessing setting (e.g. resize interpolation, class weights). |

## Entities (planned)

E_1 person Sam · E_2 model LeafScan-v3 · E_3 model ResNet-50 · E_4 dataset PlantVillage-ext (train/val) ·
E_5 dataset field set (1,200 labelled app photos) · E_6 system field app · E_7 measurement validation accuracy ·
E_8 measurement field accuracy · E_9 experiment exp-dedup · E_10 experiment exp-interp ·
E_11 experiment exp-jpeg-aug · E_12 experiment exp-finetune-field · E_13 hyperparameter resize interpolation ·
E_14 hyperparameter JPEG-quality augmentation · E_15 hyperparameter class weights ·
E_16 tool OpenCV · E_17 tool Pillow · E_18 person Joana (labelling lead) · E_19 tool Weights & Biases

## State nodes

| id | type | label | lifecycle |
|---|---|---|---|
| SN_1 | goal | Field accuracy ≥ 85% | +N_1 → achieved N_48 |
| SN_2 | open_question | H1: Is there train/val leakage? | +N_6 → resolved N_12 (yes, 3% near-duplicates, explains ~3 pts) |
| SN_3 | open_question | H2: Is normalisation different in the app? | +N_14 → resolved N_18 (no) |
| SN_4 | open_question | H3: Does resize interpolation differ between training and the app? | +N_19 → resolved N_23 (yes, ~6 pts) |
| SN_5 | decision | Use OpenCV INTER_AREA resize in both training and the app | +N_23 |
| SN_6 | open_question | H4: Is the field class distribution shifted? | +N_25 → resolved N_30 (yes, but only calibration, not accuracy) |
| SN_7 | decision | Retrain with inverse-frequency class weights | +N_27 → reverted N_31 |
| SN_8 | open_question | H5: Is phone JPEG compression the remaining gap? | +N_33 → resolved N_37 |
| SN_9 | decision | Add random JPEG-quality (30–90) augmentation | +N_37 |
| SN_10 | constraint | Labelling budget: 500 field images | +N_39 → revised N_43 (800) |
| SN_11 | decision | Fine-tune on labelled field images | +N_40 → revised N_44 (freeze backbone, train head + last block) |
| SN_12 | decision | Deduplicate splits with perceptual hashing before every retrain | +N_12 |

## Turn arc

| Turn | Date | Act | Gist | Edges / state |
|---|---|---|---|---|
| **Symptom** | | | | |
| N_1 | 03-02 | request | 94% val, ~61% field. Help. | S: +SN_1 |
| N_2 | 03-02 | clarification_request | How is field accuracy measured? | H: N_1 subcase · P: N_1 depends_on |
| N_3 | 03-02 | information | 1,200 labelled app photos (Joana's team) | P: N_2 resolves |
| N_4 | 03-02 | suggestion | Assistant lists 5 candidate causes | H: N_1 subcase · P: N_3 depends_on |
| N_5 | 03-02 | agreement | Start with the cheapest to check | P: N_4 depends_on |
| **H1: leakage** | | | | |
| N_6 | 03-02 | factual_question | Could val be inflated by duplicates? | H: N_4 subcase · S: +SN_2 |
| N_7 | 03-03 | information | Assistant: very likely the main cause (PlantVillage is known for it) | P: N_6 depends_on |
| N_8–N_10 | 03-03 | request / information | pHash dedup script; run exp-dedup | H: N_6 subcase · P: depends_on chain |
| N_11 | 03-04 | information | 3% near-dupes; val drops 94 → 91 | P: N_7 contradicts ("main cause" is wrong) |
| N_12 | 03-04 | decision | Leakage real but minor; dedup before every retrain | P: N_6 resolves · S: SN_2→resolved, +SN_12 |
| N_13 | 03-04 | follow_up | 91 vs 61: the gap is still 30 pts | P: N_11 depends_on |
| **H2: normalisation** | | | | |
| N_14 | 03-05 | suggestion | Assistant: app probably skips ImageNet normalisation | H: N_4 subcase · S: +SN_3 |
| N_15 | 03-05 | request | How to check? | H: N_14 subcase · P: N_14 depends_on |
| N_16 | 03-05 | information | Dump app tensors, compare stats | P: N_15 resolves |
| N_17 | 03-06 | information | App normalisation is identical | P: N_14 contradicts |
| N_18 | 03-06 | agreement | H2 ruled out | P: N_17 depends_on · S: SN_3→resolved |
| **H3: resize interpolation** | | | | |
| N_19 | 03-06 | information | Tensors differ at the pixel level anyway → maybe resize | H: N_14 same_level · P: N_16 references · S: +SN_4 |
| N_20 | 03-06 | information | Training uses Pillow bilinear, app uses OpenCV nearest | H: N_19 subcase · P: N_19 depends_on |
| N_21 | 03-07 | suggestion | Assistant: switch app to Pillow bilinear | P: N_20 depends_on |
| N_22 | 03-07 | information | App can't ship Pillow (mobile) → OpenCV only | P: N_21 contradicts |
| N_23 | 03-07 | decision | Standardise on OpenCV INTER_AREA in both; exp-interp: field 61 → 67 | P: N_21 revises, N_19 resolves · S: SN_4→resolved, +SN_5 |
| N_24 | 03-09 | follow_up | Recap: leakage and interpolation account for ~9 pts | H: N_12 supercase, N_23 supercase |
| **H4: class shift** | | | | |
| N_25 | 03-09 | factual_question | Field has far more "healthy" leaves (48% vs 12%) | H: N_4 subcase · S: +SN_6 |
| N_26 | 03-09 | information | Prior shift can hurt | P: N_25 depends_on |
| N_27 | 03-10 | decision | Retrain with class weights | H: N_25 subcase · P: N_26 depends_on · S: +SN_7 |
| N_28 | 03-11 | information | Weighted model: field 66 (−1), rare-class recall ↑, healthy recall ↓ | P: N_27 depends_on · ~SN_7 contradicts |
| N_29 | 03-11 | disagreement | Sam: that's worse; assistant: the macro metric improved | P: N_28 depends_on |
| N_30 | 03-11 | information | Accuracy loss is calibration; fix with prior correction at inference | P: N_25 resolves · S: SN_6→resolved |
| N_31 | 03-11 | decision | Drop class weights; use logit prior-adjustment instead | P: N_27 contradicts · S: SN_7→reverted |
| N_32 | 03-11 | information | Field 69 | P: N_31 depends_on |
| **H5: JPEG compression** | | | | |
| N_33 | 03-12 | factual_question | App photos are heavy JPEG (q≈40); training images are PNG | H: N_4 subcase · S: +SN_8 |
| N_34 | 03-12 | information | Assistant: unlikely to matter for a CNN | P: N_33 depends_on |
| N_35 | 03-13 | information | Sam: re-compressing val to q=40 drops it 91 → 74 | P: N_34 contradicts |
| N_36 | 03-13 | correction | Assistant retracts; compression is the biggest remaining gap | P: N_34 revises |
| N_37 | 03-14 | decision | exp-jpeg-aug: random JPEG q 30–90 → field 78 | P: N_33 resolves · S: SN_8→resolved, +SN_9 |
| N_38 | 03-14 | follow_up | 78 < 85: still short | P: N_37 depends_on · ~SN_1 contradicts |
| **Field fine-tuning** | | | | |
| N_39 | 03-16 | information | Joana can label 500 more field images | S: +SN_10 |
| N_40 | 03-16 | decision | Fine-tune the full model on field images | P: N_39 depends_on · S: +SN_11, ~SN_10 constrained_by |
| N_41 | 03-17 | information | Full fine-tune overfits: 80 on held-out field | P: N_40 depends_on |
| N_42 | 03-17 | suggestion | Freeze the backbone | P: N_41 depends_on |
| N_43 | 03-17 | information | Joana: budget raised to 800 | P: N_39 revises · S: SN_10→revised |
| N_44 | 03-18 | decision | Freeze backbone, train head + last block, 800 images | P: N_40 revises · S: SN_11→revised |
| N_45 | 03-18 | factual_question | Does the dedup rule still apply to field images? | H: N_12 subcase · P: N_12 references |
| N_46 | 03-18 | information | Yes: the field set has burst-shot duplicates | P: N_45 resolves · ~SN_12 supports |
| N_47 | 03-19 | information | exp-finetune-field: 86% | P: N_44 depends_on |
| N_48 | 03-19 | agreement | Target met | S: SN_1→achieved |
| N_49 | 03-20 | request | "Write the post-mortem: every cause and its effect size" | H: N_24 supercase, N_31 supercase, N_37 supercase, N_44 supercase |
| N_50 | 03-20 | follow_up | "Which of your early guesses were wrong?" | P: N_7 references, N_14 references, N_34 references |

**Label targets:** subcase ~14 · same_level ~2 · supercase 6 · depends_on ~26 · references ~6 ·
resolves ~10 · revises 4 · contradicts 8.

## Probes

| id | Question | Target | expected_any | forbidden_any | from | Designed to defeat |
|---|---|---|---|---|---|---|
| p1 | Was train/val leakage the main cause of the field gap? | SN_2 | "minor", "3 points", "3%" | "main cause" | 12 | anti-semantic (N_7 claims it is) |
| p2 | Does the app normalise images differently from training? | SN_3 | "identical", "no" | "skips normalisation" | 17 | anti-semantic |
| p3 | Which resize method should training and the app use? | SN_5 | "INTER_AREA", "OpenCV" | "Pillow bilinear" | 23 | anti-semantic (N_21 suggests Pillow) |
| p4 | Is LeafScan trained with class weights? | SN_7 | "no", "prior adjustment" | "inverse-frequency weights" | 31 | anti-hierarchical |
| p5 | Does JPEG compression matter for LeafScan? | SN_8 | "yes", "biggest", "74" | "unlikely to matter" | 36 | anti-semantic (N_34 says it doesn't) |
| p6 | How many field images can be labelled? | SN_10 | "800" | "500" | 43 | anti-semantic |
| p7 | How is the model fine-tuned on field data? | SN_11 | "freeze", "backbone" | "full fine-tune" | 44 | anti-recency |
| p8 | What must happen before every retrain? | SN_12 | "dedup", "perceptual hash" | — | 12 | anti-recency |
| p9 | What field accuracy does the final model reach? | SN_1 | "86" | "61", "78" | 47 | — |
