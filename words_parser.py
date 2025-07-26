import os
import csv
import tracemalloc
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

tracemalloc.start()


class CambridgeDictionaryParser:
    def __init__(self, data_dir: str):
        self.outputs_dir = os.path.join(data_dir, "outputs")
        self.output_file = os.path.join(
            self.outputs_dir, "cambridge_dictionary_data.csv"
        )
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def fetch_word_list(self, source):
        """Fetch word list from either URL or local file"""
        if source.startswith(("http://", "https://")):
            try:
                response = requests.get(source, headers=self.headers)
                response.raise_for_status()
                return [
                    word.strip() for word in response.text.split("\n") if word.strip()
                ]
            except requests.RequestException as e:
                print(f"Error fetching word list from URL: {e}")
                return []
        else:
            # Assume it's a local file path
            try:
                with open(source, "r", encoding="utf-8") as f:
                    return [line.strip() for line in f if line.strip()]
            except IOError as e:
                print(f"Error reading word list file: {e}")
                return []

    def parse_word_data(self, word):
        """Parse Cambridge Dictionary data for a single word"""
        url = f"https://dictionary.cambridge.org/dictionary/english-russian/{word.lower()}"
        translator = GoogleTranslator(source="en", target="ru")

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Get transcription
            transcription = (
                soup.find("span", {"class": "ipa"}).text
                if soup.find("span", {"class": "ipa"})
                else ""
            )

            # Get translation (first Russian translation)
            translation = ""
            trans_block = soup.find("span", {"class": "trans"})
            if trans_block:
                translation = trans_block.text.strip()

            # Get examples (up to 2)
            examples = []
            ex_blocks = soup.find_all("div", {"class": "examp"})[:2]
            for ex in ex_blocks:
                examples.append(ex.text.strip())

            # Translate examples to Russian using Google Translate
            ex_translations = []
            for example in examples:
                if example:
                    try:
                        translated = translator.translate(example)
                        ex_translations.append(translated)
                    except Exception as e:
                        print(f"Translation error for example '{example}': {e}")
                        ex_translations.append("")
                else:
                    ex_translations.append("")

            # Pad with empty strings if not enough examples
            while len(examples) < 2:
                examples.append("")
            while len(ex_translations) < 2:
                ex_translations.append("")

            return {
                "word": word,
                "transcription": transcription,
                "translation": translation,
                "example1": examples[0],
                "ex_translation1": ex_translations[0],
                "example2": examples[1],
                "ex_translation2": ex_translations[1],
            }

        except requests.RequestException as e:
            print(f"Error fetching data for {word}: {e}")
            return None

    def save_to_csv(self, data):
        """Save parsed data to CSV file"""
        try:
            with open(self.output_file, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = [
                    "word",
                    "transcription",
                    "translation",
                    "example1",
                    "ex_translation1",
                    "example2",
                    "ex_translation2",
                ]
                writer = csv.DictWriter(
                    csvfile,
                    fieldnames=fieldnames,
                    delimiter=";",
                    quotechar='"',
                    quoting=csv.QUOTE_ALL,
                )
                writer.writeheader()
                for item in data:
                    if item:  # Only write if data exists
                        writer.writerow(item)
            print(f"Data successfully saved to {self.output_file}")
        except IOError as e:
            print(f"Error writing to CSV file: {e}")

    def parse(self, source):
        """Main method to process all words"""
        words = self.fetch_word_list(source)
        if not words:
            print("No words to process.")
            return

        print(f"Found {len(words)} words to process...")

        results = []
        for i, word in enumerate(words, 1):
            print(f"Processing {i}/{len(words)}: {word}")
            word_data = self.parse_word_data(word)
            if word_data:
                results.append(word_data)

        self.save_to_csv(results)
