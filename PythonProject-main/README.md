# Automated SMS Ordering System

This project is a FastAPI-based service that integrates with ClickSend to receive and respond to MMS/SMS messages automatically. It follows a predefined conversation flow to collect user responses and save them to an Excel file.

## Features
- Receive and process SMS/MMS messages from ClickSend
- Automated conversation flow to collect user details
- Validate user inputs such as names and t-shirt sizes
- Store user responses in a Redis database
- Save collected data to an Excel file
- Send automated reminders for incomplete responses

## Prerequisites
Ensure you have the following installed:
- Python 3.8+
- Redis
- ClickSend API credentials

## Installation

1. Clone the repository:
   ```sh
   git clone https://https://github.com/Hollie-OurHouse/SCP-5K-2025.git
   cd SCP-5K-2025
   ```

2. Create and activate a virtual environment:
   ```sh
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   venv\Scripts\activate  # On Windows
   ```

3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the root directory and add the following:
   ```ini
   CLICKSEND_USERNAME=your_clicksend_username
   CLICKSEND_API_KEY=your_clicksend_api_key
   CLICKSEND_SMS_URL=https://rest.clicksend.com/v3/sms/send
   DEDICATED_NUMBER=your_dedicated_number
   
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_DB=0
   
   EXCEL_FILE=responses.xlsx
   TIMEOUT_SECONDS=
   ```

## Running the Application

1. Start Redis server (if not already running):
   ```sh
   redis-server
   ```

2. Start the FastAPI server:
   ```sh
   uvicorn main:app
   ```

3. The application will now be available at:
   ```
   http://127.0.0.1:8000
   ```

## Webhook Endpoint

ClickSend should be configured to send incoming messages to the following endpoint:
```
POST /webhook
```
This endpoint processes messages and triggers the conversation flow.

## Conversation Flow
1. **User sends a message** → Receives greeting and prompt for name.
2. **User provides name** → Asked for honoree's name.
3. **User provides honoree's name** → Asked for relationship.
4. **User provides relationship** → Asked for t-shirt size.
5. **User provides valid size** → Confirmation message is sent, data is saved.

If the user does not respond for a certain time, they receive a reminder before session expiration.

## Saving Data to Excel
All user responses are stored in `responses.xlsx` in the `responses/` directory. The data includes:
- Phone number
- First name
- Last name
- Honoree name
- Relationship
- T-shirt size
- Timestamp

## Error Handling
- Invalid names trigger an error message.
- Invalid t-shirt sizes prompt the user to select from valid options.
- If the request is malformed, a 400 or 500 HTTP error is returned.

## Deployment
- Use Docker, DigitalOcean, or any cloud service for production deployment.
- Set up Redis and the FastAPI server in a production environment.
