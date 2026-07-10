import sys

from interactive_argparse import QuestionKind
from interactive_argparse.parse.question import Question
from interactive_argparse.parse.web_prompter import WebPrompter


class _RecordingPyWebIOInput:
    """A minimal stand-in for `pywebio.input`, recording calls instead of
    actually rendering anything. Keeps WebPrompter's tests independent of
    the real PyWebIO package/runtime entirely - we only need to verify
    *our* mapping logic (which function gets called with which kwargs),
    not PyWebIO's own internals.
    """
    TEXT = "text"
    NUMBER = "number"
    FLOAT = "float"

    def __init__(self, input_group_result=None):
        self.input_group_result = input_group_result
        self.calls = []

    def input(self, label, **kwargs):
        self.calls.append(("input", label, kwargs))
        return ("input", label, kwargs)

    def checkbox(self, label, **kwargs):
        self.calls.append(("checkbox", label, kwargs))
        return ("checkbox", label, kwargs)

    def select(self, label, **kwargs):
        self.calls.append(("select", label, kwargs))
        return ("select", label, kwargs)

    def input_group(self, label="", inputs=None, cancelable=False):
        self.calls.append(("input_group", label, {"inputs": inputs, "cancelable": cancelable}))
        return self.input_group_result


class TestWebPrompter:
    @staticmethod
    def _call(question: Question):
        fake = _RecordingPyWebIOInput()
        WebPrompter._to_pywebio_input(fake, question)
        return fake.calls[-1]

    def test_text_kind_calls_input_with_text_type(self):
        question = Question(name="n", message="m", kind=QuestionKind.TEXT, default="hi")
        func, label, kwargs = self._call(question)
        assert func == "input"
        assert kwargs["name"] == "n"
        assert kwargs["value"] == "hi"
        assert kwargs["type"] == "text"

    def test_int_kind_calls_input_with_number_type(self):
        question = Question(name="n", message="m", kind=QuestionKind.INT, default=5)
        func, label, kwargs = self._call(question)
        assert func == "input"
        assert kwargs["type"] == "number"
        assert kwargs["value"] == 5

    def test_float_kind_calls_input_with_float_type(self):
        question = Question(name="n", message="m", kind=QuestionKind.FLOAT, default=1.5)
        func, label, kwargs = self._call(question)
        assert func == "input"
        assert kwargs["type"] == "float"
        assert kwargs["value"] == 1.5

    def test_confirm_kind_calls_checkbox_with_single_preselected_option(self):
        question = Question(name="n", message="m", kind=QuestionKind.CONFIRM, default=True)
        func, label, kwargs = self._call(question)
        assert func == "checkbox"
        assert kwargs["value"] == [True]

    def test_confirm_default_false_has_nothing_preselected(self):
        question = Question(name="n", message="m", kind=QuestionKind.CONFIRM, default=False)
        func, label, kwargs = self._call(question)
        assert func == "checkbox"
        assert kwargs["value"] == []

    def test_single_choice_kind_calls_select(self):
        question = Question(
            name="n", message="m", kind=QuestionKind.SINGLE_CHOICE,
            default="red", choices=["red", "green"],
        )
        func, label, kwargs = self._call(question)
        assert func == "select"
        assert kwargs["options"] == ["red", "green"]
        assert kwargs["value"] == "red"

    def test_multi_choice_with_choices_calls_checkbox(self):
        question = Question(
            name="n", message="m", kind=QuestionKind.MULTI_CHOICE,
            default=["a"], choices=["a", "b"],
        )
        func, label, kwargs = self._call(question)
        assert func == "checkbox"
        assert kwargs["options"] == ["a", "b"]
        assert kwargs["value"] == ["a"]

    def test_multi_choice_without_choices_falls_back_to_text_input(self):
        # No fixed choice set to render checkboxes for - a free-form
        # nargs="+" argument. __call__ splits the submitted text back into
        # a list; see test_call_splits_free_form_multi_choice_answer below.
        question = Question(
            name="n", message="m", kind=QuestionKind.MULTI_CHOICE,
            default=["a", "b"], choices=None,
        )
        func, label, kwargs = self._call(question)
        assert func == "input"
        assert kwargs["value"] == "a b"

    def test_call_splits_free_form_multi_choice_answer_into_a_list(self, monkeypatch):
        fake = _RecordingPyWebIOInput(input_group_result={"tags": "a b c"})
        monkeypatch.setattr(WebPrompter, "_load_pywebio_input", staticmethod(lambda: fake))
        question = Question(name="tags", message="m", kind=QuestionKind.MULTI_CHOICE)
        result = WebPrompter()([question])
        assert result == {"tags": ["a", "b", "c"]}

    def test_call_returns_empty_dict_when_cancelled(self, monkeypatch):
        fake = _RecordingPyWebIOInput(input_group_result=None)
        monkeypatch.setattr(WebPrompter, "_load_pywebio_input", staticmethod(lambda: fake))
        question = Question(name="n", message="m", kind=QuestionKind.TEXT)
        result = WebPrompter()([question])
        assert result == {}

    def test_pywebio_is_not_imported_by_the_test_suite(self):
        # WebPrompter's tests never need the real PyWebIO package/runtime -
        # everything above runs against _RecordingPyWebIOInput instead.
        assert "pywebio" not in sys.modules
