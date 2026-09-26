# `thesis_planning`: outline

**Domain:** an MSc student (Rita) plans and runs a thesis on **detecting misleading health claims in
Portuguese news**, meeting the assistant between supervisor meetings with Prof. Almeida.
**80 turns**, 2026-02-02 → 2026-06-26 (about 21 weeks; gaps of 1–3 weeks between sessions).

**Why this corpus:** it's the only corpus with **long real-time gaps**. It also has a decision that is
**reverted and then brought back in a different form**, a goal that is **abandoned**, and a deadline
constraint that is **revised**. Early research questions (N_4–N_6) are referenced again at N_74+,
about 70 turns later, which is the long-horizon case that recency retrieval can't reach.

## Domain config

| Type | Description |
|---|---|
| `dataset` | A named dataset or corpus. |
| `model` | A named ML model or model family (e.g. BERTimbau, GPT-4o-mini). |
| `venue` | A named conference, journal, or workshop. |
| `concept` | A named research concept or method (e.g. claim detection, inter-annotator agreement). |

## Entities (planned)

E_1 person Rita · E_2 person Prof. Almeida · E_3 organization the faculty · E_4 dataset FakeRecogna ·
E_5 dataset own annotated health-claims set · E_6 model BERTimbau · E_7 model GPT-4o-mini ·
E_8 model Llama-3.1-8B · E_9 concept claim-worthiness detection · E_10 concept Cohen's kappa ·
E_11 venue PROPOR 2026 · E_12 event thesis submission deadline · E_13 event midterm presentation ·
E_14 location Portugal · E_15 location Brazil · E_16 person Duarte (second annotator) ·
E_17 measurement macro-F1 · E_18 system faculty GPU server

## State nodes

| id | type | label | lifecycle |
|---|---|---|---|
| SN_1 | goal | Submit an MSc thesis on misleading health-claim detection in PT news | +N_1 → achieved N_80 |
| SN_2 | decision | Research questions RQ1 (can models detect claims?) and RQ2 (does PT-PT vs PT-BR matter?) | +N_6 → revised N_42 (RQ2 reframed as a cross-variety transfer question) |
| SN_3 | constraint | Scope: European Portuguese (PT-PT) news only | +N_8 → revised N_41 (PT-PT + PT-BR) |
| SN_4 | goal | Build own annotated dataset (≥2,000 claims) | +N_24 → abandoned N_39 |
| SN_5 | decision | Main method: fine-tune BERTimbau | +N_27 → reverted N_36 |
| SN_6 | constraint | Compute: faculty GPU server only, 1 × 16 GB GPU | +N_30 |
| SN_7 | decision | Main method: zero-shot / few-shot LLM classification | +N_37 → revised N_55 (LLM + fine-tuned baseline, see SN_10) |
| SN_8 | decision | Use FakeRecogna + 400 own-annotated PT-PT claims as test set | +N_40 |
| SN_9 | open_question | Is the own-annotation reliable enough to report? | +N_44 → resolved N_52 |
| SN_10 | decision | Add a fine-tuned **XLM-R-base** baseline (fits 16 GB), at supervisor's request | +N_55 |
| SN_11 | constraint | Submission deadline 30 June | +N_12 → revised N_64 (extension to 15 September) |
| SN_12 | decision | Submit a short paper to PROPOR 2026 | +N_60 → reverted N_66 (deadline clash) |
| SN_13 | decision | Thesis structure: 6 chapters, related work before method | +N_71 |
| SN_14 | open_question | Should Llama-3.1-8B (local) replace GPT-4o-mini for reproducibility? | +N_58 → resolved N_62 (report both) |

## Turn arc

| Turn(s) | Date | Act | Gist | Edges / state |
|---|---|---|---|---|
| **Scoping (Feb)** | | | | |
| N_1 | 02-02 | request | Rita: approved topic "misinformation in PT news", too broad | S: +SN_1 |
| N_2 | 02-02 | suggestion | Narrow to health claims (COVID-era data is rich) | H: N_1 subcase · P: N_1 depends_on |
| N_3 | 02-02 | agreement | Rita agrees on health claims | P: N_2 depends_on |
| N_4–N_5 | 02-02 | factual_question / information | What makes a good RQ? Examples | H: N_2 subcase · P: prev depends_on |
| N_6 | 02-02 | decision | RQ1 detection feasibility; RQ2 PT-PT vs PT-BR difference | P: N_5 depends_on · S: +SN_2 |
| N_7 | 02-09 | information | Almeida's feedback: fine, keep PT-PT focus | P: N_6 references |
| N_8 | 02-09 | decision | Scope limited to PT-PT news | H: N_6 subcase · S: +SN_3 |
| N_9–N_11 | 02-09 | factual_question / information | Which PT-PT outlets? Archive access (Arquivo.pt) | H: N_8 subcase · P: N_8 depends_on |
| N_12 | 02-09 | information | Deadline: 30 June | H: N_1 subcase · S: +SN_11 |
| **Literature review (Feb–Mar)** | | | | |
| N_13–N_20 | 02-16 → 03-02 | factual_question / information | Claim detection, fact-checking pipelines, PT resources, LLM-as-classifier papers | H: mostly subcase of N_2, pairs same_level · P: depends_on chain, 2 × references N_6 |
| N_21 | 03-02 | information | Found FakeRecogna (PT-BR only) | H: N_9 same_level · P: N_8 references |
| N_22 | 03-02 | follow_up | Recap: "three strands of related work" | H: N_13 supercase, N_16 supercase, N_19 supercase |
| N_23 | 03-02 | clarification_request | Does FakeRecogna fit the PT-PT scope? No | P: N_21 depends_on · ~SN_3 constrained_by |
| **Method & data plan (Mar)** | | | | |
| N_24 | 03-09 | decision | Build own PT-PT dataset, ≥2,000 claims | P: N_23 depends_on · S: +SN_4 |
| N_25–N_26 | 03-09 | factual_question / information | Annotation guidelines, second annotator (Duarte) | H: N_24 subcase · P: N_24 depends_on |
| N_27 | 03-09 | decision | Fine-tune BERTimbau as main method | H: N_2 subcase · P: N_22 depends_on · S: +SN_5 |
| N_28–N_29 | 03-16 | follow_up / information | Hyper-parameters, training time estimate | H: N_27 subcase · P: N_27 depends_on |
| N_30 | 03-16 | information | Only the faculty 16 GB GPU is available | S: +SN_6, ~SN_5 constrained_by |
| N_31–N_34 | 03-23 → 03-30 | information / follow_up | Annotation progress: 180 claims in 3 weeks; BERTimbau-large OOMs | H: N_24 subcase / N_27 subcase · P: depends_on |
| **Pivot (Apr)** | | | | |
| N_35 | 04-06 | information | BERTimbau-base underfits; large won't fit; 2k claims unrealistic by June | P: N_31 references, N_33 references |
| N_36 | 04-06 | decision | Drop fine-tuning as main method | P: N_27 contradicts · S: SN_5→reverted |
| N_37 | 04-06 | decision | Switch to zero/few-shot LLM classification | P: N_36 depends_on · S: +SN_7 |
| N_38 | 04-06 | disagreement | Rita worries this weakens novelty; assistant argues the variety question is the novelty | P: N_37 depends_on |
| N_39 | 04-13 | decision | Abandon 2k-claim dataset | P: N_24 contradicts · S: SN_4→abandoned |
| N_40 | 04-13 | decision | FakeRecogna + 400 own PT-PT claims as test set | P: N_39 depends_on · S: +SN_8 |
| N_41 | 04-13 | decision | Scope widened to PT-PT + PT-BR | P: N_8 revises · S: SN_3→revised |
| N_42 | 04-13 | decision | RQ2 reframed: cross-variety transfer (train/prompt on PT-BR, test on PT-PT) | P: N_6 revises · S: SN_2→revised |
| N_43 | 04-13 | follow_up | Recap of the new plan | H: N_37 supercase, N_40 supercase, N_42 supercase |
| **Experiments (Apr–May)** | | | | |
| N_44 | 04-20 | factual_question | Is annotation with only 2 annotators reliable? | H: N_40 subcase · S: +SN_9 |
| N_45–N_51 | 04-20 → 05-04 | information / follow_up | Prompt design, few-shot selection, first results (macro-F1 0.61 zero-shot, 0.68 few-shot) | H: subcase of N_37 · P: depends_on chain, 1 × references N_42 |
| N_52 | 05-04 | information | κ = 0.71 → substantial agreement, report it | P: N_44 resolves · S: SN_9→resolved |
| N_53 | 05-11 | information | Almeida: "no fine-tuned baseline is a reviewer red flag" | P: N_36 contradicts |
| N_54 | 05-11 | disagreement | Rita: but it didn't fit on the GPU | P: N_53 depends_on · ~SN_6 constrained_by |
| N_55 | 05-11 | decision | Add XLM-R-base baseline (fits 16 GB); LLM stays main | P: N_37 revises, N_54 resolves · S: SN_7→revised, +SN_10 |
| N_56–N_57 | 05-18 | information | XLM-R results: 0.64 in-variety, 0.52 cross-variety | H: N_55 subcase · P: N_55 depends_on |
| N_58 | 05-18 | factual_question | Replace GPT-4o-mini with local Llama for reproducibility? | H: N_37 subcase · S: +SN_14 |
| N_59 | 05-18 | information | Trade-offs | P: N_58 depends_on |
| N_60 | 05-25 | decision | Submit short paper to PROPOR 2026 | H: N_1 same_level · S: +SN_12 |
| N_61 | 05-25 | information | PROPOR deadline 20 June | H: N_60 subcase |
| N_62 | 05-25 | decision | Report both LLMs | P: N_58 resolves · S: SN_14→resolved |
| **Deadlines & writing (Jun)** | | | | |
| N_63 | 06-01 | information | Analysis behind schedule | P: N_12 references |
| N_64 | 06-01 | information | Faculty approves extension to 15 Sep | P: N_12 revises · S: SN_11→revised |
| N_65 | 06-01 | factual_question | Should the paper still go in? | P: N_60 depends_on |
| N_66 | 06-01 | decision | Skip PROPOR, thesis first | P: N_60 contradicts · S: SN_12→reverted |
| N_67–N_70 | 06-08 | information / follow_up | Error analysis: PT-BR→PT-PT errors on idioms and institution names | H: N_42 subcase · P: N_56 depends_on |
| N_71 | 06-15 | decision | 6-chapter structure | H: N_1 subcase · S: +SN_13 |
| N_72–N_73 | 06-15 | factual_question / information | What goes in the method chapter? | H: N_71 subcase |
| N_74 | 06-15 | factual_question | "What exactly were my RQs again? Do they still match?" | P: N_6 references, N_42 references |
| N_75 | 06-15 | information | RQ1 unchanged; RQ2 is now transfer, and the intro must reflect the pivot | P: N_74 resolves |
| N_76 | 06-22 | request | Limitations section: dataset size, 2 annotators, GPU limit | H: N_71 subcase · P: N_39 references, N_52 references, N_30 references |
| N_77 | 06-22 | follow_up | "Summarise every change of plan so the story is honest" | H: N_36 supercase, N_41 supercase, N_55 supercase, N_66 supercase |
| N_78–N_79 | 06-22 | information | Chapter drafts reviewed by Almeida | P: depends_on |
| N_80 | 06-26 | information | Full draft done; submission planned for Sep (outcome logged in 09) | S: SN_1→achieved |

*Note on N_80:* if "achieved" should mean submitted, move N_80's date to 09-10 and make it the submission turn.

**Label targets:** subcase ~34 · same_level ~12 · supercase 10 · depends_on ~38 · references ~16 ·
resolves ~7 · revises 5 · contradicts 5.

## Probes

| id | Question | Target | expected_any | forbidden_any | from | Designed to defeat |
|---|---|---|---|---|---|---|
| p1 | What is Rita's main classification method? | SN_7 | "LLM", "few-shot" | "fine-tune BERTimbau" | 55 | anti-semantic |
| p2 | Is there a fine-tuned baseline, and which model? | SN_10 | "XLM-R" | "no fine-tuned baseline", "BERTimbau" | 55 | anti-semantic |
| p3 | Is Rita building her own 2,000-claim dataset? | SN_4 | "abandoned", "400" | "2,000 claims", "still annotating" | 39 | anti-recency |
| p4 | Which Portuguese varieties are in scope? | SN_3 | "PT-BR", "both" | "PT-PT only", "European Portuguese only" | 41 | anti-semantic |
| p5 | What is RQ2 now? | SN_2 | "transfer", "cross-variety" | "difference between PT-PT and PT-BR" | 42 | anti-recency + anti-semantic (asked at N_74+, 30+ turns later) |
| p6 | When is the thesis due? | SN_11 | "15 September", "September" | "30 June" | 64 | anti-semantic |
| p7 | Is Rita submitting to PROPOR 2026? | SN_12 | "no", "skip" | "submit to PROPOR" | 66 | anti-recency |
| p8 | Is the annotation reliable enough to report? | SN_9 | "0.71", "substantial" | "unreliable" | 52 | — |
| p9 | Which LLM(s) will the thesis report? | SN_14 | "both" | "only GPT-4o-mini", "only Llama" | 62 | anti-hierarchical |
| p10 | What hardware constrains Rita's experiments? | SN_6 | "16 GB" | — | 30 | anti-recency (set at N_30, needed at N_76) |
