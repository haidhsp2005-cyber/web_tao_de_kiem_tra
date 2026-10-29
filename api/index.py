import os
import sys
import tempfile

# Ensure matplotlib and temp caches use writable /tmp in serverless environments
os.environ["MPLCONFIGDIR"] = "/tmp/.matplotlib" if os.name != "nt" else os.path.join(tempfile.gettempdir(), ".matplotlib")

# Ensure repository root is on sys.path so 'app' can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.main import app

# For local testing or ASGI server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
