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
        return jsonify({'error': 'Athlete ID is required'}), 400
    
    try:
        # Call Firecrawl API
        firecrawl_url = f"https://firecrawl.dev/api/athlete/{athlete_id}"
        headers = {
            'Authorization': f'Bearer {os.getenv("FIRECRAWL_API_KEY")}'
        }
        response = requests.get(firecrawl_url, headers=headers)
        response.raise_for_status()
        
        markdown_data = response.text
        
        # Generate story prompt
        prompt = f"""Using the following Markdown data, create a lighthearted and fun short story (2-3 paragraphs) about the parkrun journey of the runner. The story should be in the third person, include a notable news event from the week of their first parkrun, highlight key stats (total runs, best time), and mention a few locations they have visited. Add some playful running-related puns but keep it engaging and concise.

        {markdown_data}"""
        
        # Generate story using Gemini
        response = model.generate_content(prompt)
        story = response.text
        
        return render_template('story.html', story=story)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from Firecrawl: {str(e)}")
        return jsonify({'error': 'Error fetching runner data'}), 500
    except Exception as e:
        logger.error(f"Error generating story: {str(e)}")
        return jsonify({'error': 'Error generating story'}), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('index.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('index.html', error="Internal server error"), 500
