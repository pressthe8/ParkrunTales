import os
import logging
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import markdown2
import google.generativeai as genai

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

        # Call Firecrawl API to scrape the page
        firecrawl_url = "https://firecrawl.dev/api/scrape"
        headers = {
            'Authorization': f'Bearer {os.getenv("FIRECRAWL_API_KEY")}',
            'Content-Type': 'application/json'
        }
        payload = {
            'url': parkrun_url,
            'selector': 'body'  # Adding selector to get the full content
        }

        logger.debug(f"Making request to Firecrawl API: {firecrawl_url}")
        response = requests.post(firecrawl_url, headers=headers, json=payload)

        if response.status_code != 200:
            logger.error(f"Firecrawl API error: Status {response.status_code}, Response: {response.text}")
            return render_template('index.html', error=f"Error fetching runner data: {response.text}"), 500

        markdown_data = response.text
        logger.debug(f"Received markdown data: {markdown_data[:200]}...")

        # Generate story prompt
        prompt = f"""Using the following Markdown data, create a lighthearted and fun short story (2-3 paragraphs) about the parkrun journey of the runner. The story should be in the third person, include a notable news event from the week of their first parkrun, highlight key stats (total runs, best time), and mention a few locations they have visited. Add some playful running-related puns but keep it engaging and concise.

        {markdown_data}"""

        # Generate story using Gemini
        response = model.generate_content(prompt)
        story = response.text

        return render_template('story.html', story=story)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from Firecrawl: {str(e)}")
        return render_template('index.html', error=f"Error fetching runner data: {str(e)}"), 500
    except Exception as e:
        logger.error(f"Error generating story: {str(e)}")
        return render_template('index.html', error=f"Error generating story: {str(e)}"), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('index.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('index.html', error="Internal server error"), 500