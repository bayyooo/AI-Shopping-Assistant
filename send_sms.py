from twilio.rest import Client
import os
from dotenv import load_dotenv

# Load API keys from .env file
load_dotenv()

# Twilio Credentials 
TWILIO_ACCOUNT_SID = os.getenv("account sid goes here")
TWILIO_AUTH_TOKEN = os.getenv("my auth token goes here ")
TWILIO_PHONE_NUMBER = os.getenv("twilio phone goes here")
USER_PHONE_NUMBER = os.getenv("my phone number goes here") 

# Initialize Twilio Client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Send SMS
message = client.messages.create(
    body="hello this is a test message ",
    from_=twilio number goes here,
    to=my number goes here 
)

print(f"Message sent! ID: {message.sid}")