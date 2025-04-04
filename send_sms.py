from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from firebase_config.firebase_config import init_firebase
from firebase_admin import firestore 
from dotenv import load_dotenv
import os
import re
import json
from datetime import datetime

app = Flask(__name__)
load_dotenv()
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

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

def extract_budget_amount(message):
    """
    Extracts the dollar amount from a budget setting message.
    For example: "set budget to $20" -> 20.0
    """
    # Look for a dollar amount in the message (like $20 or $20.50)
    dollar_pattern = r'\$(\d+(?:\.\d+)?)'
    matches = re.findall(dollar_pattern, message)
    
    if matches:
        # Return the first dollar amount found, converted to a float
        return float(matches[0])
    return None

def extract_purchase_info(message):
    dollar_pattern = r'\$(\d+(?:\.\d+)?)'
    matches = re.findall(dollar_pattern, message)

    if not matches:
        return None, None
    amount = float(matches[0])

    words = message.lower().split()
    item = "item"
# this is gonna look for words between the buy word and "for" or "$"
    for buy_word in ["bought", "purchased", "spent"]:
        if buy_word in words:
            buy_index = words.index(buy_word)
            for i in range(buy_index + 1, len(words)):
                if words[i] == "for" or "$" in words[i]:
                    item_words = words[buy_index + 1:i]
                    if item_words:
                        item = " ".join(item_words)
                    break
    
    return item, amount


def track_purchase(user_number, message):
    """
    Records a purchase and checks it against the user's budget.
    Returns a confirmation message.
    """
    item, amount = extract_purchase_info(message)
    
    if not amount:
        return "Can u try with a format like 'bought coffee for $5'."
    
    # Save the purchase to Firestore
    db.collection("purchases").add({
        "phone": user_number,
        "item": item,
        "amount": amount,
        "timestamp": firestore.SERVER_TIMESTAMP
    })
    
    # Get the user's budget
    budget_doc = db.collection("budgets").document(user_number).get()
    
    if budget_doc.exists:
        budget = budget_doc.to_dict().get("amount", 0)
        
        # Get recent purchases (simple approach - all purchases)
        purchases = db.collection("purchases").where("phone", "==", user_number).stream()
        total_spent = sum(purchase.to_dict().get("amount", 0) for purchase in purchases)
        
        remaining = budget - total_spent
        
        if remaining < 0:
            return f"I've recorded your {item} purchase for ${amount:.2f}. You've now spent ${total_spent:.2f}, which is ${abs(remaining):.2f} over your ${budget:.2f} budget."
        else:
            return f"I've recorded your {item} purchase for ${amount:.2f}. You've spent ${total_spent:.2f} of your ${budget:.2f} budget. You have ${remaining:.2f} left to spend."
    else:
        return f"I've recorded your {item} purchase for ${amount:.2f}. You haven't set a budget yet. Text 'set budget $X' to set one."

    
    

def set_budget(user_number, message):
    amount = extract_budget_amount(message)
    
    if not amount:
        return "Can u try again with a dollar amount like $20."
    
    # Save the budget to Firestore
    db.collection("budgets").document(user_number).set({
        "amount": amount,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    
    return f"Okayy! I set your budget to ${amount:.2f}. Imma help you keep track of your spending."


@app.route("/")
def home():
    return "Flask is running! 🎉"

@app.route("/welcome", methods=["POST"])
def send_welcome():

     # Try to get JSON data, or fall back to form data
    data = request.get_json(silent=True)
    if not data:
        data = request.form.to_dict()
    
    print(f"Received welcome request with data: {data}")  # Debug logging
    
    if not data or 'phone' not in data:
        print("Missing phone number in request")
        return "Missing phone number", 400
    
    user_number = data['phone']
    print(f"Processing welcome for phone: {user_number}")
    try:
        # Print environment variables (first few chars only for security)
        print(f"SID: {TWILIO_ACCOUNT_SID[:5] if TWILIO_ACCOUNT_SID else 'None'}... Token: {TWILIO_AUTH_TOKEN[:5] if TWILIO_AUTH_TOKEN else 'None'}... Phone: {TWILIO_PHONE_NUMBER}")
        
        # Initialize Twilio client
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Send welcome message
        message = client.messages.create(
            body="Hello this is my AI Shopping Assistant. This is supposed to help you stay on budget . if u type HELP youll get a menu",
            from_=TWILIO_PHONE_NUMBER,
            to=user_number
        )
        
        # Log this in Firebase
        db.collection("welcome_messages").add({
            "phone": user_number,
            "message_sid": message.sid,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        
        print(f"Welcome message sent successfully to {user_number}")
        return "Welcome message sent", 200
        
    except Exception as e:
        import traceback
        print(f"Error sending welcome message: {str(e)}")
        print(traceback.format_exc())
        return f"Error: {str(e)}", 500

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
        response_text = set_budget(user_number, incoming_msg)
    elif intent == "track_purchase":
        response_text = track_purchase(user_number, incoming_msg)
    elif intent == "help":
        response_text = "this is the menu \n- Set a budget: 'Set budget $100'\n- Track a purchase: 'Bought coffee for $5'"
    else:
        response_text = "I dont have a response for that yet hehe. Type 'help' for the commands."
    

      # Reply to user
    resp = MessagingResponse()
    resp.message(response_text)
    return Response(str(resp), content_type="application/xml")




if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
