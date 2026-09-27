"""Construct conversations/ml_debugging/{corpus.json, ground_truth.json}.

Same method as conversations/marathon_trip/build.py and hpc_support/build.py:
raw per-node fields are authored below; recurrence_count, retrieval_count,
epistemic_status/history, entities.mentioned_in, and state_nodes
status/last_updated_turn are derived programmatically.

Hypotheses are modelled as open_question state nodes (H1-H5), so the corpus
exercises epistemic status changes more densely than any other. Outline:
outline.md in this folder.
"""
import json
from collections import Counter
from pathlib import Path

INITIAL_STATUS = {"goal": "active", "decision": "active", "constraint": "active", "open_question": "open"}
OPEN_DEFAULT_ACTS = {"factual_question", "clarification_request"}

ENTITIES = {
    "E_1": {"type": "person", "name": "Sam"},
    "E_2": {"type": "model", "name": "LeafScan-v3"},
    "E_3": {"type": "model", "name": "ResNet-50"},
    "E_4": {"type": "dataset", "name": "PlantVillage-ext"},
    "E_5": {"type": "dataset", "name": "field set"},
    "E_6": {"type": "system", "name": "LeafScan field app"},
    "E_7": {"type": "measurement", "name": "validation accuracy"},
    "E_8": {"type": "measurement", "name": "field accuracy"},
    "E_9": {"type": "experiment", "name": "exp-dedup"},
    "E_10": {"type": "experiment", "name": "exp-interp"},
    "E_11": {"type": "experiment", "name": "exp-jpeg-aug"},
    "E_12": {"type": "experiment", "name": "exp-finetune-field"},
    "E_13": {"type": "hyperparameter", "name": "resize interpolation"},
    "E_14": {"type": "hyperparameter", "name": "JPEG-quality augmentation"},
    "E_15": {"type": "hyperparameter", "name": "class weights"},
    "E_16": {"type": "tool", "name": "OpenCV"},
    "E_17": {"type": "tool", "name": "Pillow"},
    "E_18": {"type": "person", "name": "Joana"},
    "E_19": {"type": "tool", "name": "Weights & Biases"},
}

STATE_NODE_DEFS = {
    "SN_1": {"type": "goal", "label": "Raise LeafScan field accuracy to at least 85%"},
    "SN_2": {"type": "open_question", "label": "H1: Is there train/validation leakage inflating validation accuracy?"},
    "SN_3": {"type": "open_question", "label": "H2: Does the field app normalise images differently from training?"},
    "SN_4": {"type": "open_question", "label": "H3: Does resize interpolation differ between training and the field app?"},
    "SN_5": {"type": "decision", "label": "Use OpenCV INTER_AREA resizing in both the training pipeline and the field app"},
    "SN_6": {"type": "open_question", "label": "H4: Is the field class distribution shifted relative to training?"},
    "SN_7": {"type": "decision", "label": "Retrain LeafScan with inverse-frequency class weights"},
    "SN_8": {"type": "open_question", "label": "H5: Is phone JPEG compression causing the remaining accuracy gap?"},
    "SN_9": {"type": "decision", "label": "Add random JPEG-quality (30-90) augmentation to training"},
    "SN_10": {"type": "constraint", "label": "Labelling budget of 500 field images"},
    "SN_11": {"type": "decision", "label": "Fine-tune the full model on labelled field images"},
    "SN_12": {"type": "decision", "label": "Deduplicate data splits with perceptual hashing before every retrain"},
}

LABEL_OVERRIDES = {
    ("SN_10", "N_43"): "Labelling budget of 800 field images (originally: 500)",
    ("SN_11", "N_44"): "Fine-tune on 800 labelled field images with the backbone frozen, training only the head and last block (originally: full fine-tune)",
}

NODES = [
    # ---- Symptom ---------------------------------------------------------------
    dict(id="N_1", date="2026-03-02",
         q="I need help debugging a model. LeafScan-v3, our plant-disease classifier (a ResNet-50), gets 94% validation accuracy, but in the field app it's around 61%. Management wants the field number at 85% or better. Where do I start?",
         a="A 33-point gap between validation and deployment almost always means the validation number is inflated, the deployment inputs differ from training inputs, or the deployment data distribution differs. Before guessing, let's pin down exactly how the 61% is measured.",
         act="request", ents=["E_1", "E_2", "E_3", "E_7", "E_8", "E_6"], cites=[], hier=[], prag=[],
         creates=["SN_1"], updates=[], relates=[],
         summary="LeafScan scores 94% validation but ~61% in the field; goal set to reach 85% field accuracy.",
         ref="Field gap reported, 85% goal"),
    dict(id="N_2", date="2026-03-02",
         q="What exactly do you need to know about how the field accuracy is measured?",
         a="Where the field images come from, who labelled them, and how many there are. If the 61% comes from a few dozen images it may just be noise; if it's a properly labelled set, it's a real gap.",
         act="clarification_request", ents=["E_8"], cites=[], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Assistant asks how the field accuracy is measured.",
         ref="Field measurement questioned"),
    dict(id="N_3", date="2026-03-02",
         q="It's 1,200 photos taken through the app by farmers last season, labelled by Joana's agronomy team. So it's a solid number.",
         a="Then the gap is real. 1,200 expert-labelled images is plenty to trust a 30-point difference.",
         act="information", ents=["E_5", "E_18", "E_6"], cites=[], hier=[["N_2", "subcase"]], prag=[["N_2", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Field accuracy is measured on 1,200 expert-labelled app photos, so the gap is real.",
         ref="Field set: 1,200 labelled photos"),
    dict(id="N_4", date="2026-03-02",
         q="OK, so what could be causing it?",
         a="Five usual suspects, roughly cheapest to check first: (1) train/validation leakage inflating the 94%; (2) a preprocessing mismatch such as normalisation; (3) a resize or interpolation mismatch; (4) a shift in the class distribution; (5) image-quality differences such as compression or lighting. Each can be tested with a small experiment.",
         act="suggestion", ents=[], cites=[], hier=[["N_1", "subcase"]], prag=[["N_3", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Assistant lists five candidate causes of the gap.",
         ref="Five candidate causes"),
    dict(id="N_5", date="2026-03-02",
         q="Let's go through them in that order then, cheapest first.",
         a="Agreed. I'll keep each one as an explicit hypothesis so we can record what we ruled in or out and how many points it explains.",
         act="agreement", ents=[], cites=[], hier=[], prag=[["N_4", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Agree to test the hypotheses cheapest first.",
         ref="Test cheapest first"),
    # ---- H1: leakage ---------------------------------------------------------------
    dict(id="N_6", date="2026-03-02",
         q="Starting with leakage: could the validation accuracy be inflated by duplicate images across the train and validation splits?",
         a="It's worth checking first because it's cheap and common.",
         act="factual_question", ents=["E_4", "E_7"], cites=[], hier=[["N_4", "subcase"]], prag=[["N_4", "depends_on"]],
         creates=["SN_2"], updates=[], relates=[],
         summary="Opens H1: train/validation leakage via duplicate images.",
         ref="H1 leakage opened"),
    dict(id="N_7", date="2026-03-03",
         q="How likely do you think leakage is, honestly?",
         a="Very likely, and probably the main cause. PlantVillage-style datasets are known for near-duplicate photos of the same leaf, and a random split puts them on both sides. I'd expect deduplication alone to close most of the gap.",
         act="factual_question", ents=["E_4"], cites=[], hier=[["N_6", "subcase"]], prag=[["N_6", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Assistant predicts leakage is very likely the main cause of the gap.",
         ref="Leakage predicted as main cause"),
    dict(id="N_8", date="2026-03-03",
         q="How do I find the duplicates?",
         a="Compute a perceptual hash (pHash) for every image and flag pairs across splits with a Hamming distance of 6 or less. Exact file hashes miss re-saved or slightly cropped copies; pHash catches them.",
         act="request", ents=[], cites=[], hier=[["N_6", "subcase"]], prag=[["N_7", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks how to find duplicates; answer: perceptual hashing across splits.",
         ref="pHash method"),
    dict(id="N_9", date="2026-03-03",
         q="Script is written. Should I just drop the flagged validation images?",
         a="Drop them from validation, re-split by leaf/plant ID if you have it, and log it as its own run so we can see the before/after cleanly. Call it exp-dedup.",
         act="follow_up", ents=["E_9"], cites=[], hier=[["N_8", "subcase"]], prag=[["N_8", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Plan exp-dedup: drop flagged validation duplicates and log the run.",
         ref="exp-dedup planned"),
    dict(id="N_10", date="2026-03-03",
         q="Running exp-dedup now; I'm tracking everything in Weights & Biases.",
         a="Good. When it finishes, look at both the number of duplicates found and the new validation accuracy.",
         act="information", ents=["E_9", "E_19"], cites=[], hier=[["N_9", "subcase"]], prag=[["N_9", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="exp-dedup running, tracked in Weights & Biases.",
         ref="exp-dedup running"),
    dict(id="N_11", date="2026-03-04",
         q="Results: only 3% of validation images had near-duplicates in train. After removing them, validation drops from 94% to 91%. That's it.",
         a="Then I was wrong that leakage is the main cause: it's real but minor, worth about 3 points. Most of the gap has to be somewhere else.",
         act="information", ents=["E_9", "E_7"], cites=[], hier=[["N_10", "subcase"]], prag=[["N_7", "contradicts"]],
         creates=[], updates=[], relates=[],
         summary="exp-dedup: 3% duplicates, validation 94% -> 91%; leakage is real but minor.",
         ref="Leakage only ~3 points"),
    dict(id="N_12", date="2026-03-04",
         q="Should we keep the dedup step anyway?",
         a="Yes. It's cheap and stops the validation number from lying again. Make it a fixed step: deduplicate the splits with perceptual hashing before every retrain. H1 is closed: leakage exists but explains about 3 points.",
         act="decision", ents=["E_9"], cites=[], hier=[["N_11", "subcase"]], prag=[["N_6", "resolves"]],
         creates=["SN_12"], updates=[["SN_2", "resolved"]], relates=[["SN_2", "resolves"]],
         summary="H1 closed (minor leakage); perceptual-hash dedup before every retrain adopted.",
         ref="Dedup before every retrain"),
    dict(id="N_13", date="2026-03-04",
         q="So we're at 91% validation versus 61% field. The gap is still 30 points.",
         a="Right, and that's actually informative: a clean validation set is still far above the field, so the problem is in how field images differ from training images, not in how we measure.",
         act="follow_up", ents=["E_7", "E_8"], cites=[], hier=[], prag=[["N_11", "depends_on"]],
         creates=[], updates=[], relates=[["SN_1", "constrained_by"]],
         summary="After dedup the gap is still 30 points; the cause lies in field-vs-training inputs.",
         ref="Gap still 30 points"),
    # ---- H2: normalisation ------------------------------------------------------------
    dict(id="N_14", date="2026-03-05",
         q="What's the next hypothesis to check?",
         a="Preprocessing. My bet is the app skips the ImageNet mean/std normalisation the model was trained with; that's the most common deployment bug with ResNets, and it would easily cost 30 points.",
         act="suggestion", ents=["E_6", "E_3"], cites=[], hier=[["N_4", "subcase"]], prag=[],
         creates=["SN_3"], updates=[], relates=[],
         summary="Assistant proposes H2: the app skips ImageNet normalisation.",
         ref="H2 normalisation proposed"),
    dict(id="N_15", date="2026-03-05",
         q="How would I check that without reading all of the mobile team's code?",
         a="Compare what the model actually receives rather than reading code.",
         act="request", ents=[], cites=[], hier=[["N_14", "subcase"]], prag=[["N_14", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks how to check normalisation without reading the app code.",
         ref="How to check preprocessing"),
    dict(id="N_16", date="2026-03-05",
         q="Compare it how, concretely?",
         a="Run the same 20 photos through the training dataloader and through the app's preprocessing (the mobile team can dump the input tensors), then compare per-channel mean and std and a few raw pixel values.",
         act="clarification_request", ents=["E_6"], cites=[], hier=[["N_15", "subcase"]], prag=[["N_15", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Dump app input tensors and compare channel statistics with the training pipeline.",
         ref="Tensor-dump comparison"),
    dict(id="N_17", date="2026-03-06",
         q="Got the dumps. The per-channel mean and std are identical: the app normalises exactly like training.",
         a="Then my normalisation guess was wrong. The app applies the same ImageNet normalisation.",
         act="information", ents=["E_6"], cites=[], hier=[["N_16", "subcase"]], prag=[["N_14", "contradicts"]],
         creates=[], updates=[], relates=[],
         summary="Tensor dumps show identical normalisation; the H2 guess is wrong.",
         ref="Normalisation identical"),
    dict(id="N_18", date="2026-03-06",
         q="So H2 is out?",
         a="Yes, H2 is ruled out: normalisation is not the problem.",
         act="agreement", ents=[], cites=[], hier=[], prag=[["N_17", "depends_on"]],
         creates=[], updates=[["SN_3", "resolved"]], relates=[["SN_3", "resolves"]],
         summary="H2 ruled out.",
         ref="H2 ruled out"),
    # ---- H3: resize interpolation ------------------------------------------------------
    dict(id="N_19", date="2026-03-06",
         q="One odd thing though: even with the same normalisation stats, the individual pixel values in the dumps don't match between the two pipelines.",
         a="That's a good catch. Matching statistics but different pixels points at the resize step: different resampling produces slightly different images from the same photo.",
         act="information", ents=["E_13"], cites=[], hier=[["N_14", "same_level"]], prag=[["N_16", "references"]],
         creates=["SN_4"], updates=[], relates=[],
         summary="Pixel values differ despite matching statistics; opens H3 on resize interpolation.",
         ref="H3 resize opened"),
    dict(id="N_20", date="2026-03-06",
         q="You're right. Training resizes with Pillow's bilinear filter; the app uses OpenCV with nearest-neighbour.",
         a="Nearest-neighbour downscaling from a 12-megapixel phone photo to 224×224 produces heavy aliasing, which destroys exactly the fine lesion texture the model relies on.",
         act="information", ents=["E_17", "E_16", "E_13"], cites=[], hier=[["N_19", "subcase"]], prag=[["N_19", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Training uses Pillow bilinear, the app uses OpenCV nearest-neighbour resizing.",
         ref="Pillow bilinear vs OpenCV nearest"),
    dict(id="N_21", date="2026-03-07",
         q="What's the fix?",
         a="Make the app match training: switch the app to Pillow's bilinear resize so both pipelines are identical.",
         act="suggestion", ents=["E_17", "E_6"], cites=[], hier=[["N_20", "subcase"]], prag=[["N_20", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Assistant suggests switching the app to Pillow bilinear resizing.",
         ref="Switch app to Pillow suggested"),
    dict(id="N_22", date="2026-03-07",
         q="The mobile team says that's not possible: the app runs on-device and can't ship Pillow. OpenCV is the only image library they have.",
         a="Then the app can't match training; training has to match the app instead.",
         act="information", ents=["E_16", "E_17", "E_6"], cites=[], hier=[["N_21", "subcase"]], prag=[["N_21", "contradicts"]],
         creates=[], updates=[], relates=[],
         summary="The app cannot ship Pillow, so the suggested fix is not possible.",
         ref="Pillow not possible on-device"),
    dict(id="N_23", date="2026-03-07",
         q="So which setting should both use?",
         a="Standardise on OpenCV's INTER_AREA in both training and the app: it's available on-device and is the right filter for downscaling. I reran with that as exp-interp, and field accuracy goes from 61% to 67%. H3 confirmed: interpolation was worth about 6 points.",
         act="decision", ents=["E_16", "E_10", "E_13", "E_8"], cites=[], hier=[["N_22", "subcase"]], prag=[["N_21", "revises"], ["N_19", "resolves"]],
         creates=["SN_5"], updates=[["SN_4", "resolved"]], relates=[["SN_4", "resolves"], ["SN_1", "supports"]],
         summary="Both pipelines standardise on OpenCV INTER_AREA; exp-interp raises field accuracy 61% -> 67%.",
         ref="OpenCV INTER_AREA everywhere"),
    dict(id="N_24", date="2026-03-09",
         q="Quick recap before we continue. Where are we?",
         a="Leakage [N_12] explained about 3 points of validation inflation, and the interpolation mismatch [N_23] about 6 points of field accuracy. Normalisation was ruled out. Field is at 67%, so about 18 points remain.",
         act="follow_up", ents=["E_8"], cites=["N_12", "N_23"], hier=[["N_12", "supercase"], ["N_23", "supercase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Recap: leakage ~3 points, interpolation ~6 points; field at 67%, 18 points to go.",
         ref="Recap after H1-H3"),
    # ---- H4: class shift -------------------------------------------------------------
    dict(id="N_25", date="2026-03-09",
         q="Next one: I looked at the labels, and the field set is 48% 'healthy' leaves, while training is only 12% healthy. Is that a problem?",
         a="That's a large prior shift. A model trained on 12% healthy will under-predict 'healthy' on data that is 48% healthy.",
         act="factual_question", ents=["E_5", "E_4"], cites=[], hier=[["N_4", "subcase"]], prag=[],
         creates=["SN_6"], updates=[], relates=[],
         summary="Field set is 48% healthy vs 12% in training; opens H4 on class shift.",
         ref="H4 class shift opened"),
    dict(id="N_26", date="2026-03-09",
         q="How much can a prior shift like that cost?",
         a="Potentially a lot, if 'healthy' leaves are being misclassified as mild diseases. The usual first remedy is class reweighting during training.",
         act="information", ents=[], cites=[], hier=[["N_25", "subcase"]], prag=[["N_25", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="A prior shift can cost a lot; class reweighting suggested.",
         ref="Prior shift can hurt"),
    dict(id="N_27", date="2026-03-10",
         q="OK, let's try that: retrain with class weights.",
         a="Use inverse-frequency class weights in the loss, keep everything else fixed, and compare on the field set.",
         act="decision", ents=["E_15"], cites=[], hier=[["N_25", "subcase"]], prag=[["N_26", "depends_on"]],
         creates=["SN_7"], updates=[], relates=[],
         summary="Decides to retrain with inverse-frequency class weights.",
         ref="Class-weighted retrain"),
    dict(id="N_28", date="2026-03-11",
         q="Weighted model results: field accuracy 66%, down 1 point. Recall on rare diseases went up, but recall on 'healthy' dropped a lot.",
         a="So reweighting traded 'healthy' recall for rare-class recall, and with 48% healthy in the field that's a net loss in accuracy.",
         act="information", ents=["E_15", "E_8"], cites=[], hier=[["N_27", "subcase"]], prag=[["N_27", "depends_on"]],
         creates=[], updates=[], relates=[["SN_7", "contradicts"]],
         summary="Class weights lower field accuracy to 66% by hurting 'healthy' recall.",
         ref="Class weights: 66%"),
    dict(id="N_29", date="2026-03-11",
         q="That's worse! Reweighting was supposed to fix this.",
         a="On accuracy, yes, it's worse, but macro-F1 actually improved, so the model didn't get worse at telling classes apart. That tells us the problem is calibration to the field prior, not the features.",
         act="disagreement", ents=[], cites=[], hier=[], prag=[["N_28", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Sam objects the result is worse; assistant points to improved macro-F1 and a calibration issue.",
         ref="Worse accuracy, better macro-F1"),
    dict(id="N_30", date="2026-03-11",
         q="So what does that mean for H4?",
         a="H4 is confirmed, but as a calibration problem: the field class prior differs, and the fix belongs at inference time rather than in training. Adjust the logits by the log-ratio of field to training priors.",
         act="information", ents=[], cites=[], hier=[["N_29", "subcase"]], prag=[["N_25", "resolves"]],
         creates=[], updates=[["SN_6", "resolved"]], relates=[["SN_6", "resolves"]],
         summary="H4 confirmed as a calibration issue, to be fixed with logit prior adjustment at inference.",
         ref="H4: fix at inference"),
    dict(id="N_31", date="2026-03-11",
         q="Then do we keep the class weights?",
         a="No, drop the class weights entirely and go back to the unweighted model, with the logit prior adjustment at inference.",
         act="decision", ents=["E_15"], cites=[], hier=[["N_27", "same_level"]], prag=[["N_27", "contradicts"], ["N_30", "depends_on"]],
         creates=[], updates=[["SN_7", "reverted"]], relates=[],
         summary="Class weights dropped; unweighted model with inference-time prior adjustment.",
         ref="Drop class weights"),
    dict(id="N_32", date="2026-03-11",
         q="With the prior adjustment, field accuracy is 69%.",
         a="Good: +2 points over 67%, and no training change needed. 16 points still to go.",
         act="information", ents=["E_8"], cites=[], hier=[], prag=[["N_31", "depends_on"]],
         creates=[], updates=[], relates=[["SN_1", "supports"]],
         summary="Prior adjustment brings field accuracy to 69%.",
         ref="Field at 69%"),
    # ---- H5: JPEG compression -----------------------------------------------------------
    dict(id="N_33", date="2026-03-12",
         q="Last hypothesis. The app saves photos as heavily compressed JPEGs (quality around 40) before uploading, while all our training images are PNGs. Could that matter?",
         a="Let's think about how much compression artefacts would affect a CNN.",
         act="factual_question", ents=["E_6", "E_4"], cites=[], hier=[["N_4", "subcase"]], prag=[],
         creates=["SN_8"], updates=[], relates=[],
         summary="Opens H5: app photos are heavily compressed JPEGs, training images are PNG.",
         ref="H5 JPEG opened"),
    dict(id="N_34", date="2026-03-12",
         q="What's your intuition?",
         a="Honestly, I think it's unlikely to matter much. ResNets are fairly robust to JPEG artefacts at moderate quality; I'd expect a point or two at most.",
         act="factual_question", ents=["E_3"], cites=[], hier=[["N_33", "subcase"]], prag=[["N_33", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Assistant expects JPEG compression to matter only marginally.",
         ref="JPEG predicted minor"),
    dict(id="N_35", date="2026-03-13",
         q="I tested it anyway: I re-compressed the clean validation set to JPEG quality 40, and validation accuracy drops from 91% to 74%.",
         a="That's a 17-point drop, which is not marginal at all.",
         act="information", ents=["E_7"], cites=[], hier=[["N_34", "subcase"]], prag=[["N_34", "contradicts"]],
         creates=[], updates=[], relates=[],
         summary="Re-compressing validation to JPEG q=40 drops accuracy 91% -> 74%.",
         ref="JPEG costs 17 points"),
    dict(id="N_36", date="2026-03-13",
         q="So you were wrong about this one too?",
         a="Yes, I retract it. Compression is the biggest remaining factor, not a minor one. At quality 40 the blocking artefacts wipe out the fine lesion textures, and the model has never seen them during training.",
         act="correction", ents=[], cites=[], hier=[["N_35", "subcase"]], prag=[["N_34", "revises"]],
         creates=[], updates=[], relates=[],
         summary="Assistant retracts: compression is the biggest remaining factor.",
         ref="Compression biggest factor"),
    dict(id="N_37", date="2026-03-14",
         q="How do we fix it without changing the app?",
         a="Train with the artefacts: add random JPEG re-compression at quality 30–90 as an augmentation. As exp-jpeg-aug, field accuracy reaches 78%. H5 confirmed.",
         act="decision", ents=["E_11", "E_14", "E_8"], cites=[], hier=[["N_33", "subcase"]], prag=[["N_33", "resolves"]],
         creates=["SN_9"], updates=[["SN_8", "resolved"]], relates=[["SN_8", "resolves"], ["SN_1", "supports"]],
         summary="Random JPEG-quality augmentation added; exp-jpeg-aug reaches 78% field accuracy.",
         ref="JPEG augmentation: 78%"),
    dict(id="N_38", date="2026-03-14",
         q="78% is great progress, but it's still short of 85%.",
         a="Agreed. We've fixed the input mismatches we know about. The remaining 7 points are probably field conditions the training data never covered, like lighting, backgrounds and leaf angles, so the next step is some real field data in training.",
         act="follow_up", ents=["E_8"], cites=[], hier=[], prag=[["N_37", "depends_on"]],
         creates=[], updates=[], relates=[["SN_1", "contradicts"]],
         summary="78% still short of 85%; next step is training on real field data.",
         ref="Still 7 points short"),
    # ---- Field fine-tuning ---------------------------------------------------------------
    dict(id="N_39", date="2026-03-16",
         q="Joana says her team can label 500 more field images for us, beyond the 1,200 test set.",
         a="500 labelled field images is enough to fine-tune on, as long as the 1,200 set stays untouched for testing.",
         act="information", ents=["E_18", "E_5"], cites=[], hier=[["N_38", "subcase"]], prag=[],
         creates=["SN_10"], updates=[], relates=[],
         summary="Labelling budget: 500 extra field images from Joana's team.",
         ref="500-image labelling budget"),
    dict(id="N_40", date="2026-03-16",
         q="Then let's fine-tune the whole model on those 500 once they're labelled.",
         a="OK: fine-tune all layers on the 500 field images with a low learning rate, and evaluate on the untouched field test set.",
         act="decision", ents=["E_12"], cites=[], hier=[["N_39", "subcase"]], prag=[["N_39", "depends_on"]],
         creates=["SN_11"], updates=[], relates=[["SN_10", "constrained_by"]],
         summary="Decides to fine-tune the full model on the 500 field images.",
         ref="Full fine-tune decided"),
    dict(id="N_41", date="2026-03-17",
         q="The full fine-tune overfits: training accuracy on the 500 goes to 99%, but the held-out field set only reaches 80%.",
         a="Classic: 500 images is too few to move 25 million parameters safely.",
         act="information", ents=["E_12", "E_8"], cites=[], hier=[["N_40", "subcase"]], prag=[["N_40", "depends_on"]],
         creates=[], updates=[], relates=[["SN_11", "contradicts"]],
         summary="Full fine-tune overfits: 80% on held-out field data.",
         ref="Full fine-tune overfits"),
    dict(id="N_42", date="2026-03-17",
         q="What would you change?",
         a="Freeze the backbone and train only the classifier head plus the last residual block. Far fewer parameters, much less overfitting.",
         act="suggestion", ents=["E_3"], cites=[], hier=[["N_41", "subcase"]], prag=[["N_41", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Assistant suggests freezing the backbone and training only the head and last block.",
         ref="Freeze backbone suggested"),
    dict(id="N_43", date="2026-03-17",
         q="Also, good news: Joana got approval to label 800 images instead of 500.",
         a="Even better: more data plus a frozen backbone should reduce overfitting further.",
         act="information", ents=["E_18"], cites=[], hier=[["N_39", "same_level"]], prag=[["N_39", "revises"]],
         creates=[], updates=[["SN_10", "revised"]], relates=[],
         summary="Labelling budget raised from 500 to 800 images.",
         ref="Budget raised to 800"),
    dict(id="N_44", date="2026-03-18",
         q="So the plan is the frozen backbone with all 800 images?",
         a="Yes: fine-tune on the 800 labelled field images with the backbone frozen, training only the head and the last block, with JPEG augmentation and INTER_AREA resizing kept on.",
         act="decision", ents=["E_12", "E_14", "E_16"], cites=[], hier=[["N_42", "subcase"]], prag=[["N_40", "revises"], ["N_43", "depends_on"]],
         creates=[], updates=[["SN_11", "revised"]], relates=[["SN_5", "supports"], ["SN_9", "supports"]],
         summary="Plan revised: frozen-backbone fine-tune on 800 field images.",
         ref="Frozen-backbone fine-tune"),
    dict(id="N_45", date="2026-03-18",
         q="Does the dedup rule we set earlier also apply to the new field images?",
         a="It does apply, and it matters even more here.",
         act="factual_question", ents=["E_5"], cites=[], hier=[["N_12", "subcase"]], prag=[["N_12", "references"]],
         creates=[], updates=[], relates=[],
         summary="Asks whether the dedup rule applies to field images.",
         ref="Dedup for field images?"),
    dict(id="N_46", date="2026-03-18",
         q="Why even more?",
         a="Farmers often take burst shots of the same leaf. If near-identical frames land in both the 800 fine-tuning images and the 1,200 test set, the field number gets inflated exactly as validation was. Run the pHash dedup across both sets before fine-tuning.",
         act="clarification_request", ents=["E_5"], cites=[], hier=[["N_45", "subcase"]], prag=[["N_45", "resolves"]],
         creates=[], updates=[], relates=[["SN_12", "supports"]],
         summary="Burst-shot duplicates make dedup essential between fine-tuning and test field sets.",
         ref="Burst-shot duplicates"),
    dict(id="N_47", date="2026-03-19",
         q="exp-finetune-field is done: after dedup, 86% on the field test set.",
         a="86%! That clears the 85% target, on a deduplicated test set, so the number is trustworthy.",
         act="information", ents=["E_12", "E_8"], cites=[], hier=[], prag=[["N_44", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="exp-finetune-field reaches 86% field accuracy after dedup.",
         ref="Field at 86%"),
    dict(id="N_48", date="2026-03-19",
         q="So we're done with the target.",
         a="Yes, the 85% goal is met.",
         act="agreement", ents=[], cites=[], hier=[], prag=[["N_47", "depends_on"], ["N_1", "resolves"]],
         creates=[], updates=[["SN_1", "achieved"]], relates=[],
         summary="The 85% field accuracy goal is achieved.",
         ref="Goal achieved"),
    dict(id="N_49", date="2026-03-20",
         q="I need to write the post-mortem. Can you list every cause we found and roughly what each was worth?",
         a="Starting from 61% field: interpolation mismatch fixed with OpenCV INTER_AREA [N_23], +6; field class prior fixed with inference-time logit adjustment, class weights dropped [N_31], +2; JPEG compression fixed with quality 30–90 augmentation [N_37], +9; frozen-backbone fine-tuning on 800 deduplicated field images [N_44], +8, for 86% in total. Separately, leakage inflated validation by about 3 points and is now prevented by dedup before every retrain.",
         act="request", ents=["E_8"], cites=["N_23", "N_31", "N_37", "N_44"], hier=[["N_24", "supercase"], ["N_31", "supercase"], ["N_37", "supercase"], ["N_44", "supercase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Post-mortem: each cause and its effect on field accuracy, 61% -> 86%.",
         ref="Post-mortem summary"),
    dict(id="N_50", date="2026-03-20",
         q="And for honesty's sake: which of your early guesses turned out to be wrong?",
         a="Three: I called leakage the main cause [N_7] (it was about 3 points), I bet on a normalisation bug [N_14] (normalisation was identical), and I said JPEG compression was unlikely to matter [N_34] (it was the largest single factor).",
         act="follow_up", ents=[], cites=["N_7", "N_14", "N_34"], hier=[], prag=[["N_7", "references"], ["N_14", "references"], ["N_34", "references"]],
         creates=[], updates=[], relates=[],
         summary="Assistant lists its three wrong early guesses for the post-mortem.",
         ref="Wrong guesses listed"),
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
    "conversation_id": "ml_debugging",
    "domain": "Debugging an ML image classifier's validation-vs-field accuracy gap",
    "schema_note": (
        "Mirrors INESCTEC_RESEARCH.md section 3/4 output schema, same convention as "
        "conversations/marathon_trip and hpc_support. Domain entity types (domain_config.json): model, "
        "dataset, experiment, hyperparameter. Built to exercise dense contradicts (experiments refuting the "
        "assistant's hypotheses: N_11->N_7, N_17->N_14, N_22->N_21, N_31->N_27, N_35->N_34), hypotheses as "
        "open_question state nodes (H1-H5, all resolved), and assistant self-correction (N_36 revises N_34)."
    ),
    "schema_findings": [
        {
            "raised_at_node": "N_11",
            "issue": "An experiment refuting a hypothesis is recorded twice: at the interaction level (N_11 "
                     "contradicts N_7, the turn that asserted it) and at the state-node level (SN_2 resolved at "
                     "N_12, where the conclusion is drawn). Refutation and resolution fall on different turns.",
            "proposed_direction": "Keep both. The interaction edge marks where the claim was contradicted; the "
                                   "state-node update marks where the open question was closed. Annotators should "
                                   "not force them onto the same turn.",
        },
        {
            "raised_at_node": "N_30",
            "issue": "A hypothesis can be 'confirmed' with a different mechanism than proposed (H4: the class shift "
                     "is real, but it's a calibration problem, not a training one). open_question only has "
                     "open/resolved, so 'resolved' covers confirmed, refuted and reframed alike.",
            "proposed_direction": "Record the outcome in the resolving turn's summary rather than extending the "
                                   "status enum. Flag if Phase 4 needs to distinguish confirmed from refuted.",
        },
        {
            "raised_at_node": "N_31",
            "issue": "N_31 contradicts N_27 (a decision turn by the user, not an assistant claim) and reverts SN_7. "
                     "Using contradicts, not revises, because the class-weight decision is abandoned, not refined.",
            "proposed_direction": "Convention: revises when a decision is adjusted and still stands in modified "
                                   "form (e.g. N_44 revises N_40); contradicts when it is dropped outright.",
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
