# Subcommands (`add_subparsers`)

`InteractiveArgumentParser` supports `ArgumentParser.add_subparsers()`: it prompts for a subcommand first, then prompts for that subcommand's own arguments.

```python
import argparse
from interactive_argparse import InteractiveArgumentParser


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--speed", type=int, default=1, help="How fast to run.")

    subparsers.add_parser("stop")

    iparser = InteractiveArgumentParser(parser)
    args = iparser.parse_args()
    print(args)


if __name__ == "__main__":
    main()
```

Run without arguments, this prompts for `command` (a choice of `run`/`stop`), and then — only after that's answered — prompts for whichever subcommand's own arguments (`--speed`, if `run` was chosen; nothing, if `stop` was chosen). Passing real CLI arguments (e.g. `run --speed 5`) or `--no_interactive` still dispatches to the chosen subcommand the normal, non-interactive `argparse` way.

See [`examples/subparsers.py`](../examples/subparsers.py) for a complete, runnable version of the example above.

## How it works

Prompting happens in rounds: one round for the top-level parser's own arguments plus the subcommand choice, then (if a subcommand was chosen) another round for that subcommand's own arguments, and so on for any further nesting (a subcommand that itself has `add_subparsers()`). Each round is a single, ordinary call to your `prompter` — nothing about writing a custom `Prompter` needs to change to support this; see [docs/prompters.md](prompters.md).

A few details worth knowing:

- If `add_subparsers(dest=...)` was given an explicit `dest` (as in the example above), the chosen subcommand name is set on the result under that name, exactly like non-interactive `argparse`.
- If `dest` was omitted (`add_subparsers()` with no `dest=`), `argparse` itself never stores the chosen subcommand name on the namespace — `InteractiveArgumentParser` matches that: the subcommand is still asked about (to know which arguments to prompt for next), just not written to the result.
- If a subcommand has no arguments of its own (like `stop` above), nothing further is asked once it's chosen — your prompter is only ever called with a non-empty list of questions.
- With no explicit `default=` on `add_subparsers()` (the common case), nothing is pre-selected — accepting a blank answer isn't possible; a subcommand must be actively chosen rather than one being silently picked by registration order.
