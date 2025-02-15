import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys
    FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

    # Flask Configuration
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'

    # Security
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

    # Host Configuration
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))

class ProductionConfig(Config):
    DEBUG = False

class DevelopmentConfig(Config):
    DEBUG = True