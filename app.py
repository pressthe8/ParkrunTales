import os
import logging
from flask import Flask, render_template, request
from dotenv import load_dotenv
import google.generativeai as genai
from firecrawl import FirecrawlApp

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default-secret-key")

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

# Configure Firecrawl
firecrawl = FirecrawlApp(api_key=os.getenv('FIRECRAWL_API_KEY'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_story', methods=['POST'])
def generate_story():
    athlete_id = request.form.get('athlete_id')

    if not athlete_id:
        return render_template('index.html', error='Athlete ID is required'), 400

    try:
        # Remove 'A' prefix if present and format the Parkrun URL
        numeric_id = athlete_id.lstrip('A')
        parkrun_url = f"https://www.parkrun.org.uk/parkrunner/{numeric_id}/all/"

        logger.debug(f"Attempting to scrape URL: {parkrun_url}")

        # Use Firecrawl Python client to scrape the page
        response = firecrawl.scrape_url(
            url=parkrun_url,
            params={
                'formats': ['markdown']
            }
        )

        if not response or not response.text:
            logger.error("No data received from Firecrawl")
            return render_template('index.html', error="Could not fetch runner data"), 500

        markdown_data = response.text
        logger.debug(f"Received markdown data: {markdown_data[:200]}...")

        # Generate story prompt
        prompt = f"""Using the following Markdown data, create a lighthearted and fun short story (2-3 paragraphs) about the parkrun journey of the runner. The story should be in the third person, include a notable news event from the week of their first parkrun, highlight key stats (total runs, best time), and mention a few locations they have visited. Add some playful running-related puns but keep it engaging and concise.

        {markdown_data}"""

        # Generate story using Gemini
        response = model.generate_content(prompt)
        story = response.text

        return render_template('story.html', story=story)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return render_template('index.html', error=f"Error: {str(e)}"), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('index.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('index.html', error="Internal server error"), 500