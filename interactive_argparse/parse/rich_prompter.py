import re
from typing import Any, Dict, List, Tuple, Type

from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt, PromptBase

from .prompter import Prompter
from .question import Question, QuestionKind


class RichPrompter(Prompter):
    """Terminal prompter built on `rich.prompt` - a lighter-weight, actively
    maintained alternative to `PyInquirerPrompter`.

    Registered as "rich" - usable via `@interactive("rich")`.
    """
    name = "rich"

    _MULTI_CHOICE_SPLIT_RE = re.compile(r"[,\s]+")

    _PROMPT_CLASSES = {
        QuestionKind.TEXT: Prompt,
        QuestionKind.INT: IntPrompt,
        QuestionKind.FLOAT: FloatPrompt,
        QuestionKind.CONFIRM: Confirm,
        QuestionKind.SINGLE_CHOICE: Prompt,
    }

    def __call__(self, questions: List[Question]) -> Dict[str, Any]:
        answers: Dict[str, Any] = {}
        for question in questions:
            if question.kind == QuestionKind.MULTI_CHOICE:
                answers[question.name] = self._ask_multi_choice(question)
            else:
                prompt_cls, kwargs = self._to_rich_prompt(question)
                answers[question.name] = prompt_cls.ask(**kwargs)
        return answers

    def _ask_multi_choice(self, question: Question) -> List[str]:
        _, kwargs = self._to_rich_prompt(question)
        valid_choices = set(question.choices) if question.choices else None
        while True:
            raw = Prompt.ask(**kwargs)
            value = [v for v in self._MULTI_CHOICE_SPLIT_RE.split(raw.strip()) if v]
            if valid_choices is None:
                return value
            invalid = [v for v in value if v not in valid_choices]
            if not invalid:
                return value
            kwargs = {
                **kwargs,
                "prompt": (
                    f"Invalid value(s) {', '.join(invalid)!r} - "
                    f"choose from {sorted(valid_choices)}. {question.message}"
                ),
            }

    @classmethod
    def _to_rich_prompt(cls, question: Question) -> Tuple[Type[PromptBase], Dict[str, Any]]:
        kwargs: Dict[str, Any] = {"prompt": question.message}

        if question.kind == QuestionKind.MULTI_CHOICE:
            if question.default:
                kwargs["default"] = " ".join(str(v) for v in question.default)
            return Prompt, kwargs

        if question.kind == QuestionKind.SINGLE_CHOICE and question.choices:
            kwargs["choices"] = [str(c) for c in question.choices]

        if question.default is not None:
            is_single_choice = question.kind == QuestionKind.SINGLE_CHOICE
            kwargs["default"] = str(question.default) if is_single_choice else question.default

        return cls._PROMPT_CLASSES[question.kind], kwargs
