"""Exercise the real API client against an in-process HTTP fixture."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from src.adapters.openai_compatible_adapter import OpenAICompatibleAdapter
from src.schemas import Generation, ModelConfig


def test_api_request_and_completion(monkeypatch):
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            observed.append((self.path, self.headers.get("Authorization"),
                json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            body = json.dumps({"choices": [{"message": {"content": "S1. Example proof."}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8},
                "system_fingerprint": "fixture"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("TEST_PROOF_KEY", "fixture-secret")
    try:
        config = ModelConfig(name="test", model_id="served-model", backend="openai-compatible",
            base_url=f"http://127.0.0.1:{server.server_port}/v1", api_key_env="TEST_PROOF_KEY")
        output = OpenAICompatibleAdapter(config).generate("Prove a theorem", Generation(do_sample=False))
        path, authorization, payload = observed[0]
        assert path == "/v1/chat/completions"
        assert authorization == "Bearer fixture-secret"
        assert payload["temperature"] == 0 and payload["top_p"] == 1
        assert payload["seed"] == 42 and payload["max_tokens"] == 4096
        assert payload["messages"] == [{"role": "user", "content": "Prove a theorem"}]
        assert output.text == "S1. Example proof."
        assert output.token_count_input == 12 and output.token_count_output == 8
        assert "fixture-secret" not in output.model_dump_json()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
