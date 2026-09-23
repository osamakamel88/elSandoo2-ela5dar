import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.config import config
from app.utils.logging_utils import configure_terminal_logger


def __init_logger():
    # _log_file = utils.storage_dir("logs/server.log")
    _lvl = config.log_level

    configure_terminal_logger(
        sys.stdout,
        level=_lvl,
        colorize=True,
    )

    # logger.add(
    #     _log_file,
    #     level=_lvl,
    #     format=format_log_record,
    #     rotation="00:00",
    #     retention="3 days",
    #     backtrace=True,
    #     diagnose=True,
    #     enqueue=True,
    # )


__init_logger()
