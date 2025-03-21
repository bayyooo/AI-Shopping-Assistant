# AI-Shopping-Assistant
## 📌 Sign Up for SmartShop AI

To start using the SmartShop AI Shopping Assistant, sign up using the link below:

[🛍️ Sign Up for SmartShop AI](https://docs.google.com/forms/d/e/1FAIpQLSdCXRf9NGCWu7UDbD9PDn_tncDXlH1Ob3kdcfVFhPOd14ZZPw/viewform?usp=preview)

By signing up, you’ll receive AI-powered shopping reminders, budget tracking, and purchase insights via SMS.

- Reply **HELP** for commands.
- Reply **STOP** to unsubscribe anytime.

- # 🛍️ AI Shopping Assistant – MVP README

## Project Overview
An AI-powered SMS-based shopping assistant that helps users track spending, set budgets, and receive reminders. Built to be convenient, hands-free, and personalized. Users can interact through SMS and voice commands (Siri/Alexa).

---

## MVP Goal
Launch a functional MVP in **6 weeks** using SMS, Flask backend, GPT-4 for AI logic, and Firebase/PostgreSQL for data storage.

---

## Tech Stack
- **Backend:** Flask (Python)
- **AI:** OpenAI GPT-4
- **SMS Integration:** Twilio API
- **Database:** Firebase or PostgreSQL
- **Voice Commands:** Siri Shortcuts, Alexa Skills API (basic voice triggers)
- **Deployment:** Ngrok (local), AWS/GCP (future)
- **Version Control:** GitHub
- **Project Management:** Jira

---

##  MVP Features
### 1. SMS AI Assistant
- Users can text: "I’m going to Target"
- AI replies asking what they’re buying and responds with reminders

### 2. Budget Setting & Alerts
- Text: "Set $50 budget for Ulta"
- AI stores the budget and sends alerts when users go over

### 3. Manual Purchase Logging
- Text: "Bought mascara for $12"
- AI logs it and reminds users later

### 4. Memory & Purchase History
- AI remembers recent purchases
- Gives contextual feedback: “Didn’t you just buy that?”

### 5. Custom AI Personality & Text Frequency
- Choose tone: Gentle / Mean / Tough Love
- Set # of texts per trip (e.g., 1-3 nudges)
---

##  Development Timeline
### Week 1 – Setup & Planning
- ✅ Twilio + OpenAI setup
- ⬜ Database config
- ⬜ Flask API
- ⬜ Ngrok testing
- ✅ GitHub + Jira integration

### Week 2 – SMS Chatbot Features
- ⬜ Budget setting via text
- ⬜ Manual logging of purchases
- ⬜ Basic AI nudge responses

### Week 3 – AI Memory
- ⬜ Store purchase history
- ⬜ Reference past purchases
- ⬜ Begin spending pattern detection

### Week 4 – Voice Shortcut Integration
- ⬜ Siri Shortcuts setup
- ⬜ Voice triggers to text AI

### Week 5 – Optional: Receipt Scanning
- ⬜ Integrate Google Vision API for OCR
- ⬜ Parse receipt text to store purchases

### Week 6 – Testing & Beta
- ⬜ End-to-end testing
- ⬜ Invite 5 users to test
- ⬜ Debug + refine AI logic

---

## Post-MVP (Phase 2 Features)
-  GPS geofencing
-  Receipt scanner auto-logging
-  Mobile app w/ dashboards
-  Full Alexa integration
-  Visual analytics and reporting

---

##  Developer Notes
- Start with Twilio SMS webhooks → Flask API endpoint
- Use GPT-4 to parse user intent (shopping list, budgets, etc.)
- Store/retrieve data from Firebase/PostgreSQL
- Use Ngrok to test endpoints locally before deployment

---

## Project Links
- [GitHub Repo](#)
- [Jira Board Template](#)
- [OpenAI Setup Docs](https://platform.openai.com/docs)
- [Twilio SMS API Docs](https://www.twilio.com/docs/sms)

---

## Built With Intention
Created for users who hate logging things manually. This assistant keeps them accountable while shopping without ever needing to open an app. SMS-first = convenience-first.

