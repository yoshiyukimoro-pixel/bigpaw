/* BIG PAW 推しワン – prioritize eligible promoted puppies inside existing filtered search results.
 * No duplicates, at most five sponsored positions, regular listings remain searchable.
 * Browser: window.BigPawOshiwanSearch; Node tests: module.exports.
 */
(function(root){
  'use strict';
  function prioritize(regularResults, featuredGroups, maxSponsored){
    const results=Array.isArray(regularResults)?regularResults:[];
    const limit=Math.max(0,Math.min(5,Number.isFinite(maxSponsored)?Math.floor(maxSponsored):5));
    const resultById=new Map(results.map(p=>[String(p.id),p]));
    const groups=(Array.isArray(featuredGroups)?featuredGroups:[]).map(group=>
      Array.isArray(group.puppies)?group.puppies.map(p=>String(p.id)):[]
    );
    const featured=[];
    const used=new Set();
    let more=true;
    while(more && featured.length<limit){
      more=false;
      for(const items of groups){
        while(items.length){
          more=true;
          const id=items.shift();
          const p=resultById.get(id);
          // Only promote a puppy that actually passed ALL current search filters.
          if(!p || used.has(id) || p.status!=='募集中')continue;
          used.add(id);
          featured.push(p);
          break;
        }
        if(featured.length>=limit)break;
      }
    }
    return {
      ordered:featured.concat(results.filter(p=>!used.has(String(p.id)))),
      featuredIds:featured.map(p=>String(p.id))
    };
  }
  const api={prioritize};
  if(typeof module!=='undefined' && module.exports)module.exports=api;
  if(root)root.BigPawOshiwanSearch=api;
})(typeof window!=='undefined'?window:null);
