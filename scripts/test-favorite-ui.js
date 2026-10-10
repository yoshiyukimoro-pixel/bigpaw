/* Regression guard: the updated page scripts must remain valid browser JavaScript. */
const fs=require('fs');
const vm=require('vm');
const assert=require('assert');
function check(file){
  const source=fs.readFileSync(file,'utf8');
  const scripts=[...source.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
  assert(scripts.length>0,file+' scripts missing');
  let checked=0;
  for(const part of scripts){
    if(/\bsrc\s*=/.test(part[1]) || !part[2].trim())continue;
    new vm.Script(part[2],{filename:file+':inline-'+checked});
    checked++;
  }
  assert(checked>0,file+' no inline scripts');
  return source;
}
const account=check('app/account.html');
const favorites=check('app/favorites.html');
const dashboard=check('app/admin.html');
const puppy=check('app/puppy-detail.html');
assert(account.includes('favoriteUpdateMail'));
assert(account.includes('/favorite-notifications/settings'));
assert(favorites.includes('メール通知のON・OFF'));
assert(dashboard.includes('engagementStats'));
assert(dashboard.includes('favoriteCount')&&dashboard.includes('viewCount')&&dashboard.includes('viewerCount'));
assert(dashboard.includes('operatorScopeId')&&dashboard.includes('breederId='));
assert(puppy.includes('puppy-view-tracker.js'));
assert(fs.readFileSync('app/assets/puppy-view-tracker.js','utf8').includes('visitorId'));
console.log('FAVORITE_UI_REGRESSION_OK');
