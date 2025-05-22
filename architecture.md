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