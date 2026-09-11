import sys
import os

# Ensure root is on path so all `services.*` and `packages.*` imports resolve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
