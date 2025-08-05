import os
from dotenv import load_dotenv
from words_parser import WordParser

# Load environment variables from .env file
load_dotenv()

HOME = os.getcwd()
DATA = os.path.join(HOME, "data")

# source = "https://raw.githubusercontent.com/arstgit/high-frequency-vocabulary/refs/heads/master/30k.txt"
source = os.path.join(DATA, "inputs", "lemmas_60k.txt")


def main():
    # Get Yandex API key from environment variables
    yandex_api_key = os.getenv("YANDEX_API_KEY")

    parser = WordParser(data_dir=DATA, yandex_api_key=yandex_api_key)
    parser.parse(source, max_words=9200, start_index=0, words_per_file=500)


if __name__ == "__main__":
    main()
