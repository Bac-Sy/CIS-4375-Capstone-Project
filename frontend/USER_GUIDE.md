# Space City Couture: User Guide

This guide is for the people who use the inventory app day to day: managers and employees.
It covers every page, in the order you'll usually need them.

**Managers** can do everything. **Employees** can do the day-to-day work: checking stock, recording sales and restocks, correcting counts, fixing orders, and editing a product's or variant's details from Inventory. They can't add or delete products, manage the catalog lists, change store settings or manage accounts. Section 11 lists exactly what's managers only.

A few things work the same on every page:

- **The ⋯ button** at the end of a row opens that row's actions (edit, adjust, delete…). Click outside it or press Esc to close it.
- **Anything that changes data asks first.** A pop-up names exactly what you're about to save or delete. Choose Cancel if it isn't right.
- **After you save,** a message at the top of the page says what happened, or what to fix.
- **On a phone,** the menu is behind the ☰ button at the top left. Wide tables scroll sideways.

---

## 1. Logging in and out

1. Open the website your team gave you (for example `http://localhost:8080`).
2. Enter your **username** and **password**, then choose **Log in**.
3. You land on the Dashboard with a "Welcome" message.

To **log out**, choose the arrow button next to your name at the bottom of the menu, or go to **Settings → Log out**.
You're logged out automatically after 8 hours.

**Forgot your password?** Ask a manager to reset it (Employees → ⋯ → Reset password).
After 10 wrong tries in 15 minutes, logging in is paused for that username for 15 minutes.

## 2. The Dashboard

The Dashboard is the first page after logging in. It has four cards:

| Card | What it shows |
|---|---|
| **Sales** | Money taken and units sold in the last 30 days, split by category |
| **Recent orders** | The 5 newest **Sales**. Use the **Restocks** and **Adjustments** tabs to see those instead. "View all" opens the Orders page with that type |
| **Inventory** | How many units are in stock right now, across how many items and products. Underneath, **Low stock** lists items at or below the low stock threshold (5 by default) |
| **Stock in vs. out** | Units sold and units restocked each week for the last 4 weeks, with a one-line summary, e.g. "Sold 41, restocked 30: stock is down 11 units". Hover over a bar to see its number. Adjustments aren't counted |

## 3. Checking inventory

Open **Inventory** from the menu.

- Each **product** is a bold row showing its category, how many variants (size / color combinations) it has, and its **Total** stock.
- Its **variants** are listed underneath with their location, price and **In stock** count.
- A red **Low** tag means that variant is at or below the low stock threshold. "**1 low**" on a product row means one of its variants is low.
- A grey **Not available** tag means the product has been switched off (see section 6).
- Choose **▾** next to a product to hide its variants, and **▸** to show them again.
- **Low stock only** shows just the low items, which is handy for making a reorder list. **All items** shows everything again.

## 4. Correcting a stock count (Adjust stock)

Use this when the shelf count doesn't match the app, for example after a recount or a damaged item.

1. On **Inventory**, choose **⋯** on the variant's row, then **Adjust stock**.
2. Use **−** and **+**, or type the correct count. The note underneath shows the change, e.g. "Was 5 · saves +2 as an Adjustment".
3. Choose **Save**, or **Cancel** to leave it as it was.

Every adjustment is saved as an **Adjustment** order with your name and the date, so there's always a record of who changed what. Counts can't go below 0.

## 5. Recording a sale or a restock

1. Open **Orders** and choose **+ Record Transaction**.
2. Choose the item (product, size and color).
3. Choose **Sale** (a customer bought it in the store) or **Restock** (stock arrived from the supplier).
4. Enter the **quantity** as a positive number and choose **Record**.

The stock updates straight away: a Sale takes units away, a Restock adds them.
You can't sell more than you have; the app says how many are in stock instead.

## 6. Products, sizes and colors (managers)

### Add a new product

1. Open **Manage catalog** and choose **+ Add product** in the Products box.
2. Enter the name and choose its category and supplier. Leave Availability as **Available** unless you're not selling it yet.
3. Choose **Add**. The app takes you straight to **Add variants**.

### Add sizes and colors (variants)

1. **Step 1:** tick every **size** and every **color** the product comes in.
2. **Step 2:** a row appears for each size / color combination. **Untick** any combination you don't actually have, e.g. if the dress only comes in white in medium.
3. For each ticked row, enter the **starting stock**, and the **price** and **cost** if they differ by size or color.
   - **Same location for all variants** (ticked by default) puts every row in the location you choose at the top. Untick it to pick a location per row.
   - **Same price and cost for all variants**: enter the price and cost at the top and tick this to use them for every row.
4. Choose **Add N variants**.

Combinations the product already has say **Already exists** and can't be added twice, so stock is never split between two identical variants.
You can also add variants later from **Inventory → ⋯ on the product → Add variants**.

### Edit or switch off a product

- **Inventory → ⋯ on the product → Edit product** (or Manage catalog → ⋯ → Edit product).
- Change the name, category or supplier, and choose **Save changes**.
- To stop selling a product without losing its history, set **Availability** to **Not available**. It stays on Inventory with a **Not available** tag.
- **Delete product** only works if the product has no variants. This keeps order history from being lost.

### Edit a variant

**Inventory → ⋯ on the variant → Edit variant.** The page is titled with the variant's name, e.g. "Satin Midi Dress – M / Black".
You can change its size, color, location, price and cost.
**Delete variant** (managers) only works for a variant that was added by mistake: one with 0 in stock that has never been sold, restocked or adjusted. Anything with history is kept so the sales records stay complete.

## 7. Suppliers, categories, locations, colors and sizes (managers)

These lists live on **Manage catalog**, one box each. Every box works the same way:

- **Add:** fill in the form at the bottom of the box and choose **Add**. A supplier needs a name; email and phone are optional.
- **Change:** choose **⋯** next to an entry.
  - Suppliers, categories and locations: **Edit** opens their page, and **Delete** removes them (only if nothing uses them).
  - Colors and sizes: **Rename** changes the name everywhere it's used.

## 8. Reviewing and correcting orders

Open **Orders** to see every Sale, Restock and Adjustment, newest first. Use the **All / Adjustment / Restock / Sale** tabs to filter.

**To fix a mistake:** choose **⋯ → Edit order**.

- The top of the page says exactly which order it is, e.g. "Sale · Satin Midi Dress – M / Black · −2 · 11/12/2026 · recorded by Test".
- You can change the **type**, the **item**, the **date** and the **quantity change**. A Sale is negative, a Restock is positive, and an Adjustment can be either.
- The **What saving will do** box explains the stock change before you save. For example, moving a sale to a different color puts the units back on the old one and takes them off the new one.
- If an item doesn't have enough stock, nothing is saved and the message says why.
- **Recorded by** can't be changed: it's the record of who entered the order.

**Managers** can also **delete** an order (⋯ → Delete order). Deleting undoes its stock change.

## 9. Best sellers report

Open **Best sellers** to rank what sells most.

- Choose a period: last 7, 30 or 90 days, or all time.
- **By product** adds up all sizes and colors of a product. **By item** ranks each size / color separately.
- Each row shows units sold and revenue. Items that sold the same amount share a rank.

## 10. Settings

- **My account:** your name, username, email and role. Ask a manager to change these.
- **Change my password:** enter your current password, then the new one twice (at least 8 characters).
- **Store settings** (managers): the **low stock threshold**, the count at or below which items are flagged as low on Inventory and the Dashboard.
- **Log out.**

## 11. Employees and permissions

Open **Employees** to see everyone with an account. Your own row says **(you)**.

**Managers** can:

- **+ Add employee:** name, username, email, role (Employee or Manager) and a starting password.
- **⋯ → Edit employee:** change details or role. You can't remove your own Manager role.
- **⋯ → Reset password:** set a new password for someone who forgot theirs.
- **⋯ → Delete employee:** they can no longer log in. You can't delete yourself.

**Managers only:**

| Page or action | Employees see |
|---|---|
| Manage catalog (products, suppliers, categories, locations, colors, sizes) | Not in the menu |
| Add product, Add variants, delete anything | Hidden, or an "Access denied" page explaining that manager permissions are needed |
| Add, edit or delete employees; reset passwords | No ⋯ menu on the Employees page |
| Delete an order | Only "Edit order" in the ⋯ menu |
| Store settings (low stock threshold) | Not shown on Settings |

---

## For whoever sets up the app

Installation and running the servers are covered in the project [README](../README.md).
On a **new, empty database**, create the first manager account with `python create_manager.py` in the `backend` folder; after that, managers add everyone else from the Employees page.
