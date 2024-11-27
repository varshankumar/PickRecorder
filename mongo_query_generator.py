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
You are an assistant that converts natural language queries into MongoDB queries or aggregation pipelines.

**Database Schema:**
{json.dumps(self.collection_schema, indent=2)}

**Instructions:**
- Determine if the user's query requires data aggregation (e.g., calculating win rates).
- If so, output a MongoDB aggregation pipeline as a Python list of dictionaries.
- If not, output a MongoDB find query as a JSON object.
- Ensure that all operators and operands are correctly formatted.
- Do **not** provide SQL queries.
- Only output the MongoDB query or pipeline with no additional text or explanations.
- Do **not** include any code snippets or formatting, just the pure query object.

**Examples:**

**User Query:**
What is the win rate of the Lakers?

**MongoDB Aggregation Pipeline:**
[
  {{"$match": {{"$or": [{{"teams.home.name": "Lakers"}}, {{"teams.away.name": "Lakers"}}]}}}},
  {{"$group": {{"_id": null, "total_games": {{"$sum": 1}},
               "wins": {{"$sum": {{"$cond": [{{"$eq": ["$result.winner", "Lakers"]}}, 1, 0]}}}}}}}},
  {{"$project": {{"_id": 0, "win_rate": {{"$multiply": [{{"$divide": ["$wins", "$total_games"]}}, 100]}},
                  "total_games": 1, "wins": 1}}}}
]

---

Now convert the following user query into a MongoDB query or aggregation pipeline:

**User Query:**
{prompt}
"""

            response = self.model.generate_content(system_prompt)

            # Extract the query
            response_text = response.text.strip()

            # Ensure response is valid JSON
            try:
                if response_text.startswith('['):
                    # It's an aggregation pipeline
                    query = json.loads(response_text)
                    is_aggregation = True
                else:
                    # It's a regular query
                    query = json.loads(response_text)
                    is_aggregation = False
            except json.JSONDecodeError as e:
                print(f"Error parsing generated query JSON: {e}")
                print(f"Response text: {response_text}")
                return {'query': {}, 'is_aggregation': False}

            # Ensure that 'win_rate' is included in the aggregation pipeline when expected

            return {'query': query, 'is_aggregation': is_aggregation}

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