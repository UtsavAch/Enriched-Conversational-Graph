# `product_rename`: outline

**Domain:** a product manager (Priya) at a small SaaS startup (Tessellate) plans the launch of a
team-scheduling product codenamed **Falcon**. At N_21 a trademark conflict forces a rename to
**Nimbus**, and the offline-sync feature (codename **Tailwind**) is cut and later restored under a new
name, **"Work Offline"**. **50 turns**, 2026-05-04 → 2026-06-26.

**Why this corpus:** it's built to break **semantic retrieval**. Most decisions are made under the old
names (Falcon, Tailwind); late turns and every probe use the new names (Nimbus, Work Offline). The
only link is the rename turns (N_21, N_36) and the edges from them. It also tests **entity aliasing**:
the gold keeps one entity with aliases, so an extractor that creates "Falcon" and "Nimbus" as two
entities is counted as a merge failure.

## Domain config

| Type | Description |
|---|---|
| `product` | A named product, product codename, or product tier. |
| `feature` | A named product feature or feature codename. |
| `metric` | A named business/product metric (e.g. activation rate, MRR). |

## Entities (planned; aliases in the gold file)

| id | type | name | aliases |
|---|---|---|---|
| E_1 | person | Priya | |
| E_2 | organization | Tessellate | |
| E_3 | product | Nimbus | Falcon, Project Falcon |
| E_4 | feature | Work Offline | Tailwind, offline sync |
| E_5 | feature | Smart Rota | auto-scheduler |
| E_6 | feature | Slack integration | |
| E_7 | product | Nimbus Team tier | Falcon Pro |
| E_8 | product | Nimbus Free tier | Falcon Lite |
| E_9 | organization | Falcon Systems Ltd (trademark holder) | |
| E_10 | person | Marcus (CTO) | |
| E_11 | person | Elena (design lead) | |
| E_12 | event | public launch | |
| E_13 | event | beta with Café Aurora chain | |
| E_14 | organization | Café Aurora | |
| E_15 | metric | activation rate | |
| E_16 | measurement | €6 per seat/month | |

## State nodes

| id | type | label (as first created) | lifecycle |
|---|---|---|---|
| SN_1 | goal | Launch Falcon publicly with a paying beta customer | +N_1 → achieved N_50 (label becomes "Launch Nimbus…" at N_21) |
| SN_2 | decision | Launch date 2 June | +N_3 → revised N_24 (16 June, rename work) → revised N_40 (23 June, Tailwind re-added) |
| SN_3 | decision | Tailwind (offline sync) is in the launch scope | +N_6 → reverted N_14 |
| SN_4 | decision | Two tiers: Falcon Lite (free, 5 seats) and Falcon Pro (€5/seat) | +N_9 → revised N_28 (€6/seat, Lite capped at 3 seats; renamed Free/Team) |
| SN_5 | constraint | Engineering capacity: 2 backend + 1 mobile engineer until launch | +N_12 → revised N_35 (contractor added: +1 mobile) |
| SN_6 | open_question | Can we keep the name Falcon? | +N_19 → resolved N_21 (no; renamed to Nimbus) |
| SN_7 | decision | Product name is Nimbus | +N_21 |
| SN_8 | decision | Smart Rota ships as beta-labelled | +N_17 |
| SN_9 | decision | Café Aurora is the beta customer | +N_10 |
| SN_10 | decision | Offline mode ("Work Offline") is in the launch scope, Team tier only | +N_36 (new node; SN_3 is terminal) |
| SN_11 | constraint | No Slack integration until after launch | +N_16 → lifted N_44 (Marcus built it in a hack week) |
| SN_12 | open_question | Why did Café Aurora threaten to drop the beta? | +N_31 → resolved N_34 (staff at sites with no signal can't see rotas) |

## Turn arc

| Turn | Date | Act | Gist | Edges / state |
|---|---|---|---|---|
| **Planning as "Falcon"** | | | | |
| N_1 | 05-04 | request | Priya: plan the Falcon launch; need a paying beta | S: +SN_1 |
| N_2 | 05-04 | information | Launch checklist | H: N_1 subcase · P: N_1 depends_on |
| N_3 | 05-04 | decision | Launch 2 June | H: N_2 subcase · S: +SN_2 |
| N_4–N_5 | 05-05 | factual_question / information | Core features: Smart Rota, shift swaps, Tailwind | H: N_1 subcase · P: depends_on |
| N_6 | 05-05 | decision | Tailwind is in launch scope | H: N_4 subcase · S: +SN_3 |
| N_7–N_8 | 05-06 | factual_question / information | Pricing research | H: N_1 subcase, N_4 same_level |
| N_9 | 05-06 | decision | Falcon Lite free (5 seats), Falcon Pro €5/seat | P: N_8 depends_on · S: +SN_4 |
| N_10 | 05-07 | decision | Café Aurora (12 cafés) as beta | H: N_1 subcase · S: +SN_9 |
| N_11 | 05-07 | information | Café Aurora's needs: rota by site, mobile first | H: N_10 subcase |
| N_12 | 05-08 | information | Marcus: 2 backend + 1 mobile until launch | S: +SN_5 |
| N_13 | 05-08 | information | Tailwind is 3 weeks of mobile work alone | H: N_6 subcase · P: N_12 depends_on · ~SN_3 constrained_by |
| N_14 | 05-08 | decision | Cut Tailwind from launch | P: N_6 contradicts · S: SN_3→reverted |
| N_15 | 05-09 | follow_up | What does the beta lose without Tailwind? | P: N_14 depends_on, N_11 references |
| N_16 | 05-09 | decision | No Slack integration before launch either | H: N_14 same_level · S: +SN_11 |
| N_17 | 05-10 | decision | Smart Rota ships labelled beta | H: N_4 subcase · S: +SN_8 |
| N_18 | 05-10 | follow_up | Falcon scope recap | H: N_6 supercase, N_9 supercase, N_17 supercase |
| **The rename** | | | | |
| N_19 | 05-12 | factual_question | Legal found "Falcon Systems Ltd" holds the mark in our class | H: N_1 subcase · S: +SN_6 |
| N_20 | 05-12 | information | Options: coexistence letter (slow) vs rename | P: N_19 depends_on |
| N_21 | 05-13 | decision | Rename **Falcon → Nimbus** everywhere | P: N_19 resolves · S: SN_6→resolved, +SN_7 |
| N_22 | 05-13 | follow_up | Rename checklist: domain, app stores, marketing | H: N_21 subcase · P: N_21 depends_on |
| N_23 | 05-14 | information | App-store rename needs a new review cycle (~10 days) | H: N_22 subcase |
| N_24 | 05-14 | decision | Launch moved to 16 June | P: N_3 revises, N_23 depends_on · S: SN_2→revised |
| N_25–N_27 | 05-15 → 05-18 | information / follow_up | Elena's new brand; copy updates (**from here on, only "Nimbus" is used**) | H: N_22 subcase · P: depends_on |
| N_28 | 05-19 | decision | Tiers renamed Nimbus Free / Nimbus Team; Team €6/seat; Free capped at 3 seats | P: N_9 revises · S: SN_4→revised |
| N_29 | 05-19 | disagreement | Marcus: price hike right before launch is risky | P: N_28 depends_on |
| N_30 | 05-20 | agreement | Keep €6; grandfather beta at €5 | P: N_29 resolves · ~SN_4 supports |
| **Beta trouble & restoring offline** | | | | |
| N_31 | 05-25 | factual_question | Café Aurora threatens to leave the beta. Why? | H: N_10 subcase · S: +SN_12 |
| N_32–N_33 | 05-26 | information | Interviews: basement kitchens, no signal | P: N_31 depends_on · P: N_11 references |
| N_34 | 05-27 | information | Root cause: staff can't see rotas offline | P: N_31 resolves · S: SN_12→resolved |
| N_35 | 05-27 | information | Marcus hires a mobile contractor for 4 weeks | S: SN_5→revised |
| N_36 | 05-28 | decision | Bring back the offline feature as "**Work Offline**", Team tier only | P: N_14 contradicts, N_34 depends_on, N_35 depends_on · S: +SN_10 |
| N_37 | 05-28 | clarification_request | "Is this the same thing we cut in May?" (**the only explicit Tailwind ↔ Work Offline link**) | P: N_6 references, N_36 depends_on |
| N_38 | 05-28 | information | Yes: same design, read-only first | P: N_37 resolves |
| N_39 | 05-29 | information | Needs 1 extra week | H: N_36 subcase |
| N_40 | 05-29 | decision | Launch 23 June | P: N_24 revises · S: SN_2→revised |
| N_41–N_43 | 06-02 → 06-09 | information / follow_up | Work Offline QA; sync conflict edge cases | H: N_36 subcase · P: depends_on chain |
| N_44 | 06-10 | information | Marcus built Slack integration in hack week; can ship | P: N_16 contradicts · S: SN_11→lifted |
| N_45 | 06-11 | factual_question | Slack on Free or Team? | H: N_44 subcase · P: N_28 depends_on |
| N_46 | 06-11 | decision | Both tiers | P: N_45 resolves |
| N_47 | 06-18 | follow_up | Launch-day scope for Nimbus (no old names used) | H: N_28 supercase, N_36 supercase, N_46 supercase |
| N_48 | 06-23 | information | Launched; Café Aurora converts to paid | P: N_40 depends_on |
| N_49 | 06-24 | follow_up | "Write the launch retro: what changed and why" | H: N_14 supercase, N_21 supercase, N_36 supercase |
| N_50 | 06-26 | information | Activation 41% in week 1 | S: SN_1→achieved |

**Label targets:** subcase ~18 · same_level ~4 · supercase 9 · depends_on ~24 · references ~5 ·
resolves ~7 · revises 4 · contradicts 3.

## Probes (all phrased with the **new** names only)

| id | Question | Target | expected_any | forbidden_any | from | Designed to defeat |
|---|---|---|---|---|---|---|
| p1 | Is Work Offline part of the Nimbus launch? | SN_10 | "yes", "Team tier" | "cut", "not in scope" | 36 | anti-semantic (the cut decision is phrased as "Tailwind") |
| p2 | Was Work Offline ever dropped from the plan, and why? | SN_3 | "capacity", "mobile" | — | 37 | anti-semantic (only reachable via the N_37 alias link) |
| p3 | When does Nimbus launch? | SN_2 | "23 June" | "2 June", "16 June" | 40 | anti-semantic |
| p4 | What does a Nimbus Team seat cost? | SN_4 | "€6" | "€5" (except "grandfathered" context) | 28 | anti-semantic (N_9 has "Pro €5") |
| p5 | How many seats does Nimbus Free allow? | SN_4 | "3" | "5 seats" | 28 | anti-semantic |
| p6 | Why was the product renamed? | SN_6 | "trademark", "Falcon Systems" | — | 21 | anti-hierarchical |
| p7 | Does Nimbus ship with Slack integration? | SN_11 | "yes", "both tiers" | "after launch", "no Slack" | 44 | anti-semantic |
| p8 | Is Smart Rota labelled beta at launch? | SN_8 | "beta" | — | 17 | anti-recency (set pre-rename, never repeated) |
| p9 | Who is the Nimbus beta customer? | SN_9 | "Café Aurora" | — | 10 | anti-recency + anti-semantic (set pre-rename) |
