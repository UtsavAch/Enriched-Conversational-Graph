"""Construct conversations/hpc_support/{corpus.json, ground_truth.json}.

Same method as conversations/marathon_trip/build.py: raw per-node fields are
authored below; recurrence_count, retrieval_count, epistemic_status/history,
entities.mentioned_in, and state_nodes status/last_updated_turn are derived
programmatically from the authored edges/links.

Document-grounded corpus: the assistant answers from aurora_user_guide.md. Each
node records the guide sections it relies on in ``docs`` (emitted as
``grounding_sections``); see schema_findings for why these are section ids and
not DocumentChunk ids. Outline: outline.md in this folder.
"""
import json
from collections import Counter
from pathlib import Path

INITIAL_STATUS = {"goal": "active", "decision": "active", "constraint": "active", "open_question": "open"}
OPEN_DEFAULT_ACTS = {"factual_question", "clarification_request"}

ENTITIES = {
    "E_1": {"type": "person", "name": "Tomás"},
    "E_2": {"type": "system", "name": "Aurora"},
    "E_3": {"type": "document", "name": "Aurora User Guide"},
    "E_4": {"type": "partition", "name": "gpu-a100"},
    "E_5": {"type": "partition", "name": "gpu-short"},
    "E_6": {"type": "filesystem", "name": "$HOME"},
    "E_7": {"type": "filesystem", "name": "$PROJECT"},
    "E_8": {"type": "filesystem", "name": "$SCRATCH"},
    "E_9": {"type": "command", "name": "sbatch"},
    "E_10": {"type": "command", "name": "--mem"},
    "E_11": {"type": "tool", "name": "conda"},
    "E_12": {"type": "tool", "name": "Apptainer"},
    "E_13": {"type": "tool", "name": "SLURM"},
    "E_14": {"type": "command", "name": "sacct"},
    "E_15": {"type": "measurement", "name": "24-hour walltime limit"},
    "E_16": {"type": "measurement", "name": "10 GB home quota"},
    "E_17": {"type": "person", "name": "Inês"},
    "E_18": {"type": "organization", "name": "Research Computing helpdesk"},
}

STATE_NODE_DEFS = {
    "SN_1": {"type": "goal", "label": "Run the protein-embedding training pipeline on Aurora GPUs"},
    "SN_2": {"type": "constraint", "label": "No computation on the login nodes"},
    "SN_3": {"type": "decision", "label": "Use a conda environment installed in $HOME (~/envs)"},
    "SN_4": {"type": "decision", "label": "Keep the training dataset in $SCRATCH"},
    "SN_5": {"type": "open_question", "label": "Why do training jobs die after a few minutes with no Python traceback?"},
    "SN_6": {"type": "decision", "label": "Request --mem=32G per training job"},
    "SN_7": {"type": "decision", "label": "Run training on the gpu-a100 partition"},
    "SN_8": {"type": "constraint", "label": "Jobs on gpu-a100 are limited to 24 hours of walltime"},
    "SN_9": {"type": "open_question", "label": "How to run a training that needs about 60 hours given the partition limit?"},
    "SN_10": {"type": "decision", "label": "Checkpoint every 2 hours and resubmit via an afterany dependency chain"},
    "SN_11": {"type": "constraint", "label": "$PROJECT quota is 1 TB shared by the whole group"},
    "SN_12": {"type": "decision", "label": "Run GPU jobs inside an Apptainer container instead of a conda environment"},
    "SN_13": {"type": "decision", "label": "Run the 40-configuration hyper-parameter sweep as a job array, max 10 concurrent"},
}

LABEL_OVERRIDES = {
    ("SN_3", "N_24"): "Use a conda environment installed under $PROJECT/envs (originally: in $HOME, ~/envs)",
    ("SN_4", "N_36"): "Keep the master copy of the dataset in $PROJECT and stage a working copy to $SCRATCH per job (originally: dataset kept in $SCRATCH only)",
    ("SN_6", "N_29"): "Request --mem=64G per training job for the full dataset (originally: --mem=32G)",
}

NODES = [
    # ---- Access & environment ------------------------------------------------
    dict(id="N_1", date="2026-10-01",
         q="Hi! I'm Tomás, a new PhD student. I just got my account on Aurora and I need to train a protein-embedding model on the GPUs there for my first project. I've never used a cluster before, so where do I even start?",
         a="Welcome! The short path is: log in with an SSH key, set up a software environment, put your data in the right storage area, then submit training as SLURM batch jobs on a GPU partition. The Aurora User Guide covers each step; it also flags four sections that cause most new-user problems (login-node limits, where to install conda, memory requests, and the scratch purge policy). Let's go step by step.",
         act="request", ents=["E_1", "E_2", "E_3"], cites=[], docs=["§1"], hier=[], prag=[],
         creates=["SN_1"], updates=[], relates=[],
         summary="Tomás sets the goal of training a protein-embedding model on Aurora GPUs; assistant outlines the onboarding path.",
         ref="Goal: train on Aurora GPUs"),
    dict(id="N_2", date="2026-10-01",
         q="OK, first things first. How do I actually log in?",
         a="Aurora only accepts SSH keys; passwords are disabled. Generate a key on your laptop with `ssh-keygen -t ed25519`, upload the public key (`~/.ssh/id_ed25519.pub`) in the Research Computing portal under Profile → SSH keys, then connect with `ssh <username>@login.aurora.inst`.",
         act="factual_question", ents=["E_2"], cites=[], docs=["§2.1"], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks how to log in; answer: SSH key authentication via the portal.",
         ref="Login method asked"),
    dict(id="N_3", date="2026-10-01",
         q="Uploaded the key but the login still gets rejected. Did I do something wrong?",
         a="Probably not. New keys take up to 15 minutes to propagate to the login nodes. Wait a bit and try again, and make sure you uploaded the .pub file, not the private key. Never copy your private key onto Aurora itself.",
         act="follow_up", ents=[], cites=[], docs=["§2.1"], hier=[["N_2", "subcase"]], prag=[["N_2", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Login rejected right after uploading the key; explained by the 15-minute propagation delay.",
         ref="Key propagation delay"),
    dict(id="N_4", date="2026-10-01",
         q="I'm in. Can I just run a quick Python test of my data loader right here on the login node? It only takes a few minutes.",
         a="Please don't. The login nodes are shared by every user and are only for editing, managing files and submitting jobs. Any process using more than 10 minutes of CPU time there is killed automatically, and repeated violations can get the account suspended.",
         act="factual_question", ents=["E_2"], cites=[], docs=["§2.2"], hier=[["N_1", "subcase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Asks whether a quick test can run on the login node.",
         ref="Login-node test asked"),
    dict(id="N_5", date="2026-10-01",
         q="Got it. So what's the right way to do a quick interactive test then?",
         a="Ask SLURM for an interactive session on a compute node, e.g. `srun --partition=cpu --time=00:30:00 --cpus-per-task=4 --mem=8G --pty bash`. You get a shell on a real compute node and can test freely. Treat it as a hard rule from now on: no computation on login nodes.",
         act="follow_up", ents=["E_13"], cites=[], docs=["§2.2"], hier=[["N_4", "subcase"]], prag=[["N_4", "resolves"]],
         creates=["SN_2"], updates=[], relates=[],
         summary="Interactive srun session recommended; establishes the no-compute-on-login-nodes rule.",
         ref="No compute on login nodes"),
    dict(id="N_6", date="2026-10-02",
         q="Next: what Python is available on Aurora?",
         a="Centrally installed software comes as environment modules. Run `module avail` to see everything, and `module load python/3.11` for Python. In batch scripts, start with `module purge` so jobs don't inherit whatever you had loaded interactively.",
         act="factual_question", ents=["E_2"], cites=[], docs=["§3.1"], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks which Python is available; answer: environment modules, python/3.11.",
         ref="Python via modules"),
    dict(id="N_7", date="2026-10-02",
         q="`module load python/3.11` works. Is that enough for everything, or should I add packages to it?",
         a="The module gives you the interpreter and a small standard set of packages; you can't install into it. For anything beyond that, you'll want your own environment.",
         act="follow_up", ents=[], cites=[], docs=["§3.1"], hier=[["N_6", "subcase"]], prag=[["N_6", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Module Python confirmed working but cannot be extended with packages.",
         ref="Module Python limits"),
    dict(id="N_8", date="2026-10-02",
         q="I need PyTorch plus a couple of custom protein libraries. Module or conda?",
         a="For a custom stack like that, conda is the practical option.",
         act="factual_question", ents=["E_11"], cites=[], docs=["§3.2"], hier=[["N_6", "subcase"]], prag=[["N_7", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks whether to use modules or conda for PyTorch plus custom libraries.",
         ref="Module vs conda asked"),
    dict(id="N_9", date="2026-10-02",
         q="Is conda actually allowed on Aurora, though? Some clusters ban it.",
         a="Yes, conda is allowed. Load it with `module load miniforge`, then create and activate your own environment as usual.",
         act="clarification_request", ents=["E_11", "E_2"], cites=[], docs=["§3.2"], hier=[["N_8", "subcase"]], prag=[["N_8", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Confirms conda is allowed via the miniforge module (omits the install-location rule).",
         ref="Conda allowed"),
    dict(id="N_10", date="2026-10-02",
         q="Done: I created the environment in ~/envs/protein with PyTorch and my libraries. Everything imports fine.",
         a="Great, that gives you a working environment. Keep an `environment.yml` exported in your repo so you can recreate it later.",
         act="decision", ents=["E_11", "E_6"], cites=[], docs=["§3.2"], hier=[["N_9", "subcase"]], prag=[["N_9", "depends_on"]],
         creates=["SN_3"], updates=[], relates=[],
         summary="Tomás installs his conda environment in $HOME (~/envs/protein).",
         ref="Conda env in $HOME"),
    dict(id="N_11", date="2026-10-02",
         q="Where should my training data live? It's about 400 GB of protein sequence shards.",
         a="Aurora has three storage areas, $HOME, $PROJECT and $SCRATCH, with very different sizes and rules. 400 GB certainly doesn't fit in $HOME.",
         act="factual_question", ents=["E_6", "E_7", "E_8"], cites=[], docs=["§5"], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks where to store the 400 GB training dataset.",
         ref="Dataset location asked"),
    dict(id="N_12", date="2026-10-02",
         q="So which of the other two is best for a big dataset that training reads over and over?",
         a="$SCRATCH: it's the high-performance parallel filesystem with 50 TB of space, so it's the fastest place for heavy training I/O and large datasets.",
         act="follow_up", ents=["E_8"], cites=[], docs=["§5.3"], hier=[["N_11", "subcase"]], prag=[["N_11", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Assistant recommends $SCRATCH for the dataset for speed (omits the purge policy).",
         ref="Scratch recommended for data"),
    dict(id="N_13", date="2026-10-02",
         q="Perfect, I've copied the whole 400 GB dataset to $SCRATCH and deleted it from my laptop to free space.",
         a="Good. Your training jobs will read it quickly from there.",
         act="decision", ents=["E_8"], cites=[], docs=[], hier=[["N_12", "subcase"]], prag=[["N_12", "depends_on"]],
         creates=["SN_4"], updates=[], relates=[],
         summary="Dataset copied to $SCRATCH as its only copy.",
         ref="Dataset kept only in scratch"),
    # ---- First jobs & failures ------------------------------------------------
    dict(id="N_14", date="2026-10-05",
         q="Now I want to submit my first real job. Can you help me write a batch script?",
         a="Sure. Batch jobs are shell scripts with `#SBATCH` directives at the top, submitted with `sbatch job.sh`. You need at least a job name, partition, time limit and CPU count.",
         act="request", ents=["E_9", "E_13"], cites=[], docs=["§4.1"], hier=[["N_1", "subcase"]], prag=[["N_1", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks for help writing a first SLURM batch script.",
         ref="First batch script asked"),
    dict(id="N_15", date="2026-10-05",
         q="Could you give me a minimal template I can adapt?",
         a="Here's the guide's minimal version: `#SBATCH --job-name=test`, `--partition=cpu`, `--time=01:00:00`, `--cpus-per-task=4`, then `module purge`, `module load python/3.11` and your command. Submit with `sbatch job.sh` and watch it with `squeue -u $USER`.",
         act="request", ents=["E_9"], cites=[], docs=["§4.1"], hier=[["N_14", "subcase"]], prag=[["N_14", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Provides a minimal sbatch template and the squeue command.",
         ref="Minimal sbatch template"),
    dict(id="N_16", date="2026-10-05",
         q="Submitted it, but it's been sitting in PENDING for twenty minutes. Is something broken?",
         a="Check the REASON column in `squeue -u $USER`. What does it say?",
         act="follow_up", ents=[], cites=[], docs=["§4.1"], hier=[["N_14", "subcase"]], prag=[["N_15", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="First job stuck in PENDING.",
         ref="Job pending"),
    dict(id="N_17", date="2026-10-05",
         q="It says `Resources`.",
         a="Then nothing is broken: the resources you asked for simply aren't free yet. It will start when they are. Smaller requests (fewer cores, shorter time) usually start sooner. `Priority` would instead mean other jobs are ahead of yours.",
         act="information", ents=[], cites=[], docs=["§4.1"], hier=[["N_16", "subcase"]], prag=[["N_16", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Pending reason 'Resources' explained; smaller requests start sooner.",
         ref="Pending reason explained"),
    dict(id="N_18", date="2026-10-06",
         q="The job ran this time, but it died after about 3 minutes, and there's no Python traceback in the output file at all. It just stops. Any idea?",
         a="A job that ends abruptly with no traceback is usually killed by the scheduler, not by Python. Let's find out what SLURM thinks happened.",
         act="factual_question", ents=[], cites=[], docs=[], hier=[["N_14", "subcase"]], prag=[],
         creates=["SN_5"], updates=[], relates=[],
         summary="Training job dies after 3 minutes with no traceback.",
         ref="Silent job death"),
    dict(id="N_19", date="2026-10-06",
         q="How do I check what SLURM thinks happened?",
         a="Run `sacct -j <jobid> --format=JobID,State,Elapsed,MaxRSS,ExitCode` and look at the State and MaxRSS columns.",
         act="clarification_request", ents=["E_14"], cites=[], docs=["§4.1"], hier=[["N_18", "subcase"]], prag=[["N_18", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="sacct recommended to inspect the finished job.",
         ref="Use sacct"),
    dict(id="N_20", date="2026-10-06",
         q="State is `OUT_OF_MEMORY`, and MaxRSS is about 7.8 GB. I only asked for 4 CPUs.",
         a="That explains it: with 4 cores and no memory request you only got 8 GB.",
         act="information", ents=["E_14"], cites=[], docs=["§4.2"], hier=[["N_19", "subcase"]], prag=[["N_19", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="sacct shows OUT_OF_MEMORY with MaxRSS ~7.8 GB.",
         ref="OOM state found"),
    dict(id="N_21", date="2026-10-06",
         q="Why only 8 GB? And what should I ask for?",
         a="Without an explicit request, Aurora gives 2 GB per allocated core, so 4 cores = 8 GB, and exceeding it gets the job killed silently. Your data loader alone is close to that. Request memory explicitly: for this setup `--mem=32G` gives plenty of headroom.",
         act="decision", ents=["E_10"], cites=[], docs=["§4.2"], hier=[["N_20", "subcase"]], prag=[["N_18", "resolves"], ["N_20", "depends_on"]],
         creates=["SN_6"], updates=[["SN_5", "resolved"]], relates=[["SN_5", "resolves"]],
         summary="Default 2 GB/core explains the silent kill; decides to request --mem=32G.",
         ref="Request --mem=32G"),
    dict(id="N_22", date="2026-10-06",
         q="Resubmitted with --mem=32G and it's been running for an hour now. Thanks!",
         a="Great. Keep an eye on MaxRSS in sacct after each run so you can size future requests with about 20% headroom.",
         act="agreement", ents=["E_10"], cites=[], docs=["§4.2"], hier=[], prag=[["N_21", "depends_on"]],
         creates=[], updates=[], relates=[["SN_6", "supports"]],
         summary="Job runs successfully with --mem=32G.",
         ref="32G job runs"),
    dict(id="N_23", date="2026-10-08",
         q="New problem: pip suddenly fails inside my environment with 'Disk quota exceeded', and even saving a small file in my home directory fails.",
         a="That's your $HOME quota, which is 10 GB and strictly enforced. Your conda environment in ~/envs [N_10] is almost certainly what's filling it.",
         act="information", ents=["E_6", "E_16"], cites=["N_10"], docs=["§5.1"], hier=[["N_10", "subcase"]], prag=[["N_10", "references"]],
         creates=[], updates=[], relates=[["SN_3", "contradicts"]],
         summary="Disk quota exceeded in $HOME, traced to the conda environment.",
         ref="Home quota exceeded"),
    dict(id="N_24", date="2026-10-08",
         q="But you said conda was fine to use. What should I have done?",
         a="Conda is allowed, but I left out the important part earlier: the guide says to install environments under $PROJECT, not $HOME, because deep-learning environments are typically 5–15 GB and $HOME has a 10 GB quota. So create it as `conda create --prefix $PROJECT/envs/protein python=3.11`. It's also worth pointing caches elsewhere, e.g. `export HF_HOME=$PROJECT/.cache/huggingface`.",
         act="correction", ents=["E_7", "E_11", "E_16"], cites=[], docs=["§3.2", "§5.1"], hier=[["N_23", "subcase"]], prag=[["N_9", "contradicts"], ["N_23", "resolves"]],
         creates=[], updates=[["SN_3", "revised"]], relates=[],
         summary="Corrects the earlier conda advice: environments belong in $PROJECT; the env is moved.",
         ref="Conda env belongs in $PROJECT"),
    dict(id="N_25", date="2026-10-08",
         q="Can I just `mv ~/envs/protein $PROJECT/envs/` to move it?",
         a="No. Conda environments hard-code their own paths, so a moved directory breaks in subtle ways.",
         act="follow_up", ents=["E_11"], cites=[], docs=["§3.2"], hier=[["N_24", "subcase"]], prag=[["N_24", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks whether the environment can simply be moved.",
         ref="Moving env asked"),
    dict(id="N_26", date="2026-10-08",
         q="Then how do I move it without breaking anything?",
         a="Export it with `conda env export > environment.yml`, recreate it with `conda env create --prefix $PROJECT/envs/protein -f environment.yml`, check it imports, then delete ~/envs/protein to free your home quota.",
         act="request", ents=["E_11", "E_7"], cites=[], docs=["§3.2"], hier=[["N_25", "subcase"]], prag=[["N_25", "resolves"]],
         creates=[], updates=[], relates=[],
         summary="Recreate the environment in $PROJECT from environment.yml, then delete the old one.",
         ref="Recreate env from yml"),
    # ---- GPUs & long training -----------------------------------------------------
    dict(id="N_27", date="2026-10-12",
         q="The CPU pipeline works. Time for the real thing: which GPU partition should I use for training?",
         a="For training and production runs, `gpu-a100`: A100 40 GB cards, normal priority. Request GPUs with `--partition=gpu-a100 --gres=gpu:1`, up to 4 per node.",
         act="decision", ents=["E_4"], cites=[], docs=["§6.1"], hier=[["N_14", "same_level"]], prag=[["N_1", "depends_on"]],
         creates=["SN_7"], updates=[], relates=[["SN_1", "supports"]],
         summary="Chooses the gpu-a100 partition for training.",
         ref="Use gpu-a100"),
    dict(id="N_28", date="2026-10-12",
         q="Is there a time limit on gpu-a100?",
         a="Yes: 24 hours maximum walltime per job. Jobs asking for more than that are rejected at submission.",
         act="factual_question", ents=["E_4", "E_15"], cites=[], docs=["§6.1"], hier=[["N_27", "subcase"]], prag=[["N_27", "depends_on"]],
         creates=["SN_8"], updates=[], relates=[],
         summary="gpu-a100 has a 24-hour walltime limit.",
         ref="24 h walltime limit"),
    dict(id="N_29", date="2026-10-12",
         q="The first GPU run on the full dataset got killed with OUT_OF_MEMORY again, even with 32G. MaxRSS says about 51 GB.",
         a="The full dataset needs more host memory than the subset did. With 51 GB peak plus roughly 20% headroom, request `--mem=64G` for the full-dataset runs.",
         act="information", ents=["E_10", "E_14"], cites=[], docs=["§4.2"], hier=[["N_27", "subcase"]], prag=[["N_21", "revises"]],
         creates=[], updates=[["SN_6", "revised"]], relates=[],
         summary="Full-dataset run OOMs at 32G; memory request raised to 64G.",
         ref="Memory raised to 64G"),
    dict(id="N_30", date="2026-10-12",
         q="Bigger problem: I estimate one full training run takes about 60 hours. How can I do that with a 24-hour limit?",
         a="You can't do it in a single job on any partition; you'll need to split the run across several jobs.",
         act="factual_question", ents=["E_15"], cites=[], docs=["§6.1"], hier=[["N_28", "subcase"]], prag=[["N_28", "depends_on"]],
         creates=["SN_9"], updates=[], relates=[["SN_8", "constrained_by"]],
         summary="A ~60 h training run conflicts with the 24 h limit.",
         ref="60 h run vs 24 h limit"),
    dict(id="N_31", date="2026-10-12",
         q="Split it how, exactly? Can't I just ask for a longer reservation?",
         a="Extended reservations exist but only in exceptional cases with PI approval. The standard approach, and a requirement for work over 24 hours, is checkpointing: save model and optimizer state every 1–2 hours so a new job can resume from the last checkpoint.",
         act="clarification_request", ents=[], cites=[], docs=["§6.2"], hier=[["N_30", "subcase"]], prag=[["N_30", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Checkpointing is required for work over 24 hours; reservations are exceptional.",
         ref="Checkpointing required"),
    dict(id="N_32", date="2026-10-12",
         q="OK, so I checkpoint every 2 hours. How do the jobs pick up automatically after each other?",
         a="Chain them with dependencies: `sbatch --dependency=afterany:<jobid> train.sh`, where train.sh always resumes from the latest checkpoint. `afterany` starts the next job even when the previous one hits the time limit, which is exactly what you want here. Three to four chained 24-hour jobs cover the 60 hours.",
         act="decision", ents=["E_9"], cites=[], docs=["§4.4", "§6.2"], hier=[["N_31", "subcase"]], prag=[["N_30", "resolves"], ["N_31", "depends_on"]],
         creates=["SN_10"], updates=[["SN_9", "resolved"]], relates=[["SN_9", "resolves"]],
         summary="Decides on 2-hourly checkpoints with an afterany dependency chain.",
         ref="Checkpoint + dependency chain"),
    dict(id="N_33", date="2026-10-13",
         q="My debug runs sit in the gpu-a100 queue for ages before they start. Is there a faster way to iterate on small tests?",
         a="Yes, there's a partition meant for exactly that.",
         act="follow_up", ents=["E_4"], cites=[], docs=["§6.1"], hier=[["N_27", "same_level"]], prag=[["N_27", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Debug runs wait too long on gpu-a100.",
         ref="Slow debug iterations"),
    dict(id="N_34", date="2026-10-13",
         q="Which one?",
         a="`gpu-short`: same A100 cards, 2-hour maximum, higher priority. Use it for debugging and short tests, and keep `gpu-a100` for the real training chain.",
         act="factual_question", ents=["E_5", "E_4"], cites=[], docs=["§6.1"], hier=[["N_33", "subcase"]], prag=[["N_33", "resolves"]],
         creates=[], updates=[], relates=[["SN_7", "supports"]],
         summary="gpu-short (2 h, high priority) for debugging; gpu-a100 stays for training.",
         ref="gpu-short for debugging"),
    # ---- The scratch purge ----------------------------------------------------
    dict(id="N_35", date="2026-10-19",
         q="Something scary happened. About half of my dataset shards have vanished from $SCRATCH. I didn't delete anything!",
         a="That matches the scratch purge policy. The shards that disappeared are probably the ones your jobs hadn't read recently.",
         act="information", ents=["E_8"], cites=[], docs=["§5.3"], hier=[["N_13", "subcase"]], prag=[["N_13", "references"]],
         creates=[], updates=[], relates=[["SN_4", "contradicts"]],
         summary="Half the dataset shards vanished from $SCRATCH.",
         ref="Scratch files vanished"),
    dict(id="N_36", date="2026-10-19",
         q="Purge policy? You told me scratch was the right place for my dataset!",
         a="I did, and that advice was incomplete, sorry. Scratch is fast, but the guide is explicit: files not accessed in 30 days are deleted automatically, and scratch is not backed up, so it must never hold the only copy of anything. The recommended pattern is to keep the master copy in $PROJECT (backed up, never purged) and stage a working copy to $SCRATCH at the start of each job or job chain.",
         act="correction", ents=["E_8", "E_7"], cites=[], docs=["§5.3", "§5.2"], hier=[["N_35", "subcase"]], prag=[["N_12", "contradicts"], ["N_35", "resolves"]],
         creates=[], updates=[["SN_4", "revised"]], relates=[],
         summary="Corrects the scratch advice: master copy in $PROJECT, per-job working copy staged to $SCRATCH.",
         ref="Master copy in $PROJECT"),
    dict(id="N_37", date="2026-10-19",
         q="Is there enough room in $PROJECT for 400 GB?",
         a="$PROJECT is 1 TB per group, and it's shared by everyone in your group, so check current usage with `aurora-quota` before adding 400 GB and coordinate with your group.",
         act="factual_question", ents=["E_7"], cites=[], docs=["§5.2"], hier=[["N_36", "subcase"]], prag=[["N_36", "depends_on"]],
         creates=["SN_11"], updates=[], relates=[],
         summary="$PROJECT is a 1 TB quota shared by the group.",
         ref="Project quota shared"),
    dict(id="N_38", date="2026-10-19",
         q="aurora-quota shows the group already uses about 650 GB. So 400 GB won't fit?",
         a="1 TB minus 650 GB leaves roughly 350 GB, so the raw 400 GB won't fit as-is. Talk to whoever manages your group's storage before anything else.",
         act="follow_up", ents=["E_7"], cites=[], docs=["§5.2"], hier=[["N_37", "subcase"]], prag=[["N_37", "depends_on"]],
         creates=[], updates=[], relates=[["SN_11", "constrained_by"]],
         summary="Group already uses 650 GB; 400 GB does not fit in the remaining space.",
         ref="400 GB doesn't fit"),
    dict(id="N_39", date="2026-10-19",
         q="I talked to Inês, who manages our group's storage. She confirmed there's 350 GB free and suggested compressing the shards. They compress to about 230 GB.",
         a="That works: 230 GB fits in the 350 GB free. Store the compressed master copy in $PROJECT and decompress into $SCRATCH when staging for a run.",
         act="information", ents=["E_17", "E_7"], cites=[], docs=["§5.2"], hier=[["N_38", "subcase"]], prag=[["N_38", "resolves"]],
         creates=[], updates=[], relates=[["SN_11", "constrained_by"]],
         summary="Compressed dataset (230 GB) fits in the group's free $PROJECT space.",
         ref="Compressed copy fits"),
    dict(id="N_40", date="2026-10-20",
         q="To stop the purge from hitting the scratch copy again, can I just run a nightly `touch` over all the shards?",
         a="Please don't: the guide explicitly prohibits artificially updating access times to dodge the purge, and it can cost you scratch access.",
         act="follow_up", ents=["E_8"], cites=[], docs=["§5.3"], hier=[["N_36", "subcase"]], prag=[["N_36", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Asks whether touching files can keep the scratch copy from being purged.",
         ref="Touch-to-avoid-purge asked"),
    dict(id="N_41", date="2026-10-20",
         q="Then what's the right way to keep a working copy available?",
         a="Re-stage from $PROJECT at the start of each job chain: the first job decompresses the shards into $SCRATCH, and the later jobs in the chain reuse them. If the chain is idle for weeks and the copy gets purged, the next chain simply re-stages it; nothing is lost because the master is in $PROJECT.",
         act="request", ents=["E_7", "E_8"], cites=[], docs=["§5.3"], hier=[["N_40", "subcase"]], prag=[["N_40", "resolves"]],
         creates=[], updates=[], relates=[["SN_4", "supports"]],
         summary="Re-stage the working copy from $PROJECT at the start of each job chain.",
         ref="Re-stage per job chain"),
    # ---- Containers, arrays, wrap-up ------------------------------------------
    dict(id="N_42", date="2026-10-22",
         q="On the GPU nodes my environment now crashes on import with a CUDA error: 'CUDA driver version is insufficient for CUDA runtime version'. It worked on gpu-short last week.",
         a="That's a classic conda problem on these nodes: conda-installed CUDA libraries often mismatch the A100 driver, and the guide warns about this. It's the same environment we rebuilt in $PROJECT [N_24], so rebuilding it again won't reliably fix it.",
         act="information", ents=["E_4", "E_11"], cites=["N_24"], docs=["§3.2"], hier=[["N_27", "subcase"]], prag=[["N_24", "references"]],
         creates=[], updates=[], relates=[["SN_3", "contradicts"]],
         summary="Conda environment fails on GPU nodes with a CUDA driver mismatch.",
         ref="CUDA mismatch in conda"),
    dict(id="N_43", date="2026-10-22",
         q="So what should I use instead?",
         a="Containers. Apptainer is the recommended way to run GPU workloads on Aurora: the image bundles a CUDA runtime that matches the driver when you run it with `--nv`. I'd move the whole training stack into an Apptainer image and retire the conda environment for GPU jobs.",
         act="decision", ents=["E_12", "E_11"], cites=[], docs=["§7.1"], hier=[["N_42", "subcase"]], prag=[["N_42", "resolves"]],
         creates=["SN_12"], updates=[["SN_3", "reverted"]], relates=[],
         summary="Switches GPU jobs to an Apptainer container; conda env retired.",
         ref="Switch to Apptainer"),
    dict(id="N_44", date="2026-10-22",
         q="I don't have root on Aurora. How do I build the .sif image?",
         a="Two options: build it on a compute node with `apptainer build --fakeroot train.sif train.def` (not on a login node), or build it on your own machine and copy it to $PROJECT. You can also convert a Docker image, e.g. `apptainer build train.sif docker://pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime`, then run with `apptainer exec --nv train.sif python train.py`.",
         act="factual_question", ents=["E_12"], cites=[], docs=["§7.1"], hier=[["N_43", "subcase"]], prag=[["N_43", "depends_on"]],
         creates=[], updates=[], relates=[["SN_2", "constrained_by"]],
         summary="Build the .sif with --fakeroot on a compute node, or locally, or from a Docker image.",
         ref="Building the image"),
    dict(id="N_45", date="2026-10-26",
         q="Training works in the container. Now my supervisor wants a sweep over 40 hyper-parameter configurations. Do I submit 40 separate jobs?",
         a="Use a job array instead: `#SBATCH --array=1-40%10` submits all 40 configs as one array and runs at most 10 at a time; each task reads its config via `$SLURM_ARRAY_TASK_ID`. The guide asks for a concurrency limit on large arrays, and each task still uses the same checkpoint-and-resume logic.",
         act="decision", ents=["E_9", "E_13"], cites=[], docs=["§4.3"], hier=[["N_14", "same_level"]], prag=[["N_32", "depends_on"]],
         creates=["SN_13"], updates=[], relates=[],
         summary="Decides to run the 40-config sweep as a job array with at most 10 concurrent tasks.",
         ref="Sweep as job array"),
    dict(id="N_46", date="2026-10-26",
         q="Looking back, the 24-hour limit really isn't a problem for me anymore, is it?",
         a="Right: with checkpoint-and-resume chains [N_32] every run is already split into sub-24-hour jobs, so the limit no longer constrains anything you plan to do. It's still the partition policy, but it has stopped binding your work.",
         act="information", ents=["E_15"], cites=["N_32"], docs=["§6.2"], hier=[], prag=[["N_30", "references"]],
         creates=[], updates=[["SN_8", "lifted"]], relates=[],
         summary="With checkpoint chains, the 24-hour limit no longer constrains the plan.",
         ref="24 h limit no longer binding"),
    dict(id="N_47", date="2026-10-27",
         q="Weird: after the sweep, my jobs are suddenly waiting much longer than before, with reason `Priority`.",
         a="That's fair-share at work. Priority depends on your group's recent usage, and a 40-config sweep is a lot of usage.",
         act="factual_question", ents=[], cites=[], docs=["§8.1"], hier=[["N_45", "subcase"]], prag=[["N_45", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Jobs wait longer with reason Priority after the sweep.",
         ref="Priority dropped"),
    dict(id="N_48", date="2026-10-28",
         q="How long until my priority recovers? And good news: the first full 60-hour training finished overnight with good results!",
         a="Congratulations, that's the main goal done! Usage decays with a 7-day half-life, so your priority recovers over about one to two weeks; `sshare -u $USER` shows your current standing.",
         act="information", ents=[], cites=[], docs=["§8.1"], hier=[["N_47", "subcase"]], prag=[["N_47", "resolves"]],
         creates=[], updates=[["SN_1", "achieved"]], relates=[],
         summary="Fair-share recovery explained; the first full training run completed successfully.",
         ref="First full training done"),
    dict(id="N_49", date="2026-10-28",
         q="A new labmate starts on Aurora next week. Can you give me a checklist of everything I learned the hard way?",
         a="Here's the checklist: (1) never compute on login nodes; use `srun --pty` for tests. (2) Keep environments out of $HOME, and for GPU work use an Apptainer image rather than conda. (3) Master data lives in $PROJECT (a 1 TB quota shared by the group); scratch is a purged working area, staged per job chain. (4) Always request memory explicitly, sized from MaxRSS plus about 20%. (5) Anything longer than 24 h is checkpointed and chained; debug on gpu-short; sweeps go in job arrays with a concurrency limit.",
         act="request", ents=["E_7", "E_8", "E_12", "E_5"], cites=[], docs=["§2.2", "§3.2", "§4.2", "§5.3", "§6.2", "§7.1"], hier=[["N_5", "supercase"], ["N_24", "supercase"], ["N_36", "supercase"], ["N_43", "supercase"]], prag=[],
         creates=[], updates=[], relates=[],
         summary="Summarises all the onboarding lessons as a checklist for a new labmate.",
         ref="Onboarding checklist"),
    dict(id="N_50", date="2026-10-29",
         q="Thanks. I'm also opening a helpdesk ticket suggesting that the quickstart page mention the scratch purge right next to the dataset advice.",
         a="Good idea, since that was the most costly surprise. Include the section number (§5.3) in the ticket. If they want to discuss it, Research Computing holds office hours on Thursdays, 14:00–16:00.",
         act="agreement", ents=["E_18"], cites=[], docs=["§9.1"], hier=[], prag=[["N_49", "depends_on"]],
         creates=[], updates=[], relates=[],
         summary="Tomás opens a helpdesk ticket to add the scratch-purge warning to the quickstart.",
         ref="Helpdesk ticket opened"),
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
        "grounding_sections": n["docs"],
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
    "conversation_id": "hpc_support",
    "domain": "Document-grounded HPC cluster onboarding and troubleshooting",
    "document": "aurora_user_guide.md",
    "schema_note": (
        "Mirrors INESCTEC_RESEARCH.md section 3/4 output schema, same convention as "
        "conversations/marathon_trip. Domain entity types (domain_config.json): partition, command, "
        "filesystem. Adds one field not in the base schema: grounding_sections, the Aurora User Guide "
        "sections (§x.y) each answer relies on. citations keeps its existing meaning (interaction ids "
        "cited in the answer text as [N_k]). Built to exercise document grounding, error -> diagnosis -> "
        "fix resolves chains, two assistant claims contradicted by the document itself (N_9 via N_24, "
        "N_12 via N_36), and constraint: lifted."
    ),
    "schema_findings": [
        {
            "raised_at_node": "N_24",
            "issue": "Gold document grounding can't be expressed as InteractionNode.grounded_by, because that "
                     "field holds DocumentChunk ids (DOC_n:k) that only exist after ingestion and depend on "
                     "the chunking parameters.",
            "proposed_direction": "Record stable guide section ids in grounding_sections. To score grounding, "
                                   "map each retrieved chunk to the section(s) its text spans at evaluation time, "
                                   "instead of freezing chunk ids into the gold file.",
        },
        {
            "raised_at_node": "N_46",
            "issue": "SN_8 (24 h walltime) is marked 'lifted' although the cluster policy itself never "
                     "changed; what changed is that the constraint stopped binding the user's plan "
                     "(checkpoint chains make every job shorter than 24 h).",
            "proposed_direction": "Kept as lifted, since state nodes track the conversation's plan, not the "
                                   "world. Flagged so annotators apply 'lifted' consistently: 'no longer "
                                   "constrains the plan' counts, even if the underlying rule still exists.",
        },
        {
            "raised_at_node": "N_43",
            "issue": "SN_3 goes active -> revised (N_24) -> reverted (N_43): the environment was first moved, "
                     "then abandoned in favour of a container. The replacement is a new decision (SN_12), "
                     "since reverted is terminal.",
            "proposed_direction": "Same convention as the outlines: a replaced decision is reverted and the "
                                   "replacement is a new state node, never a re-activation.",
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
