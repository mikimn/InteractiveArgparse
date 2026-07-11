import argparse
import os
import sys
sys.path.append(os.getcwd())
from interactive_argparse import InteractiveArgumentParser


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs.")
    parser.add_argument("--learning_rate", type=float, default=0.001, help="Optimizer learning rate.")

    # Answers are written to .persist_answers.py.interactive_argparse_answers.json
    # after a successful prompt, and read back as the shown default next run.
    iparser = InteractiveArgumentParser(parser, persist_answers=True)
    args = iparser.parse_args()
    print(args)


if __name__ == "__main__":
    main()
