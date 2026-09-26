"""Structural consistency checks for conversations/ml_debugging, mirroring
conversations/marathon_trip/validate.py, plus domain entity types from
domain_config.json. (Same file as hpc_support/validate.py; the document
section check only runs when the ground truth names a document.)"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
corpus = json.loads((BASE / "corpus.json").read_text())
gt = json.loads((BASE / "ground_truth.json").read_text())

errors = []

VALID_SPEECH_ACTS = {"factual_question", "clarification_request", "decision", "suggestion",
                      "feedback", "correction", "follow_up", "agreement", "disagreement",
                      "information", "request"}
VALID_HIER = {"subcase", "supercase", "same_level"}
VALID_PRAG = {"revises", "contradicts", "resolves", "depends_on", "references"}
VALID_RELATES = {"supports", "contradicts", "constrained_by", "resolves"}
VALID_ENTITY_TYPES = {"person", "organization", "system", "measurement", "tool", "location", "event", "document"}
VALID_ENTITY_TYPES |= set(json.loads((BASE / "domain_config.json").read_text()))
VALID_STATUSES_BY_TYPE = {
    "goal": {"active", "achieved", "abandoned"},
    "decision": {"active", "revised", "reverted"},
    "constraint": {"active", "lifted", "revised"},
    "open_question": {"open", "resolved"},
}

nodes = gt["interaction_nodes"]
node_ids = list(nodes.keys())
node_order = {nid: i for i, nid in enumerate(node_ids)}

# 1. corpus/ground-truth text equality
corpus_by_id = {c["id"]: c for c in corpus}
if set(corpus_by_id) != set(nodes):
    errors.append(f"ID set mismatch between corpus and ground_truth: {set(corpus_by_id) ^ set(nodes)}")
for nid, gn in nodes.items():
    cn = corpus_by_id.get(nid)
    if not cn:
        continue
    if cn["turns"][0]["text"] != gn["question"] or cn["turns"][1]["text"] != gn["answer"]:
        errors.append(f"{nid}: corpus/ground_truth text mismatch")

# 2. edge target existence & backward-in-time direction
for nid, n in nodes.items():
    for tgt, label in n["edges"]["hierarchical"]:
        if tgt not in nodes:
            errors.append(f"{nid}: hierarchical target {tgt} does not exist")
        elif node_order[tgt] >= node_order[nid]:
            errors.append(f"{nid}: hierarchical edge to {tgt} is not backward in time")
        if label not in VALID_HIER:
            errors.append(f"{nid}: invalid hierarchical label {label}")
    for tgt, label in n["edges"]["pragmatic"]:
        if tgt not in nodes:
            errors.append(f"{nid}: pragmatic target {tgt} does not exist")
        elif node_order[tgt] >= node_order[nid]:
            errors.append(f"{nid}: pragmatic edge to {tgt} is not backward in time")
        if label not in VALID_PRAG:
            errors.append(f"{nid}: invalid pragmatic label {label}")

# 3 & 12. state-node reference validity + creation/update provenance
sn = gt["state_nodes"]
sn_creates_seen = {}
sn_updates_seen = {sid: [] for sid in sn}
sn_relates_seen = {sid: [] for sid in sn}
for nid, n in nodes.items():
    links = n.get("state_node_links", {})
    for sid in links.get("creates", []):
        if sid not in sn:
            errors.append(f"{nid}: creates unknown state node {sid}")
        else:
            sn_creates_seen[sid] = nid
    for sid, status in links.get("updates", []):
        if sid not in sn:
            errors.append(f"{nid}: updates unknown state node {sid}")
        else:
            sn_updates_seen[sid].append([nid, status])
    for sid, relation in links.get("relates", []):
        if sid not in sn:
            errors.append(f"{nid}: relates unknown state node {sid}")
        elif relation not in VALID_RELATES:
            errors.append(f"{nid}: invalid relates label {relation} for {sid}")
        else:
            sn_relates_seen[sid].append([nid, relation])

for sid, sdata in sn.items():
    if sn_creates_seen.get(sid) != sdata["creation_turn"]:
        errors.append(f"{sid}: creation_turn {sdata['creation_turn']} != actual creating node {sn_creates_seen.get(sid)}")
    if sdata["status"] not in VALID_STATUSES_BY_TYPE[sdata["type"]]:
        errors.append(f"{sid}: status {sdata['status']} invalid for type {sdata['type']}")
    if sn_updates_seen[sid] != sdata["last_updated_turn"]["updates"]:
        errors.append(f"{sid}: last_updated_turn.updates mismatch: {sn_updates_seen[sid]} vs {sdata['last_updated_turn']['updates']}")
    if sn_relates_seen[sid] != sdata["last_updated_turn"]["relates"]:
        errors.append(f"{sid}: last_updated_turn.relates mismatch: {sn_relates_seen[sid]} vs {sdata['last_updated_turn']['relates']}")

# 4. bidirectional entity mention consistency + 11. entity-type validity
ents = gt["entities"]
ent_mentions_from_nodes = {eid: [] for eid in ents}
for nid, n in nodes.items():
    for eid in n["named_entities"]:
        if eid not in ents:
            errors.append(f"{nid}: named_entities references unknown entity {eid}")
        else:
            ent_mentions_from_nodes[eid].append(nid)
for eid, edata in ents.items():
    if edata["type"] not in VALID_ENTITY_TYPES:
        errors.append(f"{eid}: invalid entity type {edata['type']}")
    if ent_mentions_from_nodes[eid] != edata["mentioned_in"]:
        errors.append(f"{eid}: mentioned_in mismatch: {ent_mentions_from_nodes[eid]} vs {edata['mentioned_in']}")

# 5. citation-bracket/field consistency
for nid, n in nodes.items():
    brackets = set(re.findall(r"\[(N_\d+)\]", n["answer"]))
    cites = set(n["citations"])
    if brackets != cites:
        errors.append(f"{nid}: citation mismatch, brackets={brackets} citations={cites}")
    for c in cites:
        if c not in nodes:
            errors.append(f"{nid}: citation to unknown node {c}")
        elif node_order[c] >= node_order[nid]:
            errors.append(f"{nid}: citation to {c} is not backward in time")

# 6. recurrence-count correctness
recompute = {nid: 0 for nid in nodes}
for nid, n in nodes.items():
    for tgt, _ in n["edges"]["hierarchical"]:
        recompute[tgt] = recompute.get(tgt, 0) + 1
    for tgt, _ in n["edges"]["pragmatic"]:
        recompute[tgt] = recompute.get(tgt, 0) + 1
for nid, n in nodes.items():
    if n["recurrence_count"] != recompute[nid]:
        errors.append(f"{nid}: recurrence_count {n['recurrence_count']} != computed {recompute[nid]}")
    if n["retrieval_count"] != n["recurrence_count"]:
        errors.append(f"{nid}: retrieval_count != recurrence_count")

# 10. speech-act validity
for nid, n in nodes.items():
    if n["speech_act"] not in VALID_SPEECH_ACTS:
        errors.append(f"{nid}: invalid speech_act {n['speech_act']}")

# epistemic_history sanity: first entry must be [nid, "creation", status]
for nid, n in nodes.items():
    hist = n["epistemic_history"]
    if not hist or hist[0] != [nid, "creation", hist[0][2]]:
        errors.append(f"{nid}: epistemic_history first entry malformed: {hist[:1]}")
    if hist[-1][2] != n["epistemic_status"]:
        errors.append(f"{nid}: epistemic_status {n['epistemic_status']} != last history entry {hist[-1]}")

# 13. grounding sections must exist in the guide (as a "## N." or "### N.M" heading)
guide_sections = set()
if gt.get("document"):
    guide = (BASE / gt["document"]).read_text()
    guide_sections = {f"§{m}" for m in re.findall(r"^#{2,3} (\d+(?:\.\d+)?)\.? ", guide, re.M)}
for nid, n in nodes.items():
    for sec in n.get("grounding_sections", []):
        if sec not in guide_sections:
            errors.append(f"{nid}: grounding section {sec} not found in {gt.get('document')}")

print(f"Checked {len(nodes)} interaction nodes, {len(sn)} state nodes, {len(ents)} entities, "
      f"{len(guide_sections)} guide sections.")
if errors:
    print(f"\n{len(errors)} ERROR(S):")
    for e in errors:
        print(" -", e)
else:
    print("All checks passed.")
