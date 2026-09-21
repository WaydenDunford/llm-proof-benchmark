# Open-source LLM run report

**Scope:** operational status of the models in `configs/models.yaml` for this
benchmark, recorded 21 September 2026. “Works” means the benchmark successfully
generated a proof artifact. It does **not** mean that the proof has already been
judged mathematically correct; that requires the blind ChatGPT evaluation import.

## Environment summary

| Environment | Result | Why |
|---|---|---|
| Local Windows computer, CPU-only PyTorch | Not suitable for these full 7B/8B checkpoints in the current setup | Each model's full-precision weights are about 14–15 GB on disk and also require substantial RAM and working memory while loading/generating. The computer had about 14 GB of free disk space after the downloads. Automatic device placement attempted offloading and generation then failed on unmaterialised “meta” tensors. |
| Google Colab, Tesla T4 with 15 GB VRAM, 4-bit loading | Suitable for one model at a time | 4-bit quantisation lowers GPU weight-memory requirements enough for a 7B/8B model. The benchmark loads, generates with, unloads, and clears memory for each enabled model. |
| Google Colab, all three models selected | Operationally supported, sequentially | They are **not** loaded together. The trade-off is a roughly 44 GB first-time download into Colab's temporary storage and a longer run. |

The local CPU run recorded in
`results/proofs/T001_2026-09-21_072311_622868_d5d2da_proofs.json` failed for all
three generators with `RuntimeError: Tensor.item() cannot be called on meta tensors`.
That is a resource/loading failure, not evidence that any model cannot write the
theorem proof.

## Generator status

| Config name | Checkpoint | Status | Reason |
|---|---|---|---|
| `deepseek-r1-distill-qwen-7b` | [`deepseek-ai/DeepSeek-R1-Distill-Qwen-7B`](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B) | **Works on Colab T4** | A real `T001` proof was generated in Colab on 21 September 2026, producing the run `2026-09-21_093954_319476_7db12b` and its anonymous evaluation bundle. This 7B Qwen-based reasoning distill is directly supported by the Transformers adapter and fitted after 4-bit loading. Its reasoning-oriented training makes it an appropriate candidate for proof generation, but proof quality still needs blind scoring. The DeepSeek paper describes the released Qwen- and Llama-based distilled models. [DeepSeek-R1 paper](https://arxiv.org/abs/2501.12948) |
| `deeptheorem-qwen-7b` | [`Jiahao004/DeepTheorem-Qwen-7B-RL`](https://huggingface.co/Jiahao004/DeepTheorem-Qwen-7B-RL) | **Ready for a Colab test; not yet verified there** | The checkpoint was downloaded locally, but its local CPU attempt failed with the same meta-tensor resource error as the others. The benchmark configuration supports it through the standard Transformers/Qwen path. Use the prepared selector cell in the Colab notebook, 4-bit loading, and the same T4 workflow to establish a real result. No claim of proof quality or successful Colab generation should be made until that run completes. |
| `qwen3` | [`Qwen/Qwen3-8B`](https://huggingface.co/Qwen/Qwen3-8B) | **Ready for a Colab test; not yet verified there** | This is an 8B Qwen3 model, so it has slightly higher memory pressure than the 7B models but is still expected to fit on the T4 with 4-bit loading. The benchmark uses its chat template with `enable_thinking: false`, producing a direct proof response rather than exposing a long internal reasoning trace. Qwen3 supports selectable thinking/non-thinking behaviour through its prompting/template design. [Qwen3 technical report](https://arxiv.org/abs/2505.09388) |

## Evaluator status

| Evaluator | Status | Reason |
|---|---|---|
| ChatGPT blind evaluation | Pending import for the successful DeepSeek run | The generated Markdown bundle is anonymous by design. Once ChatGPT returns its required JSON, importing it will validate the proof IDs and update the evaluations JSON, report, and Excel workbook. |
| Math-Shepherd | Real checkpoint with an adapted 4-bit Colab scoring method; the earlier successful DeepSeek run used mock mode | The configured checkpoint is a separate Mistral 7B process-reward model. The revised workflow unloads the generator, then loads Math-Shepherd in 4-bit mode. The benchmark scores each numbered theorem-proof step from `+` versus `-` next-token probabilities. This is an adaptation by this project, and is a supplementary automated signal rather than a formal proof checker or an official Math-Shepherd theorem-proof metric. [Checkpoint configuration](https://huggingface.co/peiyi9979/math-shepherd-mistral-7b-prm/blob/main/config.json) and [Math-Shepherd paper](https://arxiv.org/abs/2312.08935). |

## Why the local run failed

The error is not a missing Python package—the earlier `torch` installation issue was
resolved. It occurred after the checkpoints had downloaded. CPU-only inference can
work in principle, but this particular run combined large 7B/8B checkpoints,
automatic device placement, limited free disk, and insufficient practical memory for
the full model plus temporary tensors. Transformers/Accelerate left some values as
meta placeholders during offload, so generation failed when code tried to read one.

The practical remedy is the Colab setup already added to this repository:

1. Select a T4 GPU runtime.
2. Enable 4-bit loading.
3. Run one model at a time, or select all models for the benchmark's sequential
   load/generate/unload cycle.
4. Download the results before Colab clears `/content`.

## Next evidence to collect

1. Run `deeptheorem-qwen-7b` using notebook cell 4a, then cell 5.
2. Run `qwen3` the same way, or use cell 4b to run all models sequentially.
3. Import the anonymous ChatGPT evaluation JSON for each run.
4. Compare the imported scores and comments in `results/benchmark_results.xlsx`.

After these runs, replace the two “ready for a Colab test” labels with the actual
run IDs and evaluator scores. That keeps the report evidence-based rather than
predicting model quality from names or model cards.
