from decimal import Decimal

import pytest

from app.core.errors import BusinessError
from app.modules.exam.types import MultipleChoiceMode
from app.modules.question.types import QuestionType


def test_automatic_score_uses_exact_sets_partial_rounding_and_false_as_an_answer():
    from app.modules.grading.service import automatic_score

    options = ["a", "b", "c", "d"]
    cases = [
        (QuestionType.MULTIPLE_CHOICE, ["a", "b", "c"], ["a"], "2.0", MultipleChoiceMode.PARTIAL),
        (
            QuestionType.MULTIPLE_CHOICE,
            ["a", "b", "c"],
            ["a", "d"],
            "0.0",
            MultipleChoiceMode.PARTIAL,
        ),
        (QuestionType.MULTIPLE_CHOICE, ["a", "b", "c"], ["a"], "0.0", MultipleChoiceMode.EXACT),
        (
            QuestionType.MULTIPLE_CHOICE,
            ["a", "b", "c"],
            ["c", "a", "b"],
            "6.0",
            MultipleChoiceMode.EXACT,
        ),
        (QuestionType.TRUE_FALSE, False, False, "6.0", MultipleChoiceMode.EXACT),
        (QuestionType.SHORT_ANSWER, "参考", "  ", "0.0", MultipleChoiceMode.EXACT),
        (QuestionType.SHORT_ANSWER, "参考", "答案", None, MultipleChoiceMode.EXACT),
    ]
    for kind, standard, answer, expected, mode in cases:
        actual = automatic_score(kind, options, standard, answer, Decimal("6.0"), mode)
        assert actual == (Decimal(expected) if expected is not None else None)
    assert automatic_score(
        QuestionType.MULTIPLE_CHOICE,
        options,
        ["a", "b", "c"],
        ["a"],
        Decimal("2.5"),
        MultipleChoiceMode.PARTIAL,
    ) == Decimal("0.8")
    # 1.25的中点必须向上舍入，区别于Decimal默认的银行家舍入。
    assert automatic_score(
        QuestionType.MULTIPLE_CHOICE,
        options,
        ["a", "b"],
        ["a"],
        Decimal("2.5"),
        MultipleChoiceMode.PARTIAL,
    ) == Decimal("1.3")
    for invalid in (["a", "a"], ["unknown"]):
        with pytest.raises(BusinessError, match="选项"):
            automatic_score(
                QuestionType.MULTIPLE_CHOICE,
                options,
                ["a", "b"],
                invalid,
                Decimal("6.0"),
                MultipleChoiceMode.PARTIAL,
            )
