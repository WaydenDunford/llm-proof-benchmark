# Literature review and model-selection report

## Purpose

This report explains why the graduation benchmark uses DeepTheorem-Qwen-7B-RL,
DeepSeek-R1-Distill-Qwen-7B, and Qwen3-8B rather than older influential language
models. It evaluates suitability for a reproducible experiment in natural-language
theorem proving, not the historical importance of excluded models.

The original repository brief retained only the final three models, not the earlier
longlist. The candidates below are therefore a reconstructed review centred on the
models discussed in planning, including GPT-2 and Minerva. Amend it if the original
list is recovered.

## Selection criteria

A model was favoured when it had public open weights, a maintained Transformers
workflow, a realistic 4-bit single-T4 deployment path, current reasoning ability,
mathematical relevance, and a comparable prompting interface. These criteria rule
out unavailable weights, very large models, and old general-purpose baselines.

## Candidate review

| Model or paper | Decision | Reason |
|---|---|---|
| **GPT-2** (2019), [paper](https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf) | Excluded | An important historical language-model baseline, but neither mathematics- nor proof-oriented. It would primarily measure age-related progress. |
| **GPT-Neo** (2021), [project](https://www.eleuther.ai/artifacts/gpt-neo) | Excluded | Open and runnable, but an older general-language baseline that adds little to a modern reasoning comparison. |
| **GPT-J-6B** (2021), [model card](https://huggingface.co/EleutherAI/gpt-j-6b) | Excluded | Feasible, but predates current instruction tuning, chat templates, and reasoning-oriented post-training. Include only if a historical baseline is a research question. |
| **GPT-NeoX-20B** (2022), [paper](https://arxiv.org/abs/2204.06745) | Excluded | Its 20B scale is not practical in the single free-T4 protocol and it is a general language model. |
| **Minerva** (2022), [paper](https://arxiv.org/abs/2206.14858) | Excluded | A central reference for quantitative reasoning, but its reported systems are very large and not a practical open-weight checkpoint for this project. It belongs in the literature review, not the runnable set. |
| **Galactica** (2022), [paper](https://arxiv.org/abs/2211.09085) | Excluded | Science-oriented rather than proof-specialised; its useful variants are also not suitable for the available hardware. |
| **LLaMA** (2023), [paper](https://arxiv.org/abs/2302.13971) | Excluded as a direct generator | An important ancestor of current models, but the original base models need adaptation and later checkpoints are easier to reproduce and more task-relevant. |
| **Mistral 7B** (2023), [paper](https://arxiv.org/abs/2310.06825) | Excluded as a generator | A good hardware fit but a generic foundation model. It remains relevant indirectly because the Math-Shepherd reward model is Mistral-based. |
| **Llemma 7B / 34B** (2023), [paper](https://arxiv.org/abs/2310.10631) | Reserve candidate | Strongly relevant mathematics models. The 7B variant is suitable for later expansion; 34B exceeds the T4 constraint. |
| **DeepSeekMath 7B** (2024), [paper](https://arxiv.org/abs/2402.03300) | Reserve candidate | It fits the size and mathematical-relevance criteria. It was deferred to avoid overlapping too heavily with the newer DeepSeek-R1 distill in the first comparison. |
| **Qwen2.5-Math-7B**, [model card](https://huggingface.co/Qwen/Qwen2.5-Math-7B-Instruct) | Reserve candidate | A valuable controlled baseline because DeepSeek-R1-Distill-Qwen-7B is based on Qwen2.5-Math-7B. A later comparison can measure the effect of R1 distillation. |
| **DeepTheorem-Qwen-7B-RL**, [model card](https://huggingface.co/Jiahao004/DeepTheorem-Qwen-7B-RL) | **Selected** | It is directly aligned with textual theorem/reasoning generation and fits the sequential 4-bit T4 workflow. |
| **DeepSeek-R1-Distill-Qwen-7B**, [model card](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B), [paper](https://arxiv.org/abs/2501.12948) | **Selected** | It combines current reasoning-oriented post-training, mathematical ancestry, public weights, and a 7B size compatible with the Colab workflow. |
| **Qwen3-8B**, [technical report](https://arxiv.org/abs/2505.09388), [model card](https://huggingface.co/Qwen/Qwen3-8B) | **Selected** | A current general reasoning model that fits in 4-bit form and supplies a useful comparison against the two mathematics/theorem-oriented models. The benchmark fixes non-thinking mode for comparable proof outputs. |

## Why the selected set is defensible

| Comparison role | Model | Question tested |
|---|---|---|
| Theorem-oriented specialist | DeepTheorem-Qwen-7B-RL | Does task-specific theorem/reasoning training improve textual proofs? |
| Mathematics/reasoning distill | DeepSeek-R1-Distill-Qwen-7B | Does modern reasoning-oriented distillation improve textual proofs? |
| Current general model | Qwen3-8B | How well can a current general open-weight reasoner write proofs without theorem-specific training? |

The models are close in scale (7B–8B), so they can use the same prompt and similar
generation settings on a single T4. This is a more controlled comparison than
combining a 1.5B historical baseline, a 20B model, and a very large research system
with fundamentally different access and hardware requirements.

## Limits and recommended methodology wording

This is a practical, small-scale comparison, not a universal ranking. Training data,
post-training, chat format, and licence differ across models. The benchmark evaluates
natural-language proofs, not formally verified proof terms; a high evaluation score
is not machine-checked correctness.

> We selected three publicly available open-weight models in the 7B–8B range:
> DeepTheorem-Qwen-7B-RL, DeepSeek-R1-Distill-Qwen-7B, and Qwen3-8B. The selection
> balances theorem-oriented training, reasoning-oriented mathematical distillation,
> and a recent general reasoning model while keeping the hardware conditions
> comparable on a single 4-bit GPU runtime. Earlier models such as GPT-2, GPT-J,
> GPT-NeoX, Minerva, and Galactica were retained as literature references but not
> used as generators because they are historical general-language baselines,
> impractical for the available hardware, or not publicly runnable as suitable
> open-weight checkpoints. Llemma and DeepSeekMath are suitable future additions.
