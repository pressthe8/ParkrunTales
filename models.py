from datetime import datetime
from app import db

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    athlete_id = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    url_hash = db.Column(db.String(16), unique=True, nullable=False)
