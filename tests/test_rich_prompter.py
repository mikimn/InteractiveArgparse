from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt

from interactive_argparse import QuestionKind
from interactive_argparse.parse.question import Question
from interactive_argparse.parse.rich_prompter import RichPrompter


class TestRichPrompterMapping:
    @staticmethod
    def _map(question: Question):
        return RichPrompter._to_rich_prompt(question)

    def test_text_kind_maps_to_prompt_with_default(self):
        question = Question(name="n", message="m", kind=QuestionKind.TEXT, default="hi")
        prompt_cls, kwargs = self._map(question)
        assert prompt_cls is Prompt
        assert kwargs == {"prompt": "m", "default": "hi"}

    def test_text_kind_omits_default_when_none(self):
        question = Question(name="n", message="m", kind=QuestionKind.TEXT, default=None)
        prompt_cls, kwargs = self._map(question)
        assert prompt_cls is Prompt
        assert kwargs == {"prompt": "m"}

    def test_int_kind_maps_to_int_prompt(self):
        question = Question(name="n", message="m", kind=QuestionKind.INT, default=5)
        prompt_cls, kwargs = self._map(question)
        assert prompt_cls is IntPrompt
        assert kwargs == {"prompt": "m", "default": 5}

    def test_float_kind_maps_to_float_prompt(self):
        question = Question(name="n", message="m", kind=QuestionKind.FLOAT, default=1.5)
        prompt_cls, kwargs = self._map(question)
        assert prompt_cls is FloatPrompt
        assert kwargs == {"prompt": "m", "default": 1.5}

    def test_confirm_kind_maps_to_confirm_with_default(self):
        question = Question(name="n", message="m", kind=QuestionKind.CONFIRM, default=False)
        prompt_cls, kwargs = self._map(question)
        assert prompt_cls is Confirm
        assert kwargs == {"prompt": "m", "default": False}

    def test_confirm_kind_omits_default_when_none(self):
        question = Question(name="n", message="m", kind=QuestionKind.CONFIRM, default=None)
        prompt_cls, kwargs = self._map(question)
        assert kwargs == {"prompt": "m"}

    def test_single_choice_maps_to_prompt_with_stringified_choices_and_default(self):
        question = Question(
            name="n", message="m", kind=QuestionKind.SINGLE_CHOICE,
            default="red", choices=["red", "green", "blue"],
        )
        prompt_cls, kwargs = self._map(question)
        assert prompt_cls is Prompt
        assert kwargs == {"prompt": "m", "choices": ["red", "green", "blue"], "default": "red"}

    def test_single_choice_stringifies_non_string_choices(self):
        question = Question(
            name="n", message="m", kind=QuestionKind.SINGLE_CHOICE,
            default=2, choices=[1, 2, 3],
        )
        prompt_cls, kwargs = self._map(question)
        assert kwargs["choices"] == ["1", "2", "3"]
        assert kwargs["default"] == "2"

    def test_multi_choice_joins_default_list_into_a_string(self):
        question = Question(
            name="n", message="m", kind=QuestionKind.MULTI_CHOICE,
            default=["a", "b"], choices=["a", "b", "c"],
        )
        prompt_cls, kwargs = self._map(question)
        assert prompt_cls is Prompt
        assert kwargs == {"prompt": "m", "default": "a b"}

    def test_multi_choice_omits_default_when_empty(self):
        question = Question(name="n", message="m", kind=QuestionKind.MULTI_CHOICE, default=[])
        prompt_cls, kwargs = self._map(question)
        assert kwargs == {"prompt": "m"}


class TestRichPrompterCall:
    def test_call_returns_raw_answers_for_non_multi_choice(self, monkeypatch):
        monkeypatch.setattr(Prompt, "ask", classmethod(lambda cls, **kwargs: "hello"))
        monkeypatch.setattr(IntPrompt, "ask", classmethod(lambda cls, **kwargs: 42))
        questions = [
            Question(name="text_q", message="m1", kind=QuestionKind.TEXT, default="hi"),
            Question(name="int_q", message="m2", kind=QuestionKind.INT, default=1),
        ]
        answers = RichPrompter()(questions)
        assert answers == {"text_q": "hello", "int_q": 42}

    def test_call_splits_multi_choice_answer_on_commas_and_whitespace(self, monkeypatch):
        monkeypatch.setattr(Prompt, "ask", classmethod(lambda cls, **kwargs: "a, b  c"))
        question = Question(name="tags", message="m", kind=QuestionKind.MULTI_CHOICE, default=[])
        answers = RichPrompter()([question])
        assert answers == {"tags": ["a", "b", "c"]}

    def test_call_returns_empty_list_for_blank_multi_choice_answer(self, monkeypatch):
        monkeypatch.setattr(Prompt, "ask", classmethod(lambda cls, **kwargs: ""))
        question = Question(name="tags", message="m", kind=QuestionKind.MULTI_CHOICE, default=[])
        answers = RichPrompter()([question])
        assert answers == {"tags": []}
