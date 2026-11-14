# Redesign: before and after

Screenshots of the same pages, logged in as the same manager account, with the same data from our shared database (taken November 13, 2026).
**Before** is `dev` right after PR #17. **After** is the redesign branch, which builds the suggestions in [`docs/design-suggestions`](../design-suggestions/README.md).

The data is mostly test records (one product, lots of +1/−1 adjustments), so the pages look emptier than they will with real products.

| # | Page | What changed |
|---|---|---|
| 1 | [Dashboard](#1-dashboard) | Recent orders shows Sales, with Restocks / Adjustments tabs; "Stock in vs. out" replaces the flat trend graph |
| 2 | [Inventory](#2-inventory) | Variants grouped under their product with a total; ⋯ menu; Adjust stock with − / + |
| 3 | [Add variants](#3-add-variants) | Pick sizes and colors, check the combinations you have, each with its own stock, location, price and cost |
| 4 | [Edit variant](#4-edit-variant) | Named "Satin Midi Dress – M / Black" instead of "Edit variant #1" |
| 5 | [Orders](#5-orders) | One actions column with a ⋯ menu; "Order #" |
| 6 | [Edit order](#6-edit-order) | Type, item, date and quantity can be corrected; explains the stock change before saving |
| 7 | [Employees](#7-employees) | ⋯ menu; "(you)"; + Add employee on the page instead of the sidebar |
| 8 | [Settings](#8-settings) | Change my password, low stock threshold, log out |
| 9 | [Manage catalog](#9-manage-catalog) | Same layout in every box; no "Product variants" box; + Add product inside its box |

---

## 1. Dashboard

| Before | After |
|---|---|
| ![Dashboard before](before-1-dashboard.png) | ![Dashboard after](after-1-dashboard.png) |

Before: 4 of the 5 "Recent Orders" were adjustments, and the trend graph was a flat line with no numbers.

## 2. Inventory

| Before | After |
|---|---|
| ![Inventory before](before-2-inventory.png) | ![Inventory after](after-2-inventory.png) |

After, in Adjust stock mode (⋯ → Adjust stock):

![Inventory adjust stock](after-2b-inventory-adjust-stock.png)

## 3. Add variants

| Before | After |
|---|---|
| ![Add variant before](before-3-add-variants.png) | ![Add variants after](after-3-add-variants.png) |

After, with sizes and colors picked (M / Black already exists, so it can't be added twice):

![Add variants with picks](after-3b-add-variants-picked.png)

## 4. Edit variant

| Before | After |
|---|---|
| ![Edit variant before](before-4-edit-variant.png) | ![Edit variant after](after-4-edit-variant.png) |

## 5. Orders

| Before | After |
|---|---|
| ![Orders before](before-5-orders.png) | ![Orders after](after-5-orders.png) |

After, with a row's ⋯ menu open:

![Orders menu](after-5b-orders-menu.png)

## 6. Edit order

| Before | After |
|---|---|
| ![Edit order before](before-6-edit-order.png) | ![Edit order after](after-6-edit-order.png) |

## 7. Employees

| Before | After |
|---|---|
| ![Employees before](before-7-employees.png) | ![Employees after](after-7-employees.png) |

## 8. Settings

| Before | After |
|---|---|
| ![Settings before](before-8-settings.png) | ![Settings after](after-8-settings.png) |

## 9. Manage catalog

| Before | After |
|---|---|
| ![Manage catalog before](before-9-manage-catalog.png) | ![Manage catalog after](after-9-manage-catalog.png) |
