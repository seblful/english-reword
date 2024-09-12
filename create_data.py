import os

from formatter import RewordFormatter

HOME = os.getcwd()
DATA = os.path.join(HOME, "data")

JSON_NAME = "phrasal_verbs.json"


def main() -> None:
    formatter = RewordFormatter(data_dir=DATA,
                                use_description=True,
                                max_words=5000)

    formatter.format_json(json_name=JSON_NAME)


if __name__ == "__main__":
    main()
