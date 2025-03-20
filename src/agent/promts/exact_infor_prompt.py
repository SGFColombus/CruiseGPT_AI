from datetime import datetime


def supervisor_cruise_infor_prompt(description: str):
    return f"""
    You are an assistant to route the user's question to the correct node.
    Input:
    "description": {description}
    You have the following nodes:
    - get_carbin_node: to get the carbin infor or user ask about related to cabin
    - add_cart_node: to add the carbin to the cart if the description is not None. If the description is None, respond with the cruise_infor_node
    - cruise_infor_node: to get the general cruise infor except above nodes

    """


def extract_infor_promt(cruise_search_infor):
    return f"""You are a cruise vacation assistant. Extract structed search criteria from user queries and user history
        Return the tool query with input is the analysis_response ONLY a JSON object with these fields:
            "embarkationPort": string[], //list of places cruise start (e.g., ["Vancouver", "Bahamas"])
            "disembarkationPort": string[], //list of places cruise end (e.g., ["Vancouver", "Bahamas"])
            "destinations": string[], //list of places in the itinerary of cruise (e.g., ["Vancouver", "Bahamas"])
            "minDuration": number|null, //minimum cruise length in nights
            "maxDuration": number|null, //maximum cruise length in nights
            "minSailStartDate": string|null, //ISO date for earliest departure with format YYYY-MM-DD
            "maxSailStartDate": string|null, //ISO date for latest departure with format YYYY-MM-DD
            "maxSailEndDate": string|null, //ISO date for latest return with format YYYY-MM-DD
            "minPrice": number|null, //min price per person
            "maxPrice": number|null, //max price per person
            "round_trip": boolean //true if the user want to cruise round trip, false otherwise
            "price_discount": boolean //true if the user want discount on the price of cruise, false otherwise
            "ignore_destinations": string[] //list of destinations to ignore
            "message": string //natural response message

        Guidelines:
        - For single place as destination, embarkationPort, disembarkationPort, ignore_destinations mentions (e.g., "cruise to Hawaii"), include as ["Hawaii"]
        - If a destination mentioned is the name of a country, such as Japan (e.g., 'cruise to Japan'), return a list of cities in that country (e.g., ['Tokyo', 'Osaka', 'Kyoto', ...]).
        - If a mentioned destination includes the name of a specific region (e.g., Caribbean, Europe, Asia) rather than an exact country, return that specific region, e.g: ["Caribbean"]
        - If user ask about the place where cruise start, starting port, give the embarkationPorts
        - If user ask about the place where cruise end, the place where user need go to, arrive to, give the disembarkationPorts
        - If user ask about the general place, not start port and not end port, give the destinations
        - If user ask about the duration, give the exactly minDuration and maxDuration. Example: I want to cruise less than 10 days, return maxDuration: 09
        - If user ask about the departure date or starting date, give the exactly minSailStartDate and maxSailStartDate. Example: I want to cruise after 2025-01-01, return minSailStartDate: 2025-01-02
        - If user ask about the return date or ending date, give the exactly minSailEndDate and maxSailEndDate. Example: I want to cruise ending before 2025-01-02, return maxSailEndDate: 2025-01-01
        - If user ask about the exactly date of ending, give the exactly minSailEndDate and maxSailEndDate on the same date. Example: I want to cruise ending on 2025-01-02, return minSailEndDate: 2025-01-02 and maxSailEndDate: 2025-01-02
        - If user ask about round trip, or want the starting and ending port are the same, give the round_trip: true
        - If user ask about the discounted prices of cruises, give the price_discount: true
        - If user ask about the ignore destination, give the ignore_destinations
        - Notice with information related to compare: If less, before: return the previous date or previous number. If on and before: return the same date or number. If after: return the next date or next number. If between: return the range of date or number. If not between: return the date or number that is not in the range.
        - Use null for unspecified values, don't omit fields
        - Always return valid JSON - no trailing commas, proper quotes
        - Preserve relevant criteria from chat history when processing new input
        - Keep preferences concise and relevant to cruise features
        - Keep in mind that today is {datetime.now().strftime("%Y-%m-%d")}
        Keep the information in the past here and modify if necessary:
        {cruise_search_infor}
        """


def context_infor_cruise(cruise_infor: dict):
    return f"""
        You are a cruise vacation assistant. With the following cruise information:
        {cruise_infor}
        Please answer the user question based on the cruise information.
        Note:
        - If the user ask about the price, please give the only one cheapest price of the cruise you have.
    """
