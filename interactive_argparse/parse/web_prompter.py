from typing import Any, Dict, List

from .interactive_parser import Question, QuestionKind


class WebPrompter:
    """Renders `Question`s as an auto-generated web form, using PyWebIO.

    PyWebIO's `input_group` blocks until the form is submitted - the same
    execution model as the builtin `input()` - and handles starting a
    local server and opening the browser itself, so no server/threading
    plumbing is needed here. PyWebIO is a `web` extra (`pip install
    InteractiveArgparse[web]`) and is only imported the first time this
    prompter is actually invoked.
    """

    def __call__(self, questions: List[Question]) -> Dict[str, Any]:
        pywebio_input = self._load_pywebio_input()
        free_form_multi_choice = {
            question.name for question in questions
            if question.kind == QuestionKind.MULTI_CHOICE and not question.choices
        }
        inputs = [self._to_pywebio_input(pywebio_input, question) for question in questions]
        answers = pywebio_input.input_group("", inputs=inputs, cancelable=True) or {}
        for name in free_form_multi_choice:
            if isinstance(answers.get(name), str):
                answers[name] = answers[name].split()
        return answers

    @staticmethod
    def _load_pywebio_input():
        import pywebio.input
        return pywebio.input

    @classmethod
    def _to_pywebio_input(cls, pywebio_input, question: Question):
        if question.kind == QuestionKind.CONFIRM:
            return pywebio_input.checkbox(
                question.message, name=question.name,
                options=[{"label": "Yes", "value": True}],
                value=[True] if question.default else [],
            )
        if question.kind == QuestionKind.SINGLE_CHOICE:
            return pywebio_input.select(
                question.message, name=question.name,
                options=question.choices or [],
                value=question.default,
            )
        if question.kind == QuestionKind.MULTI_CHOICE and question.choices:
            return pywebio_input.checkbox(
                question.message, name=question.name,
                options=question.choices,
                value=question.default or [],
            )
        if question.kind == QuestionKind.MULTI_CHOICE:
            # No fixed choices to render as checkboxes (e.g. a free-form
            # nargs="+" argument) - fall back to a space-separated text
            # field; __call__ splits it back into a list before returning.
            default_text = " ".join(str(v) for v in question.default) if question.default else None
            return pywebio_input.input(
                question.message, name=question.name, value=default_text,
                help_text="Separate multiple values with spaces.",
            )
        type_map = {
            QuestionKind.INT: pywebio_input.NUMBER,
            QuestionKind.FLOAT: pywebio_input.FLOAT,
            QuestionKind.TEXT: pywebio_input.TEXT,
        }
        return pywebio_input.input(
            question.message, name=question.name,
            type=type_map[question.kind],
            value=question.default,
        )
