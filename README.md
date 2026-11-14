# CIS-4375-Capstone-Project

**Stack:** MySQL on AWS RDS (managed in MySQL Workbench) → Flask API (`backend/`) → Node/Express server (`frontend/server.js`) rendering EJS views (`frontend/`)

**Using the app:** see the [User Guide](frontend/USER_GUIDE.md).
**Setting it up:** see [Backend](#backend-flask-api-port-5000) and [Frontend](#frontend-express--ejs-port-8080) below, then [First manager account](#first-manager-account).

```
backend/
  api.py              Flask API routes (CRUD, login, invoices, stock adjustments)
  reporting.py        read-only reports: /inventory, /orders, /employees, /dashboard, store settings
  security.py         login tokens and the check that every API call is logged in
  sql.py              DBconnection (reuses connections), execute_read_query, execute_update_query
  creds.py            mycreds class: reads DB login from backend/.env.<env>
  create_manager.py   creates the first Manager account on a new database
  requirements.txt
frontend/
  server.js           Express routes
  lib/                charts (donut, stock in vs. out) and formatting helpers
  views/pages/        one .ejs file per page (index.ejs, ...)
  views/template/     shared pieces: head, nav, footer, messages, scripts, confirm, rowmenu (the ⋯ menu)
  tests/              offline checks (see Running the tests)
  USER_GUIDE.md       user guide
public/
  css/styles.css      all custom CSS
  main.js             menu, ⋯ menus, Inventory adjust buttons
  js/                 page scripts (add-variants.js, edit-order.js)
database/             create_capstone_tables.sql, sample_data.sql
docs/                 design suggestions and before/after screenshots
package.json
```

### Adding a feature

1. **Flask route** in `backend/api.py`: query the database and return JSON.
2. **Express route** in `frontend/server.js`: call that API with `apiGet` / `apiPost` / `apiPut` (they add the login token), then `page(req, res, 'name', {...})` to render it.
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

### First manager account
On a new, empty database nobody can log in yet, and adding employees needs a manager. Create the first one from the `backend` folder (with the same `.env.development` as the API):
```bash
python create_manager.py
```
It asks for a name, username, email and password, and saves a Manager. After that, managers add everyone else from **Employees → + Add employee**. (`database/sample_data.sql` also creates a "Test User" manager for testing.)

### Store settings
The low stock threshold (default 5) can be changed by a manager on **Settings**. It's saved in `backend/settings.json`, which is git-ignored; until someone saves one, `LOW_STOCK_THRESHOLD` in the backend `.env` file is used.

### Running the tests
These run offline (no database or servers needed), from the project folder:
```bash
node frontend/tests/check_routes.js        # routes exist, logins and manager-only actions are enforced, product flow
node frontend/tests/verify_templates.js    # every page template compiles and every form has its CSRF token
python frontend/tests/check_security.py    # login tokens, and that the API refuses calls without one
```

### Stopping a server that's still running
If a port is already in use (`EADDRINUSE` or "Address already in use"), something is still running on it. In PowerShell:
```powershell
8080, 5000 | ForEach-Object { Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```