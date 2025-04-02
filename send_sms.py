from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from firebase_config.firebase_config import init_firebase
from firebase_admin import firestore 






app = Flask(__name__)

# Initialize Firebase DB
db = init_firebase()

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

      # Reply to user
    resp = MessagingResponse()
    resp.message(f"You said: {incoming_msg}")
    return Response(str(resp), content_type="application/xml")


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)