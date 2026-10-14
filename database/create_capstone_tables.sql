-- Space City Couture inventory system
-- Matches: ERD - Bianca's Final Changes (location lookup table, employee password)
-- Run the whole file with the plain lightning bolt.

USE Capstone_Project;

-- ---------- Lookup / parent tables (no foreign keys) ----------

CREATE TABLE Supplier (
    Supplier_ID   INT AUTO_INCREMENT PRIMARY KEY,
    Name          VARCHAR(100) NOT NULL,
    Email         VARCHAR(100) UNIQUE,
    Phone         VARCHAR(20)
);

CREATE TABLE Category (
    Category_ID   INT AUTO_INCREMENT PRIMARY KEY,
    Category      VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE Color (
    Color_ID      INT AUTO_INCREMENT PRIMARY KEY,
    Color         VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE Size (
    Size_ID       INT AUTO_INCREMENT PRIMARY KEY,
    Size          VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE Location (
    Location_ID   INT AUTO_INCREMENT PRIMARY KEY,
    Location_Name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE Transaction_Type (
    Transaction_Type_ID INT AUTO_INCREMENT PRIMARY KEY,
    Transaction_Type    VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE Employee (
    Employee_ID   INT AUTO_INCREMENT PRIMARY KEY,
    First_Name    VARCHAR(50) NOT NULL,
    Last_Name     VARCHAR(50) NOT NULL,
    Role          VARCHAR(50) NOT NULL,
    Password      VARCHAR(255) NOT NULL
);

-- ---------- Child tables (have foreign keys) ----------

CREATE TABLE Product (
    Product_ID    INT AUTO_INCREMENT PRIMARY KEY,
    Name          VARCHAR(100) NOT NULL,
    Category_ID   INT NOT NULL,
    Availability  BOOLEAN NOT NULL DEFAULT TRUE,
    Supplier_ID   INT NOT NULL,
    FOREIGN KEY (Category_ID) REFERENCES Category(Category_ID),
    FOREIGN KEY (Supplier_ID) REFERENCES Supplier(Supplier_ID)
);

CREATE TABLE Product_Variant (
    Variant_ID    INT AUTO_INCREMENT PRIMARY KEY,
    Size_ID       INT NOT NULL,
    Color_ID      INT NOT NULL,
    Product_ID    INT NOT NULL,
    Location_ID   VARCHAR(20) NOT NULL,   -- str per ERD (no FK: MySQL can't link str to int)
    Price         DECIMAL(10,2) NOT NULL CHECK (Price >= 0),
    Cost          INT NOT NULL CHECK (Cost >= 0),
    FOREIGN KEY (Size_ID)     REFERENCES Size(Size_ID),
    FOREIGN KEY (Color_ID)    REFERENCES Color(Color_ID),
    FOREIGN KEY (Product_ID)  REFERENCES Product(Product_ID)
);

CREATE TABLE Inventory (
    Inventory_ID  INT AUTO_INCREMENT PRIMARY KEY,
    Quantity      INT NOT NULL DEFAULT 0 CHECK (Quantity >= 0),
    Variant_ID    INT NOT NULL,
    FOREIGN KEY (Variant_ID) REFERENCES Product_Variant(Variant_ID)
);

CREATE TABLE Invoice (
    Invoice_ID          INT AUTO_INCREMENT PRIMARY KEY,
    Transaction_Type_ID INT NOT NULL,
    Quantity_Change     INT NOT NULL,     -- negative for sales/removals
    Date                DATE NOT NULL,
    Variant_ID          INT NOT NULL,
    Employee_ID         INT NOT NULL,
    FOREIGN KEY (Variant_ID)          REFERENCES Product_Variant(Variant_ID),
    FOREIGN KEY (Employee_ID)         REFERENCES Employee(Employee_ID)
);

-- ---------- Check ----------
SHOW TABLES;   -- should list 11 tables
