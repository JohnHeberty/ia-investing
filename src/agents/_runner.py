from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from agents import Agent, Runner
from database.config import Settings, get_settings

if TYPE_CHECKING:
    from agents.run import RunResult

from ._config import AgentConfig
from ._pricing import estimate_cost as _estimate_cost

logger = logging.getLogger(__name__)

PROMPTS_ROOT = Path(__file__).resolve().parent.parent.parent / "prompts"


@dataclass(slots=True)
class AgentResult:
    agent_name: str
    output_data: dict | str | None
    model_used: str
    tokens_prompt: int
    tokens_completion: int
    cost_usd: float
    duration_ms: float
    status: str
    error_message: str | None = None


def _resolve_output_type(type_path: str | None) -> type | None:
    if type_path is None:
        return None
    try:
        module_path, class_name = type_path.rsplit(".", 1)
    except ValueError:
        raise ValueError(f"Invalid type_path format '{type_path}': expected 'module.ClassName'") from None
    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise ImportError(f"Cannot import module '{module_path}' for type '{type_path}'") from exc
    try:
        return getattr(mod, class_name)
    except AttributeError as exc:
        raise AttributeError(f"Module '{module_path}' has no attribute '{class_name}'") from exc


def _load_system_prompt(path: str) -> str:
    full = PROMPTS_ROOT / path
    return full.read_text(encoding="utf-8")


def _extract_usage(result: RunResult) -> tuple[int, int]:
    usage = result.raw_response.usage if hasattr(result, "raw_response") and result.raw_response else None
    if usage is None:
        return 0, 0
    return getattr(usage, "prompt_tokens", 0) or 0, getattr(usage, "completion_tokens", 0) or 0


class AgentRunner:
    def __init__(self, config: AgentConfig, settings: Settings | None = None) -> None:
        self.config = config
        self.settings = settings or get_settings()
        self._system_prompt: str | None = None
        self._output_type = _resolve_output_type(config.structured_output_type)

    def _load_prompt_if_needed(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = _load_system_prompt(self.config.system_prompt_path)
        return self._system_prompt

    def _build_agent(self, tools: list | None = None) -> Agent:
        kwargs: dict[str, object] = {
            "name": self.config.name,
            "instructions": self._load_prompt_if_needed(),
            "model": self.config.model,
        }
        if self._output_type is not None:
            kwargs["output_type"] = self._output_type
        if tools:
            kwargs["tools"] = tools
        return Agent(**kwargs)

    def _format_input(self, input_data: dict, context: dict | None) -> str:
        parts: list[str] = []
        if context:
            parts.append(json.dumps({"context": context}, ensure_ascii=False, default=str))
        parts.append(json.dumps(input_data, ensure_ascii=False, default=str))
        return "\n\n".join(parts)

    async def run(self, input_data: dict, context: dict | None = None) -> AgentResult:
        agent = self._build_agent()
        return await self._execute(agent, input_data, context)

    async def run_with_tools(
        self, input_data: dict, tools: list, context: dict | None = None,
    ) -> AgentResult:
        agent = self._build_agent(tools=tools)
        return await self._execute(agent, input_data, context)

    async def _execute(
        self, agent: Agent, input_data: dict, context: dict | None,
    ) -> AgentResult:
        start = time.monotonic()
        try:
            prompt = self._format_input(input_data, context)
            result: RunResult = await asyncio.wait_for(
                Runner.run(agent, prompt),
                timeout=self.config.max_timeout_seconds,
            )
            elapsed_ms = (time.monotonic() - start) * 1000

            prompt_tokens, completion_tokens = _extract_usage(result)
            cost = _estimate_cost(self.config.model, prompt_tokens, completion_tokens)

            final_output = result.final_output
            if isinstance(final_output, str):
                with contextlib.suppress(json.JSONDecodeError):
                    final_output = json.loads(final_output)

            logger.info(
                "agent=%s model=%s tokens=%d/%d cost=%.6f duration=%.0fms",
                self.config.name,
                self.config.model,
                prompt_tokens,
                completion_tokens,
                cost,
                elapsed_ms,
            )

            return AgentResult(
                agent_name=self.config.name,
                output_data=final_output,
                model_used=self.config.model,
                tokens_prompt=prompt_tokens,
                tokens_completion=completion_tokens,
                cost_usd=cost,
                duration_ms=elapsed_ms,
                status="completed",
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.exception("Agent %s failed", self.config.name)
            return AgentResult(
                agent_name=self.config.name,
                output_data=None,
                model_used=self.config.model,
                tokens_prompt=0,
                tokens_completion=0,
                cost_usd=0.0,
                duration_ms=elapsed_ms,
                status="failed",
                error_message=str(exc),
            )
