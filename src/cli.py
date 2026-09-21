"""Command-line entry points; execute from the checkout or pass --root."""
import logging
from pathlib import Path
from typing import Annotated
import typer
from rich.console import Console
from rich.table import Table
from .benchmark import run_benchmark
from .dual import bundle, import_chatgpt, math_shepherd
from .reporting import generate_reports
from .schemas import ModelsConfig
from .utils import load_config, load_theorems

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
console = Console()
ROOT = Path(__file__).resolve().parent.parent


@app.callback()
def main(root: Annotated[Path | None, typer.Option(help="Repository root containing configs and theorems")] = None):
    global ROOT
    if root:
        ROOT = root.resolve()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


@app.command("list-models")
def list_models():
    table = Table("Name", "Enabled", "Backend", "Model ID")
    for model in load_config(ROOT / "configs/models.yaml", ModelsConfig).models:
        table.add_row(model.name, str(model.enabled), model.backend, model.model_id)
    console.print(table)


@app.command("list-theorems")
def list_theorem_command():
    table = Table("ID", "Title", "Domain", "Difficulty")
    for theorem in load_theorems(ROOT):
        table.add_row(theorem.id, theorem.title, theorem.domain, theorem.difficulty)
    console.print(table)


def execute(theorem, prompt, backend, temperature, top_p, max_new_tokens, seed, do_sample, repetitions):
    overrides = {key: value for key, value in dict(temperature=temperature, top_p=top_p,
                 max_new_tokens=max_new_tokens, seed=seed, do_sample=do_sample).items() if value is not None}
    raw = run_benchmark(ROOT, theorem, prompt, backend, overrides, repetitions)
    console.print(f"Proofs: {raw}")
    return raw


@app.command()
def run(theorem: str = typer.Option(...), prompt: str = "structured", backend: str | None = None,
        temperature: float | None = None, top_p: float | None = None,
        max_new_tokens: int | None = None, seed: int | None = None,
        do_sample: bool | None = typer.Option(None, "--do-sample/--no-sample"), repetitions: int | None = None):
    """Generate proofs and unevaluated reports for all enabled models."""
    execute(theorem, prompt, backend, temperature, top_p, max_new_tokens, seed, do_sample, repetitions)


@app.command("full-run")
def full_run(theorem: str = typer.Option(...), prompt: str = "structured", backend: str | None = None,
             temperature: float | None = None, top_p: float | None = None,
             max_new_tokens: int | None = None, seed: int | None = None,
             do_sample: bool | None = typer.Option(None, "--do-sample/--no-sample"),
             repetitions: int | None = None):
    """Legacy alias: generate proofs; manual evaluation is prepared separately."""
    execute(theorem, prompt, backend, temperature, top_p, max_new_tokens, seed, do_sample, repetitions)


@app.command("run-all")
def run_all(prompt: str = "structured", backend: str | None = None,
            temperature: float | None = None, top_p: float | None = None,
            max_new_tokens: int | None = None, seed: int | None = None,
            do_sample: bool | None = typer.Option(None, "--do-sample/--no-sample"),
            repetitions: int | None = None):
    """Run every theorem. Prepare/import evaluation bundles separately."""
    for theorem in load_theorems(ROOT):
        execute(theorem.id, prompt, backend, temperature, top_p, max_new_tokens, seed, do_sample, repetitions)


@app.command("prepare-dual-evaluation")
def prepare_dual_evaluation(theorem: str = typer.Option(...), prompt: str = "structured", backend: str | None = None,
                            math_shepherd_backend: str | None = None, temperature: float | None = None,
                            top_p: float | None = None, max_new_tokens: int | None = None, seed: int | None = None,
                            do_sample: bool | None = typer.Option(None, "--do-sample/--no-sample"), repetitions: int | None = None):
    """Generate one proofs file, verify it, update Excel, and prepare ChatGPT bundle."""
    proofs = execute(theorem, prompt, backend, temperature, top_p, max_new_tokens, seed, do_sample, repetitions)
    evaluations = math_shepherd(ROOT, proofs, math_shepherd_backend)
    markdown, _ = bundle(ROOT, proofs)
    console.print(f"Evaluations: {evaluations}")
    console.print(f"Excel: {ROOT / 'results/benchmark_results.xlsx'}")
    console.print("Upload to ChatGPT:")
    console.print(str(markdown))


@app.command("prepare-chatgpt")
def prepare_chatgpt(theorem: str = typer.Option(...), prompt: str = "structured", backend: str | None = None,
                    temperature: float | None = None, top_p: float | None = None,
                    max_new_tokens: int | None = None, seed: int | None = None,
                    do_sample: bool | None = typer.Option(None, "--do-sample/--no-sample"),
                    repetitions: int | None = None, include_reference_proof: bool = False):
    """Deprecated compatibility alias for prepare-dual-evaluation."""
    proofs = execute(theorem, prompt, backend, temperature, top_p, max_new_tokens, seed, do_sample, repetitions)
    math_shepherd(ROOT, proofs, "mock" if backend == "mock" else None)
    markdown, _ = bundle(ROOT, proofs)
    console.print(f"Upload this file to ChatGPT Plus:\n{markdown}")


@app.command("import-chatgpt-evaluation")
def import_chatgpt_evaluation(run_id: str = typer.Option(...), evaluation: Path = typer.Option(..., exists=True)):
    """Merge a ChatGPT result into the same evaluations file and update Excel."""
    target = import_chatgpt(ROOT, run_id, evaluation)
    data = __import__("json").loads(target.read_text(encoding="utf-8"))
    table = Table("Model", "MathShepherd", "ChatGPT", "Verdict")
    for item in data["evaluations"]:
        table.add_row(item["model_name"], str(item["math_shepherd"].get("mean_score", "—")), str(item["chatgpt"].get("total_score", "pending")), str(item["chatgpt"].get("verdict", "pending")))
    console.print(table)
    console.print(f"Evaluations: {target}\nExcel: {ROOT / 'results/benchmark_results.xlsx'}")


@app.command()
def report(result: Path):
    """Rebuild a report from a canonical evaluations JSON file."""
    from .reporting import generate_dual_reports
    import json
    data = json.loads(result.read_text(encoding="utf-8"))
    matches = list((ROOT / "results/proofs").glob(f"*_{data['run_id']}_proofs.json"))
    if len(matches) != 1:
        raise typer.BadParameter("Matching canonical proofs file was not found")
    for path in generate_dual_reports(ROOT, json.loads(matches[0].read_text(encoding="utf-8")), data):
        console.print(str(path))


if __name__ == "__main__":
    app()
