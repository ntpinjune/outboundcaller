import traceback
import sys

try:
    print(f"Python version: {sys.version}")
    from langfuse import Langfuse
    print("Langfuse import successful")
except Exception:
    print("Langfuse import failed:")
    traceback.print_exc()
