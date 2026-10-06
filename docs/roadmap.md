# AI Job Agent — 25-Day Implementation Roadmap

## Project Goal

Build a production-style AI-powered job application assistant that can:

- Parse resumes
- Build structured candidate profiles
- Search permitted job sources
- Deduplicate job listings
- Match and rank jobs
- Generate tailored application materials
- Require human approval
- Support permitted application workflows
- Track applications
- Track interviews and deadlines
- Schedule calendar events
- Send notifications
- Run locally using Docker
- Use LangChain and LangGraph
- Include automated tests
- Use Git/GitHub and CI/CD

---

# Phase 1 — Foundation

## Day 1 — Project Definition & Architecture

### Objectives

- [x] Define project goal
- [x] Define MVP scope
- [x] Define technology stack
- [x] Create repository
- [x] Create initial project structure
- [x] Create README
- [x] Create architecture documentation
- [x] Create roadmap documentation
- [ ] Create `.gitignore`
- [ ] Create `.env.example`
- [ ] Create initial Docker Compose file
- [ ] Create first Git commit
- [ ] Push repository to GitHub

### Deliverable

A clean, documented project repository ready for development.

---

# Phase 2 — Backend Foundation

## Day 2 — Development Environment

### Objectives

- Install/configure Python
- Create virtual environment
- Configure FastAPI
- Configure Pydantic
- Configure SQLAlchemy
- Configure pytest
- Configure Ruff
- Create FastAPI application
- Create `/health` endpoint
- Add initial tests

### Deliverable

Running FastAPI backend with a working test suite.

---

## Day 3 — Database

### Objectives

- Add PostgreSQL
- Configure Docker Compose
- Configure SQLAlchemy
- Configure database connection
- Create initial models
- Configure migrations
- Add database tests

### Deliverable

Working PostgreSQL database with application connectivity.

---

# Phase 3 — Resume Intelligence

## Day 4 — Resume Upload

### Objectives

- Create resume upload endpoint
- Validate file type
- Validate file size
- Store uploaded files safely
- Create Resume database model
- Add tests

### Deliverable

Users can upload PDF/DOCX resumes.

---

## Day 5 — Resume Text Extraction

### Objectives

- Integrate PyMuPDF
- Integrate python-docx
- Extract text from PDF
- Extract text from DOCX
- Handle invalid files
- Add extraction tests

### Deliverable

Reliable raw resume text extraction.

---

## Day 6 — AI Resume Parser

### Objectives

- Define structured candidate schema
- Create Pydantic models
- Integrate LLM
- Extract:
  - Skills
  - Experience
  - Education
  - Projects
  - Certifications
  - Languages
  - Location
- Validate LLM output
- Store structured profile

### Deliverable

Resume → structured candidate profile.

---

## Day 7 — Resume Quality

### Objectives

- Improve extraction accuracy
- Handle missing information
- Handle malformed AI responses
- Add retry/fallback logic
- Create resume evaluation dataset
- Add automated tests

### Deliverable

Reliable resume intelligence pipeline.

---

# Phase 4 — Job Discovery

## Day 8 — Job Database & Search API

### Objectives

- Create Job model
- Create Job API
- Add filtering
- Add pagination
- Add search
- Add tests

### Deliverable

Internal job database and API.

---

## Day 9 — First Job Source

### Objectives

- Define JobSource interface
- Integrate first permitted job source
- Normalize job data
- Store jobs
- Handle errors
- Add tests

### Deliverable

First working external job source.

---

## Day 10 — Multiple Job Sources

### Objectives

- Add second job source
- Normalize provider differences
- Implement deduplication
- Track source information
- Handle duplicate listings

### Deliverable

Multi-source job discovery.

---

# Phase 5 — Job Matching

## Day 11 — Keyword Matching

### Objectives

Implement:

- Skill matching
- Title matching
- Experience matching
- Location matching
- Preference matching
- Salary matching

Initial score:

```text
0.40 × Skill
0.20 × Experience
0.15 × Title
0.10 × Location
0.10 × Preference
0.05 × Salary
```

### Deliverable

Transparent rule-based matching.

---

## Day 12 — Semantic Matching

### Objectives

- Generate embeddings
- Store embeddings
- Add vector search
- Calculate cosine similarity
- Compare semantic vs keyword matching

### Deliverable

Hybrid keyword + semantic matching.

---

## Day 13 — Recommendation API

### Objectives

- Create matching API
- Rank jobs
- Return match scores
- Return explanations
- Show matched skills
- Show missing skills
- Add recommendation tests

### Deliverable

Ranked job recommendations.

---

# Phase 6 — AI Agent

## Day 14 — LangChain

### Objectives

- Integrate LangChain
- Configure model abstraction
- Create prompts
- Create structured outputs
- Create reusable AI services

### Deliverable

Reusable LLM service layer.

---

## Day 15 — LangGraph

### Objectives

Create agent state:

```text
resume
candidate_profile
jobs
matches
selected_job
cover_letter
application_answers
approval_required
application_status
```

Workflow:

```text
START
 ↓
Load Resume
 ↓
Parse Resume
 ↓
Search Jobs
 ↓
Deduplicate
 ↓
Score
 ↓
Filter
 ↓
Generate Materials
 ↓
Human Approval
 ↓
Application Workflow
 ↓
Record
 ↓
Follow-up
 ↓
END
```

### Deliverable

Working LangGraph workflow.

---

# Phase 7 — Application Preparation

## Day 16 — Tailored Materials

### Objectives

Generate:

- Cover letters
- Application answers
- Professional summaries
- Job-specific resume suggestions

Ensure generated content does not invent candidate experience.

### Deliverable

Job-specific application materials.

---

## Day 17 — Application Workflow

### Objectives

Create:

- Application model
- Application states
- Approval state
- Submission tracking
- Notes
- Application history

Statuses:

```text
DISCOVERED
MATCHED
SELECTED
PREPARING
AWAITING_APPROVAL
SUBMITTED
INTERVIEW
REJECTED
OFFER
```

### Deliverable

Complete application lifecycle tracking.

---

## Day 18 — Permitted Application Automation

### Objectives

- Define application provider interface
- Support permitted application workflows
- Build user-assisted workflow where necessary
- Require explicit approval
- Handle failures
- Record submission results

Never bypass CAPTCHA, authentication, anti-bot controls, rate limits, or platform restrictions.

### Deliverable

Safe application workflow.

---

# Phase 8 — User Experience

## Day 19 — Application Dashboard

### Objectives

Build frontend dashboard showing:

- Candidate profile
- Recommended jobs
- Match scores
- Applications
- Application status
- Interviews
- Deadlines
- Notifications

### Deliverable

Working job-management dashboard.

---

## Day 20 — Calendar Integration

### Objectives

Integrate a calendar provider.

Support:

- Interviews
- Assessments
- Deadlines
- Follow-ups
- Recruiter calls

Reminder defaults:

```text
7 days before
24 hours before
1 hour before
After interview
```

### Deliverable

Calendar-aware application tracking.

---

## Day 21 — Notifications

### Objectives

Implement notification abstraction.

Initial channel:

- Email

Future channels:

- Push
- SMS

Notifications for:

- Application deadlines
- Interviews
- Follow-ups
- Recruiter responses
- Offers
- Assessment deadlines

### Deliverable

Automated notification system.

---

# Phase 9 — Infrastructure

## Day 22 — Full Dockerization

### Objectives

Create Docker services:

```text
frontend
api
worker
postgres
redis
```

### Deliverable

Entire application runs using Docker Compose.

---

## Day 23 — CI/CD

### Objectives

Configure GitHub Actions.

Pull request checks:

- Lint
- Type checking
- Unit tests
- Integration tests
- Docker build
- Security checks

Main branch:

```text
Build
 ↓
Test
 ↓
Package
 ↓
Deploy
 ↓
Health Check
```

### Deliverable

Automated CI/CD pipeline.

---

# Phase 10 — Quality & Release

## Day 24 — Security, Reliability & Evaluation

### Security

- Secret management
- Authentication
- Authorization
- Input validation
- File validation
- Rate limiting
- Secure logging

### Reliability

- Retry handling
- Timeouts
- Error handling
- Job-source failures
- LLM failures
- Worker failures

### AI Evaluation

Create evaluation dataset:

```text
10 resumes
50 jobs
```

Evaluate:

- Resume extraction accuracy
- Precision@5
- Recall@10
- Match explanations
- Generation relevance
- Personalization
- Unsupported claims
- Automation success rate

### Deliverable

Production-quality evaluation and reliability baseline.

---

## Day 25 — Final Integration & Release

### Objectives

Run the complete workflow:

```text
Upload Resume
 ↓
Parse Resume
 ↓
Create Candidate Profile
 ↓
Search Jobs
 ↓
Deduplicate
 ↓
Match
 ↓
Rank
 ↓
Recommend
 ↓
Select Job
 ↓
Generate Materials
 ↓
User Approval
 ↓
Permitted Application Workflow
 ↓
Track Application
 ↓
Schedule Interview
 ↓
Calendar
 ↓
Notifications
```

Final tasks:

- Fix integration bugs
- Improve UI
- Improve error messages
- Run complete test suite
- Run security checks
- Verify Docker deployment
- Verify CI/CD
- Update documentation
- Create release notes
- Tag `v1.0.0`

### Deliverable

Working AI Job Agent MVP.

---

# MVP Definition of Done

The MVP is complete when a user can:

- [ ] Upload a resume
- [ ] Parse the resume
- [ ] Review structured candidate information
- [ ] Search permitted job sources
- [ ] See deduplicated jobs
- [ ] Receive ranked recommendations
- [ ] Understand why a job was recommended
- [ ] Select a job
- [ ] Generate a tailored cover letter
- [ ] Generate application answers
- [ ] Review generated content
- [ ] Approve an application
- [ ] Complete a permitted application workflow
- [ ] Track the application
- [ ] Track interviews
- [ ] Track deadlines
- [ ] Create calendar events
- [ ] Receive notifications

---

# Engineering Definition of Done

Before considering a feature complete:

- [ ] Code implemented
- [ ] Tests added
- [ ] Error handling added
- [ ] Logging added where appropriate
- [ ] Documentation updated
- [ ] No secrets committed
- [ ] Code formatted/linted
- [ ] Tests passing
- [ ] Git commit created
- [ ] Pull request reviewed where applicable

---

# Development Strategy

The project will prioritize a working vertical slice over implementing every integration immediately.

Recommended progression:

```text
Resume
  ↓
Candidate Profile
  ↓
One Job Source
  ↓
Matching
  ↓
Recommendation
  ↓
Application Materials
  ↓
Approval
  ↓
Tracking
```

Only after this core flow works should additional integrations be added.

---

# Cost Strategy

Development target:

**$0**

Prefer:

- Open-source libraries
- Local PostgreSQL
- Local Redis
- Docker
- Local LLMs where practical
- Free GitHub features
- Mock notification services during development

Paid APIs or cloud services should only be introduced when required for production or when a free/local alternative is no longer practical.

---

# Current Progress

## Day 1

- [x] Repository created
- [x] Project structure created
- [x] README created
- [x] Architecture created
- [x] Roadmap created
- [ ] `.gitignore`
- [ ] `.env.example`
- [ ] Docker Compose skeleton
- [ ] Initial Git commit
- [ ] GitHub repository