import logging
import os
import sys
from pathlib import Path

_LOG_FILE = Path(__file__).parents[3] / "logs" / "server.log"


def configure_logging(level: int | None = None) -> None:
    if level is None:
        env = os.environ.get("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env, logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(fmt)

    _LOG_FILE.parent.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(_LOG_FILE)
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.handlers = [stderr_handler, file_handler]
    root.setLevel(level)

    # Undo fileConfig(disable_existing_loggers=True) side-effects so all
    # app loggers can propagate records up to the root handlers above.
    for name, lgr in logging.Logger.manager.loggerDict.items():
        if isinstance(lgr, logging.Logger) and (name == "app" or name.startswith("app.")):
            lgr.disabled = False
            lgr.handlers = []
            lgr.propagate = True
