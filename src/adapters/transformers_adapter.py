"""Hugging Face causal language models with optional 4-bit loading."""
from .base import Adapter
from ..schemas import Generation, GenerationOutput


class TransformersAdapter(Adapter):
    def load(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        cfg = self.config
        kwargs = dict(cfg.backend_options)
        reserved = {"revision", "trust_remote_code", "device_map", "torch_dtype", "quantization_config"}
        if reserved.intersection(kwargs):
            raise ValueError("Use explicit YAML model fields instead of reserved backend_options")
        kwargs.update(revision=cfg.revision, trust_remote_code=cfg.trust_remote_code,
                      device_map=cfg.device, torch_dtype=cfg.dtype if cfg.dtype == "auto" else getattr(torch, cfg.dtype))
        if cfg.load_in_4bit:
            kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
        self.tokenizer = AutoTokenizer.from_pretrained(cfg.model_id, revision=cfg.revision,
                                                       trust_remote_code=cfg.trust_remote_code)
        self.model = AutoModelForCausalLM.from_pretrained(cfg.model_id, **kwargs)
        self.model.eval()

    def generate(self, prompt: str, settings: Generation) -> GenerationOutput:
        import torch
        from transformers import set_seed
        set_seed(settings.seed)
        if self.tokenizer.chat_template:
            actual = self.tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}], tokenize=False,
                add_generation_prompt=True, **self.config.chat_template_kwargs)
            inputs = self.tokenizer(actual, return_tensors="pt", add_special_tokens=False)
        else:
            actual = prompt
            inputs = self.tokenizer(actual, return_tensors="pt")
        inputs = inputs.to(self.model.device)
        sampling = settings.do_sample and settings.temperature > 0
        pad_token = self.tokenizer.pad_token_id
        kwargs = {"max_new_tokens": settings.max_new_tokens, "do_sample": sampling,
                  "pad_token_id": pad_token if pad_token is not None else self.tokenizer.eos_token_id,
                  "num_beams": 1, "repetition_penalty": 1.0}
        if sampling:
            kwargs.update(temperature=settings.temperature, top_p=settings.top_p, top_k=0)
        with torch.inference_mode():
            output = self.model.generate(**inputs, **kwargs)
        count = inputs["input_ids"].shape[-1]
        completion = output[0][count:]
        return GenerationOutput(text=self.tokenizer.decode(completion, skip_special_tokens=True),
                                token_count_input=count, token_count_output=len(completion),
                                metadata={"resolved_revision": getattr(self.model.config, "_commit_hash", None),
                                          "effective_generation": kwargs, "model_input": actual})

    def unload(self) -> None:
        if hasattr(self, "model"):
            del self.model
        if hasattr(self, "tokenizer"):
            del self.tokenizer
        super().unload()
