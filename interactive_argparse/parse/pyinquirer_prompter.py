from typing import Any, Dict, List

from .prompter import Prompter
from .question import Question, QuestionKind


class PyInquirerPrompter(Prompter):
    """Default prompter: renders `Question`s as a terminal prompt via
    PyInquirer. PyInquirer is only imported the first time this prompter is
    actually invoked, so constructing (or not using) it costs nothing for
    callers who plug in a different prompter.
    """
    name = "pyinquirer"

    _TYPE_MAP = {
        QuestionKind.TEXT: "input",
        QuestionKind.INT: "input",
        QuestionKind.FLOAT: "input",
        QuestionKind.CONFIRM: "confirm",
        QuestionKind.SINGLE_CHOICE: "list",
        QuestionKind.MULTI_CHOICE: "checkbox",
    }

    def __call__(self, questions: List[Question]) -> Dict[str, Any]:
        prompt = self._load_prompt()
        return prompt([self._to_pyinquirer_dict(q) for q in questions])

    @staticmethod
    def _load_prompt():
        import collections
        import collections.abc
        # PyInquirer's pinned `prompt_toolkit<2.0` imports ABCs from
        # `collections`, which were removed in Python 3.10. Restore them
        # before importing PyInquirer.
        if not hasattr(collections, "Mapping"):
            collections.Mapping = collections.abc.Mapping
        from PyInquirer import prompt
        return prompt

    @classmethod
    def _to_pyinquirer_dict(cls, question: Question) -> dict:
        result = {
            "type": cls._TYPE_MAP[question.kind],
            "name": question.name,
            "message": question.message,
        }
        if question.default is not None:
            # PyInquirer's "input" prompt renders the default as text, so it
            # must be a string; "confirm"/"list"/"checkbox" expect the raw
            # value.
            is_text_like = question.kind in (QuestionKind.TEXT, QuestionKind.INT, QuestionKind.FLOAT)
            result["default"] = str(question.default) if is_text_like else question.default
        if question.choices:
            result["choices"] = question.choices
        return result
