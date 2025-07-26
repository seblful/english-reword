import os
import csv
import tracemalloc
import requests
from bs4 import BeautifulSoup

tracemalloc.start()


class WordHuntParser:
    def __init__(self, data_dir: str):
        self.outputs_dir = os.path.join(data_dir, "outputs")
        self.output_file = os.path.join(self.outputs_dir, "word_hunt_data.csv")
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

    def extract_american_transcription(self, trans_block):
        def replace_pipes(text):
            # Replace first | with [ and second | with ]
            parts = text.split("|")
            if len(parts) >= 3:  # We have text between pipes
                return f"[{parts[1]}]"
            return text  # fallback if no pipes found

        # Try pattern 1 (with "амер." in es_div_1)
        amer_div = trans_block.find("i", string="амер.")
        if amer_div:
            trans_div = amer_div.find_parent("div", class_="trans_sound")
            if trans_div:
                amer_section = amer_div.find_parent("div").find_next_sibling("div")
                if amer_section:
                    transcriptions = [
                        replace_pipes(span.get_text(strip=True))
                        for span in amer_section.find_all(
                            "span", class_="transcription"
                        )
                    ]
                    return ", ".join(transcriptions)

        # Try pattern 2 (with id="us_tr_sound")
        us_div = trans_block.find("div", id="us_tr_sound")
        if us_div:
            transcription = us_div.find("span", class_="transcription")
            if transcription:
                return replace_pipes(transcription.get_text(strip=True))

        return None

    def parse_word_data(self, word):
        """Parse WoordHunt data for a single word"""
        url = f"https://wooordhunt.ru/word/{word.lower()}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Check if word exists
            if "К сожалению" in soup.text or "В тексте песен" in soup.text:
                print(f"Word '{word}' not found in WoordHunt")
                return None

            # Get transcription
            transcription = ""
            trans_block = soup.find("div", class_="trans_sound")
            if trans_block:
                transcription = self.extract_american_transcription(trans_block)

            # Get translation
            translation = ""
            translation_block = soup.find("div", class_="t_inline_en")
            if translation_block:
                translation = translation_block.text.strip()
            else:
                print(f"Word '{word}' doesn't have a translation")
                return None

            # Get examples
            examples = []
            ex_translations = []

            # example_block = soup.find("div", class_="block")
            # example_block = soup.select_one("div.block:not([id])")
            example_block = soup.find(
                lambda tag: tag.name == "div"
                and tag.get("class") == ["block"]
                and not tag.has_attr("id")
            )
            if example_block:
                # Find all paragraphs with class 'ex_o' for English examples
                english_examples = example_block.find_all("p", class_="ex_o")

                for eng_ex in english_examples:
                    # Check if the number of examples is sufficient
                    if len(examples) >= 2:
                        break

                    # Get the English text (without the span and img tags)
                    eng_text = eng_ex.get_text(strip=True)

                    # The Russian translation is in the next p tag with class 'ex_t human'
                    rus_ex = eng_ex.find_next("p", class_="ex_t human")
                    rus_text = rus_ex.get_text(strip=True)

                    examples.append(eng_text)
                    ex_translations.append(rus_text)

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
        # TODO change 100
        for i, word in enumerate(words[:100], 1):
            print(f"Processing {i}/{len(words)}: {word}")
            word_data = self.parse_word_data(word)
            if word_data:
                results.append(word_data)

        self.save_to_csv(results)
