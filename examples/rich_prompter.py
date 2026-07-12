import argparse
from interactive_argparse import interactive


@interactive("rich")
def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="The user's name.")
    parser.add_argument("--should_greet", help="Whether or not I should greet the user", action="store_true")
    parser.add_argument("--color", help="A favorite color", choices=["red", "green", "blue"])
    return parser


def main():
    args = build_parser().parse_args()
    print(args)


if __name__ == "__main__":
    main()
