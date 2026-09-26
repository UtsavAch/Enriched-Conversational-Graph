"""Construct conversations/product_rename/{corpus.json, ground_truth.json}.

Same method as conversations/marathon_trip/build.py: raw per-node fields are
authored below; recurrence_count, retrieval_count, epistemic_status/history,
entities.mentioned_in, and state_nodes status/last_updated_turn are derived
programmatically.

Built to break semantic retrieval: decisions are made under the old names
(Falcon, Tailwind, Falcon Lite/Pro); from N_21 on the text uses only the new
names (Nimbus, Work Offline, Nimbus Free/Team), except the explicit link turns
N_21, N_28, N_36-N_38 and the retrospective N_49. Entities follow the schema's
own convention (core/schema/entity.py): ``name`` is the surface form as first
mentioned, later surface forms go in ``aliases``. Outline: outline.md.
"""
import json
from collections import Counter
from pathlib import Path

INITIAL_STATUS = {"goal": "active", "decision": "active", "constraint": "active", "open_question": "open"}
OPEN_DEFAULT_ACTS = {"factual_question", "clarification_request"}

ENTITIES = {
    "E_1": {"type": "person", "name": "Priya", "aliases": []},
    "E_2": {"type": "organization", "name": "Tessellate", "aliases": []},
    "E_3": {"type": "product", "name": "Falcon", "aliases": ["Project Falcon", "Nimbus"]},
    "E_4": {"type": "feature", "name": "Tailwind", "aliases": ["offline sync", "Work Offline"]},
    "E_5": {"type": "feature", "name": "Smart Rota", "aliases": ["auto-scheduler"]},
    "E_6": {"type": "feature", "name": "Slack integration", "aliases": []},
    "E_7": {"type": "product", "name": "Falcon Pro", "aliases": ["Nimbus Team"]},
    "E_8": {"type": "product", "name": "Falcon Lite", "aliases": ["Nimbus Free"]},
    "E_9": {"type": "organization", "name": "Falcon Systems Ltd", "aliases": []},
    "E_10": {"type": "person", "name": "Marcus", "aliases": []},
    "E_11": {"type": "person", "name": "Elena", "aliases": []},
    "E_12": {"type": "event", "name": "public launch", "aliases": []},
    "E_13": {"type": "event", "name": "Café Aurora beta", "aliases": []},
    "E_14": {"type": "organization", "name": "Café Aurora", "aliases": []},
    "E_15": {"type": "metric", "name": "activation rate", "aliases": []},
    "E_16": {"type": "measurement", "name": "per-seat monthly price", "aliases": []},
}

STATE_NODE_DEFS = {
    "SN_1": {"type": "goal", "label": "Launch Falcon publicly with a paying beta customer"},
    "SN_2": {"type": "decision", "label": "Public launch on 2 June"},
    "SN_3": {"type": "decision", "label": "Tailwind (offline sync) is in the launch scope"},
    "SN_4": {"type": "decision", "label": "Two tiers: Falcon Lite (free, up to 5 seats) and Falcon Pro (€5 per seat per month)"},
    "SN_5": {"type": "constraint", "label": "Engineering capacity until launch: 2 backend engineers and 1 mobile engineer"},
    "SN_6": {"type": "open_question", "label": "Can we keep the name Falcon?"},
    "SN_7": {"type": "decision", "label": "The product is named Nimbus"},
    "SN_8": {"type": "decision", "label": "Smart Rota ships labelled as beta"},
    "SN_9": {"type": "decision", "label": "Café Aurora is the beta customer"},
    "SN_10": {"type": "decision", "label": "Work Offline (offline access) is in the launch scope, Team tier only"},
    "SN_11": {"type": "constraint", "label": "No Slack integration until after launch"},
    "SN_12": {"type": "open_question", "label": "Why is Café Aurora threatening to drop the beta?"},
}

LABEL_OVERRIDES = {
    ("SN_1", "N_48"): "Launch Nimbus (originally codenamed Falcon) publicly with a paying beta customer",
    ("SN_2", "N_24"): "Public launch on 16 June (originally: 2 June)",
    ("SN_2", "N_40"): "Public launch on 23 June (originally: 2 June, then 16 June)",
    ("SN_4", "N_28"): "Two tiers: Nimbus Free (up to 3 seats) and Nimbus Team (€6 per seat per month); originally Falcon Lite (5 seats) and Falcon Pro (€5)",
    ("SN_5", "N_35"): "Engineering capacity until launch: 2 backend engineers and 2 mobile engineers (a 4-week mobile contractor added)",
}

NODES = [
    # ---- Planning as "Falcon" -------------------------------------------------------
    dict(id="N_1", date="2026-05-04",
         q="I'm Priya, PM at Tessellate. We're launching Falcon, our team-scheduling product for shift-based businesses, and I want a paying beta customer on board before the public launch. Can you help me plan it?",
         a="Happy to. Let's build a launch checklist: date, scope, pricing, beta customer, and team capacity. Those five decisions drive everything else.",
         act="request", ents=["E_1", "E_2", "E_3"], cites=[], hier=[], prag=[],
         creates=["SN_1"], updates=[], relates=[],
         summary="Priya sets the goal of launching Falcon publicly with a paying beta customer.",
         ref="Falcon launch goal"),
    dict(id="N_2", date="2026-05-04",
         q="What goes on the checklist first?",
         a="The date, because scope and staffing both work backwards from it. Then scope, then pricing, then the beta customer, who should be secured early so their feedback can still change things.",
         act="factual_question", ents=[], cites=[], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Checklist order: date, scope, pricing, beta customer.",
         ref="Checklist order"),
    dict(id="N_3", date="2026-05-04",
         q="Let's say the public launch is 2 June.",
         a="2 June gives four weeks, which is tight but workable if scope stays small. I'll plan everything back from that date.",
         act="decision", ents=["E_12"], cites=[], hier=[["N_2", "subcase"]], prag=[["N_2", "depends_on"]],
         creates=["SN_2"], updates=[], relates=[],
         summary="Public launch set for 2 June.",
         ref="Launch 2 June"),
    dict(id="N_4", date="2026-05-05",
         q="For scope, what should Falcon ship with?",
         a="What are the core features on your roadmap? Let's rank them by what a beta customer can't live without.",
         act="factual_question", ents=["E_3"], cites=[], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks what Falcon should ship with at launch.",
         ref="Scope question"),
    dict(id="N_5", date="2026-05-05",
         q="Three big ones: Smart Rota, the auto-scheduler; shift swaps between staff; and Tailwind, our codename for offline sync in the mobile app.",
         a="Smart Rota and shift swaps are the core of a scheduling product. Tailwind is the riskiest of the three to build, since offline sync is hard, but valuable for staff without reliable signal.",
         act="information", ents=["E_5", "E_4"], cites=[], hier=[["N_4", "subcase"]], prag=[["N_4", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Core features listed: Smart Rota, shift swaps, and Tailwind (offline sync).",
         ref="Core features listed"),
    dict(id="N_6", date="2026-05-05",
         q="I want all three in the launch, including Tailwind.",
         a="OK, Tailwind is in scope. Let's confirm with engineering that it fits in four weeks alongside everything else.",
         act="decision", ents=["E_4"], cites=[], hier=[["N_5", "subcase"]], prag=[["N_5", "depends_on"]],
         creates=["SN_3"], updates=[], relates=[],
         summary="Tailwind (offline sync) put into the launch scope.",
         ref="Tailwind in scope"),
    dict(id="N_7", date="2026-05-06",
         q="Next is pricing. What do competitors charge for team scheduling?",
         a="Most charge per seat per month, typically €4–€8, with a free tier for very small teams to drive sign-ups.",
         act="factual_question", ents=["E_16"], cites=[], hier=[["N_1", "subcase"], ["N_4", "same_level"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Asks about competitor pricing; per-seat €4-€8 with a free tier is typical.",
         ref="Competitor pricing"),
    dict(id="N_8", date="2026-05-06",
         q="Would a free tier cannibalise the paid one?",
         a="Not if it's capped by seats. A cap of a handful of seats keeps it useful for a single small shop but pushes any real team onto the paid plan.",
         act="clarification_request", ents=[], cites=[], hier=[["N_7", "subcase"]], prag=[["N_7", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="A seat-capped free tier is suggested to avoid cannibalisation.",
         ref="Seat-capped free tier"),
    dict(id="N_9", date="2026-05-06",
         q="Then two tiers: Falcon Lite, free for up to 5 seats, and Falcon Pro at €5 per seat per month.",
         a="That's a clean structure and within the market range. Falcon Lite (5 seats, free) and Falcon Pro (€5/seat/month) it is.",
         act="decision", ents=["E_8", "E_7", "E_16"], cites=[], hier=[["N_8", "subcase"]], prag=[["N_8", "depends_on"]],
         creates=["SN_4"], updates=[], relates=[],
         summary="Tiers set: Falcon Lite free up to 5 seats, Falcon Pro €5 per seat.",
         ref="Falcon Lite / Pro pricing"),
    dict(id="N_10", date="2026-05-07",
         q="For the beta, Café Aurora (a chain of 12 cafés) is keen. Should we go with them?",
         a="Yes. Twelve sites with rotating shift staff is exactly the target customer, and a chain gives you multi-site feedback. Café Aurora as the beta customer is a good choice.",
         act="decision", ents=["E_14", "E_13"], cites=[], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=["SN_9"], updates=[], relates=[],
         summary="Café Aurora (12 cafés) chosen as the beta customer.",
         ref="Café Aurora beta"),
    dict(id="N_11", date="2026-05-07",
         q="Their ops manager says what matters most is seeing rotas per site on staff phones.",
         a="So mobile-first, per-site rotas. That fits Smart Rota; keep their needs in mind as we lock scope.",
         act="information", ents=["E_14", "E_5"], cites=[], hier=[["N_10", "subcase"]], prag=[["N_10", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Café Aurora needs per-site rotas visible on staff phones.",
         ref="Café Aurora needs"),
    dict(id="N_12", date="2026-05-08",
         q="Marcus, our CTO, says until launch we only have 2 backend engineers and 1 mobile engineer.",
         a="That's a hard constraint on scope; everything has to fit into three people's time over four weeks.",
         act="information", ents=["E_10"], cites=[], hier=[["N_1", "subcase"]], prag=[],
         creates=["SN_5"], updates=[], relates=[],
         summary="Capacity constraint: 2 backend engineers and 1 mobile engineer until launch.",
         ref="Engineering capacity"),
    dict(id="N_13", date="2026-05-08",
         q="Marcus also estimates Tailwind alone is about three weeks of the mobile engineer's time.",
         a="Then Tailwind would consume nearly all of your only mobile engineer's time before launch, leaving no room for the rest of the mobile app.",
         act="information", ents=["E_10", "E_4"], cites=[], hier=[["N_6", "subcase"]], prag=[["N_12", "depends_on"]],
         creates=[], updates=[], relates=[["SN_3", "constrained_by"]],
         summary="Tailwind needs ~3 weeks of the single mobile engineer's time.",
         ref="Tailwind cost 3 weeks"),
    dict(id="N_14", date="2026-05-08",
         q="Then we have to cut it, right?",
         a="Yes. Cut Tailwind from the launch and ship the mobile app online-only. It can come back after launch.",
         act="decision", ents=["E_4"], cites=[], hier=[["N_13", "subcase"]], prag=[["N_6", "contradicts"]],
         creates=[], updates=[["SN_3", "reverted"]], relates=[],
         summary="Tailwind cut from the launch scope.",
         ref="Tailwind cut"),
    dict(id="N_15", date="2026-05-09",
         q="What does Café Aurora lose without Tailwind?",
         a="Staff will need a connection to see their rota. Given their focus on phones [N_11], it's worth checking how many of their sites have poor signal.",
         act="follow_up", ents=["E_14", "E_4"], cites=["N_11"], hier=[["N_14", "subcase"]], prag=[["N_14", "depends_on"], ["N_11", "references"]],
         creates=[], updates=[], relates=[],
         summary="Without Tailwind, Café Aurora staff need connectivity to see rotas.",
         ref="Impact of the cut"),
    dict(id="N_16", date="2026-05-09",
         q="Along the same lines, should we also hold back the Slack integration?",
         a="Yes, no Slack integration before launch either. It's backend time we don't have.",
         act="decision", ents=["E_6"], cites=[], hier=[["N_14", "same_level"]], prag=[["N_12", "depends_on"]],
         creates=["SN_11"], updates=[], relates=[["SN_5", "constrained_by"]],
         summary="Slack integration deferred until after launch.",
         ref="No Slack before launch"),
    dict(id="N_17", date="2026-05-10",
         q="Smart Rota's suggestions are still a bit rough. Ship it anyway?",
         a="Ship it but label it beta in the UI, so customers treat the suggestions as a starting point and give feedback rather than trusting them blindly.",
         act="decision", ents=["E_5"], cites=[], hier=[["N_5", "subcase"]], prag=[["N_5", "depends_on"]],
         creates=["SN_8"], updates=[], relates=[],
         summary="Smart Rota ships labelled as beta.",
         ref="Smart Rota beta label"),
    dict(id="N_18", date="2026-05-10",
         q="Can you recap Falcon's launch plan so far?",
         a="Falcon launches 2 June with Smart Rota (labelled beta) and shift swaps, no Tailwind and no Slack. Pricing is Falcon Lite (free, 5 seats) and Falcon Pro (€5/seat). Café Aurora is the beta customer.",
         act="follow_up", ents=["E_3", "E_5", "E_8", "E_7", "E_14"], cites=[], hier=[["N_14", "supercase"], ["N_9", "supercase"], ["N_17", "supercase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Recap of Falcon's launch plan before the rename.",
         ref="Pre-rename recap"),
    # ---- The rename -----------------------------------------------------------------------
    dict(id="N_19", date="2026-05-12",
         q="Bad news from legal: a company called Falcon Systems Ltd holds the 'Falcon' trademark in our software class. Can we keep the name?",
         a="That's a serious risk. Launching under a mark someone else holds in your class invites an injunction right when you get traction.",
         act="factual_question", ents=["E_9", "E_3"], cites=[], hier=[["N_1", "subcase"]], prag=[],
         creates=["SN_6"], updates=[], relates=[],
         summary="Falcon Systems Ltd holds the Falcon trademark; opens whether the name can be kept.",
         ref="Trademark conflict"),
    dict(id="N_20", date="2026-05-12",
         q="What are our options?",
         a="Two: negotiate a coexistence agreement, which could take months with no guarantee, or rename before launch while you have almost no public footprint.",
         act="factual_question", ents=["E_9"], cites=[], hier=[["N_19", "subcase"]], prag=[["N_19", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Options: coexistence agreement (slow) or rename now.",
         ref="Rename vs coexistence"),
    dict(id="N_21", date="2026-05-13",
         q="We've decided: we're renaming Falcon to Nimbus, everywhere.",
         a="Good call; renaming now is far cheaper than after launch. The product is Nimbus from here on.",
         act="decision", ents=["E_3"], cites=[], hier=[["N_20", "subcase"]], prag=[["N_19", "resolves"], ["N_20", "depends_on"]],
         creates=["SN_7"], updates=[["SN_6", "resolved"]], relates=[["SN_6", "resolves"]],
         summary="Product renamed to Nimbus.",
         ref="Renamed to Nimbus"),
    dict(id="N_22", date="2026-05-13",
         q="What does the rename checklist look like?",
         a="Domain and email, the app-store listings, the marketing site and copy, in-app strings, legal documents, and the beta customer's onboarding materials.",
         act="request", ents=[], cites=[], hier=[["N_21", "subcase"]], prag=[["N_21", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Rename checklist: domain, app stores, site, in-app text, legal, beta materials.",
         ref="Rename checklist"),
    dict(id="N_23", date="2026-05-14",
         q="Problem: changing the app name in the app stores triggers a fresh review cycle, roughly 10 days.",
         a="That doesn't fit the current date. The store review alone eats most of the remaining time.",
         act="information", ents=[], cites=[], hier=[["N_22", "subcase"]], prag=[["N_22", "depends_on"]],
         creates=[], updates=[], relates=[["SN_2", "contradicts"]],
         summary="App-store rename requires a ~10-day review.",
         ref="Store review 10 days"),
    dict(id="N_24", date="2026-05-14",
         q="Then let's move the launch to 16 June.",
         a="16 June leaves room for the store review plus a buffer. Nimbus launches on 16 June.",
         act="decision", ents=["E_12", "E_3"], cites=[], hier=[["N_23", "subcase"]], prag=[["N_3", "revises"], ["N_23", "depends_on"]],
         creates=[], updates=[["SN_2", "revised"]], relates=[],
         summary="Launch moved to 16 June because of the rename.",
         ref="Launch 16 June"),
    dict(id="N_25", date="2026-05-15",
         q="Elena, our design lead, has a first version of the Nimbus brand: a cloud mark and a soft blue palette.",
         a="Nice, and it fits the name. Get it into the app-store assets first, since they gate the review.",
         act="information", ents=["E_11", "E_3"], cites=[], hier=[["N_22", "subcase"]], prag=[["N_22", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Elena delivers the Nimbus brand.",
         ref="Nimbus brand"),
    dict(id="N_26", date="2026-05-16",
         q="Store listings for Nimbus are submitted.",
         a="Good; the review clock starts now, so 16 June still holds.",
         act="information", ents=["E_3"], cites=[], hier=[["N_22", "subcase"]], prag=[["N_24", "depends_on"]],
         creates=[], updates=[], relates=[["SN_2", "supports"]],
         summary="Nimbus app-store listings submitted.",
         ref="Store listings submitted"),
    dict(id="N_27", date="2026-05-18",
         q="Marketing copy for the Nimbus site is done too. Should the pricing page change while we're at it?",
         a="It's a good moment. Every page is being rewritten anyway, so a pricing change costs nothing extra now.",
         act="follow_up", ents=["E_3"], cites=[], hier=[["N_22", "subcase"]], prag=[["N_26", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Site copy done; pricing change considered alongside the rewrite.",
         ref="Pricing page rewrite"),
    dict(id="N_28", date="2026-05-19",
         q="New tiers then: the old Lite and Pro become Nimbus Free and Nimbus Team. Team goes to €6 per seat, and Free is capped at 3 seats instead of 5.",
         a="Nimbus Free (3 seats) and Nimbus Team (€6/seat/month): still in the market range, and the tighter free cap pushes small teams to upgrade sooner.",
         act="decision", ents=["E_8", "E_7", "E_16"], cites=[], hier=[["N_27", "subcase"]], prag=[["N_9", "revises"]],
         creates=[], updates=[["SN_4", "revised"]], relates=[],
         summary="Tiers renamed and repriced: Nimbus Free (3 seats) and Nimbus Team (€6 per seat).",
         ref="Nimbus Free / Team pricing"),
    dict(id="N_29", date="2026-05-19",
         q="Marcus pushed back: raising the price right before launch looks bad, especially to the beta customer.",
         a="He has a point about the beta: Café Aurora agreed to a price and shouldn't be surprised. For new customers the launch is the natural moment to set the price.",
         act="disagreement", ents=["E_10", "E_14"], cites=[], hier=[], prag=[["N_28", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Marcus objects to raising the price before launch.",
         ref="Price rise pushback"),
    dict(id="N_30", date="2026-05-20",
         q="Compromise: €6 for everyone new, and Café Aurora keeps €5 per seat as the beta customer.",
         a="That works: new customers pay €6 per seat on Nimbus Team, and Café Aurora is grandfathered at €5.",
         act="agreement", ents=["E_14", "E_7"], cites=[], hier=[], prag=[["N_29", "resolves"]],
         creates=[], updates=[], relates=[["SN_4", "supports"]],
         summary="€6 per seat for new customers; Café Aurora grandfathered at €5.",
         ref="Grandfather beta at €5"),
    # ---- Beta trouble & restoring offline --------------------------------------------------
    dict(id="N_31", date="2026-05-25",
         q="Café Aurora just told us they might drop out of the beta. I don't know why yet; their feedback has been vague. Why would they?",
         a="Let's find out before guessing. Ask to interview a few shift leads directly rather than the head office.",
         act="factual_question", ents=["E_14", "E_13"], cites=[], hier=[["N_10", "subcase"]], prag=[],
         creates=["SN_12"], updates=[], relates=[["SN_9", "contradicts"]],
         summary="Café Aurora threatens to drop the beta; the reason is unknown.",
         ref="Beta at risk"),
    dict(id="N_32", date="2026-05-26",
         q="Interviewed five shift leads. Several sites have kitchens and stockrooms in basements with no phone signal.",
         a="That's a strong clue. Where do staff usually check their rota?",
         act="information", ents=[], cites=[], hier=[["N_31", "subcase"]], prag=[["N_31", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Several Café Aurora sites have basement areas with no signal.",
         ref="Basements without signal"),
    dict(id="N_33", date="2026-05-26",
         q="Right there, on their breaks, in the basement. And the app shows nothing without a connection.",
         a="So the gap is exactly the per-site rota on phones they asked for at the start [N_11], which only works online.",
         act="information", ents=["E_3"], cites=["N_11"], hier=[["N_32", "subcase"]], prag=[["N_32", "depends_on"], ["N_11", "references"]],
         creates=[], updates=[], relates=[],
         summary="Staff check rotas in basements where the app shows nothing offline.",
         ref="App blank offline"),
    dict(id="N_34", date="2026-05-27",
         q="So the root cause is that staff can't see their rotas offline?",
         a="Yes. That's why Café Aurora is at risk: staff can't access rotas without signal, and for a scheduling product that's the core job.",
         act="clarification_request", ents=[], cites=[], hier=[["N_31", "subcase"]], prag=[["N_31", "resolves"], ["N_33", "depends_on"]],
         creates=[], updates=[["SN_12", "resolved"]], relates=[["SN_12", "resolves"]],
         summary="Root cause: staff can't see rotas offline.",
         ref="Root cause found"),
    dict(id="N_35", date="2026-05-27",
         q="Marcus found budget to hire a mobile contractor for four weeks.",
         a="That doubles mobile capacity to two engineers until launch, which changes what's feasible on the app side.",
         act="information", ents=["E_10"], cites=[], hier=[], prag=[["N_12", "revises"]],
         creates=[], updates=[["SN_5", "revised"]], relates=[],
         summary="A 4-week mobile contractor is hired; mobile capacity doubles.",
         ref="Mobile contractor hired"),
    dict(id="N_36", date="2026-05-28",
         q="Then let's bring offline access back for launch. We'll call it Work Offline, and put it on the Team tier only.",
         a="Agreed: Work Offline goes back into the launch scope, Team tier only. With two mobile engineers it fits, and it directly fixes Café Aurora's problem.",
         act="decision", ents=["E_4", "E_7"], cites=[], hier=[["N_34", "subcase"]], prag=[["N_14", "contradicts"], ["N_34", "depends_on"], ["N_35", "depends_on"]],
         creates=["SN_10"], updates=[], relates=[["SN_9", "supports"]],
         summary="Offline access restored to launch scope as 'Work Offline', Team tier only.",
         ref="Work Offline in scope"),
    dict(id="N_37", date="2026-05-28",
         q="Wait, is Work Offline the same thing as Tailwind, the offline sync we cut back in early May?",
         a="Yes, it's the same feature under a new name: Tailwind was the internal codename. What changed is capacity, not the feature itself.",
         act="clarification_request", ents=["E_4"], cites=[], hier=[["N_36", "subcase"]], prag=[["N_6", "references"], ["N_36", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Confirms Work Offline is the same feature as the earlier cut Tailwind.",
         ref="Work Offline = Tailwind"),
    dict(id="N_38", date="2026-05-28",
         q="Same design as before, then?",
         a="Same design, but read-only first: staff can view rotas offline, and edits sync when they reconnect. That keeps it within the contractor's four weeks.",
         act="follow_up", ents=["E_4"], cites=[], hier=[["N_37", "subcase"]], prag=[["N_37", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Work Offline ships read-only first, reusing the earlier design.",
         ref="Read-only first"),
    dict(id="N_39", date="2026-05-29",
         q="The mobile team says Work Offline needs one more week than we have before 16 June.",
         a="Then the date has to move again, or Work Offline misses launch, and Café Aurora made it clear that it can't.",
         act="information", ents=["E_4"], cites=[], hier=[["N_36", "subcase"]], prag=[["N_36", "depends_on"]],
         creates=[], updates=[], relates=[["SN_2", "contradicts"]],
         summary="Work Offline needs one extra week beyond 16 June.",
         ref="One more week needed"),
    dict(id="N_40", date="2026-05-29",
         q="OK, final answer: we launch on 23 June.",
         a="23 June it is. That's the new public launch date for Nimbus.",
         act="decision", ents=["E_12", "E_3"], cites=[], hier=[["N_39", "subcase"]], prag=[["N_24", "revises"], ["N_39", "depends_on"]],
         creates=[], updates=[["SN_2", "revised"]], relates=[],
         summary="Launch moved to 23 June to include Work Offline.",
         ref="Launch 23 June"),
    dict(id="N_41", date="2026-06-02",
         q="Work Offline QA started. Sync works, but there are conflicts when a manager edits the rota while someone is offline.",
         a="For a read-only first version the rule is simple: the server always wins, and offline devices just refresh their copy on reconnect.",
         act="information", ents=["E_4"], cites=[], hier=[["N_36", "subcase"]], prag=[["N_38", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Sync conflicts found in QA; server-wins rule for the read-only version.",
         ref="Sync conflicts"),
    dict(id="N_42", date="2026-06-05",
         q="What about staff who stay offline for days?",
         a="Show a clear 'last updated' timestamp on the rota, and a warning if it's older than 24 hours.",
         act="factual_question", ents=["E_4"], cites=[], hier=[["N_41", "subcase"]], prag=[["N_41", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Stale offline rotas get a last-updated timestamp and warning.",
         ref="Stale-rota warning"),
    dict(id="N_43", date="2026-06-09",
         q="Work Offline passed QA on Café Aurora's own devices.",
         a="Great: that's the customer who needed it, on their real hardware.",
         act="information", ents=["E_4", "E_14"], cites=[], hier=[["N_36", "subcase"]], prag=[["N_42", "depends_on"]],
         creates=[], updates=[], relates=[["SN_10", "supports"]],
         summary="Work Offline passes QA on Café Aurora devices.",
         ref="Work Offline passes QA"),
    dict(id="N_44", date="2026-06-10",
         q="Surprise: Marcus built the Slack integration during a hack week, and it's solid enough to ship.",
         a="Then the earlier reason for holding it back, a lack of backend time, no longer applies. It can ship at launch.",
         act="information", ents=["E_10", "E_6"], cites=[], hier=[], prag=[["N_16", "contradicts"]],
         creates=[], updates=[["SN_11", "lifted"]], relates=[],
         summary="Slack integration built in a hack week; it can ship at launch.",
         ref="Slack ready"),
    dict(id="N_45", date="2026-06-11",
         q="Should Slack be on Free or only on Team?",
         a="Slack is cheap for you to run and good for adoption; on the free tier it helps word-of-mouth inside companies.",
         act="factual_question", ents=["E_6", "E_8", "E_7"], cites=[], hier=[["N_44", "subcase"]], prag=[["N_28", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks which tier gets Slack.",
         ref="Slack tier question"),
    dict(id="N_46", date="2026-06-11",
         q="Then both tiers get Slack.",
         a="Slack integration on both Nimbus Free and Nimbus Team.",
         act="decision", ents=["E_6", "E_8", "E_7"], cites=[], hier=[["N_45", "subcase"]], prag=[["N_45", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Slack integration ships on both tiers.",
         ref="Slack on both tiers"),
    dict(id="N_47", date="2026-06-18",
         q="Final launch-day scope check for Nimbus, please.",
         a="Nimbus launches 23 June with Smart Rota (labelled beta), shift swaps, Work Offline (read-only, Team tier) and Slack integration on both tiers. Pricing: Nimbus Free up to 3 seats, Nimbus Team €6 per seat, Café Aurora grandfathered at €5.",
         act="request", ents=["E_3", "E_5", "E_4", "E_6", "E_8", "E_7", "E_14"], cites=[], hier=[["N_28", "supercase"], ["N_36", "supercase"], ["N_46", "supercase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Launch-day scope for Nimbus confirmed.",
         ref="Launch-day scope"),
    dict(id="N_48", date="2026-06-23",
         q="We launched today! And Café Aurora converted to a paid Nimbus Team account.",
         a="Congratulations. A public launch with a paying customer on day one is exactly the goal you set.",
         act="information", ents=["E_12", "E_14", "E_7"], cites=[], hier=[], prag=[["N_40", "depends_on"], ["N_1", "resolves"]],
         creates=[], updates=[["SN_1", "achieved"]], relates=[],
         summary="Nimbus launched; Café Aurora converted to paid.",
         ref="Launched, beta converted"),
    dict(id="N_49", date="2026-06-24",
         q="I need to write the launch retro. What changed from the original plan, and why?",
         a="Three big changes. The name: Falcon became Nimbus because of Falcon Systems' trademark [N_21], which pushed launch to 16 June. Scope: offline sync was cut for capacity [N_14], then restored as Work Offline once a contractor was hired and Café Aurora's basement problem surfaced [N_36], pushing launch to 23 June. Pricing: Falcon Lite/Pro became Nimbus Free (3 seats) and Team (€6). Slack also made it in after Marcus's hack week.",
         act="request", ents=["E_3", "E_9", "E_4", "E_14", "E_8", "E_7", "E_6", "E_10"], cites=["N_14", "N_21", "N_36"], hier=[["N_14", "supercase"], ["N_21", "supercase"], ["N_36", "supercase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Launch retro: rename, offline cut and restore, pricing change, Slack.",
         ref="Launch retro"),
    dict(id="N_50", date="2026-06-26",
         q="First-week numbers: 41% of new sign-ups activated.",
         a="41% activation in week one is a strong start for a scheduling product. Track it weekly against the Work Offline and Slack usage to see which one drives it.",
         act="information", ents=["E_15"], cites=[], hier=[], prag=[["N_48", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="First-week activation is 41%.",
         ref="41% activation"),
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
    eid: {"type": d["type"], "name": d["name"], "aliases": d["aliases"], "mentioned_in": mentioned_in[eid]}
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
    "conversation_id": "product_rename",
    "domain": "SaaS product launch planning with a mid-conversation product rename",
    "schema_note": (
        "Mirrors INESCTEC_RESEARCH.md section 3/4 output schema, same convention as "
        "conversations/marathon_trip. Domain entity types (domain_config.json): product, feature, metric. "
        "Entities carry an aliases list (core/schema/entity.py Entity.aliases): name is the surface form as "
        "first mentioned, later surface forms are aliases (Falcon -> Nimbus, Tailwind -> Work Offline, "
        "Falcon Lite/Pro -> Nimbus Free/Team). Built to break semantic retrieval: decisions are made under "
        "old names and every probe uses the new names."
    ),
    "schema_findings": [
        {
            "raised_at_node": "N_21",
            "issue": "entity_prf scores by (turn, normalised name) and ignores aliases. The flat gold therefore "
                     "uses the first surface form ('Falcon') for every mention of E_3, including turns whose text "
                     "only says 'Nimbus'.",
            "proposed_direction": "With the current scorer this rewards correct merging (a merged entity keeps "
                                   "its first name, matching gold on every turn) and penalises a separate 'Nimbus' "
                                   "entity on each post-rename turn. An alias-aware criterion (match if the "
                                   "predicted name equals the gold name or any alias) would additionally report "
                                   "surface-form recall separately from merge accuracy; not implemented yet.",
        },
        {
            "raised_at_node": "N_36",
            "issue": "Restoring a cut feature cannot re-activate SN_3, because reverted is terminal. The restored "
                     "scope is a new decision (SN_10) with a different name and a narrower scope (Team tier only).",
            "proposed_direction": "Same convention as the other corpora. The link between SN_3 and SN_10 exists "
                                   "only through the interaction graph (N_36 contradicts N_14; N_37 references "
                                   "N_6), which is exactly what probe p2 tests.",
        },
        {
            "raised_at_node": "N_44",
            "issue": "SN_11 (no Slack before launch) is lifted because its reason, missing backend time, "
                     "disappeared, not because anyone decided otherwise. N_44 contradicts N_16.",
            "proposed_direction": "Consistent with hpc_support's SN_8: lifted means the constraint no longer binds "
                                   "the plan, whatever the cause.",
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

# Old names must not appear in turn text after the rename, except in the explicit link turns.
OLD_NAMES = ("Falcon", "Tailwind")
LINK_TURNS = {"N_21", "N_28", "N_37", "N_49"}
leaks = [n["id"] for n in NODES[node_index["N_22"]:]
         if n["id"] not in LINK_TURNS and any(o in n["q"] + n["a"] for o in OLD_NAMES)]
assert not leaks, f"old names leak into post-rename turns: {leaks}"

print(f"Wrote {len(NODES)} interaction nodes, {len(ENTITIES)} entities, {len(STATE_NODE_DEFS)} state nodes.")
print("Epistemic status:", dict(Counter(status.values())))
print("Speech acts:", dict(Counter(n["act"] for n in NODES)))
print("Hierarchical:", dict(Counter(l for n in NODES for _, l in n["hier"])))
print("Pragmatic:", dict(Counter(l for n in NODES for _, l in n["prag"])))
print("State nodes:", dict(Counter((d["type"], sn_status[sid]) for sid, d in STATE_NODE_DEFS.items())))
print("Entity types:", dict(Counter(d["type"] for d in ENTITIES.values())))
