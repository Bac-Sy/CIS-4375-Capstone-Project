'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const root = path.join(__dirname, '..', 'frontend', 'views');

// Lightweight EJS tag compiler for offline JavaScript-syntax validation.
function compile(template) {
  const re = /<%([=-]?)([\s\S]*?)%>/g;
  let match, last = 0;
  let js = "let __out=''; with (locals) {\n";
  while ((match = re.exec(template))) {
    js += `__out += ${JSON.stringify(template.slice(last, match.index))};\n`;
    if (match[1] === '=' || match[1] === '-') js += `__out += (${match[2]});\n`;
    else js += match[2] + '\n';
    last = re.lastIndex;
  }
  js += `__out += ${JSON.stringify(template.slice(last))};\n} return __out;`;
  return new Function('locals', 'include', js);
}
const sampleUser = { id:'1', name:'Test User', firstName:'Test', username:'testuser', email:'test@example.org', role:'Manager' };
const fmt = require('../frontend/lib/format');
const partialData = { user:sampleUser, authenticated:true, FirstName:'Test', Role:'Manager', csrfToken:'VALID_CSRF', env:'development', api:{status:'ok'}, fmt, message:null, title:'Test', showStatus:true, active:'dashboard' };
const data = { ...partialData,
  rows:[{ Variant_ID:1,Product_ID:1,Product:'Satin Midi Dress',Size:'M',Color:'Black',Location:'Main Store',Quantity:3 }],
  items:[], threshold:5, dataAvailable:true, employees:[{first_name:'Test',last_name:'User',username:'testuser',email:'test@example.org',role:'Manager'}],
  types:['Sale','Adjustment','Restock'], selected:'', limit:100,
  supplier:{Supplier_ID:1,Name:'Supplier',Email:'',Phone:''},
  category:{Category_ID:1,Category:'Dresses'}, location:{Location_ID:1,Location_Name:'Main Store'},
  product:{Product_ID:1,Name:'Dress',Category_ID:1,Supplier_ID:1,Availability:1},
  variant:{Variant_ID:1,Size_ID:1,Color_ID:1,Product_ID:1,Location_ID:1,Price:10,Cost:2},
  products:[{ Product_ID:1,Name:'Dress' }], variants:[{Variant_ID:1}], suppliers:[{Supplier_ID:1,Name:'Supplier'}],
  categories:[{Category_ID:1,Category:'Dresses'}], locations:[{Location_ID:1,Location_Name:'Main Store'}],
  sizes:[{Size_ID:1,Size:'M'}], colors:[{Color_ID:1,Color:'Black'}],
  error:null, ErrorMessage:null, username:'', Username:'', detail:'Not found', title:'Error',
  data:{sales:{revenue:50,units:1,days:30},recent_orders:[],low_stock:[],low_stock_threshold:5,trend:[]}, donut:null, trend:null,
};
let compiled = 0;
for (const folder of ['pages','template']) {
  for (const filename of fs.readdirSync(path.join(root, folder)).filter(n=>n.endsWith('.ejs'))) {
    const source = fs.readFileSync(path.join(root, folder, filename), 'utf8');
    const fn = compile(source);
    const result = fn(data, ()=> '');
    assert(result.includes('<') || filename === 'head.ejs', filename);
    if (source.includes('method="POST"')) {
      assert(source.includes('name="_csrf"'), filename+' missing csrf input');
    }
    if (filename === 'index.ejs') assert(!source.includes('schema_map.json'));
    console.log('PASS',folder+'/'+filename);
    compiled++;
  }
}
console.log('Verified',compiled,'EJS templates offline.');
