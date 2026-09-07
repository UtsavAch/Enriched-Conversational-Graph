# Enriching the Conversational Graph — Phase 1 & Phase 2 Report

## Schema Design and Extraction Pipeline Design, prepared ahead of Phase 3 (Prototype Validation)

---

Utsav Acharya  
Supervisor: Prof. Davide Carneiro

**The practical implementations will be available here:**   
[https://github.com/UtsavAch/Enriched-Conversational-Graph](https://github.com/UtsavAch/Enriched-Conversational-Graph)

## **Processing Pipeline diagram:**

[https://canva.link/abpn4zlqrtbdy5o](https://canva.link/abpn4zlqrtbdy5o)

## 

## 

## 

## 

## 

## 

## 

## 

## 

## 

## 

# Summary

This report documents the schema (Phase 1\) and extraction-pipeline design (Phase 2\) for extending the graph-augmented conversational memory architecture described in Oliveira thesis (2026) beyond its current subcase / supercase / same\_level relation set. It exists so that Phase 1 and Phase 2 can be reviewed and closed out as a unit before any implementation work (Phase 3\) begins.

Two things motivate this work. First, the thesis's own evaluation found the existing graph to be **structurally thin** on the LoCoMo benchmark: supercase fired in only 4 of 3,954 edges, because LoCoMo is a bank of independent evaluation probes rather than a developing line of inquiry, and no non-zero graph-slot fraction improved recall on that benchmark. Second, the scholarship explicitly calls for a memory layer that also represents entities, goals, decisions, constraints, and open questions categories the current schema does not have.

This document is **not** a re-run of the thesis's evaluation, and it is not a claim that the enriched schema will outperform the baseline. It is a design specification: what the new nodes, edges, and fields are, how they are produced, what they cost per turn, and what remains undecided going into Phase 3\. Where something is still an open question, it is left as an open question rather than resolved by assumption. Phase 3's manual validation is the point at which several of these are meant to be settled empirically.

---

## **AI Usage Disclosure**

*Claude and Chat GPT are used as research assistants throughout the work. They are used in an iterative manner, providing suggestions, alternative ideas, and feedback while the author makes the final decisions and reviews the results. The AI tools are treated as supporting helpers rather than decision-makers, and are also used to improve the organization, structure, and clarity of the report.*

## ---

## 

## 

## 

## 

## 

# Contents

1. Background and Scope  
2. Conversation Input Format  
3. Phase 1 — Schema Design  
   * 3.1 Interaction nodes  
     1. 3.1.1 Cited answer  
   * 3.2 Entities  
   * 3.3 State nodes  
     1. Status values by type  
   * 3.4 Edges  
   * 3.5 Epistemic status  
   * 3.6 Compression/Summary representation  
4. Worked Example  
5. Phase 2 — Extraction Pipeline Design  
   * 5.1 LLM Calls in the Pipeline  
   * 5.2 Call Design Decision: Multi-call vs Combined  
   * 5.3 Cost Estimate  
   * 5.4 Candidate Selection Strategy (Retrieval-Side Extension)  
   * 5.5 Context Assembly Procedure  
   * 5.6 Prompts  
   * 5.7 Answer Generation and Memory Update Procedure  
   * 5.8 Extraction Pipeline Diagram  
6. Open Questions and Risks Carried Into Phase 3  
7. Phase 3 Readiness Checklist  
8. References

---

## 

## 

# 1\. Background and Scope

The baseline architecture (Oliveira, 2026\) represents each human–model interaction as a node in a persistent graph, embeds it, and connects it to prior nodes through one of three typed hierarchical relations: subcase, supercase, same\_level or no\_relation, in which case no edge is stored. Context for a new turn is assembled under a fixed item budget T \= N\_recent \+ K\_historical, split between a recency layer and a historical layer; the historical layer is itself filled by semantic retrieval plus a bounded graph-expansion step from the top semantic entry points. This pipeline, the bounded-per-turn-cost constraint, and the two-phase (context-construction / memory-update) structure are all **inherited unchanged** from the thesis and are treated as the baseline for everything below.

What this phase adds, per the task list, is:

* Richer **interaction-node attributes**: named entities, speech act, epistemic status, citations.  
* **Pragmatic edges** between interactions (revises, contradicts, resolves, depends\_on, references), alongside the existing hierarchical edges.  
* **Named entities as nodes**: The named entities treated as nodes on their own.  
* **First-class state nodes**: Goal, Decision, Constraint, OpenQuestion, that interactions can link to, in addition to linking to each other.  
* **Interaction-State edges**: Edges like supports, contradicts, constrained\_by, resolves, that link state nodes with interaction nodes.  
* A **compression rule** so the context builder can inject a full interaction, a summary, or a state/entity reference, depending on the remaining budget.

None of this changes the granularity of the base graph (still one node per interaction), the retrieval formula, or the bounded-cost requirement. It is an enrichment of what a node can carry and connect to, not a redesign of the retrieval mechanism, although Section (5.4) proposes a reframing of how the new signals feed that mechanism.

---

## 

# 

# 

# 2\. Conversation Input Format

Input conversations are supplied as a list of dated interactions, each containing two speaker turns, one being an assistant. There will be hundreds or thousands of  turns in the real conversation.

\[  
{  
  "id": "I\_1",  
  "date": "2026-03-02",  
  "turns": \[  
    {"speaker": "researcher", "text": "...question/query..."},  
    {"speaker": "assistant", "text": "...answer/response..."}  
  \]  
},  
…  
\]

*Note: The examples throughout this report assume a conversation between a researcher and a chat assistant, but nothing in the schema is domain-specific.*

---

## 

## 

## 

## 

## 

## 

## 

## 

## 

# 3\. Phase 1 — Schema Design

*(Corresponds to workplan tasks 1.1–1.4.)*

## 3.1 Interaction Nodes

An interaction node is still one question/answer pair plus its embedding, extended with the attributes below.

| Field | Datatype | Meaning | Produced by |
| :---- | :---- | :---- | :---- |
| question | string | The user's turn. | N/A — user input, not model-produced |
| answer | string | The assistant's turn. | Answer-generation call |
| embedding | vector\<float\> | Fixed-dimension embedding of (question \+ answer), used for semantic retrieval. | Embedding model |
| named\_entities | array\<string\> | Entity IDs (E\_n) mentioned in this interaction. | Entity-extraction call (W1) |
| speech\_act | enum\<string\>: factual\_question, clarification\_request, decision, suggestion, feedback, correction, follow\_up, agreement, disagreement, information, request | The discourse function of the turn. | Speech-act classification call (W1) |
| epistemic\_status | enum\<string\>: open, resolved, superseded, contested | Whether this interaction's conclusion currently stands, is pending, has been overtaken, or is disputed. See (3.5). | Written as a side effect of pragmatic-edge classification (3.5), not by an independent call |
| epistemic\_history | array\<\[string, string, string\]\> | Append-only log of \[source\_node\_id, edge\_label, new\_status\] triples, one per status change. Kept for traceability during manual validation (Phase 3.1). | Appended programmatically whenever epistemic\_status changes |
| recurrence\_count | integer ≥ 0 | Structural, edge-derived,  in-degree from later node’s edges pointing back at this one. | Computed programmatically from the edge graph, not model-produced |
| retrieval\_count | integer ≥ 0 | Access-based incremented each time this node is actually pulled into context to answer a later query, whether or not that retrieval produced a formal edge. | Incremented by the retrieval pipeline at read time, not model-produced |
| summary | string | Short paraphrase of the interaction, for medium-compression context injection. | Summary-generation call (W5) |
| reference | string | A short, self-contained fallback phrase for the lowest compression tier, used only when a node has no linked entity or state node to point to instead. Most nodes never show this text. See (3.6) for what actually renders at this tier. | Summary-generation call, same call as summary, returned as a second field (W5) |
| citations | array\<string\> | Interaction node IDs (N\_n) that the answer-generation call actually cited when producing this turn's answer. | Answer-generation call (R2) |
| edges.hierarchical | array\<\[string, enum\]\> | \[target\_id, label\] pairs, label ∈ {subcase, supercase, same\_level}. | Hierarchical edge-classification call (W2) |
| edges.pragmatic | array\<\[string, enum\]\> | \[target\_id, label\] pairs, label ∈ {revises, contradicts, resolves, depends\_on, references}. target\_id is another interaction node (N\_n). | Pragmatic edge-classification call (W3) |
| state\_node\_links.creates | array\<string\> | State node IDs (SN\_n) newly created by this interaction. | State-node extraction/merge call (W4) |
| state\_node\_links.updates | array\<\[string, string\]\> | \[state\_node\_id, new\_status\] pairs. State nodes whose lifecycle status this interaction changed, and what it changed to. | State-node extraction/merge call (W4) |
| state\_node\_links.relates | array\<\[string, enum\]\> | \[state\_node\_id, relation\] pairs, relation ∈ {supports, contradicts, constrained\_by, resolves} (3.4). Most relations don't change the target's status. resolves is the one exception: It can change the target’s status to resolved (3.4) | State-node extraction/merge call (W4) |

### **3.1.1 Cited answer**

A cited answer points to the exact earlier node(s) it depends on, e.g. *"Yes, still all five \[N\_2\], no changes \- the report's ready for review."* This is a cheap, factual check rather than a subjective quality judgement:

* It **makes an answer checkable**, not just readable, a reviewer can jump to the cited node and confirm the claim in seconds, rather than re-deriving correctness from scratch.  
* It turns to "is this a good answer?" into "does every citation actually appear in what was retrieved for this turn?", **a set-membership check, not a judgement call**.  
* It **catches a failure that quality scoring may miss**: a topically plausible, even factually true sentence that was not derived from the retrieved content. Only checking the citation against the retrieved set reveals this gap.  
* It **is cheap**, no extra model call, just membership-checking each cited ID against the node's retrieval set,  so it can run on every answer in a long conversation.  
* It also **gives the graph view something concrete to display**: which specific nodes a given answer drew from, rather than an undifferentiated "these nodes are connected." Might be beneficial for (Phase 5\) graph view.

## 3.2 Entities

Entities are stored as separate nodes rather than inline strings, so that graph traversal treats them as first-class and the same entity can be referenced from multiple interaction nodes. They can also be used as retrieval entry points (5.4).

| Field | Datatype | Meaning | Produced by |
| :---- | :---- | :---- | :---- |
| type | enum\<string\>: person, organization, system, measurement, tool, location, event, document | Category of the entity. *Provisional, see note below.* | Entity-extraction call (W1) |
| name | string | The entity's name, as extracted. | Entity-extraction call (W1) |
| mentioned\_in | array\<string\> | Interaction node IDs (N\_n) that mention this entity. | Set at creation by the entity-extraction call (W1); appended programmatically on each later mention, not regenerated |

***Note**: the entity-type list above reflects the domain used in Example (4), which is a research conversation. Tool and event are domain-specific additions to the more general person / organization / system / location / document set. A deployment in a different domain should revisit this list rather than assume it is fixed.*

## 3.3 State Nodes

State nodes are a second layer of nodes that interactions can attach to, distinct from relating interactions to each other. Four types are defined:

* **Goal**:  an objective stated by the user (e.g. *"extend the graph schema to represent entities, goals, decisions, constraints, and open questions"*).  
* **Decision**: a choice made during the conversation (e.g. *"adopt five pragmatic edge types: revises, contradicts, resolves, depends\_on, references"*).  
* **Constraint**: a requirement or restriction that must be satisfied or checked (e.g. *"per-turn extraction cost must stay bound to a small number of async calls"*).  
* **Open Question**: a question raised but not yet answered (e.g. *"does classification order between W2 and W3 matter, or can they run fully in parallel?"*).

| Field | Datatype | Meaning | Produced by |
| :---- | :---- | :---- | :---- |
| type | enum\<string\>: goal, decision, constraint, open\_question | Which state-node category this is. | State-node extraction/merge call (W4) |
| label | string | Short summary of this state node. | State-node extraction/merge call (W4) |
| embedding | vector\<float\> | Embedding of label, for retrieval. | Embedding model |
| creation\_turn | string | Interaction node ID (N\_n) where this state node was first created. | State-node extraction/merge call (W4) |
| status | enum\<string\>:  values depend on type, see below (3.3.1) | Current lifecycle state. | State-node extraction/merge call (W4) |
| Last\_updated\_turn | {"updates": array\<\[string, string\]\>, "relates": array\<\[string, string\]\>} | Reverse index of state\_node\_links.updates and .relates (3.1), split by which one caused the touch. A status-changing update lands in .updates as \[interaction\_id, new\_status\]; a typed relation lands in .relates as \[interaction\_id, relation\]. *A resolves turn produces one entry in each, since it writes to both state\_node\_links.updates and .relates on the interaction side (3.4.2)*. | Set to {"updates": \[\], "relates": \[\]} at creation; appended to programmatically, mirroring state\_node\_links.updates/.relates on the interaction node that touched this one |

### 3.3.1 Status values by type

This tracks the lifecycle stage for a state node itself (a goal, decision, constraint, or open question), and each of the four types has its own small set of allowed values because "done" means something different for each.

| Type | Allowed status values | Terminal values |
| :---- | :---- | :---- |
| goal | active, achieved, abandoned | achieved, abandoned |
| decision | active, revised, reverted | reverted |
| constraint | active, lifted, revised | lifted |
| open\_question | open, resolved | resolved |

**What each value means:**

| Value | Applies to | Meaning |
| :---- | :---- | :---- |
| active | goal, decision, constraint | Currently in force / still being pursued. The default, non-terminal starting state for all three. |
| achieved | goal | The objective was met. Terminal. |
| abandoned | goal | The objective was given up on without being met. Terminal. |
| revised (decision) | decision | The decision's specifics changed but it still stands in some form. Not Terminal. Can be revised more than once. |
| reverted | decision | The decision was undone. Terminal. |
| lifted | constraint | The requirement no longer applies. Terminal |
| revised (constraint) | constraint | The constraint's terms changed but it's still in force. Not Terminal. Can be revised more than once.  |
| open | open\_question | Not yet answered. The starting state. |
| resolved | open\_question | Answered. Terminal. Also the one status value directly tied to a typed edge, see the resolves relation (3.4). |

**What "terminal" actually does, mechanically:** 

It's not just a label. apply\_w4 (5.7) checks sn.status IN TERMINAL\_STATUSES\[sn.type\] before allowing any update, and rejects the update if the node is already in a terminal state. LLM can *propose* it (W4 has no way to stop the model from trying), but the applier refuses to write it.

## 3.4 Edges

### 3.4.1 Interaction Node edges

Hierarchical and pragmatic edges are **two independent axes**, not two flavors of one edge type. They come from two separate classification calls: W2 for hierarchical, W3 for pragmatic (5.6), run over the *same* candidate set (5.5) for the same (source, target) pair. Nothing links the two calls' outputs together, so for any given pair of interaction nodes, the actual relationship can be:

* **hierarchical only** — e.g. the new turn is a subcase of an earlier one, with no pragmatic relationship.  
* **pragmatic only** — e.g. the new turn revises an earlier decision, without the two turns being topically nested in either direction.  
* **both** — e.g. a turn could plausibly be both a subcase of an earlier topic *and* depends\_on it, since one axis is about topic structure and the other is about discourse function; nothing in the schema or the two prompts prevents this.  
* **neither** — both calls return no\_relation for that pair, and (per the note below) nothing is stored at all.

This is a direct consequence of how the schema is defined (3.1): edges.hierarchical and edges.pragmatic are two separate arrays on the node, each populated independently by its own call, not one merged edges list with a single label per target. no\_relation is each call's explicit "nothing on this axis" answer, not a stored value. If W2 returns no\_relation for a candidate, no hierarchical edge is written for that pair; independently, if W3 returns no\_relation, no pragmatic edge is written. A pair with no\_relation on both axes has no edge between it at all.

#### Hierarchical edges

| Edge | Meaning | Strength | Justification |
| :---- | :---- | :---- | :---- |
| subcase | The source is more specific than the target, the source narrows or deepens the target's topic. | 1.0 | Strongest signal: a specialisation is the most directly useful expansion target. |
| supercase | The source is more general than the target, the source broadens or abstracts the target's topic. | 0.8 | Useful, but a generalisation is slightly less immediately actionable than a specific detail. |
| same\_level | Target and source address parallel topics at similar specificity. | 0.6 | Related but not as load-bearing as a direct narrowing or broadening. |
| no\_relation | No meaningful relation. | — | Not stored as an edge. |

#### Pragmatic edges

| Edge | Meaning | Strength | Justification |
| :---- | :---- | :---- | :---- |
| revises | Source corrects or invalidates the target. | 1.0 *(proposed)* | Omitting this risks presenting retracted information as current,  the costliest possible omission. |
| contradicts | Source conflicts with the target, without confirming which one is right. | 0.9 *(proposed)* | Surfaces a genuine unresolved tension the reader needs to see. |
| resolves | Source answers a question the target left open. | 0.85 *(proposed)* | Directly closes a tracked open thread; keeps open\_question status accurate. Solves the nodes with open status. |
| depends\_on | Source presupposes a decision, constraint, or fact established at the target. | 0.7 *(proposed)* | Necessary background, but less urgent than a correction or resolution. |
| references | Source explicitly points back to the target without correcting, resolving, or depending on it. | 0.5 *(proposed)* | Weakest pragmatic signal, acknowledges a connection without carrying much load. |
| no\_relation | No meaningful relation. | — | Not stored as an edge. |

***Note**: The five pragmatic strength values are proposed, not empirically fit. They encode the same working assumption the Oliveira thesis used for the hierarchical scores (more corrective/resolving relations weigh more), and should be treated as a starting point for the parameter sweep in Phase 4, not a fixed constant.*

### 3.4.2 Interaction-State edges

A third, independent axis, added per workplan Task 1.3. Unlike hierarchical and pragmatic edges (both interaction-to-interaction), this one connects an (interaction to a **state node)**. It answers a different question than either of the two tables above: not "how does this turn relate to an earlier turn" but "how does this turn relate to a goal, decision, constraint, or open question currently being tracked."

*(Note: The edge strength here is in case we use them while candidate retrieval. These are proposed, not empirically fit)*

| Relation | Meaning | Changes target's status? | Strength | Justification |
| :---- | :---- | :---- | :---- | :---- |
| contradicts | The interaction conflicts with the target without revising or lifting it. | No | 0.9 *(proposed)* | Mirrors pragmatic contradicts. A live tension is worth considering. |
| resolves | The interaction answers or closes a target open\_question. | **Yes** — the one relation that is also always a status change. Recorded in **both** state\_node\_links.updates and .relates. See (3.1) and the worked example (4). | 0.85 *(proposed)* | Mirrors pragmatic resolves exactly. |
| constrained\_by | The interaction's content is bound or limited by the target. | No | 0.7 *(proposed)* | Analogous to pragmatic depends\_on (0.7). Both mean "presupposes/bound by something established" |
| supports | The interaction reinforces the target without changing it. Evidence or justification for a goal / decision / constraint currently in force. | No | 0.6 *(proposed)* | Between references (0.5, weakest) and depends\_on/constrained\_by (0.7), active reinforcement is worth more than a bare callback, but it changes nothing, so it shouldn't outrank relations that do |
| no\_relation | No meaningful relation. | \_ | \_ | Not stored as an edge. |

## 3.5 Epistemic Status

epistemic\_status is **derived** from pragmatic edges rather than assigned independently: it only changes when a later interaction is classified as revises, resolves, or contradicts a prior one.

**Write-time vs. read-time**

 Two implementations were considered:

* **(a) Read-time**: derive status by walking the graph on every retrieval.  
* **(b) Write-time (adopted):** the later node, once its pragmatic edges are classified, writes the status update back onto the earlier (target) node.

(b) is adopted for consistency with the write-time pattern already used elsewhere in the schema (recurrence\_count, state-node status). Also better since we don’t need to re-read the graph again.

**Edge → status effect on the target node**

| Edge classified | Effect on target's epistemic\_status |
| :---- | :---- |
| revises | → superseded |
| resolves | → resolved |
| contradicts | → contested (new status, added to cover unconfirmed conflicts that open/resolved/superseded don't) |
| depends\_on | No change |
| references | No change |

**State-dependent transitions**

* The effect also depends on the target's current status: a resolves edge arriving on an already-contested node clears the contest (→ resolved).   
* A revises edge always wins regardless of current status (→ superseded).   
* superseded is treated as effectively terminal, further resolves/contradicts edges are no-ops against it, though still logged to epistemic\_history for provenance.   
* resolved is intentionally **not** locked, since a resolved conclusion can later be revised if shown wrong.

| Current status | revises arrives | resolves arrives | contradicts arrives |
| :---- | :---- | :---- | :---- |
| open | → superseded | → resolved | → contested |
| resolved | → superseded | → resolved (no-op, already there) | → contested |
| contested | → superseded | → resolved (clears the contest) | → contested (no-op, already there) |
| superseded | → superseded (no-op, but still "wins") | blocked, stays superseded | blocked, stays superseded |

***(Note**: depends\_on and references never change status regardless of current state. Already covered by the Edge → status table above.)*

**Default status on creation** 

Depends on speech\_act, not a single constant. A node defaults to open only if its speech act inherently leaves something pending; everything else defaults to resolved, since a decision, a correction, a feedback, or an agreement is a complete statement the moment it's made. 

| Default | Speech acts |
| :---- | :---- |
| open | factual\_question, clarification\_request |
| resolved | decision, information, agreement, request, correction, follow\_up, suggestion, feedback, disagreement |

This is an **engineering default, not an established fact**. It is the simplest rule consistent with the worked example, not something derived from data. Phase 3's manual validation should stress-test the edge cases. If validation shows a speech act needs a different default, we need to change this table.

**Where this is actually set:** speech\_act is W1's own output (5.1, item 3), so the default is assigned inside apply\_w1 (5.7) at the same time speech\_act is written. epistemic\_history starts as an empty array at creation; it only gains entries from actual pragmatic-edge-driven changes afterward (5.8), not from this initial default assignment. The default is a starting value, not a logged event. *(**Note**: Default is set at speech act classification (W1), update happens after pragmatic edge classification (W3) (5.7, 5.8))*

**Is node with epistemic status superseded relevant?**

superseded does not mean deleted or irrelevant. It means a later interaction has explicitly corrected this node's conclusion, so that conclusion should no longer be treated as current,  the node may still hold a durable fact, or record what was believed at the time. It answers one narrow question: *is this node's conclusion still trustworthy?,* not whether the node is worth retrieving.

**Limitation**

Status is tracked at the whole-node level, not per claim. A node that bundles a durable fact with a later-revised interpretation gets both marked superseded together, even though only the interpretation was wrong. Claim-level status tracking would fix this but is out of scope here, deferred as future work (6).

## 3.6 Compression / Summary Representation

*(Task 1.4.)*

There are three tiers, ordered from most to least detail. Each is described below by what it means, how it is constructed, and when it is used. The mechanics live in (5.5) (Context Assembly Procedure). This section defines what each tier is; (5.5) shows how they get selected and rendered.

**Tier 1: full.** The complete question and answer text, verbatim. This is what every node gets in the recency layer unconditionally, and what every historical-layer node gets if the remaining token budget allows it. Constructed by nothing — it is simply the node's own question/answer fields, already stored. No compression, no information loss.

**Tier 2: summary.** A one-sentence paraphrase, under 20 words, naming the specific fact, decision, or question the turn established, not a generic description (5.6, W5's prompt). Constructed once, at write time, by the W5 call, and stored on the node (node.summary). Fixed for the node's lifetime. It does not change if a later turn revises or resolves something this node said, the same way a full-tier rendering of an old node doesn't change either. A summary is a paraphrase of this turn's own content.

**Tier 3: reference.** The lowest tier, meant to answer "what was this turn about" in the fewest possible tokens. Two different things can produce this tier's text, in a fixed priority order:

1. If the node created or updated a state node, the reference is a live pointer into the state-node registry, e.g. *"\[decision\] Adopt five pragmatic edge types"* or *"\[constraint, revised\] Per-turn extraction cost bounded"*, built by reading that state node's current type/label/status at render time, not by copying them once. This is the "entity/decision reference" Task 1.4 and Task 4.1 both name explicitly. Priority when a node has more than one kind of link: creates first (a new state node is usually the most newsworthy thing about the turn), then updates (a status change on an existing one), then entity mentions, since those are the least specific of the three.  
2. If the node has no state-node link but does have named entities, the reference names up to two of them, e.g. *"\[entities\] Claude, MySQL"*.  
3. If neither, the reference falls back to node.reference, the free-text phrase W5 generated, stored on the node. This is the only case where anything is read from a stored field for this tier; the common case (state-node or entity link present) is computed fresh every time, from data the node already carries as edges/links.

**Why the state/entity case is computed live, not stored.** 

A state node's label and status can change after the interaction node that created it is long since committed (a decision gets revised, a constraint gets lifted). A reference frozen at write time would keep showing the state node's original label forever.Computing it live costs one dictionary lookup, not an LLM call, so there is no real performance argument for persisting it either. See render\_reference in (5.5).

**Selection rule**

choose\_compression\_tier (5.5) tries full, then summary, then reference, in that order, against the remaining token budget at the point each historical-layer node is being placed, greedy first-fit, not a global optimization over the whole layer. This is a pure budget rule today. *(**Note**: it does not yet consider a node's epistemic\_status or recurrence\_count when deciding how hard to compress it (e.g. compressing a superseded node harder regardless of budget, or protecting a high-recurrence\_count node from compression longer). That might be the next refinement in the future.)*

**Note**: "budget" here is a token budget, not the fixed item-count budget (T \= 45\) Oliveira thesis original system used. This is because compressed items can pack more densely into the same space than a fixed slot count would allow.

---

# 4\. Worked Example

It is generated with **Claude**, given the conversation structure as input and the desired output structure as a target. It has ten turns, kept deliberately compact, but is constructed to exercise every part of the schema in one place. Nothing here is representative of real conversation *length*, a real conversation may have hundreds or thousands of turns. It only consists of the range of things one graph needs to be able to represent.

## Context

A researcher and Claude are working through the schema and pipeline design for Phase 1 and 2 of this project. A goal and a cost constraint are set up front. Five new pragmatic edge types are proposed and adopted, and two parallel questions follow from that: one about call ordering that is left open, one about default status handling that is settled immediately. A design pushback briefly puts the five-edge-type decision in doubt before being defended and confirmed. Months later, testing resolves the ordering question, which in turn forces a small revision to the default-status rule. A final check-in, right before a supervisor meeting, confirms the plan is still intact.

## Input

*\[*   
*{ "id": "I\_1", "date": "2026-01-15", "turns": \[*  
*{"speaker": "researcher", "text": "For Phase 1 and 2 of the INESC TEC graph memory work, our goal is to extend the schema to represent entities, goals, decisions, constraints, and open questions \- and whatever we add, per-turn extraction cost needs to stay bounded to just a few extra async calls."},*  
*{"speaker": "assistant", "text": "Got it \- I'll track both: the goal is the enriched schema covering entities and the four state-node types, and the constraint is keeping added extraction cost to a small, bounded number of async calls per turn."} \] },*  
*{ "id": "I\_2", "date": "2026-01-20", "turns": \[*  
*{"speaker": "researcher", "text": "What relation types should we add beyond subcase, supercase, and same\_level?"},*  
*{"speaker": "assistant", "text": "I'd propose five pragmatic edges \- revises, contradicts, resolves, depends\_on, and references \- covering correction, disagreement, resolution, prerequisite, and simple callback, while keeping the number of extra calls Claude makes each turn bounded \[N\_1\]."} \] },*  
*{ "id": "I\_3", "date": "2026-02-02", "turns": \[*  
*{"speaker": "researcher", "text": "When you said pragmatic edges get their own classification call \- does that mean W2 and W3 always run fully independently in parallel, or could the order actually matter?"},*  
*{"speaker": "assistant", "text": "Good question to pin down \- that's not settled yet. I'd flag it as an open question: does W3 need W2's hierarchical labels first, or can they run fully in parallel? We won't know for certain until we test it end to end."} \] },*  
*{ "id": "I\_4", "date": "2026-02-04", "turns": \[*  
*{"speaker": "researcher", "text": "Separately, what should the default epistemic\_status be when a new node is created?"},*  
*{"speaker": "assistant", "text": "I'd default to open only for factual\_question and clarification\_request, and resolved for every other speech act."} \] },*  
*{ "id": "I\_5", "date": "2026-02-10", "turns": \[*  
*{"speaker": "researcher", "text": "Can you summarize the schema decisions in the Phase 1-2 report so far?"},*  
*{"speaker": "assistant", "text": "Sure \- we're adding five pragmatic edge types while staying within the bounded per-turn cost constraint \[N\_1\], defaulting new nodes to resolved unless they're a question, and we still haven't settled whether W2 and W3 need a fixed order."} \] },*  
*{ "id": "I\_6", "date": "2026-03-01", "turns": \[*  
*{"speaker": "researcher", "text": "Actually, I think five pragmatic types is overengineered \- let's just keep revises and resolves, the rest adds complexity without proven benefit."},*  
*{"speaker": "assistant", "text": "Worth taking seriously \- I'll flag this as a direct challenge to the five-edge-type decision until we think it through."} \] },*  
*{ "id": "I\_7", "date": "2026-03-04", "turns": \[*  
*{"speaker": "researcher", "text": "Have you thought it through?"},*  
*{"speaker": "assistant", "text": "Yes \- each of the five maps to something the thesis needs distinctly \[N\_6\]: contradicts surface disputes explicitly instead of hiding them in a plain edge, and depends\_on lets retrieval find prerequisite context. I'd keep all five, though the strength values should stay provisional until Phase 4's parameter sweep."} \] },*  
*{ "id": "I\_8", "date": "2026-04-12", "turns": \[*  
*{"speaker": "researcher", "text": "We tested it \- does the W2/W3 ordering actually matter?"},*  
*{"speaker": "assistant", "text": "No, it doesn't \- we checked: both calls read the same candidate list and neither touches the other's output, so there's no dependency between them. They run fully in parallel. Resolved."} \] },*  
*{ "id": "I\_9", "date": "2026-04-15", "turns": \[*  
*{"speaker": "researcher", "text": "Separately, should we simplify the default epistemic\_status rule too?"},*  
*{"speaker": "assistant", "text": "Yes \- simplify further: default resolved unless the speech act is a question type, no separate handling for edge cases."} \] },*  
*{ "id": "I\_10", "date": "2026-07-10", "turns": \[*  
*{"speaker": "researcher", "text": "Right before the meeting with my thesis advisor \- are we still keeping all five pragmatic edge types?"},*  
*{"speaker": "assistant", "text": "Yes, still all five \[N\_2\], no changes \- the report's ready for review."} \] }*  
*\]*

## Output

Note on retrieval\_count: it is computed exactly from the edges in this static example, so it equals recurrence\_count below,  illustrative only. In a real run the two diverge.

epistemic\_history is populated for every node, including ones whose status never changed after creation (a single \["\<id\>", "creation", "\<status\>"\] entry). This makes the field's always-present, append-only nature explicit rather than leaving it to be inferred.

*{ "interaction\_nodes": {*  
*"N\_1": { "question": "For Phase 1 and 2 of the INESC TEC graph memory work, our goal is to extend the schema to represent entities, goals, decisions, constraints, and open questions \- and whatever we add, per-turn extraction cost needs to stay bounded to just a few extra async calls.",*  
*"answer": "Got it \- I'll track both: the goal is the enriched schema covering entities and the four state-node types, and the constraint is keeping added extraction cost to a small, bounded number of async calls per turn.",*  
*"embedding": "\<vector: N\_1 question+answer\>",*  
*"named\_entities": \["E\_1", "E\_6"\],*  
*"citations": \[\],*  
*"speech\_act": "request",*  
*"epistemic\_status": "resolved",*  
*"epistemic\_history": \[\["N\_1", "creation", "resolved"\]\],*  
*"recurrence\_count": 1,*  
*"retrieval\_count": 1,*  
*"summary": "Sets the goal (enriched schema) and the constraint (bounded per-turn extraction cost) for Phase 1-2.",*  
*"reference": "Goal and cost constraint set",*  
*"edges": {"hierarchical": \[\], "pragmatic": \[\]},*  
*"state\_node\_links": {"creates": \["SN\_1", "SN\_2"\]} },*

*"N\_2": { "question": "What relation types should we add beyond subcase, supercase, and same\_level?",*  
*"answer": "I'd propose five pragmatic edges \- revises, contradicts, resolves, depends\_on, and references \- covering correction, disagreement, resolution, prerequisite, and simple callback, while keeping the number of extra calls Claude makes each turn bounded \[N\_1\].",*  
*"embedding": "\<vector: N\_2 question+answer\>",*  
*"named\_entities": \["E\_3"\],*  
*"citations": \["N\_1"\],*  
*"speech\_act": "decision",*  
*"epistemic\_status": "resolved",*  
*"epistemic\_history": \[\["N\_2", "creation", "resolved"\], \["N\_6", "contradicts", "contested"\], \["N\_7", "resolves", "resolved"\]\],*  
*"recurrence\_count": 5,*  
*"retrieval\_count": 5,*  
*"summary": "Five pragmatic edge types are proposed: revises, contradicts, resolves, depends\_on, references.",*  
*"reference": "Five pragmatic edge types adopted",*  
*"edges": {"hierarchical": \[\], "pragmatic": \[\["N\_1", "depends\_on"\]\]},*  
*"state\_node\_links": {"creates": \["SN\_3"\], "relates": \[\["SN\_2", "constrained\_by"\]\]} },*

*"N\_3": { "question": "When you said pragmatic edges get their own classification call \- does that mean W2 and W3 always run fully independently in parallel, or could the order actually matter?", "answer": "Good question to pin down \- that's not settled yet. I'd flag it as an open question: does W3 need W2's hierarchical labels first, or can they run fully in parallel? We won't know for certain until we test it end to end.",*  
*"embedding": "\<vector: N\_3 question+answer\>",*  
*"named\_entities": \[\],*  
*"citations": \[\],*  
*"speech\_act": "clarification\_request",*  
*"epistemic\_status": "resolved",*  
*"epistemic\_history": \[\["N\_3", "creation", "open"\], \["N\_8", "resolves", "resolved"\]\],*  
*"recurrence\_count": 2,*  
*"retrieval\_count": 2,*  
*"summary": "Opens the question of whether W2/W3 call ordering matters or can run in parallel.", "reference": "W2/W3 ordering question opened",*  
*"edges": {"hierarchical": \[\["N\_2", "subcase"\]\], "pragmatic": \[\]},*  
*"state\_node\_links": {"creates": \["SN\_4"\]} },*

*"N\_4": { "question": "Separately, what should the default epistemic\_status be when a new node is created?",*  
*"answer": "I'd default to open only for factual\_question and clarification\_request, and resolved for every other speech act.",*  
*"embedding": "\<vector: N\_4 question+answer\>",*  
*"named\_entities": \[\],*  
*"citations": \[\],*  
*"speech\_act": "decision",*  
*"epistemic\_status": "superseded",*  
*"epistemic\_history": \[\["N\_4", "creation", "resolved"\], \["N\_9", "revises", "superseded"\]\],*  
*"recurrence\_count": 2,*  
*"retrieval\_count": 2,*  
*"summary": "Sets the default epistemic\_status rule: open for questions, resolved otherwise.",*  
*"reference": "Default epistemic\_status rule set",*  
*"edges": {"hierarchical": \[\["N\_3", "same\_level"\]\], "pragmatic": \[\]},*  
*"state\_node\_links": {"creates": \["SN\_5"\]} },*

*"N\_5": { "question": "Can you summarize the schema decisions in the Phase 1-2 report so far?",*  
*"answer": "Sure \- we're adding five pragmatic edge types while staying within the bounded per-turn cost constraint \[N\_1\], defaulting new nodes to resolved unless they're a question, and we still haven't settled whether W2 and W3 need a fixed order.",*  
*"embedding": "\<vector: N\_5 question+answer\>",*  
*"named\_entities": \["E\_4"\],*  
*"citations": \["N\_1"\],*  
*"speech\_act": "information",*  
*"epistemic\_status": "resolved",*  
*"epistemic\_history": \[\["N\_5", "creation", "resolved"\]\],*  
*"recurrence\_count": 0,*  
*"retrieval\_count": 0,*  
*"summary": "Summarizes the schema decisions so far: five edge types, default status rule, ordering still open.",*  
*"reference": "Schema decisions summarized",*  
*"edges": {"hierarchical": \[\["N\_2", "supercase"\], \["N\_4", "supercase"\]\], "pragmatic": \[\]},*  
*"state\_node\_links": {"relates": \[\["SN\_2", "supports"\]\]} },*

*"N\_6": { "question": "Actually, I think five pragmatic types is overengineered \- let's just keep revises and resolves, the rest adds complexity without proven benefit.",*  
*"answer": "Worth taking seriously \- I'll flag this as a direct challenge to the five-edge-type decision until we think it through.",*  
*"embedding": "\<vector: N\_6 question+answer\>",*  
*"named\_entities": \[\],*  
*"citations": \[\],*  
*"speech\_act": "disagreement",*  
*"epistemic\_status": "resolved",*  
*"epistemic\_history": \[\["N\_6", "creation", "resolved"\], \["N\_7", "resolves", "resolved"\]\],*  
*"recurrence\_count": 1,*  
*"retrieval\_count": 1,*  
*"summary": "Pushback: five pragmatic edge types may be overengineered relative to two.",*  
*"reference": "Five-edge-type decision disputed",*  
*"edges": {"hierarchical": \[\], "pragmatic": \[\["N\_2", "contradicts"\]\]},*  
*"state\_node\_links": {"relates": \[\["SN\_3", "contradicts"\]\]} },*

*"N\_7": { "question": "Have you thought it through?",*  
*"answer": "Yes \- each of the five maps to something the thesis needs distinctly \[N\_6\]: contradicts surface disputes explicitly instead of hiding them in a plain edge, and depends\_on lets retrieval find prerequisite context. I'd keep all five, though the strength values should stay provisional until Phase 4's parameter sweep.",*  
*"embedding": "\<vector: N\_7 question+answer\>",*  
*"named\_entities": \[\],*  
*"citations": \["N\_6"\],*  
*"speech\_act": "correction",*  
*"epistemic\_status": "resolved",*  
*"epistemic\_history": \[\["N\_7", "creation", "resolved"\]\],*  
*"recurrence\_count": 0,*  
*"retrieval\_count": 0,*  
*"summary": "Defends keeping all five pragmatic edge types, resolving the pushback.",*  
*"reference": "Five-edge-type dispute resolved",*  
*"edges": {"hierarchical": \[\], "pragmatic": \[\["N\_6", "resolves"\], \["N\_2", "resolves"\]\]},*  
*"state\_node\_links": {"relates": \[\["SN\_3", "supports"\]\]} },*

*"N\_8": { "question": "We tested it \- does the W2/W3 ordering actually matter?",*  
*"answer": "No, it doesn't \- we checked: both calls read the same candidate list and neither touches the other's output, so there's no dependency between them. They run fully in parallel. Resolved.",*  
*"embedding": "\<vector: N\_8 question+answer\>",*  
*"named\_entities": \[\],*  
*"citations": \[\],*  
*"speech\_act": "information",*  
*"epistemic\_status": "resolved",*  
*"epistemic\_history": \[\["N\_8", "creation", "resolved"\]\],*  
*"recurrence\_count": 0,*  
*"retrieval\_count": 0,*  
*"summary": "Testing confirms W2 and W3 have no dependency and run fully in parallel.",*  
*"reference": "W2/W3 confirmed independent, run in parallel",*  
*"edges": {"hierarchical": \[\], "pragmatic": \[\["N\_3", "resolves"\]\]},*  
*"state\_node\_links": {"updates": \[\["SN\_4", "resolved"\]\], "relates": \[\["SN\_4", "resolves"\]\]} },*

*"N\_9": { "question": "Separately, should we simplify the default epistemic\_status rule too?",*  
*"answer": "Yes \- simplify further: default resolved unless the speech act is a question type, no separate handling for edge cases.",*  
*"embedding": "\<vector: N\_9 question+answer\>",*  
*"named\_entities": \[\],*  
*"citations": \[\],*  
*"speech\_act": "decision",*  
*"epistemic\_status": "resolved",*  
*"epistemic\_history": \[\["N\_9", "creation", "resolved"\]\],*  
*"recurrence\_count": 0,*  
*"retrieval\_count": 0,*  
*"summary": "Simplifies the default epistemic\_status rule further, independent of the ordering question.",*  
*"reference": "Default status rule simplified",*  
*"edges": {"hierarchical": \[\], "pragmatic": \[\["N\_4", "revises"\]\]},*  
*"state\_node\_links": {"updates": \[\["SN\_5", "revised"\]\]} },*

*"N\_10": { "question": "Right before the meeting with my thesis advisor \- are we still keeping all five pragmatic edge types?",*  
*"answer": "Yes, still all five \[N\_2\], no changes \- the report's ready for review.",*  
*"embedding": "\<vector: N\_10 question+answer\>",*  
*"named\_entities": \["E\_2", "E\_5", "E\_4"\],*  
*"citations": \["N\_2"\],*  
*"speech\_act": "follow\_up",*  
*"epistemic\_status": "resolved",*  
*"epistemic\_history": \[\["N\_10", "creation", "resolved"\]\],*  
*"recurrence\_count": 0,*  
*"retrieval\_count": 0,*  
*"summary": "Confirms the five-edge-type decision still holds ahead of the supervisor meeting.",*  
*"reference": "Plan reconfirmed before review",*  
*"edges": {"hierarchical": \[\], "pragmatic": \[\["N\_2", "references"\]\]},*  
*"state\_node\_links": {} } },*

---

*"entities": {*  
*"E\_1": {"type": "organization", "name": "INESC TEC", "mentioned\_in": \["N\_1"\]},*  
*"E\_2": {"type": "person", "name": "the thesis advisor", "mentioned\_in": \["N\_10"\]},*  
*"E\_3": {"type": "system", "name": "Claude", "mentioned\_in": \["N\_2"\]},*  
*"E\_4": {"type": "document", "name": "the Phase 1-2 report", "mentioned\_in": \["N\_5", "N\_10"\]},*  
*"E\_5": {"type": "event", "name": "the supervisor meeting", "mentioned\_in": \["N\_10"\]},*  
*"E\_6": {"type": "measurement", "name": "per-turn extraction cost budget", "mentioned\_in": \["N\_1"\]} },*

---

*"state\_nodes": {*  
*"SN\_1": { "type": "goal",*  
*"label": "Extend the graph schema to represent entities, goals, decisions, constraints, and open questions",*  
*"embedding": "\<vector: SN\_1 label\>",*  
*"creation\_turn": "N\_1",*  
*"status": "active",*  
*"last\_updated\_turn": {"updates": \[\], "relates": \[\]} },*

*"SN\_2": { "type": "constraint",*  
*"label": "Per-turn extraction cost must stay bounded to a small number of async calls",*  
*"embedding": "\<vector: SN\_2 label\>",*  
*"creation\_turn": "N\_1",*  
*"status": "active",*  
*"last\_updated\_turn": {"updates": \[\], "relates": \[\["N\_2", "constrained\_by"\], \["N\_5", "supports"\]\]} },*

*"SN\_3": { "type": "decision",*  
*"label": "Adopt five pragmatic edge types: revises, contradicts, resolves, depends\_on, references",*  
*"embedding": "\<vector: SN\_3 label\>",*  
*"creation\_turn": "N\_2",*  
*"status": "active",*  
*"last\_updated\_turn": {"updates": \[\], "relates": \[\["N\_6", "contradicts"\], \["N\_7", "supports"\]\]} },*

*"SN\_4": { "type": "open\_question",*  
*"label": "Does classification order between W2 and W3 matter, or can they run fully in parallel?",*  
*"embedding": "\<vector: SN\_4 label\>",*  
*"creation\_turn": "N\_3",*  
*"status": "resolved",*  
*"last\_updated\_turn": {"updates": \[\["N\_8", "resolved"\]\], "relates": \[\["N\_8", "resolves"\]\]} },*

*"SN\_5": { "type": "decision",*  
*"label": "Default epistemic\_status: open only for factual\_question/clarification\_request, resolved otherwise",*  
*"embedding": "\<vector: SN\_5 label\>",*  
*"creation\_turn": "N\_4",*  
*"status": "revised",*  
*"last\_updated\_turn": {"updates": \[\["N\_9", "revised"\]\], "relates": \[\]} } } }*

The interactive version of this worked example is available on github. The link is on the first page.

---

# 5\. Phase 2 — Extraction Pipeline Design

*(Corresponds to workplan tasks 2.1–2.2.)*

## 5.1 LLM Calls in the Pipeline

The pipeline now involves the following model/embedding calls, in addition to the baseline answer-generation call:

1. Generate the answer to the user's question.  
2. Generate an embedding of the node: (question \+ answer).  
3. Classify the speech act.  
4. Extract named entities (question \+ answer).  
5. Classify hierarchical edges against candidate prior nodes.  
6. Classify pragmatic edges against candidate prior interactions.  
7. Set epistemic\_status as a side effect of (6) above. See (3.5).  
8. Generate the summary version of the node.  
9. Generate the reference version of the node,  the same call as (8); see (5.6) (W5).  
10. Retrieval. Comparing nodes by embedding similarity.  
11. Create or update state nodes, W4.  
12. LLM-as-judge: scores final answer quality for evaluation. Does not build the graph.

## 5.2 Call-Design Decision: Multi-Call vs. Combined

There are two ways to structure the extraction calls above: several small, task-scoped calls, or one combined call that returns everything at once. Both have trade-offs, and neither is obviously correct without measurement.

**Several separate calls**

Each call is scoped to one task (or a group of some tasks), which may extract better information per task, but this is unverified, not assumed. It also resends the same shared context (interaction, candidate nodes) per call, so total tokens processed is probably higher than a single combined call. Running calls sequentially would add their latencies; firing them concurrently avoids that, so wall-clock time does not have to grow with the number of calls, provided the async runtime genuinely parallelises them.

**One combined call** 

The prompt covers everything at once, so it is larger and the model must produce more per response: this could increase generation time, and quality on any one task might suffer from split attention across objectives (also unverified). It resends the shared context once instead of several times, so total tokens are likely lower.

**Comparison**

|  | Multi-call (W1–W5) | Combined |
| :---- | :---- | :---- |
| Extra calls/turn | 5 total (as of now) (5.6) | 1 |
| Token cost | Higher (context resent per call) | Lower (context sent once) |
| Wall-clock (if concurrent) | ≈ two sequential LLM calls on the critical path (5.3). the dependency graph in 5.8 gates W2/W3 on both EMBED and W1 finishing first | 1 call, larger generation |
| Per-task extraction quality | Likely better (task-scoped prompt):  **unverified** | Likely worse under split attention: **unverified** |
| Failure isolation | A bad pragmatic-edge call doesn't corrupt the entities call | One malformed JSON blob risks losing everything for the turn |

**Decision (provisional).** 

The multi-call design (W1–W5) is adopted as the default for writing Phase 2's prompts, on two grounds: task-scoped prompts are the safer default for quality on the highest-risk task (pragmatic-edge classification, where five subtle categories must be distinguished), and failure isolation matters more here than token cost, a malformed combined-call response risks losing entities, edges, and state-node updates for the turn at once, whereas a multi-call failure only drops one call's output, which the existing best-effort update rule already tolerates.

***Note: This is not final.** It is the working default carried into prompt-writing, to be compared empirically against the combined-call variant in Phase 4 (per the workplan's own instruction). Both variants should be implemented so the comparison is a configuration change, not a rewrite.*

## 5.3 Cost Estimate

*(Note: All figures below are design-time estimates, not measurements, intended to show the design respects the bounded-per-turn-cost constraint (baseline 3.1 \- Oliveira thesis) on paper. Phase 3 replaces them with numbers from an actual run.)*

**Multi-call design (W1–W5)**

| Call | Produces | Sync/Async | Needs | Est. input tokens | Est. output tokens |
| :---- | :---- | :---- | :---- | :---- | :---- |
| EMBED | node embedding | Sync (to W4; to W2/W3 jointly with W1) | new turn only | n/a (embedding call, not a completion) | n/a |
| W1 | entities, speech\_act, epistemic\_status default | Sync (to W2/W3 jointly with EMBED) | new turn only | \~150–300 | \~50–100 |
| W2 | hierarchical edges | Async (once EMBED \+ W1 both done) | new turn \+ N candidate interactions | \~800–1,500 | \~80 |
| W3 | pragmatic edges, epistemic\_status update | Async (once EMBED \+ W1 both done) | new turn \+ N candidate interactions | \~800–1,500 | \~80 |
| W4 | state-node create/update | Async (once EMBED done) | new turn \+ new turn's embedding \+ K\_state\_w4 semantically-selected non-terminated state nodes (5.5) | \~500–900 | \~100–150 |
| W5 | summary \+ reference | Async (from the start, no dependents) | new turn only | \~150–300 | \~40–70 |

* epistemic\_status adds no extra call, it is a side-effect write after W3 (3.5).

* **Wall-clock latency**: The slowest critical path max(EMBED\_time \+ W4\_time, max(EMBED\_time, W1\_time) \+ max(W2\_time, W3\_time), W5\_time). In practice, since embedding calls are typically much faster than LLM completions, this collapses close to W1\_time \+ max(W2\_time, W3\_time), i.e. **roughly two sequential LLM calls**. *This needs measuring in Phase 3\. The actual gap depends on how much faster EMBED is than W1 in practice, and how close W2/W3's latencies are to each other.*

* Total extra tokens/turn (summed across calls, since each pays for its own context): roughly 2,400–4,500 input \+ 270–400 output tokens, across 5 calls.

**Single-combined-call design**

| Call | Produces | Sync/Async | Needs | Est. input tokens | Est. output tokens |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Combined | entities, speech\_act, hierarchical edges, pragmatic edges, state-node action, summary, reference | Async | new turn \+ N candidate interactions \+ open state nodes (sent once) | \~1,800–2,200 | \~360–460 |

* Wall-clock latency: one call, but a larger single generation, likely higher than any *individual* multi-call latency, though well below the multi-call design's serial sum.  
* Total tokens/turn: lower overall than multi-call (candidate list sent once), but concentrated in one call the model must get entirely right in one pass.

## 5.4. Candidate Selection Strategy (Retrieval-Side Extension)

*This section extends how the new signals feed retrieval; it is design work for Phase 4's integration task, included here because it follows directly from the schema and pipeline (5.9).*

**Baseline (Oliveira thesis 3.4–3.5)** 

Fixed item budget T \= N\_recent \+ K\_historical \= 5 \+ 40 \= 45. Graph expansion: K\_semantic \= 5 entry points (top semantic matches) → 1-hop neighbours along typed edges → scored by score \= 0.75·sim \+ 0.25·edge\_strength → top G \= round(K\_historical × f) taken, f \= 0.25 by default.

**Important caveat carried over from the thesis**

The parameter sweep found that *no* f \> 0 improved recall@k on LoCoMo: every non-zero graph-slot allocation slightly hurt recall through displacement, using the sub/super/same-level graph alone. (**Note**: *This is the risk baseline any extension has to overcome; it is not a solved problem, and this report does not claim it is solved by the new relation types.)*

**Proposed reframing**

Recency, semantic retrieval, entity-based retrieval, and state-node- based retrieval are not five independent parallel sources. 1-hop expansion is the shared mechanism, and entity/state-node signals should feed it as additional *entry-point generators*, reusing the existing scoring formula extended to cover pragmatic edges too:

Entry points \= TopK\_semantic(query) ∪   
EntityAnchored(query) ∪ StateNodeAnchored(query)  
                        ↓  
        1-hop expansion (hierarchical \+ pragmatic edges)  
                        ↓  
        score \= 0.75·sim \+ 0.25·edge\_strength  
                        ↓  
        Top-G by score → graph slots

* **Recency** — unconditional, unchanged.  
* **Semantic entry points** — unchanged.  
* **Entity-anchored entry points (new)**: only fires if the query contains a recognized entity; pulls that entity's mentioned\_in list. (*Conditional, not a guaranteed quota.)*  
* **State-node-anchored entry points (new)**: only fires if an active/open state node relates to the query. *(**Note**: open\_question nodes may bypass the similarity selection entirely, since the point of tracking them is to resurface even when later phrasing doesn't match, not a default applied to all state-node types.)*

**Other sources considered** (to document, not all adopted yet)

| Source | Rationale | Risk if omitted |
| :---- | :---- | :---- |
| Contradiction / safety surfacing | Force-include a contested node or an active contradicts target relevant to the topic, regardless of rank. | Silently presenting one side of an unresolved conflict, undermines the epistemic-status design (3.5). |
| Pragmatic-edge-anchored entry points | Use depends\_on / references etc. to seed entry points, not just to score neighbours after the fact. | Five new edge types are built but only used for scoring, never for seeding, half the signal unused. |
| Interaction-State edge anchored entry points | Use relates edges (supports / contradicts / constrained\_by / resolves, 3.4) themselves to seed entry points directly. Similar to the pragmatic-edge-anchored idea above. | relates edges are currently only reachable via one-hop expansion from an already-established entry point (3.4) or indirectly through state-node-anchored entry points last\_updated\_turn read (5.5). |
| Citation chains | Nodes previously cited (citations field, 3.1) by an answer similar to the current query are a pre-vetted relevance signal. | Cheap, already-computed signal currently unused in retrieval. |
| Recurrence-weighted recency /Retrieval weighted | Give a small floor to nodes with high recurrence\_count even if not recently active. | recurrence\_count is computed but not currently consumed downstream. |

**Parameters**

| Parameter | Starting value | Notes |
| :---- | :---- | :---- |
| N\_recent | 5 | unchanged |
| K\_historical | 40 | unchanged |
| K\_semantic | 5 | unchanged (entry points) |
| K\_entity | 2 | new, sweep 0/2/4 |
| K\_state | 2 | new, sweep 0/2/4; test bypass-gate variant for open\_question separately |
| f\_graph | 0.25 | ceiling across all entry-point types combined, not per-source, to preserve the bounded-cost guarantee |
| K\_edge | 8 | unchanged (write-time candidate set, (5.6)) |
| r\_pragmatic | NULL (pooled default) | new, sweep 0.0/0.25/0.5/0.75/1.0 for the graph-slot budget split (5.5); NULL for production/ENRICHED \= pooled best-edge-wins scoring |

The baseline's neutrality coincided with a structurally thin graph (supercase in 4 of 3,954 edges). The working hypothesis for this extension is: **richer relation types plus entity and state-node anchored entry points give the graph enough real structure to overcome the displacement cost that a thinner graph could not.** This is a hypothesis to test, not a claim already supported by the schema design alone. The schema being richer does not by itself guarantee the retrieval signal improves, which is exactly why Phase 3 validation and the Phase 4 evaluation against both baselines are needed before drawing a conclusion.

**Task 4.4 comparison profiles.** 

Rather than implementing the sub/super/same-level-only graph and the semantic-RAG baseline as separate codebases, both are reconstructed as degenerate parameter settings of assemble\_context itself. See RECENCY\_ONLY\_PROFILE, BASELINE\_SEMANTIC\_PROFILE, BASELINE\_HIERARCHICAL\_PROFILE, PRAGMATIC\_ONLY\_PROFILE, and ENRICHED\_PROFILE in 5.5. This is a real ablation study that also happens to satisfy Task 4.4's baseline-comparison requirement, not a reimplementation of the old codebase. A stronger method claim, since it removes the confound of comparing against a separately-written system that might differ from the enriched one in ways that have nothing to do with the graph structure being tested. The hierarchical/pragmatic split (r\_pragmatic) is a **budget allocation, not a score comparison**: a hierarchical-reached candidate is never ranked against a pragmatic-reached one. Each pool is ranked only against itself, and r\_pragmatic decides how large a slice of the graph-slot budget each pool gets. See 5.5, step 4, and 5.10 for the decision record.

## 5.5 Context Assembly Procedure

What each compression tier means and when it applies is defined in 3.6 (Task 1.4). This section covers the mechanics: how candidates are selected, scored, and rendered at whichever tier 3.6's rule assigns them.  
*\# \============================================================*  
*\# Shared core — one function, two call sites (answer-time and*  
*\# write-time), differing only by which profile is passed in.*  
*\# \============================================================*

HIERARCHICAL\_EDGE\_LABELS \= {"subcase", "supercase", "same\_level"}                          *\# 3.4.1*  
PRAGMATIC\_EDGE\_LABELS    \= {"revises", "contradicts", "resolves", "depends\_on", "references"}  *\# 3.4.2*  
*\# used only to route a scored candidate into the right pool*

FUNCTION assemble\_context(query\_embedding, seed\_entities, graph, ann\_index, state\_index, entity\_registry, profile):  
    *\# profile \= { N\_recent, K\_target, K\_semantic, K\_entity, K\_state, f\_graph, r\_pragmatic, compress, count\_retrieval }*  
    *\# r\_pragmatic: NULL (default) \= pooled best-edge-wins scoring, the production/ENRICHED behavior.*   
   *\# A number in \[0, 1\] \= split the graph-slot budget G into two independently-ranked pools instead. see step 4\.*

    *\# \---- 1\. Recency layer \----*  
    recency\_layer \= graph.most\_recent\_nodes(profile.N\_recent)  
    excluded \= set(n.id FOR n IN recency\_layer)  
    K\_historical \= profile.K\_target \- profile.N\_recent

    *\# \---- Short-circuit: pure recency, nothing else computed.*  
    *\# A true recency-only condition (RECENCY\_ONLY\_PROFILE, 5.4).*  
    *\#Setting N\_recent \== K\_target (so K\_historical \<= 0\) to produce recency-only behavior.*  
    *\#This guard also skips steps 2-5 entirely rather than computing entry points and discarding them, which matters for*  
    IF K\_historical \<= 0:  
        context\_items \= \[\]  
        FOR node IN recency\_layer:  
            context\_items.append(render(node, tier="full", state\_nodes, entity\_registry)))  
            IF profile.count\_retrieval:  
                bump\_retrieval(node)  
        RETURN context\_items

    *\# \---- 2\. Entry-point generation \----*  
    semantic\_entries \= ann\_index.top\_k(query\_embedding, profile.K\_semantic,  
                                        exclude=excluded)

    entity\_entries \= \[\]  
    FOR eid IN seed\_entities:  
        entity\_entries.extend(entity\_registry\[eid\].mentioned\_in)  
    entity\_entries \= top\_k\_by\_recency(dedup(entity\_entries) MINUS excluded,  
                                       profile.K\_entity)

    state\_matches \= state\_index.top\_k(  
        query\_embedding, profile.K\_state,  
        filter \= status IN {"active", "open"},  
        bypass\_similarity\_gate\_for \= "open\_question"  
    )  
    state\_entries \= dedup(  
        flatten(  
            \[sn.creation\_turn\] \+ \[pair\[0\] FOR pair IN sn.last\_updated\_turn.updates\]  
                                \+ \[pair\[0\] FOR pair IN sn.last\_updated\_turn.relates\]  
            FOR sn IN state\_matches  
        )  
    ) MINUS excluded

    entry\_points \= dedup(semantic\_entries \+ entity\_entries \+ state\_entries)

    *\# \---- 3\. 1-hop graph expansion \+ scoring \----*

    *\# Two separate score pools, hierarchical vs. pragmatic, are tracked here*  
    *\#Formula (0.75\*sim \+ 0.25\*strength) for both, just routed into two dicts by the edge-label family.            \# kept SEPARATE and independently budgeted for Task 4.4 evaluation via profile.r\_pragmatic.*  
    *\# This step just makes both options available without redoing the traversal.*  
    scored\_hierarchical \= {}  
    scored\_pragmatic \= {}  
    FOR entry IN entry\_points:  
        IF entry NOT IN excluded:  
            direct\_score \= cosine(query\_embedding, graph.get(entry).embedding)  
            scored\_hierarchical\[entry\] \= max(scored\_hierarchical.get(entry, \-1), direct\_score)  
            scored\_pragmatic\[entry\] \= max(scored\_pragmatic.get(entry, \-1), direct\_score)  
        FOR (neighbor\_id, edge\_label, edge\_strength) IN graph.one\_hop\_neighbors(entry): *\#It is a graph traversal (way to find all the neighboring edges from a node)*  
            IF neighbor\_id IN excluded:  
                CONTINUE  
            sim \= cosine(query\_embedding, graph.get(neighbor\_id).embedding)  
            score \= 0.75 \* sim \+ 0.25 \* edge\_strength   *\# SAME formula for both families. r\_pragmatic controls candidate-POOL allocation, never per-candidate scoring*  
            IF edge\_label IN HIERARCHICAL\_EDGE\_LABELS:  
                scored\_hierarchical\[neighbor\_id\] \= max(scored\_hierarchical.get(neighbor\_id, \-1), score)  
            ELIF edge\_label IN PRAGMATIC\_EDGE\_LABELS:  
                scored\_pragmatic\[neighbor\_id\] \= max(scored\_pragmatic.get(neighbor\_id, \-1), score)

    *\# \---- 4\. Graph-slot selection \----*  
    G \= round(K\_historical \* profile.f\_graph)

    IF profile.r\_pragmatic IS NULL:  
        *\# Production / ENRICHED default: pooled, best-edge-wins. A candidate's score is the max across whichever family scores it higher.*  
        pooled \= {}  
        FOR id IN set(scored\_hierarchical.keys()) UNION set(scored\_pragmatic.keys()):  
            pooled\[id\] \= max(scored\_hierarchical.get(id, \-1), scored\_pragmatic.get(id, \-1))  
        ranked \= sort(pooled.items(), by=score, descending=True)  
        graph\_slots \= \[id FOR (id, score) IN ranked\[:G\]\]

    ELSE:  
        *\#G is divided into two separate budgets: one for hierarchical retrieval and one for pragmatic retrieval. Each group is ranked only against candidates within its own group. The parameter r\_pragmatic controls how much of the budget goes to pragmatic retrieval:*  
         *0.0 → only hierarchical retrieval (baseline)*  
         *1.0 → only pragmatic retrieval*  
         *Between 0.0 and 1.0 → a mix of both, allowing a proper comparison across different ratios.*  
        G\_pragmatic \= round(G \* profile.r\_pragmatic)  
        G\_hierarchical \= G \- G\_pragmatic

        ranked\_hierarchical \= sort(scored\_hierarchical.items(), by=score, descending=True)  
        graph\_slots\_hierarchical \= \[id FOR (id, score) IN ranked\_hierarchical\[:G\_hierarchical\]\]  
Candidate instead of a duplicate.  
        *\# Excludes anything the hierarchical pool already took, so a candidate strong in both pools doesn't consume the budget twice. pragmatic fills its own budget with its next-best UNIQUE candidate instead of a duplicate.*  
        ranked\_pragmatic \= sort(scored\_pragmatic.items(), by=score, descending=True)  
        graph\_slots\_pragmatic \= \[  
            id FOR (id, score) IN ranked\_pragmatic  
            IF id NOT IN graph\_slots\_hierarchical  
        \]\[:G\_pragmatic\]

        graph\_slots \= graph\_slots\_hierarchical \+ graph\_slots\_pragmatic

    *\# \---- 5\. Remaining historical slots: pure semantic fill \----*  
    remaining \= K\_historical \- len(graph\_slots)  
    already\_selected \= excluded UNION set(graph\_slots)  
    semantic\_fill \= ann\_index.top\_k(query\_embedding, remaining,  
                                     exclude=already\_selected)  
    historical\_layer \= graph\_slots \+ semantic\_fill

    *\# \---- 6\. Rendering \----*  
    context\_items \= \[\]  
    FOR node IN recency\_layer:  
        context\_items.append(render(node, tier="full", state\_nodes, entity\_registry))  
        IF profile.count\_retrieval:  
            bump\_retrieval(node)

    remaining\_token\_budget \= TOTAL\_CONTEXT\_TOKEN\_BUDGET \- estimate\_tokens(context\_items)  
    FOR node IN historical\_layer (ordered by score, descending):  
        IF profile.compress:  
            tier \= choose\_compression\_tier(node, remaining\_token\_budget, state\_nodes, entity\_registry)  
            IF tier IS NULL:  
                CONTINUE  
            remaining\_token\_budget \-= count\_tokens\_for\_tier(node, tier, state\_nodes, entity\_registry)  
        ELSE:  
            tier \= "full"  
        context\_items.append(render(node, tier, state\_nodes, entity\_registry))  
        IF profile.count\_retrieval:  
            bump\_retrieval(node)

    RETURN context\_items

FUNCTION bump\_retrieval(node):  
*\#retrieval\_count is only used for evaluation and diagnostics, such as checking which nodes are retrieved and how visible long-tail nodes are. It is never used for retrieval scoring because doing so would create a feedback loop where frequently retrieved nodes become even more likely to be retrieved.*  
    node.retrieval\_count \+= 1

FUNCTION choose\_compression\_tier(node, remaining\_token\_budget, state\_nodes, entity\_registry):  
    FOR tier IN \["full", "summary", "reference"\]:  
        cost \= count\_tokens\_for\_tier(node, tier, state\_nodes, entity\_registry)  
        IF cost \<= remaining\_token\_budget:  
            RETURN tier  
    RETURN NULL

FUNCTION render\_reference(node, state\_nodes, entity\_registry):  
*\#The lowest-level text is generated fresh each time instead of being stored, so it always reflects the state node’s latest status. This avoids stale information after revisions or resolutions, with negligible performance cost.*  
    IF node.state\_node\_links.creates is non-empty:  
        sn \= state\_nodes\[node.state\_node\_links.creates\[0\]\]  
        RETURN f"\[{sn.type}\] {sn.label}"  
    IF node.state\_node\_links.updates is non-empty:  
        sn \= state\_nodes\[node.state\_node\_links.updates\[-1\]\[0\]\]  
        RETURN f"\[{sn.type}, {sn.status}\] {sn.label}"  
    IF node.named\_entities is non-empty:  
        names \= \[entity\_registry\[e\].name FOR e IN node.named\_entities\[:2\]\]  
        RETURN f"\[entities\] {', '.join(names)}"  
    *\# fallback: W5's free-text output \- the only case that reads a stored field for this tier*  
    RETURN node.reference

FUNCTION count\_tokens\_for\_tier(node, tier, state\_nodes, entity\_registry):  
    IF tier \== "full":      RETURN count\_tokens(node.question) \+ count\_tokens(node.answer)  
    IF tier \== "summary":   RETURN count\_tokens(node.summary)  
*\#The reference cost must be based on the actual live pointer that will be displayed, not just node.reference, so the budget check matches what is actually shown.*  
    IF tier \== "reference": RETURN count\_tokens(render\_reference(node, state\_nodes, entity\_registry))

FUNCTION render(node, tier,  state\_nodes, entity\_registry):  
    IF tier \== "full":      RETURN {node.question, node.answer}  
    IF tier \== "summary":   RETURN node.summary  
    IF tier \== "reference": RETURN render\_reference(node, state\_nodes, entity\_registry)

*\# \---- The two call sites \----*

ANSWER\_PROFILE \= { N\_recent: 5, K\_target: 45, K\_semantic: 5, K\_entity: 2, K\_state: 2,  
                    f\_graph: 0.25, r\_pragmatic: NULL, compress: true, count\_retrieval: true }

EDGE\_PROFILE   \= { N\_recent: 1, K\_target: 8,  K\_semantic: 3, K\_entity: 2, K\_state: 2,  
                    f\_graph: 0.5,  r\_pragmatic: NULL, compress: false, count\_retrieval: false }  
*\#r\_pragmatic is NULL because the split-budget mechanism does not apply to write-time edge candidates. count\_retrieval is false because being selected for edge classification is different from being retrieved to answer a later query, and counting both would make the metric unclear.*

*\# \---- Task 4.4 comparison profiles \----*

*\#All five conditions are based on ANSWER\_PROFILE, changing only the parameters being compared. Everything else remains fixed, so only retrieval composition varies between conditions.*  
RECENCY\_ONLY\_PROFILE \= ANSWER\_PROFILE with {  
    N\_recent: 45,   *\#K\_target forces K\_historical to zero, making this a recency-only profile. The other parameters stay unchanged intentionally, so the short-circuit is what ensures recency-only behavior.*  
}

BASELINE\_SEMANTIC\_PROFILE \= ANSWER\_PROFILE with {  
    f\_graph: 0.0, K\_entity: 0, K\_state: 0,  
 *\#f\_graph \= 0 means there are no graph slots, so all historical slots are filled semantically. K\_entity and K\_state are set to zero only for clarity, and r\_pragmatic has no effect because there is no graph budget.*  
}

BASELINE\_HIERARCHICAL\_PROFILE \= ANSWER\_PROFILE with {  
    r\_pragmatic: 0.0, K\_entity: 0, K\_state: 0,  
*\#This reconstructs Oliveira’s original baseline: semantic entry points followed by graph expansion, using the 0.75 × similarity \+ 0.25 × edge-strength scoring. Only the hierarchical pool is used; semantic retrieval and graph expansion remain active as in the original baseline.*  
}

PRAGMATIC\_ONLY\_PROFILE \= ANSWER\_PROFILE with {  
    r\_pragmatic: 1.0, K\_entity: 0, K\_state: 0,  
*\#G\_hierarchical \= 0 means graph slots are filled only by the pragmatic pool. This tests whether pragmatic edges provide useful retrieval signals on their own, rather than only complementing hierarchical structure.*  
}

ENRICHED\_PROFILE \= ANSWER\_PROFILE  
*r\_pragmatic \= NULL keeps the default behavior: hierarchical and pragmatic edges are scored together, with the best edge winning.*

FUNCTION assemble\_answer\_context(question\_text, graph, ann\_index, state\_index,  
                                  entity\_registry, profile=ANSWER\_PROFILE):  
    *\# profile is now a parameter, not hardcoded, specifically so Task 4.4's comparison can run the same function under all four profiles above rather than needing four near-duplicate implementations.*  
    IF profile.K\_target \- profile.N\_recent \<= 0:  
*\#Recency-only skips embedding and entity extraction entirely because they are unnecessary. This keeps it as the cheapest possible condition for comparison.*  
        RETURN assemble\_context(NULL, \[\], graph, ann\_index, state\_index,  
                                 entity\_registry, profile)

    query\_embedding \= embed(question\_text)  
    query\_entities \= R1\_extract\_entities(question\_text)  
    seed\_entities \= \[resolve\_entity(e, entity\_registry) FOR e IN query\_entities\]  
    RETURN assemble\_context(query\_embedding, seed\_entities, graph, ann\_index,  
                             state\_index, entity\_registry, profile)

FUNCTION assemble\_edge\_candidates(node, graph, ann\_index, state\_index, entity\_registry):  
*This feeds W2 (hierarchical) and W3 (pragmatic) and requires both node embeddings and named entities. Therefore, it can run only after both EMBED and W1 are completed.*      
RETURN assemble\_context(node.embedding, node.named\_entities, graph, ann\_index,  
                             state\_index, entity\_registry, EDGE\_PROFILE)

FUNCTION assemble\_state\_node\_candidates(node, state\_index):  
*\# This feeds W4 and only requires node embeddings. It performs direct semantic search over state nodes, so it can start as soon as EMBED finishes.*  
    RETURN state\_index.top\_k(  
        node.embedding, K\_state\_w4,  
        filter \= status IN {"active", "open"},           *\# i.e. NOT IN any TERMINAL\_STATUSES (3.3.1) \- "non-terminated"*  
        bypass\_similarity\_gate\_for \= "open\_question",   
    )

## 5.6 Prompts

*Few-shot examples added below for every prompt, per the workplan's Task 2.2 deliverable ("prompt templates ... and few-shot examples"). (**Note**: Examples are drawn from the worked example  (4) , which might be updated in the future.)*

### Retrieval phase

**R1 — Query Entity Extraction**

*SYSTEM:*  
 *You extract named entities from a user's question, so they can be looked up in*  
 *an existing entity index. Only extract specific, referenceable entities:*  
 *proper nouns, technical terms, system/product/tool names, people, organizations.*  
 *Skip generic words, pronouns, and vague references.*

*Valid types: person, organization, system, tool, measurement, location, event, document.*

*Return strict JSON only, no prose, no markdown fences:*  
 *{"entities": \[{"name": "\<as mentioned in the question\>", "type": "\<one of the valid types\>"}\]}*  
 *If no entities are found, return {"entities": \[\]}.*

*USER:*  
 *Question: "{query\_text}"*

*FEW-SHOT EXAMPLES:*

*Question: "What did INESC TEC decide about the per-turn extraction cost budget?"*  
 *→ {"entities": \[{"name": "INESC TEC", "type": "organization"}, {"name": "per-turn extraction cost budget", "type": "measurement"}\]}*

*Question: "Why did that turn out to matter?"*  
 *→ {"entities": \[\]}*  
 *(pronoun-only reference, nothing specific or referenceable to look up)*

**R2 — Cited Answer Generation**

*SYSTEM:*  
 *You are answering a question in an ongoing conversation. Some context from*  
 *earlier in the conversation will be provided below, tagged with bracketed IDs*  
 *(e.g. \[N14\], \[SN\_2\]).*

*Use the context the way a helpful assistant naturally would:*  
 *\- Cite an ID when it points to something specific and useful \- a decision, a*  
 *fact, a number, a prior commitment \- especially if the user might want to*  
 *trace or verify it.*  
 *\- Citing matters most when something changed: if something was later revised*  
 *or superseded, say so and cite both, e.g. "we initially chose Postgres \[N5\],*  
 *but later switched to MySQL \[N14\]."*  
 *\- Don't force a citation onto answers that don't need one \- general knowledge,*  
 *definitions, greetings, anything not actually drawn from the context. Just*  
 *answer normally.*  
 *\- Don't cite something just because it happens to be present; cite it because*  
 *it's actually doing work in your answer.*  
 *\- Never cite an ID that is not present in the context below.*  
 *\- Little or no context (e.g. early in the conversation) is normal, not a*  
 *problem \- answer from your own knowledge if you can.*

*USER:*  
 *CONTEXT:*  
 *{assembled\_context\_with\_bracketed\_ids}*

*QUESTION:*  
 *{query\_text}*

*FEW-SHOT EXAMPLE:*

*CONTEXT:*  
 *\[N\_4\] Q: "Separately, what should the default epistemic\_status be when a new node is created?" A: "I'd default to open only for factual\_question and clarification\_request, and resolved for every other speech act."*  
 *\[N\_9\] Q: "Given that finding, should we simplify the default epistemic\_status rule too?" A: "Yes \- simplify further: default resolved unless the speech act is a question type, no separate handling for edge cases."*

*QUESTION: "What's the current default epistemic\_status rule?"*

*→ "The rule was originally open only for factual\_question and clarification\_request, resolved otherwise \[N\_4\], but it was later simplified to default resolved unless the speech act is a question type \[N\_9\]."*  
 *(both cited, since the answer is exactly the "something changed" case the system prompt calls out \- citing only N\_9 would hide that a revision happened at all)*

### Write phase

**W1 — Entities \+ Speech Act** *(needs only the new turn)*

*SYSTEM:*  
 *Given a single conversational turn (question \+ answer), extract:*  
 *1\. Named entities mentioned \- valid types: person, organization, system, tool, measurement, location, event, document.*  
 *2\. The speech act of the turn \- exactly one of:*  
 *factual\_question, clarification\_request, correction, decision, feedback, follow\_up, suggestion, agreement, disagreement, information, request*

*Return strict JSON only:*  
 *{"entities": \[{"name": "...", "type": "..."}\], "speech\_act": "..."}*

*Note on citations: the answer may contain bracketed markers like \[N\_3\] pointing back*  
 *to an earlier interaction node. These are citation/provenance markers only \- never*  
 *extract a bracketed ID as an entity, and ignore them when judging the speech act.*

*USER:*  
 *Q: "{new\_question}"*  
 *A: "{new\_answer}"*

*FEW-SHOT EXAMPLES:*

*Q: "What relation types should we add beyond subcase, supercase, and same\_level?"*  
 *A: "I'd propose five pragmatic edges \- revises, contradicts, resolves, depends\_on, and references \- covering correction, disagreement, resolution, prerequisite, and simple callback, while keeping the number of extra calls Claude makes each turn bounded \[N\_1\]."*  
 *→ {"entities": \[{"name": "Claude", "type": "system"}\], "speech\_act": "decision"}*  
 *(\[N\_1\] is a citation marker, not an entity \- it is not present in the output)*

*Q: "When you said pragmatic edges get their own classification call \- does that mean W2 and W3 always run fully independently in parallel, or could the order actually matter?"*  
 *A: "Good question to pin down \- that's not settled yet. I'd flag it as an open question: does W3 need W2's hierarchical labels first, or can they run fully in parallel? We won't know for certain until we test it end to end."*  
 *→ {"entities": \[\], "speech\_act": "clarification\_request"}*  
 *(no citations here \- confirms the rule isn't "always strip a bracket", it's "there was none to strip")*

**W2 — Hierarchical Edge Classification** *(needs candidate interactions)*

*SYSTEM:*  
 *You classify the topical relationship between a NEW interaction and each*  
 *CANDIDATE prior interaction. For each candidate, choose exactly one:*

*\- subcase: NEW is a more specific case of the candidate's topic*  
 *\- supercase: NEW is a more general topic that the candidate is a case of*  
 *\- same\_level: NEW and the candidate discuss the same specific topic*  
 *\- no\_relation: no meaningful topical relationship*

*Return strict JSON only: {"\<candidate\_id\>": "\<label\>", ...} for every candidate*  
 *listed.*

*Note on citations: NEW's answer, and any candidate's answer, may contain bracketed*  
 *markers like \[N\_3\]. These are citation/provenance markers from a prior call, not*  
 *classification targets \- classify against the candidate list given below the prompt,*  
 *never against an ID that only appears inside bracket text.*

*USER:*  
 *NEW:*  
 *Q: "{new\_question}"*  
 *A: "{new\_answer}"*

*CANDIDATES:*  
 *{candidate\_interactions\_list}*

*FEW-SHOT EXAMPLE:*

*NEW:*  
 *Q: "Can you summarize the schema decisions in the Phase 1-2 report so far?"*  
 *A: "Sure \- we're adding five pragmatic edge types while staying within the bounded per-turn cost constraint \[N\_1\], defaulting new nodes to resolved unless they're a question, and we still haven't settled whether W2 and W3 need a fixed order."*

*CANDIDATES:*  
 *N\_1: Q: "For Phase 1 and 2 of the INESC TEC graph memory work, our goal is..." A: "Got it \- I'll track both..."*  
 *N\_2: Q: "What relation types should we add beyond subcase, supercase, and same\_level?" A: "I'd propose five pragmatic edges \- revises, contradicts, resolves, depends\_on, and references \- covering correction, disagreement, resolution, prerequisite, and simple callback, while keeping the number of extra calls Claude makes each turn bounded \[N\_1\]."*  
 *N\_4: Q: "Separately, what should the default epistemic\_status be when a new node is created?" A: "I'd default to open only for factual\_question and clarification\_request, and resolved for every other speech act."*

*→ {"N\_1": "no\_relation", "N\_2": "supercase", "N\_4": "supercase"}*  
 *(NEW is a summary spanning both the edge-type decision and the default-status decision, so it's a supercase of each individually \- N\_1 sets up the project's goal/constraint but isn't itself one of the things being summarized, so no\_relation; note N\_2's own answer cites \[N\_1\] internally, but that's N\_2's business, not a signal about NEW's relation to N\_1)*

**W3 — Pragmatic Edge Classification** *(needs candidate interactions )*

*SYSTEM:*  
 *You classify the discourse relationship between a NEW interaction and each*  
 *CANDIDATE prior interaction. Candidates are the prior interactions. For each candidate, choose exactly one:*

*\- revises: NEW changes or supersedes a decision/position taken in the candidate*  
 *\- contradicts: NEW conflicts with the candidate without explicitly revising it*  
 *\- resolves: NEW answers or closes an open question raised in the candidate*  
 *\- depends\_on: NEW's content relies on something established in the candidate*  
 *\- references: NEW explicitly calls back to the candidate without changing or*  
 *resolving it*  
 *\- no\_relation: none of the above*

*Return strict JSON only: {"\<candidate\_id\>": "\<label\>", ...} for every candidate*  
 *listed.*

*Note on citations: NEW's answer, and any candidate's answer, may contain bracketed*  
 *markers like \[N\_6\]. These are citation markers a prior answer-generation call*  
 *inserted, not a signal of a revises/contradicts/resolves relationship by themselves \-*  
 *judge the discourse relation from the actual content, the same way you would if the*  
 *bracket weren't there.*

*USER:*  
 *NEW:*  
 *Q: "{new\_question}"*  
 *A: "{new\_answer}"*

*CANDIDATE INTERACTIONS:*  
 *{candidate\_interactions\_list}*

*FEW-SHOT EXAMPLE:*

*NEW:*  
 *Q: "Have you thought it through?"*  
 *A: "Yes \- each of the five maps to something the thesis needs distinctly \[N\_6\]: contradicts surface disputes explicitly instead of hiding them in a plain edge, and depends\_on lets retrieval find prerequisite context. I'd keep all five, though the strength values should stay provisional until Phase 4's parameter sweep."*

*CANDIDATE INTERACTIONS:*  
 *N\_2: Q: "What relation types should we add beyond subcase, supercase, and same\_level?" A: "I'd propose five pragmatic edges \- revises, contradicts, resolves, depends\_on, and references..."*  
 *N\_6: Q: "Actually, I think five pragmatic types is overengineered \- let's just keep revises and resolves, the rest adds complexity without proven benefit." A: "Worth taking seriously \- I'll flag this as a direct challenge to the five-edge-type decision until we think it through."*

*→ {"N\_2": "resolves", "N\_6": "resolves"}*  
 *(NEW settles the open pushback N\_6 raised, and in doing so also closes the doubt N\_6 had cast over N\_2's original decision \- \[N\_6\] in NEW's own answer is a citation, not the classification target itself, N\_6 the candidate turn is)*

**W4 — State-Node Detection / Merge** *(needs open state nodes)*

*SYSTEM:*  
 *Given a new conversational turn and the list of currently OPEN state nodes*  
 *(goals, decisions, constraints, open questions), identify everything this turn*  
 *does with respect to state nodes. A single turn can do more than one of these*  
 *at once \- return every one that applies, not just the first you notice:*

*1\. CREATES \- a new goal, decision, constraint, or open question not already*  
 *tracked. A turn can create more than one (e.g. stating both a goal and a*  
 *constraint at the same time).*  
 *2\. UPDATES \- changes an existing state node's lifecycle status (revises a*  
 *decision, marks a goal achieved/abandoned, lifts/revises a constraint,*  
 *resolves an open question).*  
 *3\. RELATES \- connects this turn to an existing state node WITHOUT changing*  
 *its status, using exactly one of:*  
 *\- supports: reinforces the target, evidence or justification for it*  
 *\- contradicts: conflicts with the target, without revising or lifting it*  
 *\- constrained\_by: this turn's content is bound or limited by the target*  
 *\- resolves: answers/closes a target open\_question \- IMPORTANT: resolves*  
 *ALWAYS also produces a matching UPDATE (new\_status: "resolved") on the*  
 *same target; it is the one relation that is also a status change, so it*  
 *appears in both lists, not one or the other.* *If none of the above apply, return all three lists empty.*

*Valid new\_status values for UPDATES, by the target's type \- use exactly one of these,*  
 *never invent a status outside this list:*  
 *\- goal: achieved (met) | abandoned (given up on)*  
 *\- decision: revised (changed but still stands \- can happen more than once) | reverted*  
 *(undone entirely)*  
 *\- constraint: revised (terms changed, still in force) | lifted (no longer applies)*  
 *\- open\_question: resolved (answered)*  
 *achieved, abandoned, reverted, lifted, and resolved are terminal \- do not propose an*  
 *update against a state node whose current status is already one of those.*

*Note on citations: the new turn's answer may contain bracketed markers like \[N\_2\]*  
 *pointing back to an earlier interaction node. These are citation markers, not state*  
 *nodes \- never treat a bracketed interaction ID as a state\_node\_id.*

*Return strict JSON only:*  
 *{"creates": \[{"state\_type": "goal"|"decision"|"constraint"|"open\_question", "label": "\<short summary, under 12 words\>"}, ...\],*  
 *"updates": \[{"state\_node\_id": "\<id from the list below\>", "new\_status": "\<the node's next status\>"}, ...\],*  
 *"relates": \[{"state\_node\_id": "\<id from the list below\>", "relation": "supports"|"contradicts"|"constrained\_by"|"resolves"}, ...\]}*

*USER:*  
 *NEW TURN:*  
 *Q: "{new\_question}"*  
 *A: "{new\_answer}"*

*CURRENTLY OPEN STATE NODES:*  
 *{open\_state\_nodes\_list}*

*FEW-SHOT EXAMPLES:*

*NEW TURN:*  
 *Q: "For Phase 1 and 2 of the INESC TEC graph memory work, our goal is to extend the schema to represent entities, goals, decisions, constraints, and open questions \- and whatever we add, per-turn extraction cost needs to stay bounded to just a few extra async calls."*  
 *A: "Got it \- I'll track both: the goal is the enriched schema covering entities and the four state-node types, and the constraint is keeping added extraction cost to a small, bounded number of async calls per turn."*

*CURRENTLY OPEN STATE NODES: (none yet)*

*→ {"creates": \[{"state\_type": "goal", "label": "Extend the graph schema to represent entities, goals, decisions, constraints, and open questions"}, {"state\_type": "constraint", "label": "Per-turn extraction cost must stay bounded to a small number of async calls"}\], "updates": \[\], "relates": \[\]}*  
 *(one turn, two creates \- a goal and a constraint stated in the same breath; this is exactly the case a single-action output could not represent)*

*NEW TURN:*  
 *Q: "What relation types should we add beyond subcase, supercase, and same\_level?"*  
 *A: "I'd propose five pragmatic edges \- revises, contradicts, resolves, depends\_on, and references \- covering correction, disagreement, resolution, prerequisite, and simple callback, while keeping the number of extra calls Claude makes each turn bounded \[N\_1\]."*

*CURRENTLY OPEN STATE NODES:*  
 *SN\_2 (constraint): "Per-turn extraction cost must stay bounded to a small number of async calls" \- active*

*→ {"creates": \[{"state\_type": "decision", "label": "Adopt five pragmatic edge types: revises, contradicts, resolves, depends\_on, references"}\], "updates": \[\], "relates": \[{"state\_node\_id": "SN\_2", "relation": "constrained\_by"}\]}*  
 *(a create AND a relate in the same turn \- the new decision is explicitly scoped by the existing cost constraint, which stays active and untouched)*

*NEW TURN:*  
 *Q: "We tested it \- does the W2/W3 ordering actually matter?"*  
 *A: "No, it doesn't \- we checked: both calls read the same candidate list and neither touches the other's output, so there's no dependency between them. They run fully in parallel. Resolved."*

*CURRENTLY OPEN STATE NODES:*  
 *SN\_4 (open\_question): "Does classification order between W2 and W3 matter, or can they run fully in parallel?" \- open*

*→ {"creates": \[\], "updates": \[{"state\_node\_id": "SN\_4", "new\_status": "resolved"}\], "relates": \[{"state\_node\_id": "SN\_4", "relation": "resolves"}\]}*  
 *(resolves \- appears in BOTH lists: the status change itself in updates, the typed reason in relates)*

*NEW TURN:*  
 *Q: "Given that finding, should we simplify the default epistemic\_status rule too?"*  
 *A: "Yes \- simplify further: default resolved unless the speech act is a question type, no separate handling for edge cases."*

*CURRENTLY OPEN STATE NODES:*  
 *SN\_5 (decision): "Default epistemic\_status: open only for factual\_question/clarification\_request, resolved otherwise" \- active*

*→ {"creates": \[\], "updates": \[{"state\_node\_id": "SN\_5", "new\_status": "revised"}\], "relates": \[\]}*  
 *(a plain status change with no typed reason \- revised isn't one of the four relation labels, so updates is enough on its own; no relates entry needed)*

*NEW TURN:*  
 *Q: "Actually, I think five pragmatic types is overengineered \- let's just keep revises and resolves, the rest adds complexity without proven benefit."*  
 *A: "Worth taking seriously \- I'll flag this as a direct challenge to the five-edge-type decision until we think it through."*

*CURRENTLY OPEN STATE NODES:*  
 *SN\_3 (decision): "Adopt five pragmatic edge types: revises, contradicts, resolves, depends\_on, references" \- active*

*→ {"creates": \[\], "updates": \[\], "relates": \[{"state\_node\_id": "SN\_3", "relation": "contradicts"}\]}*  
 *(pushback recorded as a typed edge; SN\_3 stays active \- there is no contested-equivalent status to move it to, see 3.4)*

*NEW TURN:*  
 *Q: "Right before the meeting with my thesis advisor \- are we still keeping all five pragmatic edge types?"*  
 *A: "Yes, still all five, no changes \- the report's ready for review."*

*CURRENTLY OPEN STATE NODES:*

*SN\_3 (decision): "Adopt five pragmatic edge types: revises, contradicts, resolves, depends\_on, references" \- active*

*→ {"creates": \[\], "updates": \[\], "relates": \[\]}*  
 *(a confirmation that doesn't itself add new information about SN\_3 beyond what N\_7 already recorded \- all three lists empty is still a valid, distinct output, not an error case)*

**W5 — Summary \+ Reference Generation** *(needs only the new turn; higher temperature)*

*SYSTEM:*  
 *Given a single conversational turn (question \+ answer), produce two*  
 *compressed representations of it:*

*1\. "summary": one sentence, under 20 words. Be concrete \- name the specific*  
 *decision, fact, or question, not a generic description.*  
 *2\. "reference": a short noun-phrase title, 6 words or fewer, naming just the*  
 *specific fact/decision/question \- not a full sentence. This is the lowest-*  
 *compression tier and must always stand on its own, whether or not this turn*  
 *ends up linked to a state node.*

*If the answer contains bracketed citation markers like \[N\_1\], do not reproduce them*  
 *in "summary" or "reference" \- both are self-contained paraphrases, not quotations,*  
 *and paraphrase the underlying content instead of the citation notation.*

*Return strict JSON only:*  
 *{"summary": "...", "reference": "..."}*

*USER:*  
 *Q: "{new\_question}"*  
 *A: "{new\_answer}"*

*FEW-SHOT EXAMPLES:*

*Q: "What relation types should we add beyond subcase, supercase, and same\_level?"*  
 *A: "I'd propose five pragmatic edges \- revises, contradicts, resolves, depends\_on, and references \- covering correction, disagreement, resolution, prerequisite, and simple callback, while keeping the number of extra calls Claude makes each turn bounded \[N\_1\]."*  
 *→ {"summary": "Five pragmatic edge types are proposed: revises, contradicts, resolves, depends\_on, references.", "reference": "Five pragmatic edge types adopted"}*  
 *(\[N\_1\] is dropped \- the summary paraphrases the content, it doesn't carry the citation forward)*

*Q: "For Phase 1 and 2 of the INESC TEC graph memory work, our goal is to extend the schema to represent entities, goals, decisions, constraints, and open questions..."*  
 *A: "Got it \- I'll track both: the goal is the enriched schema covering entities and the four state-node types, and the constraint is keeping added extraction cost to a small, bounded number of async calls per turn."*  
 *→ {"summary": "Sets the goal (enriched schema) and the constraint (bounded per-turn extraction cost) for Phase 1-2.", "reference": "Goal and cost constraint set"}*  
 *(this turn also creates two state nodes, SN\_1 and SN\_2 \- reference is still self-authored, not replaced by either state node's label; see the correction to 5.8)*

### Single combined prompt (write phase only)

***SYSTEM***  
*You are updating a conversational memory graph after a new turn. Given the new turn, a set of candidate prior interactions, and the currently open state nodes, produce ALL of the following in one JSON object. Do not include any text outside the JSON.*

*1\. "entities" \- named entities in the new turn.*  
   *Valid types: person, organization, system, tool, measurement, location, event, document.*  
   *Format: \[{"name": "...", "type": "..."}\]*

*2\. "speech\_act" \- exactly one of:*  
   *factual\_question, clarification\_request, correction, decision, feedback,*  
   *follow\_up, suggestion, agreement, disagreement, information, request*

*3\. "hierarchical\_edges" \- for EACH candidate interaction listed below, exactly one of:*  
   *subcase, supercase, same\_level, no\_relation*  
   *Format: {"\<candidate\_id\>": "\<label\>", ...}*

*4\. "pragmatic\_edges" \- for EACH candidate INTERACTION listed below (never*  
   *state nodes \- state nodes are handled only by items 5-7 below), exactly*  
   *one of: revises, contradicts, resolves, depends\_on, references, no\_relation*  
   *Format: {"\<candidate\_id\>": "\<label\>", ...}*

*5\. "creates" \- state nodes newly created by this turn (can be more than one).*  
   *Format: \[{"state\_type": "goal"|"decision"|"constraint"|"open\_question", "label": "..."}, ...\]*

*6\. "updates" \- existing state nodes whose status this turn changed (can be*  
   *more than one). Valid new\_status values, by the target's type \- never*  
   *invent a status outside this list:*  
   *goal:          achieved | abandoned*  
   *decision:      revised  | reverted*  
   *constraint:    revised  | lifted*  
   *open\_question: resolved*  
*achieved, abandoned, reverted, lifted, and resolved are terminal \- do not propose an update against a state node already in one of those states.*  
*Format: \[{"state\_node\_id": "...", "new\_status": "..."}, ...\]*

*7\. "relates" \- typed edges to existing state nodes that do NOT change their status \- supports, contradicts, constrained\_by, or resolves. resolves ALWAYS also appears in "updates" (new\_status: "resolved") \- it is the one relation that is also a status change, so it appears in both, not one or the other.*  
*Format: \[{"state\_node\_id": "...", "relation": "supports"|"contradicts"|"constrained\_by"|"resolves"}, ...\]*  
*If none of creates/updates/relates apply, return all three as empty lists.*

*8\. "summary" \- one-sentence summary of the new turn, under 20 words.*

*9\. "reference" \- a short noun-phrase title, 6 words or fewer, naming just the*  
   *specific fact/decision/question \- not a full sentence.*

*Note on citations: the new turn's answer, or a candidate's answer, may*  
*contain bracketed markers like \[N\_1\] pointing back to an earlier interaction*  
*node. These are citation/provenance markers only \- never extract one as an*  
*entity (item 1), never classify against one as if it were a candidate*  
*(items 3-4), and never treat one as a state\_node\_id (items 6-7).*

*Return one JSON object with exactly these keys:*  
*entities, speech\_act, hierarchical\_edges, pragmatic\_edges,*  
*creates, updates, relates, summary, reference.*

*NEW TURN:*  
*Q: "{new\_question}"*  
*A: "{new\_answer}"*

*CANDIDATE INTERACTIONS (for hierarchical\_edges and pragmatic\_edges):*  
*{candidate\_interactions\_list}     \# e.g. N5: Q: "..." A: "..."*

*CURRENTLY OPEN STATE NODES (for creates/updates/relates only):*  
*{open\_state\_nodes\_list}           \# e.g. SN\_2 (decision): "use MySQL" \- active*

*FEW SHOT EXAMPLE 1:*

*NEW TURN:*  
*Q: "We tested it \- does the W2/W3 ordering actually matter?"*  
*A: "No, it doesn't \- we checked: both calls read the same candidate list and*  
    *neither touches the other's output, so there's no dependency between*  
    *them. They run fully in parallel. Resolved."*

*CANDIDATE INTERACTIONS:*  
*N\_3: Q: "When you said pragmatic edges get their own classification call \-*  
     *does that mean W2 and W3 always run fully independently in parallel,*  
     *or could the order actually matter?"*  
     *A: "Good question to pin down \- that's not settled yet..."*

*CURRENTLY OPEN STATE NODES:*  
*SN\_4 (open\_question): "Does classification order between W2 and W3 matter,*  
                        *or can they run fully in parallel?" \- open*  
*→{*  
  *"entities": \[\],*  
  *"speech\_act": "information",*  
  *"hierarchical\_edges": {"N\_3": "no\_relation"},*  
  *"pragmatic\_edges": {"N\_3": "resolves"},*  
  *"creates": \[\],*  
  *"updates": \[{"state\_node\_id": "SN\_4", "new\_status": "resolved"}\],*  
  *"relates": \[{"state\_node\_id": "SN\_4", "relation": "resolves"}\],*  
  *"summary": "Testing confirms W2 and W3 have no dependency and run fully in parallel.",*  
  *"reference": "W2/W3 confirmed independent, run in parallel"*  
*}*  
*FEW SHOT EXAMPLE 2:*

*NEW TURN:*  
*Q: "What relation types should we add beyond subcase, supercase, and*  
    *same\_level?"*  
*A: "I'd propose five pragmatic edges \- revises, contradicts, resolves,*  
    *depends\_on, and references \- covering correction, disagreement,*  
    *resolution, prerequisite, and simple callback, while keeping the number*  
    *of extra calls Claude makes each turn bounded \[N\_1\]."*

*CANDIDATE INTERACTIONS:*  
*N\_1: Q: "For Phase 1 and 2 of the INESC TEC graph memory work, our goal is*  
     *to extend the schema to represent entities, goals, decisions,*  
     *constraints, and open questions \- and whatever we add, per-turn*  
     *extraction cost needs to stay bounded to just a few extra async calls."*  
     *A: "Got it \- I'll track both: the goal is the enriched schema covering*  
     *entities and the four state-node types, and the constraint is keeping*  
     *added extraction cost to a small, bounded number of async calls per*  
     *turn."*

*CURRENTLY OPEN STATE NODES:*  
*SN\_2 (constraint): "Per-turn extraction cost must stay bounded to a small*  
                     *number of async calls" \- active*

*→{*  
  *"entities": \[{"name": "Claude", "type": "system"}\],*  
  *"speech\_act": "decision",*  
  *"hierarchical\_edges": {"N\_1": "no\_relation"},*  
  *"pragmatic\_edges": {"N\_1": "depends\_on"},*  
  *"creates": \[*  
    *{"state\_type": "decision", "label": "Adopt five pragmatic edge types: revises, contradicts, resolves, depends\_on, references"}*  
  *\],*  
  *"updates": \[\],*  
  *"relates": \[{"state\_node\_id": "SN\_2", "relation": "constrained\_by"}\],*  
  *"summary": "Five pragmatic edge types are proposed: revises, contradicts, resolves, depends\_on, references.",*  
  *"reference": "Five pragmatic edge types adopted"*  
*}*

## 5.7 Answer Generation Memory Update Procedure

Pseudo-code for updating the memory graph from the LLM-call outputs and computed values above. Structure mirrors the baseline's two-phase design: a synchronous stub allocates identity and holds the raw turn, and an asynchronous commit populates it and writes it into the graph exactly once, fully formed. *(**Note**: Under the current assumption that the next turn cannot begin until this turn's answer and graph write are both complete.)*

### **Overview: two phases, three waves**

Every turn goes through two phases. **Answer Generation** happens first, synchronously, and produces what the user sees. **Memory Graph Update** happens after, asynchronously, and is what the rest of (5.7) implements.

**A. Answer Generation Phase**

* The user asks a question.  
* Named entities are extracted from the question, if any, so nodes related to those entities can be found.  
* The question is embedded, producing its own candidate source: the top-K nodes nearest to it by semantic similarity, independent of any entity or state anchoring.  
* The state nodes relevant to the query are found, and the interaction nodes tied to those state nodes are pulled in as a third candidate source.  
* All three sources: semantic, entity-anchored, and state-anchored are unioned and expanded one hop, giving the candidate interaction nodes for answer generation.  
* The answer is generated with citations (R2).

**B. Memory Graph Update Phase**

After the answer is generated, the new turn (question \+ answer) is embedded and its entities extracted. Candidate selection for edge classification runs through the **same three-source union** as answer generation: semantic, entity-anchored, and state-anchored, just under a smaller budget (EDGE\_PROFILE vs. ANSWER\_PROFILE, (5.5)). State-node relevance is one of the three inputs here, not the only one: a turn with no state-node links still gets candidates from the semantic and entity sources.

This candidate set feeds hierarchical (W2) and pragmatic (W3) edge classification, both of which therefore need node.embedding *and* node.named\_entities before they can run i.e. entity extraction (W1) has to finish before W2/W3 can start, not just embedding. Summary/reference generation (W5) needs only the raw turn, nothing else. State-node create/update (W4) needs the turn's embedding and the current non-terminated state nodes, but never named entities or candidate interactions, so it does not need to wait on W1.

That dependency graph resolves into three waves, implemented by handle\_turn below:

* **Wave 1**: EMBED, W1, W5 start immediately; each needs only the raw turn.  
* **Wave 2**: W4 starts as soon as EMBED alone completes.  
* **Wave 3**: W2 and W3 start once *both* EMBED and W1 have completed and candidate selection has run; they then run in parallel with each other.

*(Also check the processing pipeline diagram (5.8))*

**Constants referenced below** (each mirrors a schema table already defined in Section 3, listed here so the pseudocode doesn't reference undefined lookups):

DEFAULT\_STATUS\_BY\_SPEECH\_ACT \= {  
    "factual\_question":        "open",  
    "clarification\_request":   "open",  
    "decision":                "resolved",  
    "information":             "resolved",  
    "agreement":                "resolved",  
    "request":                 "resolved",  
    "correction":               "resolved",  
    "follow\_up":                "resolved",  
    "suggestion":               "resolved",  
    "feedback":                 "resolved",  
    "disagreement":             "resolved",  
} *\# 3.5, "Default status on creation"*

EPISTEMIC\_TRIGGER\_LABELS \= {"revises", "resolves", "contradicts"} *\# 3.5's "Edge \-\> status effect" table; the labels that can ever change a target's epistemic\_status. depends\_on and references are absent because they have no effect on epistemic status..*

TERMINAL\_STATUSES \= {  
    "goal":           {"achieved", "abandoned"},  
    "decision":       {"reverted"},  
    "constraint":     {"lifted"},  
    "open\_question":  {"resolved"},  
} *\# 3.3.1*

VALID\_STATUSES \= {  
    "goal":           {"active", "achieved", "abandoned"},  
    "decision":       {"active", "revised", "reverted"},  
    "constraint":     {"active", "revised", "lifted"},  
    "open\_question":  {"open", "resolved"},  
} *\# 3.3.1*

DEFAULT\_STATUS\_BY\_TYPE \= {  
    "goal": "active", "decision": "active", "constraint": "active", "open\_question": "open",  
} *\# 3.3.1, initial status on creation*

RELATION\_TYPES \= {"supports", "contradicts", "constrained\_by", "resolves"} *\# 3.4.2, valid state\_node\_links.relates labels*

**The three stages** (*what gets written where*)

*(**Note**: This is a plan for now which might/should be changed in the future)*

**1\. Stub.** create\_stub makes a bare node: id, question, answer, timestamp, and two empty containers (edges, state\_node\_links) waiting to be filled. Nothing else. A separate scratch entry (turn\_scratch) is set up alongside it for bookkeeping that never becomes part of the node.

**2\. Enrichment: the source node only.** The six calls (EMBED, W1–W5) run across the three waves above, and every one of their appliers writes exclusively onto the node created in step 1: its own embedding, entities, speech act, epistemic-status default, hierarchical/pragmatic edges, state-node links, summary, and reference. Nothing outside this one node is touched. 

**3\. Finalization.** Once all six calls are in, maybe\_finalize commits the node to the graph, and only then touches anything else: every target node this new node's revises/resolves/contradicts edges point at gets its epistemic\_status and epistemic\_history updated, and every state node this turn created, updated, or related to gets created fresh or has its status touched. This is the only stage that ever modifies something other than the node itself.

### **Phase 0: synchronous stub** 

*(runs when the answer is returned)*

*\# \============================================================*  
*\# PHASE 0 \- synchronous, runs the instant the answer is generated*  
*\# \============================================================*

FUNCTION create\_stub(question, answer):  
    node \= {  
        id: new\_id(),  
        question: question,  
        answer: answer,  
        timestamp: now(),  
        edges: {"hierarchical": \[\], "pragmatic": \[\]},  
        state\_node\_links: {"creates": \[\], "updates": \[\], "relates": \[\]},  
    }

    pending\_nodes\[node.id\] \= node  
    turn\_scratch\[node.id\] \= {  
        "pending\_state\_node\_creates": \[\],   *\# staging area for W4 CREATES, see apply\_w4 below*  
        "w2\_w3\_dispatched": false,           *\# guards \_spawn\_w2\_w3 (Phase 1\) from firing twice. Both apply\_embedding and apply\_w1 can reach it*  
    }  
    RETURN node.id

### Turn orchestration

*(the piece that ties Phase 0's stub, Phase 1's appliers, and 5.5's candidate-selection functions together. Who actually calls W2/W3/W4, in what order)*

FUNCTION handle\_turn(question):  
    context \= assemble\_answer\_context(question, graph, ann\_index, state\_index, entity\_registry, profile)  *\#See (5..5)*  
    answer \= generate\_answer(question, context)          *\# R2*

    node\_id \= create\_stub(question, answer)  
    node \= pending\_nodes\[node\_id\]

    *\# \---- Wave 1: everything that needs only the raw turn (Q+A) \----*  
    *\# EMBED, W1, and W5 depend on nothing but node.question / node.answer, so all three fire together, with no ordering between them.*  
    spawn\_async(embed, node.question \+ " " \+ node.answer,  
                on\_complete \= LAMBDA result: apply\_embedding(node, result))  
    spawn\_async(call\_w1, node.question, node.answer,  
                on\_complete \= LAMBDA result: apply\_w1(node, result))  
    spawn\_async(call\_w5, node.question, node.answer,  
                on\_complete \= LAMBDA result: apply\_w5(node, result))

    RETURN node\_id

### Phase 1: per-call appliers

Six appliers, each fires the moment its own upstream call (embedding, W1–W5) returns, and ends by calling mark\_complete \+ maybe\_finalize. Only three of the six calls are actually independent of everything else — EMBED, W1, and W5 (see "Turn orchestration" above). W4 is gated on EMBED; W2 and W3 are gated on both EMBED and W1. apply\_embedding and apply\_w1 are where that gating is enforced: each checks whether the other has already landed, and whichever one finishes second is the one that actually dispatches the calls it was gating.

FUNCTION apply\_embedding(node, embedding):  
    node.embedding \= embedding  
    mark\_complete(node.id, "EMBED")  
    maybe\_finalize(node.id)

    *\# \---- Wave 2: EMBED alone unblocks W4 \----*  
    *\# W4 (5.6) never reads named\_entities or candidate interactions. Only the turn's embedding and the current non-terminated state nodes. So it does not need to wait for W1.*  
    state\_node\_candidates \= assemble\_state\_node\_candidates(node, state\_index)  
    spawn\_async(call\_w4, node, state\_node\_candidates,  
                on\_complete \= LAMBDA result: apply\_w4(node, result))

    *\# \---- Wave 3, half of the join \----*  
    *\# W2/W3 require both node.embedding and node.named\_entities. If W1 has already completed, W2/W3 can start as soon as the embedding is ready. If W1 is still running, the same check will be performed when W1 finishes.*  
    IF node.speech\_act IS NOT NULL:  
        \_spawn\_w2\_w3(node)

FUNCTION apply\_w1(node, w1\_result):  
    *\# entities \+ speech\_act \+ epistemic\_status default*  
    resolved\_entities \= \[\]  
    FOR ent IN w1\_result.entities:  
        cid \= resolve\_entity(ent.name, ent.type, entity\_registry)  
        IF cid IS NULL:  
            cid \= create\_entity(ent.name, ent.type, entity\_registry)  
        IF node.id NOT IN entity\_registry\[cid\].mentioned\_in:  
            entity\_registry\[cid\].mentioned\_in.append(node.id)  
        resolved\_entities.append(cid)

    node.named\_entities \= dedup(resolved\_entities)  
    node.speech\_act \= w1\_result.speech\_act

    *\# 3.5, "Default status on creation" \+ "Where this is actually set", the default is assigned here, at the same time as speech\_act, not by a separate call.*  
    node.epistemic\_status \= DEFAULT\_STATUS\_BY\_SPEECH\_ACT\[w1\_result.speech\_act\]  
    node.epistemic\_history \= \[\[node.id, "creation", node.epistemic\_status\]\]

    mark\_complete(node.id, "W1")  
    maybe\_finalize(node.id)

    *\# \---- Wave 3, other half of the join: did EMBED already finish? \----*  
    IF node.embedding IS NOT NULL:  
        \_spawn\_w2\_w3(node)

FUNCTION \_spawn\_w2\_w3(node):  
    *\# This is shared by apply\_embedding and apply\_w1. Whichever finishes second triggers it. The w2\_w3\_dispatched flag ensures it runs only once, even though both functions can reach it. The flag is kept in turn\_scratch (Phase 0), not on the node.*  
    IF turn\_scratch\[node.id\]\["w2\_w3\_dispatched"\]:  
        RETURN turn\_scratch\[node.id\]\["w2\_w3\_dispatched"\] \= true

    edge\_candidates \= assemble\_edge\_candidates(node, graph, ann\_index, state\_index, entity\_registry)  
    spawn\_async(call\_w2, node, edge\_candidates,  
                on\_complete \= LAMBDA result: apply\_w2(node, result))  
    spawn\_async(call\_w3, node, edge\_candidates,  
                on\_complete \= LAMBDA result: apply\_w3(node, result))

FUNCTION apply\_w2(node, w2\_result):  
    *\# hierarchical edges*  
    FOR (cand\_id, label) IN w2\_result.hierarchical\_edges:  
        IF label \!= "no\_relation" AND \[cand\_id, label\] NOT IN node.edges.hierarchical:  
            node.edges.hierarchical.append(\[cand\_id, label\])  
            bump\_recurrence(cand\_id)  
    mark\_complete(node.id, "W2")  
    maybe\_finalize(node.id)

FUNCTION apply\_w3(node, w3\_result):  
    *\# pragmatic edges*  
    FOR (cand\_id, label) IN w3\_result.pragmatic\_edges:  
        IF label \!= "no\_relation" AND \[cand\_id, label\] NOT IN node.edges.pragmatic:  
            node.edges.pragmatic.append(\[cand\_id, label\])  
            bump\_recurrence(cand\_id)  
    mark\_complete(node.id, "W3")  
    maybe\_finalize(node.id)

FUNCTION apply\_w4(node, w4\_result):  
    *\# state-node linking*  
    scratch \= turn\_scratch\[node.id\]  
    IF node.state\_node\_links.creates IS empty AND scratch\["pending\_state\_node\_creates"\] IS empty:  
        FOR c IN w4\_result.creates:  
            sn\_id \= new\_id()  
            scratch\["pending\_state\_node\_creates"\].append({id: sn\_id, type: c.state\_type, label: c.label})  
            node.state\_node\_links.creates.append(sn\_id)

    *\# UPDATES \- reading sn.status to validate is safe (reads don't need to be deferred); writing it is not, so only the intent is staged here.*  
    FOR u IN w4\_result.updates:  
        IF \[u.state\_node\_id, u.new\_status\] NOT IN node.state\_node\_links.updates:  
            sn \= state\_nodes\[u.state\_node\_id\]  
            IF sn.status IN TERMINAL\_STATUSES\[sn.type\]:  
                log\_warning("update rejected \- terminal node")  
                CONTINUE  
            ELSE IF u.new\_status NOT IN VALID\_STATUSES\[sn.type\]:  
                log\_warning("invalid status")  
                CONTINUE  
            ELSE:  
                node.state\_node\_links.updates.append(\[sn.id, u.new\_status\])   *\# staged only*

    *\# RELATES \- staged only (same reason as UPDATES)*  
    FOR r IN w4\_result.relates:  
        IF r.relation NOT IN RELATION\_TYPES:  
            log\_warning("invalid relation")  
            CONTINUE  
        IF \[r.state\_node\_id, r.relation\] NOT IN node.state\_node\_links.relates:  
            node.state\_node\_links.relates.append(\[r.state\_node\_id, r.relation\])   *\# staged only*

    mark\_complete(node.id, "W4")  
    maybe\_finalize(node.id)

FUNCTION apply\_w5(node, w5\_result):  
    *\# summary \+ reference*  
    node.summary \= w5\_result.summary  
    node.reference \= w5\_result.reference  
    mark\_complete(node.id, "W5")  
    maybe\_finalize(node.id)

### Phase 3: Turn-Completion Coordinator

Tracks per-node completion across all six slots (EMBED, W1–W5); finalizes exactly once. This is also where every deferred target-write from Phase 1 actually lands: both epistemic-status back-propagation (via pragmatic edges, W3) and state-node back-propagation (via W4) happen here, after the source node is durably committed, for the same atomicity reason in both cases.

*(**Note**: this section is agnostic to the wave ordering that decides* when *each call gets dispatched (5.7, "Turn orchestration"). It only tracks* whether *each of the six slots has landed, and finalizes once they all have, regardless of what order they arrived in.)*

FUNCTION mark\_complete(node\_id, slot):  
    tracker\[node\_id\]\[slot\] \= "ok"

FUNCTION mark\_timeout(node\_id, slot):  
    IF tracker\[node\_id\]\[slot\] \== "pending":  
        tracker\[node\_id\]\[slot\] \= "timeout"  
    maybe\_finalize(node\_id)

FUNCTION maybe\_finalize(node\_id):  
    IF node\_id NOT IN pending\_nodes:  
        RETURN  
    node \= pending\_nodes\[node\_id\]  
    IF NOT all(s IN {"ok", "timeout"} FOR s IN tracker\[node\_id\].values()):  
        RETURN  
    completion\_log.write(node\_id, dict(tracker\[node\_id\]))  
    graph.add(node)

    *\# \---- Epistemic-status back-propagation (3.5) \----*  
    FOR (cand\_id, label) IN node.edges.pragmatic:  
        IF label IN EPISTEMIC\_TRIGGER\_LABELS:   *\# revises / resolves / contradicts*  
            target \= graph.get(cand\_id)  
            new\_status \= resolve\_new\_status(target.epistemic\_status, label)   *\# (3.5)'s table*  
            IF new\_status \!= target.epistemic\_status:  
                target.epistemic\_status \= new\_status  
            target.epistemic\_history.append(\[node.id, label, new\_status\])

    FOR spec IN turn\_scratch\[node\_id\]\["pending\_state\_node\_creates"\]:  
        state\_nodes\[spec.id\] \= {  
            type: spec.type,  
            label: spec.label,  
            embedding: embed(spec.label),  
            creation\_turn: node.id,  
            status: DEFAULT\_STATUS\_BY\_TYPE\[spec.type\],   *\# "active" or "open" per type (3.3.1)*  
            last\_updated\_turn: {"updates": \[\], "relates": \[\]},  
        }  
        state\_index.add(spec.id, state\_nodes\[spec.id\].embedding)

    FOR (sn\_id, new\_status) IN node.state\_node\_links.updates:  
        sn \= state\_nodes\[sn\_id\]  
        sn.status \= new\_status  
        sn.last\_updated\_turn.updates.append(\[node.id, new\_status\])   *\# .updates, not a flat append (3.3)*

    FOR (sn\_id, relation) IN node.state\_node\_links.relates:  
        sn \= state\_nodes\[sn\_id\]  
        sn.last\_updated\_turn.relates.append(\[node.id, relation\])   *\# .relates, not a flat append (3.3)*

    ann\_index.add(node.id, node.embedding)

*\# turn\_scratch only contains temporary data, so nothing needs to be removed from the node. This simply cleans up the scratch map after use.*  
    turn\_scratch.pop(node\_id)

    pending\_nodes.pop(node\_id)  
    RETURN node

FUNCTION resolve\_new\_status(current\_status, label):  
    *\# Implements 3.5's state-dependent transitions table exactly.*  
    IF label \== "revises":  
        RETURN "superseded"   *\# always wins, regardless of current status*  
    IF current\_status \== "superseded":  
        RETURN "superseded"   *\# terminal against resolves/contradicts*  
    IF label \== "resolves":  
        RETURN "resolved"     *\# clears open or contested alike*  
    IF label \== "contradicts":  
        RETURN "contested"    *\# from open, resolved, or contested itself*

## 5.8 Extraction Pipeline Diagram

*(The diagram will be kept on updated with need)*

---

# 6\. Open Questions and Risks Carried Into Phase 3

1. **Which turns belong in graph memory at all?** Not every turn is useful, a human user may ask off-topic or mistaken questions, and storing those costs storage and adds unnecessary comparison/evaluation overhead. There is not yet a rule for deciding what enters the graph in the first place; this predates the new schema and is not fixed by it.

2. **Epistemic status is tracked at the whole-node level, not per claim.** A node that bundles a durable fact with a later-revised interpretation gets both marked superseded together, even though only the interpretation was wrong. Claim-level tracking would fix this but is out of scope; see the same limitation noted in (3.5).

3. **Multi-call vs. combined-call is provisional** (5.2). The multi-call design is the working default for writing prompts, to be compared empirically in Phase 4, not a final architectural choice.

4. **Proposed edge-strength values are unfit.** All three sets of strength scores in (3.4), hierarchical, pragmatic, and interaction-state node relations encode a working assumption by analogy, not a measured quantity. They are a starting point for the Phase 4 parameter sweep, not a finding.

5. **Async concurrency needs confirming, not assuming.** The latency estimates in (5.3) assume the runtime genuinely fires the W2/W3/W4/W5 calls concurrently (W2 and W3 depend on W1, not on each other); if it accidentally serialises them, the "wall-clock ≈ slowest call" claim does not hold.

6. **The baseline neutrality risk is unresolved by design alone.** As stated in (5.4), a richer schema does not automatically overcome the displacement effect the thesis measured. This is the central empirical question the rest of this project needs to answer, and it is exactly why the Phase 3 validation corpus (item 8 below) matters.

7. **The subcase/supercase direction fix (3.4) needs a source-code cross-check.** This report can only fix its own documentation; if the actual edge-classification implementation used the old, backwards reading, that's a real bug independent of this report, and graph expansion (5.5) would currently be traversing the hierarchy the wrong way. **Do not assume the fix in (3.4) is already true of the running code, verify it.**

8. **Evaluation-corpus choice matters more than usual here.** Per the workplan (Phase 3.1), the validation corpus should be conversations with genuine topic development, technical support or tutoring dialogues, for instance, rather than an independent-question benchmark like LoCoMo, because LoCoMo's lack of discourse structure is the documented reason the baseline graph came out thin and neutral (1, 5.4). **Deferred by direction: to be worked out during Phase 3 itself, not pre-decided here.**

9. **ANSWER\_PROFILE and EDGE\_PROFILE's parameter values (5.5) are provisional, and not currently tracked as an open item anywhere else.** N\_recent, K\_semantic, K\_entity, K\_state, and f\_graph for both profiles are first guesses, in the same sense as the edge-strength values. Both profiles are Phase 4 sweep targets.

10. **Turn-serialization is currently assumed, not enforced anywhere, and needs revisiting.** This report currently assumes the next user turn cannot begin until the current turn's answer *and* its full graph write (5.7, 5.8) are both finished. Nothing in the pipeline actually enforces this. It's a simplifying assumption adopted for now, not a designed constraint.

---

# 7\. Phase 3 Readiness Checklist

What Phase 1 and Phase 2 hand to Phase 3, mapped against the workplan's Phase 3 tasks:

| Phase 3 task | What this report provides | Still needed before/during Phase 3 |
| :---- | :---- | :---- |
| 3.1 Manual validation on a small corpus | Full node/edge/state-node schema (3), a examples with full edge/state-node-type coverage (4.1, 4.2), and draft prompts for every extraction task (5.6) | A validation corpus with genuine topic development ((6) item 7); a small set of real big multi-turn conversations to run the pipeline on |
| 3.1 Precision/recall of entity extraction | Entity schema and R1/W1 prompts (3.2, 5.6) | Ground-truth entity annotations on the chosen corpus |
| 3.1 Whether state nodes are created/merged sensibly | State-node schema and W4 prompt, now the sole path for state-node relations (3.3, 5.6) | Decision on a validation metric for merge correctness (duplicate state nodes vs. missed updates to an existing one) once real data is available |
| 3.2 Iterate on prompts/schema based on findings | Baseline prompt versions to iterate from (5.6) | The findings themselves, this is explicitly Phase 3 work, not pre-empted here |

# 

---

# References

