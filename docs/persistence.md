# Persisting answers across runs

Every run of an interactively-wrapped script normally starts fresh from each argument's static `default=`. For a script you run repeatedly during development — most values staying the same between runs — that means re-typing the same answers over and over.

`InteractiveArgumentParser(parser, persist_answers=True)` opts into remembering what you answered last time and pre-filling it as the new default, without changing anything about the script's code:

```python
import argparse
from interactive_argparse import InteractiveArgumentParser


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--learning_rate", type=float, default=0.001)

    iparser = InteractiveArgumentParser(parser, persist_answers=True)
    args = iparser.parse_args()
    print(args)


if __name__ == "__main__":
    main()
```

The first run prompts using the static defaults (`10`, `0.001`) as usual. Whatever you answer is written to a local JSON file after a successful prompt. The next run reads that file back and shows your previous answers as the defaults instead — but only as what's *shown* to the prompter. The `ArgumentParser`'s own `default=` is never modified, so `--no_interactive` (or passing real CLI args) still falls back to the original static defaults, not your last interactive answers.

See [`examples/persist_answers.py`](../examples/persist_answers.py) for a complete, runnable version of the example above.

## Where answers are stored

- `persist_answers=True` derives a filename from the parser's `prog` (e.g. `.myscript.interactive_argparse_answers.json`), written in the current working directory.
- `persist_answers="path/to/file.json"` uses that exact path instead, if you want a specific location (e.g. shared across scripts, or outside the working directory).
- `persist_answers=False` (the default) disables this entirely — nothing is read or written, and behavior is unchanged from before this feature existed.

## Failure handling

If the file is missing (first run) or unreadable/corrupt (not valid JSON, or valid JSON that isn't an object), it's treated as if no answers were persisted yet — every argument falls back to its static default, exactly like `persist_answers=False`. Nothing raises for a missing or corrupt file; only a failure to *write* the file (e.g. an unwritable directory) propagates as a normal `OSError`, since at that point you've explicitly opted into persistence and would want to know it's not working.
