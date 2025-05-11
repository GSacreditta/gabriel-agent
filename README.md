# Gabriel Agent Task Flow

An AI-powered personal assistant for managing structured tasks, reminders, and file-based workflows.

## MVP Scope

- Document processing (PDF investment reports)
- Automatic folder organization
- Task summarization
- Basic command-line interface

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
- Copy `.env.example` to `.env`
- Fill in required API keys and credentials

## Required API Keys

- Google Cloud API credentials
- Supabase credentials
- OpenAI API key (for LangChain)

## Project Structure

```
gabriel-agent/
├── app/
│   ├── api/
│   ├── core/
│   └── services/
├── config/
├── tests/
├── .env
├── requirements.txt
└── README.md
```
