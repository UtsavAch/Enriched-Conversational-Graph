# `relocation`: outline

**Domain:** a software engineer (Daniel) relocates from Lisbon to Munich for a job at Brennwerk GmbH,
with his partner Sofia and daughter Lia (8). Six threads run **interleaved**, and each is dropped and
picked up again 15–30 turns later. **80 turns**, 2026-04-06 → 2026-08-31.

**Why this corpus:** interleaved parallel threads are the natural home of `same_level`, and
**cross-thread `depends_on`** (the bank account needs the Anmeldung, which needs a rental contract) is a
dependency that is far away in the conversation but close in the graph. Returning to a thread after
20+ turns is exactly where recency retrieval fails and hierarchical/pragmatic edges should help.

## Threads

| Thread | Tag | Turns (interleaved) |
|---|---|---|
| Visa / EU Blue Card | **V** | N_3–6, N_21–23, N_44–46, N_63 |
| Housing | **H** | N_7–11, N_24–29, N_47–49, N_64–65 |
| Registration (Anmeldung) & bank | **R** | N_12–14, N_30–33, N_50–53 |
| School for Lia | **S** | N_15–18, N_34–38, N_54–57, N_72 |
| Health insurance | **I** | N_19–20, N_39–41, N_58–60 |
| Moving shipment | **M** | N_42–43, N_61–62, N_66–69 |
| Overview / recap | — | N_1–2, N_70–71, N_73–80 |

## Domain config

| Type | Description |
|---|---|
| `permit` | A named residence/work permit or official registration (e.g. EU Blue Card, Anmeldung). |
| `document` | (default) a named form, certificate, or contract. |

## Entities (planned)

E_1 person Daniel · E_2 person Sofia · E_3 person Lia · E_4 organization Brennwerk GmbH ·
E_5 location Munich · E_6 location Lisbon · E_7 permit EU Blue Card · E_8 permit Anmeldung ·
E_9 organization KVR (Munich immigration office) · E_10 organization N26 · E_11 organization Sparkasse ·
E_12 location Haidhausen · E_13 location Pasing · E_14 organization Grundschule an der Kirchenstraße ·
E_15 organization Bavarian International School · E_16 organization TK (Techniker Krankenkasse) ·
E_17 document Wohnungsgeberbestätigung (landlord confirmation) · E_18 organization Transeuropa Movers ·
E_19 measurement €58,400 salary threshold · E_20 measurement €2,300/month rent cap · E_21 event start date at Brennwerk

## State nodes

| id | type | label | thread | lifecycle |
|---|---|---|---|---|
| SN_1 | goal | Move the family to Munich and be settled before Lia's school year | — | +N_1 → achieved N_80 |
| SN_2 | decision | Daniel starts at Brennwerk on 1 July | — | +N_2 → revised N_45 (15 July, visa appointment delay) |
| SN_3 | decision | Apply for the EU Blue Card (not a general work visa) | V | +N_5 |
| SN_4 | open_question | Does Sofia get work rights automatically? | V | +N_6 → resolved N_23 (yes, family reunification under Blue Card) |
| SN_5 | constraint | Rent cap €2,300/month warm | H | +N_8 → revised N_27 (€2,600 after Brennwerk relocation allowance) |
| SN_6 | decision | Live in Pasing (cheaper, S-Bahn) | H | +N_10 → reverted N_28 |
| SN_7 | decision | Live in Haidhausen (walkable to school, shorter commute) | H | +N_28 |
| SN_8 | decision | Open an N26 account before arriving | R | +N_13 → reverted N_32 (N26 account can't be used for the rental deposit guarantee) |
| SN_9 | decision | Open a Sparkasse account after the Anmeldung | R | +N_32 |
| SN_10 | open_question | Public Grundschule or international school for Lia? | S | +N_15 → resolved N_36 |
| SN_11 | decision | Grundschule an der Kirchenstraße + weekly German tutor | S | +N_36 → revised N_56 (plus a Übergangsklasse / transition class for 6 months) |
| SN_12 | decision | Public health insurance (TK), family co-insured | I | +N_20 → revised N_41 (Sofia insured separately once she starts working) |
| SN_13 | constraint | Temporary flat only until 31 July | H | +N_25 → lifted N_48 (lease signed) |
| SN_14 | decision | Ship with Transeuropa, 20 ft container | M | +N_43 → revised N_62 (shared container, fewer items; car sold) |
| SN_15 | open_question | Bring the car or sell it? | M | +N_42 → resolved N_62 (sell) |

## Turn arc

| Turn | Date | Thread | Act | Gist | Edges / state |
|---|---|---|---|---|---|
| N_1 | 04-06 | — | request | Got the Brennwerk offer; family move before September | S: +SN_1 |
| N_2 | 04-06 | — | decision | Start date 1 July | H: N_1 subcase · S: +SN_2 |
| N_3 | 04-07 | V | factual_question | Which permit? | H: N_1 subcase · P: N_1 depends_on |
| N_4 | 04-07 | V | information | Blue Card salary threshold €58,400; his offer is €72k | P: N_3 depends_on |
| N_5 | 04-07 | V | decision | Blue Card | P: N_3 resolves · S: +SN_3 |
| N_6 | 04-07 | V | factual_question | Can Sofia work? | H: N_5 subcase · S: +SN_4 |
| N_7 | 04-10 | H | request | Where to live? | H: N_1 subcase · H: N_3 same_level |
| N_8 | 04-10 | H | decision | Rent cap €2,300 warm | H: N_7 subcase · S: +SN_5 |
| N_9 | 04-10 | H | information | Neighbourhood options | P: N_8 depends_on |
| N_10 | 04-11 | H | decision | Pasing | P: N_9 depends_on · S: +SN_6, ~SN_5 constrained_by |
| N_11 | 04-11 | H | information | Munich rental market: bring SCHUFA-alternative docs | H: N_7 subcase |
| N_12 | 04-14 | R | factual_question | What is the Anmeldung? | H: N_1 subcase · H: N_7 same_level |
| N_13 | 04-14 | R | decision | Open N26 before arriving | H: N_12 same_level · S: +SN_8 |
| N_14 | 04-14 | R | information | Anmeldung needs the landlord's Wohnungsgeberbestätigung | H: N_12 subcase · P: N_12 resolves |
| N_15 | 04-17 | S | factual_question | Public vs international school for Lia? | H: N_1 subcase · H: N_7 same_level · S: +SN_10 |
| N_16–N_18 | 04-17 | S | information / follow_up | Grundschule catchment rules; BIS fees €18k/yr; Lia speaks no German | H: N_15 subcase · P: depends_on chain |
| N_19 | 04-20 | I | factual_question | Public vs private insurance? | H: N_1 subcase · H: N_15 same_level |
| N_20 | 04-20 | I | decision | TK, family co-insured | P: N_19 resolves · S: +SN_12 |
| N_21 | 04-28 | V | information | KVR appointment only on 8 July (**return to V after 14 turns**) | H: N_5 subcase · P: N_5 depends_on |
| N_22 | 04-28 | V | factual_question | Can he start work before the card? | P: N_21 depends_on |
| N_23 | 04-28 | V | information | Yes with the pre-approval; Sofia gets work rights via family reunification | P: N_6 resolves · S: SN_4→resolved |
| N_24 | 05-04 | H | information | Found a temporary furnished flat from 1 July (**return to H**) | H: N_7 subcase · P: N_10 references |
| N_25 | 05-04 | H | information | Temp flat only until 31 July | H: N_24 subcase · S: +SN_13 |
| N_26 | 05-06 | H | information | Brennwerk offers a €300/month relocation allowance for a year | H: N_7 subcase |
| N_27 | 05-06 | H | decision | Raise rent cap to €2,600 | P: N_8 revises, N_26 depends_on · S: SN_5→revised |
| N_28 | 05-08 | H | decision | Switch to Haidhausen (school walkable, commute 15 min) | P: N_10 contradicts, N_27 depends_on · S: SN_6→reverted, +SN_7 |
| N_29 | 05-08 | H | follow_up | Does Haidhausen affect which Grundschule? | P: N_16 references |
| N_30 | 05-12 | R | information | Landlords want a rent-deposit guarantee account (**return to R**) | H: N_12 subcase · P: N_28 depends_on |
| N_31 | 05-12 | R | factual_question | Can N26 do that? | P: N_13 depends_on |
| N_32 | 05-12 | R | decision | No: Sparkasse after Anmeldung; keep N26 only for spending | P: N_13 contradicts, N_31 resolves · S: SN_8→reverted, +SN_9 |
| N_33 | 05-12 | R | information | Chain: lease → Wohnungsgeberbestätigung → Anmeldung → Sparkasse → deposit | H: N_12 supercase · P: N_14 depends_on, N_30 depends_on |
| N_34 | 05-18 | S | information | Haidhausen catchment school: Kirchenstraße (**return to S**) | H: N_15 subcase · P: N_28 depends_on |
| N_35 | 05-18 | S | disagreement | Sofia prefers BIS; Daniel worries about cost | P: N_17 references |
| N_36 | 05-20 | S | decision | Kirchenstraße + weekly German tutor | P: N_15 resolves · S: SN_10→resolved, +SN_11 |
| N_37–N_38 | 05-20 | S | factual_question / information | School registration needs the Anmeldung | P: N_33 depends_on (cross-thread) |
| N_39 | 05-25 | I | information | Sofia has a job interview in Munich (**return to I**) | H: N_19 subcase |
| N_40 | 05-25 | I | factual_question | Does family co-insurance still work if she's employed? | P: N_20 depends_on |
| N_41 | 05-25 | I | decision | No: she'll be insured through her own employer | P: N_20 revises · S: SN_12→revised |
| N_42 | 06-01 | M | factual_question | Bring the car or sell? | H: N_1 subcase · S: +SN_15 |
| N_43 | 06-01 | M | decision | Transeuropa, full 20 ft container | H: N_42 same_level · S: +SN_14 |
| N_44 | 06-03 | V | information | Blue Card pre-approval arrived, KVR still 8 July | P: N_21 depends_on |
| N_45 | 06-03 | V | decision | Brennwerk agrees to shift start to 15 July | P: N_2 revises · S: SN_2→revised |
| N_46 | 06-03 | V | follow_up | Does the later start break the temp-flat dates? | P: N_25 depends_on (cross-thread) |
| N_47 | 06-10 | H | information | Viewed three Haidhausen flats | H: N_28 subcase |
| N_48 | 06-15 | H | information | Lease signed, €2,480 warm, from 1 August | P: N_27 depends_on · S: SN_13→lifted, ~SN_5 supports |
| N_49 | 06-15 | H | follow_up | Temp flat now needed 15 → 31 July only | P: N_45 depends_on, N_25 references |
| N_50–N_53 | 07-16 → 07-22 | R | information / follow_up | Anmeldung done (07-17), Sparkasse opened, deposit guarantee set | H: N_33 subcase · P: N_33 depends_on, N_48 depends_on |
| N_54–N_57 | 07-24 → 07-30 | S | information / decision | School places Lia in an Übergangsklasse for 6 months first | H: N_36 subcase · P: N_36 revises (at N_56) · S: SN_11→revised |
| N_58–N_60 | 07-28 | I | information | Sofia got the job; TK family setup changed | H: N_39 subcase · P: N_41 depends_on |
| N_61 | 07-29 | M | information | 20 ft container quote €7,800, over budget | H: N_43 subcase |
| N_62 | 07-29 | M | decision | Sell the car; shared container | P: N_42 resolves, N_43 revises · S: SN_15→resolved, SN_14→revised |
| N_63 | 08-01 | V | information | Blue Card issued | P: N_44 depends_on |
| N_64–N_65 | 08-02 | H | information | Moved into the Haidhausen flat | H: N_47 subcase · P: N_48 depends_on |
| N_66–N_69 | 08-05 → 08-12 | M | information / follow_up | Container arrives; missing box; insurance claim | H: N_62 subcase · P: depends_on chain |
| N_70 | 08-14 | — | request | "Status of everything?" | H: N_3 supercase, N_7 supercase, N_12 supercase, N_15 supercase, N_19 supercase, N_42 supercase |
| N_71 | 08-14 | — | follow_up | Open items list | P: N_70 depends_on |
| N_72 | 08-20 | S | information | Lia's first-day details confirmed | P: N_56 depends_on |
| N_73–N_78 | 08-20 → 08-28 | — | factual_question / information | Admin tail: tax ID arrives, Rundfunkbeitrag, residence parking permit | H: N_12 same_level / subcase · P: 2 × references N_33 |
| N_79 | 08-30 | — | follow_up | "What changed from our April plan?" | H: N_28 supercase, N_32 supercase, N_45 supercase, N_62 supercase |
| N_80 | 08-31 | — | information | Lia starts school on 14 Sept; family settled | S: SN_1→achieved |

**Label targets:** subcase ~30 · same_level ~14 · supercase 12 · depends_on ~34 · references ~10 ·
resolves ~8 · revises 7 · contradicts 3.

## Probes

| id | Question | Target | expected_any | forbidden_any | from | Designed to defeat |
|---|---|---|---|---|---|---|
| p1 | Which neighbourhood is the family living in? | SN_7 | "Haidhausen" | "Pasing" | 28 | anti-semantic |
| p2 | When does Daniel start at Brennwerk? | SN_2 | "15 July" | "1 July" | 45 | anti-recency (N_2 is the canonical statement) |
| p3 | What is the rent cap? | SN_5 | "2,600" | "2,300" | 27 | anti-semantic |
| p4 | Which bank handles the rent deposit? | SN_9 | "Sparkasse" | "N26" | 32 | anti-semantic |
| p5 | What must be done before opening the Sparkasse account? | SN_9 | "Anmeldung", "Wohnungsgeberbestätigung" | — | 33 | anti-hierarchical (cross-thread chain) |
| p6 | Which school will Lia attend, and how does she start? | SN_11 | "Kirchenstraße", "Übergangsklasse", "transition class" | "Bavarian International School" | 56 | anti-recency |
| p7 | Is Sofia co-insured on Daniel's TK plan? | SN_12 | "own employer", "separately" | "family co-insured" | 41 | anti-semantic |
| p8 | Are they shipping the car? | SN_15 | "sell", "sold" | "ship the car" | 62 | — |
| p9 | Can Sofia work in Germany? | SN_4 | "yes", "family reunification" | "needs her own permit" | 23 | anti-recency (answered at N_23, needed at N_39) |
| p10 | How are household goods being shipped? | SN_14 | "shared container" | "20 ft container" | 62 | anti-semantic |
