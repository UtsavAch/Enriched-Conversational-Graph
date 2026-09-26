# `kitchen_reno`: outline

**Domain:** a homeowner (Carla) plans a kitchen renovation in her Lisbon apartment on a fixed budget,
collecting quotes, changing contractors and re-cutting line items. **50 turns**, 2026-01-10 → 2026-04-18.

**Why this corpus:** numbers that **keep changing** (total budget, cabinet line item, wall length,
start date). Later turns often mention a topic *with a stale number in passing*, which should trip
recency-only retrieval. It also covers everyday entity types (`measurement`, `organization`, `person`,
`location`) and adds a `material` type.

## Domain config

| Type | Description |
|---|---|
| `material` | A named building/finishing material (e.g. quartz, laminate, porcelain tile). |
| `product` | A named product or appliance model (e.g. an induction hob model). |
| `trade` | A named trade or professional role (e.g. electrician, plumber). |

## Entities (planned)

E_1 person Carla · E_2 person Miguel (partner) · E_3 location Lisbon apartment (Alvalade) ·
E_4 organization Ferreira Obras (contractor A) · E_5 organization Casa Nova Remodelações (contractor B) ·
E_6 person Sr. Ferreira · E_7 person Ana (Casa Nova PM) · E_8 measurement €18,000 total budget ·
E_9 measurement cabinet line item · E_10 measurement 3.40 m back wall · E_11 material quartz ·
E_12 material HPL laminate · E_13 material porcelain tile · E_14 product induction hob ·
E_15 product built-in oven · E_16 trade electrician · E_17 organization Lisbon city hall (Câmara) ·
E_18 organization IKEA

## State nodes

| id | type | label | lifecycle |
|---|---|---|---|
| SN_1 | goal | Finish the kitchen before Miguel's parents visit (early May) | +N_1 → achieved N_50 |
| SN_2 | constraint | Total budget €18,000 | +N_2 → revised N_29 (€21,500 after an inheritance top-up) |
| SN_3 | decision | Cabinets: IKEA Metod, €4,200 | +N_8 → revised N_22 (€5,100 with custom filler panels) → revised N_36 (€4,600, fillers dropped, door upgrade kept) |
| SN_4 | decision | Hire Ferreira Obras | +N_12 → reverted N_19 |
| SN_5 | decision | Hire Casa Nova Remodelações | +N_20 |
| SN_6 | decision | Countertop: quartz | +N_14 → reverted N_27 |
| SN_7 | decision | Countertop: HPL laminate, stone-look | +N_27 |
| SN_8 | open_question | Is a permit (comunicação prévia) needed to move the gas line? | +N_15 → resolved N_24 (switching to induction removes the gas work, so no permit) |
| SN_9 | decision | Switch from gas to induction | +N_24 |
| SN_10 | constraint | Back wall is 3.40 m | +N_6 → revised N_17 (re-measured: 3.28 m, out-of-plumb wall) |
| SN_11 | decision | Start date 2 March | +N_21 → revised N_33 (16 March, tile delay) |
| SN_12 | decision | Oven in a tall column, not under the hob | +N_31 |
| SN_13 | constraint | Electrician must upgrade the circuit for induction (+€650) | +N_25 → lifted N_40 (existing 32A circuit is sufficient) |

## Turn arc

| Turn | Date | Act | Gist | Edges / state |
|---|---|---|---|---|
| **Planning & first numbers (Jan)** | | | | |
| N_1 | 01-10 | request | Kitchen redo before in-laws visit in May | S: +SN_1 |
| N_2 | 01-10 | decision | Total budget €18k | H: N_1 subcase · S: +SN_2 |
| N_3 | 01-10 | information | Typical split: cabinets 25%, counters 10%, labour 35%… | H: N_2 subcase · P: N_2 depends_on |
| N_4–N_5 | 01-11 | factual_question / information | Layout: L-shape vs galley | H: N_1 subcase, then same_level |
| N_6 | 01-11 | information | Back wall 3.40 m | H: N_4 subcase · S: +SN_10 |
| N_7 | 01-12 | factual_question | IKEA vs custom cabinets? | H: N_3 subcase · P: N_3 depends_on |
| N_8 | 01-12 | decision | IKEA Metod, €4,200 | P: N_7 resolves · S: +SN_3, ~SN_2 constrained_by |
| N_9–N_11 | 01-15 | information / follow_up | Two quotes: Ferreira €7,900 labour, Casa Nova €9,400 | H: N_3 subcase · P: depends_on |
| N_12 | 01-16 | decision | Go with Ferreira (cheaper) | P: N_11 depends_on · S: +SN_4 |
| N_13 | 01-18 | factual_question | Countertop material? | H: N_3 subcase |
| N_14 | 01-18 | decision | Quartz, €2,300 | P: N_13 resolves · S: +SN_6 |
| N_15 | 01-20 | factual_question | Moving the hob means moving the gas line; permit? | H: N_4 subcase · S: +SN_8 |
| N_16 | 01-20 | information | Probably needs a comunicação prévia; check with Câmara | P: N_15 depends_on |
| **Problems (Feb)** | | | | |
| N_17 | 02-01 | correction | Ferreira re-measured: 3.28 m, wall out of plumb | P: N_6 revises · S: SN_10→revised |
| N_18 | 02-01 | information | Ferreira's revised quote +€2,100 "for surprises" and a 6-week wait | H: N_12 subcase · P: N_12 depends_on |
| N_19 | 02-02 | decision | Drop Ferreira | P: N_12 contradicts · S: SN_4→reverted |
| N_20 | 02-02 | decision | Hire Casa Nova (€9,400, fixed price) | P: N_19 depends_on, N_11 references · S: +SN_5 |
| N_21 | 02-03 | decision | Casa Nova can start 2 March | H: N_20 subcase · S: +SN_11 |
| N_22 | 02-05 | information | 3.28 m leaves a 12 cm gap → custom filler panels, cabinets now €5,100 | P: N_17 depends_on, N_8 revises · S: SN_3→revised |
| N_23 | 02-05 | follow_up | Running total €19,700: over budget | H: N_2 subcase · P: N_2 depends_on · ~SN_2 contradicts |
| N_24 | 02-07 | decision | Switch to induction: no gas line move, no permit | P: N_15 resolves · S: SN_8→resolved, +SN_9 |
| N_25 | 02-08 | information | Ana: induction needs a circuit upgrade, +€650 | H: N_24 subcase · S: +SN_13 |
| N_26 | 02-08 | follow_up | Now €20,350; where to cut? | P: N_23 depends_on |
| N_27 | 02-09 | decision | Downgrade quartz → HPL laminate (saves €1,500) | P: N_14 contradicts, N_26 resolves · S: SN_6→reverted, +SN_7 |
| N_28 | 02-10 | disagreement | Miguel hates the laminate idea | P: N_27 depends_on |
| N_29 | 02-12 | information | Miguel's parents top up: budget now €21,500 | P: N_2 revises · S: SN_2→revised |
| N_30 | 02-12 | factual_question | Go back to quartz then? | P: N_29 depends_on |
| N_31 | 02-12 | decision | No: keep laminate, spend the margin on a tall oven column | P: N_30 resolves · S: +SN_12, ~SN_7 supports |
| N_32 | 02-14 | follow_up | Budget recap across all line items | H: N_8 supercase, N_20 supercase, N_27 supercase, N_31 supercase |
| **Execution (Mar–Apr)** | | | | |
| N_33 | 02-24 | information | Tile supplier delay → start moved to 16 March | P: N_21 revises · S: SN_11→revised |
| N_34 | 02-24 | factual_question | Does 16 March still finish before May? | P: N_33 depends_on · ~SN_1 constrained_by |
| N_35 | 02-24 | information | 6-week job → end of April, tight but OK | P: N_34 resolves |
| N_36 | 03-02 | decision | IKEA restocked a 20 cm module → fillers dropped, cabinets €4,600 | P: N_22 revises · S: SN_3→revised |
| N_37 | 03-16 | information | Demolition started | P: N_33 depends_on |
| N_38 | 03-18 | information | Found old wiring behind the wall | H: N_37 subcase |
| N_39 | 03-19 | factual_question | Does this change the induction upgrade? | P: N_25 references |
| N_40 | 03-19 | information | Electrician: existing 32A line is fine, no upgrade needed (−€650) | P: N_25 contradicts, N_39 resolves · S: SN_13→lifted |
| N_41 | 03-20 | follow_up | Miguel mentions "our €18k kitchen" to his parents (**stale number in passing**) | P: N_2 references |
| N_42–N_45 | 03-25 → 04-06 | information / factual_question | Tiling, cabinet install, oven column fit (3.28 m wall OK) | H: N_37 subcase, pairs same_level · P: depends_on chain, 1 × references N_17 |
| N_46 | 04-08 | factual_question | Final paint colour? | H: N_37 same_level |
| N_47 | 04-10 | information | Snag list | H: N_37 subcase |
| N_48 | 04-15 | information | Final bill €20,950 | P: N_29 depends_on |
| N_49 | 04-15 | follow_up | "What did we change from the original plan and why?" | H: N_19 supercase, N_24 supercase, N_27 supercase, N_36 supercase |
| N_50 | 04-18 | agreement | Done, 2 weeks before the visit | S: SN_1→achieved |

**Label targets:** subcase ~16 · same_level ~5 · supercase 8 · depends_on ~22 · references ~5 ·
resolves ~7 · revises 6 · contradicts 5.

## Probes

| id | Question | Target | expected_any | forbidden_any | from | Designed to defeat |
|---|---|---|---|---|---|---|
| p1 | What is Carla's total renovation budget? | SN_2 | "21,500" | "18,000", "€18k" | 29 | anti-recency (N_41 repeats the stale €18k) |
| p2 | How much are the cabinets budgeted at? | SN_3 | "4,600" | "4,200", "5,100" | 36 | anti-semantic (three similar turns, two stale) |
| p3 | Which contractor is doing the work? | SN_5 | "Casa Nova" | "Ferreira" | 20 | anti-semantic |
| p4 | What countertop material was chosen? | SN_7 | "laminate", "HPL" | "quartz" | 27 | anti-semantic |
| p5 | How long is the back wall? | SN_10 | "3.28" | "3.40" | 17 | anti-recency |
| p6 | Does the kitchen need a permit? | SN_8 | "no", "induction" | "comunicação prévia is required" | 24 | anti-hierarchical |
| p7 | Does the electrician need to upgrade the circuit? | SN_13 | "no", "32A" | "+€650", "upgrade needed" | 40 | anti-semantic |
| p8 | When did work start? | SN_11 | "16 March" | "2 March" | 33 | anti-semantic |
| p9 | Where does the oven go? | SN_12 | "tall column" | "under the hob" | 31 | anti-recency |
