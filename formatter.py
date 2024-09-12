import os

import json
import csv


class RewordFormatter:
    def __init__(self,
                 data_dir: str,
                 max_words: int = None,
                 max_examples: int = 6) -> None:
        # Paths
        self.inputs_dir = os.path.join(data_dir, "inputs")
        self.outputs_dir = os.path.join(data_dir, "outputs")

        # Limitations
        self.max_words = max_words
        self.max_examples = max_examples

        self.__rows_names = None

    @property
    def rows_names(self) -> list[str]:
        if self.__rows_names == None:
            rows_names = ["word", "transcription", "translation"]

            for i in range(1, self.max_examples + 1):
                rows_names.append(f"example{i}")
                rows_names.append(f"ex.translation{i}")

            self.__rows_names = rows_names

        return self.__rows_names

    @staticmethod
    def open_json(json_path: str) -> dict:
        with open(json_path, "r", encoding="utf-8") as file:
            json_dict = json.load(file)

        return json_dict

    def format_json(self, json_name: str) -> None:
        # Open json file and retriece dict
        json_path = os.path.join(self.inputs_dir, json_name)
        json_dict = RewordFormatter.open_json(json_path)

        # Open csv file and init writer
        csv_name = os.path.splitext(json_name)[0] + ".csv"
        csv_path = os.path.join(self.outputs_dir, csv_name)
        csv_file = open(csv_path, "a", encoding="utf-8", newline='')
        writer = csv.writer(csv_file, delimiter=";")

        # Counter for words
        counter = 0

        for eng_word in json_dict.keys():
            # Extract word data
            word_data = json_dict[eng_word]

            # Create row with data and add word to it
            row = []

            # English word
            row.append(eng_word)

            # Transcription
            transcription = ""
            row.append(transcription)

            # Translations
            translations = []
            trans_values = word_data.get("translations", dict()).values()

            # Add single translations to all translations
            for value in trans_values:
                for rus_word in value.keys():
                    translations.append(rus_word)

            translation = ", ".join(translations)
            row.append(translation)

            # Examples
            examples = word_data.get("examples", [])

            # Add example and example translation to row
            for example in examples[:self.max_examples]:
                row.append(example)
                transcription = ""
                row.append(transcription)

            # Write row
            writer.writerow(row)

            if self.max_words is not None:
                counter += 1

                if counter == self.max_words:
                    break

        csv_file.close()
