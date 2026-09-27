import sys
import os

# Add parent directory to sys.path so 'backend' module is found on Vercel
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.main import app
