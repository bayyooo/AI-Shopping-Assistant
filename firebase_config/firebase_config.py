import firebase_admin, os, json
from firebase_admin import credentials, firestore

def init_firebase():
    service_account_info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    return firestore.client()


