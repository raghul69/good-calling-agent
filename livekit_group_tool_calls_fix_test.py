from backend.livekit_group_tool_calls_fix import apply_patch
from livekit.agents import llm
from livekit.agents.llm._provider_format import utils


def test_duplicate_call_ids_are_matched_to_groups_in_order() -> None:
    apply_patch()

    chat_ctx = llm.ChatContext(
        [
            llm.ChatMessage(id="group-1/message", role="assistant", content=["checking first"]),
            llm.FunctionCall(
                id="group-1/tool",
                call_id="reused_call_id",
                name="save_booking_intent",
                arguments='{"slot":"10:00"}',
            ),
            llm.FunctionCallOutput(
                id="group-1/output",
                call_id="reused_call_id",
                name="save_booking_intent",
                output="first saved",
                is_error=False,
            ),
            llm.ChatMessage(id="group-2/message", role="assistant", content=["checking second"]),
            llm.FunctionCall(
                id="group-2/tool",
                call_id="reused_call_id",
                name="save_booking_intent",
                arguments='{"slot":"11:00"}',
            ),
            llm.FunctionCallOutput(
                id="group-2/output",
                call_id="reused_call_id",
                name="save_booking_intent",
                output="second saved",
                is_error=False,
            ),
        ]
    )

    grouped = [
        group
        for group in utils.group_tool_calls(chat_ctx)
        if group.tool_calls or group.tool_outputs
    ]

    assert len(grouped) == 2
    assert [group.tool_calls[0].id for group in grouped] == ["group-1/tool", "group-2/tool"]
    assert [group.tool_outputs[0].output for group in grouped] == ["first saved", "second saved"]

