import os
import time
import email
from email import policy
from imapclient import IMAPClient
import google.generativeai as genai
from dotenv import load_dotenv

# Load configuration
load_dotenv()

# Configuration
HOST = os.getenv('PROTON_HOST', '127.0.0.1')
PORT = int(os.getenv('PROTON_PORT', 1143))
USERNAME = os.getenv('PROTON_USERNAME')
PASSWORD = os.getenv('PROTON_PASSWORD')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CHECK_INTERVAL = 60  # seconds
SEARCH_CRITERIA = 'ALL' # Use 'UNSEEN' for only unread, or 'ALL' for everything in the inbox

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_email_category(subject, sender, body_snippet):
    prompt = f"""
    You are an AI email sorter. Categorize the following email into a single folder name (one or two words).
    If it's an invoice, call it 'Invoices'. 
    If it's a newsletter, call it 'Newsletters'.
    If it's personal, call it 'Personal'.
    If it's work-related, call it 'Work'.
    If it doesn't fit these, create a specific but concise folder name.

    Subject: {subject}
    From: {sender}
    Snippet: {body_snippet}

    Return ONLY the folder name. No other text.
    """
    try:
        response = model.generate_content(prompt)
        category = response.text.strip().replace(' ', '_') # Use underscores for IMAP folders if needed
        return category
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        return "Uncategorized"

def process_emails():
    print(f"Connecting to {HOST}:{PORT}...")
    try:
        with IMAPClient(HOST, port=PORT, ssl=False) as client:
            client.login(USERNAME, PASSWORD)
            client.select_folder('INBOX')

            # Search for emails
            messages = client.search([SEARCH_CRITERIA])
            print(f"Found {len(messages)} emails matching criteria '{SEARCH_CRITERIA}'.")

            for msg_id, data in client.fetch(messages, ['ENVELOPE', 'RFC822']).items():
                envelope = data[b'ENVELOPE']
                subject = envelope.subject.decode() if envelope.subject else "No Subject"
                sender = str(envelope.from_[0])
                
                # Extract body snippet
                raw_email = data[b'RFC822']
                msg = email.message_from_bytes(raw_email, policy=policy.default)
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_content()
                            break
                else:
                    body = msg.get_content()
                
                snippet = body[:500] # Limit to 500 chars for the LLM
                
                print(f"Processing: {subject} from {sender}")
                category = get_email_category(subject, sender, snippet)
                print(f"Category: {category}")

                # Create folder if it doesn't exist
                if not client.folder_exists(category):
                    print(f"Creating folder: {category}")
                    client.create_folder(category)

                # Move email
                client.move([msg_id], category)
                print(f"Moved email {msg_id} to {category}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if not all([USERNAME, PASSWORD, GEMINI_API_KEY]):
        print("Please set PROTON_USERNAME, PROTON_PASSWORD, and GEMINI_API_KEY in your .env file.")
    else:
        while True:
            process_emails()
            print(f"Sleeping for {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)
