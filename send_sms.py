from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from firebase_config.firebase_config import init_firebase
from firebase_admin import firestore 
from dotenv import load_dotenv
import openai
from openai import OpenAI
import os
import os
import re
import json
from datetime import datetime
from datetime import timedelta

app = Flask(__name__)
load_dotenv()
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    # Check for voice/personality setting
    if "set voice" in message or "change voice" in message or "set personality" in message:
        return "set_voice", message
    
    # Check for help request
    if message == "help" or "help" in message:
        return "help", None
        
    return "unknown", None

def extract_voice_type(message):
    """
    Extracts the requested voice/personality type from the message.
    For example: "set voice to strict" -> "strict"
    """
    message = message.lower()
    
    # Look for specific personality types after keywords
    voice_types = ["gentle", "strict", "mean"]
    
    for voice in voice_types:
        if voice in message:
            return voice
            
    return None

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
    Returns a confirmation message based on the user's personality setting.
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
    
    # Get the user's personality
    personality = get_user_personality(user_number)
    
    if budget_doc.exists:
        budget = budget_doc.to_dict().get("amount", 0)
        
        # Get recent purchases
        purchases = db.collection("purchases").where("phone", "==", user_number).stream()
        total_spent = sum(purchase.to_dict().get("amount", 0) for purchase in purchases)
        
        remaining = budget - total_spent
        
        # Create responses based on personality and budget status
        if remaining < 0:
            # Over budget responses
            responses = {
                "gentle": f"I've recorded your {item} purchase for ${amount:.2f}. You've now spent ${total_spent:.2f}, which is ${abs(remaining):.2f} over your ${budget:.2f} budget. We can work together to get back on track!",
                "strict": f"Purchase recorded: {item} for ${amount:.2f}. WARNING: You are now ${abs(remaining):.2f} OVER your ${budget:.2f} budget. You need to stop spending immediately.",
                "mean": f"${abs(remaining):.2f} over budget. Congratulations. You’re not just failing financially — youre actively proving you don’t respect yourself enough to stop."
            }
        else:
            # Under budget responses
            responses = {
                "gentle": f"Great job! I've recorded your {item} purchase for ${amount:.2f}. You've spent ${total_spent:.2f} of your ${budget:.2f} budget. You have ${remaining:.2f} left to spend!",
                "strict": f"Purchase logged: {item} for ${amount:.2f}. Current status: ${total_spent:.2f} spent, ${remaining:.2f} remaining from your ${budget:.2f} budget.",
                "mean": f"${total_spent:.2f} down, ${remaining:.2f} left. Dont blow it now — prove to yourself youre not the same reckless mess you were last month."
            }
            
        return responses.get(personality, f"I've recorded your {item} purchase for ${amount:.2f}. You've spent ${total_spent:.2f} of your ${budget:.2f} budget. You have ${remaining:.2f} left to spend.")
    else:
        # No budget set responses
        responses = {
            "gentle": f"I've recorded your {item} purchase for ${amount:.2f}. You haven't set a budget yet. Would you like to set one? Just text 'set budget $X'.",
            "strict": f"Purchase logged: {item} for ${amount:.2f}. NOTE: You don't have a budget set. Set one immediately with 'set budget $X'.",
            "mean": f"${amount:.2f} gone. No budget set. No surprise. Set one now or accept that your wallet will always be empty — like your sense of self-control."
        }
        
        return responses.get(personality, f"I've recorded your {item} purchase for ${amount:.2f}. You haven't set a budget yet. Text 'set budget $X' to set one.")

def set_budget(user_number, message):
    amount = extract_budget_amount(message)
    
    if not amount:
        return "Can u try again with a dollar amount like $20."
    
    # Save the budget to Firestore
    db.collection("budgets").document(user_number).set({
        "amount": amount,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    # Get the user's personality and return an appropriate response
    personality = get_user_personality(user_number)
    
    responses = {
        "gentle": f"Wonderful! I've set your budget to ${amount:.2f}. I'll help you stay on track with gentle reminders!",
        "strict": f"Budget set to ${amount:.2f}. I'll hold you accountable to this limit. No excuses.",
        "mean": f"Budget: ${amount:.2f}.  bitch u better fucking stick to your budget, do you really like being a broke bitch? Stick to your damn budget before your card declines. If you keep spending like this, you deserve to stay exactly where you are — broke and blaming everything but yourself."
    }
    
    return responses.get(personality, f"Okayy! I set your budget to ${amount:.2f}. Imma help you keep track of your spending.")
   
def get_spending_summary(user_number):
    # Get all purchases for this user
    purchases = db.collection("purchases").where("phone", "==", user_number).stream()
    
    # Group purchases by category or item
    spending_by_item = {}
    total_spent = 0
    
    for purchase in purchases:
        data = purchase.to_dict()
        item = data.get("item", "unknown")
        amount = data.get("amount", 0)
        
        if item not in spending_by_item:
            spending_by_item[item] = 0
        spending_by_item[item] += amount
        total_spent += amount
        
    # Format a response
    response = f"You've spent ${total_spent:.2f} total.\n"
    response += "Breakdown:\n"
    
    for item, amount in spending_by_item.items():
        response += f"- {item}: ${amount:.2f}\n"
        
    return response

def get_spending_for_period(user_number, period):# Calculate start and end dates based on period (week, month, etc.)

    now = datetime.now()
    
    if period == "today":
        start_date = datetime(now.year, now.month, now.day)
        period_name = "today"
    elif period == "week":
        # Start from beginning of week
        start_date = now - timedelta(days=now.weekday())
        start_date = datetime(start_date.year, start_date.month, start_date.day)
        period_name = "this week"
    elif period == "month":
        start_date = datetime(now.year, now.month, 1)
        period_name = "this month"
    else:
        # Default to all time
        start_date = None
        period_name = "all time"
        
    # Query with date filter if needed
    query = db.collection("purchases").where("phone", "==", user_number)
    
    if start_date:
        query = query.where("timestamp", ">=", start_date)
        
    purchases = query.stream()
    
    # Group purchases by category or item
    spending_by_item = {}
    total_spent = 0
    
    for purchase in purchases:
        data = purchase.to_dict()
        item = data.get("item", "unknown")
        amount = data.get("amount", 0)
        
        if item not in spending_by_item:
            spending_by_item[item] = 0
        spending_by_item[item] += amount
        total_spent += amount
    
    # Get the user's personality
    personality = get_user_personality(user_number)
    
    # Format a response based on personality
    responses = {
        "gentle": f"Here's your spending summary for {period_name}. You've spent ${total_spent:.2f} in total.",
        "strict": f"SPENDING REPORT ({period_name}): ${total_spent:.2f} total expenditure.",
        "mean": f"You've blown ${total_spent:.2f} {period_name}. Happy now?"
    }
    
    response = responses.get(personality, f"You've spent ${total_spent:.2f} for {period_name}.")
    response += "\nBreakdown:\n"
    
    for item, amount in spending_by_item.items():
        percent = (amount / total_spent * 100) if total_spent > 0 else 0
        response += f"- {item}: ${amount:.2f} ({percent:.1f}%)\n"
        
    return response

def format_response(user_number, message_type, data):
    """
    Format a response based on the user's chosen personality.
    Like having different tones for different moods - gentle is like a supportive friend,
    strict is like a financial advisor, and savage is like a no-nonsense coach.
    """
    # Get user's personality preference
    pref_doc = db.collection("user_preferences").document(user_number).get()
    
    if pref_doc.exists:
        personality = pref_doc.to_dict().get("personality", "gentle")
    else:
        personality = "gentle"  # Default
        
    # Define response templates for different personalities
    templates = {
        "budget_set": {
            "gentle": "Wonderful! I've set your budget to ${amount:.2f}. I'll help you stay on track!",
            "strict": "Budget set to ${amount:.2f}. I expect you to stay within this limit.",
            "mean": "Budget: ${amount:.2f}. bitch u better fucking stick to your budget, do you really like being a broke bitch? Stick to your damn budget before your card declines. If you keep spending like this, you deserve to stay exactly where you are — broke and blaming everything but yourself."
        },
        "purchase_tracked": {
            # Similar structure for purchase tracking responses
        }
    }
    
    # Select and format the appropriate template
    if message_type in templates and personality in templates[message_type]:
        return templates[message_type][personality].format(**data)
    else:
        # Fallback to default response
        return data.get("default_response", "Ok, got it!")

def get_user_personality(user_number):
    """
    Gets the user's preferred AI personality.
    Returns 'gentle' if not set.
    """
    pref_doc = db.collection("user_preferences").document(user_number).get()
    
    if pref_doc.exists and "personality" in pref_doc.to_dict():
        return pref_doc.to_dict()["personality"]
    else:
        return "gentle"  # Default personality

def get_help_message(user_number):
    """
    Returns a help message based on the user's personality setting.
    """
    personality = get_user_personality(user_number)
    
    base_commands = """
Just talk to me naturally! Here are some examples:

💰 Budgets
- "Set my budget to $100"
- "I need a $50 Target budget"
- "My weekly budget is $200"
- "Reset my budget"

💸 Tracking Purchases
- "I spent $5 on coffee"
- "Bought groceries at Walmart for $45"
- "Spent $20 on lunch today"

📊 Checking Spending
- "How much have I spent?"
- "What's my Target spending?"
- "Show my weekly spending"

🗣️ Changing My Voice
- "Change to mean voice"
- "Make your tone gentle"
- "Switch to strict mode"
    """
    
    responses = {
        "gentle": f"Hello! You can talk to me naturally - no need for specific formats! Here are some examples of what you can say:{base_commands}",
        "strict": f"You can use natural language input. Here are command examples:{base_commands}",
        "mean": f"Just talk normally, I'm not stupid. Examples:{base_commands}"
    }
    
    return responses.get(personality, f"this is the menu {base_commands}")

def handle_format_confusion(user_number, intent):
    """
    Responds to users who seem to be struggling with formats.
    """
    personality = get_user_personality(user_number)
    
    examples = {
        "set_budget": "Instead of 'set budget $100', you could say 'I want to budget $100' or 'My budget is $100'",
        "track_purchase": "Instead of 'bought coffee for $5', you could say 'I spent $5 on coffee' or even just 'coffee $5'",
        "set_store_budget": "Instead of 'set Target budget $50', you could say 'I want to spend $50 at Target' or 'My Target budget is $50'"
    }
    
    example = examples.get(intent, "You can talk to me naturally! For example, 'I spent $20 on lunch' or 'How much is left in my budget?'")
    
    responses = {
        "gentle": f"You don't need to use any specific format! {example}. I'm designed to understand natural language, so just talk to me like you would a friend! 😊",
        "strict": f"Format not required. {example}. Natural language input is accepted.",
        "mean": f"Why are you trying so hard with these formats? Just talk normally. {example}. It's not rocket science."
    }
    
    return responses.get(personality, f"No need for specific formats! {example}")

def analyze_message_with_ai(message, user_number):
    """
    Uses OpenAI to understand user intent and extract relevant information.
    This is like having a smart translator that figures out what the user 
    really wants, even if they don't use the exact keywords we're looking for.
    """
    try:
        # Get the user's personality preference for context
        personality = get_user_personality(user_number)
        
        # Prepare prompt for OpenAI
        prompt = f"""
As a shopping and budget assistant with a {personality} personality, analyze this message:
"{message}"

Determine the user's intent and extract any relevant information.

Possible intents:
- set_budget (extract amount)
- track_purchase (extract item, amount, and possibly store)
- set_voice (extract voice type: gentle, strict, or mean)
- help (no extraction needed)
- get_spending_summary (extract time period if any)
- reset_budget (no extraction needed)
- set_store_budget (extract store and amount)
- set_period_budget (extract period: daily/weekly/monthly and amount, also extract category if present)
- unknown

For set_period_budget:
1. Extract the time period (day/week/month)
2. Extract the amount
3. Extract any category the user mentions (food, groceries, entertainment, clothing, gas, etc.)
4. Users can create their own categories, so extract whatever category they mention

For example:
- "set my food budget for this week to $10" → period="week", category="food", amount=10
- "my entertainment budget is $50 this month" → period="month", category="entertainment", amount=50
- "set a $20 coffee budget for the week" → period="week", category="coffee", amount=20

Return JSON in this exact format without deviating:
{{"intent": "intent_name", "data": {{"key1": "value1", "key2": "value2"}}}}
"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  
            messages=[
                {"role": "system", "content": "You are a helpful shopping assistant that analyzes messages and extracts intents and data."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Extract and parse the response
        ai_response = response.choices[0].message.content
        return json.loads(ai_response)
        
    except Exception as e:
        print(f"Error in AI analysis: {str(e)}")
        # Return a fallback response
        return {"intent": "unknown", "data": {}}

def set_budget_with_amount(user_number, amount):
    """
    Sets a budget using the amount directly (extracted by AI).
    """
    try:
        # Convert to float and validate
        amount = float(amount)
        if amount <= 0:
            return "Budget amount must be positive. Please try again."
        
        # Save the budget to Firestore
        db.collection("budgets").document(user_number).set({
            "amount": amount,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        
        # Get the user's personality and return an appropriate response
        personality = get_user_personality(user_number)
        
        responses = {
            "gentle": f"Wonderful! I've set your budget to ${amount:.2f}. I'll help you stay on track with gentle reminders!",
            "strict": f"Budget set to ${amount:.2f}. I'll hold you accountable to this limit. No excuses.",
            "mean": f"Budget: ${amount:.2f}. Let's see if you can actually stick to it this time!"
        }
        return responses.get(personality, f"Okayy! I set your budget to ${amount:.2f}. Imma help you keep track of your spending.")
        
    except (ValueError, TypeError):
        return "I couldn't understand that amount. Please try something like 'set budget $100'."

def track_purchase_with_data(user_number, item, amount):
    """
    Records a purchase using the item and amount directly (extracted by AI).
    """
    try:
        # Convert to float and validate
        amount = float(amount)
        if amount <= 0:
            return "Purchase amount must be positive. Please try again."
            
        # Save the purchase to Firestore
        db.collection("purchases").add({
            "phone": user_number,
            "item": item,
            "amount": amount,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        
        # Get the user's budget
        budget_doc = db.collection("budgets").document(user_number).get()
        
        # Get the user's personality
        personality = get_user_personality(user_number)
        
        if budget_doc.exists:
            budget = budget_doc.to_dict().get("amount", 0)
            
            # Get recent purchases
            purchases = db.collection("purchases").where("phone", "==", user_number).stream()
            total_spent = sum(purchase.to_dict().get("amount", 0) for purchase in purchases)
            
            remaining = budget - total_spent
            
            # Create responses based on personality and budget status
            if remaining < 0:
                # Over budget responses
                responses = {
                    "gentle": f"I've recorded your {item} purchase for ${amount:.2f}. You've now spent ${total_spent:.2f}, which is ${abs(remaining):.2f} over your ${budget:.2f} budget. We can work together to get back on track!",
                    "strict": f"Purchase recorded: {item} for ${amount:.2f}. WARNING: You are now ${abs(remaining):.2f} OVER your ${budget:.2f} budget. You need to stop spending immediately.",
                    "mean": f"${abs(remaining):.2f} over budget. Congratulations. You're not just failing financially — youre actively proving you don't respect yourself enough to stop."
                }
            else:
                # Under budget responses
                responses = {
                    "gentle": f"Great job! I've recorded your {item} purchase for ${amount:.2f}. You've spent ${total_spent:.2f} of your ${budget:.2f} budget. You have ${remaining:.2f} left to spend!",
                    "strict": f"Purchase logged: {item} for ${amount:.2f}. Current status: ${total_spent:.2f} spent, ${remaining:.2f} remaining from your ${budget:.2f} budget.",
                    "mean": f"${total_spent:.2f} down, ${remaining:.2f} left. Dont blow it now — prove to yourself youre not the same reckless mess you were last month."
                }
                
            return responses.get(personality, f"I've recorded your {item} purchase for ${amount:.2f}. You've spent ${total_spent:.2f} of your ${budget:.2f} budget. You have ${remaining:.2f} left to spend.")
        else:
            # No budget set responses
            responses = {
                "gentle": f"I've recorded your {item} purchase for ${amount:.2f}. You haven't set a budget yet. Would you like to set one? Just text 'set budget $X'.",
                "strict": f"Purchase logged: {item} for ${amount:.2f}. NOTE: You don't have a budget set. Set one immediately with 'set budget $X'.",
                "mean": f"${amount:.2f} gone. No budget set. No surprise. Set one now or accept that your wallet will always be empty — like your sense of self-control."
            }
            
            return responses.get(personality, f"I've recorded your {item} purchase for ${amount:.2f}. You haven't set a budget yet. Text 'set budget $X' to set one.")
            
    except (ValueError, TypeError):
        return "I couldn't understand that amount. Please try something like 'bought coffee for $5'."

def track_purchase_with_category(user_number, item, amount, category=None):
    """
    Records a purchase with an optional category and checks it against category budgets.
    """
    try:
        # Convert to float and validate
        amount = float(amount)
        if amount <= 0:
            return "Purchase amount must be positive. Please try again."
        
        # If no category provided, try to guess from the item
        if not category:
            # Common categories mapping (you can expand this)
            category_mappings = {
                "coffee": "coffee",
                "lunch": "food",
                "dinner": "food",
                "grocery": "groceries",
                "groceries": "groceries",
                "gas": "transportation",
                "uber": "transportation",
                "lyft": "transportation",
                "movie": "entertainment",
                "game": "entertainment",
                "clothes": "clothing",
                "shirt": "clothing",
                "pants": "clothing"
            }
            
            for key, value in category_mappings.items():
                if key in item.lower():
                    category = value
                    break
        
        # Save the purchase to Firestore with category info
        purchase_data = {
            "phone": user_number,
            "item": item,
            "amount": amount,
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        
        if category:
            purchase_data["category"] = category.lower()
            
        db.collection("purchases").add(purchase_data)
        
        # If we have a category, check against category budgets
        if category:
            # Get current time period
            now = datetime.now()
            
            # Check daily budget
            daily_start = datetime(now.year, now.month, now.day)
            daily_purchases = db.collection("purchases").where("phone", "==", user_number)\
                .where("category", "==", category.lower())\
                .where("timestamp", ">=", daily_start)\
                .stream()
                
            daily_spent = sum(purchase.to_dict().get("amount", 0) for purchase in daily_purchases)
            
            # Check weekly budget
            weekly_start = now - timedelta(days=now.weekday())
            weekly_start = datetime(weekly_start.year, weekly_start.month, weekly_start.day)
            weekly_purchases = db.collection("purchases").where("phone", "==", user_number)\
                .where("category", "==", category.lower())\
                .where("timestamp", ">=", weekly_start)\
                .stream()
                
            weekly_spent = sum(purchase.to_dict().get("amount", 0) for purchase in weekly_purchases)
            
            # Check monthly budget
            monthly_start = datetime(now.year, now.month, 1)
            monthly_purchases = db.collection("purchases").where("phone", "==", user_number)\
                .where("category", "==", category.lower())\
                .where("timestamp", ">=", monthly_start)\
                .stream()
                
            monthly_spent = sum(purchase.to_dict().get("amount", 0) for purchase in monthly_purchases)
            
            # Get the budget limits
            budget_doc = db.collection("period_budgets").document(user_number).get()
            
            if budget_doc.exists:
                budget_data = budget_doc.to_dict()
                
                # Check for category-specific budgets
                daily_budget = budget_data.get(f"daily_{category.lower()}_amount")
                weekly_budget = budget_data.get(f"weekly_{category.lower()}_amount")
                monthly_budget = budget_data.get(f"monthly_{category.lower()}_amount")
                
                # Get the user's personality
                personality = get_user_personality(user_number)
                
                # Build the response based on budget status
                response = f"I've recorded your {item} purchase for ${amount:.2f} in your {category} category. "
                
                # Add information about category budget status
                period_info = []
                
                if daily_budget and daily_budget > 0:
                    daily_remaining = daily_budget - daily_spent
                    if daily_remaining < 0:
                        period_info.append(f"You're ${abs(daily_remaining):.2f} over your daily {category} budget.")
                    else:
                        period_info.append(f"You have ${daily_remaining:.2f} left in your daily {category} budget.")
                
                if weekly_budget and weekly_budget > 0:
                    weekly_remaining = weekly_budget - weekly_spent
                    if weekly_remaining < 0:
                        period_info.append(f"You're ${abs(weekly_remaining):.2f} over your weekly {category} budget.")
                    else:
                        period_info.append(f"You have ${weekly_remaining:.2f} left in your weekly {category} budget.")
                
                if monthly_budget and monthly_budget > 0:
                    monthly_remaining = monthly_budget - monthly_spent
                    if monthly_remaining < 0:
                        period_info.append(f"You're ${abs(monthly_remaining):.2f} over your monthly {category} budget.")
                    else:
                        period_info.append(f"You have ${monthly_remaining:.2f} left in your monthly {category} budget.")
                
                if period_info:
                    if personality == "gentle":
                        response += " ".join(period_info)
                    elif personality == "strict":
                        response += " ".join(period_info).replace("You have", "Remaining:").replace("You're", "ALERT: You are")
                    elif personality == "mean":
                        over_budget = any("over" in info for info in period_info)
                        if over_budget:
                            response += "Congratulations on blowing through another budget. " + " ".join(period_info)
                        else:
                            response += "Try not to waste what's left. " + " ".join(period_info)
                    else:
                        response += " ".join(period_info)
                else:
                    response += f"You don't have a {category} budget set yet. Use 'set {category} budget for week/month to $X' to create one."
                
                return response
            else:
                return f"I've recorded your {item} purchase for ${amount:.2f} in your {category} category. You don't have any category budgets set up yet."
        else:
            # If no category, fall back to regular purchase tracking
            return track_purchase(user_number, f"bought {item} for ${amount}")
            
    except (ValueError, TypeError):
        return "I couldn't understand that amount. Please try something like 'spent $25 on groceries'."

def set_voice_with_type(user_number, voice_type):

    """
    Sets the user's voice preference using the voice type extracted by AI.
    """
    # Validate voice type
    valid_voices = ["gentle", "strict", "mean"]
    
    if voice_type not in valid_voices:
        return f"I don't recognize '{voice_type}' as a valid voice option. Please try 'gentle', 'strict', or 'mean'."
    
    # Save the voice preference to Firestore
    db.collection("user_preferences").document(user_number).set({
        "personality": voice_type,
        "updated_at": firestore.SERVER_TIMESTAMP
    }, merge=True)
    
    # Different response messages based on the selected voice
    responses = {
        "gentle": "Voice set to gentle! this one is very nnice ",
        "strict": "Voice set to strict. very direct",
        "mean": "Voice set to mean. this one is mean"
    }
    
    return responses.get(voice_type, f"Voice set to {voice_type}!")

def set_voice(user_number, message):
    """
    Sets the user's preferred AI voice/personality.
    Think of this like choosing between different characters - 
    like switching between a supportive friend, a serious mentor, 
    or a tough coach for your spending habits.
    """
    voice_type = extract_voice_type(message)
    
    if not voice_type:
        return "I didn't catch which voice you want. Try 'set voice to gentle', 'set voice to strict', or 'set voice to mean'."
    
    # Save the voice preference to Firestore
    db.collection("user_preferences").document(user_number).set({
        "personality": voice_type,
        "updated_at": firestore.SERVER_TIMESTAMP
    }, merge=True)
    
    # Different response messages based on the selected voice
    responses = {
        "gentle": "Voice set to gentle! I'll be supportive and kind as we manage your spending together.",
        "strict": "Voice set to strict. I'll be direct and clear about your spending habits.",
        "mean": "Voice set to mean. I won't sugarcoat anything when you're wasting money!"
    }
    
    return responses.get(voice_type, f"Voice set to {voice_type}!")

def reset_budget(user_number):
    """
    Resets the user's budget.
    """
    # Delete the budget document
    db.collection("budgets").document(user_number).delete()
    
    # Get the user's personality
    personality = get_user_personality(user_number)
    
    # Different response messages based on the selected voice
    responses = {
        "gentle": "I've reset your budget. You can set a new one by texting 'set budget $X'.",
        "strict": "Budget reset. Set a new budget immediately with 'set budget $X'.",
        "mean": "Budget deleted. Let me guess, you blew through it too fast? Set a new one or don't - your financial disaster either way."
    }
    
    return responses.get(personality, "Your budget has been reset. Text 'set budget $X' to set a new one.")

def set_store_budget(user_number, store, amount):
    """
    Sets a budget for a specific store.
    """
    try:
        # Convert to float and validate
        amount = float(amount)
        if amount <= 0:
            return "Store budget amount must be positive. Please try again."
        
        # Standardize store name (lowercase, strip extra spaces)
        store = store.lower().strip()
        
        # Save the store budget to Firestore
        db.collection("store_budgets").add({
            "phone": user_number,
            "store": store,
            "amount": amount,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        
        # Get the user's personality
        personality = get_user_personality(user_number)
        
        # Different response messages based on the selected voice
        responses = {
            "gentle": f"Great! I've set your {store} budget to ${amount:.2f}. I'll help you keep track of your spending there.",
            "strict": f"Store budget set: {store} - ${amount:.2f}. Stay within this limit.",
            "mean": f"${amount:.2f} for {store}? Good luck with that. We both know what happened last time."
        }
        
        return responses.get(personality, f"I've set your {store} budget to ${amount:.2f}.")
        
    except (ValueError, TypeError):
        return "I couldn't understand that amount. Please try something like 'set Target budget $100'."

def track_store_purchase(user_number, store, item, amount):
    """
    Records a purchase at a specific store and checks it against the store budget.
    """
    try:
        # Convert to float and validate
        amount = float(amount)
        if amount <= 0:
            return "Purchase amount must be positive. Please try again."
        
        # Standardize store name
        store = store.lower().strip()
        
        # Save the purchase to Firestore with store info
        db.collection("purchases").add({
            "phone": user_number,
            "item": item,
            "store": store,
            "amount": amount,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        
        # Get the store budget
        store_budgets = db.collection("store_budgets").where("phone", "==", user_number).where("store", "==", store).limit(1).stream()
        store_budget_doc = next(store_budgets, None)
        
        # Get the user's personality
        personality = get_user_personality(user_number)
        
        if store_budget_doc:
            store_budget = store_budget_doc.to_dict().get("amount", 0)
            
            # Get purchases from this store
            store_purchases = db.collection("purchases").where("phone", "==", user_number).where("store", "==", store).stream()
            store_total = sum(purchase.to_dict().get("amount", 0) for purchase in store_purchases)
            
            remaining = store_budget - store_total
            
            # Create responses based on personality and budget status
            if remaining < 0:
                # Over budget responses
                responses = {
                    "gentle": f"I've recorded your {item} purchase at {store} for ${amount:.2f}. You've now spent ${store_total:.2f} there, which is ${abs(remaining):.2f} over your ${store_budget:.2f} budget for this store.",
                    "strict": f"Purchase recorded: {item} at {store} for ${amount:.2f}. WARNING: You are ${abs(remaining):.2f} OVER your store budget of ${store_budget:.2f}.",
                    "mean": f"${abs(remaining):.2f} over budget at {store}. Why am I not surprised? At this point just hand them your whole paycheck."
                }
            else:
                # Under budget responses
                responses = {
                    "gentle": f"Great job! I've recorded your {item} purchase at {store} for ${amount:.2f}. You've spent ${store_total:.2f} of your ${store_budget:.2f} {store} budget. You have ${remaining:.2f} left to spend there!",
                    "strict": f"Purchase logged: {item} at {store} for ${amount:.2f}. Current status: ${store_total:.2f} spent, ${remaining:.2f} remaining from your store budget.",
                    "mean": f"${amount:.2f} at {store}? Fine. You've got ${remaining:.2f} left there. Try not to blow through it all at once."
                }
                
            return responses.get(personality, f"I've recorded your {item} purchase at {store} for ${amount:.2f}. You've spent ${store_total:.2f} of your ${store_budget:.2f} {store} budget.")
        else:
            # No store budget set responses
            responses = {
                "gentle": f"I've recorded your {item} purchase at {store} for ${amount:.2f}. You haven't set a budget for {store} yet. Would you like to set one?",
                "strict": f"Purchase logged: {item} at {store} for ${amount:.2f}. NOTE: No budget set for this store. Set one with 'set {store} budget $X'.",
                "mean": f"Another ${amount:.2f} at {store} with no budget? At least commit to a spending limit before you waste your money."
            }
            
            return responses.get(personality, f"I've recorded your {item} purchase at {store} for ${amount:.2f}. You haven't set a budget for {store}.")
            
    except (ValueError, TypeError):
        return "I couldn't understand that amount. Please try something like 'bought shirt at Target for $25'."

def set_period_budget(user_number, period, amount):
    """
    Sets a budget for a specific time period (day, week, month).
    """
    try:
        # Convert to float and validate
        amount = float(amount)
        if amount <= 0:
            return "Budget amount must be positive. Please try again."
        
        # Validate time period
        valid_periods = ["daily", "weekly", "monthly", "day", "week", "month", "this week", "this month", "today"]
        if period.lower() not in valid_periods:
            return f"I don't recognize '{period}' as a valid time period. Please use daily, weekly, or monthly."
        
        # Standardize period format
        standardized_period = period.lower()
        if any(p in standardized_period for p in ["day", "daily", "today"]):
            standardized_period = "daily"
        elif any(p in standardized_period for p in ["week", "weekly", "this week"]):
            standardized_period = "weekly"
        elif any(p in standardized_period for p in ["month", "monthly", "this month"]):
            standardized_period = "monthly"
        else:
            return f"I don't recognize '{period}' as a valid time period. Please use daily, weekly, or monthly."
        # If category is None, check if there's one in the period text
        if category is None:
            # This would be from your AI analysis
            category = None

        # Document structure to save
        budget_data = {
            f"{standardized_period}_updated_at": firestore.SERVER_TIMESTAMP
        }

        # Set the overall period budget if no category
        if not category:
            budget_data[f"{standardized_period}_amount"] = amount
        else:
            # If there's a category, save that with the period
            category = category.lower().strip()
            budget_data[f"{standardized_period}_{category}_amount"] = amount
            budget_data[f"{standardized_period}_{category}_updated_at"] = firestore.SERVER_TIMESTAMP
        
        # Save to Firestore
        db.collection("period_budgets").document(user_number).set(
            budget_data, merge=True
        )
        
        # Get the user's personality
        personality = get_user_personality(user_number)


        
        # Save the period budget to Firestore
        db.collection("period_budgets").document(user_number).set({
            period: amount,
            f"{period}_updated_at": firestore.SERVER_TIMESTAMP
        }, merge=True)
        
        # Get the user's personality
        personality = get_user_personality(user_number)
        
       # Build response message
        if category:
            budget_description = f"{category} budget for {standardized_period.replace('ly', '')}"
        else:
            budget_description = f"{standardized_period} budget"
        
        # Different response messages based on the selected voice
        responses = {
            "gentle": f"Wonderful! I've set your {budget_description} to ${amount:.2f}. I'll help you stay on track!",
            "strict": f"{budget_description.capitalize()} set: ${amount:.2f}. I will monitor your spending accordingly.",
            "mean": f"${amount:.2f} for {budget_description}? Let's see how fast you blow through that."
        }
        
        return responses.get(personality, f"I've set your {period} budget to ${amount:.2f}.")
        
    except (ValueError, TypeError):
        return "I couldn't understand that amount. Please try something like 'set weekly budget $200'."



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
    
    # Special case for voice change requests without specifying which voice
    if ("change voice" in incoming_msg.lower() or "change my voice" in incoming_msg.lower() or 
        "set voice" in incoming_msg.lower()) and not any(voice in incoming_msg.lower() for voice in ["gentle", "strict", "mean"]):
        # If they just asked to change voice without specifying which one
        response_text = "Which voice would you like? Options are: gentle, strict, or mean."
        resp = MessagingResponse()
        resp.message(response_text)
        return Response(str(resp), content_type="application/xml")
    
    # Use AI to analyze the message
    ai_analysis = analyze_message_with_ai(incoming_msg, user_number)
    intent = ai_analysis["intent"]
    extracted_data = ai_analysis["data"]

    # Create a response based on the intent
    if intent == "set_budget":
        if "amount" in extracted_data:
            # Use the amount extracted by AI
            response_text = set_budget_with_amount(user_number, extracted_data["amount"])
        else:
            # Fall back to regex extraction
            response_text = set_budget(user_number, incoming_msg)
            
    elif intent == "track_purchase":
        if "item" in extracted_data and "amount" in extracted_data:
            category = extracted_data.get("category")
            if category:
                # Track purchase with category
                response_text = track_purchase_with_category(
                    user_number, 
                    extracted_data["item"], 
                    extracted_data["amount"],
                    category
                )
            elif "store" in extracted_data:
                # Track store-specific purchase
                response_text = track_store_purchase(
                    user_number, 
                    extracted_data["store"], 
                    extracted_data["item"], 
                    extracted_data["amount"]
                )
            else:
                # Use the item and amount extracted by AI
                response_text = track_purchase_with_data(
                    user_number, 
                    extracted_data["item"], 
                    extracted_data["amount"]
                )
        else:
            # Fall back to regex extraction
            response_text = track_purchase(user_number, incoming_msg)
            
    elif intent == "set_voice":
        if "voice_type" in extracted_data:
            # Use the voice type extracted by AI
            response_text = set_voice_with_type(user_number, extracted_data["voice_type"])
        else:
            # Fall back to regex extraction
            response_text = set_voice(user_number, incoming_msg)
            
    elif intent == "reset_budget":
        response_text = reset_budget(user_number)
        
    elif intent == "set_store_budget":
        if "store" in extracted_data and "amount" in extracted_data:
            response_text = set_store_budget(
                user_number, 
                extracted_data["store"], 
                extracted_data["amount"]
            )
        else:
            response_text = "I couldn't understand the store or amount. Please try something like 'set Target budget $100'."
            
    elif intent == "set_period_budget":
        if "period" in extracted_data and "amount" in extracted_data:
            response_text = set_period_budget(
                user_number, 
                extracted_data["period"], 
                extracted_data["amount"]
            )
        else:
            response_text = "I couldn't understand the time period or amount. Please try something like 'set weekly budget $200'."
            
    elif intent == "help":
        response_text = get_help_message(user_number)
        
    elif intent == "get_spending_summary":
        # Get spending summary
        time_period = extracted_data.get("time_period", "all")
        response_text = get_spending_for_period(user_number, time_period)
        
    else:
        # Check if it seems like they're trying to use a specific format but failing
        if any(format_word in incoming_msg.lower() for format_word in ["set budget", "bought", "spent", "set voice"]):
            intent_guess = "unknown"
            if "budget" in incoming_msg.lower():
                intent_guess = "set_budget"
            elif any(word in incoming_msg.lower() for word in ["bought", "spent", "purchase"]):
                intent_guess = "track_purchase"
            elif "voice" in incoming_msg.lower():
                intent_guess = "set_voice"
            
            response_text = handle_format_confusion(user_number, intent_guess)
        else:
            # Regular unknown intent response
            personality = get_user_personality(user_number)
        
            unknowns = {
                "gentle": "I'm not sure what you're asking. Remember, you can talk to me naturally! Type 'help' to see what I can do! <3",
                "strict": "Unrecognized input. Natural language is accepted. Type 'help' for examples.",
                "mean": "What? That made no sense. Talk normally. Type 'help' if you're confused."
            }
        
            response_text = unknowns.get(personality, "I dont have a response for that yet hehe. Type 'help' for the commands.")
    # Reply to user
    resp = MessagingResponse()
    resp.message(response_text)
    return Response(str(resp), content_type="application/xml")




if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
