-- Sample data for testing. Run the whole file with the plain lightning bolt.
-- Every INSERT here should succeed (green check).

USE Capstone_Project;

INSERT INTO Supplier (Name, Email, Phone) VALUES ('Houston Threads Co', 'orders@houstonthreads.com', '713-555-0101');
INSERT INTO Category (Category) VALUES ('Dresses'), ('Tops');
INSERT INTO Color (Color) VALUES ('Black'), ('Red');
INSERT INTO Size (Size) VALUES ('S'), ('M');
INSERT INTO Location (Location_Name) VALUES ('Main Store'), ('Warehouse');
INSERT INTO Transaction_Type (Transaction_Type) VALUES ('Restock'), ('Sale');
INSERT INTO Employee (First_Name, Last_Name, Role, Password) VALUES ('Test', 'User', 'Manager', 'placeholder_hash');

INSERT INTO Product (Name, Category_ID, Availability, Supplier_ID) VALUES ('Satin Midi Dress', 1, TRUE, 1);
INSERT INTO Product_Variant (Size_ID, Color_ID, Product_ID, Location_ID, Price, Cost) VALUES (2, 1, 1, 1, 79.99, 32.50);
INSERT INTO Inventory (Quantity, Variant_ID) VALUES (10, 1);
INSERT INTO Invoice (Transaction_Type_ID, Quantity_Change, Date, Variant_ID, Employee_ID) VALUES (1, 10, '2026-10-06', 1, 1);

-- Check: joins across all the related tables. Should return 1 row.
SELECT p.Name AS Product, c.Category, s.Size, col.Color, l.Location_Name,
       v.Price, i.Quantity AS In_Stock
FROM Product_Variant v
JOIN Product  p   ON v.Product_ID  = p.Product_ID
JOIN Category c   ON p.Category_ID = c.Category_ID
JOIN Size     s   ON v.Size_ID     = s.Size_ID
JOIN Color    col ON v.Color_ID    = col.Color_ID
JOIN Location l   ON v.Location_ID = l.Location_ID
JOIN Inventory i  ON i.Variant_ID  = v.Variant_ID;
