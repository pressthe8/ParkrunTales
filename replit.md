# Parkrun Story Generator

## Overview

A Flask web application that generates personalized, whimsical stories for Parkrun athletes based on their performance data. The application scrapes athlete data from Parkrun websites using Firecrawl, processes it through Google's Gemini AI to create engaging narratives, and stores stories in Firebase for sharing. Features include social media integration, shareable links, and dynamically generated social media cards.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: Flask with Jinja2 templating
- **UI Library**: Bootstrap 5 with dark theme and Bootstrap Icons
- **Client-side Logic**: Vanilla JavaScript for form interactions and social sharing
- **Responsive Design**: Mobile-first approach with Bootstrap grid system

### Backend Architecture
- **Web Framework**: Flask application with modular configuration
- **Story Generation**: Google Gemini 1.5 Pro for AI-powered content creation
- **Data Scraping**: Firecrawl API for extracting athlete data from Parkrun websites
- **URL Generation**: Secure token-based hash generation for shareable story links
- **Image Processing**: PIL (Pillow) for dynamic social media card generation

### Data Storage
- **Primary Database**: Firebase Realtime Database for story persistence
- **Authentication**: Firebase Admin SDK with custom authentication tokens
- **Security Rules**: Read access for specific queries, write access restricted to authenticated users
- **Data Structure**: Stories indexed by URL hash with athlete metadata

### API Design
- **Story Generation Endpoint**: POST route accepting athlete ID for story creation
- **Story Retrieval**: GET route for accessing stories via shareable URL hash
- **Social Card Generation**: Dynamic image generation endpoint for social media previews
- **Error Handling**: Comprehensive error responses for invalid athlete IDs and API failures

### Security Architecture
- **Environment Variables**: Sensitive credentials stored in .env file
- **Firebase Security Rules**: Granular access control preventing unauthorized data access
- **CORS Protection**: Flask built-in security measures
- **Input Validation**: Server-side validation for athlete ID format and existence

## External Dependencies

### Third-party APIs
- **Google Gemini AI**: Text generation service for creating personalized stories
- **Firecrawl API**: Web scraping service for extracting Parkrun athlete data
- **Firebase Realtime Database**: Cloud database for story storage and retrieval
- **Firebase Admin SDK**: Server-side Firebase integration and authentication

### External Services
- **Social Media Integration**: Twitter and Facebook sharing with Open Graph meta tags
- **CDN Resources**: Bootstrap CSS/JS and Bootstrap Icons from external CDNs
- **Font Resources**: System fonts and web fonts for social card generation

### Python Dependencies
- **Flask**: Web application framework
- **google-generativeai**: Google Gemini AI client library
- **firecrawl-py**: Firecrawl API client
- **firebase-admin**: Firebase server-side SDK
- **python-dotenv**: Environment variable management
- **Pillow**: Image processing and generation
- **pathlib**: File system path management

### Development Tools
- **Configuration Management**: Separate development and production configurations
- **Logging**: Python logging module for debugging and monitoring
- **Security Testing**: Custom Firebase security rule validation scripts