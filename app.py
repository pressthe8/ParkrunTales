import os
import logging
import time
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
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "default-secret-key")

# Add this code after app initialization
# Ensure static/images directory exists and copy the run-story-image
static_images_dir = Path('static/images')
static_images_dir.mkdir(parents=True, exist_ok=True)

# Copy the image from attached_assets to static/images if it doesn't exist
source_image = Path('attached_assets/run-story-image.jpg')
target_image = static_images_dir / 'run-story-image.jpg'
if source_image.exists() and not target_image.exists():
    shutil.copy2(source_image, target_image)


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

        return render_template('story.html', story=matching_story['content'], url_hash=url_hash, athlete_name=matching_story.get('athlete_name', 'Athlete'))

    except Exception as e:
        logger.error(f"Error retrieving story: {str(e)}")
        return render_template('index.html', error="Error retrieving story"), 500

def convert_markdown_to_json(markdown_data):
    """Convert markdown data to structured JSON using Gemini API."""
    prompt = f"""Please use the below markdown data and convert it into a neatly formatted json file that breaks out the key stats in 3 groups:

1) Summary Stats for All Locations
2) Best Overall Annual Achievements
3) All Results

Please ensure the output is valid JSON format.

Here's the markdown data:
{markdown_data}"""

    try:
        response = model.generate_content(prompt)
        # Parse the response to ensure it's valid JSON
        try:
            json_data = json.loads(response.text)
            return json_data
        except json.JSONDecodeError:
            # If the response isn't valid JSON, log it and return None
            logger.error(f"Invalid JSON response from Gemini: {response.text[:200]}...")
            return None
    except Exception as e:
        logger.error(f"Error converting markdown to JSON: {str(e)}")
        return None

@app.route('/generate_story', methods=['GET', 'POST'])
def generate_story():
    if request.method == 'GET':
        return redirect(url_for('index'))

    athlete_id = request.form.get('athlete_id')

    if not athlete_id:
        return render_template('index.html', error='Athlete ID is required'), 400

    try:
        start_time = time.time()
        logger.info(f"Starting story generation for athlete ID: {athlete_id}")

        # Remove 'A' prefix if present
        numeric_id = athlete_id.lstrip('A')

        # Check if we have recent data for this athlete
        stories = ref.get()
        current_time = int(time.time())
        CACHE_DURATION = 7 * 24 * 60 * 60  # 7 days in seconds

        recent_story = None
        if stories:
            for story_id, story_data in stories.items():
                if (story_data.get('athlete_id') == athlete_id and 
                    story_data.get('parkrun_data') and  # Now checking for JSON data instead of markdown
                    story_data.get('last_fetched') and 
                    (current_time - story_data['last_fetched']) < CACHE_DURATION):
                    recent_story = story_data
                    logger.info(f"Found recent story for athlete {athlete_id} - Using cached data from {story_data['last_fetched']}")
                    break

        if recent_story:
            # Use cached JSON data
            parkrun_data = recent_story['parkrun_data']
            athlete_name = recent_story.get('athlete_name', 'Athlete')
            logger.info("✅ Using cached parkrun data - No API calls needed")
        else:
            # Fetch new data from Parkrun
            logger.info(f"No recent data found for {athlete_id} - Making new API call")
            parkrun_url = f"https://www.parkrun.org.uk/parkrunner/{numeric_id}/all/"
            api_start_time = time.time()

            response = firecrawl.scrape_url(
                url=parkrun_url,
                params={
                    'formats': ['markdown']
                }
            )

            api_duration = time.time() - api_start_time
            logger.info(f"🌐 Firecrawl API call completed in {api_duration:.2f} seconds")

            if not response or not isinstance(response, dict) or 'markdown' not in response:
                logger.error("Invalid response format from Firecrawl")
                return render_template('index.html', error="Could not fetch runner data"), 500

            markdown_data = response['markdown']
            logger.debug(f"Received markdown data: {markdown_data[:200]}...")

            # Check for invalid athlete ID
            if "couldn't find the page you were looking for" in markdown_data.lower():
                error_message = f"'{athlete_id}' does not seem to be a valid Athlete ID, please try again"
                return render_template('index.html', error=error_message), 404

            # Convert markdown to structured JSON
            logger.info("Converting markdown to JSON format...")
            json_start_time = time.time()
            parkrun_data = convert_markdown_to_json(markdown_data)
            json_duration = time.time() - json_start_time
            logger.info(f"✨ JSON conversion completed in {json_duration:.2f} seconds")

            if not parkrun_data:
                return render_template('index.html', error="Error processing runner data"), 500

            # Extract athlete's name
            athlete_name = "Athlete"  # Default fallback
            if isinstance(parkrun_data, dict) and "summary" in parkrun_data:
                athlete_name = parkrun_data.get("summary", {}).get("name", "Athlete").split()[0]

        # Generate story using JSON data
        story_prompt = f"""Using the following JSON data about a parkrun athlete, create a lighthearted and fun short story (2-3 paragraphs) about their parkrun career.

Requirement - Craft a story in the third person to include:

1) Introduction: Start by talking about the date and location of their first ever parkrun, with a creative reason for them first getting involved.
2) Key Stats & Evolving Affinities: Highlight key stats (total runs, best time so far), and mention a few locations they have visited.
3) Milestones and Memories: Mention any milestone clubs achieved and include anecdotes about highs and lows, particularly PBs.
4) Celebration and Conclusion: Celebrate their achievements focusing on the journey and community aspects.

Here's the structured data:
{json.dumps(parkrun_data, indent=2)}"""

        story_start_time = time.time()
        response = model.generate_content(story_prompt)
        story_content = response.text
        story_duration = time.time() - story_start_time
        logger.info(f"📖 Story generation completed in {story_duration:.2f} seconds")

        # Create and save the story with additional fields
        url_hash = generate_url_hash()
        story_data = {
            'athlete_id': athlete_id,
            'content': story_content,
            'url_hash': url_hash,
            'athlete_name': athlete_name,
            'parkrun_data': parkrun_data,  # Store JSON instead of markdown
            'last_fetched': current_time,
            'created_at': {'.sv': 'timestamp'}
        }

        ref.push(story_data)

        total_duration = time.time() - start_time
        logger.info(f"✨ Total process completed in {total_duration:.2f} seconds")

        return render_template('story.html', story=story_content, url_hash=url_hash, athlete_name=athlete_name)

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