"""Answer numbering shared by citations, feedback and the message list."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.history import count_answers, question_and_answer, session_turns

HISTORY = [
    HumanMessage(content="군휴학 절차?"),
    AIMessage(content="", tool_calls=[{"name": "retrieval", "args": {"query": "군휴학"}, "id": "c1"}]),
    AIMessage(content="로그인 → 학적변동 → 휴학신청 [1]"),
    HumanMessage(content="파일 형식은?"),
    AIMessage(content="PDF입니다 [2]"),
]


def test_empty_ai_messages_are_not_answers() -> None:
    turns = session_turns(HISTORY)
    assert [(t.role, t.turn_index) for t in turns] == [
        ("user", None), ("assistant", 0), ("user", None), ("assistant", 1),
    ]
    assert count_answers(HISTORY) == 2


def test_question_and_answer_pairs_each_answer_with_its_question() -> None:
    assert question_and_answer(HISTORY, 1) == ("파일 형식은?", "PDF입니다 [2]")
    assert question_and_answer(HISTORY, 0) == ("군휴학 절차?", "로그인 → 학적변동 → 휴학신청 [1]")
    assert question_and_answer(HISTORY, 2) is None


def test_session_title_is_the_first_question_on_one_line() -> None:
    from app.agent.history import title_from_message

    assert title_from_message("  군휴학   신청\n절차 알려줘 ") == "군휴학 신청 절차 알려줘"
    long = "재제조 스로틀바디 기밀성 시험 조건을 제조 에이전트에게 물어봐서 자세히 알려줘"
    title = title_from_message(long)
    assert len(title) == 40 and title.endswith("…") and long.startswith(title[:-1])
