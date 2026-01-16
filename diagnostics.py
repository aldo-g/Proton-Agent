import os
from imapclient import IMAPClient
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Gemini Config
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

print("--- Gemini Models ---")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error listing models: {e}")

print("\n--- Proton Folders ---")
HOST = os.getenv('PROTON_HOST', '127.0.0.1')
PORT = int(os.getenv('PROTON_PORT', 1143))
USERNAME = os.getenv('PROTON_USERNAME')
PASSWORD = os.getenv('PROTON_PASSWORD')

try:
    with IMAPClient(HOST, port=PORT, ssl=False) as client:
        client.login(USERNAME, PASSWORD)
        folders = client.list_folders()
        for flags, delimiter, name in folders:
            print(f"{name} (Delimiter: {delimiter}, Flags: {flags})")
except Exception as e:
    print(f"Error listing folders: {e}")
