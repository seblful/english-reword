import os

import json
import csv


class RewordFormatter:
    def __init__(self,
                 data_dir: str) -> None:
        # Paths
        self.inputs_dir = os.path.join(data_dir, "inputs")
        self.outputs_dir = os.path.join(data_dir, "outputs")

    @staticmethod
    def open_json(json_path: str) -> dict:
        with open(json_path, "r", encoding="utf-8") as file:
            json_dict = json.load(file)

        return json_dict

    def format_json(self, json_name: str) -> None:
        json_path = os.path.join(self.inputs_dir(json_name))
