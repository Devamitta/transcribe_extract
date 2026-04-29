"""Tests for DeepSeek provider and provider routing."""

import importlib
import os
import unittest
from unittest.mock import patch


class DeepSeekProviderRoutingTests(unittest.TestCase):
    """Tests for provider selection and model configuration."""

    def _reload_provider(self) -> object:
        import tools.provider

        return importlib.reload(tools.provider)

    def test_deepseek_provider_imports_correct_module(self) -> None:
        """Verify that PROVIDER=deepseek routes to deepseek module."""
        with patch.dict(
            "os.environ", {"PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "test-key"}
        ):
            provider = self._reload_provider()

            self.assertEqual(provider.PROVIDER, "deepseek")
            self.assertTrue(hasattr(provider, "generate_content"))
            self.assertTrue(callable(provider.generate_content))

    def test_deepseek_models_configured(self) -> None:
        """Verify DeepSeek model configuration matches spec."""
        from tools.provider import DEEPSEEK_WORK_MODELS, DEEPSEEK_TEST_MODELS

        self.assertEqual(DEEPSEEK_WORK_MODELS, ["deepseek-v4-flash"])
        self.assertEqual(DEEPSEEK_TEST_MODELS, ["deepseek-v4-flash"])

    def test_provider_routing_accepts_deepseek(self) -> None:
        """Verify provider.py handles PROVIDER=deepseek without error."""
        with patch.dict(
            "os.environ", {"PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "test-key"}
        ):
            provider = self._reload_provider()

            # Should not raise or exit
            self.assertEqual(provider.PROVIDER, "deepseek")

    def test_error_message_lists_deepseek(self) -> None:
        """Verify error message mentions deepseek as supported provider."""
        from tools.provider import PROVIDER_ERROR_MSG

        self.assertIn("deepseek", PROVIDER_ERROR_MSG)


class DeepSeekClientTests(unittest.TestCase):
    """Tests for DeepSeek client functionality."""

    def test_list_models_returns_expected_models(self) -> None:
        """Verify list_models returns the supported model list."""
        from tools.deepseek import list_models

        models = list_models()
        self.assertIn("deepseek-v4-flash", models)
        self.assertIn("deepseek-v4-pro", models)
        self.assertEqual(len(models), 2)

    def test_generate_content_success(self) -> None:
        """Test generate_content returns non-empty text (integration test)."""
        if not os.getenv("DEEPSEEK_API_KEY"):
            self.skipTest("requires DEEPSEEK_API_KEY")

        from tools.deepseek import generate_content

        result = generate_content(
            contents="Say 'test'",
            system_instruction="Be brief. Just output one word.",
            model="deepseek-v4-flash",
            max_output_tokens=50,
        )

        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_get_working_key_integration(self) -> None:
        """Test get_working_key with actual API (integration test)."""
        if not os.getenv("DEEPSEEK_API_KEY"):
            self.skipTest("requires DEEPSEEK_API_KEY")

        from tools.deepseek import get_working_key

        result = get_working_key()
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
