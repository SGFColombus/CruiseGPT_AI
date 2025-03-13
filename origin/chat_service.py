import os
from openai import OpenAI
import dotenv
import json
from datetime import datetime
from db import DBTool
dotenv.load_dotenv()

class ChatService:
    def __init__(self):
        self.openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.db_tool = DBTool()
    def get_system_prompt(self, chat_history=""):
        return f'''You are a cruise vacation assistant. Extract structed search criteria from user queries and user history
        Return ONLY a JSON object with these fields:        
        "destinations": string[], //list of places (e.g., ["Vancouver", "Bahamas"])
            "minDuration": number|null, //minimum cruise length in nights
            "maxDuration": number|null, //maximum cruise length in nights
            "departureAfter": string|null, //ISO date for earliest departure
            "departureBefore": string|null, //ISO date for latest departure
            "maxPrice": number|null, //max price per person
            "preferences": string[], //special interests (e.g., ["luxury", "family-friendly"])
            "message": string //natural response message
        
        Guidelines:
        1. For single destination mentions (e.g., "cruise to Hawaii"), include as ["Hawaii"]
        2. Use null for unspecified values, don't omit fields
        3. Always return valid JSON - no trailing commas, proper quotes
        4. Preserve relevant criteria from chat history when processing new input
        5. Keep preferences concise and relevant to cruise features
        6. Keep in mind that today is {datetime.now().strftime("%Y-%m-%d")}
        ''' + chat_history + "\nAnalyze the above history with the new input to update search criteria:"

    def simple_chat(self, message):
        analysis_response = self.openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": message}
            ],
            temperature=0.3,
            max_tokens=500
        )
        print("Raw OpenAI response:", analysis_response.choices[0].message)

        try:
            content = analysis_response.choices[0].message.content.strip()
            preferences = json.loads(content)
            print(f"Successfully parsed preferences: {preferences}")
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            raise e

        response = self.db_tool.get_cruises(preferences)
        return response
    
    async def chat_with_context(self, message, session_id):
        history = self.get_history(session_id)
        system_prompt = self.get_system_prompt(history)
        print("System prompt:", system_prompt)
        analysis_response = self.openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.3,
            max_tokens=500
        )
        print("Raw OpenAI response:", analysis_response.choices[0].message)

        try:
            content = analysis_response.choices[0].message.content.strip()
            preferences = json.loads(content)
            print(f"Successfully parsed preferences: {preferences}")
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            raise e

        response = await self.db_tool.get_cruises(preferences)
        return response

    def get_history(self, session_id):
        history= self.db_tool.get_history(session_id)
        history_str = "This is the chat history:\n"
        for message in history:
            history_str += "<Human>: " + message["message"] + "\n" if message["isUser"] else \
                            "<Assistant>: " + message["message"] + "\n"
        return history_str
if __name__ == "__main__":
    chat_service = ChatService()
    print(chat_service.simple_chat("I want a cruise to Vancouver"))
