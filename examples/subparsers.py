import argparse
import os
import sys
sys.path.append(os.getcwd())
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
