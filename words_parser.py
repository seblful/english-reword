import os
import csv
import tracemalloc
import requests
from bs4 import BeautifulSoup

tracemalloc.start()


class WordHuntParser:
    """A class for parsing word definitions and examples from WoordHunt website."""

    BASE_URL = "https://wooordhunt.ru/word/{}"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    YANDEX_DICT_URL = "https://dictionary.yandex.net/api/v1/dicservice.json/lookup"

    def __init__(self, data_dir: str, yandex_api_key: str = None):
        """Initialize the parser with output directory configuration and API key.

        Args:
            data_dir (str): Base directory for output files
            yandex_api_key (str, optional): Yandex Dictionary API key for fallback translations
        """
        self.outputs_dir = os.path.join(data_dir, "outputs")
        self.output_file = os.path.join(self.outputs_dir, "word_hunt_data.csv")
        self.headers = {"User-Agent": self.USER_AGENT}
        self.yandex_api_key = yandex_api_key

    def _fetch_yandex_data(self, word: str) -> dict:
        """Fetch word data from Yandex Dictionary API.

        Args:
            word (str): Word to look up

        Returns:
            dict: API response data or None if failed
        """
        if not self.yandex_api_key:
            print("Yandex API key not provided")
            return None

        params = {"key": self.yandex_api_key, "lang": "en-ru", "text": word}

        try:
            response = requests.get(self.YANDEX_DICT_URL, params=params)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as e:
            print(f"Error fetching data from Yandex API for {word}: {e}")
            return None

    def _parse_yandex_data(self, data: dict, word: str) -> dict:
        """Parse word data from Yandex Dictionary API response.

        Args:
            data (dict): API response data
            word (str): Original word

        Returns:
            dict: Parsed word data or None if invalid
        """
        if not data or "def" not in data or not data["def"]:
            return None

        translations = []
        eng_examples = []
        rus_examples = []

        for definition in data["def"]:
            # Get translations
            if "tr" in definition:
                for tr in definition["tr"]:
                    translations.append(tr.get("text", ""))

                    # Get examples if available
                    if "ex" in tr and len(eng_examples) < 5:
                        for ex in tr["ex"]:
                            if "text" in ex and "tr" in ex and len(eng_examples) < 5:
                                eng_examples.append(ex["text"])
                                rus_examples.append(ex["tr"][0]["text"])

        # Fill missing examples with empty strings
        while len(eng_examples) < 5:
            eng_examples.append("")
            rus_examples.append("")

        result = {
            "word": word,
            "transcription": definition.get("ts", ""),  # Get transcription if available
            "translation": ", ".join(translations),
        }

        # Add examples
        for i, (eng_example, rus_example) in enumerate(
            zip(eng_examples, rus_examples), 1
        ):
            result[f"eng_example{i}"] = eng_example
            result[f"rus_example{i}"] = rus_example

        return result

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

    def _format_transcription(self, text: str) -> str:
        """Format transcription by replacing pipes with brackets.

        Args:
            text (str): Raw transcription text

        Returns:
            str: Formatted transcription
        """
        parts = text.split("|")
        if len(parts) >= 3:
            return f"[{parts[1]}]"
        return text

    def _extract_pattern1_transcription(self, trans_block) -> str:
        """Extract transcription using pattern 1 (with "амер." marker).

        Args:
            trans_block: BeautifulSoup element containing transcription

        Returns:
            str: Extracted transcription or None
        """
        amer_div = trans_block.find("i", string="амер.")
        if not amer_div:
            return None

        trans_div = amer_div.find_parent("div", class_="trans_sound")
        if not trans_div:
            return None

        amer_section = amer_div.find_parent("div").find_next_sibling("div")
        if not amer_section:
            return None

        transcriptions = [
            self._format_transcription(span.get_text(strip=True))
            for span in amer_section.find_all("span", class_="transcription")
        ]
        return ", ".join(transcriptions) if transcriptions else None

    def _extract_pattern2_transcription(self, trans_block) -> str:
        """Extract transcription using pattern 2 (with us_tr_sound ID).

        Args:
            trans_block: BeautifulSoup element containing transcription

        Returns:
            str: Extracted transcription or None
        """
        us_div = trans_block.find("div", id="us_tr_sound")
        if not us_div:
            return None

        transcription = us_div.find("span", class_="transcription")
        if not transcription:
            return None

        return self._format_transcription(transcription.get_text(strip=True))

    def extract_transcription(self, trans_block) -> str:
        """Extract American English transcription from the page.

        Args:
            trans_block: BeautifulSoup element containing transcription

        Returns:
            str: Extracted transcription or None
        """
        return self._extract_pattern1_transcription(
            trans_block
        ) or self._extract_pattern2_transcription(trans_block)

    def _fetch_page_content(self, word: str) -> BeautifulSoup:
        """Fetch and parse the webpage for a given word.

        Args:
            word (str): Word to look up

        Returns:
            BeautifulSoup: Parsed page content or None if failed
        """
        url = self.BASE_URL.format(word.lower())
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            print(f"Error fetching data for {word}: {e}")
            return None

    def _is_word_exists(self, soup: BeautifulSoup, word: str) -> bool:
        """Check if the word exists in the dictionary.

        Args:
            soup (BeautifulSoup): Parsed page content
            word (str): Word being looked up

        Returns:
            bool: True if word exists, False otherwise
        """
        if (
            "Проверьте нет ли опечатки. Если такое слово существует, то мы постараемся это исправить."
            in soup.text
            or "В тексте песен:" in soup.text
        ):
            print(f"Word '{word}' not found in WoordHunt")
            return False
        return True

    def _extract_translation(self, soup: BeautifulSoup, word: str) -> str:
        """Extract word translation from the page.

        Args:
            soup (BeautifulSoup): Parsed page content
            word (str): Word being looked up

        Returns:
            str: Translation or None if not found
        """
        translation_block = soup.find("div", class_="t_inline_en")
        if not translation_block:
            print(f"Word '{word}' doesn't have a translation")
            return None
        return translation_block.text.strip()

    def _get_example_block(self, soup: BeautifulSoup):
        """Get the block containing usage examples.

        Args:
            soup (BeautifulSoup): Parsed page content

        Returns:
            element: BeautifulSoup element containing examples
        """
        return soup.find(
            lambda tag: tag.name == "div"
            and tag.get("class") == ["block"]
            and not tag.has_attr("id")
        )

    def _extract_examples(
        self, example_block, num_examples: int = 5
    ) -> tuple[list, list]:
        """Extract examples and their translations.

        Args:
            example_block: BeautifulSoup element containing examples
            num_examples (int): Number of examples to extract

        Returns:
            tuple: Lists of examples and their translations
        """
        eng_examples = []
        rus_examples = []

        if example_block:
            eng_example_blocks = example_block.find_all("p", class_="ex_o")
            for eng_example_block in eng_example_blocks:
                if len(eng_examples) >= num_examples:
                    break

                eng_example = eng_example_block.get_text(strip=True)
                rus_example_block = eng_example_block.find_next(
                    "p", class_="ex_t human"
                )

                # Only add the example if we have both English and Russian text
                if rus_example_block:
                    rus_example = rus_example_block.get_text(strip=True)

                    eng_examples.append(eng_example)
                    rus_examples.append(rus_example)

        # Pad with empty strings if needed
        while len(eng_examples) < num_examples:
            eng_examples.append("")
        while len(rus_examples) < num_examples:
            rus_examples.append("")

        return eng_examples, rus_examples

    def parse_word_data(self, word: str) -> dict:
        """Parse word data from WoordHunt or Yandex Dictionary API.

        Args:
            word (str): Word to parse data for

        Returns:
            dict: Parsed word data or None if failed from both sources
        """
        # Try WoordHunt first
        soup = self._fetch_page_content(word)
        if soup and self._is_word_exists(soup, word):
            # Get transcription
            transcription = ""
            trans_block = soup.find("div", class_="trans_sound")
            if trans_block:
                transcription = self.extract_transcription(trans_block)

            # Get translation
            translation = self._extract_translation(soup, word)
            if translation:
                # Get examples
                example_block = self._get_example_block(soup)
                eng_examples, rus_examples = self._extract_examples(example_block)

                examples_dict = {
                    "word": word,
                    "transcription": transcription,
                    "translation": translation,
                }
                for i, (eng_example, rus_example) in enumerate(
                    zip(eng_examples, rus_examples), 1
                ):
                    examples_dict[f"eng_example{i}"] = eng_example
                    examples_dict[f"rus_example{i}"] = rus_example

                return examples_dict

        # If WoordHunt fails, try Yandex API
        print(f"Falling back to Yandex API for word '{word}'")
        yandex_data = self._fetch_yandex_data(word)
        if yandex_data:
            return self._parse_yandex_data(yandex_data, word)

        return None

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
            print(f"Processing {i}/{len(words)}: {word}")
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
