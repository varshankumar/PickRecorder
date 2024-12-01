# PickRecorder

A web application for tracking sports betting odds and results across NBA and NFL games. Visit the live site at https://pickrecorder.onrender.com

## Features

### Game Tracking
- Real-time odds tracking for sports games
- Automatic timezone detection for accurate game times
- View today's games, upcoming games, and past results
- Pagination support for browsing large game sets

### Team Statistics
- Detailed team performance analysis
- Win/loss records as favorite and underdog
- Historical moneyline tracking
- Filterable team-specific game history

### AI-Powered Search
- Natural language query processing using Google's Gemini AI
- Complex MongoDB query generation
- Search games by various criteria (date, team, odds, status)

### User Management
- Secure user authentication
- Personalized session management
- User registration and login system

## Tech Stack

- **Backend**: Python/Flask
- **Database**: MongoDB
- **Frontend**: Bootstrap 5, Moment.js
- **Authentication**: Flask-Login
- **AI Integration**: Google Gemini API
- **Time Management**: pytz, Moment.js

## Automated Tasks
Uses GitHub Actions for:

- Daily odds fetching (7 AM PST)
- Game results updates (hourly between 12 PM - 11 PM PST)
- Background task scheduling using PST timezone

## License
This project is proprietary and not licensed for distribution or modification. The source code is provided exclusively for evaluation purposes. Any use, reproduction, or distribution of this code without permission is prohibited.