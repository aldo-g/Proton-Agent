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

def get_email_category(subject, sender, body_snippet, existing_folders=None):
    folders_context = ""
    if existing_folders:
        folders_context = "\nEXISTING FOLDERS (Reuse these if they fit):\n- " + "\n- ".join(existing_folders)

    prompt = f"""
    You are an AI email sorter. Categorize the following email into a hierarchical folder path.
    {folders_context}

    SPECIAL RULES: 
    1. If the email is obvious junk or promotional spam, return 'REVIEW'.
    2. If the email is from a platform you are ACTIVELY working on (like Alignerr, Labelbox, Hubstaff, etc.), file it under 'Work/Notifications' or 'Work/Opportunities'. DO NOT put these in REVIEW.

    If you are unsure, return 'SKIP'.

    RULES:
    - Use ONE or TWO words per level, separate levels with '/'.
    - Use normal spaces between words.
    - LOOK AT THE EXISTING FOLDERS LIST ABOVE. If an existing folder is a good match, use it EXACTLY as written (without the 'Folders/' prefix).
    
    EXAMPLES:
    - Job Alerts from Boards (LinkedIn alerts, Indeed): 'Work/Opportunities/Job Boards'
    - Cold emails/Direct contact from Recruiters: 'Work/Opportunities/Recruiters'
    - Career Feedback (rejections, interview requests, status updates): 'Work/Feedback'
    - Certification Vouchers (Microsoft exam codes): 'Work/Certifications'
    - Invoices/Receipts (Group by merchant): 'Finances/Invoices/MERCHANT NAME' (e.g., 'Finances/Invoices/99 Bikes')
    - Travel & Holidays (By destination): 'Travel/LOCATION NAME' (e.g., 'Travel/Tasmania')
    - Notifications (System alerts, app updates): 'Notifications'
    - Bank/Government/Legal (Use full names): 'Official/Home Affairs Australia' or 'Official/Gemeente Amsterdam'
    - Spam/Junk/Redundant: 'REVIEW'

    Email Subject: {subject}
    From: {sender}
    Content Snippet: {body_snippet}

    Return ONLY the folder path or 'REVIEW' or 'SKIP'. No other text.
    """
    try:
        response = model.generate_content(prompt)
        category = response.text.strip().replace('"', '').replace("'", "")
        
        if category.upper() == 'SKIP' or len(category) < 2:
            return None
        
        if category.upper() == 'REVIEW':
            return 'Folders/Review'
            
        # Clean up weird characters but keep spaces and slashes
        category = ''.join(e for e in category if e.isalnum() or e in ' /_-')
        
        if category.startswith('Folders/'):
            return category
        return f"Folders/{category}"
    except Exception as e:
        if "429" in str(e):
            print("Gemini Rate Limit reached (429).")
        else:
            print(f"Error calling Gemini: {e}")
        return None

def process_emails():
    print(f"Connecting to {HOST}:{PORT}...")
    try:
        with IMAPClient(HOST, port=PORT, ssl=False) as client:
            client.login(USERNAME, PASSWORD)
            client.select_folder('INBOX')

            # Fetch existing Folders to help Gemini reuse them
            raw_folders = client.list_folders()
            existing_folders = []
            for flags, delimiter, name in raw_folders:
                if name.startswith('Folders/'):
                    # Strip 'Folders/' for the AI but keep for our reference if needed
                    existing_folders.append(name.replace('Folders/', ''))
            
            print(f"Known folders: {', '.join(existing_folders)}")

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
                    category = get_email_category(subject, sender, snippet, existing_folders=existing_folders)
                    
                    if not category:
                        print(f"Skipping: No clear category/rate limited for '{subject}'. Keeping in Inbox.")
                        continue

                    # Standardize folder name: Title Case for every part except 'Folders'
                    # e.g. 'official/home affairs australia' -> 'Folders/Official/Home Affairs Australia'
                    parts = category.split('/')
                    standardized_parts = [parts[0]] # Keep 'Folders' as is
                    for p in parts[1:]:
                        # capitalize each word, e.g. 'home affairs' -> 'Home Affairs'
                        # Use a space as joiner now
                        standardized_parts.append(' '.join(word.capitalize() for word in p.replace('_', ' ').split()))
                    category = '/'.join(standardized_parts)

                    print(f"Category identified: {category}")

                    # Create folder hierarchy if it doesn't exist
                    try:
                        if not client.folder_exists(category):
                            print(f"Creating folder: {category}")
                            client.create_folder(category)
                            # Update existing_folders list so next email treats it as known
                            short_name = category.replace('Folders/', '')
                            if short_name not in existing_folders:
                                existing_folders.append(short_name)
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
        process_emails()
        print("Done sorting. Inbox is clear.")
