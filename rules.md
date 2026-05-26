# BLACKCLAP_BACKEND_RULES.md

## 1. Project Overview

BlackClap is a startup-focused social media backend built for:

* short-form video content
* image posts
* realtime interactions
* social graph features
* scalable media delivery

The backend is designed using a **modular monolith architecture** to optimize:

* fast MVP delivery
* maintainability
* scalability
* future microservice migration

The primary launch target is:

* ~20k users
* India-first deployment
* fast feature iteration
* production-ready foundations

This project prioritizes:

* clean architecture
* async performance
* scalability paths
* startup execution speed

---

# 2. Technology Stack

| Layer              | Technology                     |
| ------------------ | ------------------------------ |
| Language           | Python 3.12                    |
| Framework          | FastAPI                        |
| ORM                | SQLAlchemy 2 Async             |
| Database           | PostgreSQL                     |
| Migration Tool     | Alembic                        |
| Authentication     | JWT + Bcrypt (Local Auth)      |
| Storage            | AWS S3                         |
| CDN                | AWS CloudFront                 |
| Background Jobs    | Celery + Redis                 |
| Realtime           | FastAPI WebSockets             |
| Push Notifications | Firebase Cloud Messaging (FCM) |
| Deployment         | Docker + Docker Compose        |
| Reverse Proxy      | Nginx                          |
| CI/CD              | GitHub Actions                 |

---

# 3. Architecture Pattern

## Modular Monolith

The project MUST remain a modular monolith during phase-1.

DO NOT introduce:

* microservices
* Kubernetes
* event-driven architecture
* distributed systems complexity

until scaling actually requires it.

---

# 4. Core Architecture Principles

## 1. Async First

All I/O operations MUST use async/await:

* database
* S3 operations
* Redis
* external APIs
* websocket communication

Blocking operations are prohibited inside FastAPI request lifecycle.

---

## 2. Thin Routers

Routers/controllers should only:

* validate request
* authenticate user
* call service layer
* return response

Business logic MUST remain in services.

---

## 3. Service-Oriented Business Logic

All business rules belong in services:

* feed generation
* engagement logic
* notifications
* follow system
* media handling
* chat logic

---

## 4. Avoid Premature Abstractions

DO NOT overengineer:

* repository layers
* generic abstractions
* complex inheritance trees
* unnecessary interfaces

Preferred flow:

```text
router → service → database
```

---

## 5. DTO Separation

Use Pydantic v2 for:

* request validation
* response models
* websocket payload schemas

All APIs MUST define response models.

---

## 6. UUID-Based Models

All database entities MUST use UUID primary keys.

Every model should contain:

* id
* created_at
* updated_at
* optional deleted_at

---

# 5. Project Structure

```text
blackclap-backend/
│
├── app/
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config/
│   │   ├── database/
│   │   ├── middleware/
│   │   ├── security/
│   │   ├── websocket/
│   │   ├── storage/
│   │   ├── utils/
│   │   ├── logging/
│   │   └── constants/
│   │
│   ├── modules/
│   │   ├── auth/
│   │   ├── users/
│   │   ├── posts/
│   │   ├── media/
│   │   ├── feed/
│   │   ├── comments/
│   │   ├── likes/
│   │   ├── follows/
│   │   ├── hashtags/
│   │   ├── notifications/
│   │   ├── chat/
│   │   └── realtime/
│   │
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── tasks/
│   │
│   └── shared/
│       ├── dto/
│       ├── models/
│       ├── enums/
│       └── exceptions/
│
├── alembic/
├── docker/
├── scripts/
├── tests/
├── .github/workflows/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

# 6. Database Rules

## Database

Use PostgreSQL only.

SQLite is prohibited outside local experiments.

---

## ORM Rules

Use:

* SQLAlchemy 2 Async
* AsyncSession
* Declarative models

Avoid:

* synchronous SQLAlchemy
* raw SQL unless absolutely necessary

---

## Migration Rules

Use Alembic ONLY.

Never manually modify production schema.

Migration flow:

```bash
alembic revision --autogenerate -m "message"
alembic upgrade head
```

---

# 7. Authentication Architecture

## Authentication Provider

Authentication is handled locally using standard Python libraries and JWT tokens.

Backend responsibilities:

* Store credentials securely in the database (email, username, hashed_password).
* Verify user credentials via bcrypt password hashing.
* Issue signed JSON Web Tokens (JWT) for authenticated sessions.
* Authenticate routes using standard OAuth2 Password Bearer token dependency.

---

## Supported Login Methods

Initially support:

* email/password (Local credential registration and login)

---

## Auth Flow

```text
Flutter App
    ↓
Registers/Logs in with Email & Password
    ↓
FastAPI hashes/verifies password
    ↓
FastAPI generates signed JWT token
    ↓
Flutter App stores token
    ↓
FastAPI verifies JWT on subsequent requests
```

---

# 8. Media Architecture

## Storage

All media MUST be stored in AWS S3.

Never store media on EC2 filesystem.

---

## Upload Strategy

Media uploads MUST use presigned URLs.

Correct flow:

```text
Flutter App
    ↓
Backend generates presigned URL
    ↓
Direct upload to S3
    ↓
Backend stores metadata
```

Uploading through FastAPI server is prohibited.

---

## Media Categories

```text
media/
  users/
  posts/
  chat/
  thumbnails/
```

---

## Video Constraints

Phase-1 video support:

* max duration: 15 seconds
* original upload only
* thumbnail generation

Avoid complex transcoding initially.

---

# 9. Feed Architecture

## Feed Type

Phase-1 feed should use:

* chronological ordering
* engagement scoring
* following prioritization
* hashtags/trending support

DO NOT implement:

* ML recommendation engine
* AI ranking
* advanced personalization

---

## Trending Logic

Simple trending calculation:

* likes
* comments
* shares
* recency

Complex recommendation systems are future scope.

---

# 10. Realtime Architecture

## WebSockets

Use FastAPI native WebSockets.

Supported realtime features:

* live chat
* typing indicators
* online presence
* realtime comments
* realtime notifications

---

## Scaling Strategy

Initial websocket scaling:

* single server
* in-memory connection manager

Future scaling:

* Redis Pub/Sub
* dedicated websocket service

---

# 11. Chat Architecture

## Phase-1 Chat

Use:

* websocket connections
* PostgreSQL storage
* basic conversation models

Avoid:

* end-to-end encryption
* distributed websocket architecture
* message queues for chat

---

# 12. Notifications

## Push Notifications

Use Firebase Cloud Messaging (FCM).

Notification types:

* likes
* comments
* follows
* chat messages

---

## Notification Delivery

Notifications should be asynchronous using Celery tasks.

---

# 13. Background Jobs

## Celery Usage

Use Celery for:

* notifications
* thumbnail generation
* cleanup jobs
* scheduled tasks

---

## Redis

Redis is used for:

* Celery broker
* caching
* websocket scaling later

---

# 14. Deployment Architecture

## Initial Infrastructure

```text
EC2
├── FastAPI App
├── Celery Worker
├── Redis
├── Nginx
└── Docker Compose
```

External services:

* RDS PostgreSQL
* S3
* CloudFront

---

## Deployment Rules

Use:

* Docker containers
* environment variables
* GitHub Actions CI/CD

Avoid:

* manual deployments
* directly running python on server

---

# 15. AWS Infrastructure

## Services Used

| Service        | Purpose           |
| -------------- | ----------------- |
| EC2            | Backend hosting   |
| RDS PostgreSQL | Database          |
| S3             | Media storage     |
| CloudFront     | CDN               |
| IAM            | Permissions       |
| CloudWatch     | Logs              |
| Route53        | Domain management |

---

# 16. Security Rules

## Mandatory Rules

### Environment Variables

Secrets MUST NEVER be hardcoded.

Use:

* .env files locally
* AWS Secrets Manager later

---

## S3 Rules

Buckets should remain private.

Media access should use:

* CloudFront
* presigned URLs

---

## API Security

Mandatory:

* JWT validation
* rate limiting
* request validation
* CORS restrictions

---

# 17. Logging & Monitoring

## Logging

Use structured logging.

Log:

* request IDs
* errors
* authentication failures
* websocket disconnects

Avoid excessive console prints.

---

# 18. CI/CD Rules

## GitHub Actions

CI pipeline should include:

* linting
* tests
* Docker build
* deployment

---

## Branch Strategy

```text
main → production
develop → staging
feature/* → feature branches
```

---

# 19. Code Quality Standards

## Formatting

Use:

* ruff
* black

---

## Type Checking

Use:

* mypy

---

## Pre-commit Hooks

Mandatory before production pushes.

---

# 20. API Design Rules

## REST Only

Use REST APIs only for phase-1.

Avoid:

* GraphQL
* gRPC

---

## API Versioning

```text
/api/v1/
```

Mandatory for all routes.

---

# 21. Initial Core Modules

## Mandatory Modules

### auth

Authentication & Firebase verification

### users

Profiles, settings, social graph

### posts

Post creation & retrieval

### media

Upload management

### feed

Feed generation

### comments

Comment system

### likes

Like system

### follows

Follow system

### notifications

Push notifications

### chat

Realtime messaging

---

# 22. Features Explicitly Deferred

The following are intentionally NOT phase-1 scope:

* livestreaming
* AI recommendations
* microservices
* Kubernetes
* Elasticsearch
* advanced analytics
* creator monetization
* AI moderation
* advanced video transcoding
* multi-region deployment

---

# 23. Development Philosophy

BlackClap prioritizes:

* shipping fast
* maintainable architecture
* scalable foundations
* startup execution speed

The goal is:

* fast MVP launch
* minimal rewrites later
* clean scalability path

Avoid premature optimization.

Build only what current scale requires.
