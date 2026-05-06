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


def test_confusion_busy_and_wrong_number_recovery_replies():
    router = FastVoiceRouter()

    assert route(router, "not clear").message == "Sorry sir, konjam simple-ah solren."
    assert route(router, "I am busy").message == "No problem sir, convenient time la call pannaren."
    assert route(router, "wrong number").message == "Sorry sir, wrong number disturb panniten."


def test_area_and_budget_together_skips_budget_question():
    router = FastVoiceRouter()

    property_type = route(router, "2bhk flat")
    area_budget = route(router, "OMR 80 lakh")

    assert property_type.message == "Chennai la endha area property venum sir?"
    assert area_budget.intent == "area_budget_answer"
    assert area_budget.message == "Eppo buying plan panreenga sir?"
    assert {"area", "budget"}.issubset(router.state.answered_fields)


def test_duplicate_question_blocker_switches_to_recovery():
    router = FastVoiceRouter()
    router.state.last_question_key = "area"

    result = route(router, "flat")

    assert result.message == "Sir, answer clear-ah varala. Konjam simple-ah sollunga."
    assert router.state.repeat_counter == 1
