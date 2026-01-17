import os
from imapclient import IMAPClient
from dotenv import load_dotenv

load_dotenv()

# Configuration
HOST = os.getenv('PROTON_HOST', '127.0.0.1')
PORT = int(os.getenv('PROTON_PORT', 1143))
USERNAME = os.getenv('PROTON_USERNAME')
PASSWORD = os.getenv('PROTON_PASSWORD')

def reset_to_inbox():
    print(f"Connecting to {HOST}:{PORT} to reset inbox...")
    try:
        with IMAPClient(HOST, port=PORT, ssl=False) as client:
            client.login(USERNAME, PASSWORD)
            
            # Get all folders
            raw_folders = client.list_folders()
            folders_to_process = []
            
            for flags, delimiter, name in raw_folders:
                # We only want to process folders created by our agent (those in Folders/*)
                if name.startswith('Folders/'):
                    folders_to_process.append(name)
            
            # Sort folders by depth (deepest first) to ensure children are deleted before parents
            folders_to_process.sort(key=lambda x: x.count('/'), reverse=True)
            
            print(f"Found {len(folders_to_process)} folders to process: {', '.join(folders_to_process)}")

            for folder in folders_to_process:
                print(f"--- Processing: {folder} ---")
                try:
                    client.select_folder(folder)
                    messages = client.search(['ALL'])
                    
                    if messages:
                        print(f"Moving {len(messages)} messages to INBOX...")
                        client.move(messages, 'INBOX')
                    
                    # Unselect so we can delete it
                    client.unselect_folder()
                    
                    print(f"Deleting folder: {folder}")
                    client.delete_folder(folder)
                except Exception as fe:
                    print(f"Note: Could not fully process/delete {folder}: {fe}")

            print("\nReset complete. All messages moved to INBOX and custom folders deleted.")
            
            # Optional: Ask user if they want to delete empty folders
            print("Note: The empty folders still exist. You can delete them manually or I can add a cleanup step if needed.")

    except Exception as e:
        print(f"An error occurred during reset: {e}")

if __name__ == "__main__":
    if not all([USERNAME, PASSWORD]):
        print("Please ensure PROTON_USERNAME and PROTON_PASSWORD are set in your .env file.")
    else:
        confirm = input("This will move ALL emails from 'Folders/*' back to your INBOX. Are you sure? (y/n): ")
        if confirm.lower() == 'y':
            reset_to_inbox()
        else:
            print("Reset cancelled.")
