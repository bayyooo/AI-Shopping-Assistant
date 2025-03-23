from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/")
def home():
    return "Flask is running! 🎉"

@app.route("/sms", methods=["POST"])
def sms_reply():
    incoming_msg = request.form.get("Body", "")  # Get the SMS message text
    resp = MessagingResponse()  # Create a Twilio response object
    resp.message(f"You said: {incoming_msg}")  # Add response message
    xml_response = str(resp)  # Convert response to XML
    print("Twilio Response:", xml_response)  # Print response in Flask logs

    return Response(xml_response, content_type="application/xml")  # Force correct Content-Type


if __name__ == "__main__":
    app.run(debug=True)