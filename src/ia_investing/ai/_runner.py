from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents import Agent, Runner
from ia_investing.settings import Settings, get_settings

from ._config import AgentConfig
from ._pricing import estimate_cost as _estimate_cost

logger = logging.getLogger(__name__)
PROMPTS_ROOT = Path(__file__).resolve().parents[3] / "prompts"


@dataclass(slots=True)
class AgentResult:
    agent_name: str
    output_data: dict[str, Any] | str | None
    model_used: str
    tokens_prompt: int
    tokens_completion: int
    cost_usd: float
    duration_ms: float
    status: str
    error_message: str | None = None


def _resolve_output_type(type_path: str | None) -> type[Any] | None:
    if type_path is None:
        return None
    try:
        module_path, class_name = type_path.rsplit(".", 1)
    except ValueError:
        raise ValueError(f"Invalid type_path format '{type_path}': expected 'module.ClassName'") from None
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise ImportError(f"Cannot import module '{module_path}' for type '{type_path}'") from exc
    try:
        output_type: type[Any] = getattr(module, class_name)
    except AttributeError as exc:
        raise AttributeError(f"Module '{module_path}' has no attribute '{class_name}'") from exc
    return output_type


def _load_system_prompt(path: str) -> str:
    relative_path = Path(path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"Prompt path must be relative to the prompt root: {path}")
    prompt_root = PROMPTS_ROOT.resolve()
    full_path = (prompt_root / relative_path).resolve()
    if not full_path.is_relative_to(prompt_root):
        raise ValueError(f"Prompt path escapes the prompt root: {path}")
    return full_path.read_text(encoding="utf-8")


def _extract_usage(result: Any) -> tuple[int, int]:
    context_wrapper = getattr(result, "context_wrapper", None)
    usage = getattr(context_wrapper, "usage", None)
    if usage is None:
        return 0, 0
    return getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0


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

    def _build_agent(self, tools: list[Any] | None = None) -> Agent[Any]:
        return Agent(
            name=self.config.name,
            instructions=self._load_prompt_if_needed(),
            model=self.config.model,
            output_type=self._output_type,
            tools=tools or [],
        )

    @staticmethod
    def _format_input(input_data: dict[str, Any], context: dict[str, Any] | None) -> str:
        parts: list[str] = []
        if context:
            parts.append(json.dumps({"context": context}, ensure_ascii=False, default=str))
        parts.append(json.dumps(input_data, ensure_ascii=False, default=str))
        return "\n\n".join(parts)

    async def run(self, input_data: dict[str, Any], context: dict[str, Any] | None = None) -> AgentResult:
        return await self._execute(self._build_agent(), input_data, context)

    async def run_with_tools(
        self,
        input_data: dict[str, Any],
        tools: list[Any],
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        return await self._execute(self._build_agent(tools), input_data, context)

    async def _execute(
        self,
        agent: Agent[Any],
        input_data: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> AgentResult:
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                Runner.run(agent, self._format_input(input_data, context)),
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
                self.config.name,
                final_output,
                self.config.model,
                prompt_tokens,
                completion_tokens,
                cost,
                elapsed_ms,
                "completed",
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.exception("Agent %s failed", self.config.name)
            return AgentResult(
                self.config.name,
                None,
                self.config.model,
                0,
                0,
                0.0,
                elapsed_ms,
                "failed",
                str(exc),
            )
