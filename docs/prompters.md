# Prompters

`InteractiveArgumentParser` doesn't know how to render questions itself — that job belongs to a **prompter**: a callable that takes the list of questions built from your `ArgumentParser` and returns the user's answers. By default it uses [PyInquirer](https://github.com/CITGuru/PyInquirer) to prompt in the terminal, but you can plug in a completely different interactive flow — for example, a web form.

## Built-in prompters

| Prompter | Registered name | Renders as | Extra dependency |
| --- | --- | --- | --- |
| `PyInquirerPrompter` | `"pyinquirer"` | Terminal prompts (the default) | none (bundled) |
| `RichPrompter` | `"rich"` | Terminal prompts via [`rich.prompt`](https://rich.readthedocs.io/en/stable/prompt.html) | none (bundled) |
| `WebPrompter` | `"web"` | An auto-generated web form, opened in your browser | `pip install InteractiveArgparse[web]` |

## Using `RichPrompter`

`rich` is already a bundled dependency (used to build a maintained terminal prompt without PyInquirer's `prompt_toolkit<2.0` pin and `collections.Mapping` compat shim), so no extra install is needed:

```python
from interactive_argparse import interactive


@interactive("rich")
def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="The user's name.")
    parser.add_argument("--should_greet", help="Whether or not I should greet the user", action="store_true")
    parser.add_argument("--color", help="A favorite color", choices=["red", "green", "blue"])
    return parser


args = build_parser().parse_args()
```

`rich.prompt` has no native multi-select control, so a `MULTI_CHOICE` question (e.g. `nargs="+"`) falls back to a free-text prompt, split on commas/whitespace into a list — values are still checked against `choices=` if the argument has any, with a re-prompt on an invalid entry (up to 3 attempts, then a clear error rather than prompting forever).

See [`examples/rich_prompter.py`](../examples/rich_prompter.py) for a complete, runnable version of the example above.

## Using `WebPrompter`

Install the `web` extra first:

```shell script
pip install InteractiveArgparse[web]
```

Then pass a `WebPrompter` instance to `InteractiveArgumentParser`:

```python
import argparse
from interactive_argparse import InteractiveArgumentParser
from interactive_argparse.parse.web_prompter import WebPrompter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="The user's name.")
    parser.add_argument("--should_greet", help="Whether or not I should greet the user", action="store_true")
    parser.add_argument("--color", help="A favorite color", choices=["red", "green", "blue"])

    iparser = InteractiveArgumentParser(parser, prompter=WebPrompter())
    args = iparser.parse_args()
    print(args)


if __name__ == "__main__":
    main()
```

Running this without arguments starts a local web server, opens your browser to it, and blocks until you submit the form — the same way the terminal prompt blocks until you answer its questions. Field labels are humanized from each argument's name (`--should_greet` becomes "Should greet"), and any `help=` text is shown as a caption under the field.

See [`examples/web.py`](../examples/web.py) for a complete, runnable version of the example above.

### Selecting a prompter by name

Every registered prompter can also be selected by name through the `@interactive` decorator, instead of constructing `InteractiveArgumentParser` directly:

```python
from interactive_argparse import interactive


@interactive("web")
def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name")
    return parser


args = build_parser().parse_args()
```

Bare `@interactive` (no arguments) keeps using the default `PyInquirerPrompter`, exactly as before. This only covers picking a *registered* prompter by name — for anything else (a custom `prompter` instance, `interactive_flag`, `enable_by_default`, ...) construct `InteractiveArgumentParser` directly instead.

### Selecting the default prompter via an environment variable

Scripts that construct `InteractiveArgumentParser` (or use bare `@interactive`) without an explicit `prompter=` normally always get `PyInquirerPrompter`. Setting the `INTERACTIVE_ARGPARSE_PROMPTER` environment variable overrides that default without touching the script's code — handy for e.g. using `WebPrompter` on your own machine while a CI/headless environment keeps the terminal prompter (or opts out entirely via `--no_interactive`):

```shell script
INTERACTIVE_ARGPARSE_PROMPTER=web python my_script.py
```

The value is looked up in `Prompter.registry` by name, same as `@interactive("name")`. An unset variable falls back to `PyInquirerPrompter`; a name that isn't registered raises a `ValueError` listing the registered prompters. An explicit `prompter=` argument (or a name passed to `@interactive(...)`) always takes precedence over the environment variable.

## Writing a custom prompter

A prompter is any `Prompter` subclass that implements `__call__` and returns a `{argument_name: raw_answer}` dict:

```python
from typing import Any, Dict, List
from interactive_argparse import Prompter
from interactive_argparse.parse.question import Question


class MyPrompter(Prompter):
    name = "mine"  # registers this class as Prompter.registry["mine"]

    def __call__(self, questions: List[Question]) -> Dict[str, Any]:
        answers = {}
        for question in questions:
            answers[question.name] = ...  # collect the answer however you like
        return answers
```

Setting `name` auto-registers the class in `Prompter.registry`, which is what makes `@interactive("mine")` resolve it. If you don't need name-based lookup, you can just leave `name` unset and pass an instance directly: `InteractiveArgumentParser(parser, prompter=MyPrompter())`.

Each `Question` describes one argument, independent of any particular UI:

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | `str` | The argument's `dest` — the key your answer dict must use. |
| `message` | `str` | A ready-to-use, terminal-formatted prompt string (name, help and default combined). |
| `help` | `Optional[str]` | The raw, unformatted `help=` text, for prompters that want to lay out label and description separately (this is what `WebPrompter` uses). |
| `kind` | `QuestionKind` | `TEXT`, `INT`, `FLOAT`, `CONFIRM`, `SINGLE_CHOICE`, or `MULTI_CHOICE`. |
| `default` | `Any` | The argument's default value, in its real type — never stringified. |
| `choices` | `Optional[List[Any]]` | The argument's `choices=`, if any. |
| `cast` | `Optional[Callable]` | Do **not** call this yourself — `InteractiveArgumentParser` applies it to whatever raw value your prompter returns, so every prompter gets correct type coercion for free. Just return the most natural value for your UI (e.g. a raw string from a text field). |

Return raw answers — don't apply `cast` yourself, and don't worry about stringifying `default`/`choices` for display; format them however your UI needs.

If your prompter does its own validation and gives up (e.g. a bounded retry loop, the way `RichPrompter` handles a `MULTI_CHOICE` question with a fixed set of `choices`), it's fine to raise a `ValueError` or `TypeError` instead of returning - `InteractiveArgumentParser` catches both and reports a normal argparse usage error, the same as any other unrecoverable answer.
