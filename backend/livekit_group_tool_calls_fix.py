"""Workaround for duplicate tool call_id batching in livekit-agents.

When the LLM/provider reuses the same call_id for sequential tool calls,
``group_tool_calls`` only kept the last group for that id, so outputs were
attached to the wrong group and LiveKit logged warnings like
"function call missing the corresponding function output".

See: https://github.com/livekit/agents/issues/3329

Import and call ``apply_patch()`` before ``from livekit.agents import ...``.

After patching ``utils.group_tool_calls``, all submodules under
``livekit.agents.llm._provider_format`` that expose ``group_tool_calls`` are
rebound (including any added in newer ``livekit-agents`` releases).
"""

from __future__ import annotations

import pkgutil
from collections import OrderedDict

_PATCHED = False


def apply_patch() -> None:
    global _PATCHED
    if _PATCHED:
        return

    from livekit.agents import llm
    from livekit.agents.llm._provider_format import utils as utils_module
    from livekit.agents.log import logger

    _ChatItemGroup = utils_module._ChatItemGroup

    def fixed_group_tool_calls(chat_ctx: llm.ChatContext) -> list:
        item_groups: dict[str, _ChatItemGroup] = OrderedDict()
        tool_outputs: list[llm.FunctionCallOutput] = []
        for item in chat_ctx.items:
            if (item.type == "message" and item.role == "assistant") or item.type == "function_call":
                if item.type == "function_call" and item.group_id:
                    group_id = item.group_id
                else:
                    group_id = item.id.split("/")[0]
                if group_id not in item_groups:
                    item_groups[group_id] = _ChatItemGroup().add(item)
                else:
                    item_groups[group_id].add(item)
            elif item.type == "function_call_output":
                tool_outputs.append(item)
            else:
                item_groups[item.id] = _ChatItemGroup().add(item)

        call_id_to_groups: dict[str, list[_ChatItemGroup]] = {}
        for group in item_groups.values():
            for tool_call in group.tool_calls:
                call_id_to_groups.setdefault(tool_call.call_id, []).append(group)

        call_id_next_index: dict[str, int] = {}
        for tool_output in tool_outputs:
            call_id = tool_output.call_id
            if call_id not in call_id_to_groups:
                logger.warning(
                    "function output missing the corresponding function call, ignoring",
                    extra={"call_id": tool_output.call_id, "tool_name": tool_output.name},
                )
                continue

            available = call_id_to_groups[call_id]
            idx = call_id_next_index.get(call_id, 0)
            if idx < len(available):
                available[idx].add(tool_output)
                call_id_next_index[call_id] = idx + 1
            else:
                logger.warning(
                    "function output missing the corresponding function call, ignoring",
                    extra={"call_id": tool_output.call_id, "tool_name": tool_output.name},
                )

        for group in item_groups.values():
            group.remove_invalid_tool_calls()

        return list(item_groups.values())

    utils_module.group_tool_calls = fixed_group_tool_calls

    # Rebind any provider module that did `from .utils import group_tool_calls` (stale ref).
    # Discover dynamically so new providers (e.g. mistralai) are covered after upgrades.
    import livekit.agents.llm._provider_format as _provider_format_pkg

    for _finder, modname, _ispkg in pkgutil.iter_modules(_provider_format_pkg.__path__):
        if modname == "utils":
            continue
        try:
            mod = __import__(
                f"livekit.agents.llm._provider_format.{modname}",
                fromlist=["_livekit_patch_probe"],
            )
            if getattr(mod, "group_tool_calls", None) is not None:
                mod.group_tool_calls = fixed_group_tool_calls
        except Exception:
            pass

    _PATCHED = True
