"""I am letting the package run as a command: python -m workflow ..."""

from .cli import main

raise SystemExit(main())