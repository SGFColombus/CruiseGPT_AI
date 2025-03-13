
# CruiseGPT1 Frontend

This is the core AI application for the CruiseGPT1 project. The project repository can be found at: https://github.com/SGFColombus/CruiseGPT_AI

## Overview

CruiseGPT_AI is an application that connects to a backend, and frontend service for data processing and interaction.

## Main Applicaion Features

- Interactive chat interface for cruise recommendations
- AI-powered cruise suggestions based on user preferences
- Real-time cruise search and filtering
- Shopping cart functionality
- Detailed cruise itineraries and pricing

## Tech Stack

- AI: OpenAI API integration

## Prerequisites

- Python 3.11+

## Setup and Installation AI server
1. Install `uv` library
```
pip install uv
```
2. Activate the virtual environment (on Windows)
```
python -m uv sync
```
3. Install dependencies
```
source .venv/Scripts/activate (for linux)
```
```
.\.venv\Scripts\Activate.ps1 (for windows)
```
4. Run the server
```
python agent_server.py
```

- FastAPI server

The application will be available on port 5000.

## Project Structure

1. CruiseGPT_AI Application Files:
- agent_server.py - The main server implementation
- agent.py - Core agent functionality
- agent_cruise_infor.py - Cruise information handling
- db.py - Database operations
- db_tool.py - Database utility functions

2. Testing Files:
- input_test.py - Input features extraction testing
- assistant_test.py - Assistant functionality testing

3. Utility Files:
- utils.py - General utility functions
- pyproject.toml - Python project configuration and dependencies

## Contributing

1. Create a new fork in the project
2. Make your changes
3. Test thoroughly
4. Submit changes for review using the Projects tool
5. Merge changes into the main branch when approved

## License

Smart Goldfish IP reserved
