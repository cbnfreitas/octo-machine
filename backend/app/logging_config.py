import logging

for _name in ("uvicorn", "uvicorn.error"):
    logging.getLogger(_name).setLevel(logging.INFO)

logger = logging.getLogger("uvicorn")


def yellow_tool(name: str) -> str:
    return f"\033[33m{name}\033[0m"
