import os
import time
import random
import csv
import requests
from bs4 import BeautifulSoup
import cloudscraper
from fake_useragent import UserAgent


class WordParser:
    """A class for parsing word definitions from Yandex Dictionary API and examples from Reverso Context."""

    YANDEX_DICT_URL = "https://dictionary.yandex.net/api/v1/dicservice.json/lookup"
    REVERSO_API_URL = "https://context.reverso.net/translation/english-russian/{}"

    def __init__(
        self, data_dir: str, yandex_api_key: str = None, num_examples: int = 5
    ):
        """Initialize the parser with output directory configuration and API keys.

        Args:
            data_dir (str): Base directory for output files
            yandex_api_key (str, optional): Yandex Dictionary API key for translations
            num_examples (int, optional): Number of examples to extract for each word. Defaults to 5
        """
        self.outputs_dir = os.path.join(data_dir, "outputs")
        os.makedirs(self.outputs_dir, exist_ok=True)

        self.output_file = os.path.join(self.outputs_dir, "word_data.csv")
        self.not_found_file = os.path.join(self.outputs_dir, "not_found_words.txt")

        self.user_agent = UserAgent()
        self.yandex_api_key = yandex_api_key
        self.num_examples = num_examples

        # Define consistent fieldnames for CSV
        self.fieldnames = ["word", "transcription", "translations"]
        for i in range(1, self.num_examples + 1):
            self.fieldnames.extend([f"eng_example{i}", f"rus_example{i}"])

    def _initialize_empty_word_data(self, word: str) -> dict:
        """Create a dictionary with all expected fields initialized to empty strings.

        Args:
            word (str): The word to include in the data

        Returns:
            dict: Dictionary with all possible fields initialized
        """
        data = {"word": word, "transcription": "", "translations": ""}
        for i in range(1, self.num_examples + 1):
            data[f"eng_example{i}"] = ""
            data[f"rus_example{i}"] = ""
        return data

    def _fetch_from_url(self, url: str) -> list:
        """Fetch word list from URL."""
        try:
            response = requests.get(url)
            response.raise_for_status()
            return [word.strip() for word in response.text.split("\n") if word.strip()]
        except requests.RequestException as e:
            print(f"Error fetching word list from URL: {e}")
            return []

    def _fetch_from_file(self, filepath: str) -> list:
        """Fetch word list from local file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except IOError as e:
            print(f"Error reading word list file: {e}")
            return []

    def fetch_word_list(self, source: str) -> list:
        """Fetch word list from either URL or local file."""
        if source.startswith(("http://", "https://")):
            return self._fetch_from_url(source)
        return self._fetch_from_file(source)

    def _log_not_found_word(self, word: str) -> None:
        """Log words that weren't found in any source."""
        try:
            with open(self.not_found_file, "a", encoding="utf-8") as f:
                f.write(f"{word}\n")
        except IOError as e:
            print(f"Error logging not found word {word}: {e}")

    def _get_yandex_response(self, word: str) -> requests.Response:
        """Fetch word data from Yandex Dictionary API."""
        if not self.yandex_api_key:
            print("Yandex API key not provided")
            return None

        params = {"key": self.yandex_api_key, "lang": "en-ru", "text": word}

        try:
            response = requests.get(self.YANDEX_DICT_URL, params=params)
            response.raise_for_status()
            return response
        except (requests.RequestException, ValueError) as e:
            print(f"Error fetching data from Yandex API for '{word}': {e}")
            return None

    def _parse_yandex_response(self, response: requests.Response, word: str) -> dict:
        """Parse translations from Yandex Dictionary API response."""
        if not response:
            return None

        try:
            data = response.json()
        except ValueError as e:
            print(f"Error parsing Yandex response JSON for '{word}': {e}")
            return None

        # Check if no definitions were found
        if not data or "def" not in data or not data["def"]:
            print(f"No definitions found for '{word}' in Yandex Dictionary")
            return None

        # Initialize result with empty values
        result = {"transcription": "", "translations": []}

        # Get transcription if available
        if "ts" in data["def"][0]:
            transcription = data["def"][0]["ts"]
            result["transcription"] = f"[{transcription}]" if transcription else ""

        # Get translations
        translations = []
        for definition in data["def"]:
            if "tr" in definition:
                for tr in definition["tr"]:
                    if "text" in tr:
                        translations.append(tr["text"])

        if translations:
            result["translations"] = translations

        return result if (result["transcription"] or result["translations"]) else None

    def _get_reverso_response(self, word: str, retries: int = 5) -> requests.Response:
        """Fetch examples from Reverso Context."""
        scraper = cloudscraper.create_scraper(
            browser={"custom": self.user_agent.random}
        )
        url = self.REVERSO_API_URL.format(word)

        for attempt in range(retries):
            try:
                response = scraper.get(url)
                response.raise_for_status()
                return response
            except (requests.RequestException, ValueError) as e:
                print(
                    f"Error fetching data from Reverso Context for '{word}' (attempt {attempt + 1}): {e}"
                )
                time.sleep(3)

        print(
            f"Failed to fetch data from Reverso Context for '{word}' after {retries} attempts."
        )
        return None

    def _parse_reverso_response(self, response: requests.Response, word: str) -> dict:
        """Parse examples from Reverso Context response."""
        if not response:
            return None

        try:
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"Error parsing Reverso HTML for '{word}': {e}")
            return None

        # Initialize result with empty values
        result = {
            "transcription": "",
            "translations": [],
            "eng_examples": [],
            "rus_examples": [],
        }

        # Transcription extraction
        transcription_block = soup.select_one("#transliteration-content .ipa")
        if transcription_block:
            transcription = transcription_block.text.strip("/").strip()
            result["transcription"] = f"[{transcription}]" if transcription else ""

        # Translation extraction
        translation_block = soup.find("div", id="translations-content")
        if translation_block:
            for translation in translation_block.find_all("a", class_="translation"):
                display_term = translation.find("span", class_="display-term")
                if display_term:
                    result["translations"].append(display_term.get_text(strip=True))

        # Example extraction
        examples_section = soup.find("section", id="examples-content")
        if examples_section:
            eng_examples = []
            rus_examples = []

            for example in examples_section.find_all("div", class_="example"):
                src = example.find("div", class_="src")
                trg = example.find("div", class_="trg")
                if src and trg:
                    eng_examples.append(
                        src.get_text(strip=False).strip().replace('"', "'")
                    )
                    rus_examples.append(
                        trg.get_text(strip=False).strip().replace('"', "'")
                    )

            if len(eng_examples) > self.num_examples:
                indices = random.sample(range(len(eng_examples)), self.num_examples)
                result["eng_examples"] = [eng_examples[i] for i in indices]
                result["rus_examples"] = [rus_examples[i] for i in indices]

        # If we got at least one piece of data, return it
        if any(
            [
                result["transcription"],
                result["translations"],
                result["eng_examples"],
                result["rus_examples"],
            ]
        ):
            return result

        return None

    def parse_word_data(self, word: str) -> dict:
        """Parse word data from Yandex Dictionary API and examples from Reverso Context.

        Returns:
            A dictionary containing all fields (initialized to empty strings if no data found)
            with structure matching self.fieldnames.
        """
        # Start with a complete empty dataset
        parsed_data = self._initialize_empty_word_data(word)
        found_data = False

        # Try Yandex Dictionary first
        yandex_response = self._get_yandex_response(word)
        yandex_data = self._parse_yandex_response(yandex_response, word)

        if yandex_data:
            found_data = True
            if "transcription" in yandex_data:
                parsed_data["transcription"] = yandex_data["transcription"]
            if "translations" in yandex_data and yandex_data["translations"]:
                parsed_data["translations"] = ", ".join(yandex_data["translations"])

        # Try Reverso Context for examples and fallback translations
        reverso_response = self._get_reverso_response(word)
        reverso_data = self._parse_reverso_response(reverso_response, word)

        if reverso_data:
            found_data = True
            # Only update fields if we didn't get them from Yandex or if Reverso has better data
            if not parsed_data["transcription"] and "transcription" in reverso_data:
                parsed_data["transcription"] = reverso_data["transcription"]
            if (
                not parsed_data["translations"]
                and "translations" in reverso_data
                and reverso_data["translations"]
            ):
                parsed_data["translations"] = ", ".join(reverso_data["translations"])

            # Add examples if available
            for i, (eng, rus) in enumerate(
                zip(
                    reverso_data.get("eng_examples", []),
                    reverso_data.get("rus_examples", []),
                )
            ):
                if i < self.num_examples:
                    parsed_data[f"eng_example{i + 1}"] = eng
                    parsed_data[f"rus_example{i + 1}"] = rus

        if not found_data:
            self._log_not_found_word(word)
            print(f"No data found for word: '{word}'")
            return None

        return parsed_data

    def _get_next_file_number(self) -> int:
        """Find the next available file number by checking existing files."""
        base_name = os.path.splitext(os.path.basename(self.output_file))[0]
        existing_files = []

        try:
            for filename in os.listdir(self.outputs_dir):
                if filename.startswith(f"{base_name}_") and filename.endswith(".csv"):
                    try:
                        num = int(
                            filename.replace(f"{base_name}_", "").replace(".csv", "")
                        )
                        existing_files.append(num)
                    except ValueError:
                        continue
            return max(existing_files, default=0) + 1
        except OSError:
            return 1

    def _get_csv_filename(self, file_number: int = None) -> str:
        """Generate CSV filename with a numeric index."""
        base_name = os.path.splitext(os.path.basename(self.output_file))[0]
        if file_number is None:
            file_number = self._get_next_file_number()
        return os.path.join(self.outputs_dir, f"{base_name}_{file_number}.csv")

    def _write_batch_to_csv(self, batch_data: list, batch_number: int) -> bool:
        """Write a batch of words to a CSV file."""
        if not batch_data:
            return False

        try:
            output_file = self._get_csv_filename(batch_number)

            with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(
                    csvfile,
                    fieldnames=self.fieldnames,
                    delimiter=";",
                    quotechar='"',
                    quoting=csv.QUOTE_ALL,
                )
                writer.writerows(batch_data)

            print(f"Batch {batch_number} saved to {output_file}")
            return True
        except IOError as e:
            print(f"Error writing batch {batch_number} to CSV file: {e}")
            return False

    def parse(
        self,
        source: str,
        max_words: int = None,
        start_index: int = 0,
        words_per_file: int = 1000,
    ) -> None:
        """Main method to process all words."""
        words = self.fetch_word_list(source)
        if not words:
            print("No words to process.")
            return

        # Validate and adjust start_index
        if start_index < 0:
            print("Start index cannot be negative. Starting from beginning.")
            start_index = 0
        elif start_index >= len(words):
            print("Start index exceeds word list length. Starting from beginning.")
            start_index = 0

        # Apply both max_words and start_index limits
        words = words[start_index:max_words] if max_words else words[start_index:]
        print(
            f"Found {len(words)} words to process starting from index {start_index}..."
        )

        current_batch = []
        processed_count = 0
        batch_number = self._get_next_file_number()

        for i, word in enumerate(words, start_index + 1):
            print(f"Processing {i - start_index}/{len(words)}: '{word}'")
            word_data = self.parse_word_data(word)

            if word_data:
                current_batch.append(word_data)
                processed_count += 1

                # Write batch when we reach words_per_file limit
                if len(current_batch) >= words_per_file:
                    self._write_batch_to_csv(current_batch, batch_number)
                    current_batch = []
                    batch_number += 1

        # Write any remaining words
        if current_batch:
            self._write_batch_to_csv(current_batch, batch_number)

        print(f"Processing completed. {processed_count} words processed successfully.")
