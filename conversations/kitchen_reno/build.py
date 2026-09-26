"""Construct conversations/kitchen_reno/{corpus.json, ground_truth.json}.

Same method as conversations/marathon_trip/build.py: raw per-node fields are
authored below; recurrence_count, retrieval_count, epistemic_status/history,
entities.mentioned_in, and state_nodes status/last_updated_turn are derived
programmatically.

Numbers that keep changing (total budget, cabinet line item, wall length,
start date), and a late turn (N_41) that repeats a stale number in passing, to
trip recency-only retrieval. Running totals are checked by BUDGET below.
Outline: outline.md in this folder.
"""
import json
from collections import Counter
from pathlib import Path

INITIAL_STATUS = {"goal": "active", "decision": "active", "constraint": "active", "open_question": "open"}
OPEN_DEFAULT_ACTS = {"factual_question", "clarification_request"}

ENTITIES = {
    "E_1": {"type": "person", "name": "Carla"},
    "E_2": {"type": "person", "name": "Miguel"},
    "E_3": {"type": "location", "name": "Alvalade apartment"},
    "E_4": {"type": "organization", "name": "Ferreira Obras"},
    "E_5": {"type": "organization", "name": "Casa Nova Remodelações"},
    "E_6": {"type": "person", "name": "Sr. Ferreira"},
    "E_7": {"type": "person", "name": "Ana"},
    "E_8": {"type": "measurement", "name": "total renovation budget"},
    "E_9": {"type": "measurement", "name": "cabinet budget"},
    "E_10": {"type": "measurement", "name": "back wall length"},
    "E_11": {"type": "material", "name": "quartz"},
    "E_12": {"type": "material", "name": "HPL laminate"},
    "E_13": {"type": "material", "name": "porcelain tile"},
    "E_14": {"type": "product", "name": "induction hob"},
    "E_15": {"type": "product", "name": "built-in oven"},
    "E_16": {"type": "trade", "name": "electrician"},
    "E_17": {"type": "organization", "name": "Câmara Municipal de Lisboa"},
    "E_18": {"type": "organization", "name": "IKEA"},
}

STATE_NODE_DEFS = {
    "SN_1": {"type": "goal", "label": "Finish the kitchen before Miguel's parents visit in early May"},
    "SN_2": {"type": "constraint", "label": "Total renovation budget of €18,000"},
    "SN_3": {"type": "decision", "label": "IKEA Metod cabinets, budgeted at €4,200"},
    "SN_4": {"type": "decision", "label": "Hire Ferreira Obras as the contractor"},
    "SN_5": {"type": "decision", "label": "Hire Casa Nova Remodelações as the contractor (€9,400 fixed price)"},
    "SN_6": {"type": "decision", "label": "Quartz countertop (€2,300)"},
    "SN_7": {"type": "decision", "label": "Stone-look HPL laminate countertop (€800)"},
    "SN_8": {"type": "open_question", "label": "Is a permit (comunicação prévia) needed to move the gas line?"},
    "SN_9": {"type": "decision", "label": "Switch from a gas hob to an induction hob"},
    "SN_10": {"type": "constraint", "label": "The back wall is 3.40 m long"},
    "SN_11": {"type": "decision", "label": "Works start on 2 March"},
    "SN_12": {"type": "decision", "label": "Put the oven in a tall column cabinet, not under the hob"},
    "SN_13": {"type": "constraint", "label": "Induction requires an electrical circuit upgrade (+€650)"},
}

LABEL_OVERRIDES = {
    ("SN_10", "N_17"): "The back wall is 3.28 m long, out of plumb (originally measured as 3.40 m)",
    ("SN_3", "N_22"): "IKEA Metod cabinets plus custom filler panels and a narrow custom unit, budgeted at €5,100 (originally €4,200)",
    ("SN_2", "N_29"): "Total renovation budget of €21,500 after a family top-up (originally €18,000)",
    ("SN_11", "N_33"): "Works start on 16 March (originally 2 March), because of a tile delivery delay",
    ("SN_3", "N_36"): "IKEA Metod cabinets with a standard 30 cm drawer unit, no custom pieces, budgeted at €4,600 (originally €4,200, then €5,100)",
}

# Running totals quoted in the dialogue, recomputed here so the numbers can't drift.
BUDGET = {
    "N_23": 5100 + 9400 + 2300 + 2900,               # cabinets + labour + quartz + appliances/tiles
    "N_26": 5100 + 9400 + 2300 + 2900 + 650,         # + circuit upgrade
    "N_27": 5100 + 9400 + 800 + 2900 + 650,          # quartz -> laminate
    "N_32": 5100 + 9400 + 800 + 2900 + 650 + 900,    # + oven column
    "N_48": 4600 + 9400 + 800 + 2900 + 900 + 1100 + 350,  # final: cabinets cut, no upgrade, rewiring, extra tiles
}
assert BUDGET == {"N_23": 19700, "N_26": 20350, "N_27": 18850, "N_32": 19750, "N_48": 20050}, BUDGET

NODES = [
    # ---- Planning & first numbers (Jan) ----------------------------------------------
    dict(id="N_1", date="2026-01-10",
         q="Hi! I'm Carla. My partner Miguel and I want to redo the kitchen in our Alvalade apartment. His parents are visiting in early May and we want it done before then. Where do we start?",
         a="Nice project. Early May gives about four months, which is realistic for a kitchen if decisions don't drag. Start with the budget and the layout; almost everything else follows from those two.",
         act="request", ents=["E_1", "E_2", "E_3"], cites=[], hier=[], prag=[],
         creates=["SN_1"], updates=[], relates=[],
         summary="Carla and Miguel want to renovate their kitchen before early May.",
         ref="Kitchen before May"),
    dict(id="N_2", date="2026-01-10",
         q="Our total budget is €18,000, and we really can't go above it.",
         a="€18,000 is workable for a mid-range kitchen in Lisbon if the layout stays mostly as it is. We'll treat it as a hard cap.",
         act="decision", ents=["E_8"], cites=[], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=["SN_2"], updates=[], relates=[],
         summary="Total budget capped at €18,000.",
         ref="Budget €18,000"),
    dict(id="N_3", date="2026-01-10",
         q="How is a budget like that usually split?",
         a="Roughly: cabinets 25%, countertop 10–15%, labour 35–45%, appliances and tiles 15%, plus a contingency if you can. Labour is usually the biggest single line in Lisbon.",
         act="factual_question", ents=["E_8"], cites=[], hier=[["N_2", "subcase"]], prag=[["N_2", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Typical budget split: labour largest, cabinets ~25%, counter 10-15%.",
         ref="Budget split"),
    dict(id="N_4", date="2026-01-11",
         q="For the layout, should we go L-shaped or galley?",
         a="That depends on the room. What are the dimensions, and where are the window and the door?",
         act="factual_question", ents=[], cites=[], hier=[["N_1", "subcase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Asks about L-shaped vs galley layout.",
         ref="Layout question"),
    dict(id="N_5", date="2026-01-11",
         q="The window is on the short wall and the door is opposite it, so the long back wall is free.",
         a="Then an L-shape along the back wall and the window wall works well: it keeps the door path clear and gives you the most counter space.",
         act="information", ents=[], cites=[], hier=[["N_4", "same_level"]], prag=[["N_4", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Room layout suits an L-shape along the back and window walls.",
         ref="L-shape layout"),
    dict(id="N_6", date="2026-01-11",
         q="I measured the back wall: 3.40 m.",
         a="Good; the cabinet plan will be built around 3.40 m of run on that wall.",
         act="information", ents=["E_10"], cites=[], hier=[["N_4", "subcase"]], prag=[["N_5", "depends_on"]],
         creates=["SN_10"], updates=[], relates=[],
         summary="Back wall measured at 3.40 m.",
         ref="Wall 3.40 m"),
    dict(id="N_7", date="2026-01-12",
         q="IKEA or custom cabinets?",
         a="With your budget, IKEA. Custom joinery for an L-shape would easily eat half the budget on its own.",
         act="factual_question", ents=["E_18"], cites=[], hier=[["N_3", "subcase"]], prag=[["N_3", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks IKEA vs custom cabinets; IKEA recommended.",
         ref="IKEA vs custom"),
    dict(id="N_8", date="2026-01-12",
         q="I did the IKEA planner for Metod cabinets: €4,200 for the whole L.",
         a="That's about 23% of the budget, right in range. Metod cabinets at €4,200 it is.",
         act="decision", ents=["E_18", "E_9"], cites=[], hier=[["N_7", "subcase"]], prag=[["N_7", "resolves"]],
         creates=["SN_3"], updates=[], relates=[["SN_2", "constrained_by"]],
         summary="IKEA Metod cabinets chosen at €4,200.",
         ref="Cabinets €4,200"),
    dict(id="N_9", date="2026-01-15",
         q="We asked two contractors for labour quotes. Ferreira Obras quoted €7,900.",
         a="That's on the low end for demolition, plumbing, electrics and installation. Check what's excluded.",
         act="information", ents=["E_4"], cites=[], hier=[["N_3", "subcase"]], prag=[["N_3", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Ferreira Obras quotes €7,900 for labour.",
         ref="Ferreira quote €7,900"),
    dict(id="N_10", date="2026-01-15",
         q="And Casa Nova Remodelações quoted €9,400, but as a fixed price, and they include waste removal.",
         a="A fixed price with waste removal is worth something: fewer surprises. €1,500 more, but with a firm number.",
         act="information", ents=["E_5"], cites=[], hier=[["N_9", "same_level"]], prag=[["N_9", "references"]],
         creates=[], updates=[], relates=[],
         summary="Casa Nova quotes €9,400 fixed price including waste removal.",
         ref="Casa Nova quote €9,400"),
    dict(id="N_11", date="2026-01-15",
         q="Which one would you pick?",
         a="On numbers alone Ferreira is cheaper. If the budget is truly tight, Ferreira, as long as the scope is written down.",
         act="follow_up", ents=["E_4", "E_5"], cites=[], hier=[["N_9", "subcase"]], prag=[["N_10", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Assistant leans towards the cheaper Ferreira quote.",
         ref="Leaning Ferreira"),
    dict(id="N_12", date="2026-01-16",
         q="We'll go with Ferreira Obras then.",
         a="OK, Ferreira Obras. Get the quote itemised and signed before any work starts.",
         act="decision", ents=["E_4"], cites=[], hier=[["N_11", "subcase"]], prag=[["N_11", "depends_on"]],
         creates=["SN_4"], updates=[], relates=[],
         summary="Ferreira Obras hired.",
         ref="Hire Ferreira"),
    dict(id="N_13", date="2026-01-18",
         q="Countertop: what material?",
         a="For the look you described, quartz or a good stone-look laminate. Quartz is more durable; laminate is much cheaper.",
         act="factual_question", ents=["E_11", "E_12"], cites=[], hier=[["N_3", "subcase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Asks about countertop material: quartz vs laminate.",
         ref="Countertop question"),
    dict(id="N_14", date="2026-01-18",
         q="We love quartz. The quote is €2,300 for both runs.",
         a="Quartz at €2,300 is about 13% of the budget, within range. Quartz it is.",
         act="decision", ents=["E_11"], cites=[], hier=[["N_13", "subcase"]], prag=[["N_13", "resolves"]],
         creates=["SN_6"], updates=[], relates=[["SN_2", "constrained_by"]],
         summary="Quartz countertop chosen at €2,300.",
         ref="Quartz €2,300"),
    dict(id="N_15", date="2026-01-20",
         q="We want the hob on the back wall instead of by the window. That means moving the gas line. Do we need a permit?",
         a="Moving a gas line is regulated work; it may need a comunicação prévia to the Câmara.",
         act="factual_question", ents=["E_17"], cites=[], hier=[["N_4", "subcase"]], prag=[],
         creates=["SN_8"], updates=[], relates=[],
         summary="Moving the hob means moving the gas line; opens whether a permit is needed.",
         ref="Gas line permit?"),
    dict(id="N_16", date="2026-01-20",
         q="How do I find out for sure?",
         a="Ask the Câmara's urbanism desk or have the contractor check. Gas works also need a certified gas technician and an inspection afterwards.",
         act="clarification_request", ents=["E_17"], cites=[], hier=[["N_15", "subcase"]], prag=[["N_15", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Check with the Câmara; gas work needs a certified technician and inspection.",
         ref="Check with Câmara"),
    # ---- Problems (Feb) ----------------------------------------------------------------------
    dict(id="N_17", date="2026-02-01",
         q="Sr. Ferreira came to measure properly: the back wall is actually 3.28 m, not 3.40. It's out of plumb and narrower at the top.",
         a="That's 12 cm less than the plan assumes, which matters for the cabinet run.",
         act="correction", ents=["E_6", "E_10"], cites=[], hier=[["N_6", "subcase"]], prag=[["N_6", "revises"]],
         creates=[], updates=[["SN_10", "revised"]], relates=[],
         summary="Back wall re-measured at 3.28 m, out of plumb.",
         ref="Wall 3.28 m"),
    dict(id="N_18", date="2026-02-01",
         q="He also sent a revised quote: €2,100 extra 'for surprises', and he can only start in six weeks.",
         a="An open-ended €2,100 'surprises' line on a quote you chose for being cheap removes its main advantage, and a six-week wait threatens the May deadline.",
         act="information", ents=["E_6", "E_4"], cites=[], hier=[["N_12", "subcase"]], prag=[["N_12", "depends_on"]],
         creates=[], updates=[], relates=[["SN_4", "contradicts"], ["SN_1", "constrained_by"]],
         summary="Ferreira adds €2,100 for 'surprises' and a six-week wait.",
         ref="Ferreira revised quote"),
    dict(id="N_19", date="2026-02-02",
         q="We're not comfortable with that. Should we drop Ferreira?",
         a="Yes. Ferreira at €10,000 with an open-ended line is now more expensive than Casa Nova's fixed price, and slower.",
         act="decision", ents=["E_4"], cites=[], hier=[["N_18", "subcase"]], prag=[["N_12", "contradicts"]],
         creates=[], updates=[["SN_4", "reverted"]], relates=[],
         summary="Ferreira Obras dropped.",
         ref="Drop Ferreira"),
    dict(id="N_20", date="2026-02-02",
         q="Then we go with Casa Nova?",
         a="Yes: Casa Nova Remodelações at their €9,400 fixed price [N_10]. Ana will be your project manager.",
         act="decision", ents=["E_5", "E_7"], cites=["N_10"], hier=[["N_19", "subcase"]], prag=[["N_19", "depends_on"], ["N_10", "references"]],
         creates=["SN_5"], updates=[], relates=[],
         summary="Casa Nova Remodelações hired at €9,400 fixed.",
         ref="Hire Casa Nova"),
    dict(id="N_21", date="2026-02-03",
         q="Ana says they can start on 2 March.",
         a="2 March leaves about eight weeks before early May, enough for a six-week job with some slack.",
         act="decision", ents=["E_7"], cites=[], hier=[["N_20", "subcase"]], prag=[["N_20", "depends_on"]],
         creates=["SN_11"], updates=[], relates=[["SN_1", "supports"]],
         summary="Works to start 2 March.",
         ref="Start 2 March"),
    dict(id="N_22", date="2026-02-05",
         q="Because the wall is 3.28 m, the 40 cm drawer unit no longer fits. IKEA's planner suggests custom filler panels and a narrow custom unit. Cabinets go up to €5,100.",
         a="The 12 cm shortfall forces custom pieces, so the cabinet line rises from €4,200 to €5,100.",
         act="information", ents=["E_9", "E_10", "E_18"], cites=[], hier=[["N_8", "subcase"]], prag=[["N_17", "depends_on"], ["N_8", "revises"]],
         creates=[], updates=[["SN_3", "revised"]], relates=[],
         summary="The shorter wall forces custom pieces; cabinets rise to €5,100.",
         ref="Cabinets €5,100"),
    dict(id="N_23", date="2026-02-05",
         q="Where does that leave the total?",
         a="Cabinets €5,100 + labour €9,400 + quartz €2,300 + appliances and tiles about €2,900 = €19,700. That's €1,700 over the €18,000 cap.",
         act="follow_up", ents=["E_8"], cites=[], hier=[["N_2", "subcase"]], prag=[["N_2", "depends_on"]],
         creates=[], updates=[], relates=[["SN_2", "contradicts"]],
         summary="Running total €19,700, €1,700 over budget.",
         ref="Total €19,700"),
    dict(id="N_24", date="2026-02-07",
         q="Idea: if we switch to an induction hob, there's no gas line to move at all. Does that also get rid of the permit question?",
         a="Yes. With induction there's no gas work, so there's nothing to notify the Câmara about and no gas inspection. The permit question disappears. Switching to induction solves both problems.",
         act="decision", ents=["E_14", "E_17"], cites=[], hier=[["N_15", "subcase"]], prag=[["N_15", "resolves"]],
         creates=["SN_9"], updates=[["SN_8", "resolved"]], relates=[["SN_8", "resolves"]],
         summary="Switch to induction: no gas work, so no permit needed.",
         ref="Switch to induction"),
    dict(id="N_25", date="2026-02-08",
         q="Ana says induction needs a dedicated circuit, so the electrician has to upgrade it: about €650.",
         a="That's a common requirement. It adds €650, so we need to keep an eye on the total.",
         act="information", ents=["E_7", "E_16", "E_14"], cites=[], hier=[["N_24", "subcase"]], prag=[["N_24", "depends_on"]],
         creates=["SN_13"], updates=[], relates=[],
         summary="Induction needs a circuit upgrade, +€650.",
         ref="Circuit upgrade +€650"),
    dict(id="N_26", date="2026-02-08",
         q="So now we're at €20,350? Where can we cut?",
         a="Yes, €20,350. The biggest flexible line is the countertop: a good stone-look laminate is around €800 versus €2,300 for quartz.",
         act="follow_up", ents=["E_8", "E_11", "E_12"], cites=[], hier=[["N_23", "same_level"]], prag=[["N_23", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Total €20,350; the countertop is the biggest flexible cost.",
         ref="Total €20,350"),
    dict(id="N_27", date="2026-02-09",
         q="OK. We'll switch the countertop from quartz to the stone-look HPL laminate.",
         a="That saves €1,500 and brings the total to €18,850. Still €850 over, but much closer.",
         act="decision", ents=["E_12", "E_11"], cites=[], hier=[["N_13", "subcase"]], prag=[["N_14", "contradicts"], ["N_26", "resolves"]],
         creates=["SN_7"], updates=[["SN_6", "reverted"]], relates=[],
         summary="Countertop switched from quartz to HPL laminate; total €18,850.",
         ref="Laminate countertop"),
    dict(id="N_28", date="2026-02-10",
         q="Miguel hates the idea. He says laminate will look cheap.",
         a="Modern HPL stone-look laminates are quite convincing, and they handle heat and scratches reasonably well. It's worth seeing a sample in person before deciding it looks cheap.",
         act="disagreement", ents=["E_2", "E_12"], cites=[], hier=[], prag=[["N_27", "depends_on"]],
         creates=[], updates=[], relates=[["SN_7", "contradicts"]],
         summary="Miguel objects to the laminate countertop.",
         ref="Miguel objects"),
    dict(id="N_29", date="2026-02-12",
         q="News: Miguel's parents offered to help. They're adding €3,500, so our budget is now €21,500.",
         a="That's very generous, and it changes the picture: the budget is now €21,500.",
         act="information", ents=["E_2", "E_8"], cites=[], hier=[["N_2", "subcase"]], prag=[["N_2", "revises"]],
         creates=[], updates=[["SN_2", "revised"]], relates=[],
         summary="A family top-up raises the budget to €21,500.",
         ref="Budget €21,500"),
    dict(id="N_30", date="2026-02-12",
         q="So should we go back to quartz?",
         a="You could afford it now. But think about what else the margin could buy that you'd use more.",
         act="factual_question", ents=["E_11"], cites=[], hier=[["N_27", "subcase"]], prag=[["N_29", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks whether to go back to quartz given the bigger budget.",
         ref="Back to quartz?"),
    dict(id="N_31", date="2026-02-12",
         q="We talked it over. We'll keep the laminate and instead put the oven in a tall column cabinet at eye level, not under the hob. Miguel's mother has a bad back.",
         a="Good use of the margin. A tall oven column adds about €900 for the cabinet and installation, and it's far more comfortable to use. Laminate stays.",
         act="decision", ents=["E_15", "E_12"], cites=[], hier=[["N_30", "subcase"]], prag=[["N_30", "resolves"]],
         creates=["SN_12"], updates=[], relates=[["SN_7", "supports"]],
         summary="Keep laminate; add a tall oven column (+€900) instead of an under-hob oven.",
         ref="Oven in tall column"),
    dict(id="N_32", date="2026-02-14",
         q="Can you recap the whole budget now?",
         a="Cabinets €5,100 [N_22], labour with Casa Nova €9,400 [N_20], laminate €800 [N_27], appliances and tiles €2,900, circuit upgrade €650, oven column €900 [N_31]: €19,750 against a €21,500 budget, leaving €1,750 of contingency.",
         act="follow_up", ents=["E_8", "E_9", "E_5", "E_12", "E_15"], cites=["N_20", "N_22", "N_27", "N_31"], hier=[["N_8", "supercase"], ["N_20", "supercase"], ["N_27", "supercase"], ["N_31", "supercase"]], prag=[],
         creates=[], updates=[], relates=[["SN_2", "supports"]],
         summary="Budget recap: €19,750 planned against €21,500.",
         ref="Budget recap €19,750"),
    # ---- Execution (Mar-Apr) -------------------------------------------------------------------
    dict(id="N_33", date="2026-02-24",
         q="Bad news: the porcelain tiles are delayed two weeks, so Ana moved the start to 16 March.",
         a="16 March instead of 2 March. That eats most of the slack before May.",
         act="information", ents=["E_13", "E_7"], cites=[], hier=[["N_21", "subcase"]], prag=[["N_21", "revises"]],
         creates=[], updates=[["SN_11", "revised"]], relates=[],
         summary="Start moved to 16 March because of a tile delay.",
         ref="Start 16 March"),
    dict(id="N_34", date="2026-02-24",
         q="Will it still be done before the visit in early May?",
         a="Let's check it against Casa Nova's schedule.",
         act="factual_question", ents=[], cites=[], hier=[["N_33", "subcase"]], prag=[["N_33", "depends_on"]],
         creates=[], updates=[], relates=[["SN_1", "constrained_by"]],
         summary="Asks whether the later start still finishes before May.",
         ref="Still before May?"),
    dict(id="N_35", date="2026-02-24",
         q="Ana says it's a six-week job.",
         a="Six weeks from 16 March ends around 27 April. Tight, but it works, provided the cabinets and tiles arrive on time.",
         act="information", ents=["E_7"], cites=[], hier=[["N_34", "subcase"]], prag=[["N_34", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Six weeks from 16 March ends around 27 April: tight but feasible.",
         ref="Ends ~27 April"),
    dict(id="N_36", date="2026-03-02",
         q="Good news: IKEA restocked a standard 30 cm Metod drawer unit. With it, the 3.28 m wall only needs a small standard filler, no custom pieces.",
         a="Then drop the custom filler panels and the narrow custom unit. Cabinets come down to €4,600.",
         act="decision", ents=["E_18", "E_9", "E_10"], cites=[], hier=[["N_22", "same_level"]], prag=[["N_22", "revises"]],
         creates=[], updates=[["SN_3", "revised"]], relates=[],
         summary="A standard 30 cm unit replaces the custom pieces; cabinets €4,600.",
         ref="Cabinets €4,600"),
    dict(id="N_37", date="2026-03-16",
         q="Demolition started today!",
         a="Exciting. The first few days usually reveal whatever is hiding behind the old cabinets.",
         act="information", ents=["E_5"], cites=[], hier=[["N_1", "subcase"]], prag=[["N_33", "depends_on"]],
         creates=[], updates=[], relates=[["SN_1", "supports"]],
         summary="Demolition starts on 16 March.",
         ref="Demolition started"),
    dict(id="N_38", date="2026-03-18",
         q="They found old cloth-insulated wiring behind the back wall. Ana says it has to be replaced: €1,100.",
         a="That has to be done; old cloth wiring is a fire risk. It comes out of the contingency.",
         act="information", ents=["E_7", "E_16"], cites=[], hier=[["N_37", "subcase"]], prag=[["N_37", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Old cloth wiring found; replacement costs €1,100.",
         ref="Rewiring €1,100"),
    dict(id="N_39", date="2026-03-19",
         q="Since the electrician is redoing the wiring anyway, does that change the induction circuit upgrade?",
         a="It might; ask him to check what the hob actually needs against what's there.",
         act="factual_question", ents=["E_16", "E_14"], cites=[], hier=[["N_38", "subcase"]], prag=[["N_25", "references"]],
         creates=[], updates=[], relates=[],
         summary="Asks whether the rewiring changes the induction upgrade.",
         ref="Upgrade still needed?"),
    dict(id="N_40", date="2026-03-19",
         q="The electrician checked: the existing 32A line to the hob position is enough for our induction hob. No upgrade needed.",
         a="So the €650 circuit upgrade [N_25] is off the list; it partly offsets the rewiring.",
         act="information", ents=["E_16", "E_14"], cites=["N_25"], hier=[["N_39", "subcase"]], prag=[["N_25", "contradicts"], ["N_39", "resolves"]],
         creates=[], updates=[["SN_13", "lifted"]], relates=[],
         summary="The existing 32A line suffices; the €650 upgrade is dropped.",
         ref="No upgrade needed"),
    dict(id="N_41", date="2026-03-20",
         q="Funny: Miguel told his parents on the phone that our '€18k kitchen' is coming along nicely. I didn't correct him.",
         a="Ha, that number stuck from the beginning. It's a good sign that things feel on track.",
         act="information", ents=["E_2", "E_8"], cites=[], hier=[], prag=[["N_2", "references"]],
         creates=[], updates=[], relates=[],
         summary="Miguel mentions the old '€18k' figure in passing.",
         ref="Stale €18k mention"),
    dict(id="N_42", date="2026-03-25",
         q="Tiling started. Do we tile the whole wall or just the backsplash?",
         a="Just the backsplash, up to the wall cabinets. Full-height tiling adds cost and time for little benefit.",
         act="factual_question", ents=["E_13"], cites=[], hier=[["N_37", "subcase"]], prag=[["N_37", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Tiling only the backsplash.",
         ref="Backsplash only"),
    dict(id="N_43", date="2026-03-30",
         q="The cabinets are being installed. The small filler at the end of the 3.28 m wall looks fine.",
         a="Good; the standard filler works because the 30 cm unit absorbed most of the difference.",
         act="information", ents=["E_9", "E_10"], cites=[], hier=[["N_42", "same_level"]], prag=[["N_36", "depends_on"], ["N_17", "references"]],
         creates=[], updates=[], relates=[["SN_3", "supports"]],
         summary="Cabinet installation fits the 3.28 m wall.",
         ref="Cabinets fit"),
    dict(id="N_44", date="2026-04-02",
         q="The oven column is in. Miguel's mother is going to love not bending down.",
         a="That was a good call. It's the change people use every single day.",
         act="information", ents=["E_15"], cites=[], hier=[["N_42", "same_level"]], prag=[["N_31", "depends_on"]],
         creates=[], updates=[], relates=[["SN_12", "supports"]],
         summary="Oven column installed.",
         ref="Oven column in"),
    dict(id="N_45", date="2026-04-06",
         q="We ran a bit short on tiles, since some broke. Ana says another box and fitting is €350.",
         a="Normal breakage. €350 is fine within the remaining contingency.",
         act="information", ents=["E_13", "E_7"], cites=[], hier=[["N_42", "subcase"]], prag=[["N_42", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Extra tiles cost €350.",
         ref="Extra tiles €350"),
    dict(id="N_46", date="2026-04-08",
         q="What colour should we paint the remaining walls?",
         a="A warm off-white goes well with the stone-look laminate and keeps the small room bright.",
         act="factual_question", ents=["E_12"], cites=[], hier=[["N_37", "same_level"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Asks about wall paint colour; warm off-white suggested.",
         ref="Paint colour"),
    dict(id="N_47", date="2026-04-10",
         q="Ana gave us the snag list: a drawer that doesn't close fully and a missing plinth.",
         a="Both are small. Make sure they're fixed before you sign off the final payment.",
         act="information", ents=["E_7"], cites=[], hier=[["N_37", "subcase"]], prag=[["N_45", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Snag list: a drawer and a missing plinth.",
         ref="Snag list"),
    dict(id="N_48", date="2026-04-15",
         q="Final bill: €20,050 in total.",
         a="That matches: the €19,750 plan, minus €500 on cabinets and the €650 upgrade you didn't need, plus €1,100 rewiring and €350 tiles. €20,050 against a €21,500 budget, €1,450 under.",
         act="information", ents=["E_8"], cites=[], hier=[["N_32", "subcase"]], prag=[["N_29", "depends_on"], ["N_32", "depends_on"]],
         creates=[], updates=[], relates=[["SN_2", "supports"]],
         summary="Final bill €20,050, €1,450 under the €21,500 budget.",
         ref="Final bill €20,050"),
    dict(id="N_49", date="2026-04-15",
         q="Looking back, what did we change from our original plan, and why?",
         a="Four big changes. Contractor: Ferreira was dropped for an open-ended extra and a long wait [N_19], replaced by Casa Nova. Hob: induction instead of gas, which removed the permit issue [N_24]. Countertop: laminate instead of quartz to stay on budget [N_27]. Cabinets: back to a standard layout once IKEA restocked the 30 cm unit [N_36]. And the budget itself grew to €21,500.",
         act="follow_up", ents=["E_4", "E_5", "E_14", "E_12", "E_9", "E_8"], cites=["N_19", "N_24", "N_27", "N_36"], hier=[["N_19", "supercase"], ["N_24", "supercase"], ["N_27", "supercase"], ["N_36", "supercase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Retrospective: contractor, hob, countertop and cabinet changes.",
         ref="What changed"),
    dict(id="N_50", date="2026-04-18",
         q="Snags fixed, final payment made. The kitchen is done, two weeks before the visit!",
         a="Congratulations, Carla and Miguel. Finished before the visit and under budget.",
         act="agreement", ents=["E_1", "E_2"], cites=[], hier=[], prag=[["N_1", "resolves"], ["N_47", "depends_on"]],
         creates=[], updates=[["SN_1", "achieved"]], relates=[],
         summary="Kitchen finished two weeks before the visit.",
         ref="Kitchen done"),
]

node_index = {n["id"]: i for i, n in enumerate(NODES)}

# --- Validate backward-in-time edges ---
for n in NODES:
    for tgt, _ in n["hier"] + n["prag"]:
        assert node_index[tgt] < node_index[n["id"]], f"{n['id']} -> {tgt} not backward"

# --- Running totals quoted in the text must match BUDGET ---
for nid, total in BUDGET.items():
    text = next(n["q"] + n["a"] for n in NODES if n["id"] == nid)
    assert f"€{total:,}" in text, f"{nid} does not state €{total:,}"

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
    "conversation_id": "kitchen_reno",
    "domain": "Kitchen renovation planning on a fixed budget",
    "schema_note": (
        "Mirrors INESCTEC_RESEARCH.md section 3/4 output schema, same convention as "
        "conversations/marathon_trip. Domain entity types (domain_config.json): material, product, trade. "
        "Built to exercise numeric state that is revised repeatedly (budget SN_2, cabinets SN_3 twice, wall "
        "SN_10, start date SN_11), two decisions reverted and replaced (contractor SN_4 -> SN_5, countertop "
        "SN_6 -> SN_7), constraint: lifted (SN_13), and a late stale mention of an old value (N_41: '€18k')."
    ),
    "schema_findings": [
        {
            "raised_at_node": "N_41",
            "issue": "N_41 mentions the superseded €18,000 budget in passing (Miguel's phrase), without asserting "
                     "it as current. It is neither a revision nor a contradiction of the current budget.",
            "proposed_direction": "Recorded as references to N_2 only, with no state-node link. This is the "
                                   "intended trap for recency-only retrieval: the most recent budget mention in "
                                   "the conversation carries a stale number.",
        },
        {
            "raised_at_node": "N_27",
            "issue": "N_27 both contradicts N_14 (quartz dropped) and resolves N_26 (where to cut). One turn can "
                     "close a question and overturn an earlier decision at the same time.",
            "proposed_direction": "Keep both pragmatic edges; they target different turns and mean different "
                                   "things.",
        },
        {
            "raised_at_node": "N_48",
            "issue": "The outline's final bill (€20,950) did not add up; the corpus uses €20,050, which build.py "
                     "recomputes from the line items (BUDGET) and asserts against the text.",
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
