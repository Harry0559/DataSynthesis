"""Post-processor 管线层"""

from __future__ import annotations

from .loader import create_input_source
from .runner import run_postprocessor
from .writer import Writer

__all__ = ["create_input_source", "run_postprocessor", "Writer"]
