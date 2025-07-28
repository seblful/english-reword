import os
from words_parser import WordHuntParser

HOME = os.getcwd()
DATA = os.path.join(HOME, "data")

# source = "https://raw.githubusercontent.com/first20hours/google-10000-english/refs/heads/master/google-10000-english-usa.txt"
# source = "https://gist.githubusercontent.com/eyturner/3d56f6a194f411af9f29df4c9d4a4e6e/raw/63b6dbaf2719392cb2c55eb07a6b1d4e758cc16d/20k.txt"
source = "https://raw.githubusercontent.com/arstgit/high-frequency-vocabulary/refs/heads/master/30k.txt"


def main():
    parser = WordHuntParser(data_dir=DATA)
    parser.parse(source, max_words=30000, start_index=0, words_per_file=1000)


if __name__ == "__main__":
    main()
