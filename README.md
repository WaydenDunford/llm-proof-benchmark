# LLM Proof Benchmark

This project compares local/open-weight models that write natural-language proofs.
Each run creates one canonical proofs JSON and one canonical evaluations JSON. Local
Math-Shepherd verification and manual blind ChatGPT Plus evaluation merge into that
single evaluations file. A global Excel workbook updates automatically after both.

## Recommended workflow

```powershell
cd 'C:\Users\DT User\llm-proof-benchmark'
.\.venv\Scripts\python.exe -m src.cli prepare-dual-evaluation --theorem T001 --prompt structured
```

It prints:

```text
Proofs: results/proofs/T001_<run-id>_proofs.json
Evaluations: results/evaluations/T001_<run-id>_evaluations.json
Excel: results/benchmark_results.xlsx
Upload to ChatGPT: results/evaluation_input/T001_<run-id>_chatgpt_bundle.md
```

Upload only the Markdown bundle to ChatGPT Plus. It contains theorem information,
the rubric, anonymous proof IDs, and proof text. It excludes model names, model IDs,
Math-Shepherd scores, runtimes, token counts, and backend data. Never upload the
local mapping under `results/evaluation_maps/`.

Save ChatGPT's JSON-only response locally, then merge it into the existing
evaluations file and update Excel/reports in place:

```powershell
.\.venv\Scripts\python.exe -m src.cli import-chatgpt-evaluation `
  --run-id <run-id> `
  --evaluation results/evaluation_output/T001_<run-id>_chatgpt.json
```

There is no ChatGPT API call. Import validates proof IDs, score integers (0–2),
score totals, and verdicts before accepting the result.

## Result storage

```text
results/
  proofs/              One *_proofs.json per benchmark run
  evaluations/         One *_evaluations.json per benchmark run
  evaluation_input/    One blind ChatGPT bundle per run
  evaluation_maps/     Local identity mapping; do not upload
  reports/             One Markdown and HTML report per run
  benchmark_results.xlsx
```

The proofs JSON contains every model's generated proof and generation metadata. The
evaluations JSON contains Math-Shepherd and ChatGPT assessments, proof/model identity,
and agreement data. `run_id + proof_id` is the stable key across JSON and Excel.
Re-importing an evaluation updates rows instead of duplicating them.

## Excel workbook

`results/benchmark_results.xlsx` contains:

- `Results` — one row per model/proof/run, without full proof text.
- `Proofs` — full generated proof text with wrapping.
- `MathShepherdSteps` — one row per verified proof step.
- `Runs` — configuration and environment metadata for each run.
- `Summary` — simple per-model cross-run averages and verdict counts.

The workbook has frozen, filtered headers, wrapped comments/proofs, and simple score
conditional formatting. Close it before an update if Excel locks the file.

## Math-Shepherd

`configs/math_shepherd.yaml` controls the local verifier. The default uses the local
Transformers checkpoint `peiyi9979/math-shepherd-mistral-7b-prm` and scores numbered
`S1`, `S2`, … steps from its next-token probabilities for `+` and `-`. It requires
the checkpoint download and adequate local memory.

For a GPU-free plumbing test, use deterministic mock generators and verifier:

```powershell
.\.venv\Scripts\python.exe -m src.cli prepare-dual-evaluation `
  --theorem example_theorem --backend mock --math-shepherd-backend mock
```

Mock scores are fixtures, not mathematical evidence.

## Setup and tests

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

For real generation, configure `configs/models.yaml`. Models load one at a time.
CPU-only inference of 7B models is very slow; use CUDA and sufficient VRAM where possible.
