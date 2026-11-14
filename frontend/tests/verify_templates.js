'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const root = path.join(__dirname, '..', 'views'); // frontend/views (this file is in frontend/tests)

// Lightweight EJS tag compiler for offline JavaScript-syntax validation.
function compile(template) {
  const re = /<%([=-]?)([\s\S]*?)%>/g;
  let match, last = 0;
  let js = "let __out=''; with (locals) {\n";
  while ((match = re.exec(template))) {
    js += `__out += ${JSON.stringify(template.slice(last, match.index))};\n`;
    // <%- include(...); %> is valid EJS, so drop a trailing semicolon before wrapping the expression.
    if (match[1] === '=' || match[1] === '-') js += `__out += (${match[2].trim().replace(/;\s*$/, '')});\n`;
    else js += match[2] + '\n';
    last = re.lastIndex;
  }
  js += `__out += ${JSON.stringify(template.slice(last))};\n} return __out;`;
  return new Function('locals', 'include', js);
}
const sampleUser = { id:'1', name:'Test User', firstName:'Test', username:'testuser', email:'test@example.org', role:'Manager' };
const fmt = require('../lib/format');
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
  data:{sales:{revenue:50,units:1,days:30},recent_by_type:{Sale:[],Restock:[],Adjustment:[]},low_stock:[],low_stock_threshold:5,inventory_totals:{units:3,items:1,products:1}}, donut:null, flow:null, recentType:'Sale',
  // Best sellers report
  periods:[{days:30,label:'Last 30 days'}], days:30, view:'product', byProduct:[], byItem:[], totalUnits:0, totalRevenue:0,
  // Inventory (grouped), Add variants, Edit order, Settings, Manage catalog
  groups:[{id:1,name:'Satin Midi Dress',category:'Dresses',available:false,variants:[{Variant_ID:1,Product_ID:1,Size:'M',Color:'Black',Location:'Main Store',Quantity:3,Price:10}],total:3,low:1}],
  allGroups:undefined, lowOnly:false, lowCount:1, adjusting:'1', existing:['1-1'], variantCounts:{1:1}, renaming:null,
  order:{invoice_id:25,date:'2026-11-12',transaction_type:'Sale',product:'Satin Midi Dress',size:'M',color:'Black',quantity_change:-1,employee:'Test User',variant_id:1},
  today:'2026-11-13', storeSettings:{low_stock_threshold:5},
  menuLabel:'Actions for Satin Midi Dress', menuItems:[{label:'Edit product',href:'/products/1/edit',icon:'edit'},{label:'Delete',action:'/products/1/delete',confirm:'Delete?',danger:true}],
  employee:{id:2,First_Name:'Maria',Last_Name:'Lopez',Username:'mlopez',Email:'m@example.org',Role:'Employee'}, form:{},
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
