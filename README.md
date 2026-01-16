# Proton Email Sorter Agent

This agent automatically reads your unread Proton Mail emails (via Proton Mail Bridge) and uses Gemini AI to categorize them into folders.

## Prerequisites

1.  **Proton Mail Bridge**: You must have the [Proton Mail Bridge](https://proton.me/mail/bridge) installed and running on your Mac. 
    - Open Bridge, go to **Settings** -> **Mailbox configuration**.
    - You will see your IMAP/SMTP credentials (Username and Password). These are *different* from your Proton login password.
2.  **Gemini API Key**: Get one from [Google AI Studio](https://aistudio.google.com/).

## Setup

1.  Navigate to this directory:
    ```bash
    cd /Users/alastairgrant/.gemini/antigravity/scratch/proton-email-agent
    ```
2.  Create a `.env` file from the example:
    ```bash
    cp .env.example .env
    ```
3.  Open `.env` and fill in your details:
    - `PROTON_USERNAME`: Your Bridge username.
    - `PROTON_PASSWORD`: Your Bridge password.
    - `GEMINI_API_KEY`: Your Gemini API key.
4.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the agent:
```bash
python agent.py
```

The agent will check your inbox every 60 seconds (configurable in `agent.py`) and move any unread emails to categorized folders.

## How it works

1. It searches for emails with the `UNSEEN` flag in your `INBOX`.
2. It sends the subject, sender, and a snippet of the body to Gemini.
3. Gemini returns a category name (e.g., 'Invoices', 'Newsletters').
4. The agent creates the folder if it doesn't exist and moves the email there.
