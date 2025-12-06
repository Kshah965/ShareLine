# 🧺 ShareLine — A Donation Matching Platform

ShareLine is a **FastAPI + Alpine.js + DaisyUI** web application that connects **donors** with **affected students** who need essential items on campus.

Donors can list items, and students can request them. Donors then review and approve/decline requests through a clean dashboard interface.

---

## 🌟 Features

### 👤 Authentication
- User registration and login
- Distinct roles: **donor** and **affected student**

### 🎁 Donor Dashboard
- Add new donation items
- View and manage existing items
- Review incoming requests
- Approve or decline requests using a **DaisyUI modal**

### 📦 Affected Dashboard
- Browse available items
- Send requests for needed items
- Track request status

### 💅 Frontend
- Responsive UI with **DaisyUI components**
- TailwindCSS styling
- Modals, alerts, and loading states using **Alpine.js**

### ⚙️ Backend
- **FastAPI** REST endpoints
- **SQLModel** data modeling
- Local SQLite DB for development (`shareline.db`)

---

## 🛠️ Tech Stack

| Layer      | Tools |
|-----------|------|
| Backend   | FastAPI, SQLModel |
| Frontend  | Alpine.js, TailwindCSS, DaisyUI |
| Database  | SQLite (local development) |
| Auth      | OAuth2 with Bearer tokens |
| Styling   | Tailwind, PostCSS |
| Dev       | VS Code Dev Container |

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Kshah965/ShareLine.git
cd ShareLine
```

### 2. Install backend dependencies

> Ensure you're running inside your virtual env or container.

```bash
pip install fastapi uvicorn sqlmodel python-multipart
```

Or, if you have `requirements.txt`, run:

```bash
pip install -r requirements.txt
```

### 3. Run the development server

```bash
uvicorn main:app --reload
```

Open the app in your browser:

➡️ http://127.0.0.1:8000

---

## 📁 Project Structure

```
shareline/
├── main.py            # FastAPI application
├── models.py          # SQLModel database models
├── schemas.py         # Pydantic schemas
├── routers/           # API route definitions
├── templates/         # HTML templates (Jinja2)
├── static/            # CSS, JS, images
├── tailwind.config.js # Tailwind/DaisyUI settings
└── postcss.config.js  # PostCSS build config
```

---

## 🧪 API Examples

### List all items

```
GET /items/
```

### Create a new item

```
POST /items/
```

### Approve/Reject a request

```
PATCH /requests/{id}
```

---

## 🛡️ Security Notes

- `.env` is **ignored** in `.gitignore`
- `shareline.db` is **ignored** so no personal data is committed
- `node_modules/` is **ignored**

✔️ Safe for public posting on GitHub

---

## 🧑‍💻 Author

**Brunna M. (aka Kshah)**
UMass Amherst — CICS

---

## 📄 License

MIT (feel free to reuse and modify)

---

## 🌟 Future Improvements

- Email notifications for approved requests
- Real PostgreSQL deployment
- Admin dashboard for ShareLine staff
- Deployment on Fly.io / Railway.app / Heroku

---

If you like this project — ⭐️ it on GitHub!
