from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/sms", methods=['POST'])
def sms_reply():
    incoming_msg = request.form['Body']
    resp = MessagingResponse()
    msg = resp.message(f"You said: {incoming_msg}")
    return str(resp)
