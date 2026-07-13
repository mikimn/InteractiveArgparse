import pytest
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

    def test_multi_choice_without_fixed_choices_is_not_validated(self, monkeypatch):
        # No question.choices set - free-form nargs="+" argument - so
        # anything the user types is accepted as-is, same as before.
        monkeypatch.setattr(Prompt, "ask", classmethod(lambda cls, **kwargs: "anything goes"))
        question = Question(name="tags", message="m", kind=QuestionKind.MULTI_CHOICE, default=[])
        answers = RichPrompter()([question])
        assert answers == {"tags": ["anything", "goes"]}

    def test_multi_choice_with_fixed_choices_accepts_valid_values_in_one_call(self, monkeypatch):
        calls = []

        def fake_ask(cls, **kwargs):
            calls.append(kwargs)
            return "a b"

        monkeypatch.setattr(Prompt, "ask", classmethod(fake_ask))
        question = Question(
            name="tags", message="m", kind=QuestionKind.MULTI_CHOICE,
            default=[], choices=["a", "b", "c"],
        )
        answers = RichPrompter()([question])
        assert answers == {"tags": ["a", "b"]}
        assert len(calls) == 1

    def test_multi_choice_with_fixed_choices_reprompts_on_invalid_value(self, monkeypatch):
        responses = iter(["a bogus", "a b"])

        def fake_ask(cls, **kwargs):
            return next(responses)

        monkeypatch.setattr(Prompt, "ask", classmethod(fake_ask))
        question = Question(
            name="tags", message="m", kind=QuestionKind.MULTI_CHOICE,
            default=[], choices=["a", "b", "c"],
        )
        answers = RichPrompter()([question])
        assert answers == {"tags": ["a", "b"]}

    def test_multi_choice_retry_message_mentions_the_invalid_value(self, monkeypatch):
        responses = iter(["bogus", "a"])
        seen_prompts = []

        def fake_ask(cls, **kwargs):
            seen_prompts.append(kwargs["prompt"])
            return next(responses)

        monkeypatch.setattr(Prompt, "ask", classmethod(fake_ask))
        question = Question(
            name="tags", message="Pick tags", kind=QuestionKind.MULTI_CHOICE,
            default=[], choices=["a", "b"],
        )
        RichPrompter()([question])
        assert seen_prompts[0] == "Pick tags"
        assert "bogus" in seen_prompts[1]

    def test_multi_choice_with_non_string_choices_does_not_loop_forever(self, monkeypatch):
        # Regression test: question.choices preserves its original type
        # (e.g. [1, 2, 3] for a type=int, nargs="+" argument), but the
        # split answer from Prompt.ask is always a list of raw strings.
        # Comparing "1" against the unstringified {1, 2, 3} never matches,
        # so every answer looked invalid and the retry loop never
        # terminated. A call-count guard turns that into a fast, bounded
        # test failure instead of an actual hang.
        call_count = {"n": 0}

        def fake_ask(cls, **kwargs):
            call_count["n"] += 1
            if call_count["n"] > 10:
                raise AssertionError("RichPrompter looped more than 10 times on valid input")
            return "1 2"

        monkeypatch.setattr(Prompt, "ask", classmethod(fake_ask))
        question = Question(
            name="tags", message="m", kind=QuestionKind.MULTI_CHOICE,
            default=[], choices=[1, 2, 3],
        )
        answers = RichPrompter()([question])
        assert answers == {"tags": ["1", "2"]}
        assert call_count["n"] == 1

    def test_multi_choice_exhausts_attempts_and_raises_when_always_invalid(self, monkeypatch):
        # A genuinely-stuck validation (every answer invalid) must still
        # terminate - bounded, with a clear error - rather than loop forever.
        # The call-count guard is a safety net for this test itself: without
        # a bounded retry fix, this would otherwise hang instead of failing.
        call_count = {"n": 0}

        def fake_ask(cls, **kwargs):
            call_count["n"] += 1
            if call_count["n"] > 10:
                raise AssertionError("RichPrompter looped more than 10 times on invalid input")
            return "bogus"

        monkeypatch.setattr(Prompt, "ask", classmethod(fake_ask))
        question = Question(
            name="tags", message="m", kind=QuestionKind.MULTI_CHOICE,
            default=[], choices=["a", "b"],
        )
        with pytest.raises(ValueError):
            RichPrompter()([question])
