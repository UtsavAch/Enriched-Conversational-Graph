"""Construct conversations/relocation/{corpus.json, ground_truth.json}.

Same method as conversations/marathon_trip/build.py: raw per-node fields are
authored below; recurrence_count, retrieval_count, epistemic_status/history,
entities.mentioned_in, and state_nodes status/last_updated_turn are derived
programmatically.

80 turns, six interleaved threads (visa V, housing H, registration & bank R,
school S, insurance I, moving M), each dropped and resumed 10-30 turns later,
with cross-thread dependencies (lease -> Anmeldung -> bank -> deposit ->
school registration). THREADS records which thread each turn belongs to and is
checked against the outline's interleaving. Outline: outline.md.
"""
import json
from collections import Counter
from pathlib import Path

INITIAL_STATUS = {"goal": "active", "decision": "active", "constraint": "active", "open_question": "open"}
OPEN_DEFAULT_ACTS = {"factual_question", "clarification_request"}

ENTITIES = {
    "E_1": {"type": "person", "name": "Daniel"},
    "E_2": {"type": "person", "name": "Sofia"},
    "E_3": {"type": "person", "name": "Lia"},
    "E_4": {"type": "organization", "name": "Brennwerk GmbH"},
    "E_5": {"type": "location", "name": "Munich"},
    "E_6": {"type": "location", "name": "Lisbon"},
    "E_7": {"type": "permit", "name": "EU Blue Card"},
    "E_8": {"type": "permit", "name": "Anmeldung"},
    "E_9": {"type": "organization", "name": "KVR"},
    "E_10": {"type": "organization", "name": "N26"},
    "E_11": {"type": "organization", "name": "Sparkasse"},
    "E_12": {"type": "location", "name": "Haidhausen"},
    "E_13": {"type": "location", "name": "Pasing"},
    "E_14": {"type": "organization", "name": "Grundschule an der Kirchenstraße"},
    "E_15": {"type": "organization", "name": "Bavarian International School"},
    "E_16": {"type": "organization", "name": "Techniker Krankenkasse"},
    "E_17": {"type": "document", "name": "Wohnungsgeberbestätigung"},
    "E_18": {"type": "organization", "name": "Transeuropa Movers"},
    "E_19": {"type": "measurement", "name": "Blue Card salary threshold"},
    "E_20": {"type": "measurement", "name": "monthly rent cap"},
    "E_21": {"type": "event", "name": "start date at Brennwerk"},
}

STATE_NODE_DEFS = {
    "SN_1": {"type": "goal", "label": "Move the family to Munich and be settled before Lia's school year starts"},
    "SN_2": {"type": "decision", "label": "Daniel starts at Brennwerk on 1 July"},
    "SN_3": {"type": "decision", "label": "Apply for the EU Blue Card rather than a general work visa"},
    "SN_4": {"type": "open_question", "label": "Does Sofia get the right to work in Germany?"},
    "SN_5": {"type": "constraint", "label": "Rent cap of €2,300 per month including utilities"},
    "SN_6": {"type": "decision", "label": "Live in Pasing (cheaper, S-Bahn connection)"},
    "SN_7": {"type": "decision", "label": "Live in Haidhausen (walkable to school, shorter commute)"},
    "SN_8": {"type": "decision", "label": "Open an N26 account before arriving"},
    "SN_9": {"type": "decision", "label": "Open a Sparkasse account after the Anmeldung; keep N26 for everyday spending"},
    "SN_10": {"type": "open_question", "label": "Public Grundschule or international school for Lia?"},
    "SN_11": {"type": "decision", "label": "Lia attends the Grundschule an der Kirchenstraße, with a weekly German tutor"},
    "SN_12": {"type": "decision", "label": "Public health insurance with TK, with Sofia and Lia co-insured on Daniel's policy"},
    "SN_13": {"type": "constraint", "label": "The temporary furnished flat is only available until 31 July"},
    "SN_14": {"type": "decision", "label": "Ship household goods with Transeuropa Movers in a full 20 ft container"},
    "SN_15": {"type": "open_question", "label": "Bring the car to Munich or sell it?"},
    "SN_16": {"type": "goal", "label": "Sofia keeps her Lisbon job, working remotely from Munich"},
}

LABEL_OVERRIDES = {
    ("SN_5", "N_27"): "Rent cap of €2,600 per month including utilities, after Brennwerk's relocation allowance (originally €2,300)",
    ("SN_12", "N_41"): "Public health insurance with TK: Daniel with Lia co-insured; Sofia insured through her own employer (originally: Sofia co-insured too)",
    ("SN_2", "N_45"): "Daniel starts at Brennwerk on 15 July (originally 1 July), after the KVR appointment delay",
    ("SN_11", "N_56"): "Lia attends the Grundschule an der Kirchenstraße, starting with six months in the Übergangsklasse (transition class), plus a weekly German tutor",
    ("SN_14", "N_62"): "Ship household goods with Transeuropa Movers in a shared container, fewer items (originally: full 20 ft container)",
}

# Thread per turn: V visa, H housing, R registration/bank, S school, I insurance, M moving, - overview.
THREADS = {}
for rng, t in [((1, 2), "-"), ((3, 6), "V"), ((7, 11), "H"), ((12, 14), "R"), ((15, 18), "S"),
               ((19, 20), "I"), ((21, 23), "V"), ((24, 29), "H"), ((30, 33), "R"), ((34, 38), "S"),
               ((39, 41), "I"), ((42, 43), "M"), ((44, 46), "V"), ((47, 49), "H"), ((50, 53), "R"),
               ((54, 57), "S"), ((58, 60), "I"), ((61, 62), "M"), ((63, 63), "V"), ((64, 65), "H"),
               ((66, 69), "M"), ((70, 71), "-"), ((72, 72), "S"), ((73, 80), "-")]:
    for i in range(rng[0], rng[1] + 1):
        THREADS[f"N_{i}"] = t

NODES = [
    dict(id="N_1", date="2026-04-06",
         q="I'm Daniel, a software engineer in Lisbon. I just accepted an offer from Brennwerk GmbH in Munich. My partner Sofia and our daughter Lia, who's 8, are coming too, and we want to be settled before the German school year starts in September. Where do we even begin?",
         a="Congratulations! A family move to Munich has six moving parts that depend on each other: your work permit, housing, the city registration (Anmeldung) and a bank account, a school for Lia, health insurance, and shipping your things. We'll track each thread, since they interlock.",
         act="request", ents=["E_1", "E_2", "E_3", "E_4", "E_5", "E_6"], cites=[], hier=[], prag=[],
         creates=["SN_1"], updates=[], relates=[],
         summary="Daniel's family is moving from Lisbon to Munich for a Brennwerk job and wants to be settled by September.",
         ref="Move to Munich goal"),
    dict(id="N_2", date="2026-04-06",
         q="Brennwerk wants me to start on 1 July.",
         a="1 July gives about twelve weeks for the permit and a first place to live, which is doable. We'll plan backwards from that date.",
         act="decision", ents=["E_4", "E_21"], cites=[], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=["SN_2"], updates=[], relates=[],
         summary="Start date at Brennwerk set for 1 July.",
         ref="Start 1 July"),
    # ---- V: visa ----
    dict(id="N_3", date="2026-04-07",
         q="First, the work permit. I'm Brazilian-born with only a Brazilian passport, so I do need one. Which permit should I apply for?",
         a="As a non-EU citizen with a university degree and a skilled job offer, the EU Blue Card is usually the best route: faster, and better family rights than a general work visa.",
         act="factual_question", ents=["E_7"], cites=[], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks which work permit to apply for; the EU Blue Card is suggested.",
         ref="Which permit?"),
    dict(id="N_4", date="2026-04-07",
         q="Do I qualify on salary?",
         a="The Blue Card needs a salary above a threshold that's adjusted every year, around €48,000 in 2025. Your offer of €72,000 is comfortably above it.",
         act="information", ents=["E_19"], cites=[], hier=[["N_3", "subcase"]], prag=[["N_3", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="The €72,000 offer is well above the Blue Card salary threshold.",
         ref="Salary qualifies"),
    dict(id="N_5", date="2026-04-07",
         q="Then the Blue Card it is.",
         a="Good. Brennwerk's HR can request a pre-approval from the Federal Employment Agency, which speeds things up.",
         act="decision", ents=["E_7", "E_4"], cites=[], hier=[["N_4", "subcase"]], prag=[["N_3", "resolves"]],
         creates=["SN_3"], updates=[], relates=[],
         summary="Daniel will apply for the EU Blue Card.",
         ref="Blue Card chosen"),
    dict(id="N_6", date="2026-04-07",
         q="What about Sofia? She's also Brazilian. She's a UX designer at a Lisbon agency and wants to keep that job, working remotely from Munich. Is she allowed to work in Germany?",
         a="Good question, and the answer depends on the permit she gets as your family member. Let's check the family rules before she plans on it.",
         act="factual_question", ents=["E_2", "E_6"], cites=[], hier=[["N_5", "subcase"]], prag=[["N_5", "depends_on"]],
         creates=["SN_4", "SN_16"], updates=[], relates=[],
         summary="Asks whether Sofia may work in Germany; she plans to keep her Lisbon job remotely.",
         ref="Sofia's work rights?"),
    # ---- H: housing ----
    dict(id="N_7", date="2026-04-10",
         q="Housing next. Where should we live in Munich?",
         a="Munich is expensive and competitive, so let's first set a budget, then compare neighbourhoods by commute, schools and rent.",
         act="request", ents=["E_5"], cites=[], hier=[["N_1", "subcase"], ["N_3", "same_level"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Asks where to live in Munich.",
         ref="Where to live?"),
    dict(id="N_8", date="2026-04-10",
         q="We can spend at most €2,300 a month, warm.",
         a="€2,300 warm (including heating and utilities) for a family flat in Munich is tight but possible outside the most central areas.",
         act="decision", ents=["E_20"], cites=[], hier=[["N_7", "subcase"]], prag=[["N_7", "depends_on"]],
         creates=["SN_5"], updates=[], relates=[],
         summary="Rent cap set at €2,300 per month warm.",
         ref="Rent cap €2,300"),
    dict(id="N_9", date="2026-04-10",
         q="Which neighbourhoods fit that?",
         a="Pasing is cheaper and has a fast S-Bahn to the centre; Haidhausen is more central and walkable but pricier. Brennwerk's office is in the east, near Haidhausen.",
         act="information", ents=["E_13", "E_12"], cites=[], hier=[["N_8", "subcase"]], prag=[["N_8", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Pasing is cheaper; Haidhausen is central and closer to Brennwerk but pricier.",
         ref="Pasing vs Haidhausen"),
    dict(id="N_10", date="2026-04-11",
         q="Pasing, then. It fits the budget.",
         a="Pasing it is. The S-Bahn commute to the east side is about 35 minutes.",
         act="decision", ents=["E_13"], cites=[], hier=[["N_9", "subcase"]], prag=[["N_9", "depends_on"]],
         creates=["SN_6"], updates=[], relates=[["SN_5", "constrained_by"]],
         summary="Decides to live in Pasing.",
         ref="Live in Pasing"),
    dict(id="N_11", date="2026-04-11",
         q="Anything special about renting in Munich as foreigners?",
         a="Landlords usually ask for a credit record (SCHUFA). You won't have one yet, so bring your employment contract, recent payslips and a Portuguese bank reference instead.",
         act="information", ents=[], cites=[], hier=[["N_7", "subcase"]], prag=[["N_10", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Bring contract, payslips and a bank reference instead of a SCHUFA record.",
         ref="Rental documents"),
    # ---- R: registration & bank ----
    dict(id="N_12", date="2026-04-14",
         q="People keep mentioning the Anmeldung. What is it?",
         a="The Anmeldung is the mandatory registration of your address with the city, within two weeks of moving in. Almost everything else in Germany, from bank accounts to your tax ID, depends on it.",
         act="factual_question", ents=["E_8"], cites=[], hier=[["N_1", "subcase"], ["N_7", "same_level"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Explains the Anmeldung (address registration).",
         ref="What is Anmeldung?"),
    dict(id="N_13", date="2026-04-14",
         q="I'll open an N26 account before we arrive, so we have a German IBAN from day one.",
         a="N26 lets you open an account online before you move, which is handy for salary and everyday spending.",
         act="decision", ents=["E_10"], cites=[], hier=[["N_12", "same_level"]], prag=[],
         creates=["SN_8"], updates=[], relates=[],
         summary="Decides to open an N26 account before arriving.",
         ref="N26 before arrival"),
    dict(id="N_14", date="2026-04-14",
         q="What do I need for the Anmeldung itself?",
         a="Your passport and a Wohnungsgeberbestätigung, a form your landlord signs confirming you moved in. So you can only register once you actually have a flat.",
         act="information", ents=["E_8", "E_17"], cites=[], hier=[["N_12", "subcase"]], prag=[["N_12", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="The Anmeldung needs the landlord's Wohnungsgeberbestätigung.",
         ref="Anmeldung needs landlord form"),
    # ---- S: school ----
    dict(id="N_15", date="2026-04-17",
         q="Lia's school: should she go to a public Grundschule or an international school?",
         a="Both are realistic in Munich; let's look at the trade-offs.",
         act="factual_question", ents=["E_3"], cites=[], hier=[["N_1", "subcase"], ["N_7", "same_level"]], prag=[],
         creates=["SN_10"], updates=[], relates=[],
         summary="Opens the question of public vs international school for Lia.",
         ref="Which school?"),
    dict(id="N_16", date="2026-04-17",
         q="How does a public Grundschule work?",
         a="Free, and assigned by address: each address belongs to one school's catchment area, so where you live decides which Grundschule Lia attends.",
         act="information", ents=[], cites=[], hier=[["N_15", "subcase"]], prag=[["N_15", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Public Grundschule places are assigned by catchment area.",
         ref="Catchment areas"),
    dict(id="N_17", date="2026-04-17",
         q="And the international option?",
         a="The Bavarian International School is the best known. Teaching is in English, but fees are around €18,000 a year.",
         act="information", ents=["E_15"], cites=[], hier=[["N_15", "subcase"]], prag=[["N_16", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="BIS teaches in English but costs about €18,000 a year.",
         ref="BIS fees"),
    dict(id="N_18", date="2026-04-17",
         q="Lia doesn't speak any German. Is a Grundschule even possible?",
         a="Yes. Munich schools have German-support programmes for newly arrived children, and eight-year-olds pick up the language fast.",
         act="follow_up", ents=["E_3"], cites=[], hier=[["N_16", "subcase"]], prag=[["N_17", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Grundschule is possible without German; schools support new arrivals.",
         ref="No German yet"),
    # ---- I: insurance ----
    dict(id="N_19", date="2026-04-20",
         q="Health insurance: public or private?",
         a="With a family and one main earner, public insurance is usually better: your spouse and children can be co-insured for free, whereas private insurance charges per person.",
         act="factual_question", ents=[], cites=[], hier=[["N_1", "subcase"], ["N_15", "same_level"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Asks public vs private health insurance; public favoured for families.",
         ref="Public vs private"),
    dict(id="N_20", date="2026-04-20",
         q="Then public, with Techniker Krankenkasse, and Sofia and Lia co-insured on my policy.",
         a="TK is a good choice with English-language service. Sofia and Lia are co-insured through your membership.",
         act="decision", ents=["E_16", "E_2", "E_3"], cites=[], hier=[["N_19", "subcase"]], prag=[["N_19", "resolves"]],
         creates=["SN_12"], updates=[], relates=[],
         summary="Public insurance with TK; Sofia and Lia co-insured.",
         ref="TK family insurance"),
    # ---- V ----
    dict(id="N_21", date="2026-04-28",
         q="Back to the visa: the earliest appointment at the KVR, Munich's immigration office, is 8 July.",
         a="That's a week after your planned start date. The Blue Card itself is issued at that appointment.",
         act="information", ents=["E_9", "E_7"], cites=[], hier=[["N_5", "subcase"]], prag=[["N_5", "depends_on"]],
         creates=[], updates=[], relates=[["SN_2", "contradicts"]],
         summary="The earliest KVR appointment is 8 July, after the planned start.",
         ref="KVR 8 July"),
    dict(id="N_22", date="2026-04-28",
         q="Can I start working before I have the card?",
         a="Possibly, depending on the entry visa. Let's check what the pre-approval allows.",
         act="factual_question", ents=["E_7"], cites=[], hier=[["N_21", "subcase"]], prag=[["N_21", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks whether he can start working before the card.",
         ref="Start before card?"),
    dict(id="N_23", date="2026-04-28",
         q="What did you find?",
         a="With the pre-approval and a Blue Card entry visa, you may start working before the KVR appointment. And for Sofia: as the spouse of a Blue Card holder, she gets a residence permit with unrestricted work rights, so she can work in Germany, for a German or a foreign employer.",
         act="information", ents=["E_7", "E_2"], cites=[], hier=[["N_22", "subcase"]], prag=[["N_22", "resolves"], ["N_6", "resolves"]],
         creates=[], updates=[["SN_4", "resolved"]], relates=[["SN_4", "resolves"]],
         summary="Daniel can start before the appointment; Sofia gets unrestricted work rights through family reunification.",
         ref="Sofia may work"),
    # ---- H ----
    dict(id="N_24", date="2026-05-04",
         q="Housing update: finding a Pasing flat from Lisbon is impossible, so we found a temporary furnished flat from 1 July instead.",
         a="Sensible: a furnished flat lets you search in person, and you can register your address there.",
         act="information", ents=["E_13"], cites=[], hier=[["N_7", "subcase"]], prag=[["N_10", "references"]],
         creates=[], updates=[], relates=[],
         summary="A temporary furnished flat is booked from 1 July.",
         ref="Temporary flat"),
    dict(id="N_25", date="2026-05-04",
         q="The catch: it's only available until 31 July.",
         a="So you need a permanent lease starting by 1 August. That's the real deadline for the flat search.",
         act="information", ents=[], cites=[], hier=[["N_24", "subcase"]], prag=[["N_24", "depends_on"]],
         creates=["SN_13"], updates=[], relates=[],
         summary="The temporary flat ends on 31 July.",
         ref="Temp flat until 31 July"),
    dict(id="N_26", date="2026-05-06",
         q="Good news: Brennwerk offers a €300 a month relocation allowance for the first year.",
         a="That's real money in the Munich rental market.",
         act="information", ents=["E_4"], cites=[], hier=[["N_7", "subcase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Brennwerk offers a €300/month relocation allowance.",
         ref="€300 allowance"),
    dict(id="N_27", date="2026-05-06",
         q="So we can raise the rent cap?",
         a="Yes: with the allowance, raise the cap to €2,600 warm.",
         act="decision", ents=["E_20"], cites=[], hier=[["N_26", "subcase"]], prag=[["N_8", "revises"], ["N_26", "depends_on"]],
         creates=[], updates=[["SN_5", "revised"]], relates=[],
         summary="Rent cap raised to €2,600 warm.",
         ref="Rent cap €2,600"),
    dict(id="N_28", date="2026-05-08",
         q="With €2,600 we could afford Haidhausen after all. It's walkable to Lia's future school and my commute would be 15 minutes. Should we switch from Pasing?",
         a="Yes, switch to Haidhausen: a 15-minute commute instead of 35, and a walkable school, are worth the extra rent now that it's within budget.",
         act="decision", ents=["E_12", "E_13"], cites=[], hier=[["N_9", "subcase"]], prag=[["N_10", "contradicts"], ["N_27", "depends_on"]],
         creates=["SN_7"], updates=[["SN_6", "reverted"]], relates=[],
         summary="Switches from Pasing to Haidhausen.",
         ref="Switch to Haidhausen"),
    dict(id="N_29", date="2026-05-08",
         q="Does living in Haidhausen change which school Lia would go to?",
         a="Yes: the catchment rules [N_16] mean the address decides the Grundschule, so a Haidhausen address gives you a Haidhausen school.",
         act="follow_up", ents=["E_12"], cites=["N_16"], hier=[["N_28", "subcase"]], prag=[["N_16", "references"]],
         creates=[], updates=[], relates=[],
         summary="The Haidhausen address determines Lia's Grundschule.",
         ref="Address decides school"),
    # ---- R ----
    dict(id="N_30", date="2026-05-12",
         q="Landlords in Haidhausen want the deposit in a rent-deposit account, a Mietkautionskonto.",
         a="That's standard: the deposit, up to three months' cold rent, is held in a special blocked account.",
         act="information", ents=["E_12"], cites=[], hier=[["N_12", "subcase"]], prag=[["N_28", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Landlords require a rent-deposit account.",
         ref="Deposit account needed"),
    dict(id="N_31", date="2026-05-12",
         q="Can my N26 account do that?",
         a="Let's check: not every bank offers deposit accounts.",
         act="factual_question", ents=["E_10"], cites=[], hier=[["N_30", "subcase"]], prag=[["N_13", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks whether N26 can hold the deposit.",
         ref="N26 deposit?"),
    dict(id="N_32", date="2026-05-12",
         q="And?",
         a="No: N26 doesn't offer rent-deposit accounts, and many landlords won't accept its alternatives. Open a Sparkasse account after the Anmeldung for the deposit and rent, and keep N26 only for everyday spending.",
         act="decision", ents=["E_10", "E_11"], cites=[], hier=[["N_31", "subcase"]], prag=[["N_13", "contradicts"], ["N_31", "resolves"]],
         creates=["SN_9"], updates=[["SN_8", "reverted"]], relates=[],
         summary="N26 can't hold deposits; a Sparkasse account after the Anmeldung becomes the main account.",
         ref="Sparkasse after Anmeldung"),
    dict(id="N_33", date="2026-05-12",
         q="So what order do things have to happen in?",
         a="A strict chain: sign a lease, get the landlord's Wohnungsgeberbestätigung, do the Anmeldung, open the Sparkasse account, then set up the deposit account. The Anmeldung certificate is also what the school will ask for.",
         act="information", ents=["E_17", "E_8", "E_11"], cites=[], hier=[["N_12", "supercase"]], prag=[["N_14", "depends_on"], ["N_30", "depends_on"]],
         creates=[], updates=[], relates=[["SN_9", "supports"]],
         summary="Chain: lease, landlord form, Anmeldung, Sparkasse, deposit account (and school).",
         ref="The dependency chain"),
    # ---- S ----
    dict(id="N_34", date="2026-05-18",
         q="Back to school: for the Haidhausen addresses we're looking at, the catchment school is the Grundschule an der Kirchenstraße.",
         a="That's a well-regarded school, and a short walk from most of Haidhausen.",
         act="information", ents=["E_14", "E_12"], cites=[], hier=[["N_15", "subcase"]], prag=[["N_28", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="The Haidhausen catchment school is Kirchenstraße.",
         ref="Kirchenstraße school"),
    dict(id="N_35", date="2026-05-18",
         q="Sofia still prefers the international school, so Lia doesn't have to struggle with German. I worry about the €18,000 a year.",
         a="Both worries are fair. The fees [N_17] add up over years, while a Grundschule gives Lia German and local friends, which matters if you stay long-term.",
         act="disagreement", ents=["E_2", "E_15"], cites=["N_17"], hier=[["N_34", "same_level"]], prag=[["N_17", "references"]],
         creates=[], updates=[], relates=[],
         summary="Sofia prefers BIS; Daniel worries about the fees.",
         ref="BIS vs Grundschule debate"),
    dict(id="N_36", date="2026-05-20",
         q="We've decided: Kirchenstraße, plus a weekly German tutor so Lia catches up faster.",
         a="A good compromise: free, local, and the tutor addresses Sofia's concern.",
         act="decision", ents=["E_14", "E_3"], cites=[], hier=[["N_35", "subcase"]], prag=[["N_15", "resolves"]],
         creates=["SN_11"], updates=[["SN_10", "resolved"]], relates=[["SN_10", "resolves"]],
         summary="Lia will attend Kirchenstraße with a weekly German tutor.",
         ref="Kirchenstraße + tutor"),
    dict(id="N_37", date="2026-05-20",
         q="How do we register her at the school?",
         a="In person at the school, with Lia's documents and proof of address.",
         act="factual_question", ents=["E_14"], cites=[], hier=[["N_36", "subcase"]], prag=[["N_36", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks how to register Lia at the school.",
         ref="School registration?"),
    dict(id="N_38", date="2026-05-20",
         q="What counts as proof of address?",
         a="The Anmeldung certificate, so school registration sits at the end of the same chain [N_33]: lease, landlord form, Anmeldung, then the school.",
         act="information", ents=["E_8"], cites=["N_33"], hier=[["N_37", "subcase"]], prag=[["N_37", "resolves"], ["N_33", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="The school needs the Anmeldung certificate as proof of address.",
         ref="School needs Anmeldung"),
    # ---- I ----
    dict(id="N_39", date="2026-05-25",
         q="Insurance again: Sofia has an interview with a Munich design studio next week. She's starting to think a local job would be better than working remotely for Lisbon.",
         a="That would change a few things, insurance included.",
         act="information", ents=["E_2"], cites=[], hier=[["N_19", "subcase"]], prag=[],
         creates=[], updates=[], relates=[["SN_16", "contradicts"]],
         summary="Sofia is interviewing for a Munich job instead of working remotely.",
         ref="Sofia's Munich interview"),
    dict(id="N_40", date="2026-05-25",
         q="Would she still be co-insured on my TK policy if she works in Munich?",
         a="Let's check the co-insurance rules for employed spouses.",
         act="factual_question", ents=["E_16"], cites=[], hier=[["N_39", "subcase"]], prag=[["N_20", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks whether Sofia stays co-insured if employed.",
         ref="Co-insured if employed?"),
    dict(id="N_41", date="2026-05-25",
         q="What are the rules?",
         a="Co-insurance only covers family members without a significant income. If Sofia takes a salaried job in Munich, she'll be insured through her own employer. Lia stays co-insured on your policy.",
         act="decision", ents=["E_16", "E_2", "E_3"], cites=[], hier=[["N_40", "subcase"]], prag=[["N_40", "resolves"], ["N_20", "revises"]],
         creates=[], updates=[["SN_12", "revised"]], relates=[],
         summary="If employed, Sofia is insured through her own employer; Lia stays co-insured.",
         ref="Sofia insured separately"),
    # ---- M ----
    dict(id="N_42", date="2026-06-01",
         q="Moving logistics: should we bring our car or sell it?",
         a="Importing a car means German registration and possibly an inspection. Let's get a moving quote first.",
         act="factual_question", ents=[], cites=[], hier=[["N_1", "subcase"]], prag=[],
         creates=["SN_15"], updates=[], relates=[],
         summary="Opens the question of shipping or selling the car.",
         ref="Car: ship or sell?"),
    dict(id="N_43", date="2026-06-01",
         q="For the household goods, Transeuropa Movers can do a full 20 ft container. Let's book that.",
         a="A full container fits the furniture and, in principle, the car. Booked with Transeuropa.",
         act="decision", ents=["E_18"], cites=[], hier=[["N_42", "same_level"]], prag=[],
         creates=["SN_14"], updates=[], relates=[],
         summary="Books a full 20 ft container with Transeuropa.",
         ref="20 ft container"),
    # ---- V ----
    dict(id="N_44", date="2026-06-03",
         q="The Blue Card pre-approval arrived. The KVR appointment is still 8 July, though.",
         a="Good; with the pre-approval your entry visa is straightforward. The 8 July appointment stays.",
         act="information", ents=["E_7", "E_9"], cites=[], hier=[["N_21", "subcase"]], prag=[["N_21", "depends_on"]],
         creates=[], updates=[], relates=[["SN_3", "supports"]],
         summary="Blue Card pre-approval arrived; KVR stays on 8 July.",
         ref="Pre-approval arrived"),
    dict(id="N_45", date="2026-06-03",
         q="To be safe, Brennwerk agreed to move my start date to 15 July, after the appointment.",
         a="That removes any doubt about working before the card is issued. Your start date is now 15 July.",
         act="decision", ents=["E_4", "E_21"], cites=[], hier=[["N_44", "subcase"]], prag=[["N_2", "revises"]],
         creates=[], updates=[["SN_2", "revised"]], relates=[],
         summary="Start date moved to 15 July.",
         ref="Start 15 July"),
    dict(id="N_46", date="2026-06-03",
         q="Does the later start mess up the temporary flat?",
         a="Not really: it still runs until 31 July [N_25], so you'd just use it from mid-July.",
         act="follow_up", ents=[], cites=["N_25"], hier=[["N_45", "subcase"]], prag=[["N_25", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="The temporary flat still works with a mid-July arrival.",
         ref="Temp flat still OK"),
    # ---- H ----
    dict(id="N_47", date="2026-06-10",
         q="I flew over for a weekend and viewed three Haidhausen flats.",
         a="Good; viewings in person make a huge difference with Munich landlords.",
         act="information", ents=["E_12"], cites=[], hier=[["N_28", "subcase"]], prag=[["N_28", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Daniel viewed three flats in Haidhausen.",
         ref="Three viewings"),
    dict(id="N_48", date="2026-06-15",
         q="We got one! Lease signed: €2,480 warm, starting 1 August.",
         a="Congratulations. €2,480 is within your €2,600 cap, and a 1 August start means you no longer depend on the temporary flat after July.",
         act="information", ents=["E_12", "E_20"], cites=[], hier=[["N_47", "subcase"]], prag=[["N_27", "depends_on"]],
         creates=[], updates=[["SN_13", "lifted"]], relates=[["SN_5", "supports"], ["SN_7", "supports"]],
         summary="Lease signed in Haidhausen: €2,480 warm from 1 August.",
         ref="Lease signed €2,480"),
    dict(id="N_49", date="2026-06-15",
         q="So the temporary flat is only needed from 15 to 31 July now?",
         a="Right: with the later start [N_45], you'll use it for just over two weeks.",
         act="follow_up", ents=[], cites=["N_45"], hier=[["N_48", "subcase"]], prag=[["N_45", "depends_on"], ["N_25", "references"]],
         creates=[], updates=[], relates=[],
         summary="The temporary flat is needed only from 15 to 31 July.",
         ref="Temp flat 15-31 July"),
    # ---- R ----
    dict(id="N_50", date="2026-07-16",
         q="We've arrived in Munich! The new landlord already gave us the Wohnungsgeberbestätigung for the Haidhausen flat.",
         a="Perfect: with that form you can do the Anmeldung for the new address right away, even before moving in on 1 August.",
         act="information", ents=["E_17", "E_5"], cites=[], hier=[["N_33", "subcase"]], prag=[["N_48", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Arrived; landlord form for Haidhausen received.",
         ref="Landlord form received"),
    dict(id="N_51", date="2026-07-17",
         q="Anmeldung done at the Bürgerbüro this morning!",
         a="That unlocks the rest of the chain: bank account, deposit, school registration.",
         act="information", ents=["E_8"], cites=[], hier=[["N_33", "subcase"]], prag=[["N_50", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Anmeldung completed.",
         ref="Anmeldung done"),
    dict(id="N_52", date="2026-07-20",
         q="The Sparkasse account is open.",
         a="Good; that's your main account for rent and the deposit.",
         act="information", ents=["E_11"], cites=[], hier=[["N_33", "subcase"]], prag=[["N_51", "depends_on"]],
         creates=[], updates=[], relates=[["SN_9", "supports"]],
         summary="Sparkasse account opened.",
         ref="Sparkasse opened"),
    dict(id="N_53", date="2026-07-22",
         q="And the deposit is in the Mietkautionskonto. The landlord confirmed.",
         a="Then the whole registration and banking chain is complete.",
         act="information", ents=["E_11"], cites=[], hier=[["N_33", "subcase"]], prag=[["N_52", "depends_on"], ["N_30", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Deposit account set up; the chain is complete.",
         ref="Deposit set up"),
    # ---- S ----
    dict(id="N_54", date="2026-07-24",
         q="We registered Lia at Kirchenstraße with the Anmeldung certificate.",
         a="Great, the last link in the chain.",
         act="information", ents=["E_14", "E_3", "E_8"], cites=[], hier=[["N_36", "subcase"]], prag=[["N_38", "depends_on"]],
         creates=[], updates=[], relates=[["SN_11", "supports"]],
         summary="Lia is registered at Kirchenstraße.",
         ref="Lia registered"),
    dict(id="N_55", date="2026-07-24",
         q="The school tested Lia's German. As expected, she's a beginner.",
         a="Normal for a new arrival. Schools then decide how to place her.",
         act="information", ents=["E_3"], cites=[], hier=[["N_54", "subcase"]], prag=[["N_54", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Lia's German is assessed as beginner level.",
         ref="German test"),
    dict(id="N_56", date="2026-07-27",
         q="The school wants Lia to start in the Übergangsklasse, a transition class for new arrivals, for about six months, before joining a regular third-grade class. We'll keep the tutor too.",
         a="That's a strong model: intensive German with other newcomers, then a regular class. So the plan is Kirchenstraße, starting in the Übergangsklasse, plus the weekly tutor.",
         act="decision", ents=["E_3", "E_14"], cites=[], hier=[["N_55", "subcase"]], prag=[["N_36", "revises"]],
         creates=[], updates=[["SN_11", "revised"]], relates=[],
         summary="Lia starts with six months in the transition class, then a regular class.",
         ref="Übergangsklasse first"),
    dict(id="N_57", date="2026-07-27",
         q="Sofia worries it will set Lia back a year.",
         a="Usually the opposite: children who get a solid German base first tend to catch up faster in regular classes than those thrown straight in.",
         act="follow_up", ents=["E_2", "E_3"], cites=[], hier=[["N_56", "subcase"]], prag=[["N_56", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Transition classes usually help children catch up faster.",
         ref="Won't set her back"),
    # ---- I ----
    dict(id="N_58", date="2026-07-28",
         q="Sofia got the job at the Munich design studio!",
         a="Congratulations to her! That settles the question of working remotely.",
         act="information", ents=["E_2", "E_5"], cites=[], hier=[["N_39", "subcase"]], prag=[["N_39", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Sofia got a job at a Munich design studio.",
         ref="Sofia hired in Munich"),
    dict(id="N_59", date="2026-07-28",
         q="She's resigning from the Lisbon agency. No more remote work for them.",
         a="Then the plan to keep her Lisbon job is off. She'll be a regular employee in Munich from September.",
         act="decision", ents=["E_2", "E_6"], cites=[], hier=[["N_58", "subcase"]], prag=[["N_58", "depends_on"], ["N_6", "references"]],
         creates=[], updates=[["SN_16", "abandoned"]], relates=[],
         summary="Sofia resigns from her Lisbon job; the remote-work plan is abandoned.",
         ref="Remote plan abandoned"),
    dict(id="N_60", date="2026-07-28",
         q="What happens with insurance now?",
         a="As we worked out [N_41]: from her start date Sofia is insured through her new employer, and Lia stays co-insured on your TK policy.",
         act="information", ents=["E_16", "E_2", "E_3"], cites=["N_41"], hier=[["N_58", "subcase"]], prag=[["N_41", "depends_on"]],
         creates=[], updates=[], relates=[["SN_12", "supports"]],
         summary="Sofia's insurance moves to her employer; Lia stays co-insured.",
         ref="Insurance updated"),
    # ---- M ----
    dict(id="N_61", date="2026-07-29",
         q="Transeuropa's final quote for the full 20 ft container, car included, is €7,800. That's way over what we planned.",
         a="The car is the expensive part: it takes most of the container space and needs German registration afterwards.",
         act="information", ents=["E_18"], cites=[], hier=[["N_43", "subcase"]], prag=[["N_43", "depends_on"]],
         creates=[], updates=[], relates=[["SN_14", "contradicts"]],
         summary="The full container with the car costs €7,800.",
         ref="€7,800 quote"),
    dict(id="N_62", date="2026-07-29",
         q="Haidhausen has great transport and we'd hardly use a car. Let's sell it and ship the rest in a shared container.",
         a="Agreed: sell the car in Lisbon and switch to a shared container for the household goods. Much cheaper, and it arrives in a similar time.",
         act="decision", ents=["E_18", "E_12"], cites=[], hier=[["N_61", "subcase"]], prag=[["N_42", "resolves"], ["N_43", "revises"]],
         creates=[], updates=[["SN_15", "resolved"], ["SN_14", "revised"]], relates=[["SN_15", "resolves"]],
         summary="Sell the car; ship household goods in a shared container.",
         ref="Sell car, shared container"),
    # ---- V ----
    dict(id="N_63", date="2026-08-01",
         q="The KVR issued my Blue Card, and Sofia's residence permit came with it.",
         a="Congratulations, that's the legal side done for both of you.",
         act="information", ents=["E_7", "E_9", "E_2"], cites=[], hier=[["N_21", "subcase"]], prag=[["N_44", "depends_on"]],
         creates=[], updates=[], relates=[["SN_3", "supports"]],
         summary="Blue Card and Sofia's residence permit issued.",
         ref="Blue Card issued"),
    # ---- H ----
    dict(id="N_64", date="2026-08-02",
         q="We moved into the Haidhausen flat yesterday.",
         a="Welcome home! Mostly empty for now, I assume, until the container arrives.",
         act="information", ents=["E_12"], cites=[], hier=[["N_47", "subcase"]], prag=[["N_48", "depends_on"]],
         creates=[], updates=[], relates=[["SN_7", "supports"]],
         summary="The family moved into the Haidhausen flat.",
         ref="Moved in"),
    dict(id="N_65", date="2026-08-02",
         q="Yes, when does our stuff arrive?",
         a="Shared containers usually take a little longer to fill; Transeuropa's estimate is the first week of August.",
         act="follow_up", ents=["E_18"], cites=[], hier=[["N_64", "subcase"]], prag=[["N_62", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Shipment expected in the first week of August.",
         ref="Arrival estimate"),
    # ---- M ----
    dict(id="N_66", date="2026-08-05",
         q="The container arrived today and everything was unloaded.",
         a="Great timing, well before school starts.",
         act="information", ents=["E_18"], cites=[], hier=[["N_62", "subcase"]], prag=[["N_62", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="The shipment arrived.",
         ref="Container arrived"),
    dict(id="N_67", date="2026-08-06",
         q="One box is missing: the one with Lia's books.",
         a="Check the inventory list the movers made at packing; each box should be numbered.",
         act="information", ents=["E_3"], cites=[], hier=[["N_66", "subcase"]], prag=[["N_66", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="A box with Lia's books is missing.",
         ref="Missing box"),
    dict(id="N_68", date="2026-08-08",
         q="Should we file an insurance claim?",
         a="Report it to Transeuropa in writing first; the transit insurance usually requires notice within a few days of delivery.",
         act="factual_question", ents=["E_18"], cites=[], hier=[["N_67", "subcase"]], prag=[["N_67", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks about an insurance claim for the missing box.",
         ref="Claim?"),
    dict(id="N_69", date="2026-08-12",
         q="Transeuropa found the box: it had been loaded onto another family's shipment. It's being delivered next week.",
         a="Good outcome. Keep the written report until it arrives.",
         act="information", ents=["E_18"], cites=[], hier=[["N_68", "subcase"]], prag=[["N_68", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="The missing box was found and will be delivered.",
         ref="Box found"),
    # ---- overview ----
    dict(id="N_70", date="2026-08-14",
         q="Can you give me the status of everything?",
         a="Visa: Blue Card issued. Housing: in Haidhausen at €2,480. Registration and bank: Anmeldung, Sparkasse and deposit done. School: Lia starts at Kirchenstraße in the transition class. Insurance: TK for you and Lia, Sofia through her employer. Moving: goods arrived, car sold.",
         act="request", ents=["E_7", "E_12", "E_8", "E_11", "E_14", "E_16"], cites=[], hier=[["N_3", "supercase"], ["N_7", "supercase"], ["N_12", "supercase"], ["N_15", "supercase"], ["N_19", "supercase"], ["N_42", "supercase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Status across all six threads.",
         ref="Status of everything"),
    dict(id="N_71", date="2026-08-14",
         q="What's still open?",
         a="Three admin items: waiting for your tax ID, the broadcasting fee registration, and sorting out transport now that you have no car.",
         act="follow_up", ents=[], cites=[], hier=[["N_70", "subcase"]], prag=[["N_70", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Open items: tax ID, broadcasting fee, transport.",
         ref="Open items"),
    dict(id="N_72", date="2026-08-20",
         q="Lia's school confirmed her first day: 14 September.",
         a="Perfect, with a few weeks to settle in first.",
         act="information", ents=["E_3", "E_14"], cites=[], hier=[["N_56", "subcase"]], prag=[["N_56", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Lia's first school day is 14 September.",
         ref="First day 14 Sept"),
    dict(id="N_73", date="2026-08-20",
         q="Has the tax ID shown up? Brennwerk payroll keeps asking.",
         a="It's sent automatically by post a few weeks after the Anmeldung, so it should arrive soon.",
         act="factual_question", ents=["E_4", "E_8"], cites=[], hier=[["N_71", "subcase"]], prag=[["N_33", "references"]],
         creates=[], updates=[], relates=[],
         summary="Waiting for the tax ID, which follows the Anmeldung.",
         ref="Tax ID?"),
    dict(id="N_74", date="2026-08-21",
         q="It arrived today!",
         a="Send it to Brennwerk's payroll so your salary is taxed correctly from the start.",
         act="information", ents=["E_4"], cites=[], hier=[["N_73", "subcase"]], prag=[["N_73", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Tax ID arrived; forward to payroll.",
         ref="Tax ID arrived"),
    dict(id="N_75", date="2026-08-24",
         q="We got a letter about the Rundfunkbeitrag. What is it?",
         a="The public broadcasting fee: every household pays it, whether or not you own a TV.",
         act="factual_question", ents=[], cites=[], hier=[["N_71", "subcase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Asks about the Rundfunkbeitrag letter.",
         ref="Broadcasting fee?"),
    dict(id="N_76", date="2026-08-24",
         q="How much, and do we both pay?",
         a="Once per household, not per person: roughly €18 a month. Register the household once, in one name.",
         act="information", ents=[], cites=[], hier=[["N_75", "subcase"]], prag=[["N_75", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="One broadcasting fee per household, about €18 a month.",
         ref="Fee per household"),
    dict(id="N_77", date="2026-08-27",
         q="Without a car, what's the best way to get around?",
         a="Munich's public transport covers everything you need from Haidhausen. Now that the car is sold [N_62], a monthly Deutschlandticket is the obvious choice.",
         act="factual_question", ents=["E_12"], cites=["N_62"], hier=[["N_71", "subcase"]], prag=[["N_62", "references"]],
         creates=[], updates=[], relates=[],
         summary="Asks about transport without a car; the Deutschlandticket is suggested.",
         ref="Transport without car"),
    dict(id="N_78", date="2026-08-28",
         q="Brennwerk subsidises the Deutschlandticket as a job ticket, so I've ordered it through them.",
         a="Even better. That closes the last open item.",
         act="information", ents=["E_4"], cites=[], hier=[["N_77", "subcase"]], prag=[["N_77", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Deutschlandticket ordered as a subsidised job ticket.",
         ref="Job ticket ordered"),
    dict(id="N_79", date="2026-08-30",
         q="Looking back, what changed from our April plan?",
         a="Five things: Haidhausen instead of Pasing [N_28]; Sparkasse instead of N26 as the main bank [N_32]; a 15 July start instead of 1 July [N_45]; Sofia working in Munich instead of remotely for Lisbon [N_59]; and selling the car with a shared container instead of shipping everything [N_62].",
         act="follow_up", ents=["E_12", "E_13", "E_11", "E_10", "E_2"], cites=["N_28", "N_32", "N_45", "N_59", "N_62"], hier=[["N_28", "supercase"], ["N_32", "supercase"], ["N_45", "supercase"], ["N_59", "supercase"], ["N_62", "supercase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Retrospective of the five changes from the April plan.",
         ref="What changed"),
    dict(id="N_80", date="2026-08-31",
         q="Tomorrow Sofia starts her new job, and in two weeks Lia starts school. I think we're actually settled.",
         a="You are: permits, home, bank, insurance, school and work all in place before the school year. Congratulations to all three of you.",
         act="information", ents=["E_2", "E_3"], cites=[], hier=[], prag=[["N_1", "resolves"]],
         creates=[], updates=[["SN_1", "achieved"]], relates=[],
         summary="The family is settled before the school year.",
         ref="Settled"),
]

node_index = {n["id"]: i for i, n in enumerate(NODES)}

# --- Validate backward-in-time edges and date order ---
for n in NODES:
    for tgt, _ in n["hier"] + n["prag"]:
        assert node_index[tgt] < node_index[n["id"]], f"{n['id']} -> {tgt} not backward"
for a, b in zip(NODES, NODES[1:]):
    assert a["date"] <= b["date"], f"dates out of order: {a['id']} {a['date']} > {b['id']} {b['date']}"
assert set(THREADS) == {n["id"] for n in NODES}, "THREADS must cover every turn"

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
        "thread": THREADS[n["id"]],
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
    "conversation_id": "relocation",
    "domain": "Family relocation from Lisbon to Munich (six interleaved threads)",
    "schema_note": (
        "Mirrors INESCTEC_RESEARCH.md section 3/4 output schema, same convention as "
        "conversations/marathon_trip. Domain entity type (domain_config.json): permit. Adds one field not in "
        "the base schema: thread (V visa, H housing, R registration/bank, S school, I insurance, M moving, "
        "- overview), for analysing retrieval across interleaved threads. Built to exercise same_level between "
        "parallel threads, cross-thread depends_on (lease -> Anmeldung -> Sparkasse -> deposit -> school), "
        "threads resumed 10-30 turns later, two decisions reverted (SN_6, SN_8), and a second goal: abandoned "
        "(SN_16, Sofia's remote-work plan)."
    ),
    "schema_findings": [
        {
            "raised_at_node": "N_7",
            "issue": "Opening a new thread gets two hierarchical edges: subcase of the overall goal turn (N_1) "
                     "and same_level with the previous thread's opener (N_3). The outline's convention, applied "
                     "to every thread opener.",
            "proposed_direction": "Keep both: subcase encodes the topic tree, same_level encodes that the threads "
                                   "are parallel. Metrics that allow one hierarchical label per pair will count "
                                   "only one of them (see the per-pair scoring issue noted for hpc_support).",
        },
        {
            "raised_at_node": "N_39",
            "issue": "SN_16 (Sofia keeps her Lisbon job remotely) is contradicted at N_39 by a hint (an interview), "
                     "but only abandoned at N_59 when she resigns, 20 turns later in the same thread.",
            "proposed_direction": "A contradicts relation on a goal does not change its status; only the explicit "
                                   "decision does. The gap between the two is what tests whether the extractor "
                                   "tracks status over time instead of reacting to the first sign.",
        },
        {
            "raised_at_node": "N_4",
            "issue": "The outline quoted a €58,400 Blue Card threshold, which is not a real figure. The corpus says "
                     "'around €48,000 in 2025, adjusted every year' and keeps the €72,000 offer.",
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

# Thread-return gaps: turns between consecutive visits to the same thread.
gaps = {}
last_seen = {}
for n in NODES:
    t = THREADS[n["id"]]
    i = node_index[n["id"]]
    if t != "-" and t in last_seen and i - last_seen[t] > 1:
        gaps.setdefault(t, []).append(i - last_seen[t])
    last_seen[t] = i

print(f"Wrote {len(NODES)} interaction nodes, {len(ENTITIES)} entities, {len(STATE_NODE_DEFS)} state nodes.")
print("Epistemic status:", dict(Counter(status.values())))
print("Speech acts:", dict(Counter(n["act"] for n in NODES)))
print("Hierarchical:", dict(Counter(l for n in NODES for _, l in n["hier"])))
print("Pragmatic:", dict(Counter(l for n in NODES for _, l in n["prag"])))
print("State nodes:", dict(Counter((d["type"], sn_status[sid]) for sid, d in STATE_NODE_DEFS.items())))
print("Entity types:", dict(Counter(d["type"] for d in ENTITIES.values())))
print("Thread-return gaps (turns):", gaps)
