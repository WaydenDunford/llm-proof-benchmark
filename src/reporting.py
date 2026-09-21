"""Readable Markdown and escaped, standalone HTML with a searchable index."""
import html
import json
from pathlib import Path
from jinja2 import Environment
from .schemas import RunResult
from .utils import atomic_text


def generate_dual_reports(root: Path, proofs: dict, evaluations: dict) -> tuple[Path, Path]:
    """Write the detailed per-run report from the two canonical JSON files."""
    by_id = {item["proof_id"]: item for item in evaluations["evaluations"]}
    theorem = proofs["theorem"]
    rows = []
    parts = ["# Benchmark Report", f"## Theorem\n\n**{theorem['id']}: {theorem['title']}**\n\n{theorem['statement']}", "## Benchmark configuration", f"Prompt: `{proofs['prompt']['name']}` ({proofs['prompt']['version']})\n\n```json\n{json.dumps(proofs['generation_settings'], indent=2)}\n```", "## Results summary", "| Model | Math-Shepherd | ChatGPT | Verdict | Agreement |\n| --- | ---: | ---: | --- | --- |"]
    for proof in proofs["proofs"]:
        entry = by_id.get(proof["proof_id"], {}); ms = entry.get("math_shepherd", {}); cg = entry.get("chatgpt", {})
        parts[-1] += f"\n| {proof['model_name']} | {ms.get('mean_score', '—')} | {str(cg.get('total_score', 'pending')) + '/10' if cg.get('status') == 'success' else 'pending'} | {cg.get('verdict', 'pending')} | {entry.get('comparison', {}).get('agreement_label', 'pending')} |"
        rows.append((proof, entry))
    for proof, entry in rows:
        ms, cg = entry.get("math_shepherd", {}), entry.get("chatgpt", {})
        parts += [f"## Model: {proof['model_name']}", "### Generated proof", proof.get("proof") or proof.get("error", "No proof generated."), "### Math-Shepherd evaluation", json.dumps(ms, indent=2), "### ChatGPT evaluation", json.dumps(cg, indent=2), "### Agreement", json.dumps(entry.get("comparison", {}), indent=2)]
    stem = f"{theorem['id']}_{proofs['run_id']}"; directory = root / "results/reports"; md = directory / f"{stem}.md"; html_path = directory / f"{stem}.html"
    atomic_text(md, "\n\n".join(parts) + "\n")
    blocks = "".join(f"<article><h2>{html.escape(proof['model_name'])}</h2><p><b>Math-Shepherd:</b> {html.escape(str(entry.get('math_shepherd', {}).get('mean_score', '—')))} · <b>ChatGPT:</b> {html.escape(str(entry.get('chatgpt', {}).get('total_score', 'pending')))}</p><details open><summary>Generated proof</summary><pre>{html.escape(proof.get('proof') or proof.get('error', ''))}</pre></details><h3>ChatGPT evaluation</h3><pre>{html.escape(json.dumps(entry.get('chatgpt', {}), indent=2))}</pre></article>" for proof, entry in rows)
    body = f"<h1>{html.escape(theorem['id'])} — {html.escape(theorem['title'])}</h1><p>Manual ChatGPT Plus and local Math-Shepherd comparison.</p>{blocks}"
    atomic_text(html_path, page(f"{theorem['id']} benchmark", body))
    update_index(directory)
    return md, html_path

STYLE = """
:root{color-scheme:light;--ink:#192c3b;--muted:#536778;--line:#dce4ea}
*{box-sizing:border-box}body{font:16px/1.65 system-ui,sans-serif;color:var(--ink);background:#f3f6f8;margin:0}
main{max-width:1120px;margin:40px auto;padding:32px;background:white;border:1px solid var(--line);border-radius:14px}
h1,h2,h3{line-height:1.25}h1{font-size:34px}h2{margin-top:36px}a{color:#006f82}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.75 ui-monospace,monospace;background:#f5f8fa;padding:20px;border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:12px;text-align:left;border-bottom:1px solid var(--line)}
th{background:#edf3f5}article{padding:12px 0 24px;border-bottom:1px solid var(--line)}summary{cursor:pointer;font-weight:650;padding:10px 0}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;background:#e7edf1;font-size:13px}.correct,.mostly_correct{background:#dcf3e8}.flawed,.incorrect,.error{background:#ffe5de}
.notice{padding:14px 18px;background:#fff3ce;border-left:4px solid #d4a137}.muted{color:var(--muted)}
input{width:100%;padding:12px;border:1px solid var(--line);border-radius:6px;margin:14px 0}.table-wrap{overflow-x:auto}
@media(max-width:700px){main{margin:0;padding:18px;border-radius:0}h1{font-size:27px}}
"""


def page(title: str, body: str) -> str:
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{STYLE}</style></head><body><main>{body}</main></body></html>'


def cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def fenced(text: str) -> str:
    import re
    fence = "`" * max(3, 1 + max((len(m.group()) for m in re.finditer(r"`+", text)), default=0))
    return f"{fence}text\n{text}\n{fence}"


def report_context(run: RunResult) -> dict:
    by_response = {run.anonymous_mapping[e.anonymous_proof_id]: e
                   for e in run.evaluations if e.anonymous_proof_id in run.anonymous_mapping}
    rows = []
    for response in run.responses:
        record = by_response.get(response.response_id)
        evaluation = record.evaluation if record and record.status == "success" else None
        rows.append({"response": response, "evaluation": evaluation,
                     "evaluation_error": record.error if record else None})
    scored = [row for row in rows if row["evaluation"]]
    best = max((r["evaluation"].global_score for r in scored), default=None)
    winners = [f'{r["response"].model_name} (rep {r["response"].repetition})' for r in scored if r["evaluation"].global_score == best]
    synthetic = run.metadata.get("synthetic") or bool(run.evaluator and run.evaluator.get("synthetic"))
    return {"run": run, "rows": rows, "best": best, "winners": winners, "synthetic": synthetic}


HTML_TEMPLATE = """
<a href="index.html">← All experiments</a>
<p class="muted">TEXTUAL THEOREM PROVING · {{ run.timestamp }}</p>
<h1>{{ run.theorem.id }} — {{ run.theorem.title }}</h1>
{% if synthetic %}<p class="notice"><strong>MOCK DEMONSTRATION.</strong> Proofs and/or scores are synthetic fixtures, not research findings.</p>{% endif %}
<h2>Theorem</h2><pre>{{ run.theorem.statement }}</pre>
<h3>Assumptions</h3><ul>{% for a in run.theorem.assumptions %}<li>{{ a }}</li>{% endfor %}</ul>
<h3>Allowed context</h3><ul>{% for a in run.theorem.allowed_context %}<li>{{ a }}</li>{% endfor %}</ul>
<h2>Comparison summary</h2><div class="table-wrap"><table><thead><tr><th>Model / repetition</th><th>Assumptions</th><th>Logic</th><th>Complete</th><th>Rigor</th><th>Clarity</th><th>Total</th><th>Verdict</th></tr></thead><tbody>
{% for row in rows %}{% set r = row.response %}{% set e = row.evaluation %}
<tr><td><a href="#response-{{ loop.index }}">{{ r.model_name }} / {{ r.repetition }}</a></td>
{% if e %}{% for value in e.scores.model_dump().values() %}<td>{{ value }}/2</td>{% endfor %}<td>{{ e.global_score }}/10</td><td><span class="badge {{ e.verdict }}">{{ e.verdict }}</span></td>
{% else %}<td colspan="6">—</td><td>{{ 'generation error' if r.status == 'error' else ('evaluation error' if row.evaluation_error else 'not evaluated') }}</td>{% endif %}</tr>{% endfor %}
</tbody></table></div><p>Highest score: {{ best if best is not none else 'unavailable' }}. {{ winners | join(', ') }}</p>
<p class="muted">One evaluator per experiment; evaluator disagreement is not measured. Scores concern the final proof only. LLM judgments require human review.</p>
<h2>Benchmark configuration</h2><p>Strategy: <strong>{{ run.prompt.name }}</strong> · Run: {{ run.run_id }}</p><pre>{{ settings }}</pre>
{% if run.evaluator %}<p class="muted">Evaluation: {{ run.evaluator.mode or 'unknown' }} · evaluator ID: {{ run.evaluator.evaluator_id or 'unknown' }} · template: {{ run.evaluator.prompt_version or 'unknown' }}</p>{% endif %}
{% for row in rows %}{% set r = row.response %}{% set e = row.evaluation %}
<article id="response-{{ loop.index }}"><h2>{{ r.model_name }} <span class="badge">Repetition {{ r.repetition }}</span></h2>
<p class="muted">{{ r.model_id }} · {{ r.backend }} · {{ r.runtime_seconds }} s (including loading/cleanup) · seed {{ r.seed }} · tokens {{ r.token_count_input }} → {{ r.token_count_output }}</p>
{% if r.error %}<p class="notice">{{ r.error }}</p>{% endif %}
<details open><summary>Generated proof{% if r.proof_v2 %} — final revision{% endif %}</summary><pre>{{ r.proof or 'No proof generated.' }}</pre></details>
{% if r.critique %}<details><summary>Original proof and critique</summary><h3>Proof v1</h3><pre>{{ r.proof_v1 }}</pre><h3>Critique</h3><pre>{{ r.critique }}</pre></details>{% endif %}
<h3>Evaluation</h3>{% if e %}<p><span class="badge {{ e.verdict }}">{{ e.verdict }}</span> <strong>{{ e.global_score }}/10</strong> · First error: {{ e.first_error_step or 'none reported' }}</p>
<ul>{% for name, score in e.scores.model_dump().items() %}<li>{{ name | replace('_', ' ') }}: {{ score }}/2</li>{% endfor %}</ul>
<h3>Critical issues</h3><ul>{% for issue in e.critical_issues %}<li>{{ issue }}</li>{% else %}<li>None reported.</li>{% endfor %}</ul>
<h3>Strengths</h3><ul>{% for strength in e.strengths %}<li>{{ strength }}</li>{% endfor %}</ul><h3>Evaluator comment</h3><pre>{{ e.evaluator_comment }}</pre>
{% else %}<p>{{ row.evaluation_error or 'Not evaluated.' }}</p>{% endif %}</article>{% endfor %}
<details><summary>Reproducibility metadata</summary><pre>{{ metadata }}</pre></details>
{% if run.theorem.reference_proof %}<details><summary>Reference proof (not sent to models or judge)</summary><pre>{{ run.theorem.reference_proof }}</pre></details>{% endif %}
"""


def generate_reports(result_path: Path, reports_dir: Path | None = None) -> tuple[Path, Path]:
    run = RunResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    directory = reports_dir or result_path.parent.parent / "reports"
    context = report_context(run)
    stem = f"{run.theorem.id}_{run.run_id}"
    settings = json.dumps({"generation": run.generation_settings.model_dump(),
                           "benchmark": run.benchmark_settings.model_dump()}, indent=2)
    metadata = json.dumps({"environment": run.metadata, "evaluator": run.evaluator,
                           "models": [r.model_config_snapshot for r in run.responses]}, indent=2)
    md = ["# Benchmark report", f"**{run.theorem.id}: {run.theorem.title}**", f"Date: {run.timestamp}"]
    if context["synthetic"]:
        md.append("> **MOCK DEMONSTRATION — synthetic fixtures, not research findings.**")
    md += ["## Theorem", run.theorem.statement, "### Assumptions",
           "\n".join(f"- {a}" for a in run.theorem.assumptions), "### Allowed context",
           "\n".join(f"- {a}" for a in run.theorem.allowed_context), "## Benchmark configuration",
           f"Run: `{run.run_id}` · Prompt: **{run.prompt['name']}**", fenced(settings)]
    if run.evaluator:
        md += ["### Evaluation metadata", f"Mode: `{run.evaluator.get('mode', 'unknown')}` · Evaluator: `{run.evaluator.get('evaluator_id', 'unknown')}` · Template version: `{run.evaluator.get('prompt_version', 'unknown')}`"]
    for row in context["rows"]:
        r, e = row["response"], row["evaluation"]
        md += [f"## {r.model_name} — repetition {r.repetition}",
               f"Model: `{r.model_id}` · Backend: `{r.backend}` · Seed: {r.seed}\n\nRuntime including loading/cleanup: {r.runtime_seconds}s · Tokens: {r.token_count_input} → {r.token_count_output}",
               "### Generated proof", r.proof or "No proof generated."]
        if r.error:
            md += ["### Generation error", fenced(r.error)]
        if r.critique:
            md += ["### Original proof (v1)", r.proof_v1, "### Critique", r.critique,
                   "The generated proof above is v2; only v2 is evaluated."]
        md += ["### Evaluation"]
        if e:
            md += ["\n".join(f"- {name.replace('_', ' ').capitalize()}: {score}/2" for name, score in e.scores.model_dump().items())
                   + f"\n- Total: {e.global_score}/10\n- Verdict: {e.verdict}\n- First error step: {e.first_error_step or 'none reported'}",
                   "### Critical issues", "\n".join(f"- {i}" for i in e.critical_issues) or "None reported.",
                   "### Strengths", "\n".join(f"- {s}" for s in e.strengths) or "None reported.",
                   "### Evaluator comment", e.evaluator_comment]
        else:
            md.append(row["evaluation_error"] or "Not evaluated.")
        md.append("---")
    md += ["## Results summary", "| Model / repetition | Assumptions | Logic | Complete | Rigor | Clarity | Total | Verdict |\n| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in context["rows"]:
        r, e = row["response"], row["evaluation"]
        values = [f"{r.model_name} / {r.repetition}"]
        values += [*e.scores.model_dump().values(), e.global_score, e.verdict] if e else ["—"] * 6 + ["generation error" if r.status == "error" else "not scored"]
        md[-1] += "\n| " + " | ".join(cell(v) for v in values) + " |"
    md += [f"Highest score: {context['best'] if context['best'] is not None else 'unavailable'}. " + ", ".join(context["winners"]),
           "Evaluator disagreement: not measured (one evaluator per experiment). LLM scores are judgments, not formal verification.",
           "### Main errors per model"]
    for row in context["rows"]:
        e = row["evaluation"]
        issues = "; ".join(e.critical_issues) or "None reported" if e else row["response"].error or row["evaluation_error"] or "Not evaluated"
        md.append(f"- {row['response'].model_name} / {row['response'].repetition}: {issues}")
    md += ["## Reproducibility metadata", fenced(metadata)]
    if run.theorem.reference_proof:
        md += ["## Reference proof (not sent to models or judge)", run.theorem.reference_proof]
    md_path, html_path = directory / f"{stem}.md", directory / f"{stem}.html"
    atomic_text(md_path, "\n\n".join(md) + "\n")
    body = Environment(autoescape=True).from_string(HTML_TEMPLATE).render(**context, settings=settings, metadata=metadata)
    atomic_text(html_path, page(f"{run.theorem.id} benchmark", body))
    index_item = {"run_id": run.run_id, "date": run.timestamp, "theorem": run.theorem.id,
                  "title": run.theorem.title, "prompt": run.prompt["name"],
                  "models": ", ".join(dict.fromkeys(r.model_name for r in run.responses)),
                  "best_score": context["best"], "synthetic": bool(context["synthetic"]),
                  "html": html_path.name, "markdown": md_path.name}
    atomic_text(directory / f"{stem}.index.json", json.dumps(index_item, indent=2))
    update_index(directory)
    return md_path, html_path


def update_index(directory: Path) -> None:
    entries = [json.loads(p.read_text(encoding="utf-8")) for p in directory.glob("*.index.json")]
    entries.sort(key=lambda item: item["date"], reverse=True)
    md = ["# Benchmark experiments", "Search the HTML index by theorem, model, prompt or experiment date.",
          "| Date | Theorem | Prompt | Models | Best score | Report |\n| --- | --- | --- | --- | --- | --- |"]
    rows = []
    for e in entries:
        score = str(e["best_score"]) if e["best_score"] is not None else "—"
        if e["synthetic"]:
            score += " (MOCK)"
        md[-1] += f"\n| {cell(e['date'])} | {cell(e['theorem'])} | {cell(e['prompt'])} | {cell(e['models'])} | {score} | [HTML]({e['html']}) · [Markdown]({e['markdown']}) |"
        values = [e["date"], e["theorem"] + " — " + e["title"], e["prompt"], e["models"], score]
        rows.append("<tr>" + "".join(f"<td>{html.escape(v)}</td>" for v in values)
                    + f'<td><a href="{html.escape(e["html"], quote=True)}">HTML</a> · <a href="{html.escape(e["markdown"], quote=True)}">Markdown</a></td></tr>')
    body = '<p class="muted">TEXTUAL THEOREM PROVING</p><h1>Benchmark experiments</h1><p>Browse proofs, compare model judgments, and inspect reproducibility metadata.</p><label for="search">Filter by theorem, model, prompt or date</label><input id="search" type="search" placeholder="e.g. T001, qwen, structured…"><div class="table-wrap"><table><thead><tr><th>Date</th><th>Theorem</th><th>Prompt</th><th>Models</th><th>Best score</th><th>Report</th></tr></thead><tbody>'
    body += "".join(rows) + '</tbody></table></div><script>document.getElementById("search").addEventListener("input",e=>{const q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script>'
    atomic_text(directory / "index.md", "\n\n".join(md) + "\n")
    atomic_text(directory / "index.html", page("Benchmark experiments", body))
