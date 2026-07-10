from typing import Any, Dict, List, Optional

from .prompter import Prompter
from .question import Question, QuestionKind


class WebPrompter(Prompter):
    """Renders `Question`s as an auto-generated web form, using PyWebIO.

    PyWebIO's `input_group` blocks until the form is submitted - the same
    execution model as the builtin `input()` - and handles starting a
    local server and opening the browser itself, so no server/threading
    plumbing is needed here. PyWebIO is a `web` extra (`pip install
    InteractiveArgparse[web]`) and is only imported the first time this
    prompter is actually invoked.

    Registered as "web" - usable via `@interactive("web")`.
    """
    name = "web"

    _TITLE = "Configure Arguments"

    # A standalone form reads better as a centered card in the normal page
    # flow than PyWebIO's default fixed-to-the-bottom input drawer (which is
    # built for chat-like, growing-output sessions), so the CSS below
    # replaces that layout rather than styling on top of it.
    _CSS = """
    body {
        background: linear-gradient(135deg, #f4f6fb 0%, #eceff5 100%);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    #input-container { background: transparent; }
    #input-container .card {
        max-width: 560px;
        border: none;
        border-radius: 18px;
        box-shadow: 0 20px 50px rgba(15, 23, 42, 0.10), 0 4px 14px rgba(15, 23, 42, 0.06);
        overflow: hidden;
    }
    #input-container h5.card-header {
        background: #ffffff;
        border-bottom: 1px solid #eef0f4;
        padding: 1.5rem 1.75rem 1rem;
        font-size: 1.35rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        color: #10152a;
    }
    #input-container .card-body { padding: 1.5rem 1.75rem 0.5rem; }
    .form-group {
        margin-bottom: 1.4rem;
    }
    .form-group label {
        font-weight: 600;
        font-size: 0.92rem;
        color: #3c4257;
        margin-bottom: 0.35rem;
    }
    .form-control, .form-select, select.form-control {
        border-radius: 10px;
        border: 1.5px solid #e1e4ea;
        padding: 0.55rem 0.85rem;
        transition: border-color .15s ease, box-shadow .15s ease;
    }
    .form-control:focus, .form-select:focus {
        border-color: #5b6cff;
        box-shadow: 0 0 0 3px rgba(91, 108, 255, 0.15);
    }
    .form-text {
        color: #8a90a2;
        font-size: 0.82rem;
        margin-top: 0.3rem;
    }
    .btn {
        border-radius: 10px;
        padding: 0.55rem 1.5rem;
        font-weight: 600;
    }
    .btn-primary {
        background: #5b6cff;
        border-color: #5b6cff;
    }
    .btn-primary:hover, .btn-primary:focus {
        background: #4855e0;
        border-color: #4855e0;
    }
    /* Submit is the one prominent action; Reset/Cancel read as lower-emphasis
       secondary actions instead of Bootstrap's default alarming orange/red. */
    .btn-warning, .btn-danger {
        background: #f4f5f8;
        border-color: #e5e8ef;
        color: #4b5468;
    }
    .btn-warning:hover, .btn-warning:focus,
    .btn-danger:hover, .btn-danger:focus {
        background: #e9ebf1;
        border-color: #d7dae2;
        color: #262c3f;
    }
    .custom-checkbox label, .custom-radio label { font-weight: 500; }
    """

    def __call__(self, questions: List[Question]) -> Dict[str, Any]:
        pywebio_config, pywebio_session, pywebio_input = self._load_pywebio()
        pywebio_config(title=self._TITLE, theme="yeti", css_style=self._CSS)
        pywebio_session.set_env(input_panel_fixed=False, output_max_width="100%")

        free_form_multi_choice = {
            question.name for question in questions
            if question.kind == QuestionKind.MULTI_CHOICE and not question.choices
        }
        inputs = [self._to_pywebio_input(pywebio_input, question) for question in questions]
        answers = pywebio_input.input_group(self._TITLE, inputs=inputs, cancelable=True) or {}
        for name in free_form_multi_choice:
            if isinstance(answers.get(name), str):
                answers[name] = answers[name].split()
        return answers

    @staticmethod
    def _load_pywebio():
        import pywebio
        import pywebio.input
        import pywebio.session
        return pywebio.config, pywebio.session, pywebio.input

    @staticmethod
    def _label(question: Question) -> str:
        # Web forms read better with a humanized field label ("Should
        # greet") and a separate caption than argparse's terse dest names
        # crammed into one line the way a terminal prompt needs them.
        return question.name.replace("_", " ").replace("-", " ").strip().capitalize()

    @staticmethod
    def _help_text(question: Question, extra: Optional[str] = None) -> Optional[str]:
        parts = [p for p in (question.help, extra) if p]
        if len(parts) == 2 and not parts[0].rstrip().endswith((".", "!", "?")):
            parts[0] = parts[0].rstrip() + "."
        return " ".join(parts) or None

    @classmethod
    def _to_pywebio_input(cls, pywebio_input, question: Question):
        label = cls._label(question)
        if question.kind == QuestionKind.CONFIRM:
            return pywebio_input.checkbox(
                label, name=question.name,
                options=[{"label": "Yes", "value": True}],
                value=[True] if question.default else [],
                help_text=cls._help_text(question),
            )
        if question.kind == QuestionKind.SINGLE_CHOICE:
            return pywebio_input.select(
                label, name=question.name,
                options=question.choices or [],
                value=question.default,
                help_text=cls._help_text(question),
            )
        if question.kind == QuestionKind.MULTI_CHOICE and question.choices:
            return pywebio_input.checkbox(
                label, name=question.name,
                options=question.choices,
                value=question.default or [],
                help_text=cls._help_text(question),
            )
        if question.kind == QuestionKind.MULTI_CHOICE:
            # No fixed choices to render as checkboxes (e.g. a free-form
            # nargs="+" argument) - fall back to a space-separated text
            # field; __call__ splits it back into a list before returning.
            default_text = " ".join(str(v) for v in question.default) if question.default else None
            return pywebio_input.input(
                label, name=question.name, value=default_text,
                help_text=cls._help_text(question, "Separate multiple values with spaces."),
            )
        type_map = {
            QuestionKind.INT: pywebio_input.NUMBER,
            QuestionKind.FLOAT: pywebio_input.FLOAT,
            QuestionKind.TEXT: pywebio_input.TEXT,
        }
        return pywebio_input.input(
            label, name=question.name,
            type=type_map[question.kind],
            value=question.default,
            help_text=cls._help_text(question),
        )
