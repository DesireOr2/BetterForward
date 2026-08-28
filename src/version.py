"""Application version metadata.

CI injects the git tag via Docker build-arg into BETTERFORWARD_VERSION.
Local/dev runs fall back to \"dev\".
"""

import os

VERSION = (os.environ.get("BETTERFORWARD_VERSION") or os.environ.get("VERSION") or "dev").strip() or "dev"
