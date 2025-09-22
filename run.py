import uvicorn
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

if __name__ == "__main__":
    # Run the FastAPI application with uvicorn
    uvicorn.run(
        "api.news:app",
        host="127.0.0.1",
        port=8000,
        reload=False
    )