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
