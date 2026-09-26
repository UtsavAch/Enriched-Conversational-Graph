"""Construct conversations/tutoring_stats/{corpus.json, ground_truth.json}.

Same method as conversations/marathon_trip/build.py: raw per-node fields are
authored below; recurrence_count, retrieval_count, epistemic_status/history,
entities.mentioned_in, and state_nodes status/last_updated_turn are derived
programmatically.

Tutoring dialogue (six weekly sessions): concept learning gives tree-shaped
topic structure (subcase) with natural recap turns (supercase), and a p-value
misconception that the tutor lets slide early and corrects later gives a
non-forced contradicts -> revises arc. Outline: outline.md in this folder.
"""
import json
from collections import Counter
from pathlib import Path

INITIAL_STATUS = {"goal": "active", "decision": "active", "constraint": "active", "open_question": "open"}
OPEN_DEFAULT_ACTS = {"factual_question", "clarification_request"}

ENTITIES = {
    "E_1": {"type": "person", "name": "Lena"},
    "E_2": {"type": "person", "name": "Dr. Okafor"},
    "E_3": {"type": "event", "name": "PSY210 Research Methods exam"},
    "E_4": {"type": "dataset", "name": "sleep-and-focus survey"},
    "E_5": {"type": "concept", "name": "p-value"},
    "E_6": {"type": "concept", "name": "sampling distribution"},
    "E_7": {"type": "concept", "name": "standard error"},
    "E_8": {"type": "concept", "name": "confidence interval"},
    "E_9": {"type": "method", "name": "paired t-test"},
    "E_10": {"type": "method", "name": "Welch's t-test"},
    "E_11": {"type": "method", "name": "one-way ANOVA"},
    "E_12": {"type": "method", "name": "Kruskal-Wallis test"},
    "E_13": {"type": "concept", "name": "effect size"},
    "E_14": {"type": "concept", "name": "statistical power"},
    "E_15": {"type": "measurement", "name": "alpha level"},
    "E_16": {"type": "method", "name": "linear regression"},
    "E_17": {"type": "tool", "name": "JASP"},
}

STATE_NODE_DEFS = {
    "SN_1": {"type": "goal", "label": "Pass the PSY210 Research Methods exam"},
    "SN_2": {"type": "goal", "label": "Analyse the sleep-and-focus survey for the PSY210 course project"},
    "SN_3": {"type": "open_question", "label": "What does a p-value actually mean?"},
    "SN_4": {"type": "decision", "label": "Report 95% confidence intervals alongside every p-value in the project"},
    "SN_5": {"type": "decision", "label": "Compare the sleep groups with a paired t-test"},
    "SN_6": {"type": "decision", "label": "Compare the three sleep groups with a one-way ANOVA"},
    "SN_7": {"type": "constraint", "label": "Only use methods covered in the PSY210 syllabus (no nonparametric tests)"},
    "SN_8": {"type": "open_question", "label": "Is a sample of n=42 enough to detect a medium effect?"},
    "SN_9": {"type": "decision", "label": "Use alpha = 0.05 for all comparisons"},
    "SN_10": {"type": "open_question", "label": "Is the normality assumption violated for the focus scores?"},
    "SN_11": {"type": "decision", "label": "Keep outlier participant P17 and report a sensitivity analysis without them"},
    "SN_12": {"type": "decision", "label": "Use Kruskal-Wallis as the primary test, with one-way ANOVA as a robustness check"},
}

LABEL_OVERRIDES = {
    ("SN_5", "N_26"): "Compare the sleep groups with Welch's t-test for independent groups (originally: paired t-test)",
    ("SN_9", "N_31"): "Use alpha = 0.05 for the omnibus test and a Bonferroni-corrected 0.017 per pairwise post-hoc comparison (originally: 0.05 for all comparisons)",
}

NODES = [
    # ---- Session 1: descriptives -> inference --------------------------------------
    dict(id="N_1", date="2026-10-05",
         q="Hi, I'm Lena. My PSY210 Research Methods exam is in seven weeks and I've been lost since week 3, when the course got into inference. Where should I start?",
         a="We'll get you there. Inference builds on a few ideas in a strict order, so we'll start at the bottom: means and spread, then how sample statistics vary, then p-values and intervals. Seven weeks is enough if we go step by step.",
         act="request", ents=["E_1", "E_3"], cites=[], hier=[], prag=[],
         creates=["SN_1"], updates=[], relates=[],
         summary="Lena wants to pass the PSY210 exam in seven weeks after getting lost at inference.",
         ref="Goal: pass PSY210"),
    dict(id="N_2", date="2026-10-05",
         q="OK, so where exactly is the bottom?",
         a="The mean and the standard deviation. The SD measures how spread out individual scores are around the mean, and almost everything later, from standard errors to t-tests, is built from it.",
         act="information", ents=[], cites=[], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Starts from the mean and standard deviation as the foundation.",
         ref="Mean and SD first"),
    dict(id="N_3", date="2026-10-05",
         q="There's also my course project: I ran a survey on sleep and concentration, 42 participants, sleep hours plus a focus score. I have to analyse it for PSY210.",
         a="Good, a real dataset makes this much easier to learn. We'll use your sleep-and-focus survey as the running example and build the project analysis as we go.",
         act="information", ents=["E_4"], cites=[], hier=[["N_1", "same_level"]], prag=[],
         creates=["SN_2"], updates=[], relates=[],
         summary="Lena also has to analyse her 42-person sleep-and-focus survey for the course project.",
         ref="Project: sleep survey"),
    dict(id="N_4", date="2026-10-05",
         q="Why does the SD formula divide by n−1 instead of n? That always confused me.",
         a="Because the sample mean is computed from the same data, so the scores sit slightly closer to it than to the true population mean. Dividing by n−1 corrects that underestimate of the spread.",
         act="factual_question", ents=[], cites=[], hier=[["N_2", "subcase"]], prag=[["N_2", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Explains why the sample SD divides by n-1.",
         ref="Why n-1"),
    dict(id="N_5", date="2026-10-05",
         q="And how do we get from the spread of scores to inference?",
         a="Through the sampling distribution: if you repeated your study many times, the sample mean would vary from study to study. The SD of that variation is the standard error, SD divided by the square root of n. It tells you how much your mean would wobble between studies.",
         act="information", ents=["E_6", "E_7"], cites=[], hier=[["N_2", "subcase"]], prag=[["N_4", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Introduces the sampling distribution and the standard error.",
         ref="Sampling distribution and SE"),
    dict(id="N_6", date="2026-10-05",
         q="And where do p-values come in? Like, if I get p = 0.03, that means there's a 3% chance that the null hypothesis is true, right?",
         a="Roughly, yes. A p-value is about how surprising your data are; a small one means the result would be unlikely to happen just by chance.",
         act="factual_question", ents=["E_5"], cites=[], hier=[["N_5", "subcase"]], prag=[["N_5", "depends_on"]],
         creates=["SN_3"], updates=[], relates=[],
         summary="Lena reads p = 0.03 as a 3% chance the null is true; the tutor answers vaguely without correcting it.",
         ref="p-value misreading unchallenged"),
    dict(id="N_7", date="2026-10-05",
         q="Great, I'll write that in my summary notes: p = the probability that the null hypothesis is true.",
         a="Sounds good. Keep your notes short and in your own words.",
         act="follow_up", ents=["E_5"], cites=[], hier=[["N_6", "same_level"]], prag=[["N_6", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Lena records the incorrect p-value definition in her notes.",
         ref="Wrong definition in notes"),
    dict(id="N_8", date="2026-10-05",
         q="What should I do before next week?",
         a="Practise standard errors: compute the SE for a few made-up samples so the formula becomes automatic.",
         act="agreement", ents=["E_7"], cites=[], hier=[], prag=[["N_5", "references"]],
         creates=[], updates=[], relates=[],
         summary="Homework: practise standard error calculations.",
         ref="SE homework"),
    # ---- Session 2: confidence intervals ------------------------------------------------
    dict(id="N_9", date="2026-10-12",
         q="Homework check: for n = 25 and SD = 10, I got a standard error of 2. Is that right?",
         a="Yes: 10 divided by the square root of 25 is 10/5 = 2.",
         act="factual_question", ents=["E_7"], cites=[], hier=[["N_5", "subcase"]], prag=[["N_5", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Homework check: SE = 2 for n=25, SD=10.",
         ref="SE homework correct"),
    dict(id="N_10", date="2026-10-12",
         q="What's the next idea after the standard error?",
         a="Confidence intervals. A 95% CI is your estimate plus or minus about two standard errors. With your numbers, a mean of 50 would give roughly 46 to 54.",
         act="information", ents=["E_8"], cites=[], hier=[["N_5", "same_level"]], prag=[["N_9", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Introduces 95% confidence intervals as estimate ± about 2 SE.",
         ref="Confidence intervals"),
    dict(id="N_11", date="2026-10-12",
         q="Where does the 'about two' come from? My notes say 1.96.",
         a="It is 1.96: in a normal distribution, 95% of values lie within 1.96 standard deviations of the mean. 'About two' is just a mental shortcut.",
         act="clarification_request", ents=["E_8"], cites=[], hier=[["N_10", "subcase"]], prag=[["N_10", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks where the 1.96 multiplier comes from.",
         ref="Why 1.96"),
    dict(id="N_12", date="2026-10-12",
         q="But my textbook sometimes uses 2.06 instead. Why?",
         a="With small samples you use the t distribution instead of the normal, because the SD itself is estimated. For n = 25 the t critical value is 2.06; it gets closer to 1.96 as n grows.",
         act="follow_up", ents=[], cites=[], hier=[["N_11", "subcase"]], prag=[["N_11", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Explains z vs t critical values (1.96 vs 2.06 for n=25).",
         ref="z vs t critical values"),
    dict(id="N_13", date="2026-10-12",
         q="So a 95% CI means there's a 95% chance the true mean is inside my interval?",
         a="That's close, but not quite. Let's be careful with the wording.",
         act="factual_question", ents=["E_8"], cites=[], hier=[["N_10", "subcase"]], prag=[["N_10", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks whether a 95% CI has a 95% chance of containing the true mean.",
         ref="CI interpretation asked"),
    dict(id="N_14", date="2026-10-12",
         q="What's the careful version? And should I use CIs in my project?",
         a="The careful version: if you repeated the study many times, 95% of the intervals built this way would contain the true mean; any single interval either does or doesn't. And yes, for your project, report a 95% confidence interval alongside every p-value. It shows the size and precision of each effect, not just whether it's significant.",
         act="decision", ents=["E_8", "E_5", "E_4"], cites=[], hier=[["N_13", "subcase"]], prag=[["N_13", "resolves"]],
         creates=["SN_4"], updates=[], relates=[["SN_2", "supports"]],
         summary="Corrects the CI interpretation; decides to report 95% CIs alongside every p-value in the project.",
         ref="Report 95% CIs"),
    dict(id="N_15", date="2026-10-12",
         q="Are confidence intervals and hypothesis tests related?",
         a="They're two views of the same thing: a 95% CI that excludes zero corresponds to p < 0.05 for that difference.",
         act="information", ents=["E_8"], cites=[], hier=[["N_10", "same_level"]], prag=[["N_14", "references"]],
         creates=[], updates=[], relates=[],
         summary="CIs and hypothesis tests are two views of the same inference.",
         ref="CI-test duality"),
    dict(id="N_16", date="2026-10-12",
         q="Makes sense. See you next week!",
         a="See you. Try building 95% CIs for a couple of your survey variables before then.",
         act="agreement", ents=["E_4"], cites=[], hier=[], prag=[["N_14", "references"]],
         creates=[], updates=[], relates=[],
         summary="Session 2 wrap-up with a CI exercise on the survey.",
         ref="Session 2 wrap-up"),
    # ---- Session 3: the misconception, t-tests, recap ---------------------------------------
    dict(id="N_17", date="2026-10-19",
         q="I got my quiz back and lost points on the p-value question. I wrote exactly what's in my notes.",
         a="Let's look at what's in your notes then; this matters for the exam.",
         act="information", ents=["E_5"], cites=[], hier=[], prag=[["N_7", "references"]],
         creates=[], updates=[], relates=[],
         summary="Lena lost quiz points on the p-value question using her notes.",
         ref="Quiz points lost"),
    dict(id="N_18", date="2026-10-19",
         q="My notes say: p = the probability that the null hypothesis is true.",
         a="That's the problem, and I should have corrected it when you first said it [N_6]. A p-value is the probability of getting data at least as extreme as yours if the null hypothesis were true. It is not the probability that the null is true. p = 0.03 means: if there were really no effect, results this extreme would appear only 3% of the time.",
         act="correction", ents=["E_5"], cites=["N_6"], hier=[["N_17", "subcase"]], prag=[["N_7", "contradicts"], ["N_6", "resolves"]],
         creates=[], updates=[["SN_3", "resolved"]], relates=[["SN_3", "resolves"]],
         summary="Tutor corrects the note: p is P(data this extreme | null true), not P(null true).",
         ref="p-value corrected"),
    dict(id="N_19", date="2026-10-19",
         q="OK, I rewrote the note: 'p = how likely data at least this extreme would be if the null were true.'",
         a="That's correct, and exam-proof.",
         act="follow_up", ents=["E_5"], cites=[], hier=[["N_18", "same_level"]], prag=[["N_7", "revises"]],
         creates=[], updates=[], relates=[],
         summary="Lena rewrites her p-value note correctly.",
         ref="Note rewritten"),
    dict(id="N_20", date="2026-10-19",
         q="Now t-tests. What's the difference between a one-sample and a two-sample t-test?",
         a="A one-sample t-test compares one mean to a fixed value; a two-sample t-test compares two means. Both divide a difference by its standard error.",
         act="factual_question", ents=[], cites=[], hier=[["N_10", "same_level"]], prag=[["N_18", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks the difference between one-sample and two-sample t-tests.",
         ref="t-test types"),
    dict(id="N_21", date="2026-10-19",
         q="And within two-sample tests?",
         a="It depends on the design. If the same people are measured twice, the scores are paired and you use a paired t-test; if the two groups are different people, they're independent and you use an independent-samples test.",
         act="information", ents=["E_9"], cites=[], hier=[["N_20", "subcase"]], prag=[["N_20", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Paired vs independent designs determine which two-sample test to use.",
         ref="Paired vs independent"),
    dict(id="N_22", date="2026-10-19",
         q="My participants did both conditions, so I should use a paired t-test for the project, right?",
         a="If each participant contributed a score in both conditions, then yes, a paired t-test fits. Plan on that for the project.",
         act="decision", ents=["E_9", "E_4"], cites=[], hier=[["N_21", "subcase"]], prag=[["N_21", "depends_on"]],
         creates=["SN_5"], updates=[], relates=[],
         summary="Lena plans a paired t-test, believing participants did both conditions.",
         ref="Paired t-test planned"),
    dict(id="N_23", date="2026-10-19",
         q="Oh, and Dr. Okafor said the project can only use methods from the syllabus. No nonparametric tests.",
         a="Noted. We'll stick to t-tests, ANOVA and regression, which are all in the PSY210 syllabus.",
         act="information", ents=["E_2"], cites=[], hier=[["N_3", "subcase"]], prag=[],
         creates=["SN_7"], updates=[], relates=[["SN_2", "constrained_by"]],
         summary="Dr. Okafor restricts the project to syllabus methods, no nonparametrics.",
         ref="Syllabus-only rule"),
    dict(id="N_24", date="2026-10-19",
         q="Can you tie together everything so far? It feels like a lot of separate formulas.",
         a="It's really one idea: signal divided by noise. The standard error measures the noise; a confidence interval is the estimate ± noise; a t-test divides the difference by the noise; and the p-value says how surprising that ratio would be if there were no effect.",
         act="follow_up", ents=["E_7", "E_8", "E_5"], cites=[], hier=[["N_5", "supercase"], ["N_10", "supercase"], ["N_20", "supercase"]], prag=[["N_18", "references"]],
         creates=[], updates=[], relates=[],
         summary="Recap: SE, CIs, t-tests and p-values are one signal-over-noise idea.",
         ref="Signal-over-noise recap"),
    # ---- Session 4: the project design is wrong -----------------------------------------------
    dict(id="N_25", date="2026-10-26",
         q="I brought the data. It's split into three sleep groups (under 6 hours, 6–8 hours, over 8 hours) with 14, 15 and 13 people, and each person is in exactly one group.",
         a="That changes things: each person is in only one group, so nobody did 'both conditions'.",
         act="information", ents=["E_4"], cites=[], hier=[["N_3", "subcase"]], prag=[["N_22", "references"]],
         creates=[], updates=[], relates=[["SN_5", "contradicts"]],
         summary="The data has three independent sleep groups (14/15/13), not paired measurements.",
         ref="Three independent groups"),
    dict(id="N_26", date="2026-10-26",
         q="So the paired t-test is wrong?",
         a="Yes. With different people in each group the scores are independent, not paired, so a paired t-test is invalid. For comparing two independent groups you'd use Welch's t-test instead.",
         act="correction", ents=["E_9", "E_10"], cites=[], hier=[["N_25", "subcase"]], prag=[["N_22", "contradicts"]],
         creates=[], updates=[["SN_5", "revised"]], relates=[],
         summary="Paired t-test ruled invalid; Welch's t-test for independent groups instead.",
         ref="Switch to Welch's"),
    dict(id="N_27", date="2026-10-26",
         q="Why Welch's and not the regular Student's t-test?",
         a="Student's t-test assumes both groups have equal variances.",
         act="clarification_request", ents=["E_10"], cites=[], hier=[["N_26", "subcase"]], prag=[["N_26", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks why Welch's rather than Student's t-test.",
         ref="Why Welch's"),
    dict(id="N_28", date="2026-10-26",
         q="And is that a problem for my data?",
         a="Your groups have different sizes and noticeably different spreads, so the equal-variance assumption is doubtful. Welch's doesn't need it and loses almost nothing when variances happen to be equal.",
         act="follow_up", ents=["E_10"], cites=[], hier=[["N_27", "subcase"]], prag=[["N_27", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Unequal variances and group sizes favour Welch's test.",
         ref="Unequal variances"),
    dict(id="N_29", date="2026-10-26",
         q="Wait, but I have three groups, not two. Doesn't a t-test only compare two?",
         a="Right, and that settles it: with three groups, running several t-tests inflates false positives. The correct approach is a one-way ANOVA across all three groups, not t-tests.",
         act="decision", ents=["E_11"], cites=[], hier=[["N_26", "same_level"]], prag=[["N_26", "revises"]],
         creates=["SN_6"], updates=[["SN_5", "reverted"]], relates=[],
         summary="Three groups call for a one-way ANOVA; the t-test plan is dropped.",
         ref="One-way ANOVA"),
    dict(id="N_30", date="2026-10-26",
         q="Which significance level should I use?",
         a="The standard alpha = 0.05.",
         act="decision", ents=["E_15"], cites=[], hier=[["N_29", "subcase"]], prag=[["N_29", "depends_on"]],
         creates=["SN_9"], updates=[], relates=[],
         summary="Alpha set at 0.05.",
         ref="Alpha 0.05"),
    dict(id="N_31", date="2026-10-26",
         q="And if the ANOVA is significant, I compare the pairs of groups with 0.05 too?",
         a="Not quite. The ANOVA itself uses 0.05, but the three pairwise post-hoc comparisons each need a correction. With Bonferroni, that's 0.05 / 3 ≈ 0.017 per comparison.",
         act="correction", ents=["E_15"], cites=[], hier=[["N_30", "subcase"]], prag=[["N_30", "revises"]],
         creates=[], updates=[["SN_9", "revised"]], relates=[],
         summary="Post-hoc pairwise comparisons use a Bonferroni-corrected alpha of about 0.017.",
         ref="Bonferroni 0.017"),
    dict(id="N_32", date="2026-10-26",
         q="So t-tests and ANOVA are basically doing the same thing?",
         a="Yes: both compare variation between groups with variation within groups. A t-test is the special case with two groups, and post-hoc tests are just t-tests with a stricter alpha.",
         act="follow_up", ents=["E_11"], cites=[], hier=[["N_20", "supercase"], ["N_29", "supercase"]], prag=[["N_24", "references"]],
         creates=[], updates=[], relates=[],
         summary="t-tests and ANOVA both compare between-group to within-group variation.",
         ref="t-test as special ANOVA"),
    # ---- Session 5: power, outliers, assumptions -------------------------------------------------
    dict(id="N_33", date="2026-11-02",
         q="Is 42 people even enough for this analysis?",
         a="That depends on how big an effect you're trying to detect; let's work it out properly.",
         act="factual_question", ents=["E_14", "E_4"], cites=[], hier=[["N_29", "subcase"]], prag=[],
         creates=["SN_8"], updates=[], relates=[],
         summary="Asks whether n=42 is enough for the analysis.",
         ref="Sample size question"),
    dict(id="N_34", date="2026-11-02",
         q="What do I need to know to work it out?",
         a="Two ideas: effect size, how big the difference is in standardised units (for ANOVA, Cohen's f, where 0.25 counts as medium), and power, the probability that your study detects an effect of that size if it exists. People aim for 0.80.",
         act="clarification_request", ents=["E_13", "E_14"], cites=[], hier=[["N_33", "subcase"]], prag=[["N_33", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Introduces effect size (Cohen's f) and power (target 0.80).",
         ref="Effect size and power"),
    dict(id="N_35", date="2026-11-02",
         q="Different problem: one participant, P17, has a focus score way below everyone else's. Should I delete them?",
         a="Don't delete a participant just for being extreme; that's a common way to bias results. Keep P17, and add a sensitivity analysis that reruns the test without them. If the conclusion doesn't change, you're fine; if it does, you report both.",
         act="decision", ents=["E_4"], cites=[], hier=[["N_25", "subcase"]], prag=[["N_25", "depends_on"]],
         creates=["SN_11"], updates=[], relates=[],
         summary="Keep outlier P17 and report a sensitivity analysis without them.",
         ref="Keep P17, sensitivity check"),
    dict(id="N_36", date="2026-11-02",
         q="Back to the sample size: what's the answer for my study?",
         a="For a one-way ANOVA with three groups of about 14 and a medium effect (f = 0.25), power is only about 0.3, far below 0.80. Your study is underpowered for a medium effect. That's normal for a course project; state it clearly as a limitation rather than overclaiming a non-significant result.",
         act="information", ents=["E_14", "E_13"], cites=[], hier=[["N_34", "subcase"]], prag=[["N_33", "resolves"], ["N_34", "depends_on"]],
         creates=[], updates=[["SN_8", "resolved"]], relates=[["SN_8", "resolves"], ["SN_2", "constrained_by"]],
         summary="Power is about 0.3 for a medium effect: the study is underpowered, reported as a limitation.",
         ref="Underpowered (~0.3)"),
    dict(id="N_37", date="2026-11-02",
         q="The focus scores look really skewed when I plot them. Does ANOVA still work?",
         a="ANOVA assumes the residuals are roughly normal within each group. With skewed data and small groups, that assumption is worth checking before trusting it.",
         act="factual_question", ents=["E_11"], cites=[], hier=[["N_29", "subcase"]], prag=[],
         creates=["SN_10"], updates=[], relates=[["SN_6", "contradicts"]],
         summary="Skewed focus scores raise the question of whether ANOVA's normality assumption holds.",
         ref="Normality question"),
    dict(id="N_38", date="2026-11-02",
         q="How do I check it?",
         a="Run a Shapiro-Wilk test on the residuals in JASP and look at a Q-Q plot. If normality fails, a nonparametric test would normally be the better choice, but that runs into Dr. Okafor's syllabus rule.",
         act="clarification_request", ents=["E_17", "E_2"], cites=[], hier=[["N_37", "subcase"]], prag=[["N_37", "depends_on"]],
         creates=[], updates=[], relates=[["SN_7", "constrained_by"]],
         summary="Check normality with Shapiro-Wilk and a Q-Q plot in JASP; nonparametrics clash with the syllabus rule.",
         ref="Shapiro-Wilk in JASP"),
    dict(id="N_39", date="2026-11-02",
         q="Shapiro-Wilk gives p < .01, and the Q-Q plot bends away badly at the top.",
         a="Then normality is clearly violated for the focus scores. With groups this small, ANOVA isn't a safe primary test.",
         act="information", ents=["E_11"], cites=[], hier=[["N_38", "subcase"]], prag=[["N_37", "resolves"]],
         creates=[], updates=[["SN_10", "resolved"]], relates=[["SN_10", "resolves"]],
         summary="Normality is clearly violated (Shapiro-Wilk p < .01).",
         ref="Normality violated"),
    dict(id="N_40", date="2026-11-02",
         q="I emailed Dr. Okafor. She says nonparametric tests are allowed if I justify them with the normality check.",
         a="That removes the syllabus restriction for your case, so we can use the right test.",
         act="information", ents=["E_2"], cites=[], hier=[["N_23", "subcase"]], prag=[["N_23", "contradicts"]],
         creates=[], updates=[["SN_7", "lifted"]], relates=[],
         summary="Dr. Okafor allows nonparametric tests with justification; the syllabus rule is lifted.",
         ref="Nonparametrics allowed"),
    dict(id="N_41", date="2026-11-02",
         q="So which test do I use now?",
         a="Kruskal-Wallis as the primary test: it's the nonparametric version of one-way ANOVA and doesn't assume normality, with Dunn's pairwise follow-ups. Keep the ANOVA as a robustness check and report both.",
         act="decision", ents=["E_12", "E_11"], cites=[], hier=[["N_29", "same_level"]], prag=[["N_29", "revises"], ["N_40", "depends_on"]],
         creates=["SN_12"], updates=[], relates=[["SN_6", "supports"]],
         summary="Kruskal-Wallis becomes the primary test, one-way ANOVA a robustness check.",
         ref="Kruskal-Wallis primary"),
    # ---- Session 6: regression, exam review ------------------------------------------------------
    dict(id="N_42", date="2026-11-09",
         q="My sleep variable was actually recorded in hours before I grouped it. Should I use regression instead of groups?",
         a="It's a fair question: turning a continuous variable into groups throws information away.",
         act="factual_question", ents=["E_16", "E_4"], cites=[], hier=[["N_25", "same_level"]], prag=[["N_25", "references"]],
         creates=[], updates=[], relates=[],
         summary="Asks whether regression on continuous sleep hours would be better than groups.",
         ref="Regression instead?"),
    dict(id="N_43", date="2026-11-09",
         q="How does regression relate to what we've done?",
         a="Regression is the general case: ANOVA is regression with group indicators as predictors, and a t-test is the two-group special case. With sleep hours as a continuous predictor, regression uses all the information.",
         act="information", ents=["E_16", "E_11"], cites=[], hier=[["N_29", "supercase"]], prag=[["N_42", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Regression is the general case of ANOVA and t-tests.",
         ref="Regression generalises ANOVA"),
    dict(id="N_44", date="2026-11-09",
         q="Should I switch my project to regression, then?",
         a="Not at this stage: the project brief asks for group comparisons, and your analysis is already sound. Keep the Kruskal-Wallis analysis and mention regression on continuous sleep hours as future work.",
         act="decision", ents=["E_16", "E_12"], cites=[], hier=[["N_42", "subcase"]], prag=[["N_42", "depends_on"]],
         creates=[], updates=[], relates=[["SN_12", "supports"]],
         summary="Keep the grouped Kruskal-Wallis analysis; regression mentioned as future work.",
         ref="Regression as future work"),
    dict(id="N_45", date="2026-11-09",
         q="I submitted the project yesterday!",
         a="Well done: Kruskal-Wallis with an ANOVA robustness check, 95% CIs, the P17 sensitivity analysis and the power limitation. That's a careful analysis.",
         act="information", ents=["E_4"], cites=[], hier=[["N_3", "subcase"]], prag=[["N_44", "depends_on"]],
         creates=[], updates=[["SN_2", "achieved"]], relates=[],
         summary="The course project is submitted.",
         ref="Project submitted"),
    dict(id="N_46", date="2026-11-09",
         q="Now the exam. Can you give me the map of everything, how it all fits together?",
         a="Three layers. Foundations: SD, sampling distribution, standard error. Inference as signal over noise: CIs and p-values. Tests: t-tests for two groups, ANOVA for several, both special cases of regression, plus nonparametric alternatives like Kruskal-Wallis when assumptions fail.",
         act="request", ents=["E_7", "E_8", "E_5", "E_11", "E_16", "E_12"], cites=[], hier=[["N_24", "supercase"], ["N_32", "supercase"], ["N_43", "supercase"]], prag=[],
         creates=[], updates=[], relates=[["SN_1", "supports"]],
         summary="Exam review: a map of the whole course in three layers.",
         ref="Course map"),
    dict(id="N_47", date="2026-11-09",
         q="Practice question: 'A study reports p = 0.04. Interpret it.'",
         a="Your answer should say: if the null hypothesis were true, data at least this extreme would occur about 4% of the time. It does not mean a 4% chance that the null is true, which is the trap you already know from the quiz.",
         act="factual_question", ents=["E_5"], cites=[], hier=[["N_46", "subcase"]], prag=[["N_18", "references"]],
         creates=[], updates=[], relates=[],
         summary="Practice question on interpreting p = 0.04.",
         ref="Practice: p-value"),
    dict(id="N_48", date="2026-11-09",
         q="Practice question: 'Interpret a 95% CI of [2.1, 5.3].'",
         a="If the study were repeated many times, 95% of intervals built this way would contain the true value; this interval excludes zero, so the effect is significant at 0.05.",
         act="factual_question", ents=["E_8"], cites=[], hier=[["N_46", "subcase"]], prag=[["N_14", "references"]],
         creates=[], updates=[], relates=[],
         summary="Practice question on interpreting a 95% CI.",
         ref="Practice: CI"),
    dict(id="N_49", date="2026-11-09",
         q="Last one: 'Which test for three independent groups with skewed data?'",
         a="Kruskal-Wallis, the same situation as your project.",
         act="factual_question", ents=["E_12"], cites=[], hier=[["N_46", "subcase"]], prag=[["N_41", "references"]],
         creates=[], updates=[], relates=[],
         summary="Practice question: Kruskal-Wallis for three skewed independent groups.",
         ref="Practice: which test"),
    dict(id="N_50", date="2026-11-23",
         q="Results are out: I passed PSY210 with a B+!",
         a="Congratulations, Lena! From lost at week 3 to a B+ in seven weeks. That's excellent work.",
         act="feedback", ents=["E_1", "E_3"], cites=[], hier=[], prag=[["N_1", "resolves"]],
         creates=[], updates=[["SN_1", "achieved"]], relates=[],
         summary="Lena passed PSY210 with a B+.",
         ref="Passed with B+"),
]

node_index = {n["id"]: i for i, n in enumerate(NODES)}

# --- Validate backward-in-time edges ---
for n in NODES:
    for tgt, _ in n["hier"] + n["prag"]:
        assert node_index[tgt] < node_index[n["id"]], f"{n['id']} -> {tgt} not backward"

# --- recurrence_count / retrieval_count ---
recurrence = {n["id"]: 0 for n in NODES}
for n in NODES:
    for tgt, _ in n["hier"] + n["prag"]:
        recurrence[tgt] += 1

# --- epistemic_status / epistemic_history ---
status, history = {}, {}
for n in NODES:
    default = "open" if n["act"] in OPEN_DEFAULT_ACTS else "resolved"
    status[n["id"]] = default
    history[n["id"]] = [[n["id"], "creation", default]]

TRANSITION = {
    "revises": lambda cur: "superseded",
    "resolves": lambda cur: "resolved" if cur != "superseded" else "superseded",
    "contradicts": lambda cur: "contested" if cur != "superseded" else "superseded",
}
for n in NODES:
    for tgt, label in n["prag"]:
        if label not in TRANSITION:
            continue
        new = TRANSITION[label](status[tgt])
        history[tgt].append([n["id"], label, new])
        status[tgt] = new

# --- entities.mentioned_in ---
mentioned_in = {eid: [] for eid in ENTITIES}
for n in NODES:
    for eid in n["ents"]:
        mentioned_in[eid].append(n["id"])

# --- state nodes: status + last_updated_turn ---
sn_status = {sid: INITIAL_STATUS[d["type"]] for sid, d in STATE_NODE_DEFS.items()}
sn_creation_turn = {}
sn_last_updated = {sid: {"updates": [], "relates": []} for sid in STATE_NODE_DEFS}
sn_label = {sid: d["label"] for sid, d in STATE_NODE_DEFS.items()}
for n in NODES:
    for sid in n["creates"]:
        sn_creation_turn[sid] = n["id"]
    for sid, new_status in n["updates"]:
        sn_status[sid] = new_status
        sn_last_updated[sid]["updates"].append([n["id"], new_status])
        override = LABEL_OVERRIDES.get((sid, n["id"]))
        if override:
            sn_label[sid] = override
    for sid, relation in n["relates"]:
        sn_last_updated[sid]["relates"].append([n["id"], relation])

# --- Assemble output ---
interaction_nodes = {}
for n in NODES:
    interaction_nodes[n["id"]] = {
        "question": n["q"],
        "answer": n["a"],
        "embedding": f"<vector: {n['id']} question+answer>",
        "named_entities": n["ents"],
        "citations": n["cites"],
        "speech_act": n["act"],
        "epistemic_status": status[n["id"]],
        "epistemic_history": history[n["id"]],
        "recurrence_count": recurrence[n["id"]],
        "retrieval_count": recurrence[n["id"]],
        "summary": n["summary"],
        "reference": n["ref"],
        "edges": {"hierarchical": n["hier"], "pragmatic": n["prag"]},
        "state_node_links": {
            k: v for k, v in {
                "creates": n["creates"], "updates": n["updates"], "relates": n["relates"],
            }.items() if v
        },
    }

entities_out = {
    eid: {"type": d["type"], "name": d["name"], "mentioned_in": mentioned_in[eid]}
    for eid, d in ENTITIES.items()
}

state_nodes_out = {
    sid: {
        "type": d["type"],
        "label": sn_label[sid],
        "embedding": f"<vector: {sid} label>",
        "creation_turn": sn_creation_turn[sid],
        "status": sn_status[sid],
        "last_updated_turn": sn_last_updated[sid],
    }
    for sid, d in STATE_NODE_DEFS.items()
}

ground_truth = {
    "conversation_id": "tutoring_stats",
    "domain": "Tutoring dialogue: introductory statistics over six weekly sessions",
    "schema_note": (
        "Mirrors INESCTEC_RESEARCH.md section 3/4 output schema, same convention as "
        "conversations/marathon_trip. Domain entity types (domain_config.json): concept, method, dataset. "
        "Built to exercise supercase via recap turns (N_24, N_32, N_43, N_46), a misconception accepted early "
        "(N_6/N_7) and corrected later (N_18 contradicts N_7, N_19 revises N_7), a decision revised then "
        "reverted (SN_5: paired -> Welch's -> dropped for ANOVA), and constraint: lifted (SN_7). First "
        "tutoring corpus, as named in the workplan."
    ),
    "schema_findings": [
        {
            "raised_at_node": "N_6",
            "issue": "The tutor's vague answer at N_6 neither confirms nor corrects Lena's misreading, but the "
                     "misconception is only recorded at N_7 (Lena writing it down). The error is a joint "
                     "product of two turns, and only N_7 states it explicitly.",
            "proposed_direction": "N_18 contradicts N_7 (the explicit false statement) and resolves N_6 (the "
                                   "open question). Annotators should target the turn that states the claim, "
                                   "not the one that merely failed to correct it.",
        },
        {
            "raised_at_node": "N_29",
            "issue": "SN_5 is revised (N_26, paired -> Welch's) and then reverted in the same session (N_29), "
                     "replaced by SN_6. The interaction edge N_29 -> N_26 is revises, because the analysis plan "
                     "is refined further (two-group test -> multi-group test), even though the state node itself "
                     "is reverted.",
            "proposed_direction": "Interaction edges describe what the turn does to the earlier turn; state-node "
                                   "status describes the fate of the decision. They can legitimately differ, and "
                                   "the gold keeps both as authored.",
        },
        {
            "raised_at_node": "N_36",
            "issue": "The outline assumed power of about 0.45; the correct value for a one-way ANOVA with three "
                     "groups of ~14 and f = 0.25 is about 0.3. The corpus uses 0.3.",
            "proposed_direction": "No schema change; recorded so the outline and corpus aren't read as inconsistent.",
        },
    ],
    "interaction_nodes": interaction_nodes,
    "entities": entities_out,
    "state_nodes": state_nodes_out,
}

corpus = [
    {"id": n["id"], "date": n["date"], "turns": [
        {"speaker": "user", "text": n["q"]},
        {"speaker": "assistant", "text": n["a"]},
    ]}
    for n in NODES
]

out_dir = Path(__file__).resolve().parent
(out_dir / "corpus.json").write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n")
(out_dir / "ground_truth.json").write_text(json.dumps(ground_truth, indent=2, ensure_ascii=False) + "\n")

print(f"Wrote {len(NODES)} interaction nodes, {len(ENTITIES)} entities, {len(STATE_NODE_DEFS)} state nodes.")
print("Epistemic status:", dict(Counter(status.values())))
print("Speech acts:", dict(Counter(n["act"] for n in NODES)))
print("Hierarchical:", dict(Counter(l for n in NODES for _, l in n["hier"])))
print("Pragmatic:", dict(Counter(l for n in NODES for _, l in n["prag"])))
print("State nodes:", dict(Counter((d["type"], sn_status[sid]) for sid, d in STATE_NODE_DEFS.items())))
print("Entity types:", dict(Counter(d["type"] for d in ENTITIES.values())))
