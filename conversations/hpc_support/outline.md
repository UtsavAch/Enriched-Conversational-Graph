# `hpc_support`: outline

**Domain:** a new PhD student (Tomás) onboards to the institute's HPC cluster "Aurora" with an
assistant that answers from the **Aurora User Guide** (the RAG document set). **50 turns**,
2026-10-01 → 2026-10-29.

**Why this corpus:** it's the INESC TEC use case from the workplan (support over a real document set)
and the only corpus that exercises `cites` / document chunks. Troubleshooting also produces clean
error → diagnosis → fix `resolves` chains. One assistant claim contradicts the docs, which gives a
`contradicts` that's grounded in a citation.

## Prerequisite: the document set

Write `main/data/documents/aurora_user_guide.md` **first** (about 3–4k words), with stable section ids
that turns cite as `DOC_aurora#§x.y`:

| § | Section | Facts the corpus depends on |
|---|---|---|
| 2.1 | Accounts & SSH | keys only, no passwords; `ssh tomas@aurora.inst` |
| 2.2 | Login nodes | **no compute on login nodes**; processes >10 min CPU are killed |
| 3.1 | Environment modules | `module avail`, `module load python/3.11` |
| 3.2 | Conda | allowed; install envs under `$PROJECT`, **not `$HOME`** (10 GB home quota) |
| 4.1 | SLURM basics | `sbatch`, `squeue`, `sacct` |
| 4.2 | Resource requests | default mem 2 GB/core; `--mem`; OOM → `oom-kill` in `sacct` |
| 4.3 | Job arrays | `--array=1-100%10` |
| 5.1 | `$HOME` | 10 GB, backed up |
| 5.2 | `$PROJECT` | 1 TB per group, backed up, not purged |
| 5.3 | `$SCRATCH` | 50 TB, fast, **files older than 30 days purged, no backup** |
| 6.1 | GPU partitions | `gpu-a100` (max 24 h), `gpu-short` (max 2 h, higher priority) |
| 6.2 | Checkpointing | required for jobs expected >24 h |
| 7.1 | Apptainer | build `.sif` locally or with `--fakeroot`; recommended over conda for GPU jobs |
| 8.1 | Fair-share | usage decays with 7-day half-life |
| 9.1 | Support | tickets via helpdesk; office hours Thu |

## Domain config

| Type | Description |
|---|---|
| `partition` | A named SLURM partition/queue (e.g. gpu-a100). |
| `command` | A named CLI command or flag (e.g. sbatch, --mem). |
| `filesystem` | A named storage area (e.g. $HOME, $SCRATCH). |

## Entities (planned)

E_1 person Tomás · E_2 system Aurora · E_3 document Aurora User Guide · E_4 partition gpu-a100 ·
E_5 partition gpu-short · E_6 filesystem $HOME · E_7 filesystem $PROJECT · E_8 filesystem $SCRATCH ·
E_9 command sbatch · E_10 command --mem · E_11 tool conda · E_12 tool Apptainer ·
E_13 tool SLURM · E_14 command sacct · E_15 measurement 24 h walltime limit ·
E_16 measurement 10 GB home quota · E_17 person Inês (group sysadmin contact) · E_18 organization helpdesk

## State nodes

| id | type | label | lifecycle |
|---|---|---|---|
| SN_1 | goal | Run the protein-embedding training pipeline on Aurora GPUs | +N_1 → achieved N_48 |
| SN_2 | constraint | No compute on login nodes | +N_5 (probe target, never revisited) |
| SN_3 | decision | Use a conda env installed in `$HOME` | +N_10 → revised N_24 (moved to `$PROJECT`) → reverted N_43 |
| SN_4 | decision | Keep the training dataset in `$SCRATCH` | +N_13 → revised N_36 (copy of record in `$PROJECT`, working copy in `$SCRATCH`) |
| SN_5 | open_question | Why do jobs die with no Python traceback? | +N_18 → resolved N_21 |
| SN_6 | decision | Request `--mem=32G` per job | +N_21 → revised N_29 (64G for full dataset) |
| SN_7 | decision | Use the `gpu-a100` partition | +N_27 |
| SN_8 | constraint | 24 h walltime per job | +N_28 → lifted N_46 (checkpoint/resume makes it non-binding; see note) |
| SN_9 | open_question | How to handle training that needs ~60 h? | +N_30 → resolved N_32 |
| SN_10 | decision | Checkpoint every 2 h and resubmit with a dependency chain | +N_32 |
| SN_11 | constraint | Project quota 1 TB shared with the group | +N_37 |
| SN_12 | decision | Run GPU jobs in an Apptainer container instead of conda | +N_43 |
| SN_13 | decision | Hyper-parameter sweep as a job array, max 10 concurrent | +N_45 |

*Note on SN_8:* "lifted" here means the constraint stops binding the plan. If you'd rather
keep lifted for a policy change, replace N_46 with Inês getting a 72 h reservation approved.

## Turn arc

| Turn | Date | Act | Gist | Edges / state · cites |
|---|---|---|---|---|
| **Access & environment** | | | | |
| N_1 | 10-01 | request | Tomás: got an Aurora account, wants to train a protein-embedding model on GPUs | S: +SN_1 |
| N_2 | 10-01 | factual_question | How to log in? | H: N_1 subcase · P: N_1 depends_on · §2.1 |
| N_3 | 10-01 | information | SSH key setup | P: N_2 resolves · §2.1 |
| N_4 | 10-01 | factual_question | Can I just run a quick Python test on the login node? | H: N_1 subcase · §2.2 |
| N_5 | 10-01 | information | No, login nodes are for editing/submitting; use `srun --pty` | P: N_4 resolves · S: +SN_2 · §2.2 |
| N_6 | 10-02 | factual_question | Which Python is available? | H: N_1 subcase · §3.1 |
| N_7 | 10-02 | information | `module load python/3.11` | P: N_6 resolves · §3.1 |
| N_8 | 10-02 | factual_question | Needs PyTorch + custom libs; module or conda? | H: N_6 subcase · P: N_7 depends_on · §3.2 |
| N_9 | 10-02 | information | Conda is allowed (assistant omits the where-to-install rule) | P: N_8 resolves · §3.2 |
| N_10 | 10-02 | decision | Tomás installs env in `~/envs` (`$HOME`) | P: N_9 depends_on · S: +SN_3 |
| N_11 | 10-02 | factual_question | Where should the 400 GB dataset live? | H: N_1 subcase · §5 |
| N_12 | 10-02 | information | Assistant: "`$SCRATCH` is fast and large, good for datasets" (**omits purge policy**) | P: N_11 resolves · §5.3 |
| N_13 | 10-02 | decision | Dataset copied to `$SCRATCH` only | P: N_12 depends_on · S: +SN_4 |
| **First jobs & failures** | | | | |
| N_14 | 10-05 | request | Help writing a first `sbatch` script | H: N_1 subcase · §4.1 |
| N_15 | 10-05 | information | Minimal script | P: N_14 resolves · §4.1 |
| N_16 | 10-05 | follow_up | Job pending forever? | H: N_14 subcase · P: N_15 depends_on |
| N_17 | 10-05 | information | Pending reason `Resources`; wait or use smaller request | P: N_16 resolves · §4.1 |
| N_18 | 10-06 | factual_question | Job dies after 3 min, no traceback | H: N_14 subcase · S: +SN_5 |
| N_19 | 10-06 | clarification_request | Assistant: what does `sacct` show? | P: N_18 depends_on · §4.1 |
| N_20 | 10-06 | information | `OUT_OF_MEMORY` state | P: N_19 depends_on |
| N_21 | 10-06 | decision | Default 2 GB/core → request `--mem=32G` | P: N_18 resolves · S: SN_5→resolved, +SN_6 · §4.2 |
| N_22 | 10-06 | agreement | Job runs | P: N_21 depends_on |
| N_23 | 10-08 | information | Error: "Disk quota exceeded" in `$HOME` | H: N_10 subcase · P: N_10 references |
| N_24 | 10-08 | correction | Assistant: guide says conda envs go in `$PROJECT` (10 GB home quota); move env | P: N_9 contradicts, N_23 resolves · S: SN_3→revised · §3.2, §5.1 |
| N_25 | 10-08 | follow_up | How to move a conda env without breaking it? | H: N_24 subcase · P: N_24 depends_on |
| N_26 | 10-08 | information | Recreate from `environment.yml` | P: N_25 resolves |
| **GPUs & long training** | | | | |
| N_27 | 10-12 | decision | Use `gpu-a100` | H: N_14 same_level · P: N_1 depends_on · S: +SN_7 · §6.1 |
| N_28 | 10-12 | information | Max walltime 24 h on gpu-a100 | H: N_27 subcase · S: +SN_8 · §6.1 |
| N_29 | 10-12 | information | Full dataset OOMs at 32G; raise to 64G | P: N_21 revises · S: SN_6→revised · §4.2 |
| N_30 | 10-12 | factual_question | Training needs ~60 h; what now? | H: N_28 subcase · P: N_28 depends_on · S: +SN_9 |
| N_31 | 10-12 | information | Checkpointing is required >24 h | P: N_30 depends_on · §6.2 |
| N_32 | 10-12 | decision | Checkpoint every 2 h, resubmit with `--dependency=afterany` | P: N_30 resolves · S: SN_9→resolved, +SN_10 · §6.2 |
| N_33 | 10-13 | follow_up | Can debug runs go faster? | H: N_27 same_level · §6.1 |
| N_34 | 10-13 | information | `gpu-short` (2 h, higher priority) for debugging | P: N_33 resolves · ~SN_7 supports · §6.1 |
| **The scratch purge** | | | | |
| N_35 | 10-19 | information | Half the dataset vanished from `$SCRATCH` | H: N_13 subcase · P: N_13 references |
| N_36 | 10-19 | correction | Assistant: §5.3 says 30-day purge, no backup; N_12 was incomplete. Copy of record → `$PROJECT` | P: N_12 contradicts, N_35 resolves · S: SN_4→revised · §5.3, §5.2 |
| N_37 | 10-19 | information | `$PROJECT` is 1 TB shared by the group | H: N_36 subcase · S: +SN_11 · §5.2 |
| N_38 | 10-19 | factual_question | Will 400 GB fit alongside the group's data? | H: N_37 subcase · P: N_37 depends_on |
| N_39 | 10-19 | information | Inês says 350 GB free → compress shards | P: N_38 resolves · ~SN_11 constrained_by |
| N_40 | 10-20 | follow_up | How to keep scratch copy fresh? | H: N_36 subcase · P: N_36 depends_on |
| N_41 | 10-20 | information | `touch`-ing is against policy; re-stage per job from `$PROJECT` | P: N_40 resolves · §5.3 |
| **Containers, arrays, wrap-up** | | | | |
| N_42 | 10-22 | information | Conda env breaks on GPU nodes (CUDA mismatch) | H: N_27 subcase · P: N_24 references |
| N_43 | 10-22 | decision | Switch to Apptainer image; drop the conda env | P: N_42 resolves · S: SN_3→reverted, +SN_12 · §7.1 |
| N_44 | 10-22 | factual_question | How to build the `.sif` without root? | H: N_43 subcase · P: N_43 depends_on · §7.1 |
| N_45 | 10-26 | decision | Sweep 40 configs as a job array, 10 at a time | H: N_14 same_level · P: N_32 depends_on · S: +SN_13 · §4.3 |
| N_46 | 10-26 | information | With checkpoint/resume, 24 h limit no longer blocks anything | P: N_30 references · S: SN_8→lifted |
| N_47 | 10-27 | factual_question | Priority dropped after the sweep? | H: N_45 subcase · §8.1 |
| N_48 | 10-28 | information | Fair-share decay explained; first full training done | P: N_47 resolves · S: SN_1→achieved · §8.1 |
| N_49 | 10-28 | request | "Write me a checklist of everything for my labmate" | H: N_5 supercase, N_24 supercase, N_36 supercase, N_43 supercase |
| N_50 | 10-29 | agreement | Thanks; opens a ticket to add the purge warning to the quickstart | P: N_49 depends_on · §9.1 |

**Label targets:** subcase ~22 · same_level ~4 · supercase 4 · depends_on ~20 · references ~5 ·
resolves ~20 · revises 1 · contradicts 2.

## Probes

| id | Question | Target | expected_any | forbidden_any | from | Designed to defeat |
|---|---|---|---|---|---|---|
| p1 | Where should Tomás keep the master copy of his dataset? | SN_4 | "$PROJECT" | "only in $SCRATCH", "scratch is fine" | 36 | anti-semantic (N_12 is the most similar, and wrong) |
| p2 | Is it safe to keep files in $SCRATCH long-term? | SN_4 | "purged", "30 days" | "persistent", "safe long-term" | 36 | anti-semantic |
| p3 | Can Tomás run a short Python test directly on the login node? | SN_2 | "no", "srun" | "yes, it's fine" | 5 | anti-recency |
| p4 | How should Tomás set up his software environment for GPU jobs now? | SN_12 | "Apptainer", "container" | "conda env in $HOME", "~/envs" | 43 | anti-semantic |
| p5 | How much memory should the full-dataset training job request? | SN_6 | "64G", "64 GB" | "32G" | 29 | anti-semantic |
| p6 | How does Tomás run a ~60 h training given the partition limit? | SN_10 | "checkpoint", "dependency" | "request 60 hours", "ask for longer walltime" | 32 | anti-hierarchical |
| p7 | Which partition should quick debug runs use? | SN_7 | "gpu-short" | — | 34 | anti-recency |
| p8 | How should the 40-config hyper-parameter sweep be submitted? | SN_13 | "job array", "%10" | "40 separate sbatch" | 45 | — |
| p9 | Why did Tomás's first training jobs die with no traceback? | SN_5 | "out of memory", "OOM", "2 GB" | "Python error", "bug in the code" | 21 | anti-recency |
