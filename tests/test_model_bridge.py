import argparse
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "codex-model-bridge"
    / "scripts"
    / "model_bridge.py"
)
SPEC = importlib.util.spec_from_file_location("model_bridge", SCRIPT_PATH)
assert SPEC and SPEC.loader
model_bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(model_bridge)


def sample_model(model_id: str, env_name: str) -> dict:
    return {
        "id": model_id,
        "endpoint": "https://example.com/v1/chat/completions",
        "api_key_envs": [env_name],
        "model": model_id,
    }


class ModelBridgeTests(unittest.TestCase):
    def test_schema_only_exposes_supported_reasoning_controls(self) -> None:
        unsupported = sample_model("plain", "PLAIN_KEY")
        supported = sample_model("reasoner", "REASONER_KEY")
        supported["capabilities"] = {"thinking": True, "reasoning_effort": True}

        plain_properties = model_bridge.tool_schema(unsupported)["inputSchema"]["properties"]
        reasoner_properties = model_bridge.tool_schema(supported)["inputSchema"]["properties"]

        self.assertNotIn("thinking", plain_properties)
        self.assertNotIn("reasoning_effort", plain_properties)
        self.assertIn("thinking", reasoner_properties)
        self.assertIn("reasoning_effort", reasoner_properties)

    def test_old_extra_body_config_infers_thinking_support(self) -> None:
        model = sample_model("legacy", "LEGACY_KEY")
        model["extra_body"] = {"thinking": {"type": "enabled"}}

        properties = model_bridge.tool_schema(model)["inputSchema"]["properties"]

        self.assertIn("thinking", properties)
        self.assertEqual(model_bridge.default_thinking_mode(model), "enabled")

    def test_custom_thinking_field_and_boolean_values(self) -> None:
        model = sample_model("boolean-reasoner", "BOOLEAN_KEY")
        model["capabilities"] = {
            "thinking": True,
            "thinking_field": "enable_thinking",
            "thinking_values": {"enabled": True, "disabled": False},
        }
        model["extra_body"] = {"enable_thinking": False}

        self.assertEqual(model_bridge.thinking_field_for(model), "enable_thinking")
        self.assertIs(model_bridge.thinking_value_for(model, "enabled"), True)
        self.assertEqual(model_bridge.default_thinking_mode(model), "disabled")

    def test_chat_uses_custom_thinking_mapping(self) -> None:
        model = sample_model("boolean-reasoner", "BOOLEAN_KEY")
        model["capabilities"] = {
            "thinking": True,
            "thinking_field": "enable_thinking",
            "thinking_values": {"enabled": True, "disabled": False},
        }
        captured: dict = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                return False

            def read(self) -> bytes:
                return b'{"choices":[{"message":{"content":"OK"},"finish_reason":"stop"}]}'

        def fake_urlopen(request, timeout):
            captured.update(json.loads(request.data.decode("utf-8")))
            self.assertGreater(timeout, 0)
            return FakeResponse()

        with mock.patch.dict(os.environ, {"BOOLEAN_KEY": "secret"}, clear=True):
            with mock.patch.object(model_bridge.urllib.request, "urlopen", side_effect=fake_urlopen):
                result = model_bridge.chat_completion(model, "test", thinking="enabled")

        self.assertEqual(result["content"], "OK")
        self.assertIs(captured["enable_thinking"], True)
        self.assertNotIn("thinking", captured)

    def test_status_reports_key_name_without_exposing_value(self) -> None:
        config = {"models": [sample_model("ready", "READY_KEY")]}
        secret = "do-not-print-this-secret"

        with mock.patch.dict(os.environ, {"READY_KEY": secret}, clear=True):
            status = model_bridge.format_bridge_status(config)

        self.assertIn("key found via READY_KEY", status)
        self.assertNotIn(secret, status)

    def test_compare_skips_models_without_detected_keys_by_default(self) -> None:
        config = {
            "models": [
                sample_model("ready", "READY_KEY"),
                sample_model("missing", "MISSING_KEY"),
            ]
        }
        server = model_bridge.McpServer(config)
        fake_result = {"content": "ready response", "usage": {}}

        with mock.patch.dict(os.environ, {"READY_KEY": "secret"}, clear=True):
            with mock.patch.object(model_bridge, "chat_completion", return_value=fake_result) as call:
                output = server.compare_models({"prompt": "test"})

        self.assertIn("Skipped models without detected API keys: missing", output)
        self.assertIn("ready response", output)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.args[0]["id"], "ready")

    def test_configure_prompts_for_thinking_and_writes_no_secret(self) -> None:
        answers = iter(
            [
                "custom",
                "my-model",
                "",
                "",
                "https://example.com/v1/chat/completions",
                "remote-model",
                "MY_MODEL_API_KEY",
                "",
                "",
                "",
                "",
                "y",
                "",
                "",
                "y",
                "n",
                "",
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            with mock.patch("builtins.input", side_effect=lambda _prompt: next(answers)):
                result = model_bridge.command_configure(argparse.Namespace(config=str(config_path)))
            config = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertEqual(config["models"][0]["api_key_envs"], ["MY_MODEL_API_KEY"])
        self.assertTrue(config["models"][0]["capabilities"]["thinking"])
        self.assertEqual(config["models"][0]["capabilities"]["thinking_field"], "thinking")
        self.assertEqual(
            config["models"][0]["capabilities"]["thinking_values"]["enabled"],
            {"type": "enabled"},
        )
        self.assertEqual(config["models"][0]["extra_body"]["thinking"]["type"], "enabled")
        self.assertNotIn("secret", json.dumps(config).lower())


if __name__ == "__main__":
    unittest.main()
