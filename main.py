import sys

# Force UTF-8 on Windows consoles (cp1252 can't encode Spanish characters).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from clipsmith.cli import app

if __name__ == "__main__":
    app()
