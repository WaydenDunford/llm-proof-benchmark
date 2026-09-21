"""Sequential generation, incremental checkpoints and self-critique/refine."""
from datetime import datetime, timezone
import logging
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from .adapters import create_adapter
from .schemas import BenchmarkConfig, Generation, ModelConfig, ModelsConfig, Response, RunResult
from .utils import find_theorem, load_config, provenance, render

log = logging.getLogger(__name__)


def run_benchmark(root: Path, theorem_name: str, prompt_name: str = "structured",
                  backend: str | None = None, overrides: dict | None = None,
                  repetitions: int | None = None) -> Path:
    config = load_config(root / "configs/benchmark.yaml", BenchmarkConfig)
    generation = Generation.model_validate(config.generation.model_dump() | (overrides or {}))
    if repetitions is not None:
        config.benchmark.repetitions = type(config.benchmark).model_validate(
            config.benchmark.model_dump() | {"repetitions": repetitions}).repetitions
    models = load_config(root / "configs/models.yaml", ModelsConfig).models
    models = [m for m in models if m.enabled]
    if not models:
        raise ValueError("Enable at least one model in configs/models.yaml")
    if backend:
        models = [ModelConfig.model_validate(m.model_dump() | {"backend": backend}) for m in models]
    if prompt_name not in {"basic", "structured", "critique-refine"}:
        raise ValueError("Prompt must be basic, structured, or critique-refine")
    theorem = find_theorem(root, theorem_name)
    template = (root / "prompts" / ("structured.txt" if prompt_name == "critique-refine" else f"{prompt_name}.txt")).read_text(encoding="utf-8")
    # Reference proofs are deliberately excluded from generation context.
    context = theorem.model_dump(exclude={"reference_proof"})
    initial = render(template, theorem=context)
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y-%m-%d_%H%M%S_%f") + "_" + uuid4().hex[:6]
    result = RunResult(run_id=run_id, timestamp=now.isoformat(), theorem=theorem,
        prompt={"name": prompt_name, "template": template if config.benchmark.save_prompts else None,
                "rendered_prompt": initial if config.benchmark.save_prompts else None},
        generation_settings=generation, benchmark_settings=config.benchmark,
        metadata=provenance(root) | {"synthetic": all(m.backend == "mock" for m in models),
            "critic": "same model, separate stateless generation" if prompt_name == "critique-refine" else None})
    from .dual import save_proofs
    target = save_proofs(root, result, config.evaluation.random_seed, config.evaluation.randomize_proof_order)
    for model in models:
        for repetition in range(config.benchmark.repetitions):
            settings = Generation.model_validate(generation.model_dump() | {"seed": (generation.seed + repetition) % 2**32})
            response = Response(response_id=f"{model.name}:{repetition + 1}", model_name=model.name,
                model_id=model.model_id, backend=model.backend, model_config_snapshot=model.model_dump(),
                repetition=repetition + 1, seed=settings.seed)
            result.responses.append(response)
            adapter = None
            started = perf_counter()
            try:
                adapter = create_adapter(model)
                adapter.load()

                def generate(stage: str, text: str) -> str:
                    output = adapter.generate(text, settings)
                    metadata = dict(output.metadata)
                    if not config.benchmark.save_prompts:
                        metadata.pop("model_input", None)
                    response.stages.append({"stage": stage,
                        "prompt": text if config.benchmark.save_prompts else None,
                        "raw_output": output.text if config.benchmark.save_raw_outputs else None,
                        "token_count_input": output.token_count_input,
                        "token_count_output": output.token_count_output,
                        "metadata": metadata})
                    if not output.text.strip():
                        raise ValueError("Model returned an empty completion")
                    return output.text

                response.proof_v1 = generate("proof_v1", initial)
                response.proof = response.proof_v1
                if prompt_name == "critique-refine":
                    critique_template = (root / "prompts/critique.txt").read_text(encoding="utf-8")
                    response.critique = generate("critique", render(critique_template, theorem=context, proof=response.proof_v1))
                    refine_template = (root / "prompts/refine.txt").read_text(encoding="utf-8")
                    response.proof_v2 = generate("proof_v2", render(refine_template,
                        theorem=context, proof=response.proof_v1, critique=response.critique))
                    response.proof = response.proof_v2
                response.status = "success"
            except Exception as exc:
                response.error = f"{type(exc).__name__}: {exc}"
                if "out of memory" in str(exc).lower():
                    response.error += "; try a smaller model, fewer tokens, or Transformers load_in_4bit: true."
                log.error("%s failed: %s", model.name, response.error)
            finally:
                if adapter is not None:
                    try:
                        adapter.unload()
                    except Exception as exc:
                        log.warning("Unload failed for %s: %s", model.name, exc)
                response.runtime_seconds = round(perf_counter() - started, 4)
                for field in ("token_count_input", "token_count_output"):
                    counts = [stage[field] for stage in response.stages]
                    setattr(response, field, sum(counts) if counts and all(c is not None for c in counts) else None)
                save_proofs(root, result, config.evaluation.random_seed, config.evaluation.randomize_proof_order)
    return target
