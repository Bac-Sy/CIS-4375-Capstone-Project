//load env file for the current environment (development | test | production)
const path = require('path');
const env = process.env.NODE_ENV || 'development';
require('dotenv').config({ path: path.join(__dirname, `.env.${env}`) });

//load express modules
const express = require('express');
const axios = require('axios');
const session = require('express-session');          //session management setup. Used to keep user profiles.

const API_URL = process.env.API_URL || 'http://127.0.0.1:5000';   //address of the flask API
const PORT = process.env.PORT || 8080;

//create app with express
const app = express();

//set views property
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'frontend', 'views', 'pages'));
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(session({
    secret: process.env.SESSION_SECRET,              //set in .env, never hardcode it here
    resave: false,
    saveUninitialized: false
}));


app.get('/', (req, res) => {
    axios.get(`${API_URL}/health`)                   //checks that the flask API is running
        .then((response) => {
            res.render('index', { message: `Connected to the API (${response.data.env} environment).` });
        })
        .catch(() => {
            res.render('index', { message: 'Could not reach the API. Make sure backend/api.py is running.' });
        });
});


//run application on a port
app.listen(PORT);
console.log(`Application (${env}) is listening on port ${PORT}`);
