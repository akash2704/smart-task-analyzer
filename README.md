# 🎯 Smart Task Analyzer (AI-Powered)

> An intelligent, strategy-driven task prioritization system built with Django, Tailwind CSS, and advanced scoring algorithms.

**Smart Task Analyzer** goes beyond simple "to-do" lists by using mathematical modeling and graph theory to determine what you *actually* need to do next. It considers urgency (business days), importance, effort (logarithmic scaling), and dependency chains to surface the most critical work.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Django](https://img.shields.io/badge/Django-5.0+-green.svg)
![uv](https://img.shields.io/badge/uv-fastest-purple)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)

---

## 🚀 Setup Instructions

### Option A: Docker (Recommended)
This sets up the application and a PostgreSQL database automatically using the defined `pyproject.toml`.

1. **Clone the repository**
2. **Build and Run**:
   ```bash
   docker-compose up --build
   ```
3. **Access**: Open `http://localhost:8000`

### Option B: Local Development with uv
This project uses [uv](https://github.com/astral-sh/uv) for blazing fast dependency management.

1. **Install uv** (if not installed):
   ```bash
   # On macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # On Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Sync Dependencies**:
   This creates the virtual environment and installs packages from `pyproject.toml`.
   ```bash
   uv sync
   ```

3. **Configure Database**:
   Ensure your `settings.py` is pointing to a valid DB. (See `db_settings.py` snippet below).

4. **Run Server**:
   ```bash
   uv run python manage.py migrate
   uv run python manage.py runserver
   ```

---

## 🧠 The Scoring Algorithm

The core intelligence resides in `services.py`. Unlike linear sorting, this system uses a multi-dimensional weighted scoring model (`TaskPrioritizer`).

### 1. The Strategy Engine
The system supports dynamic strategies that alter the weight of four key factors:
- **Balanced (Default)**: 35% Urgency, 35% Importance, 15% Effort, 15% Dependency.
- **Deadline Driven**: 70% Urgency.
- **Quick Wins**: 70% Effort (Low effort = High score).
- **Unblock Others**: 50% Dependency impact.

### 2. Intelligent Component Calculation

#### 📅 Urgency (Business Day Awareness)
The system counts **Business Days**, not just calendar days.
- A task due on Monday has higher urgency on Friday than a task due on Tuesday.
- **Overdue Penalty**: Exponential penalty (`abs(days_late) * 8`) forces overdue tasks to the top.

#### ⚡ Effort (Logarithmic Inverse Scale)
We use a non-linear scale to prioritize momentum:
- **< 30 mins**: 100 points (Instant gratification)
- **1 hour**: 85 points
- **10 hours**: 25 points

#### 🔗 Dependency Graphing (Blocker Bonus)
The system builds a directed graph of your tasks.
- If **Task A** blocks **Task B** and **Task C**, Task A receives a "Blocker Bonus" (+15 points per dependent).
- **Cycle Detection**: Uses Depth-First Search (DFS) to identify logical paradoxes (e.g., A waits for B, B waits for A) and flags them.

---

## 🛠 Tech Stack & Decisions

### Dependency Management: uv
We switched to **uv** for its speed and reliability. It manages the Python version and dependencies via `pyproject.toml`, ensuring deterministic builds across Docker and local environments.

### Service Layer Architecture
Logic is stripped from `views.py` and placed into `services.py` to allow isolated testing of the prioritization algorithms.

### Tailwind CSS
Provides a modern, responsive interface with instant visual feedback (color-coded borders based on score).

---

## ⏱ Time Breakdown

| Component | Time Spent | Notes |
|-----------|------------|-------|
| **Core Logic** | 2.0 hrs | developing `services.py`, DFS cycle detection. |
| **Refactoring** | 1.5 hrs | Moving logic to Service layer, implementing `TaskForm`. |
| **Infrastructure**| 1.0 hrs | Migrating to **uv** and configuring Docker/Postgres. |

---

