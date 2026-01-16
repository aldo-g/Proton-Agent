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

# Use a model confirmed to exist in your environment
MODEL_NAME = 'models/gemini-2.0-flash'

try:
    model = genai.GenerativeModel(MODEL_NAME)
except Exception as e:
    print(f"Could not initialize {MODEL_NAME}, trying fallback. Error: {e}")
    model = genai.GenerativeModel('models/gemini-flash-latest')

def get_email_category(subject, sender, body_snippet):
    prompt = f"""
    You are an AI email sorter. Categorize the following email into a single folder name.
    
    If you are unsure, if it's a notification from a system, or if it doesn't fit a clear category, return 'SKIP'.

    RULES:
    - Use ONE or TWO words max.
    - No special characters (only letters and underscores).
    - 'Invoices' for receipts or tax documents.
    - 'Newsletters' for marketing/bulk/subscriptions.
    - 'Personal' for direct personal mail from humans.
    - 'Work' for professional/job-related items.
    - 'Travel' for bookings/itineraries.

    Email Subject: {subject}
    From: {sender}
    Content Snippet: {body_snippet}

    Return ONLY the folder name or 'SKIP'. Do not include any other text.
    """
    try:
        response = model.generate_content(prompt)
        category = response.text.strip().replace(' ', '_').replace('"', '').replace("'", "")
        # Remove trailing/leading underscores or weird chars
        category = ''.join(e for e in category if e.isalnum() or e == '_')
        
        if category.upper() == 'SKIP' or len(category) < 2:
            return None
            
        return f"Folders/{category}"
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        return None

def process_emails():
    print(f"Connecting to {HOST}:{PORT}...")
    try:
        with IMAPClient(HOST, port=PORT, ssl=False) as client:
            client.login(USERNAME, PASSWORD)
            client.select_folder('INBOX')

            # Search for emails
            messages = client.search([SEARCH_CRITERIA])
            print(f"Found {len(messages)} emails matching criteria '{SEARCH_CRITERIA}'.")

            for msg_id, data in client.fetch(messages, ['ENVELOPE', 'BODY.PEEK[]']).items():
                try:
                    envelope = data[b'ENVELOPE']
                    subject = envelope.subject.decode() if envelope.subject else "No Subject"
                    sender = str(envelope.from_[0])
                    
                    # Extract body snippet
                    raw_email = data.get(b'BODY.PEEK[]') or data.get(b'BODY[]') or data.get(b'RFC822')
                    if not raw_email:
                        continue

                    msg = email.message_from_bytes(raw_email, policy=policy.default)
                    body = ""
                    try:
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_content()
                                    break
                        else:
                            body = msg.get_content()
                    except:
                        body = "Could not parse body"
                    
                    snippet = str(body)[:500]
                    
                    print(f"Processing: {subject} from {sender}")
                    category = get_email_category(subject, sender, snippet)
                    
                    if not category:
                        print(f"Skipping: No clear category for '{subject}'. Keeping in Inbox.")
                        continue

                    print(f"Category identified: {category}")

                    # Create folder if it doesn't exist
                    try:
                        # Standardize folder name to Title Case like 'Folders/Work'
                        parts = category.split('/')
                        if len(parts) > 1:
                            parts[1] = parts[1].capitalize()
                            category = '/'.join(parts)
                        
                        if not client.folder_exists(category):
                            print(f"Creating folder: {category}")
                            client.create_folder(category)
                    except Exception as fe:
                        print(f"Could not create folder {category}: {fe}. Keeping in Inbox.")
                        continue

                    # Explicitly ensure the email is marked as UNREAD before moving
                    client.remove_flags([msg_id], [b'\\Seen'])
                    
                    # Move email
                    client.move([msg_id], category)
                    print(f"Moved email {msg_id} to {category} (marked as UNREAD)")
                except Exception as ee:
                    print(f"Error processing specific email {msg_id}: {ee}")
                    continue

    except Exception as e:
        print(f"A connection error occurred: {e}")

if __name__ == "__main__":
    if not all([USERNAME, PASSWORD, GEMINI_API_KEY]):
        print("Please set PROTON_USERNAME, PROTON_PASSWORD, and GEMINI_API_KEY in your .env file.")
    else:
        while True:
            process_emails()
            print(f"Sleeping for {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)
