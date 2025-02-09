import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
