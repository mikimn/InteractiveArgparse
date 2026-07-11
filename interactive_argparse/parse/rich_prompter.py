import re
from typing import Any, Dict, List, Tuple, Type

from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt, PromptBase

from .prompter import Prompter
from .question import Question, QuestionKind


class RichPrompter(Prompter):
    """Terminal prompter built on `rich.prompt` (`Prompt`, `IntPrompt`,
    `FloatPrompt`, `Confirm`) - a lighter-weight, actively maintained
    alternative to `PyInquirerPrompter` that needs no extra dependency,
    since `rich` is already declared in requirements.txt.

    `rich.prompt` has no native multi-select control, so `MULTI_CHOICE`
    questions (including ones with fixed `choices`) fall back to a single
    free-text prompt, split on commas/whitespace into a list of strings.

    Registered as "rich" - usable via `@interactive("rich")`.
    """
    name = "rich"

    _MULTI_CHOICE_SPLIT_RE = re.compile(r"[,\s]+")

    def __call__(self, questions: List[Question]) -> Dict[str, Any]:
        answers: Dict[str, Any] = {}
        for question in questions:
            prompt_cls, kwargs = self._to_rich_prompt(question)
            value = prompt_cls.ask(**kwargs)
            if question.kind == QuestionKind.MULTI_CHOICE and isinstance(value, str):
                value = [v for v in self._MULTI_CHOICE_SPLIT_RE.split(value.strip()) if v]
            answers[question.name] = value
        return answers

    @classmethod
    def _to_rich_prompt(cls, question: Question) -> Tuple[Type[PromptBase], Dict[str, Any]]:
        kwargs: Dict[str, Any] = {"prompt": question.message}

        if question.kind == QuestionKind.CONFIRM:
            if question.default is not None:
                kwargs["default"] = question.default
            return Confirm, kwargs

        if question.kind == QuestionKind.INT:
            if question.default is not None:
                kwargs["default"] = question.default
            return IntPrompt, kwargs

        if question.kind == QuestionKind.FLOAT:
            if question.default is not None:
                kwargs["default"] = question.default
            return FloatPrompt, kwargs

        if question.kind == QuestionKind.SINGLE_CHOICE:
            if question.choices:
                kwargs["choices"] = [str(c) for c in question.choices]
            if question.default is not None:
                kwargs["default"] = str(question.default)
            return Prompt, kwargs

        if question.kind == QuestionKind.MULTI_CHOICE:
            if question.default:
                kwargs["default"] = " ".join(str(v) for v in question.default)
            return Prompt, kwargs

        # TEXT
        if question.default is not None:
            kwargs["default"] = question.default
        return Prompt, kwargs
