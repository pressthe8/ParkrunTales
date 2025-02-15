import os
import logging
from flask import Flask, render_template, request, redirect, url_for, send_file
from dotenv import load_dotenv
import google.generativeai as genai
from firecrawl import FirecrawlApp
import firebase_admin
from firebase_admin import credentials, db
import secrets
import json
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import textwrap

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default-secret-key")

# Initialize Firebase
firebase_creds_json = os.environ.get('FIREBASE_CREDENTIALS')
if not firebase_creds_json:
    raise ValueError("Firebase credentials not found in environment variables")

cred = credentials.Certificate(json.loads(firebase_creds_json))
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://parkrun-story-default-rtdb.europe-west1.firebasedatabase.app/'
})

# Get a reference to the database
ref = db.reference('stories')

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

# Configure Firecrawl
firecrawl = FirecrawlApp(api_key=os.getenv('FIRECRAWL_API_KEY'))

def generate_url_hash():
    return secrets.token_hex(8)  # 16 character hash

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/story/<url_hash>')
def view_story(url_hash):
    try:
        # Get all stories and filter by url_hash
        stories = ref.get()
        if not stories:
            logger.debug("No stories found in database")
            return render_template('index.html', error="Story not found"), 404

        # Find the story with matching url_hash
        matching_story = None
        for story_id, story_data in stories.items():
            if story_data.get('url_hash') == url_hash:
                matching_story = story_data
                break

        if not matching_story:
            logger.debug(f"No story found with url_hash: {url_hash}")
            return render_template('index.html', error="Story not found"), 404

        return render_template('story.html', story=matching_story['content'], url_hash=url_hash)

    except Exception as e:
        logger.error(f"Error retrieving story: {str(e)}")
        return render_template('index.html', error="Error retrieving story"), 500

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

        logger.debug(f"Firecrawl response: {response}")

        if not response or not isinstance(response, dict) or 'markdown' not in response:
            logger.error("Invalid response format from Firecrawl")
            return render_template('index.html', error="Could not fetch runner data"), 500

        markdown_data = response['markdown']
        logger.debug(f"Received markdown data: {markdown_data[:200]}...")

        # Check if the response indicates a "page not found" error
        if "couldn't find the page you were looking for" in markdown_data.lower():
            error_message = f"'{athlete_id}' does not seem to be a valid Athlete ID, please try again"
            return render_template('index.html', error=error_message), 404

        # Generate story prompt
        prompt = f"""Using the following Markdown data, create a lighthearted and fun short story (2-3 paragraphs) about the parkrun journey of the runner. The story should be in the third person, include a notable news event from the week of their first parkrun, highlight key stats (total runs, best time), and mention a few locations they have visited. Add some playful running-related puns but keep it engaging and concise.

        {markdown_data}"""

        # Generate story using Gemini
        response = model.generate_content(prompt)
        story_content = response.text

        # Create and save the story to Firebase Realtime Database
        url_hash = generate_url_hash()
        story_data = {
            'athlete_id': athlete_id,
            'content': story_content,
            'url_hash': url_hash,
            'created_at': {'.sv': 'timestamp'}
        }

        ref.push(story_data)

        return render_template('story.html', story=story_content, url_hash=url_hash)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return render_template('index.html', error=f"Error: {str(e)}"), 500

@app.route('/social-card/<url_hash>.png')
def generate_social_card(url_hash):
    try:
        # Get all stories and filter by url_hash
        stories = ref.get()
        if not stories:
            return "Story not found", 404

        # Find the story with matching url_hash
        matching_story = None
        for story_id, story_data in stories.items():
            if story_data.get('url_hash') == url_hash:
                matching_story = story_data
                break

        if not matching_story:
            return "Story not found", 404

        # Generate the social card image
        img_io = create_social_card(matching_story['content'], matching_story['athlete_id'])

        return send_file(
            img_io,
            mimetype='image/png',
            as_attachment=False,
            download_name=f'parkrun-story-{url_hash}.png'
        )

    except Exception as e:
        logger.error(f"Error generating social card: {str(e)}")
        return "Error generating social card", 500


def create_social_card(story_text, athlete_id):
    """Create a social media card image with the story preview."""
    # Create a new image with a dark background
    width = 1200
    height = 630
    img = Image.new('RGB', (width, height), color='#212529')
    draw = ImageDraw.Draw(img)

    # Try different font paths for Noto fonts
    try:
        font_title = ImageFont.truetype("/nix/store/*/share/fonts/noto/NotoSans-Bold.ttf", 48)
        font_text = ImageFont.truetype("/nix/store/*/share/fonts/noto/NotoSans-Regular.ttf", 32)
    except IOError:
        # Fallback to default font if custom font loading fails
        logger.warning("Failed to load Noto fonts, falling back to default font")
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    # Add title
    title = f"Parkrun Story - Athlete {athlete_id}"
    draw.text((60, 50), title, font=font_title, fill='white')

    # Add story preview (first 200 characters)
    preview_text = story_text[:200] + "..."
    wrapped_text = textwrap.wrap(preview_text, width=40)
    y = 150
    for line in wrapped_text:
        draw.text((60, y), line, font=font_text, fill='#f8f9fa')
        y += 40

    # Add footer
    draw.text((60, height - 100), "Generated by Parkrun Story Generator", font=font_text, fill='#6c757d')

    # Save to BytesIO object
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io

@app.errorhandler(404)
def not_found_error(error):
    return render_template('index.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('index.html', error="Internal server error"), 500