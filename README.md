# CIS-4375-Capstone-Project

**Stack:** MySQL on AWS RDS (managed in MySQL Workbench) → Flask API (`backend/`) → Node/Express server rendering EJS views (`frontend/`)

```
backend/     Flask API (Python)
frontend/    Express server + EJS views (Node)
```

## Environments & branches

| Branch    | Environment | Purpose                                   |
|-----------|-------------|-------------------------------------------|
| `main`    | production  | Final, working code only                  |
| `test`    | test        | Code being tested before release          |
| `dev`     | development | Everyone's work combined                  |
| `<name>`  | (local)     | Your personal branch, e.g. `bianca`       |

Each environment has its own env files. Database connection details (AWS RDS endpoint, user, password) go in those files, never in GitHub.

## Team workflow

**Ops / reviewer:** @AmrinLamisa. Only ops merges into `dev`, `test`, and `main`.

```
bianca ─┐
duy ────┼─► PR into dev ─► (ops) dev → test ─► (ops) test → main
...  ───┘
```

### First-time setup (everyone)

```bash
git clone https://github.com/Bac-Sy/CIS-4375-Capstone-Project.git
cd CIS-4375-Capstone-Project
git checkout dev
git checkout -b yourname        # create YOUR branch from dev
git push -u origin yourname
```

### Daily work

```bash
git checkout yourname
git pull origin dev             # get the latest team code first
# ...write code...
git add .
git commit -m "Describe what you did"
git push
```

Then open a pull request on GitHub: **base: `dev` ← compare: `yourname`**. AmrinLamisa reviews and merges it.

**Never push directly to `dev`, `test`, or `main`.**

### Ops: promoting code

1. Review and merge member PRs into `dev`.
2. When `dev` is stable, open a PR `dev` → `test` and test against the test database.
3. When `test` passes, open a PR `test` → `main` (production).

## Running locally

### Database
The team's MySQL database is hosted on AWS RDS. Ask the team for the RDS endpoint, username, and password, and put them in your backend `.env` file (see below).

### Backend (Flask API, port 5000)
```bash
cd backend
python -m venv venv
venv\Scripts\activate           # Windows  (Mac: source venv/bin/activate)
pip install -r requirements.txt
copy .env.development.example .env.development   # Mac: cp ...  then fill in the RDS details
python app.py
```
Use `APP_ENV=test` or `APP_ENV=production` to switch environments.

### Frontend (Express + EJS, port 3000)
```bash
cd frontend
npm install
copy .env.development.example .env.development   # Mac: cp ...
npm run dev            # development
npm run start:test     # test
npm start              # production
```
Open http://localhost:3000. The page shows whether the Flask API is reachable.

> Real `.env.*` files are git-ignored. Never commit passwords.
