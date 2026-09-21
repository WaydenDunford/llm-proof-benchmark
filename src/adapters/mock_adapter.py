"""Deterministic plumbing fixture; scores are synthetic, not judgments."""
import json
from .base import Adapter
from ..schemas import Generation, GenerationOutput


class MockAdapter(Adapter):
    def generate(self, prompt: str, settings: Generation) -> GenerationOutput:
        if prompt.startswith("EVALUATE_PROOF"):
            data = json.loads(prompt.split("PAYLOAD_JSON\n", 1)[1])
            text = json.dumps({
                "anonymous_proof_id": data["anonymous_proof_id"],
                "scores": dict.fromkeys(["assumption_handling", "logical_correctness", "completeness", "mathematical_rigor", "clarity"], 2),
                "global_score": 10, "verdict": "correct", "first_error_step": None,
                "critical_issues": [], "strengths": ["Synthetic demo fixture"],
                "evaluator_comment": "MOCK ONLY: fixed synthetic score; no mathematical assessment was performed."})
        elif prompt.startswith("CRITIQUE_PROOF"):
            text = "Check that S1 invokes the integer assumption. State the integer witness explicitly in S2. No external references are needed."
        else:
            text = ("Goal: prove that the sum of two even integers is even.\n\n"
                    "Assumptions: a and b are even integers. Plan: use the definition of evenness.\n\n"
                    "S1. There are integers m and n with a = 2m and b = 2n.\n"
                    "S2. Then a + b = 2(m + n), and m + n is an integer.\n"
                    "S3. By definition, a + b is even. This proves the claim.")
        return GenerationOutput(text=text, metadata={"synthetic": True, "token_counts": "unavailable"})
