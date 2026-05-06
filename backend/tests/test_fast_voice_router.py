from backend.fast_voice_router import FastVoiceRouter


def route(router: FastVoiceRouter, text: str):
    router.start_turn()
    return router.route_final(text)


def test_repeated_hello_uses_clear_check_without_looping():
    router = FastVoiceRouter()

    first = route(router, "hello")
    second = route(router, "hello hello")

    assert first.handled is True
    assert second.handled is True
    assert first.message == "Hello sir, voice clear-ah kekkudha?"
    assert second.message == "Hello sir, voice clear-ah kekkudha?"


def test_what_is_it_gets_property_intro_without_llm():
    router = FastVoiceRouter()

    result = route(router, "what is it?")

    assert result.handled is True
    assert result.needs_llm is False
    assert result.message == "MAXR Consultancy la irundhu property regarding call panniruken sir."


def test_confusion_and_wrong_number_recovery_replies():
    router = FastVoiceRouter()

    assert route(router, "not clear").message == "Sorry sir, konjam simple-ah solren."
    assert route(router, "wrong number").message == "Sorry sir, wrong number disturb panniten."


def test_busy_area_and_budget_allow_natural_livekit_reply():
    router = FastVoiceRouter()

    busy = route(router, "I am busy")
    property_type = route(router, "2bhk flat")
    area_budget = route(router, "OMR 80 lakh")

    assert busy.handled is False
    assert busy.needs_llm is True
    assert property_type.handled is False
    assert property_type.needs_llm is True
    assert area_budget.intent == "area_budget_answer"
    assert area_budget.handled is False
    assert area_budget.needs_llm is True
    assert {"area", "budget"}.issubset(router.state.answered_fields)


def test_duplicate_question_blocker_still_blocks_high_confidence_repeat():
    router = FastVoiceRouter()
    router.state.last_agent_text = "Chennai la endha area property venum sir?"
    router.state.last_question_key = "area"

    result = route(router, "repeat")

    assert result.handled is True
    assert result.message == "Chennai la endha area property venum sir?"
    assert result.confidence >= 0.9
