import argparse
import sys

import pytest

from interactive_argparse import InteractiveArgumentParser, interactive, Prompter, QuestionKind
from interactive_argparse.parse.question import Question
from interactive_argparse.parse.web_prompter import WebPrompter
from helpers import FakePrompter


class TestInteractiveParser:
    def test_interactive_parser_proxy_add_argument(self):
        parser = InteractiveArgumentParser(argparse.ArgumentParser(), prompter=FakePrompter({
            "string": "not_default"
        }))
        parser.add_argument("-s", "--string", help="A basic string", default="default")
        namespace = parser.parse_args([])
        assert namespace.string == "not_default"

    def test_interactive_parser_basic_string(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-s", "--string", help="A basic string", default="default")

        iparser = InteractiveArgumentParser(parser, prompter=FakePrompter({
            "string": "not_default"
        }))
        namespace = iparser.parse_args([])
        assert namespace.string == "not_default"

    def test_interactive_parser_primitive_types(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-i", "--int", help="A basic int")
        parser.add_argument("-f", "--float", help="A basic int")
        parser.add_argument("-b", "--bool", help="A bool flag", action="store_true")
        parser.add_argument("-l", "--list", help="A basic list", nargs="+")

        iparser = InteractiveArgumentParser(parser, prompter=FakePrompter({
            "int": 4,
            "float": 3.0,
            "bool": False,
            "list": ["hello", "world"]
        }))
        namespace = iparser.parse_args([])
        assert namespace.int == 4
        assert namespace.float == 3.0
        assert not namespace.bool
        assert namespace.list == ["hello", "world"]


class TestInteractiveParserEndToEnd:
    @staticmethod
    def _build_parser():
        parser = argparse.ArgumentParser()
        parser.add_argument("-s", "--string", help="A basic string", default="default")
        parser.add_argument("-i", "--int", help="A basic int", type=int, default=1)
        parser.add_argument("-f", "--float", help="A basic float", type=float, default=1.0)
        parser.add_argument("-b", "--bool", help="A bool flag", action="store_true")
        parser.add_argument("-l", "--list", help="A basic list", nargs="+", default=["x"])
        parser.add_argument("-c", "--color", help="A choice", choices=["red", "green", "blue"], default="red")
        parser.add_argument("name", help="A positional")
        return parser

    def test_full_parser_happy_path(self):
        parser = self._build_parser()
        prompter = FakePrompter({
            "string": "hello",
            "int": 5,
            "float": 2.5,
            "bool": True,
            "list": ["a", "b"],
            "color": "green",
            "name": "alice",
        })
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        namespace = iparser.parse_args([])
        assert namespace.string == "hello"
        assert namespace.int == 5
        assert namespace.float == 2.5
        assert namespace.bool is True
        assert namespace.list == ["a", "b"]
        assert namespace.color == "green"
        assert namespace.name == "alice"

    def test_defaults_are_prepopulated_and_preserved(self):
        parser = self._build_parser()
        # Only answer the positional; everything else should fall back to
        # its declared default, correctly typed.
        prompter = FakePrompter({"name": "alice"})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        namespace = iparser.parse_args([])
        assert namespace.string == "default"
        assert namespace.int == 1
        assert namespace.float == 1.0
        assert namespace.bool is False
        assert namespace.list == ["x"]
        assert namespace.color == "red"

    def test_second_call_does_not_reprompt(self):
        parser = self._build_parser()
        prompter = FakePrompter({"name": "alice"})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        first = iparser.parse_args([])
        second_namespace, extras = iparser.parse_known_args([])
        assert prompter.call_count == 1
        assert extras == []
        assert second_namespace.name == first.name

    def test_cancel_raises_system_exit(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--name")
        iparser = InteractiveArgumentParser(parser, prompter=lambda questions: {})
        with pytest.raises(SystemExit):
            iparser.parse_args([])

    def test_proxy_passthrough_to_base_parser(self):
        base = argparse.ArgumentParser(description="desc", prog="myprog")
        iparser = InteractiveArgumentParser(base, prompter=FakePrompter({}))
        assert iparser.description == "desc"
        assert iparser.prog == "myprog"
        assert iparser.add_mutually_exclusive_group() is not None

    def test_real_args_skip_prompting(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--name")
        parser.add_argument("--should_greet", action="store_true")
        prompter = FakePrompter({})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        namespace = iparser.parse_args(["--name", "Alice", "--should_greet"])
        assert namespace.name == "Alice"
        assert namespace.should_greet is True
        assert prompter.call_count == 0

    def test_no_interactive_flag_skips_prompting(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--name", default="bob")
        prompter = FakePrompter({})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        namespace = iparser.parse_args(["--no_interactive"])
        assert namespace.name == "bob"
        assert prompter.call_count == 0

    def test_no_interactive_flag_with_missing_required_arg_errors(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--name", required=True)
        prompter = FakePrompter({})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        with pytest.raises(SystemExit):
            iparser.parse_known_args(["--no_interactive"])

    def test_subparsers_does_not_crash_during_prompting(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        subparsers.add_parser("run")
        parser.add_argument("--name", default="bob")
        prompter = FakePrompter({})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        namespace = iparser.parse_args([])
        assert namespace.name == "bob"

    def test_coercion_is_applied_regardless_of_prompter(self):
        # A "dumb" prompter that always returns raw strings, the way a naive
        # web form might, without knowing anything about type coercion.
        # InteractiveArgumentParser must still produce correctly-typed
        # values - coercion is no longer something prompters opt into.
        def dumb_prompter(questions):
            return {q.name: "5" if q.name == "count" else str(q.default) for q in questions}

        parser = argparse.ArgumentParser()
        parser.add_argument("--count", type=int, default=0)
        iparser = InteractiveArgumentParser(parser, prompter=dumb_prompter)
        namespace = iparser.parse_args([])
        assert namespace.count == 5
        assert isinstance(namespace.count, int)


class TestInteractiveDecorator:
    def test_decorated_function_returns_interactive_argument_parser(self):
        @interactive
        def build_parser():
            parser = argparse.ArgumentParser(description="desc")
            parser.add_argument("--name")
            return parser

        wrapped = build_parser()
        assert isinstance(wrapped, InteractiveArgumentParser)
        assert wrapped.description == "desc"

    def test_functools_wraps_preserves_identity(self):
        @interactive
        def build_parser():
            """Builds a parser."""
            return argparse.ArgumentParser()

        assert build_parser.__name__ == "build_parser"
        assert build_parser.__doc__ == "Builds a parser."

    def test_args_and_kwargs_passthrough(self):
        @interactive
        def build_parser(prog_name):
            return argparse.ArgumentParser(prog=prog_name)

        wrapped = build_parser("myprog")
        assert wrapped.prog == "myprog"

    def test_each_call_returns_a_fresh_instance(self):
        @interactive
        def build_parser():
            return argparse.ArgumentParser()

        first = build_parser()
        second = build_parser()
        assert first is not second
        assert first._base_parser is not second._base_parser

    def test_real_args_skip_prompting_through_decorator(self):
        @interactive
        def build_parser():
            parser = argparse.ArgumentParser()
            parser.add_argument("--name")
            return parser

        namespace = build_parser().parse_args(["--name", "Alice"])
        assert namespace.name == "Alice"

    def test_prompting_works_end_to_end_through_decorator(self):
        @interactive
        def build_parser():
            parser = argparse.ArgumentParser()
            parser.add_argument("--name", default="default")
            return parser

        wrapped = build_parser()
        wrapped._prompter = FakePrompter({"name": "Alice"})
        namespace = wrapped.parse_args([])
        assert namespace.name == "Alice"


class TestInteractiveDecoratorPrompterByName:
    def test_decorator_resolves_prompter_by_registered_name(self):
        class _DummyPrompter(Prompter):
            name = "dummy_test_prompter"

            def __call__(self, questions):
                return {q.name: q.default for q in questions}

        @interactive("dummy_test_prompter")
        def build_parser():
            parser = argparse.ArgumentParser()
            parser.add_argument("--name", default="bob")
            return parser

        wrapped = build_parser()
        assert isinstance(wrapped._prompter, _DummyPrompter)
        namespace = wrapped.parse_args([])
        assert namespace.name == "bob"

    def test_decorator_raises_for_unknown_prompter_name(self):
        @interactive("this_prompter_name_does_not_exist")
        def build_parser():
            return argparse.ArgumentParser()

        with pytest.raises(ValueError):
            build_parser()

    def test_bare_decorator_still_uses_default_prompter(self):
        @interactive()
        def build_parser():
            parser = argparse.ArgumentParser()
            parser.add_argument("--name")
            return parser

        namespace = build_parser().parse_args(["--name", "Alice"])
        assert namespace.name == "Alice"


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
