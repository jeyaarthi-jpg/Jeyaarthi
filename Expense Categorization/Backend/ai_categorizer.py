import json
import google.generativeai as genai

from config import Config

genai.configure(
    api_key=Config.GEMINI_API_KEY
)

model = genai.GenerativeModel(
    "gemini-2.5-flash"
)

def categorize_transactions(text):

    try:

        print("\n===== EXTRACTED TEXT SENT TO GEMINI =====\n")
        print(text[:3000])

        prompt = f"""
You are an Expense Categorization AI.

Categories:
Food
Travel
Shopping
Bills
Entertainment
Healthcare
Others

Extract all transactions from the bank statement.

Return ONLY valid JSON.

Example:

[
  {{
    "description":"Swiggy",
    "amount":500,
    "category":"Food"
  }},
  {{
    "description":"Amazon",
    "amount":999,
    "category":"Shopping"
  }}
]

Bank Statement:

{text}
"""

        response = model.generate_content(prompt)

        print("\n===== GEMINI RESPONSE =====\n")
        print(response.text)

        cleaned = (
            response.text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        return json.loads(cleaned)

    except Exception as e:

        print("\nGemini Error:")
        print(e)

        return []