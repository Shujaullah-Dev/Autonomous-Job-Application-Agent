# AI-Powered Job Application Assistant

An AI-powered job application assistant that helps users discover relevant jobs, understand how well they match, generate tailored application materials, manage applications, and track interviews and deadlines.

## Project Goal

Build an end-to-end AI job assistant that can:

- Accept and parse a user's resume
- Extract skills, experience, education, and preferences
- Search permitted job sources
- Normalize and deduplicate job listings
- Match jobs against the user's profile
- Rank jobs using explainable scoring
- Generate tailored cover letters and application answers
- Require human approval before consequential application actions
- Support permitted application workflows or user-assisted submission
- Track application status
- Track interviews and deadlines
- Create calendar events and reminders
- Send notifications
- Provide a dashboard for managing the job search

## Core Workflow

```text
Resume Upload
      ↓
Resume Parsing
      ↓
Candidate Profile
      ↓
Job Search
      ↓
Job Normalization
      ↓
Deduplication
      ↓
Job Matching
      ↓
Ranking
      ↓
Recommended Jobs
      ↓
Generate Application Materials
      ↓
Human Review & Approval
      ↓
Permitted Application Workflow
      ↓
Application Tracking
      ↓
Interview / Deadline Tracking
      ↓
Notifications
```

## MVP

The first version will focus on:

- One resume format family: PDF/DOCX
- One or two permitted job sources
- Keyword-based matching
- Semantic/embedding-based matching
- Explainable job scores
- AI-generated cover letters
- AI-generated application answers
- Human approval before submission
- Application tracking
- Interview and deadline tracking
- Calendar integration
- Email notifications
- Dockerized local development
- Automated tests
- GitHub-based development and CI

## Technology Stack

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL
- Redis
- LangChain
- LangGraph

### AI

The system will support an LLM abstraction so that development can use a local model where practical and a hosted model can be added later.

### Resume Processing

- PyMuPDF
- python-docx

### Matching

The matching system will initially combine:

- Skills match
- Experience match
- Job title match
- Location match
- User preference match
- Salary match

Semantic embeddings will be added to improve matching beyond exact keyword overlap.

### Frontend

- React / Next.js

### Infrastructure

- Docker
- Docker Compose
- Git
- GitHub
- GitHub Actions

### Testing

- pytest
- Unit tests
- Integration tests
- End-to-end tests
- AI evaluation datasets

## Architecture

```text
                    ┌──────────────────┐
                    │    Frontend      │
                    │ React / Next.js  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │     FastAPI      │
                    │      API         │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
   Resume Service      Job Service       Application
          │                  │              Service
          ▼                  ▼                  │
    Resume Parser       Job Sources             │
          │                  │                  │
          └──────────┬───────┘                  │
                     ▼                          │
              ┌──────────────┐                  │
              │  LangGraph   │◄─────────────────┘
              │   Workflow   │
              └──────┬───────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
        LLM       Matching     Tools
                     │
                     ▼
              ┌──────────────┐
              │ PostgreSQL   │
              └──────────────┘
```

## Safety and Responsible Automation

The assistant will not bypass:

- CAPTCHA
- Authentication controls
- Anti-bot protections
- Rate limits
- Platform restrictions
- Terms or access restrictions

Consequential actions such as submitting an application require explicit user approval.

## Development Philosophy

This project follows a **free-first** development strategy.

During development, we will prefer:

- Open-source software
- Local services
- Local databases
- Local LLMs where practical
- Free GitHub functionality
- Docker-based development

Paid services will only be introduced when they provide a clear benefit that cannot reasonably be achieved with the free/local setup.

## Project Status

**Current phase:** Day 1 — Project Foundation

## License

This project is currently intended for educational and personal development purposes.