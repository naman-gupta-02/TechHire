# TechHire

TechHire is a full-stack AI-powered job search platform that helps users discover relevant job opportunities, analyze job descriptions, and evaluate resumes against job requirements. The application aggregates job listings, provides advanced filtering options, generates AI-powered job summaries, and extracts resume text for comparison.

## Features

- 🔍 Search and browse job listings
- 🎯 Advanced filtering by:
  - Skills
  - Salary
  - Experience Level
  - Work Mode
  - Visa Sponsorship
  - Date Posted
- 🤖 AI-generated job summaries
- 📄 Resume upload (PDF/TXT)
- 📊 Resume text extraction and comparison
- 🔄 Refresh job listings using web scrapers
- ⚡ Fast and responsive React frontend
- 🚀 FastAPI backend with PostgreSQL database

---

## Tech Stack

### Frontend
- React
- Vite
- Tailwind CSS
- React Query

### Backend
- FastAPI
- SQLAlchemy
- PostgreSQL

### AI
- Groq API

### Other Tools
- Docker Compose
- Python Web Scrapers

---

## Project Structure

```text
TechHire/
│
├── frontend/              # React frontend
├── scraper/               # Job scraping modules
├── db/                    # Database models and configuration
├── api.py                 # FastAPI application
├── main.py                # Scraper runner
├── requirements.txt
├── docker-compose.yml
├── setup.sh
└── README.md
```

---

# Prerequisites

Make sure you have the following installed:

- Python 3.10+
- Node.js 18+
- npm
- PostgreSQL
- Git

---

# Installation

## 1. Clone the Repository

```bash
git clone https://github.com/naman-gupta-02/TechHire.git
cd TechHire
```

---

## 2. Create Python Virtual Environment

### Windows

```bash
python -m venv venv

venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv venv

source venv/bin/activate
```

---

## 3. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure PostgreSQL

Create a PostgreSQL database.

Example:

```sql
CREATE DATABASE techhire;
```

Update your database connection string (or `.env` file if used):

```env
DATABASE_URL=postgresql://username:password@localhost:5432/techhire
```

---

## 5. Configure Environment Variables

Create a `.env` file in the project root.

Example:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/techhire

GROQ_API_KEY=your_groq_api_key
```

Replace:

- `username`
- `password`
- `your_groq_api_key`

with your own credentials.

---

## 6. Install Frontend Dependencies

```bash
cd frontend

npm install
```

---

# Running the Project

## Step 1 — Start PostgreSQL

Make sure your PostgreSQL server is running.

---

## Step 2 — Start Backend

From the project root:

```bash
uvicorn api:app --reload
```

The backend will start at:

```
http://127.0.0.1:8000
```

Swagger Documentation:

```
http://127.0.0.1:8000/docs
```

---

## Step 3 — Start Frontend

Open another terminal.

```bash
cd frontend

npm run dev
```

Frontend will be available at:

```
http://localhost:5173
```

---

## Step 4 — Refresh Job Listings (Optional)

Run the scraper:

```bash
python main.py
```

This will fetch and update the latest job listings.

---

# API Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/jobs` | Fetch all jobs |
| GET | `/jobs/{id}` | Get job details |
| GET | `/jobs/{id}/summary` | Generate AI summary |
| POST | `/resume/extract-text` | Upload resume |
| POST | `/scrape/refresh` | Refresh job data |
| GET | `/scrape/status` | Check scraper status |

---

# Available Features

- Browse jobs
- Search jobs
- Apply multiple filters
- AI-powered job summaries
- Resume parsing
- Resume-job comparison
- Job database refresh

---

# Future Improvements

- User Authentication
- Saved Jobs
- Resume Scoring
- Job Recommendations
- Email Notifications
- Deployment with Docker
- Unit and Integration Tests

---

# License

This project is intended for educational and learning purposes.

---

# Author

**Naman Gupta**

GitHub: https://github.com/naman-gupta-02
