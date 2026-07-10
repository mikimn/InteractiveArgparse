import argparse
import pathlib
import sys
from typing import List

import pytest

from interactive_argparse import InteractiveArgumentParser, interactive, QuestionKind, PyInquirerPrompter
from interactive_argparse.parse.interactive_parser import _argparse_action_to_question, Question


class FakePrompter:
    def __init__(self, mapping: dict):
        self.questions = None
        self.mapping = mapping
        self.call_count = 0

    def __call__(self, questions: List[Question]):
        self.call_count += 1
        self.questions = questions
        return {q.name: self.mapping.get(q.name, q.default) for q in questions}


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


class TestArgparseActionToQuestion:
    def test_store_true_action_is_confirm_kind(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--should_greet", action="store_true")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.CONFIRM
        assert question.default is False

    def test_choices_without_nargs_is_single_choice_kind(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--color", choices=["red", "green", "blue"], default="red")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.SINGLE_CHOICE
        assert question.choices == ["red", "green", "blue"]
        assert question.default == "red"

    def test_nargs_plus_is_multi_choice_kind(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--list", nargs="+")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.MULTI_CHOICE

    def test_nargs_int_greater_than_one_is_multi_choice_kind(self):
        # Regression test: action.nargs can be a plain int (e.g. nargs=2),
        # which previously crashed on `action.nargs.isnumeric()`.
        parser = argparse.ArgumentParser()
        parser.add_argument("--pair", nargs=2)
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.MULTI_CHOICE

    def test_multi_choice_default_is_a_raw_list(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--tags", nargs="+", default=["a", "b"])
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.MULTI_CHOICE
        assert question.default == ["a", "b"]

    def test_positional_without_default_has_no_cast_or_default(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("name")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.TEXT
        assert question.default is None
        assert question.cast is None

    def test_type_int_without_default_gets_int_cast(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--count", type=int)
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.INT
        assert question.cast("5") == 5

    def test_int_default_is_raw_not_stringified(self):
        # Stringifying for text-based prompts (e.g. PyInquirer's "input"
        # question) is a prompter concern now, not a Question concern - see
        # TestPyInquirerPrompter for that translation.
        parser = argparse.ArgumentParser()
        parser.add_argument("--count", type=int, default=5)
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.INT
        assert question.default == 5
        assert isinstance(question.default, int)

    def test_custom_type_outside_known_set_has_no_cast(self):
        # Documents current behavior: custom `type=` callables that aren't
        # int/str/bool/float are not applied as a cast, so the answer stays
        # as the raw (usually string) value from the prompter.
        parser = argparse.ArgumentParser()
        parser.add_argument("--path", type=pathlib.Path)
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.cast is None

    def test_suppress_default_returns_none(self):
        parser = argparse.ArgumentParser()
        help_action = parser._actions[0]
        assert help_action.default == argparse.SUPPRESS
        assert _argparse_action_to_question(help_action) is None

    def test_subparsers_action_returns_none(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        subparsers.add_parser("run")
        assert _argparse_action_to_question(parser._actions[-1]) is None


class TestPyInquirerPrompter:
    def test_text_like_kinds_map_to_input_type(self):
        for kind in (QuestionKind.TEXT, QuestionKind.INT, QuestionKind.FLOAT):
            question = Question(name="n", message="m", kind=kind)
            result = PyInquirerPrompter._to_pyinquirer_dict(question)
            assert result["type"] == "input"

    def test_confirm_kind_maps_to_confirm_type_with_raw_default(self):
        question = Question(name="n", message="m", kind=QuestionKind.CONFIRM, default=True)
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert result["type"] == "confirm"
        assert result["default"] is True

    def test_single_choice_kind_maps_to_list_type(self):
        question = Question(
            name="n", message="m", kind=QuestionKind.SINGLE_CHOICE,
            default="red", choices=["red", "green"],
        )
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert result["type"] == "list"
        assert result["choices"] == ["red", "green"]
        assert result["default"] == "red"

    def test_multi_choice_kind_maps_to_checkbox_type_with_raw_default(self):
        question = Question(name="n", message="m", kind=QuestionKind.MULTI_CHOICE, default=["a", "b"])
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert result["type"] == "checkbox"
        assert result["default"] == ["a", "b"]

    def test_int_default_is_stringified_for_pyinquirer(self):
        question = Question(name="n", message="m", kind=QuestionKind.INT, default=5)
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert result["default"] == "5"
        assert isinstance(result["default"], str)

    def test_no_default_omits_default_key(self):
        question = Question(name="n", message="m", kind=QuestionKind.TEXT)
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert "default" not in result

    def test_no_choices_omits_choices_key(self):
        question = Question(name="n", message="m", kind=QuestionKind.TEXT)
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert "choices" not in result

    def test_pyinquirer_is_not_imported_until_prompter_is_used(self):
        assert "PyInquirer" not in sys.modules
        PyInquirerPrompter()
        assert "PyInquirer" not in sys.modules


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
