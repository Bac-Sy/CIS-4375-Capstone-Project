# Requirements check (handoff)

Each requirement from the Requirements Traceability Matrix, where it is in the app, and how it was checked.
Checked on November 13–14, 2026, against the `bianca-redesign` branch (PR #18), on the shared development database, logged in as a test manager.

**Status: all in-scope requirements are met.** R-09 is out of scope (the store only sells physical stock). The matrix needs a few wording updates so its "Proposed Feature" column matches what was built; they're listed under [Matrix updates](#matrix-updates).

| ID | Requirement | Where in the app | How it was checked | Status |
|---|---|---|---|---|
| R-01 | Centralized records of all products | **Inventory** (every product with its size / color variants, location, price, stock); **Manage catalog** (products, suppliers, categories, locations, colors, sizes). Records are identified by their database IDs (Product_ID, Variant_ID) | Demo walkthrough steps 2–4 | Pass* |
| R-02 | Track the quantity of each product | **Inventory**: In stock per variant and a Total per product; **Dashboard → Inventory**: units in stock right now | Walkthrough steps 2, 4, 6–8; stock checked after every change | Pass |
| R-03 | Add, edit and deactivate products | **Manage catalog → + Add product**, **Add variants**, **Edit product** (Availability → Not available shows a "Not available" tag on Inventory) | Walkthrough steps 4–5 | Pass |
| R-04 | Record inventory received and sold | **Orders → + Record Transaction** (Restock / Sale); **Edit order** to correct one | Walkthrough steps 6–7; edit-order tests (change item, type, date, quantity) | Pass |
| R-05 | Update quantities automatically | Every Sale, Restock, Adjustment, order edit and order delete updates stock in the same step (the API refuses changes that would go below 0) | Walkthrough 6–8; 32 save tests (stock checked before and after each) | Pass |
| R-06 | Record in-person sales linked to products | **Record Transaction → Sale**: every sale is tied to a product, size and color. All sales are in-person (no online or dropship channel) | Walkthrough step 7 | Pass* |
| R-07 | Identify low and out-of-stock products | Red **Low** tags on Inventory; **Low stock only** filter; **Dashboard → Low stock** list; the threshold is set by managers on **Settings** | Walkthrough step 8; threshold save tests | Pass* |
| R-08 | Supplier and purchasing information | **Manage catalog → Suppliers** (add / edit / delete); every product has a supplier; purchases are recorded as **Restock** orders | Walkthrough steps 3, 4, 6 | Pass |
| R-09 | Stocked vs. dropshipped products | — | — | Out of scope |
| R-10 | Reports on current inventory and sales | **Dashboard** (sales total and by category, current inventory, low stock, stock in vs. out by week, recent orders by type); **Best sellers** report (7 / 30 / 90 days / all time, by product or by item); **Orders** filtered by type | Walkthrough step 9; the UTC date bug that made this fail on 11/11 was fixed in PR #10 | Pass |
| R-11 | Easy to learn and use | Same layout and ⋯ menu on every table; names instead of ID numbers; confirm pop-ups name what's being changed; [User Guide](../frontend/USER_GUIDE.md) | Judged by the sponsor during the demo | Ready for sponsor review |
| R-12 | Accurate, reliable inventory information | Input checks on every form and API route; every stock change is an order with who and when (audit trail); stock can't go below 0; duplicate variants blocked; variants and products with history can't be deleted; order edits and stock adjustments save all-or-nothing | Save tests (bad input, duplicates, negative counts, oversized sales) | Pass* |
| R-13 | Protect business information | Login required for every page and every API call (signed tokens); passwords stored as argon2 hashes; manager-only pages and actions checked by the website (deletes and employee changes are also checked by the API); CSRF tokens on every form; login rate limiting; **every database query uses parameters** (45 older queries were converted, so SQL injection doesn't work) | `frontend/tests/check_security.py`, `check_routes.js`; injection attempts on the API; employee view checks | Pass |

\* Passes, but the matrix wording should be updated. See below.

## Matrix updates

| ID | Matrix says | Update it to |
|---|---|---|
| R-01 | "Central product table (name, category, size, color, **SKU**, price)" | Products and variants are identified by their database IDs (Product_ID, Variant_ID); no SKU field |
| R-06 | Blocked: "no form in the UI to record a sale, and no field to mark a sale as in-person" | Sales are recorded on Orders → Record Transaction. All sales are in-person, so no extra field is needed |
| R-07 | "**Reorder-threshold** setting per product" | One **low stock threshold** for the whole store, set by managers on Settings |
| R-09 | Blocked: waiting on sponsor | Out of scope: the store only sells physical stock it holds |
| R-10 | Fail: dashboard sales showed $0 | Fixed (dates are saved in local time, PR #10). Retest |
| R-12 | "…data integrity constraints, **backups**" | The app doesn't make backups. Use AWS RDS automated backups (on by default for RDS; check the retention period in the AWS console) |
| R-13 | Note: "The blocked page says 'Please log in'…" | Fixed: it now says "Manager permissions are required for this action" |
| R-03, R-08, R-01 | Notes about edit pages not showing a success message | Fixed: every edit page shows "… updated." after saving |

## Not covered by the app (decide before handoff)

- **Backups:** handled by AWS RDS, not the app. Confirm automated backups are on for the production database.
- **Hosting:** the app runs locally (Flask on port 5000, Express on 8080). The README covers setup; there's no production hosting set up.
- **First login on a new database:** run `python backend/create_manager.py` to create the first manager.
