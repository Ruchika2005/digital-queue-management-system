from twilio.rest import Client
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

def send_whatsapp_reminder(to_number, message):
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')         
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')           
    #from_whatsapp_number = os.getenv('TWILIO_WHATSAPP_FROM')  # Should be like 'whatsapp:+14155238886'

    client = Client(account_sid, auth_token)

    client.messages.create(
        body=message,
        from_='whatsapp:+14155238886',
        to=f'whatsapp:{to_number}'  # Make sure `to_number` is like '+91xxxxxxxxxx'
    )
