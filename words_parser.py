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

    def __init__(self, data_dir: str):
        """Initialize the parser with output directory configuration.

        Args:
            data_dir (str): Base directory for output files
        """
        self.outputs_dir = os.path.join(data_dir, "outputs")
        self.output_file = os.path.join(self.outputs_dir, "word_hunt_data.csv")
        self.headers = {"User-Agent": self.USER_AGENT}

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
        if "К сожалению" in soup.text or "В тексте песен" in soup.text:
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

    def _extract_examples(self, example_block) -> tuple[list, list]:
        """Extract examples and their translations.

        Args:
            example_block: BeautifulSoup element containing examples

        Returns:
            tuple: Lists of examples and their translations
        """
        examples = []
        ex_translations = []

        if example_block:
            english_examples = example_block.find_all("p", class_="ex_o")
            for eng_ex in english_examples:
                if len(examples) >= 2:
                    break

                eng_text = eng_ex.get_text(strip=True)
                rus_ex = eng_ex.find_next("p", class_="ex_t human")
                rus_text = rus_ex.get_text(strip=True)

                examples.append(eng_text)
                ex_translations.append(rus_text)

        # Pad with empty strings if needed
        while len(examples) < 2:
            examples.append("")
        while len(ex_translations) < 2:
            ex_translations.append("")

        return examples, ex_translations

    def parse_word_data(self, word: str) -> dict:
        """Parse WoordHunt data for a single word.

        Args:
            word (str): Word to parse data for

        Returns:
            dict: Parsed word data or None if failed
        """
        soup = self._fetch_page_content(word)
        if not soup or not self._is_word_exists(soup, word):
            return None

        # Get transcription
        transcription = ""
        trans_block = soup.find("div", class_="trans_sound")
        if trans_block:
            transcription = self.extract_transcription(trans_block)

        # Get translation
        translation = self._extract_translation(soup, word)
        if not translation:
            return None

        # Get examples
        example_block = self._get_example_block(soup)
        examples, ex_translations = self._extract_examples(example_block)

        return {
            "word": word,
            "transcription": transcription,
            "translation": translation,
            "example1": examples[0],
            "ex_translation1": ex_translations[0],
            "example2": examples[1],
            "ex_translation2": ex_translations[1],
        }

    def _get_csv_fieldnames(self) -> list:
        """Get the list of CSV field names.

        Returns:
            list: List of field names for CSV
        """
        return [
            "word",
            "transcription",
            "translation",
            "example1",
            "ex_translation1",
            "example2",
            "ex_translation2",
        ]

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

    def save_to_csv(self, data: list, words_per_file: int = 1000) -> bool:
        """Save parsed data to CSV files, splitting into batches.

        Args:
            data (list): List of dictionaries containing word data
            words_per_file (int): Number of words per CSV file

        Returns:
            bool: True if save was successful, False otherwise
        """
        if not data:
            print("No data to save")
            return False

        try:
            for i in range(0, len(data), words_per_file):
                batch_number = (i // words_per_file) + 1
                batch_data = data[i : i + words_per_file]
                output_file = self._get_csv_filename(batch_number)

                with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
                    writer = csv.DictWriter(
                        csvfile,
                        fieldnames=self._get_csv_fieldnames(),
                        delimiter=";",
                        quotechar='"',
                        quoting=csv.QUOTE_ALL,
                    )
                    writer.writeheader()
                    for item in batch_data:
                        if item:  # Only write if data exists
                            writer.writerow(item)
                print(f"File {batch_number} saved to {output_file}")
            return True
        except IOError as e:
            print(f"Error writing to CSV file: {e}")
            return False

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
                    fieldnames=self._get_csv_fieldnames(),
                    delimiter=";",
                    quotechar='"',
                    quoting=csv.QUOTE_ALL,
                )
                writer.writeheader()
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

        words = words[start_index:]
        total_words = len(words)
        print(
            f"Found {total_words} words to process starting from index {start_index}..."
        )

        current_batch = []
        processed_count = 0

        # Get the starting file number based on existing files
        batch_number = self._get_next_file_number()

        # Process all words or up to max_words if specified
        word_batch = words[:max_words] if max_words else words

        for i, word in enumerate(word_batch, start_index + 1):
            print(f"Processing {i}/{total_words}: {word}")
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
