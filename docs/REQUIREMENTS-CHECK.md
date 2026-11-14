# Requirements check (handoff)

Each requirement from the Requirements Traceability Matrix: every feature its "Proposed Feature / Design Element" column promises, where it is in the app, and how it was checked.
Checked on November 13, 2026, against the `bianca-redesign` branch (PR #18), on the shared development database, logged in as a test manager. This was a line-by-line review of every RTM column, plus the problems noted in the RTM's Notes column. The demo script (steps 1–10) was then run end to end on the real app: 28 of 28 checks passed.

**Summary:** R-01 to R-10 and R-13 are met; several need RTM wording updates (listed below). R-09 is out of scope. **R-11 is in progress**: the user guide is still being written (Madison), and usability is judged by the sponsor at the demo. **R-12 is mostly met**: the audit trail is complete (Edit history); the remaining gaps are database-side (see the R-12 row and "Still open").

| ID | Promised element | Where in the app | Status |
|---|---|---|---|
| **R-01** | Central product records: name, category, size, color, price | `Product` and `Product_Variant` tables; **Inventory** page (every product with its size / color variants, location, price, stock); **Manage catalog** | Met |
| | SKU | Not built: products and variants are identified by their database IDs | Wording |
| | "shirt products" | The store sells clothing in general (dresses, tops…) | Wording |
| | RTM note: edit variant showed no success message | Every edit page shows "… updated." after saving | Fixed |
| **R-02** | Quantity on hand per product / variant, shown in the inventory view | `Inventory.Quantity` (can't go below 0); **Inventory** In stock column and product **Total**; **Dashboard → Inventory** (units in stock right now); **Inventory report** | Met |
| **R-03** | Add products | **Manage catalog → + Add product** → **Add variants** (many sizes / colors at once, duplicates blocked) | Met |
| | Edit products | **Edit product** / **Edit variant** (managers), with a confirm pop-up | Met |
| | Active / inactive flag | **Availability** on Edit product; "Not available" tag on Inventory, the Inventory report and Record transaction | Met |
| **R-04** | Receiving form | **Orders → + Record Transaction → Restock** (shows "From: \<supplier\>") | Met |
| | Sale form | **Record Transaction → Sale** | Met |
| | Transaction log | `Invoice` table; **Orders** page with type filter and **Newer / Older** paging (all orders reachable); **Sales report** lists every sale in a date range | Met |
| | RTM note: no UI form for Restock or Sale | Record Transaction | Fixed |
| **R-05** | Quantities update automatically on save | Sales, restocks, adjustments, order edits and order deletes each update stock **in the same database transaction** as the order (all-or-nothing, with the stock row locked so two sales at once can't oversell). The API refuses changes that would take stock below 0 | Met |
| **R-06** | Sales entry form linked to product and variant | Record Transaction: every sale is tied to a product, size and color | Met |
| | Sale-type (in-person) field | All sales are in-person (no online or dropship channel), so no extra field is needed | Wording |
| **R-07** | Low / out-of-stock indicators | Red **Low** / **Out** tags on Inventory; **Dashboard → Low stock** ("Out of stock" at 0); Inventory report status column | Met |
| | Filter | **Inventory → Low stock only**; **Inventory report → Low and out of stock** (a reorder list with each item's supplier) | Met |
| | Reorder threshold per product | One **low stock threshold** for the whole store, set by managers on **Settings** | Wording |
| **R-08** | Supplier table linked to products | `Supplier` table; every product has a supplier; **Manage catalog → Suppliers** (add / edit / delete; email and phone optional) | Met |
| | Purchase / receiving records | Purchases are recorded as **Restock** orders (quantity, date, who). Orders, the Dashboard and Edit order show "from \<supplier\>". The supplier shown is the product's *current* supplier; it isn't stored on each order | Met (see note) |
| | Which products to reorder | Inventory report → Low and out of stock, with supplier | Met |
| | RTM notes: no purchasing form; edit supplier showed no message | Record Transaction → Restock; edit pages show "… updated." | Fixed |
| **R-09** | Stocked vs. dropshipped | — | Out of scope |
| **R-10** | **Inventory summary report** | **Reports → Inventory report**: every item with category, supplier, location, stock, status and price; managers also see cost and stock value (at cost and at price) with totals; a low and out of stock view | Met |
| | **Sales report** | **Reports → Sales report** for any dates (this month, last month, last 30 days, this year or custom): sales, units, number of sales, average sale; managers also see cost of goods and gross profit; by product, by category, by day, and every sale with totals | Met |
| | Printable and exportable | Every report (including Best sellers and Edit history) has **Preview PDF** (a real PDF in a preview window with page thumbnails, zoom, search, **Download PDF** and **Print**) and **Download Excel** (an .xlsx with dates, money and column widths set) | Met |
| | Dashboard | Sales (last 30 days, by category), recent orders by type, current inventory, low stock, stock in vs. out by week | Met |
| | Product performance | **Reports → Best sellers** (7 / 30 / 90 days / all time, by product or by size and color) | Met |
| | RTM note: Fail (dashboard showed $0, UTC dates) | Fixed in PR #10: dates are saved in local time | Retest |
| **R-11** | Simple navigation | One sidebar: Dashboard, Inventory, Orders, Reports, Employees, Settings, Manage catalog (managers) | Met |
| | Consistent layout | The same table layout, ⋯ menu, confirm pop-ups and messages on every page; names instead of ID numbers | Met |
| | User guide | `frontend/USER_GUIDE.md`: outline only. **Madison is writing it.** It should cover Reports (print / CSV), Settings (password, threshold), the low stock filter and Best sellers | **In progress** |
| | Usability testing | With the sponsor at the demo (Nov 16–17) | Not started |
| **R-12** | Input validation | Every form is checked by the website before it reaches the API; the stock, order, report and password API routes also check their input. The older catalog API routes (suppliers, categories, products…) rely on the website's checks | Met (API partly) |
| | Transaction audit trail | Every stock change is an order with who and when, recorded under the logged-in person (the API enforces it). **Reports → Edit history** (managers) lists every change made in the app, with who made it, when, and each value before → after: order edits and deletes, stock adjustments, products, variants, suppliers, categories, locations, colors, sizes, employees, password changes (never the password) and store settings. It has filters, Print and CSV. Any employee can **fix** an order; **only managers can delete** one | Met |
| | Data integrity constraints | Foreign keys, UNIQUE and CHECK (quantity, price, cost ≥ 0) in the schema; multi-step stock changes are all-or-nothing; duplicate size / color variants are blocked by the app | Mostly met (see "Still open") |
| | Backups | Not part of the app: AWS RDS automated backups | Wording |
| **R-13** | Authentication | Login for every page and every API call (signed tokens); passwords stored as argon2 hashes; session renewed at login; login rate limiting; CSRF tokens on every form | Met |
| | Access control | **Managers only:** Manage catalog, adding / editing / deleting products, variants, suppliers, categories and locations, deleting orders, employee administration, store settings, and cost / profit in reports. **Employees:** inventory, adjust stock, record transactions, fix orders, reports without cost, their own password. Checked by the website; the API also enforces deletes, employee changes, store settings and "who recorded it" | Met |
| | Secure data storage | Real `.env` files are never committed (git history checked); cookies are httpOnly (and secure in production); every database query uses parameters (SQL injection doesn't work) | Met |
| | RTM note: blocked page said "Please log in" | Now says "Manager permissions are required for this action." | Fixed |

## Matrix updates (wording)

| ID | Matrix says | Update it to |
|---|---|---|
| R-01 | "shirt products"; "Central product table (… **SKU** …)" | "clothing products"; products and variants are identified by their database IDs, with no SKU field |
| R-04 | Notes: "No UI form for Restock or Sale" | Recorded on Orders → Record Transaction |
| R-06 | Blocked: no sale form, no in-person field | Sales are recorded on Record Transaction. All sales are in-person, so no extra field is needed |
| R-07 | "Reorder-threshold setting **per product**" | One low stock threshold for the whole store, set by managers on Settings |
| R-08 | Notes: "No UI form for purchasing"; edit supplier showed no message | Purchases are Restocks on Record Transaction; edit pages confirm saves |
| R-09 | Blocked: waiting on sponsor | Out of scope: the store only sells physical stock it holds |
| R-10 | Fail: dashboard showed $0 | Fixed (local dates, PR #10). Add the Reports pages (sales report, inventory report, print / CSV). Retest |
| R-11 | Not Started | User guide in progress (Madison); usability judged at the demo |
| R-12 | "… transaction audit trail …"; "… data integrity constraints, **backups**" | Audit trail: Reports → Edit history (stored in `backend/edit_history.jsonl`, not the database, so the ERD and data dictionary don't change). Backups: AWS RDS automated backups for the database, plus copying `backend/edit_history.jsonl` and `backend/settings.json` |
| R-13 | Note: "Please log in" on the blocked page | Fixed |

## Still open before handoff

These need the team (or the database owner), not app code:

1. **User guide** (R-11): Madison is finishing `frontend/USER_GUIDE.md`.
2. **Clean up test data and accounts** on the database being handed over:
   - TEST Amrin Dress and TEST Amrin Supplier (they appear in every report)
   - the test managers "Test User" (`database/sample_data.sql` publishes its password) and Tester1
   - Satin Midi Dress M / Black has cost $80.99 and price $32.00, so reports show a loss on it. The sample data had them the other way round.
3. **Database constraints** (R-12) to add on the live RDS database:
   - The `Invoice.Transaction_Type_ID` foreign key is missing there (see `create_capstone_tables.sql`).
   - Consider `UNIQUE (Product_ID, Size_ID, Color_ID)` on `Product_Variant`, so duplicates are blocked by the database, not only the app.
   - Run `UPDATE Supplier SET Email = NULL WHERE Email = ''`. Blank supplier emails are now saved as empty (NULL); this fixes older rows.
4. **Backups:** confirm RDS automated backups are on, with the retention you want. Two files live on the computer that runs the API, not in the database. Back them up too:
   - `backend/edit_history.jsonl`: the edit history. It can't be recreated if it's lost.
   - `backend/settings.json`: the low stock threshold. It can just be re-entered.
5. **Hosting:** the app runs locally (Flask on port 5000, Express on 8080); there's no production hosting.
6. **First login on a new database:** run `python backend/create_manager.py`.

## Known limits (fine for handoff, worth knowing)

- **Reports use current prices:** sales reports value past sales at each item's *current* price and cost, because orders don't store the price at the time of the sale. The report says so.
- **Supplier on restocks:** a restock shows the product's current supplier; it isn't saved on the order.
- **Editing an order** keeps its original "Recorded by"; the edit itself (who, when, before → after) is in Edit history. Any employee can fix an order; only managers can delete one.
- **The edit history is a file,** so it covers changes made on the computer that runs the API. That's fine for the sponsor, whose app runs on one computer. If the database is changed some other way (e.g. directly in MySQL Workbench), it isn't recorded.

## How it was checked

- **Offline tests (no database needed):** `node frontend/tests/check_routes.js`, `node frontend/tests/verify_templates.js`, `python frontend/tests/check_security.py`. All pass. They cover routes, logins, manager-only pages (including the new ones), employee access, every template, and CSRF tokens.
- **Manual checks on the real app (scripts run by the team, not saved in the repo):**
  - the demo script, steps 1–10 (28 checks)
  - adding variants, adjusting stock and editing orders (32 checks)
  - read-only checks of the converted queries, including injection attempts
  - report totals compared against the raw orders
  - Every test record was deleted afterwards.
