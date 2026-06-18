"""
HireVoice AI — entry point.

Run: python -m app.main
"""

from __future__ import annotations

import logging
import sys

from app.config import GRADIO_HOST, GRADIO_PORT, GRADIO_SHARE, MODE, ensure_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> None:
    ensure_dirs()
    logger.info("Starting HireVoice AI (mode=%s)", MODE)

    from ui.gradio_app import launch_app
    launch_app(
        server_name=GRADIO_HOST,
        server_port=GRADIO_PORT,
        share=GRADIO_SHARE,
    )


if __name__ == "__main__":
    main()