# CIS-4375-Capstone-Project

**Stack:** MySQL on AWS RDS (managed in MySQL Workbench) → Flask API (`backend/`) → Node/Express server (`frontend/server.js`) rendering EJS views (`frontend/`)

```
backend/
  api.py              Flask API routes
  sql.py              DBconnection, execute_read_query, execute_update_query
  creds.py            mycreds class: reads DB login from backend/.env.<env>
  requirements.txt
frontend/views/
  pages/              one .ejs file per page (index.ejs, ...)
  template/           shared pieces: head, nav, footer, messages, scripts
public/css/           custom CSS (styles.css)
frontend/
    server.js         Express routes
package.json
```

### Adding a feature

1. **Flask route** in `backend/api.py`: query the database and return JSON.
2. **Express route** in `frontend/server.js`: call that API with `axios`, then `res.render()` a page.
3. **Page** in `frontend/views/pages/`: copy `index.ejs` and change the `<main>` section.

Always pass user input as query parameters, never with `%` formatting (that allows SQL injection):

```python
execute_read_query(mycon, "select * from books where Title = %s", (title,))
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

### Database
The team's MySQL database is hosted on AWS RDS. Ask the team for the RDS endpoint, username, and password, and put them in your backend `.env` file (see below).

### Backend (Flask API, port 5000)
```bash
cd backend
python -m venv venv
venv\Scripts\activate           # Windows  (Mac: source venv/bin/activate)
pip install -r requirements.txt
copy .env.development.example .env.development   # Mac: cp ...  then fill in the RDS details
python -c "import secrets; print(secrets.token_hex(32))"   # generates AUTH_TOKEN_SECRET (see below)
python api.py
```
Before running `python api.py`, set `AUTH_TOKEN_SECRET` in `backend/.env.development`:

- Generate a secret with `python -c "import secrets; print(secrets.token_hex(32))"`.
- Paste it into `backend/.env.development` as `AUTH_TOKEN_SECRET=...`. It must be at least 32 characters and different from the frontend's `SESSION_SECRET`.
- Without it, login fails with "Flask or MySQL may be unavailable."
- Only put real secrets in `.env.development`, never in the `.example` files, which are committed.

Set `APP_ENV=test` or `APP_ENV=production` to switch environments. Visit http://localhost:5000/db/check to confirm the database connection.

### Frontend (Express + EJS, port 8080)
The Express server is `frontend/server.js`. `npm run dev` starts `frontend/server.js`, not the old top-level `server.js`.

In a second terminal, from the project folder (not `backend/`):
```bash
npm install
copy .env.development.example .env.development   # Mac: cp ...  then set SESSION_SECRET
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"   # generates SESSION_SECRET
npm run dev            # development (runs frontend/server.js)
npm run start:test     # test
npm start              # production
```
Open http://localhost:8080. The page shows whether the Flask API is reachable. The Flask backend must be running separately on port 5000.

> Real `.env.*` files are git-ignored. Never commit passwords.