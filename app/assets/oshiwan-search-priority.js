/* BIG PAW 推しワン – prioritize eligible promoted puppies inside existing filtered search results.
 * Five sponsored cards are ADDITIONAL placements: the same puppies also stay in regular listings.
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
      // PR slots are promotional placements, not a replacement for ordinary search.
      // Repetition is intentional: an advertised puppy remains in the full organic list.
      ordered:featured.concat(results),
      featuredIds:featured.map(p=>String(p.id))
    };
  }
  function paginate(items, requestedPage, requestedSize){
    const list=Array.isArray(items)?items:[];
    const size=Math.max(1,Math.min(100,Number.isFinite(requestedSize)?Math.floor(requestedSize):20));
    const totalPages=Math.max(1,Math.ceil(list.length/size));
    const requested=Number.isFinite(requestedPage)?Math.floor(requestedPage):1;
    const page=Math.max(1,Math.min(totalPages,requested));
    const start=(page-1)*size;
    return {page,totalPages,visible:list.slice(start,start+size),start:start+1,end:Math.min(start+size,list.length),totalSlots:list.length};
  }
  const api={prioritize,paginate};
  if(typeof module!=='undefined' && module.exports)module.exports=api;
  if(root)root.BigPawOshiwanSearch=api;
})(typeof window!=='undefined'?window:null);
