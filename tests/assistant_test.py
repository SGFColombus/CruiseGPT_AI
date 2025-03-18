from datetime import datetime
import requests
from typing import Dict, Any
import pandas as pd
import os
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json
import openpyxl
from openpyxl.styles import Alignment

# Load the embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Create the data directory if it doesn't exist
data_dir = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(data_dir, exist_ok=True)

# Define the Excel file path
EXCEL_FILE = os.path.join(data_dir, "Searching_agent_test.xlsx")

# Create the Excel file if it doesn't exist
if not os.path.exists(EXCEL_FILE):
    columns = [
        "Input",
        "Expected Message",
        "Expected Cruises",
        "Actual Message",
        "Actual Cruises",
        "Scoring (Message)",
        "Scoring (Cruises)",
        "LLM Score",
    ]
    df = pd.DataFrame(columns=columns)

    sample_data = [
        {
            "Input": "Give me cruises that are going to Asia",
            "Expected Message": "Here are some cruises to Asia:",
            "Expected Cruises": '[{"destination": "Asia"}]',
        },
        {
            "Input": "Find all cruises that last more than 10 days",
            "Expected Message": "Here are some cruises that last more than 10 days:",
            "Expected Cruises": '[{"duration_min": 10}]',
        },
        {
            "Input": "Find cruises that depart from Hong Kong",
            "Expected Message": "Here are cruises departing from Hong Kong:",
            "Expected Cruises": '[{"embarkationPortName": "Hong Kong"}]',
        },
        {
            "Input": "I want cruises that arrive at Singapore",
            "Expected Message": "Here are cruises that arrive in Singapore:",
            "Expected Cruises": '[{"disembarkationPortName": "Singapore"}]',
        },
        {
            "Input": "Find cruises where the itinerary includes Gibraltar",
            "Expected Message": "Here are cruises with itineraries that include Hong Kong:",
            "Expected Cruises": '[{"itinerary": [{"portName": "Gibraltar"}]}]',
        },
        {
            "Input": "Are there cruises starting after January 1, 2025",
            "Expected Message": "Here are cruises starting after January 1, 2025:",
            "Expected Cruises": '[{"sailStartDate_after": "2025-01-01"}]',
        },
        {
            "Input": "Provide me with cruises that end in Singapore and last exactly 11 days",
            "Expected Message": "Here are cruises that end in Singapore and last 11 days:",
            "Expected Cruises": '[{"duration_min": 11, "duration_max": 11, "disembarkationPortName": "Singapore"}]',
        },
        {
            "Input": "Find cruises departing from Hong Kong and traveling to Asia",
            "Expected Message": "Here are cruises departing from Hong Kong to Asia:",
            "Expected Cruises": '[{"embarkationPortName": "Hong Kong", "destination": "Asia"}]',
        },
        {
            "Input": "I would like to see the cruises with a duration between 7 and 14 days",
            "Expected Message": "Here are cruises lasting between 7 and 14 days:",
            "Expected Cruises": '[{"duration_min": 7, "duration_max": 14}]',
        },
        {
            "Input": "Show me some cruises that start and end at the same port",
            "Expected Message": "Here are cruises that start and end at the same port:",
            "Expected Cruises": '[{"embarkationPortName": "Hong Kong", "disembarkationPortName": "Hong Kong"}]',
        },
        {
            "Input": "Find cruises where the itinerary starts on or after May 27, 2025",
            "Expected Message": "Here are cruises starting on or after May 27, 2025:",
            "Expected Cruises": '[{"sailStartDate": "2025-05-27"}, {"sailStartDate_after": "2025-05-27"}]',
        },
        {
            "Input": "Are there any cruises that travel to any European destination",
            "Expected Message": "Here are cruises traveling to European destinations:",
            "Expected Cruises": '[{"destination": "Europe", "disembarkationPortName": "Rome"}]',
        },
        {
            "Input": "Can you find for me cruises that include Athens",
            "Expected Message": "Here are cruises that include Athens:",
            "Expected Cruises": '[{"itinerary": [{"portName": "Athens"}]}]',
        },
        {
            "Input": "Find cruises that cost less than $5000",
            "Expected Message": "Here are cruises under $5000:",
            "Expected Cruises": '[{"price_max": 5000}]',
        },
        {
            "Input": "Show me cruises that cost between $2000 and $4000",
            "Expected Message": "Here are cruises between $2000 and $4000:",
            "Expected Cruises": '[{"price_min": 2000, "price_max": 4000}]',
        },
        {
            "Input": "I want the cheapest cruises available",
            "Expected Message": "Here are the cheapest cruises available:",
            "Expected Cruises": '[{"sort_by": "price", "order": "asc"}]',
        },
        {
            "Input": "Find cruises that visit at least 3 different ports",
            "Expected Message": "Here are cruises with at least 3 stops:",
            "Expected Cruises": '[{"itinerary_min_stops": 3}]',
        },
    ]

    df = pd.DataFrame(sample_data)
    df.to_excel(EXCEL_FILE, index=False, engine="openpyxl")
    print(f"Created Excel file: {EXCEL_FILE}")

base_url = "http://localhost:5001/api/chat"


def get_response(input_text):
    """Send a message to the API and get the response."""
    payload = {"sessionId": "eb94989e-f1ee-44f6-b916-bf810281d3f6",
        "message": input_text}
    try:
        response = requests.post(base_url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return {"error": str(e)}


def calculate_similarity(text1, text2):
    """Compute cosine similarity between two text embeddings."""
    if not isinstance(text1, str):
        text1 = ""
    if not isinstance(text2, str):
        text2 = ""

    # Convert text to embeddings
    embedding1 = model.encode([text1])[0]
    embedding2 = model.encode([text2])[0]

    # Compute cosine similarity
    similarity = cosine_similarity([embedding1], [embedding2])[0][0]
    return round(similarity, 4)


def parse_date(date_str):
    """Helper function to parse dates safely"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d") if date_str else None
    except ValueError:
        return None


def validate_cruises(expected_cruises, actual_cruises):
    try:
        # Ensure valid JSON format
        expected_list = json.loads(expected_cruises) if expected_cruises and isinstance(
            expected_cruises, str) else []
        actual_list = json.loads(actual_cruises) if actual_cruises and isinstance(
            actual_cruises, str) else []

        # Edge case: If no expected cruises, return 5 if actual is also empty, otherwise 0
        if not expected_list:
            return 5.0 if not actual_list else 0.0

        score = 0
        total_checks = len(expected_list)  # Normalization factor

        for expected in expected_list:
            duration_min = expected.get("duration_min")
            duration_max = expected.get("duration_max")
            destination = expected.get("destination")
            itinerary = expected.get("itinerary", [])
            excluded_countries = expected.get("excluded_countries", [])
            price_min = expected.get("price_min")
            price_max = expected.get("price_max")
            sort_by = expected.get("sort_by")
            order = expected.get("order")
            itinerary_min_stops = expected.get("itinerary_min_stops")
            sail_start_date = expected.get("sailStartDate")
            sail_start_date_after = parse_date(
                expected.get("sailStartDate_after"))
            sail_start_date_before = parse_date(
                expected.get("sailStartDate_before"))
            sail_end_date = expected.get("sailEndDate")

            for actual in actual_list:
                cruise_duration = actual.get("duration")
                cruise_duration = int(cruise_duration) if cruise_duration is not None else 0
                cruise_destination = actual.get("destination", "")
                cruise_price = actual.get("price")
                cruise_sail_start_date = parse_date(
                    actual.get("departureDate"))
                cruise_sail_end_date = parse_date(actual.get("returnDate"))

                # Process itinerary correctly
                if isinstance(actual.get("itinerary"), str):
                    itinerary_ports = actual["itinerary"].split(" → ")
                elif isinstance(actual.get("itinerary"), list):
                    itinerary_ports = [stop["portName"]
                        for stop in actual["itinerary"]]
                else:
                    itinerary_ports = []

                # Check Duration
                if duration_min is not None and cruise_duration < duration_min:
                    continue
                if duration_max is not None and cruise_duration > duration_max:
                    continue

                # Check Destination
                if destination and destination.lower() not in cruise_destination.lower():
                    continue

                # Check Itinerary Inclusion
                if itinerary:
                    matched_itinerary = all(
                        any(stop["portName"].lower() in port.lower() for port in itinerary_ports)
                        for stop in itinerary
                    )
                    if not matched_itinerary:
                        continue

                # Check Excluded Countries
                if excluded_countries:
                    if any(excluded["portName"].lower() in (port.lower() for port in itinerary_ports) for excluded in excluded_countries):
                        continue

                # Check Price Constraints
                if price_min and (cruise_price is None or cruise_price < price_min):
                    continue
                if price_max and (cruise_price is None or cruise_price > price_max):
                    continue

                # Check Minimum Number of Itinerary Stops
                if itinerary_min_stops and len(itinerary_ports) < itinerary_min_stops:
                    continue

                # Check Sail Start Date Constraints
                if sail_start_date and cruise_sail_start_date != parse_date(sail_start_date):
                    continue
                if sail_start_date_after and cruise_sail_start_date and cruise_sail_start_date <= sail_start_date_after:
                    continue
                if sail_start_date_before and cruise_sail_start_date and cruise_sail_start_date >= sail_start_date_before:
                    continue

                # Check Sail End Date Constraint
                if sail_end_date and cruise_sail_end_date != parse_date(sail_end_date):
                    continue

                score += 1  # If all checks pass, count as a valid match
                break  # Move to the next expected cruise after a successful match

        # Normalize score between 0 and 5
        normalized_score = (score / total_checks) * 5 if total_checks else 0.0

        # Validate sorting logic separately (apply penalty if incorrect)
        if sort_by == "price" and actual_list:
            prices = [cruise.get("price") for cruise in actual_list if cruise.get("price") is not None]
            expected_order = sorted(prices) if order == "asc" else sorted(prices, reverse=True)
            if prices and prices != expected_order:
                normalized_score *= 0.8  # Reduce score by 20% for sorting issues

        return round(normalized_score, 2)  # Return score on a 5-point scale

    except json.JSONDecodeError:
        return 0.0


def extract_cruise_details(response):
    """Extract cruise details from API response."""
    try:
        # Handle case where response is a string
        if isinstance(response, str):
            response = json.loads(response)
            
        cruises = response.get("cruises", [])
        return json.dumps(
            [
                {
                    "destination": c.get("destination"),
                    "itinerary": c.get("itinerary", ""),  # Already formatted in db.py
                    "duration": c.get("duration"),
                    "price": c.get("price"),  # Price is directly available
                    "originalPrice": c.get("originalPrice"),
                    "departureDate": c.get("departureDate"),
                    "returnDate": c.get("returnDate"),
                    "embarkationPort": c.get("embarkationPort"),
                    "disembarkationPort": c.get("disembarkationPort"),
                }
                for c in cruises
            ]
        )
    except Exception as e:
        print(f"Error extracting cruise details: {e}")
        return "[]"

    
def llm_validation(user_input, expected_message, actual_message, expected_cruises, actual_cruises):
    """
    Uses a local LLaMA model via Ollama to compare expected vs. actual responses and score them on a scale of 1-5.
    """
    max_retries = 3
    timeout = 60  # Increased timeout to 60 seconds
    
    for attempt in range(max_retries):
        try:
            # Shorten the prompt to reduce processing time
            prompt = f"""Rate these cruise booking responses on a scale of 1-5:

User: {user_input}
Expected: {expected_message}
Actual: {actual_message}

Return only a number 1-5."""

            response = requests.post(
                OLLAMA_API_URL,
                json={"model": "llama2", "prompt": prompt, "stream": False},
                timeout=timeout
            )
            response.raise_for_status()
            
            response_data = response.json()
            score_text = response_data.get("response", "").strip()
            
            try:
                score = float(score_text)
                return min(max(score, 1), 5)  # Ensure score is between 1 and 5
            except ValueError:
                print(f"Could not parse score from response: {score_text}")
                return 3.0  # Return middle score on parse error
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} timed out, retrying...")
                continue
            print("All retry attempts failed")
            return 3.0  # Return middle score on timeout
        except Exception as e:
            print(f"Error in LLaMA validation: {e}")
            return 3.0  # Return middle score on error
    
    return 3.0  # Return middle score if all attempts fail


def update_excel():
    """Read input from Excel, send API request, update results, and format sheet for better readability."""
    df = pd.read_excel(EXCEL_FILE, engine="openpyxl")

    for index, row in df.iterrows():
        input_text = row["Input"]
        expected_message = row.get("Expected Message", "")
        expected_cruises = row.get("Expected Cruises", "")

        # Get API response
        api_response = get_response(input_text)
        print("Row ", index, " Response done")
        actual_message = api_response.get("message", "")
        actual_cruises = extract_cruise_details(api_response)

        score_message = calculate_similarity(actual_message, expected_message)
        score_cruises = validate_cruises(expected_cruises, actual_cruises)
        llm_score = llm_validation(input_text, expected_message, actual_message, expected_cruises, actual_cruises)

        # Update DataFrame
        df.at[index, "Actual Message"] = actual_message
        df.at[index, "Actual Cruises"] = actual_cruises
        df.at[index, "Scoring (Message)"] = score_message
        df.at[index, "Scoring (Cruises)"] = score_cruises
        df.at[index, "LLM Score"] = llm_score

    try:
        # Save updates to Excel
        df.to_excel(EXCEL_FILE, index=False, engine="openpyxl")

        # Open Excel file and format columns
        wb = openpyxl.load_workbook(EXCEL_FILE)
        ws = wb.active

        # Auto-adjust column widths
        for col in ws.columns:
            max_length = 0
            # Get the column letter (A, B, C, etc.)
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            # Set column width
            ws.column_dimensions[col_letter].width = max_length + 2

        # Enable text wrapping for all cells
        for row in ws.iter_rows():
            for cell in row:
                cell.alignment = Alignment(wrap_text=True)

        # Save the formatted file
        wb.save(EXCEL_FILE)
        print("Excel file updated and formatted successfully!")

    except PermissionError:
        print("Error: Please close the Excel file before running this script.")


if __name__ == "__main__":
    update_excel()
