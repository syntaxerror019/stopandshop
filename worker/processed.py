import json
from worker.config import PROCESSED_FILE


def load_processed():
    """
    Load the set of email IDs that have already been processed.
    """

    if not PROCESSED_FILE.exists():
        return set()

    try:
        with open(PROCESSED_FILE, "r") as f:
            return set(json.load(f))

    except Exception:
        print("Warning: Could not read processed email file.")
        return set()


def save_processed(processed):
    """
    Save processed email IDs to disk.
    """

    with open(PROCESSED_FILE, "w") as f:
        json.dump(
            list(processed),
            f,
            indent=2
        )
