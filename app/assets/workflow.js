(function(){
  function param(name){return new URLSearchParams(location.search).get(name)||''}
  function normalizeInquiry(q){if(!q)return null;return {...q,puppyName:q.puppyName||q.puppy_name||'',breeder:q.breeder||q.breeder_name||'',preferredDate:q.preferredDate||q.preferred_date||''}}
  async function context(){
    const list=(await BigPawBridge.inquiries()).map(normalizeInquiry);
    const wanted=param('inquiry');
    const inquiry=(wanted&&list.find(x=>String(x.id)===String(wanted)))||list[0]||null;
    if(!inquiry)return {inquiries:list,inquiry:null,puppy:null,deal:null};
    let puppy=null; try{puppy=await BigPawBridge.puppy(inquiry.puppy_id||inquiry.puppyId)}catch(e){}
    let deal=null; try{deal=await BigPawBridge.ensureDeal(inquiry.id)}catch(e){}
    return {inquiries:list,inquiry,puppy,deal};
  }
  function yen(n){return Number(n||0).toLocaleString('ja-JP')+'円'}
  window.BigPawWorkflow={param,normalizeInquiry,context,yen};
})();
