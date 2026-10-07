# AI Job Agent — System Architecture

## 1. Purpose

The AI Job Agent is an AI-assisted system that helps a user discover relevant employment opportunities, evaluate job fit, prepare application materials, complete permitted application workflows, and track the application lifecycle.

The system is designed around three principles:

1. **Automation where safe and useful**
2. **Human approval for consequential actions**
3. **Modular architecture so components can be replaced independently**

---

# 2. High-Level Architecture

```text
                         ┌─────────────────────┐
                         │       Frontend      │
                         │   React / Next.js   │
                         └──────────┬──────────┘
                                    │
                                    │ HTTP / REST
                                    ▼
                         ┌─────────────────────┐
                         │       FastAPI       │
                         │        API          │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       Resume Service          Job Service        Application Service
              │                     │                     │
              ▼                     ▼                     ▼
        Resume Parser          Job Sources          Application
              │                     │               Workflows
              │                     │                     │
              └──────────────┬──────┴─────────────────────┘
                             │
                             ▼
                    ┌─────────────────────┐
                    │      LangGraph      │
                    │   Agent Workflow    │
                    └──────────┬──────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ▼              ▼              ▼
               LLM          Matching         Tools
                │              │              │
                │              │              │
                └──────────────┼──────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     PostgreSQL      │
                    │       Database      │
                    └──────────┬──────────┘
                               │
                 ┌─────────────┼─────────────┐
                 │             │             │
                 ▼             ▼             ▼
              Redis         Calendar     Notifications
              Worker         Service        Service
```

---

# 3. Main Components

## 3.1 Frontend

The frontend provides the user interface for:

- Account management
- Resume upload
- Resume/profile review
- Job search
- Job recommendations
- Match explanations
- Application material review
- Application approval
- Application tracking
- Interview tracking
- Deadline tracking
- Notifications

Initial frontend technology:

- React
- Next.js
- TypeScript

The frontend communicates with the backend through the FastAPI REST API.

---

# 4. FastAPI Backend

FastAPI is the main backend application.

Responsibilities:

- Authentication
- Resume upload
- Resume management
- Job search
- Job recommendations
- Application management
- Interview management
- Notification management
- Calendar operations
- Agent workflow control

Initial API structure:

```text
/api
├── auth
├── users
├── resumes
├── jobs
├── matches
├── applications
├── interviews
├── notifications
└── health
```

Example endpoints:

```text
GET    /health

POST   /api/resumes
GET    /api/resumes
GET    /api/resumes/{id}

GET    /api/jobs
GET    /api/jobs/{id}

GET    /api/matches
GET    /api/matches/{id}

POST   /api/applications
GET    /api/applications
PATCH  /api/applications/{id}

POST   /api/interviews
GET    /api/interviews

GET    /api/notifications
```

The exact API design may evolve during implementation.

---

# 5. Resume Processing Pipeline

The resume processing pipeline converts an uploaded document into structured candidate information.

```text
Resume File
    │
    ▼
File Validation
    │
    ▼
Text Extraction
    │
    ▼
Raw Resume Text
    │
    ▼
LLM Structured Extraction
    │
    ▼
Pydantic Validation
    │
    ▼
Candidate Profile
```

The candidate profile may contain:

```text
Candidate
├── Name
├── Contact Information
├── Summary
├── Skills
├── Work Experience
├── Education
├── Certifications
├── Projects
├── Languages
├── Location
├── Preferred Locations
├── Preferred Roles
├── Salary Preference
└── Work Authorization
```

The raw extracted text should also be retained so that parsing can be improved later without requiring another upload.

---

# 6. Job Search Architecture

Job sources are abstracted behind a common interface.

```text
                ┌─────────────────┐
                │   JobSource     │
                │   Interface     │
                └────────┬────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       Source A       Source B       Source C
```

Conceptual interface:

```python
class JobSource:
    def search(self, query): ...
```

Every provider should be converted into a common internal job format.

Example normalized job:

```text
Job
├── id
├── title
├── company
├── location
├── remote
├── description
├── requirements
├── salary_min
├── salary_max
├── currency
├── employment_type
├── source
├── source_url
├── posted_at
└── discovered_at
```

Only permitted APIs, feeds, pages, or user-authorized interfaces will be used.

---

# 7. Job Deduplication

The same job can appear on multiple sources.

The system should attempt to identify duplicates using signals such as:

- Source job ID
- Application URL
- Company
- Job title
- Location
- Description similarity

Example:

```text
Source A ──┐
           │
Source B ──┼──> Deduplication ──> Canonical Job
           │
Source C ──┘
```

The canonical job should retain information about its source listings where useful.

---

# 8. Job Matching

The matching system will evolve in stages.

## Stage 1 — Rule-Based Matching

Initial weighted score:

```text
Final Score =
    0.40 × Skill Match
  + 0.20 × Experience Match
  + 0.15 × Title Match
  + 0.10 × Location Match
  + 0.10 × Preference Match
  + 0.05 × Salary Match
```

The exact weights can later be tuned using evaluation data.

## Stage 2 — Keyword Matching

Compare:

```text
Resume Skills
        ↓
Job Requirements
```

Methods may include:

- Exact matching
- Normalized matching
- Synonym matching
- TF-IDF

## Stage 3 — Semantic Matching

Generate embeddings for:

- Candidate profile
- Job description
- Job requirements

Then calculate semantic similarity.

```text
Candidate Embedding
        │
        ▼
   Vector Search
        │
        ▼
Job Embedding
```

## Stage 4 — LLM Evaluation

The LLM can provide a higher-level assessment:

- Why the candidate matches
- Missing skills
- Experience gaps
- Strengths
- Potential concerns

The LLM should not replace transparent scoring completely.

---

# 9. LangGraph Agent Workflow

LangGraph will orchestrate the multi-step AI workflow.

Conceptual state:

```text
AgentState
├── user
├── resume
├── candidate_profile
├── jobs
├── matches
├── selected_job
├── cover_letter
├── application_answers
├── approval_required
├── application_status
└── errors
```

Workflow:

```text
START
  │
  ▼
Load Resume
  │
  ▼
Parse Resume
  │
  ▼
Search Jobs
  │
  ▼
Normalize Jobs
  │
  ▼
Deduplicate
  │
  ▼
Score Jobs
  │
  ▼
Filter / Rank
  │
  ▼
Generate Materials
  │
  ▼
Human Approval
  │
  ├── Reject ──> END
  │
  ▼
Application Workflow
  │
  ▼
Record Application
  │
  ▼
Schedule Follow-up
  │
  ▼
END
```

The workflow should be resumable and observable.

---

# 10. Human-in-the-Loop

Human approval is a core architectural requirement.

The agent may:

- Search
- Analyze
- Rank
- Draft
- Prepare
- Recommend

But consequential actions require explicit approval.

```text
AI prepares application
          │
          ▼
    User reviews
          │
     ┌────┴────┐
     │         │
   Reject    Approve
     │         │
     ▼         ▼
    END    Application
             Workflow
```

The system must not attempt to bypass:

- CAPTCHA
- Authentication
- Anti-bot systems
- Rate limits
- Platform restrictions
- Access controls

---

# 11. Application Tracking

Application lifecycle:

```text
DISCOVERED
    ↓
MATCHED
    ↓
SELECTED
    ↓
PREPARING
    ↓
AWAITING_APPROVAL
    ↓
SUBMITTED
    ↓
    ├── INTERVIEW
    │
    ├── REJECTED
    │
    └── OFFER
```

Potential application fields:

```text
Application
├── id
├── user_id
├── job_id
├── status
├── applied_at
├── application_url
├── resume_version
├── cover_letter
├── application_answers
├── notes
├── recruiter
├── next_action
└── created_at
```

---

# 12. Interview and Deadline Management

Important events include:

- Application deadline
- Online assessment
- Recruiter call
- Technical interview
- Behavioral interview
- Final interview
- Follow-up
- Offer expiration

Calendar reminders may be scheduled at:

```text
7 days before
24 hours before
1 hour before
After interview
```

The exact reminder schedule should be configurable.

---

# 13. Notification System

The notification system should be abstracted so different providers can be used.

```text
NotificationService
       │
       ├── Email
       ├── Push
       └── SMS
```

For the free development environment, email can initially be mocked or logged locally.

Production providers can be added later.

---

# 14. Database Architecture

PostgreSQL will be the primary database.

Initial entities:

```text
User
Resume
CandidateProfile
Job
JobMatch
Application
Interview
Notification
```

Relationships:

```text
User
 │
 ├── Resume
 │     └── CandidateProfile
 │
 ├── JobMatch ─── Job
 │
 ├── Application ─── Job
 │
 ├── Interview ─── Application
 │
 └── Notification
```

The schema will be implemented incrementally beginning on Day 3.

---

# 15. Background Processing

Long-running operations should not block API requests.

Examples:

- Job searches
- Resume processing
- Embedding generation
- Large-scale matching
- Notification delivery
- Calendar synchronization

Architecture:

```text
FastAPI
   │
   ▼
Redis Queue
   │
   ▼
Worker
   │
   ├── Resume Processing
   ├── Job Search
   ├── Matching
   └── Notifications
```

The first implementation will prioritize simplicity. We will introduce background workers when they become necessary.

---

# 16. Security

Security requirements include:

- Secrets stored in environment variables
- No API keys committed to Git
- Input validation
- File type validation
- File size limits
- Authentication
- Authorization
- Database access controls
- Secure logging
- Sensitive data protection
- Rate limiting where appropriate

Example:

```text
.env
.env.example
```

`.env` must never be committed.

---

# 17. Observability

The system should eventually provide:

- Structured logs
- Request IDs
- Agent workflow logs
- Job source errors
- Application workflow status
- AI generation failures
- Background worker failures

This will make debugging the agent much easier.

---

# 18. Testing Architecture

Testing will exist at three levels.

## Unit Tests

Test individual components:

```text
Resume Parser
Matcher
Scoring
Deduplication
Validators
Services
```

## Integration Tests

Test components together:

```text
API → Database
API → Resume Parser
Job Source → Normalization
Matcher → Database
```

## End-to-End Tests

Test the complete workflow:

```text
Upload Resume
      ↓
Parse
      ↓
Search Jobs
      ↓
Match
      ↓
Generate Materials
      ↓
Approve
      ↓
Track Application
```

---

# 19. AI Evaluation

The AI system must be evaluated independently from normal software tests.

Initial evaluation dataset:

```text
10 resumes
50 jobs
```

Evaluation metrics include:

### Resume Extraction

- Field accuracy
- Missing fields
- Invalid structured output

### Job Matching

- Precision@5
- Recall@10
- Ranking quality
- Explanation quality

### Generation

- Relevance
- Accuracy
- Personalization
- Unsupported claims
- Grammar

### Automation

- Workflow success rate
- Failure rate
- Human intervention rate
- Duplicate applications

---

# 20. Deployment Architecture

Development:

```text
Docker Compose
│
├── frontend
├── api
├── worker
├── postgres
└── redis
```

Future production architecture can evolve independently.

The first objective is to make the complete system work locally before introducing cloud infrastructure.

---

# 21. Development Principles

The project will follow these principles:

### Keep components modular

A job source, LLM provider, notification provider, or calendar provider should be replaceable.

### Prefer deterministic logic where possible

Use normal software logic for:

- Validation
- Scoring
- Deduplication
- Status transitions
- Permissions

Use AI where it adds value:

- Extraction
- Semantic understanding
- Generation
- Reasoning
- Recommendations

### Build vertical slices

Instead of building every subsystem independently, periodically connect components into a complete working flow.

### Free-first

Use local/open-source tools whenever practical during development.

### Human approval

Never automate consequential actions without explicit approval.

---

# 22. Target End State

The final MVP should support this complete flow:

```text
User
 │
 ▼
Upload Resume
 │
 ▼
AI extracts candidate profile
 │
 ▼
Search permitted job sources
 │
 ▼
Normalize + deduplicate jobs
 │
 ▼
Match and rank jobs
 │
 ▼
User reviews recommendations
 │
 ▼
Select job
 │
 ▼
AI generates tailored materials
 │
 ▼
User reviews
 │
 ▼
User approves
 │
 ▼
Permitted application workflow
 │
 ▼
Application recorded
 │
 ▼
Interview/deadline tracking
 │
 ▼
Calendar + notifications
```

This architecture is intentionally modular so that additional job sources, LLM providers, matching algorithms, notification providers, and application workflows can be added later without redesigning the entire system.