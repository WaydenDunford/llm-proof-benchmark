"""Validated configuration, run, and blind evaluator contracts."""
from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]
Backend = Literal["transformers", "vllm", "openai-compatible", "mock"]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Generation(Schema):
    temperature: float = Field(default=0.2, ge=0)
    top_p: float = Field(default=0.95, gt=0, le=1)
    max_new_tokens: int = Field(default=4096, gt=0)
    do_sample: bool = True
    seed: int = Field(default=42, ge=0, le=2**32 - 1)


class ModelConfig(Schema):
    name: Identifier
    model_id: str
    enabled: bool = True
    backend: Backend = "transformers"
    revision: str = "main"
    device: str = "auto"
    dtype: Literal["auto", "float16", "bfloat16", "float32"] = "auto"
    load_in_4bit: bool = False
    trust_remote_code: bool = False
    chat_template_kwargs: dict[str, Any] = Field(default_factory=dict)
    backend_options: dict[str, Any] = Field(default_factory=dict)
    base_url: str = "http://localhost:8000/v1"
    api_key_env: str = "LLM_API_KEY"
    timeout_seconds: float = Field(default=300, gt=0)


class ModelsConfig(Schema):
    models: list[ModelConfig]

    @model_validator(mode="after")
    def unique_names(self):
        names = [m.name for m in self.models]
        if len(names) != len(set(names)):
            raise ValueError("Model names must be unique")
        return self


class BenchmarkOptions(Schema):
    repetitions: int = Field(default=1, ge=1)
    save_prompts: bool = True
    save_raw_outputs: bool = True


class BenchmarkConfig(Schema):
    generation: Generation = Field(default_factory=Generation)
    benchmark: BenchmarkOptions = Field(default_factory=BenchmarkOptions)
    evaluation: "EvaluationOptions" = Field(default_factory=lambda: EvaluationOptions())


class EvaluationOptions(Schema):
    """Controls local preparation of blind, manually evaluated proof bundles."""
    mode: Literal["manual_chatgpt"] = "manual_chatgpt"
    blind: bool = True
    randomize_proof_order: bool = True
    random_seed: int = Field(default=42, ge=0, le=2**32 - 1)
    prompt_version: Identifier = "chatgpt_evaluator_v1"


class EvaluatorConfig(Schema):
    model: ModelConfig
    generation: Generation = Field(default_factory=lambda: Generation(temperature=0, do_sample=False))
    retries: int = Field(default=1, ge=0, le=5)


class Theorem(Schema):
    id: Identifier
    title: str
    domain: str = "mathematics"
    statement: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    allowed_context: list[str] = Field(default_factory=list)
    reference_proof: str | None = None
    tags: list[str] = Field(default_factory=list)
    difficulty: str = "unspecified"


class GenerationOutput(Schema):
    text: str
    token_count_input: int | None = None
    token_count_output: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Response(Schema):
    response_id: str
    model_name: str
    model_id: str
    backend: Backend
    model_config_snapshot: dict[str, Any]
    repetition: int
    seed: int
    status: Literal["success", "error"] = "error"
    proof: str | None = None
    proof_v1: str | None = None
    proof_v2: str | None = None
    critique: str | None = None
    runtime_seconds: float = 0
    token_count_input: int | None = None
    token_count_output: int | None = None
    stages: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


Score = Annotated[int, Field(strict=True, ge=0, le=2)]


class Scores(Schema):
    assumption_handling: Score
    logical_correctness: Score
    completeness: Score
    mathematical_rigor: Score
    clarity: Score


class Evaluation(Schema):
    anonymous_proof_id: str
    scores: Scores
    global_score: Annotated[int, Field(strict=True, ge=0, le=10)]
    verdict: Literal["correct", "mostly_correct", "flawed", "incorrect"]
    first_error_step: str | None
    critical_issues: list[str]
    strengths: list[str]
    evaluator_comment: str

    @model_validator(mode="after")
    def total_matches(self):
        if self.global_score != sum(self.scores.model_dump().values()):
            raise ValueError("global_score must equal the sum of the five scores")
        return self


class EvaluationRecord(Schema):
    anonymous_proof_id: str
    status: Literal["success", "error"]
    evaluation: Evaluation | None = None
    error: str | None = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)


class StepEvaluation(Schema):
    """A human evaluator's judgment of one proof step shared with Math-Shepherd."""
    step_id: str = Field(pattern=r"^S[0-9]+$")
    score: Score
    status: Literal["sound", "minor_gap", "invalid"]
    comment: str


class ImportedEvaluation(Schema):
    """One result supplied by a human-operated ChatGPT Plus evaluation session."""
    proof_id: str = Field(pattern=r"^P[0-9]{3}$")
    scores: Scores
    total_score: Annotated[int, Field(strict=True, ge=0, le=10)]
    verdict: Literal["correct", "mostly_correct", "flawed", "incorrect"]
    first_error_step: str | None
    critical_issues: list[str]
    strengths: list[str]
    evaluator_comment: str
    step_evaluations: list[StepEvaluation] = Field(default_factory=list)

    @model_validator(mode="after")
    def total_matches(self):
        if self.total_score != sum(self.scores.model_dump().values()):
            raise ValueError("total_score must equal the sum of the five scores")
        return self


class ImportedEvaluationFile(Schema):
    run_id: str
    theorem_id: Identifier
    evaluator_id: Identifier = "chatgpt_plus"
    prompt_version: Identifier = "chatgpt_evaluator_v1"
    evaluations: list[ImportedEvaluation]

    @model_validator(mode="after")
    def unique_ids(self):
        proof_ids = [item.proof_id for item in self.evaluations]
        if len(proof_ids) != len(set(proof_ids)):
            raise ValueError("Each proof_id may appear only once")
        return self


class RunResult(Schema):
    schema_version: str = "1.0"
    run_id: str
    timestamp: str
    theorem: Theorem
    prompt: dict[str, Any]
    generation_settings: Generation
    benchmark_settings: BenchmarkOptions
    metadata: dict[str, Any]
    responses: list[Response] = Field(default_factory=list)
    evaluator: dict[str, Any] | None = None
    anonymous_mapping: dict[str, str] = Field(default_factory=dict)
    evaluations: list[EvaluationRecord] = Field(default_factory=list)
    evaluation_imports: list[dict[str, Any]] = Field(default_factory=list)
    models: list[dict[str, Any]] = Field(default_factory=list)
