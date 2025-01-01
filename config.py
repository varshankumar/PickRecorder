import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv('MONGO_URI')

if not MONGO_URI:
    raise EnvironmentError("MONGO_URI not found in environment variables.")

# The Odds API configuration
ODDS_API_KEY = os.getenv('ODDS_API_KEY')

if not ODDS_API_KEY:
    raise EnvironmentError("ODDS_API_KEY not found in environment variables.")

# Add Gemini API configuration
GEMINI_API_KEY = os.getenv('GEMINI_KEY')  # Changed from GEMINI_API_KEY to GEMINI_KEY

if not GEMINI_API_KEY:
    raise EnvironmentError("GEMINI_API_KEY not found in environment variables.")

# The Odds API endpoints and parameters
API_BASE_URL = 'https://api.the-odds-api.com/v4/sports/'
SPORTS = {
    'basketball_nba': 'NBA',
    'americanfootball_nfl': 'NFL',
    'basketball_ncaab': 'NCAAB',
    'americanfootball_ncaaf': 'NCAAF',  # Changed from americanfootball_college
    'icehockey_nhl': 'NHL',  # Changed from hockey_nhl
    'baseball_mlb': 'MLB'  # Add MLB support
}
REGION = 'us'         # Can be 'us', 'uk', 'eu', 'au'
MARKET = 'h2h'        # Moneyline
ODDS_FORMAT = 'american'  # or 'decimal'
DATE_FORMAT = 'iso'        # or 'unix'

# Remove LEAGUES mapping as it's redundant
