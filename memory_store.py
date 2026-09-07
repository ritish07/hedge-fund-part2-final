"""Durable append-only memory for broker-confirmed trade executions."""

import json
from pathlib import Path


MEMORY_FILE = Path(__file__).with_name("memory.json")


def append_trade_memory(record):
    """Append a JSON-serializable confirmed-trade record to disk atomically."""

    if MEMORY_FILE.exists():
        with MEMORY_FILE.open("r", encoding="utf-8") as memory_file:
            history = json.load(memory_file)
        if not isinstance(history, list):
            raise ValueError("memory.json must contain a JSON array")
    else:
        history = []

    history.append(record)
    temporary_file = MEMORY_FILE.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as memory_file:
        json.dump(history, memory_file, indent=2)
        memory_file.write("\n")

    temporary_file.replace(MEMORY_FILE)
