from typing import Dict, Any
import google.generativeai as genai
import json
from datetime import datetime, timedelta

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

    def generate_query(self, prompt: str) -> Dict[str, Any]:
        try:
            system_prompt = f"""
            You are a MongoDB query generator. Convert natural language to MongoDB queries.
            Database schema: {json.dumps(self.collection_schema, indent=2)}
            Only respond with a valid MongoDB query in JSON format, nothing else.
            """

            full_prompt = f"{system_prompt}\n\nUser query: {prompt}"
            response = self.model.generate_content(full_prompt)
            
            # Extract JSON from response
            response_text = response.text
            # Clean up the response to ensure it's valid JSON
            response_text = response_text.strip('`').strip()
            if response_text.startswith('json'):
                response_text = response_text[4:].strip()
            
            query = json.loads(response_text)
            return query

        except Exception as e:
            print(f"Error generating query: {e}")
            return {}

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