import sys
from pathlib import Path

# Makes `import goTag...` work in tests without installing the package --
# points Python at src/ directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
