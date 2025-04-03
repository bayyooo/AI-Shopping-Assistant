from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from firebase_config.firebase_config import init_firebase
from firebase_admin import firestore 
import re
import json
from datetime import datetime

app = Flask(__name__)

# Initialize Firebase DB
db = init_firebase()

def determine_intent(message): #this is gonna take th users message and figure out what they want 
    message = message.lower().strip()
    
    # Check for budget setting
    if "set budget" in message or "budget" in message and "$" in message:
        return "set_budget", message
    
    # Check for purchase tracking
    if "bought" in message or "purchased" in message or "spent" in message:
        return "track_purchase", message
    
    # Check for help request
    if message == "help" or "help" in message:
        return "help", None
        
    return "unknown", None

@app.route("/")
def home():
    return "Flask is running! 🎉"

@app.route("/sms", methods=["POST"])
def sms_reply():
    incoming_msg = request.form.get("Body", "")
    user_number = request.form.get("From", "")
    
    # Save the SMS to Firestore
    db.collection("messages").add({
        "phone": user_number,
        "text": incoming_msg,
        "timestamp": firestore.SERVER_TIMESTAMP
    })
    intent, message_content = determine_intent(incoming_msg)

     # Create a response based on the intent
    if intent == "set_budget":
        response_text = "I'll help you set a budget! (i havent doen this yet )"
    elif intent == "track_purchase":
        response_text = "I'll record your purchase! (havent done this yet either)"
    elif intent == "help":
        response_text = "Here's how to use me: \n- Set a budget: 'Set budget $100'\n- Track a purchase: 'Bought coffee for $5'"
    else:
        response_text = "I'm not sure what you want. Try saying 'help' for assistance."
    

      # Reply to user
    resp = MessagingResponse()
    resp.message(response_text)
    return Response(str(resp), content_type="application/xml")




if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
