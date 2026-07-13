import argparse

import pytest

from interactive_argparse import InteractiveArgumentParser, PyInquirerPrompter, interactive, Prompter
from interactive_argparse.parse.interactive_parser import PROMPTER_ENV_VAR
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


class TestDefaultPrompterEnvVar:
    def test_unset_env_var_defaults_to_pyinquirer(self, monkeypatch):
        monkeypatch.delenv(PROMPTER_ENV_VAR, raising=False)
        prompter = InteractiveArgumentParser._build_default_prompter()
        assert isinstance(prompter, PyInquirerPrompter)

    def test_env_var_set_to_registered_name_resolves_that_prompter(self, monkeypatch):
        class _EnvDummyPrompter(Prompter):
            name = "env_dummy_test_prompter"

            def __call__(self, questions):
                return {q.name: q.default for q in questions}

        monkeypatch.setenv(PROMPTER_ENV_VAR, "env_dummy_test_prompter")
        prompter = InteractiveArgumentParser._build_default_prompter()
        assert isinstance(prompter, _EnvDummyPrompter)

    def test_env_var_set_to_unknown_name_raises(self, monkeypatch):
        monkeypatch.setenv(PROMPTER_ENV_VAR, "this_prompter_name_does_not_exist")
        with pytest.raises(ValueError):
            InteractiveArgumentParser._build_default_prompter()

    def test_env_var_with_incidental_whitespace_is_stripped(self, monkeypatch):
        class _EnvWhitespacePrompter(Prompter):
            name = "env_whitespace_test_prompter"

            def __call__(self, questions):
                return {q.name: q.default for q in questions}

        monkeypatch.setenv(PROMPTER_ENV_VAR, "  env_whitespace_test_prompter\n")
        prompter = InteractiveArgumentParser._build_default_prompter()
        assert isinstance(prompter, _EnvWhitespacePrompter)

    def test_env_var_set_to_only_whitespace_falls_back_to_pyinquirer(self, monkeypatch):
        monkeypatch.setenv(PROMPTER_ENV_VAR, "   ")
        prompter = InteractiveArgumentParser._build_default_prompter()
        assert isinstance(prompter, PyInquirerPrompter)

    def test_constructor_uses_env_var_when_no_prompter_passed_explicitly(self, monkeypatch):
        class _EnvDummyPrompter2(Prompter):
            name = "env_dummy_test_prompter_2"

            def __call__(self, questions):
                return {q.name: q.default for q in questions}

        monkeypatch.setenv(PROMPTER_ENV_VAR, "env_dummy_test_prompter_2")
        parser = InteractiveArgumentParser(argparse.ArgumentParser())
        assert isinstance(parser._prompter, _EnvDummyPrompter2)

    def test_explicit_prompter_argument_overrides_env_var(self, monkeypatch):
        monkeypatch.setenv(PROMPTER_ENV_VAR, "pyinquirer")
        fake = FakePrompter({})
        parser = InteractiveArgumentParser(argparse.ArgumentParser(), prompter=fake)
        assert parser._prompter is fake


class _RaisingPrompter(Prompter):
    """A prompter that fails its own internal validation and gives up -
    e.g. a bounded-retry loop inside the prompter exhausting its attempts.
    Per the Prompter/Question contract, a prompter's __call__ is only ever
    expected to return raw answers, never raise - this simulates one that
    does anyway, to verify InteractiveArgumentParser degrades that to a
    normal usage error instead of a raw traceback.
    """
    def __init__(self, exc):
        self.exc = exc

    def __call__(self, questions):
        raise self.exc


class TestPrompterExceptionHandling:
    @staticmethod
    def _build_parser(prompter):
        parser = argparse.ArgumentParser(prog="prog")
        parser.add_argument("--name")
        return InteractiveArgumentParser(parser, prompter=prompter)

    def test_value_error_from_prompter_reports_usage_error_not_a_raw_crash(self, capsys):
        prompter = _RaisingPrompter(ValueError("could not satisfy validation"))
        with pytest.raises(SystemExit):
            self._build_parser(prompter).parse_args([])
        stderr = capsys.readouterr().err
        assert "usage:" in stderr

    def test_type_error_from_prompter_reports_usage_error_not_a_raw_crash(self, capsys):
        prompter = _RaisingPrompter(TypeError("bad prompter"))
        with pytest.raises(SystemExit):
            self._build_parser(prompter).parse_args([])
        stderr = capsys.readouterr().err
        assert "usage:" in stderr

    def test_rich_prompter_exhausted_multi_choice_retries_reports_usage_error(self, monkeypatch, capsys):
        # End-to-end: RichPrompter._ask_multi_choice raises ValueError once
        # its bounded retries are exhausted (see test_rich_prompter.py) -
        # verify that, wired through InteractiveArgumentParser for real,
        # this surfaces as a clean usage error, not a raw traceback.
        from rich.prompt import Prompt
        from interactive_argparse.parse.rich_prompter import RichPrompter

        monkeypatch.setattr(Prompt, "ask", classmethod(lambda cls, **kwargs: "bogus"))

        parser = argparse.ArgumentParser(prog="prog")
        parser.add_argument("--tags", nargs="+", choices=["a", "b"])
        iparser = InteractiveArgumentParser(parser, prompter=RichPrompter())

        with pytest.raises(SystemExit):
            iparser.parse_args([])
        stderr = capsys.readouterr().err
        assert "usage:" in stderr
