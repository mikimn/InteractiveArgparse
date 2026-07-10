import argparse
import os
import sys
sys.path.append(os.getcwd())
from interactive_argparse import InteractiveArgumentParser
from interactive_argparse.parse.web_prompter import WebPrompter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="The user's name.")
    parser.add_argument("--should_greet", help="Whether or not I should greet the user", action="store_true")
    parser.add_argument("--color", help="A favorite color", choices=["red", "green", "blue"])

    # The @interactive decorator intentionally takes no configuration, so a
    # custom prompter like WebPrompter needs InteractiveArgumentParser
    # constructed directly instead.
    iparser = InteractiveArgumentParser(parser, prompter=WebPrompter())
    args = iparser.parse_args()
    print(args)


if __name__ == "__main__":
    main()
