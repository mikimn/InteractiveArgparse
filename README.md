# InteractiveArgparse
![Coverage](docs/assets/coverage.svg)
![Build Status](https://github.com/mikimn/InteractiveArgparse/actions/workflows/python-package.yml/badge.svg)
![PyPI version](https://badge.fury.io/py/InteractiveArgparse.svg)

## Table of Contents

* [Installation](#installation)
* [Getting Started](#getting-started)
* [Usage](#usage)
* [Features](#features)

## Installation
To install, run
```shell script
pip install InteractiveArgparse
```

## Getting Started
The simplest use case of Arggo is to setup arguments for a script.
Start by defining arguments in a data class:
```python
from dataclasses import dataclass
from arggo.dataclass_utils import parser_field

```

Then, annotate your main function to magically receive an arguments class :

```python
import arggo


@arggo.consume
def main(args: Arguments):
    if args.should_greet:
        print(f"Greetings, {args.name}!")
```
Test by running
```shell script
python main.py --name John --should_greet
```
Outputs
```text
Greetings, John!
```

That's it!

## Usage

### Configuration

You can configure Arggo by using `arggo.configure()` instead, like so:

```python
import arggo


@arggo.configure(
    parser_argument_index=1,
    logging_dir="my_logs"
)
def greet_user(count: int, args: Arguments):
    numeral = {1: "st", 2: "nd", 3: "rd"}
    numeral = numeral[count] if count in numeral else 'th'
    if args.should_greet:
        print(f"Greetings for the {count}{numeral} time, {args.name}!")


def main():
    for i in range(4):
        greet_user(i)


main()
```

Running
```shell script
python main.py --name John
```
Outputs
```text
Greetings for the 0th time, John!
Greetings for the 1st time, John!
Greetings for the 2nd time, John!
Greetings for the 3rd time, John!
```

The `consume` and `configure()` decorators work for any function, and guarantee that the same objects are provided each time.

**Note**: Arggo relies on the first `configure()` it uses to load everything, initialize the work directory and
configure parametes. Future versions will make `consume` automatically find
the appropriate type parameter to inject the arguments object into, and consequently
`configure()` will throw an error when used more than once.

### Meta-arguments

Arggo attaches meta-arguments to each script, allowing for some extra functionality.
To view all possible meta-arguments, run your script with the `--arggo_help` flag
```shell
python main.py --arggo_help
```

#### Interactive Runs

You can provide arguments to a program interactively by supplying the `--arggo_interactive` flag:
```shell
python main.py --arggo_help
```

### Command Line Interface

Arggo powers a CLI for many useful actions. To view more information, run
```shell
arggo-cli --help
```

#### Creating a New Experiment

```shell
arggo-cli experiment create <experiment_name>
```

This command automatically creates a starter file `<experiment_name>.py`

#### Reproducing an Existing Experiment

To reproduce results of a previous experiment run, type
```shell
arggo-cli experiment reproduce <experiment_name>
```

This looks for any experiments in the `logs/` folder, and allows you to interactively choose which one to reproduce.

## Development

### Running tests

To run all tests:
```shell
python -m pytest --cov=arggo
```

## Contributing

We welcome early adopters and contributors to this project! See the [Contributing](CONTRIBUTING.md) section for details.

## License

This project is open-sourced under the MIT license. See [LICENSE](LICENSE.md) for details.

## Attributions

Icons made by [Freepik](https://www.freepik.com) from [www.flaticon.com](https://www.flaticon.com/)
