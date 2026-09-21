"""Canonical per-run proof/evaluation files, local verifier, and Excel export."""
from __future__ import annotations
from copy import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import re
from typing import Any
import yaml
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import ColorScaleRule, CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from .schemas import ImportedEvaluationFile, RunResult
from .utils import atomic_text

RESULT_HEADERS = ["Run ID", "Date", "Theorem ID", "Theorem Title", "Difficulty", "Prompt", "Prompt Version", "Proof ID", "Model Name", "Model ID", "Backend", "Generation Status", "Runtime Seconds", "Input Tokens", "Output Tokens", "Math-Shepherd Mean Score", "Math-Shepherd Minimum Score", "Math-Shepherd Weakest Step", "ChatGPT Assumption Handling", "ChatGPT Logical Correctness", "ChatGPT Completeness", "ChatGPT Mathematical Rigor", "ChatGPT Clarity", "ChatGPT Total Score", "ChatGPT Verdict", "ChatGPT First Error Step", "Agreement Label", "Critical Issues", "Strengths", "Evaluator Comment"]
PROOF_HEADERS = ["Run ID", "Theorem ID", "Proof ID", "Model Name", "Model ID", "Proof Text"]
STEP_HEADERS = ["Run ID", "Theorem ID", "Proof ID", "Model Name", "Step ID", "Step Text", "Math-Shepherd Score"]
RUN_HEADERS = ["Run ID", "Timestamp", "Theorem ID", "Theorem Title", "Prompt", "Temperature", "Top P", "Max New Tokens", "Seed", "Number of Models", "Number Successful", "Number Failed", "Math-Shepherd Version", "ChatGPT Evaluator Version", "Git Commit", "GPU", "Python Version", "Transformers Version"]


def proof_path(root: Path, theorem_id: str, run_id: str) -> Path:
    return root / "results/proofs" / f"{theorem_id}_{run_id}_proofs.json"


def evaluation_path(root: Path, theorem_id: str, run_id: str) -> Path:
    return root / "results/evaluations" / f"{theorem_id}_{run_id}_evaluations.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_proofs(result: RunResult, random_seed: int = 42, randomize: bool = True) -> dict:
    records = []
    successful = [item for item in result.responses if item.status == "success" and item.proof]
    ordered = copy(successful)
    if randomize:
        random.Random(random_seed).shuffle(ordered)
    ids = {item.response_id: f"P{number:03d}" for number, item in enumerate(ordered, 1)}
    for item in result.responses:
        records.append({"proof_id": ids.get(item.response_id), "model_name": item.model_name,
                        "model_id": item.model_id, "backend": item.backend, "status": item.status,
                        "proof": item.proof, "runtime_seconds": item.runtime_seconds,
                        "input_tokens": item.token_count_input, "output_tokens": item.token_count_output,
                        "repetition": item.repetition, "error": item.error})
    return {"schema_version": "2.0", "run_id": result.run_id, "timestamp": result.timestamp,
            "theorem": result.theorem.model_dump(), "prompt": {"name": result.prompt["name"], "version": f"{result.prompt['name']}_v1"},
            "generation_settings": result.generation_settings.model_dump(), "metadata": result.metadata,
            "proofs": records}


def save_proofs(root: Path, result: RunResult, random_seed: int = 42, randomize: bool = True) -> Path:
    document = canonical_proofs(result, random_seed, randomize)
    target = proof_path(root, result.theorem.id, result.run_id)
    atomic_text(target, json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    return target


def create_mapping(root: Path, proofs_file: Path) -> tuple[dict, Path]:
    proofs = _read(proofs_file)
    mapping = {item["proof_id"]: {"model_name": item["model_name"], "model_id": item["model_id"],
              "proof_id": item["proof_id"]} for item in proofs["proofs"] if item["proof_id"]}
    target = root / "results/evaluation_maps" / f"{proofs['theorem']['id']}_{proofs['run_id']}_mapping.json"
    atomic_text(target, json.dumps({"run_id": proofs["run_id"], "theorem_id": proofs["theorem"]["id"], "proof_mapping": mapping}, indent=2) + "\n")
    return mapping, target


def bundle(root: Path, proofs_file: Path) -> tuple[Path, Path]:
    proofs = _read(proofs_file)
    _, mapping_path = create_mapping(root, proofs_file)
    theorem = proofs["theorem"]
    parts = ["# LLM Proof Evaluation Task", "## Instructions", "Evaluate anonymous proofs independently. Do not infer model identity. Return only the required JSON.", "## Theorem", theorem["title"], theorem["statement"], "## Assumptions", *[f"- {x}" for x in theorem.get("assumptions", [])], "## Allowed context", *[f"- {x}" for x in theorem.get("allowed_context", [])], "## Rubric", "Score assumption_handling, logical_correctness, completeness, mathematical_rigor, and clarity as integers 0–2. total_score is their sum (0–10). verdict is correct, mostly_correct, flawed, or incorrect."]
    for item in proofs["proofs"]:
        if item["proof_id"]:
            parts += [f"## Proof {item['proof_id']}", item["proof"], "---"]
    shape = {"run_id": proofs["run_id"], "theorem_id": theorem["id"], "evaluator_id": "chatgpt_plus_run_1", "prompt_version": "chatgpt_evaluator_v1", "evaluations": [{"proof_id": "P001", "scores": {"assumption_handling": 0, "logical_correctness": 0, "completeness": 0, "mathematical_rigor": 0, "clarity": 0}, "total_score": 0, "verdict": "incorrect", "first_error_step": None, "critical_issues": [], "strengths": [], "evaluator_comment": ""}]}
    parts += ["## REQUIRED OUTPUT FORMAT", "Return ONLY valid JSON. No Markdown fences or surrounding prose.", "```json", json.dumps(shape, indent=2), "```", "Evaluate every proof; do not omit proof IDs."]
    target = root / "results/evaluation_input" / f"{theorem['id']}_{proofs['run_id']}_chatgpt_bundle.md"
    atomic_text(target, "\n\n".join(parts) + "\n")
    return target, mapping_path


def _steps(text: str) -> list[tuple[str, str]]:
    found = re.findall(r"(?m)^\s*(S\d+)\.?\s*(.*)$", text)
    return found or [("S1", text)]


def math_shepherd(root: Path, proofs_file: Path, backend: str | None = None) -> Path:
    """Evaluate every successful proof into a single evaluation document.

    The mock mode is deterministic test data. Transformers mode uses a local
    verifier checkpoint as a JSON-producing judge; it never uses an API.
    """
    proofs = _read(proofs_file)
    config = yaml.safe_load((root / "configs/math_shepherd.yaml").read_text(encoding="utf-8"))
    active_backend = backend or config.get("backend", "transformers")
    model = tokenizer = None
    if active_backend == "transformers":
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            dtype = config.get("dtype", "auto")
            model_kwargs = {"revision": config.get("revision", "main"), "device_map": config.get("device", "auto")}
            if dtype != "auto": model_kwargs["torch_dtype"] = getattr(torch, dtype)
            tokenizer = AutoTokenizer.from_pretrained(config["model_id"], revision=config.get("revision", "main"))
            model = AutoModelForCausalLM.from_pretrained(config["model_id"], **model_kwargs).eval()
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            active_backend = "unavailable"
    entries = []
    for item in proofs["proofs"]:
        verifier: dict[str, Any] = {"status": "skipped", "mean_score": None, "minimum_score": None, "weakest_step": None, "step_scores": []}
        if item["status"] == "success" and item["proof"]:
            steps = _steps(item["proof"])
            if active_backend == "mock":
                scores = [{"step_id": sid, "step_text": text, "score": round(max(.55, .93 - .04 * index), 2)} for index, (sid, text) in enumerate(steps)]
                verifier = {"status": "success", "mean_score": round(sum(x["score"] for x in scores) / len(scores), 3), "minimum_score": min(x["score"] for x in scores), "weakest_step": min(scores, key=lambda x: x["score"])["step_id"], "step_scores": scores, "version": "math_shepherd_mock_v1"}
            elif active_backend == "transformers":
                import torch
                scores = []
                prefix = ""
                plus_ids = tokenizer.encode("+", add_special_tokens=False) or tokenizer.encode(" +", add_special_tokens=False)
                minus_ids = tokenizer.encode("-", add_special_tokens=False) or tokenizer.encode(" -", add_special_tokens=False)
                for sid, text in steps:
                    prefix += text + "\n"
                    inputs = tokenizer(prefix, return_tensors="pt").to(model.device)
                    with torch.inference_mode(): logits = model(**inputs).logits[0, -1]
                    values = torch.stack([logits[plus_ids[-1]], logits[minus_ids[-1]]])
                    score = float(torch.softmax(values, dim=0)[0].item())
                    scores.append({"step_id": sid, "step_text": text, "score": round(score, 4)})
                verifier = {"status": "success", "mean_score": round(sum(x["score"] for x in scores) / len(scores), 4), "minimum_score": min(x["score"] for x in scores), "weakest_step": min(scores, key=lambda x: x["score"])["step_id"], "step_scores": scores, "version": config.get("version")}
            else:
                verifier = {"status": "error", "mean_score": None, "minimum_score": None, "weakest_step": None, "step_scores": [], "error": model_error}
        entries.append({"proof_id": item["proof_id"], "model_name": item["model_name"], "model_id": item["model_id"], "generation_status": item["status"], "math_shepherd": verifier, "chatgpt": {"status": "pending"}, "comparison": {"same_top_level_assessment": None, "agreement_label": "pending"}})
    target = evaluation_path(root, proofs["theorem"]["id"], proofs["run_id"])
    atomic_text(target, json.dumps({"schema_version": "2.0", "run_id": proofs["run_id"], "theorem_id": proofs["theorem"]["id"], "math_shepherd_version": config.get("version"), "evaluations": entries}, indent=2, ensure_ascii=False) + "\n")
    update_excel(root, proofs, _read(target))
    if model is not None:
        del model
    return target


def _assessment(mean: float | None) -> str | None:
    if mean is None: return None
    return "correct" if mean >= .8 else "mostly_correct" if mean >= .6 else "flawed"


def import_chatgpt(root: Path, run_id: str, source: Path) -> Path:
    matches = list((root / "results/proofs").glob(f"*_{run_id}_proofs.json"))
    if len(matches) != 1: raise ValueError(f"Expected one proofs file for run_id {run_id}")
    proofs_file = matches[0]; proofs = _read(proofs_file)
    evaluations_file = evaluation_path(root, proofs["theorem"]["id"], run_id)
    if not evaluations_file.exists(): raise ValueError("Math-Shepherd evaluation file not found; run prepare-dual-evaluation first.")
    imported = ImportedEvaluationFile.model_validate_json(source.read_text(encoding="utf-8-sig"))
    mapping = _read(root / "results/evaluation_maps" / f"{proofs['theorem']['id']}_{run_id}_mapping.json")["proof_mapping"]
    if imported.run_id != run_id or imported.theorem_id != proofs["theorem"]["id"]: raise ValueError("ChatGPT run_id or theorem_id mismatch")
    received = {x.proof_id for x in imported.evaluations}
    if received != set(mapping): raise ValueError("ChatGPT proof IDs are missing or unknown")
    document = _read(evaluations_file); by_id = {x.proof_id: x for x in imported.evaluations}
    for entry in document["evaluations"]:
        if not entry["proof_id"]: continue
        item = by_id[entry["proof_id"]]
        entry["chatgpt"] = {"status": "success", **item.model_dump()}
        local = _assessment(entry["math_shepherd"].get("mean_score"))
        entry["comparison"] = {"same_top_level_assessment": local == item.verdict if local else None, "agreement_label": "agreement" if local == item.verdict else "disagreement" if local else "unavailable"}
    document["chatgpt_metadata"] = {"evaluator_id": imported.evaluator_id, "prompt_version": imported.prompt_version, "imported_at": datetime.now(timezone.utc).isoformat()}
    atomic_text(evaluations_file, json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    update_excel(root, proofs, document)
    from .reporting import generate_dual_reports
    generate_dual_reports(root, proofs, document)
    return evaluations_file


def _sheet(book, title, headers):
    sheet = book[title] if title in book.sheetnames else book.create_sheet(title)
    if sheet.max_row >= 2 and sheet.cell(1, 1).value is None and sheet.cell(2, 1).value == headers[0]:
        sheet.delete_rows(1)
    if sheet.cell(1, 1).value is None:
        for column, header in enumerate(headers, 1):
            sheet.cell(1, column).value = header
        for cell in sheet[1]: cell.font = Font(bold=True); cell.fill = PatternFill("solid", fgColor="D9EAF7")
        sheet.freeze_panes = "A2"; sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    return sheet


def _upsert(sheet, key_columns: tuple[int, ...], row: list):
    key = tuple(row[index - 1] for index in key_columns)
    for values in sheet.iter_rows(min_row=2):
        if tuple(cell.value for cell in (values[index - 1] for index in key_columns)) == key:
            for cell, value in zip(values, row): cell.value = value
            return
    sheet.append(row)


def _finish_sheet(sheet, widths: dict[int, int], wrap_from: int = 1):
    for number, width in widths.items(): sheet.column_dimensions[get_column_letter(number)].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row[wrap_from - 1:]: cell.alignment = Alignment(wrap_text=True, vertical="top")


def update_excel(root: Path, proofs: dict, evaluations: dict) -> Path:
    path = root / "results/benchmark_results.xlsx"; path.parent.mkdir(parents=True, exist_ok=True)
    try: book = load_workbook(path) if path.exists() else Workbook()
    except PermissionError as exc: raise RuntimeError("Close benchmark_results.xlsx and retry.") from exc
    if "Sheet" in book.sheetnames and len(book.sheetnames) == 1: del book["Sheet"]
    results, proof_sheet, steps, runs = (_sheet(book, "Results", RESULT_HEADERS), _sheet(book, "Proofs", PROOF_HEADERS), _sheet(book, "MathShepherdSteps", STEP_HEADERS), _sheet(book, "Runs", RUN_HEADERS))
    by_id = {item["proof_id"]: item for item in evaluations["evaluations"]}; theorem = proofs["theorem"]
    for proof in proofs["proofs"]:
        entry = by_id.get(proof["proof_id"], {}); ms = entry.get("math_shepherd", {}); cg = entry.get("chatgpt", {})
        row = [proofs["run_id"], proofs["timestamp"], theorem["id"], theorem["title"], theorem.get("difficulty"), proofs["prompt"]["name"], proofs["prompt"]["version"], proof["proof_id"], proof["model_name"], proof["model_id"], proof["backend"], proof["status"], proof["runtime_seconds"], proof["input_tokens"], proof["output_tokens"], ms.get("mean_score"), ms.get("minimum_score"), ms.get("weakest_step"), *(cg.get("scores", {}).get(k) for k in ["assumption_handling", "logical_correctness", "completeness", "mathematical_rigor", "clarity"]), cg.get("total_score"), cg.get("verdict"), cg.get("first_error_step"), entry.get("comparison", {}).get("agreement_label"), "; ".join(cg.get("critical_issues", [])), "; ".join(cg.get("strengths", [])), cg.get("evaluator_comment")]
        _upsert(results, (1, 8), row); _upsert(proof_sheet, (1, 3), [proofs["run_id"], theorem["id"], proof["proof_id"], proof["model_name"], proof["model_id"], proof["proof"]])
        for step in ms.get("step_scores", []): _upsert(steps, (1, 3, 5), [proofs["run_id"], theorem["id"], proof["proof_id"], proof["model_name"], step["step_id"], step["step_text"], step["score"]])
    success = sum(p["status"] == "success" for p in proofs["proofs"]); meta = proofs.get("metadata", {}); pkg = meta.get("packages", {})
    _upsert(runs, (1,), [proofs["run_id"], proofs["timestamp"], theorem["id"], theorem["title"], proofs["prompt"]["name"], proofs["generation_settings"]["temperature"], proofs["generation_settings"]["top_p"], proofs["generation_settings"]["max_new_tokens"], proofs["generation_settings"]["seed"], len(proofs["proofs"]), success, len(proofs["proofs"]) - success, evaluations.get("math_shepherd_version"), evaluations.get("chatgpt_metadata", {}).get("prompt_version"), meta.get("git_commit"), ", ".join(meta.get("gpu_names", [])), meta.get("python_version"), pkg.get("transformers")])
    summary = _sheet(book, "Summary", ["Model", "Number of Proofs", "Average ChatGPT Score", "Average Math-Shepherd Score", "Correct Count", "Mostly Correct Count", "Flawed Count", "Incorrect Count"])
    # Summary rows are refreshed from all historical Results rows.
    while summary.max_row > 1: summary.delete_rows(2)
    names = sorted({row[8].value for row in results.iter_rows(min_row=2) if row[8].value})
    for name in names:
        rows = [row for row in results.iter_rows(min_row=2) if row[8].value == name]; cg = [row[23].value for row in rows if isinstance(row[23].value, (int, float))]; mscores = [row[15].value for row in rows if isinstance(row[15].value, (int, float))]; verdicts = [row[24].value for row in rows]
        summary.append([name, len(rows), sum(cg)/len(cg) if cg else None, sum(mscores)/len(mscores) if mscores else None, *(verdicts.count(v) for v in ["correct", "mostly_correct", "flawed", "incorrect"])])
    for sheet, widths, wrap in [(results, {1:25,4:28,9:28,10:42,28:40,29:40,30:55}, 1), (proof_sheet, {1:25,4:28,5:42,6:90}, 1), (steps, {1:25,4:28,6:70}, 1), (runs, {1:25,4:28,16:35}, 1), (summary, {1:28}, 1)]: _finish_sheet(sheet, widths, wrap)
    results.conditional_formatting.add(f"X2:X{max(2, results.max_row)}", ColorScaleRule(start_type="num", start_value=0, start_color="F8696B", mid_type="num", mid_value=5, mid_color="FFEB84", end_type="num", end_value=10, end_color="63BE7B"))
    temporary = path.with_suffix(".tmp.xlsx")
    try: book.save(temporary); temporary.replace(path)
    except PermissionError as exc: raise RuntimeError("Close benchmark_results.xlsx and retry.") from exc
    return path
