# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

InteractiveArgparse is a small Python library that wraps a standard `argparse.ArgumentParser` and turns it into an interactive CLI prompt (via PyInquirer) when the script is run without arguments. The entire implementation lives in one file: [interactive_argparse/parse/interactive_parser.py](interactive_argparse/parse/interactive_parser.py).

## Commands

Install dependencies:
```shell
pip install -r requirements.txt -r requirements-dev.txt
```

Run all tests:
```shell
python -m pytest
```

Run a single test:
```shell
python -m pytest tests/test_interactive_parser.py::TestInteractiveParser::test_interactive_parser_basic_string
```

Run tests with coverage (matches CI):
```shell
python -m pytest --cov=interactive_argparse
```

Lint (matches CI in [.github/workflows/python-package.yml](.github/workflows/python-package.yml)):
```shell
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

Format code (Black is configured as a pre-commit hook):
```shell
black .
```

Run the example script:
```shell
python examples/simple.py
```

## Architecture

- `InteractiveArgumentParser` ([interactive_argparse/parse/interactive_parser.py](interactive_argparse/parse/interactive_parser.py)) wraps a real `ArgumentParser` instance passed in by the caller. It does **not** subclass `ArgumentParser`; instead it proxies unknown attribute access to `self._base_parser` via `__getattr__`, so calls like `.add_argument(...)` pass straight through to the wrapped parser.
- It monkey-patches the wrapped parser's `parse_known_args` method with its own (`self._base_parser.parse_known_args = self.parse_known_args`) at construction time. This is the core trick that makes `iparser.parse_args()` — which internally calls `parse_known_args` — trigger interactive prompting instead of normal CLI parsing.
- `parse_known_args` builds an `argparse.Namespace` from the wrapped parser's registered `_actions` and `_defaults`, converts each `Action` into a PyInquirer question dict via `_argparse_action_to_question`, and passes the questions to a `prompter` callable (defaults to `PyInquirer.prompt`). Answers are merged into the namespace.
- Question-type inference from an `Action` (in `_argparse_action_to_question`) maps argparse concepts to PyInquirer question types: `nargs` of `"+"` or `>1` becomes a `checkbox`; an action with `choices` becomes a `list`; otherwise the type is guessed from `action.default`/`action.type` (`int`/`str`/`float` -> `input`, `bool` -> `confirm`).
- The parser caches the resulting `Namespace` (`self._namespace`) after the first prompt so repeated calls to `parse_known_args` don't re-prompt the user.
- The `prompter` is injectable via the constructor, which is what makes the library testable without an actual terminal prompt — see `FakePrompter` in [tests/test_interactive_parser.py](tests/test_interactive_parser.py), which answers questions from a dict instead of prompting interactively.
- `_init_interactive_parser` (called from `__init__`) adds a `--no_interactive`/`--interactive` flag (name/polarity controlled by `interactive_flag`/`enable_by_default`) to the wrapped parser. `parse_known_args` skips prompting — delegating to the base parser's real, unpatched `ArgumentParser.parse_known_args` — whenever that flag is passed or real CLI args are supplied; it only prompts on a fully bare invocation.

## Notes

- Supported Python versions: `>=3.7` (per [setup.cfg](setup.cfg)); CI matrix tests 3.8, 3.9, and 3.12. A `collections.Mapping` compat shim in [interactive_parser.py](interactive_argparse/parse/interactive_parser.py) is required for PyInquirer's pinned `prompt_toolkit<2.0` to import on Python 3.10+.
- Runtime dependencies are pinned in [requirements.txt](requirements.txt): `PyInquirer`, `prompt_toolkit`, `rich`.
- PRs should address a single concern with minimal changed lines, and include tests for changed functionality — see [CONTRIBUTING.md](CONTRIBUTING.md).
