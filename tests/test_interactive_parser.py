import argparse
import json

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


class _FlakyPrompter(Prompter):
    """Returns a canned answer dict per call, in order - lets a test drive a
    prompter through an invalid answer, followed by a corrected one (or
    another invalid one, or a cancellation), without any real terminal
    interaction.
    """
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, questions):
        self.calls.append(questions)
        return self.responses.pop(0)


class TestCastErrorHandling:
    @staticmethod
    def _build_parser(prompter):
        parser = argparse.ArgumentParser(prog="prog")
        parser.add_argument("--count", type=int, default=1)
        return InteractiveArgumentParser(parser, prompter=prompter)

    def test_invalid_answer_re_prompts_and_succeeds_with_corrected_value(self):
        prompter = _FlakyPrompter([
            {"count": "abc"},
            {"count": "5"},
        ])
        namespace = self._build_parser(prompter).parse_args([])
        assert namespace.count == 5
        assert len(prompter.calls) == 2
        # The retry only re-asks the one question that failed to cast.
        assert len(prompter.calls[1]) == 1
        assert prompter.calls[1][0].name == "count"

    def test_repeatedly_invalid_answer_exhausts_retries_and_reports_usage_error(self, capsys):
        prompter = _FlakyPrompter([
            {"count": "abc"},
            {"count": "def"},
            {"count": "ghi"},
        ])
        with pytest.raises(SystemExit):
            self._build_parser(prompter).parse_args([])
        assert len(prompter.calls) == 3
        stderr = capsys.readouterr().err
        assert "count" in stderr
        assert "invalid value" in stderr

    def test_cancelling_during_a_retry_exits_cleanly(self):
        prompter = _FlakyPrompter([
            {"count": "abc"},
            {},  # cancelled
        ])
        with pytest.raises(SystemExit):
            self._build_parser(prompter).parse_args([])

    def test_retry_answer_missing_the_expected_key_reports_usage_error(self, capsys):
        # A malformed prompter that returns a non-empty dict on retry, but
        # without the one key that was actually asked for - must not raise
        # a raw KeyError, and must still report the same usage error as
        # exhausted retries.
        prompter = _FlakyPrompter([
            {"count": "abc"},
            {"unrelated_key": "5"},
        ])
        with pytest.raises(SystemExit):
            self._build_parser(prompter).parse_args([])
        assert len(prompter.calls) == 2
        stderr = capsys.readouterr().err
        assert "count" in stderr
        assert "invalid value" in stderr

    def test_valid_answer_is_not_re_prompted(self):
        prompter = _FlakyPrompter([{"count": "7"}])
        namespace = self._build_parser(prompter).parse_args([])
        assert namespace.count == 7
        assert len(prompter.calls) == 1


class TestPersistAnswers:
    @staticmethod
    def _build_parser(path, prompter, prog="prog"):
        parser = argparse.ArgumentParser(prog=prog)
        parser.add_argument("--count", type=int, default=1)
        return InteractiveArgumentParser(parser, prompter=prompter, persist_answers=path)

    def test_disabled_by_default_does_not_write_a_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        parser = argparse.ArgumentParser(prog="prog")
        parser.add_argument("--count", type=int, default=1)
        iparser = InteractiveArgumentParser(parser, prompter=FakePrompter({"count": 5}))
        iparser.parse_args([])
        assert list(tmp_path.iterdir()) == []

    def test_first_run_writes_answers_file(self, tmp_path):
        answers_path = tmp_path / "answers.json"
        namespace = self._build_parser(str(answers_path), FakePrompter({"count": 5})).parse_args([])
        assert namespace.count == 5
        assert answers_path.exists()
        assert json.loads(answers_path.read_text()) == {"count": 5}

    def test_second_run_reads_back_and_prefills_default(self, tmp_path):
        answers_path = tmp_path / "answers.json"
        answers_path.write_text(json.dumps({"count": 42}))

        # An empty FakePrompter mapping falls back to each Question's
        # `default` - so if the persisted value round-trips into `default`,
        # the resulting namespace carries it through untouched.
        fake = FakePrompter({})
        namespace = self._build_parser(str(answers_path), fake).parse_args([])
        assert namespace.count == 42
        assert fake.questions[0].default == 42

    def test_persisted_default_does_not_change_the_static_action_default(self, tmp_path):
        answers_path = tmp_path / "answers.json"
        answers_path.write_text(json.dumps({"count": 42}))

        parser = argparse.ArgumentParser(prog="prog")
        parser.add_argument("--count", type=int, default=1)
        iparser = InteractiveArgumentParser(parser, prompter=FakePrompter({}), persist_answers=str(answers_path))
        iparser.parse_args([])

        count_action = next(a for a in parser._actions if a.dest == "count")
        assert count_action.default == 1

    def test_missing_file_degrades_to_static_default(self, tmp_path):
        answers_path = tmp_path / "does_not_exist.json"
        namespace = self._build_parser(str(answers_path), FakePrompter({})).parse_args([])
        assert namespace.count == 1

    def test_corrupt_file_degrades_to_static_default(self, tmp_path):
        answers_path = tmp_path / "answers.json"
        answers_path.write_text("{not valid json")
        namespace = self._build_parser(str(answers_path), FakePrompter({})).parse_args([])
        assert namespace.count == 1

    def test_non_dict_json_degrades_to_static_default(self, tmp_path):
        answers_path = tmp_path / "answers.json"
        answers_path.write_text(json.dumps([1, 2, 3]))
        namespace = self._build_parser(str(answers_path), FakePrompter({})).parse_args([])
        assert namespace.count == 1

    def test_persist_answers_true_derives_a_filename_from_prog(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        parser = argparse.ArgumentParser(prog="myscript")
        parser.add_argument("--count", type=int, default=1)
        iparser = InteractiveArgumentParser(parser, prompter=FakePrompter({"count": 9}), persist_answers=True)
        iparser.parse_args([])

        expected_path = tmp_path / ".myscript.interactive_argparse_answers.json"
        assert expected_path.exists()
        assert json.loads(expected_path.read_text()) == {"count": 9}
