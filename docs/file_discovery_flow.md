# File Discovery & Agent Coordination Flow

```mermaid
flowchart TD
    A([New Documents & Emails]) --> B[Scheduler Service<br/>interval trigger]
    B --> C[Agent Coordinator<br/>"new items available"]

    subgraph Discovery Queue
        C --> D[File Discovery Tool<br/>(Drive & Email scan)]
        D --> E{Already processed?}
        E -- Yes --> F[Log discovery<br/>update history only]
        E -- No --> G[Enqueue with metadata<br/>& discovery time]
    end

    G --> H[Persist queue +<br/>processing history]

    subgraph Per-Item Processing
        H --> I[Download content<br/>(Drive/Email service)]
        I --> J[Extraction Agent]
        J --> K[Storage Agent<br/>(FAISS & DB staging)]
        K --> L[HDL Agent / Slack<br/>review request]
        L --> M{HDL decision}
        M -- Approved --> N[Finalize DB records<br/>move files, mark processed]
        M -- Corrections --> O[Apply corrections<br/>Storage & DB update]
        M -- Rejected --> P[Mark rejected<br/>queue for follow-up]
    end

    N & O & P --> Q[Update processing history<br/>for dedupe]
    Q --> R[[Ready for next scan]]
```


