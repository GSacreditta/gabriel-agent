## Current Architecture (Implemented)

```mermaid
flowchart TD
    subgraph User Interface
        Slack[Slack Interface]
    end

    subgraph Core System
        API[FastAPI Backend]
        AI[AI Processing]
        DB[(ChromaDB)]
        Drive[Google Drive]
    end

    subgraph Document Processing
        PDF[PDF Processing]
        OCR[OCR Engine]
        Vector[Vector Embeddings]
    end

    subgraph Task Management
        Tasks[Task Engine]
        Scheduler[Scheduler]
        Notifications[Notifications]
    end

    %% Main flow
    Slack -->|User Commands| API
    API -->|Process Request| AI
    AI -->|Store Vectors| DB
    AI -->|Process Documents| Document Processing
    AI -->|Manage Tasks| Task Management

    %% Document Processing flow
    Document Processing -->|Store Files| Drive
    Document Processing -->|Generate Embeddings| Vector
    Vector -->|Store| DB

    %% Task Management flow
    Task Management -->|Schedule| Scheduler
    Scheduler -->|Send Updates| Notifications
    Notifications -->|Send to User| Slack

    %% External Services
    OpenAI[OpenAI API]
    AI -->|LLM Processing| OpenAI

    %% Styling
    classDef primary fill:#f9f,stroke:#333,stroke-width:2px
    classDef secondary fill:#bbf,stroke:#333,stroke-width:2px
    classDef external fill:#bfb,stroke:#333,stroke-width:2px

    class Slack,API primary
    class AI,DB,Drive secondary
    class OpenAI external
```

## Proposed Tool-Based Agent Architecture (As Proposed)

```mermaid
flowchart TD
    subgraph "Human Interface"
        Slack[Slack Interface]
    end

    subgraph "Agent Orchestration Layer (As Proposed)"
        StateManager[State Manager]
        AgentCoordinator[Agent Coordinator]
    end

    subgraph "Agent Tools (As Proposed)"
        FileAgent[File Management Agent]
        ExtractionAgent[Extraction Agent]
        StorageAgent[Storage Agent - Vector]
        HDLAgent[HDL Agent - Human Interface]
        DBAgent[DB Agent]
    end

    subgraph "External Services"
        GoogleDrive[Google Drive]
        ChromaDB[(ChromaDB)]
        PostgreSQL[(PostgreSQL)]
        OpenAI[OpenAI API]
    end

    %% Human Interface Flow
    Slack <-->|Commands & Reviews| HDLAgent

    %% Agent Coordination
    StateManager --> AgentCoordinator
    AgentCoordinator --> FileAgent
    AgentCoordinator --> ExtractionAgent
    AgentCoordinator --> StorageAgent
    AgentCoordinator --> HDLAgent
    AgentCoordinator --> DBAgent

    %% Agent Interactions (As Proposed)
    FileAgent <-->|Entity Matching| DBAgent
    ExtractionAgent -->|Extracted Content| StorageAgent
    ExtractionAgent -->|Review Requests| HDLAgent
    HDLAgent -->|File Operations| FileAgent
    StorageAgent -->|Metadata| DBAgent

    %% External Service Connections
    FileAgent <--> GoogleDrive
    StorageAgent <--> ChromaDB
    DBAgent <--> PostgreSQL
    ExtractionAgent --> OpenAI

    %% Styling
    classDef proposed fill:#fff2cc,stroke:#d6b656,stroke-width:2px
    classDef implemented fill:#d5e8d4,stroke:#82b366,stroke-width:2px
    classDef external fill:#f8cecc,stroke:#b85450,stroke-width:2px

    class FileAgent,ExtractionAgent,StorageAgent,HDLAgent,DBAgent,StateManager,AgentCoordinator proposed
    class Slack implemented
    class GoogleDrive,ChromaDB,PostgreSQL,OpenAI external
```

### Database Schema (As Proposed)

```mermaid
erDiagram
    ENTITIES {
        string entity_id PK
        string name
        string category
        text contact_info
        text notes
    }
    
    TASKS {
        string task_id PK
        text description
        string type
        string entity_id FK
        date due_date
        string frequency
        string status
        datetime created_at
    }
    
    OBLIGATIONS {
        string obligation_id PK
        text description
        string entity_id FK
        string frequency
        date trigger_date
        int reminder_lead_time
        date last_completed
    }
    
    AUTHORIZATIONS {
        string auth_id PK
        string entity_id FK
        string task_type
        string author
        date expiry
        string slack_link
        text description
    }
    
    DOCUMENT_METADATA {
        string doc_id PK
        string entity_id FK
        string file_name
        date issue_date
        text subject
        text summary
        string document_type
        string drive_link
        datetime processing_time
        text confidence_scores
    }

    ENTITIES ||--o{ TASKS : "has"
    ENTITIES ||--o{ OBLIGATIONS : "has"
    ENTITIES ||--o{ AUTHORIZATIONS : "has"
    ENTITIES ||--o{ DOCUMENT_METADATA : "owns"
```

## Implementation Status Legend
- 🟢 **Implemented** - Currently working in production
- 🟡 **As Proposed** - Planned for implementation
- 🔴 **Not Implemented** - Future consideration

### Current Implementation Status

#### Core Components
- 🟢 FastAPI Backend
- 🟢 Slack Integration
- 🟢 Google Drive Service
- 🟢 Document Processing Service
- 🟢 OCR Service
- 🟢 ChromaDB Vector Storage
- 🔴 PostgreSQL Database

#### Agent Tools (As Proposed)
- 🟡 File Management Agent
- 🟡 Extraction Agent
- 🟡 Storage Agent (Vector)
- 🟡 HDL Agent (Human Interface)
- 🟡 DB Agent

#### State Management (As Proposed)
- 🟡 AgentState Class
- 🟡 StateManager Service
- 🟡 StatefulBaseTool Base Class

#### Database Schema (As Proposed)
- 🟡 Entities Table
- 🟡 Tasks Table
- 🟡 Obligations Table
- 🟡 Authorizations Table
- 🟡 Document Metadata Table 