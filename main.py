"""Backwards-compatible entry point: ``python main.py IN OUT [options]``."""

from training_log_change.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
