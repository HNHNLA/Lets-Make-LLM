import json
import os

class DatasetLoader:
    def __init__(self, file_path):
        # Store the JSONL dataset path.
        self.file_path = file_path

    def load_data(self):
        # Validate the dataset path before reading it.
        if not self.file_path or not os.path.isfile(self.file_path):
            raise FileNotFoundError(f"Dataset file not found: {self.file_path}")

        data = []
        try:
            # Ignore invalid UTF-8 byte sequences while preserving JSON errors for review.
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as stream:
                for line_number, line in enumerate(stream, start=1):
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Invalid JSON on line {line_number}: {exc}"
                        ) from exc
                    if not isinstance(item, dict):
                        raise ValueError(
                            f"JSONL line {line_number} must contain an object."
                        )
                    data.append(item)
        except OSError as exc:
            raise IOError(f"Could not read dataset {self.file_path}: {exc}") from exc

        if not data:
            raise ValueError("The dataset contains no JSON objects.")
        return data

def remove_replacement_characters(value):
    # Remove Unicode replacement characters from strings, including nested JSON values.
    if isinstance(value, str):
        return value.replace("\ufffd", "")
    if isinstance(value, list):
        return [remove_replacement_characters(item) for item in value]
    if isinstance(value, dict):
        return {
            remove_replacement_characters(key): remove_replacement_characters(item)
            for key, item in value.items()
        }
    return value


def write_cleaned_jsonl(raw_data, output_path):
    # Persist cleaned JSONL so every later stage uses the same data.
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cleaned_data = [remove_replacement_characters(row) for row in raw_data]
    with open(output_path, "w", encoding="utf-8", newline="\n") as stream:
        for row in cleaned_data:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return cleaned_data
