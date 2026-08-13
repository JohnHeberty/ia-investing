from __future__ import annotations

import pytest

from ia_investing.ai._pricing import estimate_cost
from ia_investing.ai.gateway import GatewayProvider, OpenAIGateway, create_gateway_provider
from ia_investing.settings import Settings


class TestSettingsAcceptsLiteLLM:
    def test_litellm_provider_is_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AI__PROVIDER", "litellm")
        monkeypatch.setenv("AI__GATEWAY__BASE_URL", "http://100.91.54.69:4000/v1")
        monkeypatch.setenv("AI__GATEWAY__API_KEY", "sk-litellm-master")
        monkeypatch.setenv("AI__GATEWAY__MODEL", "qwen")

        settings = Settings(_env_file=None)
        assert settings.ai.provider == "litellm"

    def test_litellm_provider_rejects_empty_base_url_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APPLICATION__ENVIRONMENT", "production")
        monkeypatch.setenv("AI__PROVIDER", "litellm")
        monkeypatch.setenv("AI__GATEWAY__API_KEY", "sk-litellm-master")
        monkeypatch.delenv("AI__GATEWAY__BASE_URL", raising=False)

        with pytest.raises(Exception, match="AI__GATEWAY__BASE_URL"):
            Settings(_env_file=None)

    def test_litellm_provider_rejects_empty_api_key_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APPLICATION__ENVIRONMENT", "production")
        monkeypatch.setenv("AI__PROVIDER", "litellm")
        monkeypatch.setenv("AI__GATEWAY__BASE_URL", "http://100.91.54.69:4000/v1")
        monkeypatch.delenv("AI__GATEWAY__API_KEY", raising=False)

        with pytest.raises(Exception, match="AI__GATEWAY__API_KEY"):
            Settings(_env_file=None)

    def test_gateway_provider_also_requires_base_url_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APPLICATION__ENVIRONMENT", "production")
        monkeypatch.setenv("AI__PROVIDER", "gateway")
        monkeypatch.delenv("AI__GATEWAY__BASE_URL", raising=False)

        with pytest.raises(Exception, match="AI__GATEWAY__BASE_URL"):
            Settings(_env_file=None)


class TestGatewayFactoryLiteLLM:
    def test_create_gateway_provider_with_openai_sdk(self) -> None:
        provider = create_gateway_provider(
            provider="openai",
            api_key="sk-test-key",
            default_model="qwen",
            base_url="http://100.91.54.69:4000/v1",
        )
        assert isinstance(provider, GatewayProvider)
        assert isinstance(provider.gateway, OpenAIGateway)
        assert provider.gateway.default_model == "qwen"

    def test_create_gateway_provider_rejects_unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown AI gateway provider"):
            create_gateway_provider(
                provider="unknown_provider",
                api_key="sk-test",
                default_model="model",
            )


class TestPricingNewModels:
    def test_qwen_max_pricing(self) -> None:
        cost = estimate_cost("qwen-max", 1_000_000, 1_000_000)
        assert cost == pytest.approx(8.40, rel=0.01)

    def test_qwen_plus_pricing(self) -> None:
        cost = estimate_cost("qwen-plus", 1_000_000, 1_000_000)
        assert cost == pytest.approx(3.20, rel=0.01)

    def test_qwen_turbo_pricing(self) -> None:
        cost = estimate_cost("qwen-turbo", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.90, rel=0.01)

    def test_claude_sonnet_pricing(self) -> None:
        cost = estimate_cost("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
        assert cost == pytest.approx(18.00, rel=0.01)

    def test_claude_haiku_pricing(self) -> None:
        cost = estimate_cost("claude-3-5-haiku-20241022", 1_000_000, 1_000_000)
        assert cost == pytest.approx(4.80, rel=0.01)

    def test_embedding_small_pricing(self) -> None:
        cost = estimate_cost("text-embedding-3-small", 1_000_000, 0)
        assert cost == pytest.approx(0.02, rel=0.01)

    def test_embedding_large_pricing(self) -> None:
        cost = estimate_cost("text-embedding-3-large", 1_000_000, 0)
        assert cost == pytest.approx(0.13, rel=0.01)

    def test_unknown_model_falls_back_to_gpt4o(self) -> None:
        cost = estimate_cost("totally-unknown-model", 1_000_000, 1_000_000)
        assert cost == pytest.approx(12.50, rel=0.01)
