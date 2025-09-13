import os
import logging
import time
from flask import Flask, render_template, request, redirect, url_for, send_file
from dotenv import load_dotenv
import google.generativeai as genai
from firecrawl import FirecrawlApp
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.firestore import SERVER_TIMESTAMP
from google.cloud import firestore as gcf
import json
from datetime import datetime, timedelta, timezone
import secrets
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import textwrap
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
# Require secret key - no fallback for security
if not os.environ.get("FLASK_SECRET_KEY"):
    raise ValueError("FLASK_SECRET_KEY environment variable is required")
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

# Ensure static/images directory exists
static_images_dir = Path('static/images')
static_images_dir.mkdir(parents=True, exist_ok=True)

# Initialize Firebase
firebase_creds = os.environ.get('FIREBASE_CREDENTIALS')
if not firebase_creds:
    raise ValueError("FIREBASE_CREDENTIALS environment variable is required")

try:
    cred_dict = json.loads(firebase_creds)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
except json.JSONDecodeError:
    raise ValueError("Invalid JSON in FIREBASE_CREDENTIALS")

# Get Firestore client
db = firestore.client()

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-pro')

# Configure Firecrawl
firecrawl = FirecrawlApp(api_key=os.getenv('FIRECRAWL_API_KEY'))

def generate_url_hash():
    """Generate a unique URL hash for story sharing."""
    return secrets.token_hex(8)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/story/<url_hash>')
def view_story(url_hash):
    try:
        # Look up story via links collection for O(1) access
        link_ref = db.collection('links').document(url_hash)
        link_doc = link_ref.get()
        
        if not link_doc.exists:
            logger.debug(f"No link found with url_hash: {url_hash}")
            return render_template('index.html', error="Story not found"), 404
        
        link_data = link_doc.to_dict()
        athlete_id = link_data['athlete_id']
        
        # Get the actual story document
        story_ref = db.collection('athletes').document(athlete_id).collection('stories').document(url_hash)
        story_doc = story_ref.get()
        
        if not story_doc.exists:
            logger.debug(f"Story document not found for url_hash: {url_hash}")
            return render_template('index.html', error="Story not found"), 404
            
        story_data = story_doc.to_dict()
        
        return render_template(
            'story.html',
            story=story_data['content'],
            url_hash=url_hash,
            athlete_name=story_data.get('athlete_name', 'Athlete')
        )

    except Exception as e:
        logger.error(f"Error retrieving story: {str(e)}")
        return render_template('index.html', error="Error retrieving story"), 500

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
        current_time = datetime.now(timezone.utc)
        CACHE_DURATION = timedelta(days=7)

        # Query athlete's stories ordered by last_fetched to find most recent
        athlete_stories_ref = db.collection('athletes').document(athlete_id).collection('stories')
        recent_stories = athlete_stories_ref.order_by('last_fetched', direction=gcf.Query.DESCENDING).limit(1).get()
        
        recent_story = None
        if recent_stories:
            story_doc = recent_stories[0]
            story_data = story_doc.to_dict()
            last_fetched = story_data.get('last_fetched')
            
            # Check if the story is still within cache duration
            if last_fetched and (current_time - last_fetched) < CACHE_DURATION:
                recent_story = story_data

        if recent_story:
            markdown_data = recent_story['markdown_data']
            athlete_name = recent_story.get('athlete_name', 'Athlete')
            logger.info("✅ Using cached markdown data - No API call needed")
        else:
            # Fetch new data from Parkrun
            logger.info(f"No recent data found for {athlete_id} - Making new API call")
            parkrun_url = f"https://www.parkrun.org.uk/parkrunner/{numeric_id}/all/"
            api_start_time = time.time()

            response = firecrawl.scrape_url(
                url=parkrun_url,
                params={'formats': ['markdown']}
            )

            api_duration = time.time() - api_start_time
            logger.info(f"🌐 API call completed in {api_duration:.2f} seconds")

            if not response or not isinstance(response, dict) or 'markdown' not in response:
                logger.error("Invalid response format from Firecrawl")
                return render_template('index.html', error="Could not fetch runner data"), 500

            markdown_data = response['markdown']
            logger.debug(f"Received markdown data: {markdown_data[:200]}...")

            # Check for invalid athlete ID
            if "couldn't find the page you were looking for" in markdown_data.lower():
                error_message = f"'{athlete_id}' does not seem to be a valid Athlete ID, please try again"
                return render_template('index.html', error=error_message), 404

        # Extract athlete's name
        import re
        athlete_name = "Athlete"  # Default fallback
        name_match = re.search(r'## ([A-Za-z\s]+)', markdown_data)
        if name_match:
            full_name = name_match.group(1).strip()
            athlete_name = full_name.split()[0]
            logger.debug(f"Found athlete name: {full_name}, using first name: {athlete_name}")

        # Generate story prompt and content
        prompt = f"""Using the Markdown data that follows these instructions, create a lighthearted and fun short story (2-3 paragraphs) about the parkrun career of the runner.

Requirement - Craft a story in the third person to include:

1. **Introduction:** Start by talking about the date and location of their first ever parkrun, with a creative reason for them first getting involved.

2. **Key Stats & Evolving Affinities:** Highlight key stats (total runs, best time so far), and mention a few locations they have visited. Do they have a favorite course, or did their preferences change over time?

3. **Milestones and Memories:** Mention if they have achieved any milestone clubs and include anecdotes about highs and lows, particularly when they hit PBs.

Run Number is only interesting if it is 1, signifying the runner participated in a debut event at that course. 

4. **Celebration and Conclusion:** Conclude by celebrating their achievements, regardless of their best or average times. Focus on the journey, the community, and the personal satisfaction of participating. Avoid cheesy clichés, but acknowledge their dedication.

        {markdown_data}"""
        response = model.generate_content(prompt)
        story_content = response.text

        # Create and save the story with additional fields
        url_hash = generate_url_hash()
        expires_at = current_time + timedelta(days=7)
        
        story_data = {
            'athlete_id': athlete_id,
            'content': story_content,
            'url_hash': url_hash,
            'athlete_name': athlete_name,
            'markdown_data': markdown_data,
            'last_fetched': current_time,
            'created_at': SERVER_TIMESTAMP,
            'expires_at': expires_at
        }

        # Save story to athletes/{athleteId}/stories/{url_hash}
        story_ref = db.collection('athletes').document(athlete_id).collection('stories').document(url_hash)
        story_ref.set(story_data)
        
        # Create link document for fast lookup
        link_data = {
            'athlete_id': athlete_id,
            'created_at': SERVER_TIMESTAMP,
            'expires_at': expires_at
        }
        link_ref = db.collection('links').document(url_hash)
        link_ref.set(link_data)

        total_duration = time.time() - start_time
        logger.info(f"✨ Total story generation completed in {total_duration:.2f} seconds")

        return render_template('story.html', story=story_content, url_hash=url_hash, athlete_name=athlete_name)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return render_template('index.html', error=str(e)), 500

@app.route('/social-card/<url_hash>.png')
def generate_social_card(url_hash):
    try:
        # Look up story via links collection for O(1) access
        link_ref = db.collection('links').document(url_hash)
        link_doc = link_ref.get()
        
        if not link_doc.exists:
            return "Story not found", 404
        
        link_data = link_doc.to_dict()
        athlete_id = link_data['athlete_id']
        
        # Get the actual story document
        story_ref = db.collection('athletes').document(athlete_id).collection('stories').document(url_hash)
        story_doc = story_ref.get()
        
        if not story_doc.exists:
            return "Story not found", 404
            
        story_data = story_doc.to_dict()

        # Generate the social card image
        img_io = create_social_card(story_data['content'], story_data['athlete_id'])

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
    width = 1200
    height = 630
    img = Image.new('RGB', (width, height), color='#212529')
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("/nix/store/*/share/fonts/noto/NotoSans-Bold.ttf", 48)
        font_text = ImageFont.truetype("/nix/store/*/share/fonts/noto/NotoSans-Regular.ttf", 32)
    except IOError:
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

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('index.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('index.html', error="Internal server error"), 500