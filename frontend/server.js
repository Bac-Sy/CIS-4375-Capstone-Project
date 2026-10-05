const path = require("path");
const env = process.env.NODE_ENV || "development";
require("dotenv").config({ path: path.join(__dirname, `.env.${env}`) });

const express = require("express");

const app = express();
const PORT = process.env.PORT || 3000;
const API_URL = process.env.API_URL || "http://localhost:5000/api";

app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));
app.use(express.static(path.join(__dirname, "public")));
app.use(express.urlencoded({ extended: true }));

app.get("/", async (req, res) => {
  let api;
  try {
    const response = await fetch(`${API_URL}/health`);
    api = await response.json();
  } catch (err) {
    api = { status: "unreachable", error: err.message };
  }
  res.render("index", { env, api });
});

app.listen(PORT, () => {
  console.log(`Frontend (${env}) running at http://localhost:${PORT}`);
});
