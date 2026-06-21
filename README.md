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
pip install -r apps/api/requirements.txt
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
├── apps/
│   └── api/                 # FastAPI service (Cloud Run)
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/
│           ├── api/
│           ├── agents/
│           ├── core/
│           ├── services/
│           └── main.py
├── config/
├── tests/
├── alembic/                 # DB migrations
├── docs/                    # Architecture, ADRs, PRD, archive
├── cloudbuild.yaml          # Cloud Build (builds apps/api/)
├── .env                     # Local secrets (gitignored)
└── README.md
```

To run the API locally:
```bash
cd apps/api && python -m uvicorn app.main:app --reload --port 8081
```

### 4.4 Database Schema Requirements

#### 4.4.1 Core Tables

1. **Tasks Table**
   - Primary key: Task ID (Txxx)
   - Fields:
     - Description (Text)
     - Type (Enum: Payment, Reminder, etc.)
     - Entity (Foreign Key to Entities)
     - Due Date (Date)
     - Frequency (Text)
     - Status (Enum: Pending, Completed, etc.)
     - Priority (Enum: High, Medium, Low)
     - Notes (Text)

2. **Entities Table**
   - Primary key: Entity ID (Exxx)
   - Fields:
     - Name (Text)
     - Category (Enum: Education, Finance, etc.)
     - Contact Info (Text)
     - Notes (Text)

3. **Obligations Table**
   - Primary key: Obligation ID (Oxxx)
   - Fields:
     - Description (Text)
     - Related Entity (Foreign Key to Entities)
     - Frequency (Text)
     - Trigger Date (Date)
     - Reminder Lead Time (Integer, days)
     - Last Completed (Date)

4. **Authorizations Table**
   - Primary key: Auth ID (Axxx)
   - Fields:
     - Entity (Foreign Key to Entities)
     - Task Type (Enum: Payment, Access, etc.)
     - Level (Enum: Limited, Full, etc.)
     - Expiry (Date)
     - Notes (Text)

#### 4.4.2 Relationships
- Tasks → Entities (Many-to-One)
- Obligations → Entities (Many-to-One)
- Authorizations → Entities (Many-to-One)
- Tasks → Obligations (Optional Many-to-One)

#### 4.4.3 Implementation Phases
1. **Phase 1: Core Structure**
   - Basic table creation
   - Primary relationships
   - Essential fields

2. **Phase 2: Extended Features**
   - Additional fields
   - Complex relationships
   - Indexing and optimization

3. **Phase 3: Advanced Features**
   - Audit logging
   - Version control
   - Advanced querying capabilities

#### 4.4.4 Data Integrity Rules
1. **Entity Management**
   - Unique Entity IDs
   - Required contact information
   - Category validation

2. **Task Management**
   - Valid due dates
   - Status transitions
   - Priority levels

3. **Obligation Tracking**
   - Valid frequency patterns
   - Trigger date validation
   - Completion tracking

4. **Authorization Control**
   - Expiry date validation
   - Level restrictions
   - Entity association validation
