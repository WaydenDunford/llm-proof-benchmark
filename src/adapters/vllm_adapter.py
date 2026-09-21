"""Isolated vLLM worker: process exit guarantees GPU resources are released."""
import multiprocessing
from .base import Adapter
from ..schemas import Generation, GenerationOutput, ModelConfig


def _worker(connection, config: dict) -> None:
    try:
        from vllm import LLM, SamplingParams
        cfg = ModelConfig.model_validate(config)
        if cfg.load_in_4bit:
            raise ValueError("For vLLM set its supported quantization via backend_options")
        engine = LLM(model=cfg.model_id, revision=cfg.revision, dtype=cfg.dtype,
                     trust_remote_code=cfg.trust_remote_code, generation_config="vllm",
                     **cfg.backend_options)
        tokenizer = engine.get_tokenizer()
        connection.send({"ready": True})
        while True:
            request = connection.recv()
            if request is None:
                break
            prompt, options = request
            s = Generation.model_validate(options)
            actual = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True,
                **cfg.chat_template_kwargs) if tokenizer.chat_template else prompt
            params = SamplingParams(temperature=s.temperature if s.do_sample else 0,
                                    top_p=s.top_p if s.do_sample and s.temperature > 0 else 1,
                                    top_k=-1, max_tokens=s.max_new_tokens, seed=s.seed)
            result = engine.generate([actual], params, use_tqdm=False)[0]
            connection.send(GenerationOutput(text=result.outputs[0].text,
                token_count_input=len(result.prompt_token_ids), token_count_output=len(result.outputs[0].token_ids),
                metadata={"model_input": actual, "effective_generation": str(params),
                          "resolved_revision": None}).model_dump())
    except Exception as exc:
        connection.send({"error": f"{type(exc).__name__}: {exc}"})
    finally:
        connection.close()


class VLLMAdapter(Adapter):
    def _receive(self) -> dict:
        if not self.connection.poll(self.config.timeout_seconds):
            raise TimeoutError("vLLM worker timed out; increase timeout_seconds for model download/loading")
        data = self.connection.recv()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data

    def load(self) -> None:
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=_worker, args=(child, self.config.model_dump()))
        self.process.start()
        child.close()
        self._receive()

    def generate(self, prompt: str, settings: Generation) -> GenerationOutput:
        self.connection.send((prompt, settings.model_dump()))
        return GenerationOutput.model_validate(self._receive())

    def unload(self) -> None:
        if hasattr(self, "process"):
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=10)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
        if hasattr(self, "connection"):
            self.connection.close()
        super().unload()
