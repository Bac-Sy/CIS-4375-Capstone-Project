-- Run once per environment, e.g.:
--   mysql -u root -p < database/schema.sql
CREATE DATABASE IF NOT EXISTS capstone_dev;
CREATE DATABASE IF NOT EXISTS capstone_test;
CREATE DATABASE IF NOT EXISTS capstone_prod;

-- Tables go below. Run them against each database (USE capstone_dev; ...).
