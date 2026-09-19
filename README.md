<div align="center">

# ⚡ TWARVIS SCHOOL – STUDENT HUB

**Your command center for notes, past papers & study files.**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-4.2-092E20?style=for-the-badge&logo=django&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![Render](https://img.shields.io/badge/Deployed_on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**Live Demo → [twarvis-school.onrender.com](https://twarvis-school.onrender.com)**

</div>

---

## 🔥 What Is This?

A full-stack web app built to **organize, share, and manage** academic materials.  
No login required to browse public files. Just open, search, and download.

Built for students who want their study life **clean and fast**.

---

## 🚀 Features

| Feature | Description |
|---------|-------------|
| 📂 **File Vault** | Upload & manage PDFs, images, documents |
| 🔎 **Instant Search** | Find any file by name or tag in milliseconds |
| 🧮 **GPA Calculator** | Multi-system support (Diploma/Degree/Technical) |
| 🎨 **Themes** | Matrix, Dark, Light — switch on the fly |
| 🌐 **Live Backgrounds** | Matrix rain or aquarium (optional) |
| 🔐 **Private Files** | Passcode-protected folders for sensitive stuff |
| 📊 **Admin Dashboard** | Full control over files & users |

---

## 🛠️ Tech Stack
Backend → Python 3.11, Django 4.2.11 Database → Supabase (PostgreSQL + Storage) Frontend → HTML5, CSS3, JavaScript UI Icons → Font Awesome, Google Fonts Deployment → Render.com + Gunicorn + WhiteNoise


---

## ⚡ Quick Start

### Option 1 – Just Try It

Hit the live link: **https://twarvis-school.onrender.com**  
No sign-up. No hassle. Just browse.

### Option 2 – Run Locally

```bash
# Clone the repo
git clone https://github.com/twarvis/Twarvis-School.git
cd Twarvis-School

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
Set up your .env file:

SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SECRET_KEY=your_django_secret
Migrate and run:

python manage.py migrate
python manage.py runserver
Open http://127.0.0.1:8000 and you're in.

📁 Project Layout
Twarvis-School/
├── school/              # Main Django app
├── static/              # CSS, JS, images
├── templates/           # HTML templates
├── manage.py
├── requirements.txt
└── .env.example
🧑‍💻 Contributing
Want to improve this? Fork it, make your changes, and send a PR.

1. Fork the repo
2. Create a branch: git checkout -b cool-feature
3. Commit: git commit -m "Add cool feature"
4. Push: git push origin cool-feature
5. Open a Pull Request
📜 License
MIT — do whatever you want, just give credit.

Built by Twarvis
⭐ Star this repo if you like it — it fuels the code.

```
