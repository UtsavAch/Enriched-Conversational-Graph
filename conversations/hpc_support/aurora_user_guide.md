# Aurora HPC Cluster — User Guide

Version 3.2 · Maintained by the Research Computing team

Aurora is the institute's shared high-performance computing cluster. It has 96 CPU compute nodes
(2 × 32 cores, 256 GB RAM each) and 12 GPU nodes (4 × NVIDIA A100 40 GB each), connected by
InfiniBand. Jobs are scheduled with SLURM. This guide covers everything a new user needs for
day-to-day work. Section numbers (§) are stable and may be cited in support tickets.

---

## 1. Getting help quickly

Most problems new users hit are covered by §2.2 (login node limits), §3.2 (where to install conda
environments), §4.2 (memory requests) and §5.3 (scratch purge policy). Please read those four
sections before opening a ticket.

---

## 2. Access

### 2.1 Accounts and SSH

Accounts are created by your group's PI through the Research Computing portal. Aurora accepts
**SSH key authentication only**; password login is disabled.

1. Generate a key pair on your own machine: `ssh-keygen -t ed25519`.
2. Upload the **public** key (`~/.ssh/id_ed25519.pub`) in the portal under *Profile → SSH keys*.
3. Connect with `ssh <username>@login.aurora.inst`.

Keys take up to 15 minutes to propagate. Never copy your private key onto Aurora itself.

### 2.2 Login nodes

The two login nodes (`login1`, `login2`) are shared by every user. They are for editing files,
compiling small programs, managing data, and submitting jobs. **Do not run computations on the
login nodes.** Any process that uses more than 10 minutes of CPU time on a login node is killed
automatically, and repeated violations lead to account suspension.

For quick tests, request an interactive session on a compute node instead:

```
srun --partition=cpu --time=00:30:00 --cpus-per-task=4 --mem=8G --pty bash
```

---

## 3. Software environment

### 3.1 Environment modules

Centrally installed software is provided through environment modules.

- `module avail` lists available software.
- `module load python/3.11` loads a module; `module list` shows what is loaded.
- `module purge` unloads everything; do this at the top of batch scripts for reproducibility.

Common modules: `python/3.11`, `cuda/12.2`, `gcc/12.3`, `openmpi/4.1`, `apptainer/1.3`.

### 3.2 Conda

Conda (Miniforge) is available via `module load miniforge`. You may create your own environments.

**Install environments under `$PROJECT`, not `$HOME`.** Conda environments with deep-learning
libraries typically use 5–15 GB, and `$HOME` has a 10 GB quota (§5.1). Create environments with an
explicit prefix:

```
conda create --prefix $PROJECT/envs/myenv python=3.11
conda activate $PROJECT/envs/myenv
```

Keep an `environment.yml` under version control. Moving an existing environment by copying its
directory is not supported (paths are hard-coded inside it); recreate it from `environment.yml`
instead.

Note: conda-installed CUDA libraries frequently mismatch the GPU driver on the A100 nodes. For GPU
workloads, containers are recommended (§7.1).

---

## 4. Running jobs with SLURM

### 4.1 Basics

Submit batch jobs with `sbatch job.sh`. Check the queue with `squeue -u $USER`, and inspect finished
jobs with `sacct -j <jobid> --format=JobID,State,Elapsed,MaxRSS,ExitCode`.

A minimal job script:

```
#!/bin/bash
#SBATCH --job-name=test
#SBATCH --partition=cpu
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
module purge
module load python/3.11
python my_script.py
```

A job may stay `PENDING` for a while. The `REASON` column in `squeue` explains why: `Resources`
means the requested resources are not free yet; `Priority` means other jobs are ahead of yours
(§8.1). Smaller requests (fewer GPUs, shorter time) usually start sooner.

### 4.2 Resource requests and memory

If you do not request memory explicitly, jobs receive the **default of 2 GB per allocated CPU
core**. Jobs that exceed their memory allocation are killed by the scheduler without a Python
traceback; `sacct` then shows the state `OUT_OF_MEMORY`.

Request memory per node with `--mem=32G`, or per core with `--mem-per-cpu`. Use the `MaxRSS`
field from `sacct` on a previous run to size requests, and add about 20% headroom.

### 4.3 Job arrays

Use job arrays for many similar jobs such as parameter sweeps:

```
#SBATCH --array=1-100%10
```

This submits 100 tasks and runs at most 10 at a time. The task index is in
`$SLURM_ARRAY_TASK_ID`. Please always use a concurrency limit (`%N`) for large arrays.

### 4.4 Job dependencies

`sbatch --dependency=afterany:<jobid> next.sh` starts `next.sh` only after the given job ends,
whether it succeeded or not. Use `afterok` to require success. Dependency chains are the standard
way to run work longer than a partition's time limit (§6.2).

---

## 5. Storage

Aurora has three storage areas. Choose based on size, speed, and whether the data must survive.

| Area | Path variable | Size | Backed up | Purged |
|---|---|---|---|---|
| Home | `$HOME` | 10 GB per user | Yes (nightly) | No |
| Project | `$PROJECT` | 1 TB per group (shared) | Yes (weekly) | No |
| Scratch | `$SCRATCH` | 50 TB total | **No** | **Yes, 30 days** |

Check usage with `aurora-quota`.

### 5.1 `$HOME`

For configuration files, scripts, and small source trees. The 10 GB quota is enforced strictly;
exceeding it causes "Disk quota exceeded" errors, including for programs that write caches (pip,
conda, Hugging Face). Point caches elsewhere, e.g. `export HF_HOME=$PROJECT/.cache/huggingface`.

### 5.2 `$PROJECT`

For datasets, environments, results, and anything that must be kept. The 1 TB quota is **shared by
all members of your group**; coordinate large additions with your group. `$PROJECT` is backed up
weekly and never purged. It is slower than scratch for heavy I/O.

### 5.3 `$SCRATCH`

High-performance parallel filesystem for temporary working data during jobs. **Files not accessed
in 30 days are deleted automatically, and scratch is not backed up.** Do not keep the only copy of
anything important on scratch.

Recommended pattern: keep the master copy of datasets in `$PROJECT` and stage a working copy to
`$SCRATCH` at the start of a job (or a job chain). Artificially updating access times (e.g. running
`touch` over files) to avoid the purge is prohibited and may lead to loss of scratch access.

---

## 6. GPUs

### 6.1 GPU partitions

| Partition | GPUs | Max walltime | Priority | Intended use |
|---|---|---|---|---|
| `gpu-a100` | A100 40 GB | 24 hours | Normal | Training and production runs |
| `gpu-short` | A100 40 GB | 2 hours | High | Debugging, short tests |

Request GPUs with `--partition=gpu-a100 --gres=gpu:1` (up to `gpu:4` on one node). Jobs that
request more than the partition's maximum walltime are rejected at submission.

### 6.2 Long-running work and checkpointing

No partition allows jobs longer than 24 hours. Work that needs more time **must checkpoint**: save
model and optimizer state at regular intervals (every 1–2 hours is recommended), and chain jobs
with dependencies (§4.4) so each job resumes from the latest checkpoint. Extended reservations are
granted only in exceptional cases and require PI approval.

---

## 7. Containers

### 7.1 Apptainer

Apptainer (formerly Singularity) runs containers without root privileges. It is the **recommended
way to run GPU workloads**, because the container bundles a CUDA runtime that matches the cluster
driver when started with `--nv`.

```
module load apptainer/1.3
apptainer build --fakeroot train.sif train.def   # build on a compute node, not a login node
apptainer exec --nv train.sif python train.py
```

You can also build the `.sif` image on your own machine and copy it to `$PROJECT`. Docker images
can be converted with `apptainer build train.sif docker://pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime`.

---

## 8. Scheduling policy

### 8.1 Fair-share

Job priority depends on your group's recent usage (fair-share). Heavy usage lowers your priority
temporarily; usage decays with a **7-day half-life**, so priority recovers over about one to two
weeks. Check your current standing with `sshare -u $USER`.

---

## 9. Support

### 9.1 Contact

Open tickets through the helpdesk portal and include your job ID and the relevant section of this
guide. Research Computing holds drop-in office hours every **Thursday, 14:00–16:00**. Suggestions for
improving this guide are welcome through the same helpdesk.
