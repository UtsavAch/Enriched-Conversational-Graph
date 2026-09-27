# `tutoring_stats`: outline

**Domain:** a psychology undergrad (Lena) is tutored in intro statistics over six weekly
sessions while analysing her own course-project survey. **50 turns**, 2026-10-05 → 2026-11-23.

**Why this corpus:** the workplan names tutoring dialogues explicitly. Concept learning is naturally
tree-shaped (many `subcase`), has natural "big picture" recap turns (`supercase`), and a
misconception that gets corrected later is a clean, non-forced `contradicts` → `revises` arc.

## Domain config (`domain_config.json`)

| Type | Description |
|---|---|
| `concept` | A named statistical concept or quantity (e.g. p-value, standard error, effect size). |
| `method` | A named statistical test or procedure (e.g. Welch's t-test, one-way ANOVA, Mann-Whitney U). |
| `dataset` | A named dataset or data file. |

## Entities (planned)

| id | type | name |
|---|---|---|
| E_1 | person | Lena |
| E_2 | person | Dr. Okafor (course instructor) |
| E_3 | event | PSY210 Research Methods exam |
| E_4 | dataset | sleep-and-focus survey (n=42) |
| E_5 | concept | p-value |
| E_6 | concept | sampling distribution |
| E_7 | concept | standard error |
| E_8 | concept | confidence interval |
| E_9 | method | paired t-test |
| E_10 | method | Welch's t-test |
| E_11 | method | one-way ANOVA |
| E_12 | method | Mann-Whitney U / Kruskal-Wallis |
| E_13 | concept | effect size (Cohen's d / η²) |
| E_14 | concept | statistical power |
| E_15 | measurement | alpha level |
| E_16 | method | linear regression |
| E_17 | tool | JASP |

## State nodes

| id | type | label | lifecycle |
|---|---|---|---|
| SN_1 | goal | Pass the PSY210 exam | +N_1 → achieved N_50 |
| SN_2 | goal | Analyse the sleep-and-focus survey for the course project | +N_3 → achieved N_45 |
| SN_3 | open_question | What does a p-value actually mean? | +N_6 → resolved N_18 |
| SN_4 | decision | Report 95% confidence intervals alongside every p-value | +N_14 (never revisited; anti-recency probe target) |
| SN_5 | decision | Compare sleep groups with a paired t-test | +N_22 → revised N_26 (Welch's, independent) → reverted N_29 |
| SN_6 | decision | Compare the three sleep groups with a one-way ANOVA | +N_29 |
| SN_7 | constraint | Only use methods covered in the PSY210 syllabus (no nonparametrics) | +N_23 → lifted N_40 |
| SN_8 | open_question | Is n=42 enough to detect a medium effect? | +N_33 → resolved N_36 |
| SN_9 | decision | Alpha 0.05 for all comparisons | +N_30 → revised N_31 (Bonferroni: 0.017 per post-hoc pair) |
| SN_10 | open_question | Is the normality assumption violated for focus scores? | +N_37 → resolved N_39 |
| SN_11 | decision | Keep the outlier participant (P17), report a sensitivity analysis without them | +N_35 |
| SN_12 | decision | Use Kruskal-Wallis as the primary test, ANOVA as robustness check | +N_41 (after SN_7 lifted) |

## Turn arc

| Turn | Date | Act | Gist | Edges / state |
|---|---|---|---|---|
| **Session 1: descriptives → inference** | | | | |
| N_1 | 10-05 | request | Lena: exam in 7 weeks, lost after week 3; where to start? | S: +SN_1 |
| N_2 | 10-05 | information | Tutor: start from mean/SD; everything later builds on spread | H: N_1 subcase · P: N_1 depends_on |
| N_3 | 10-05 | information | Lena also needs to analyse her survey (sleep hours vs focus score) for the project | H: N_1 same_level · S: +SN_2 |
| N_4 | 10-05 | factual_question | Why divide by n−1 for SD? | H: N_2 subcase · P: N_2 depends_on |
| N_5 | 10-05 | information | Tutor: sampling distribution intro, standard error | H: N_2 subcase · P: N_4 depends_on |
| N_6 | 10-05 | factual_question | Lena: "so p=0.03 means a 3% chance the null is true?" Tutor answers vaguely ("roughly, it's about how surprising the data is") without correcting | H: N_5 subcase · P: N_5 depends_on · S: +SN_3 |
| N_7 | 10-05 | follow_up | Lena restates her (wrong) reading as a summary note | H: N_6 same_level · P: N_6 depends_on |
| N_8 | 10-05 | agreement | Session wrap-up: homework on SE | P: N_5 references |
| **Session 2: confidence intervals** | | | | |
| N_9 | 10-12 | factual_question | Homework check: SE for n=25, SD=10 | H: N_5 subcase · P: N_5 depends_on |
| N_10 | 10-12 | information | Tutor: CIs = estimate ± margin | H: N_5 same_level · P: N_9 depends_on |
| N_11 | 10-12 | clarification_request | Why 1.96? | H: N_10 subcase · P: N_10 depends_on |
| N_12 | 10-12 | information | z vs t critical values | H: N_11 subcase · P: N_11 resolves |
| N_13 | 10-12 | factual_question | Is a CI the range where the true mean is 95% likely to be? | H: N_10 subcase · P: N_10 depends_on |
| N_14 | 10-12 | decision | Tutor corrects the CI reading; they agree her project will report 95% CIs next to every p-value | P: N_13 resolves · S: +SN_4 |
| N_15 | 10-12 | information | CI and hypothesis test are two views of the same thing | H: N_10 same_level · P: N_14 references |
| N_16 | 10-12 | agreement | Wrap-up | P: N_14 references |
| **Session 3: the misconception, t-tests, recap** | | | | |
| N_17 | 10-19 | information | Lena's quiz: she lost points on a p-value question | P: N_7 references |
| N_18 | 10-19 | correction | Tutor: her N_7 note is wrong; p = P(data this extreme \| null true), not P(null true) | P: N_7 contradicts, N_6 resolves · S: SN_3→resolved |
| N_19 | 10-19 | follow_up | Lena rewrites her note correctly | H: N_18 same_level · P: N_7 revises |
| N_20 | 10-19 | factual_question | One-sample vs two-sample t-test? | H: N_10 same_level · P: N_18 depends_on |
| N_21 | 10-19 | information | Independent vs paired designs | H: N_20 subcase · P: N_20 resolves |
| N_22 | 10-19 | decision | Lena: "my participants did both conditions" → paired t-test for the project | H: N_21 subcase · P: N_21 depends_on · S: +SN_5 |
| N_23 | 10-19 | information | Dr. Okafor's rule: only syllabus methods in the project | H: N_3 subcase · S: +SN_7 |
| N_24 | 10-19 | follow_up | Recap: "SE, CIs, p-values and t-tests are all the same signal-over-noise idea" | H: N_5 supercase, N_10 supercase, N_20 supercase · P: N_18 references |
| **Session 4: the project design is wrong** | | | | |
| N_25 | 10-26 | information | Lena shares the data: 3 sleep groups (<6h, 6–8h, >8h), different people in each | H: N_3 subcase · P: N_22 references |
| N_26 | 10-26 | correction | Tutor: not paired, groups are independent → Welch's | P: N_22 contradicts · S: SN_5→revised (Welch's) |
| N_27 | 10-26 | clarification_request | Why Welch's over Student's? | H: N_26 subcase · P: N_26 depends_on |
| N_28 | 10-26 | information | Unequal variances | H: N_27 subcase · P: N_27 resolves |
| N_29 | 10-26 | decision | Three groups → one-way ANOVA, not t-tests | P: N_26 revises · S: SN_5→reverted, +SN_6 |
| N_30 | 10-26 | decision | Alpha 0.05 | H: N_29 subcase · P: N_29 depends_on · S: +SN_9 |
| N_31 | 10-26 | correction | Post-hoc pairs need correction → Bonferroni 0.05/3 ≈ 0.017 | P: N_30 revises · S: SN_9→revised |
| N_32 | 10-26 | follow_up | "So all of these (t, ANOVA, post-hoc) compare between vs within variance?" | H: N_20 supercase, N_29 supercase · P: N_24 references |
| **Session 5: power, outliers, assumptions** | | | | |
| N_33 | 11-02 | factual_question | Is n=42 enough? | H: N_29 subcase · S: +SN_8 |
| N_34 | 11-02 | information | Effect size and power basics | H: N_33 subcase · P: N_33 depends_on |
| N_35 | 11-02 | decision | P17 is an outlier; keep them and run a sensitivity check | H: N_25 subcase · P: N_25 depends_on · S: +SN_11 |
| N_36 | 11-02 | information | Power calc: ~0.45 for a medium effect → underpowered; report as limitation | P: N_33 resolves · S: SN_8→resolved, ~SN_2 constrained_by |
| N_37 | 11-02 | factual_question | Focus scores look skewed; does ANOVA still work? | H: N_29 subcase · S: +SN_10, ~SN_6 contradicts |
| N_38 | 11-02 | information | Shapiro-Wilk p<.01; nonparametric would be better, but syllabus rule | P: N_37 depends_on · S: ~SN_7 constrained_by |
| N_39 | 11-02 | information | Normality clearly violated | P: N_37 resolves · S: SN_10→resolved |
| N_40 | 11-02 | information | Lena emailed Dr. Okafor: nonparametrics allowed with justification | P: N_23 contradicts · S: SN_7→lifted |
| N_41 | 11-02 | decision | Kruskal-Wallis primary, ANOVA as robustness | P: N_29 revises, N_40 depends_on · S: +SN_12 |
| **Session 6: regression, exam review** | | | | |
| N_42 | 11-09 | factual_question | Sleep hours is continuous; regression instead of groups? | H: N_25 same_level · P: N_25 references |
| N_43 | 11-09 | information | Tutor: regression is the general case of ANOVA | H: N_29 supercase · P: N_42 resolves |
| N_44 | 11-09 | decision | Keep grouped analysis for the project; mention regression as future work | P: N_42 depends_on · S: ~SN_12 supports |
| N_45 | 11-09 | information | Project submitted | S: SN_2→achieved |
| N_46 | 11-09 | request | Exam review: "give me the map of everything" | H: N_24 supercase, N_32 supercase, N_43 supercase |
| N_47 | 11-09 | factual_question | Practice Q on p-values | H: N_46 subcase · P: N_18 references |
| N_48 | 11-09 | factual_question | Practice Q on CI interpretation | H: N_46 subcase · P: N_14 references |
| N_49 | 11-09 | factual_question | Practice Q: which test for 3 independent skewed groups? | H: N_46 subcase · P: N_41 references |
| N_50 | 11-23 | feedback | Lena passed with a B+ | P: N_1 resolves · S: SN_1→achieved |

**Label targets:** subcase ~24 · same_level ~7 · supercase ~11 · depends_on ~19 · references ~11 ·
resolves ~9 · revises 3 · contradicts 4.

## Probes

| id | Question | Target | expected_any | forbidden_any | from | Designed to defeat |
|---|---|---|---|---|---|---|
| p1 | What does it mean that Lena's result has p = 0.03? | SN_3 | "if the null were true", "data this extreme" | "3% chance the null is true", "probability the null hypothesis is true" | 18 | anti-semantic (N_6/N_7 are the closest match and wrong) |
| p2 | Which test should Lena use to compare the three sleep groups? | SN_12 | "Kruskal-Wallis" | "paired t-test", "Welch" | 41 | anti-semantic |
| p3 | Can Lena use nonparametric tests in the project? | SN_7 | "allowed", "with justification" | "only syllabus", "not allowed" | 40 | anti-hierarchical |
| p4 | Is n=42 enough for Lena's study? | SN_8 | "underpowered", "limitation" | "enough power", "sample is fine" | 36 | — |
| p5 | Should Lena report confidence intervals in her project? | SN_4 | "95%", "alongside" | "only p-values" | 14 | anti-recency (set in session 2, never repeated) |
| p6 | What alpha should Lena use for the pairwise group comparisons? | SN_9 | "0.017", "Bonferroni" | "0.05 for each" | 31 | anti-semantic |
| p7 | What should Lena do with participant P17? | SN_11 | "keep", "sensitivity" | "remove P17", "exclude" | 35 | anti-recency |
| p8 | Are Lena's participants paired? | SN_5 | "independent", "different people" | "paired", "both conditions" | 26 | anti-semantic |
| p9 | Did Lena pass PSY210? | SN_1 | "passed", "B+" | "exam is coming" | 50 | — |
