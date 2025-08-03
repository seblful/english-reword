import os
from dotenv import load_dotenv
from words_parser import WordHuntParser

# Load environment variables from .env file
load_dotenv()

HOME = os.getcwd()
DATA = os.path.join(HOME, "data")

# source = "https://raw.githubusercontent.com/first20hours/google-10000-english/refs/heads/master/google-10000-english-usa.txt"
# source = "https://gist.githubusercontent.com/eyturner/3d56f6a194f411af9f29df4c9d4a4e6e/raw/63b6dbaf2719392cb2c55eb07a6b1d4e758cc16d/20k.txt"
# source = "https://raw.githubusercontent.com/arstgit/high-frequency-vocabulary/refs/heads/master/30k.txt"
source = os.path.join(DATA, "inputs", "lemmas_60k.txt")


def main():
    # Get Yandex API key from environment variables
    yandex_api_key = os.getenv("YANDEX_API_KEY")
    if not yandex_api_key:
        print("Warning: YANDEX_API_KEY not found in .env file")

    parser = WordHuntParser(data_dir=DATA, yandex_api_key=yandex_api_key)
    parser.parse(source, max_words=25000, start_index=15201, words_per_file=1000)


if __name__ == "__main__":
    main()
