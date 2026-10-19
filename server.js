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


//EDIT SUPPLIER: load the supplier and show the form with current values filled in
app.get('/suppliers/:id/edit', (req, res) => {
    axios.get(`${API_URL}/api/suppliers`)
        .then((response) => {
            const supplier = response.data.find(s => s.Supplier_ID == req.params.id);
            if (!supplier) {
                return res.render('index', { message: `No supplier found with ID ${req.params.id}.` });
            }
            res.render('edit-supplier', { supplier: supplier });
        })
        .catch(() => {
            res.render('index', { message: 'Could not load the supplier. Make sure backend/api.py is running.' });
        });
});

//EDIT SUPPLIER: send the changes to the flask API
app.post('/suppliers/:id/edit', (req, res) => {
    const updated = {
        Name: req.body.Name,
        Email: req.body.Email || null,     //blank becomes null so the UNIQUE email rule doesn't trip
        Phone: req.body.Phone || null
    };
    axios.put(`${API_URL}/api/suppliers/${req.params.id}`, updated)
        .then(() => {
            res.render('index', { message: `Supplier ${req.params.id} updated.` });
        })
        .catch(() => {
            res.render('index', { message: 'Could not save changes. Make sure backend/api.py is running.' });
        });
});


//EDIT CATEGORY: load the category and show the form with current values filled in
app.get('/categories/:id/edit', (req, res) => {
    axios.get(`${API_URL}/api/categories`)
        .then((response) => {
            const category = response.data.find(c => c.Category_ID == req.params.id);
            if (!category) {
                return res.render('index', { message: `No category found with ID ${req.params.id}.` });
            }
            res.render('edit-category', { category: category });
        })
        .catch(() => {
            res.render('index', { message: 'Could not load the category. Make sure backend/api.py is running.' });
        });
});

//EDIT CATEGORY: send the changes to the flask API
app.post('/categories/:id/edit', (req, res) => {
    const updated = {
        Category: req.body.Category
    };
    axios.put(`${API_URL}/api/categories/${req.params.id}`, updated)
        .then(() => {
            res.render('index', { message: `Category ${req.params.id} updated.` });
        })
        .catch(() => {
            res.render('index', { message: 'Could not save changes. Make sure backend/api.py is running.' });
        });
});


//EDIT LOCATION: load the location and show the form with current values filled in
app.get('/locations/:id/edit', (req, res) => {
    axios.get(`${API_URL}/api/locations`)
        .then((response) => {
            const location = response.data.find(l => l.Location_ID == req.params.id);
            if (!location) {
                return res.render('index', { message: `No location found with ID ${req.params.id}.` });
            }
            res.render('edit-location', { location: location });
        })
        .catch(() => {
            res.render('index', { message: 'Could not load the location. Make sure backend/api.py is running.' });
        });
});

//EDIT LOCATION: send the changes to the flask API
app.post('/locations/:id/edit', (req, res) => {
    const updated = {
        Location_Name: req.body.Location_Name
    };
    axios.put(`${API_URL}/api/locations/${req.params.id}`, updated)
        .then(() => {
            res.render('index', { message: `Location ${req.params.id} updated.` });
        })
        .catch(() => {
            res.render('index', { message: 'Could not save changes. Make sure backend/api.py is running.' });
        });
});


//EDIT PRODUCT: load the product plus the category and supplier lists for the dropdowns
app.get('/products/:id/edit', (req, res) => {
    Promise.all([
        axios.get(`${API_URL}/api/products`),
        axios.get(`${API_URL}/api/categories`),
        axios.get(`${API_URL}/api/suppliers`)
    ])
        .then(([productRes, categoryRes, supplierRes]) => {
            const product = productRes.data.find(p => p.Product_ID == req.params.id);
            if (!product) {
                return res.render('index', { message: `No product found with ID ${req.params.id}.` });
            }
            res.render('edit-product', {
                product: product,
                categories: categoryRes.data,
                suppliers: supplierRes.data
            });
        })
        .catch(() => {
            res.render('index', { message: 'Could not load the product. Make sure backend/api.py is running.' });
        });
});

//EDIT PRODUCT: send the changes to the flask API
app.post('/products/:id/edit', (req, res) => {
    const updated = {
        Name: req.body.Name,
        Category_ID: req.body.Category_ID,
        Availability: req.body.Availability,     //1 = available, 0 = not available
        Supplier_ID: req.body.Supplier_ID
    };
    axios.put(`${API_URL}/api/products/${req.params.id}`, updated)
        .then(() => {
            res.render('index', { message: `Product ${req.params.id} updated.` });
        })
        .catch(() => {
            res.render('index', { message: 'Could not save changes. Make sure backend/api.py is running.' });
        });
});


//EDIT VARIANT: load the variant plus the size, color, product and location lists for the dropdowns
app.get('/variants/:id/edit', (req, res) => {
    Promise.all([
        axios.get(`${API_URL}/api/product_variants`),
        axios.get(`${API_URL}/show/all/sizes`),
        axios.get(`${API_URL}/show/all/colors`),
        axios.get(`${API_URL}/api/products`),
        axios.get(`${API_URL}/api/locations`)
    ])
        .then(([variantRes, sizeRes, colorRes, productRes, locationRes]) => {
            const variant = variantRes.data.find(v => v.Variant_ID == req.params.id);
            if (!variant) {
                return res.render('index', { message: `No variant found with ID ${req.params.id}.` });
            }
            res.render('edit-variant', {
                variant: variant,
                sizes: sizeRes.data,
                colors: colorRes.data,
                products: productRes.data,
                locations: locationRes.data
            });
        })
        .catch(() => {
            res.render('index', { message: 'Could not load the variant. Make sure backend/api.py is running.' });
        });
});

//EDIT VARIANT: send the changes to the flask API
app.post('/variants/:id/edit', (req, res) => {
    const updated = {
        Size_ID: req.body.Size_ID,
        Color_ID: req.body.Color_ID,
        Product_ID: req.body.Product_ID,
        Location_ID: req.body.Location_ID,
        Price: req.body.Price,
        Cost: req.body.Cost
    };
    axios.put(`${API_URL}/api/product_variants/${req.params.id}`, updated)
        .then(() => {
            res.render('index', { message: `Variant ${req.params.id} updated.` });
        })
        .catch(() => {
            res.render('index', { message: 'Could not save changes. Make sure backend/api.py is running.' });
        });
});


//run application on a port
app.listen(PORT);
console.log(`Application (${env}) is listening on port ${PORT}`);