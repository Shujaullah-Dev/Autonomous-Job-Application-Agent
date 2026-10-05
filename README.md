# Autonomous Job-Application Agent
---

## 1. System Architecture Diagram

The diagram below outlines the full-stack architecture, including the React dashboard, FastAPI backend services, LangGraph agent pipelines, database layer, Playwright automation module, and background workers.

```mermaid
graph TB
    subgraph Client ["Frontend"]
        Dashboard["Web Dashboard\n(React + TypeScript)"]
    end

    subgraph Backend ["FastAPI Backend Services"]
        API["FastAPI API Gateway\n(Auth • Jobs • Applications)"]
    end

    subgraph Core ["Core Services & Storage"]
        DB[(PostgreSQL Database)]
        Storage["File Storage\n(PDFs & Artifacts)"]
        Engine["Agent Engine\n(LangGraph)"]
    end

    subgraph Pipeline ["AI Agent Pipeline"]
        Parser["JD Parser"] --> Matcher["Matcher Engine"]
        Matcher --> Writer["Resume/Cover Writer"]
        Writer --> Auditor["Compliance Auditor"]
        Auditor --> Interview["Interview Prep Agent"]
    end

    subgraph Automation ["Browser & Submission Layer"]
        Playwright["Playwright Automation"]
        Approval{{"Human Approval\n(Checkpoint)"}}
        Portal["External Job Portals"]
    end

    subgraph Workers ["Background Workers (Celery / Redis)"]
        EmailMon["Email Monitor"]
        Logger["Application Logger"]
        ResGen["Resume Generator"]
        Notif["Notifications Engine"]
    end

    %% Connections
    Dashboard -->|REST API / WebSocket Live Data| API
    API --> DB
    API --> Storage
    API --> Engine
    
    Engine --> Pipeline
    Pipeline --> Playwright
    
    Playwright --> Approval
    Approval -->|Approved Submission| Portal
    
    %% Background Workers Integration
    Workers -.->|Async Tasks| API
    Workers -.->|Email Tracking| DB
    Workers -.->|Real-time Status Updates| Dashboard
```

---
