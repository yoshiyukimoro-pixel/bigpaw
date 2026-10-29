/* Offline static checks: 35 products, 63 original files, 163 ordered references. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('app/shop.html','utf8');
const js = fs.readFileSync('app/shop-detail-images.js','utf8');
const gallery = fs.readFileSync('app/shop-detail-gallery.js','utf8');
const sandbox = {window:{}};
vm.runInNewContext(js,sandbox,{filename:'shop-detail-images.js'});
const mapping = sandbox.window.BIGPAW_SHOP_DETAIL_IMAGES;
const rows = [...html.matchAll(/^'([AOZC]\d{2}\|[^']+)'[,]?$/gm)].map(m=>m[1].split('|'));
const expected = {ACANA:14,ORIJEN:8,ZIWI:9,CHARM:4};
assert.equal(rows.length,35,'storefront must still have exactly 35 items');
assert.deepEqual(Object.keys(mapping).sort(),rows.map(r=>r[0]).sort(),'image mapping must cover all 35 SKUs');
let refs=0;
const paths = new Set();
for(const row of rows){
  const [id,brand] = row;
  const images = mapping[id];
  assert(Array.isArray(images) && images.length>=4,id+' has no gallery');
  let shared=false;
  const seen=new Set();
  for(const img of images){
    refs++;
    assert(!seen.has(img.src),id+' duplicates same photo');
    seen.add(img.src);paths.add(img.src);
    assert.equal(typeof img.caption,'string');
    assert(img.caption.length>1,'missing image caption');
    assert(['specific','brand'].includes(img.scope),id+' invalid scope');
    const specific='assets/shop-details/products/'+id+'/';
    const sameBrand='assets/shop-details/shared/'+brand.toLowerCase()+'/';
    if(img.scope==='specific'){
      assert(!shared,id+' has product-specific image after brand image');
      assert(img.src.startsWith(specific),id+' product image from another SKU');
    }else{
      shared=true;
      assert(img.src.startsWith(sameBrand),id+' uses other brand artwork');
    }
    assert(/\.webp$/.test(img.src),'expected optimized WebP path');
  }
}
assert.deepEqual(Object.fromEntries(Object.entries(expected).map(([brand])=>
  [brand,rows.filter(row=>row[1]===brand).length])),expected);
assert.equal(paths.size,63,'expect 63 unique manufacturer source images');
assert.equal(refs,163,'expect exact approved gallery references per product');
const installed=[...paths].filter(src=>fs.existsSync('app/'+src));
assert([0,63].includes(installed.length),
  'Partial detail image upload: all 63 files must be present together');
if(installed.length===63){
  for(const src of installed){
    const file=fs.readFileSync('app/'+src);
    assert.equal(file.subarray(0,4).toString(),'RIFF',src+' invalid WebP');
    assert.equal(file.subarray(8,12).toString(),'WEBP',src+' invalid WebP');
  }
  console.log('SHOP_DETAIL_ASSETS_PRESENT|sources=63|format=WebP');
}else console.log('SHOP_DETAIL_ASSETS_PENDING|sources=63|github=not_uploaded');
assert(mapping.A09.some(im=>im.src.endsWith('/A09/special-1.webp')));
assert(mapping.A12.some(im=>im.src.endsWith('/A12/special-1.webp')));
assert(mapping.Z06.some(im=>im.src.includes('air-chicken-9312.webp')));
assert(!mapping.Z06.some(im=>im.src.includes('air-other-9312.webp')));
for(const id of ['Z07','Z08','Z09']){
  assert(mapping[id].some(im=>im.src.includes('steam-process.webp')));
  assert(!mapping[id].some(im=>im.src.includes('air-dried-introduction.webp')));
}
for(const id of ['Z08','Z09'])assert(mapping[id].every(im=>im.scope==='brand'),
  'no manufacturer-specific image was provided for '+id+'; never fabricate one');
assert(html.includes('<script src="shop-detail-images.js" defer></script>'));
assert(html.includes('<script src="shop-detail-gallery.js" defer></script>'));
assert(html.includes('<link rel="stylesheet" href="shop-detail-gallery.css">'));
assert(gallery.includes("img.loading='lazy'") && gallery.includes("img.decoding='async'"));
assert(!gallery.includes('fetch(') && !gallery.includes('XMLHttpRequest') &&
  !gallery.includes('Square') && !gallery.includes('localStorage'),
  'gallery cannot communicate with payments or store customer data');
console.log('SHOP_DETAIL_IMAGES_OK|products=35|sources=63|references=163|scope=validated');

// Fingerprints from the four manufacturer ZIPs: exact image order,
// filename, shared/specific scope AND Japanese caption for every SKU.
const crypto=require('node:crypto');
const fromManufacturer={"A01":"905d699642cdbbe3","A02":"1b4b33b1eb9b0d0e","A03":"cb031344a43d9e53","A04":"b89a315831cd03dc","A05":"e969c3fd576d86a3","A06":"9bb0e5f647d84845","A07":"0ebc2cac326b36c7","A08":"626b0264d9f43eea","A09":"b5af4751ecc2cc40","A10":"8ab039adc0f9ea2e","A11":"816d83cab42f4546","A12":"fbe5c7890a542b90","A13":"4fda0ecdacba6a6d","A14":"a5cd32728e078e84","C01":"9a169565f61b9e88","C02":"8ed5fa8101ad2a4f","C03":"731a742b66312cd7","C04":"4b6b76957339be04","O01":"fa1ef0b1e5cd8fb1","O02":"0f6c16f111fcf75b","O03":"ffa3ad17ff7b750c","O04":"f36730f3ab04738c","O05":"f47e029a5b6e3030","O06":"3efc1d2037ce2ac7","O07":"fb81e9c8f518d778","O08":"6fe7f93019071a80","Z01":"44142bbbc57fea36","Z02":"45557fc6217f7c12","Z03":"9a8c1abd5212cb4a","Z04":"eb7c4c93231b6249","Z05":"cc9ee76a06960a3c","Z06":"ed1f480969677999","Z07":"4f7f0e68e6c43e3b","Z08":"ec65bad87e6097f4","Z09":"ec65bad87e6097f4"};
for(const [id,fingerprint] of Object.entries(fromManufacturer)){
  const serialized=mapping[id].map(im=>
    [im.scope,im.src,im.caption].join('|')).join('\n');
  const actual=crypto.createHash('sha256').update(serialized).digest('hex').slice(0,16);
  assert.equal(actual,fingerprint,id+' source manifest differed; do not reassign brand or SKU photos');
}
