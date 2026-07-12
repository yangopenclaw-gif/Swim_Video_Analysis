import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ['STAGING_MODE'] = '1'
os.environ['STAGING_DIR'] = os.path.dirname(os.path.abspath(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from backend.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)