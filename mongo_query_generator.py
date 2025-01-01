from typing import Dict, Any
import google.generativeai as genai
import json
from datetime import datetime, timedelta
import re

class MongoQueryGenerator:
    def __init__(self, gemini_api_key: str):
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        self.collection_schema = {
            "event_date": "datetime",
            "teams": {
                "home": {
                    "name": "string",
                    "moneyline": "number"
                },
                "away": {
                    "name": "string",
                    "moneyline": "number"
                }
            },
            "result": {
                "winner": "string"
            },
            "status": "string"
        }
        self.team_pattern = r'(boston celtics|celtics|other team names...)'

    def generate_query(self, prompt: str) -> Dict[str, Any]:
        try:
            prompt = prompt.lower()
            query = {}
            is_aggregation = False

            # Example: "show me boston celtics games where they lost"
            if 'boston celtics' in prompt or 'celtics' in prompt:
                team_name = 'Boston Celtics'
                if 'lost' in prompt:
                    query = {
                        '$and': [
                            {
                                '$or': [
                                    {'teams.home.name': team_name},
                                    {'teams.away.name': team_name}
                                ]
                            },
                            {'result.winner': {'$ne': team_name}},
                            {'status': 'Completed'}
                        ]
                    }

            # Add more query patterns here...

            if not query:
                # Default query if no pattern matches
                query = {'status': 'Completed'}

            return {
                'query': query,
                'is_aggregation': is_aggregation
            }

        except Exception as e:
            print(f"Error generating query: {e}")
            return {'query': {}, 'is_aggregation': False}

    def process_date_filters(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Process and convert date-related queries to proper MongoDB date filters"""
        if 'event_date' in query:
            date_filter = query['event_date']
            if isinstance(date_filter, dict):
                for op, value in date_filter.items():
                    if isinstance(value, str):
                        if value == "today":
                            today = datetime.now()
                            date_filter[op] = today.replace(hour=0, minute=0, second=0)
                        elif value == "tomorrow":
                            tomorrow = datetime.now() + timedelta(days=1)
                            date_filter[op] = tomorrow.replace(hour=0, minute=0, second=0)
        return query