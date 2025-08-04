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
        self.output_file = os.path.join(self.outputs_dir, "word_data.csv")
        self.not_found_file = os.path.join(self.outputs_dir, "not_found_words.txt")

        self.user_agent = UserAgent()
        self.yandex_api_key = yandex_api_key

        self.num_examples = num_examples

    def _fetch_from_url(self, url: str) -> list:
        """Fetch word list from URL.

        Args:
            url (str): URL to fetch words from

        Returns:
            list: List of words
        """
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return [word.strip() for word in response.text.split("\n") if word.strip()]
        except requests.RequestException as e:
            print(f"Error fetching word list from URL: {e}")
            return []

    def _fetch_from_file(self, filepath: str) -> list:
        """Fetch word list from local file.

        Args:
            filepath (str): Path to local file

        Returns:
            list: List of words
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except IOError as e:
            print(f"Error reading word list file: {e}")
            return []

    def fetch_word_list(self, source: str) -> list:
        """Fetch word list from either URL or local file.

        Args:
            source (str): URL or file path to fetch words from

        Returns:
            list: List of words
        """
        if source.startswith(("http://", "https://")):
            return self._fetch_from_url(source)
        return self._fetch_from_file(source)

    def _log_not_found_word(self, word: str) -> None:
        """Log words that weren't found in any source.

        Args:
            word (str): The word that wasn't found
        """
        try:
            with open(self.not_found_file, "a", encoding="utf-8") as f:
                f.write(f"{word}\n")
        except IOError as e:
            print(f"Error logging not found word {word}: {e}")

    def _get_yandex_response(self, word: str) -> requests.Response:
        """Fetch word data from Yandex Dictionary API.

        Args:
            word (str): Word to look up

        Returns:
            requests.Response: API response data or None if failed
        """
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
        """Parse translations from Yandex Dictionary API response.

        Args:
            response (requests.Response): API response data from Yandex Dictionary
            word (str): The word that was looked up

        Returns:
            dict: Parsed word data or None if invalid
        """
        if not response:
            return None

        data = response.json()

        # Check if no definitions were found
        if not data or "def" not in data or not data["def"]:
            print(f"No definitions found for '{word}' in Yandex Dictionary")
            return None

        transcription = data["def"][0]
        transcription = transcription.get("ts", "")
        transcription = f"[{transcription}]" if transcription else ""

        translations = []
        for definition in data["def"]:
            if "tr" in definition:
                for tr in definition["tr"]:
                    translations.append(tr.get("text", ""))

        if not translations:
            return None

        # Only include transcription and translations
        result = {
            "transcription": transcription,
            "translations": translations,
        }

        return result

    def _get_reverso_response(self, word: str, retries: int = 5) -> requests.Response:
        """Fetch examples from Reverso Context.

        Args:
            word (str): Word to look up examples for

        Returns:
            requests.Response: Response or None if failed
        """

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
                print(f"Error fetching data from Reverso Context for '{word}': {e}")

            print(f"Attempt {attempt + 1} of {retries} failed. Retrying...")
            time.sleep(3)

        print(
            f"Failed to fetch data from Reverso Context for '{word}' after {retries} attempts."
        )
        return None

    def _parse_reverso_response(self, response: requests.Response, word: str) -> dict:
        """Parse examples from Reverso Context response.

        Args:
            response (requests.Response): Response data from Reverso Context
            word (str): The word that was looked up

        Returns:
            dict: Parsed data or None if invalid
        """
        if not response:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Transcription extraction
        transcription_block = soup.select_one("#transliteration-content .ipa")
        if transcription_block:
            transcription = transcription_block.text.strip("/").strip()
            transcription = f"[{transcription}]" if transcription else ""
        else:
            transcription = ""

        # Translation extraction
        translations = []
        translation_block = soup.find("div", id="translations-content")
        if translation_block:
            for translation in translation_block.find_all("a", class_="translation"):
                # Get just the display term, excluding any gender markers
                display_term = translation.find("span", class_="display-term")
                if display_term:
                    translations.append(display_term.get_text(strip=True))

        # Example extraction
        eng_examples = []
        rus_examples = []

        examples_section = soup.find("section", id="examples-content")
        if examples_section:
            for example in examples_section.find_all("div", class_="example"):
                eng_example = (
                    example.find("div", class_="src").get_text(strip=False).strip()
                )
                rus_example = (
                    example.find("div", class_="trg").get_text(strip=False).strip()
                )
                eng_examples.append(eng_example)
                rus_examples.append(rus_example)

        # If no examples found print a warning
        if not eng_examples and not rus_examples:
            print(f"No examples found for '{word}' in Reverso Context")
            if not translations and not transcription:
                return None

        # Randomly select up to self.num_examples if we have more
        if len(eng_examples) > self.num_examples:
            indices = random.sample(range(len(eng_examples)), self.num_examples)
            eng_examples = [eng_examples[i] for i in indices]
            rus_examples = [rus_examples[i] for i in indices]

        # Pad with empty strings if needed
        while len(eng_examples) < self.num_examples:
            eng_examples.append("")
        while len(rus_examples) < self.num_examples:
            rus_examples.append("")

        result = {
            "transcription": transcription,
            "translations": translations,
            "eng_examples": eng_examples,
            "rus_examples": rus_examples,
        }

        return result

    def parse_word_data(self, word: str) -> dict | None:
        """Parse word data from Yandex Dictionary API and examples from Reverso Context.

        Args:
            word: The word to look up and parse data for.

        Returns:
            A dictionary containing the parsed word data with structure:
            {
                "word": str,
                "transcription": str,
                "translations": str,  # semicolon-separated
                "eng_example1": str,  # example sentences
                "rus_example1": str,
                ...
            }
            Returns None if the word wasn't found in either source.
        """
        parsed_data = {"word": word}

        # Try Yandex Dictionary first
        yandex_data = self._parse_yandex_response(self._get_yandex_response(word), word)
        if yandex_data:
            parsed_data.update(
                {
                    "transcription": yandex_data.get("transcription", ""),
                    "translations": ", ".join(yandex_data.get("translations", [])),
                }
            )

        # Try Reverso Context for examples and fallback translations
        reverso_data = self._parse_reverso_response(
            self._get_reverso_response(word), word
        )
        if reverso_data:
            if not yandex_data:
                parsed_data["transcription"] = reverso_data.get("transcription", "")
                parsed_data["translations"] = ", ".join(
                    reverso_data.get("translations", [])
                )

            # Add examples if available
            for i, (eng, rus) in enumerate(
                zip(
                    reverso_data.get("eng_examples", []),
                    reverso_data.get("rus_examples", []),
                ),
                1,
            ):
                parsed_data[f"eng_example{i}"] = eng
                parsed_data[f"rus_example{i}"] = rus

        # Return None if no data was found
        if not yandex_data and not reverso_data:
            self._log_not_found_word(word)
            print(f"No data found for word: '{word}'")
            return None

        return parsed_data

    def _get_next_file_number(self) -> int:
        """Find the next available file number by checking existing files.

        Returns:
            int: Next available file number
        """
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
        """Generate CSV filename with a numeric index.
        If file_number is None, finds the next available number by checking existing files.

        Args:
            file_number (int, optional): The number for the file. If None,
                                       automatically determines the next number.

        Returns:
            str: The full path of the CSV file
        """
        base_name = os.path.splitext(os.path.basename(self.output_file))[0]
        if file_number is None:
            file_number = self._get_next_file_number()

        return os.path.join(self.outputs_dir, f"{base_name}_{file_number}.csv")

    def _write_batch_to_csv(self, batch_data: list, batch_number: int) -> bool:
        """Write a batch of words to a CSV file.

        Args:
            batch_data (list): List of word data to write
            batch_number (int): Batch number for the filename

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            output_file = self._get_csv_filename(batch_number)
            with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(
                    csvfile,
                    fieldnames=list(batch_data[0].keys()),
                    delimiter=";",
                    quotechar='"',
                    quoting=csv.QUOTE_ALL,
                )
                for item in batch_data:
                    writer.writerow(item)
            print(f"File {batch_number} saved to {output_file}")
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
        """Main method to process all words.

        Args:
            source (str): Source of words (URL or file path)
            max_words (int): Number of words to process, if None process all
            start_index (int): Index to start processing from (0-based)
            words_per_file (int): Number of words per CSV file
        """
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

        # Apply both max_words and start_index limits in one slice
        words = words[start_index:max_words] if max_words else words[start_index:]
        print(
            f"Found {len(words)} words to process starting from index {start_index}..."
        )

        current_batch = []
        processed_count = 0

        # Get the starting file number based on existing files
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
