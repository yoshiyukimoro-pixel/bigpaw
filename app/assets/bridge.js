(function(){
  async function fallbackable(apiFn, fallbackFn){
    if(window.BigPawAPI && BigPawAPI.isLive()){
      try{return await apiFn()}catch(e){
        if(!(e instanceof TypeError) && e.status!==404) throw e;
      }
    }
    return await fallbackFn();
  }
  window.BigPawBridge={
    isServerMode(){return !!(window.BigPawAPI && BigPawAPI.isLive())},
    register(v){return fallbackable(()=>BigPawAPI.register(v),()=>BigPaw.register(v))},
    login(email,pw){return fallbackable(()=>BigPawAPI.login(email,pw),()=>BigPaw.login(email,pw))},
    me(){return fallbackable(()=>BigPawAPI.me(),()=>BigPaw.currentUser())},
    puppies(params={}){return fallbackable(()=>BigPawAPI.puppies(params),()=>BigPaw.getPuppies())},
    breederPuppies(){return fallbackable(()=>BigPawAPI.breederPuppies(),()=>BigPaw.getPuppies())},
    puppy(id){return fallbackable(()=>BigPawAPI.puppy(id),()=>BigPaw.getPuppy(id))},
    addPuppy(v){return fallbackable(()=>BigPawAPI.addPuppy(v),()=>BigPaw.addPuppy(v))},
    updatePuppy(id,v){return fallbackable(()=>BigPawAPI.updatePuppy(id,v),()=>BigPaw.updatePuppy(id,v))},
    inquiries(){return fallbackable(()=>BigPawAPI.inquiries(),()=>BigPaw.getInquiries())},
    addInquiry(v){return fallbackable(()=>BigPawAPI.addInquiry(v),()=>BigPaw.addInquiry({...v,puppyId:v.puppyId||'',date1:v.preferredDate||''}))},
    updateInquiry(id,v){return fallbackable(()=>BigPawAPI.updateInquiry(id,v),()=>BigPaw.updateInquiry(id,v))},
    favorites(){return fallbackable(()=>BigPawAPI.favorites(),()=>BigPaw.getFavorites().map(id=>BigPaw.getPuppy(id)).filter(Boolean))},
    toggleFavorite(id){return fallbackable(()=>BigPawAPI.toggleFavorite(id),()=>({favorite:BigPaw.toggleFavorite(id)}))},
    messages(inquiryId){return fallbackable(()=>BigPawAPI.messages(inquiryId),()=>{let all={};try{all=JSON.parse(localStorage.getItem('bigpaw_chats_v1')||'{}')}catch(e){};return (all[inquiryId]||[]).map((x,i)=>({id:'local'+i,body:x.text,role:x.mine?'buyer':'breeder',created_at:Date.now()/1000+i}))})},
    sendMessage(inquiryId,body){return fallbackable(()=>BigPawAPI.sendMessage(inquiryId,body),()=>{let all={};try{all=JSON.parse(localStorage.getItem('bigpaw_chats_v1')||'{}')}catch(e){};all[inquiryId]=all[inquiryId]||[];all[inquiryId].push({mine:true,text:body});localStorage.setItem('bigpaw_chats_v1',JSON.stringify(all));return {body}})},
    visit(inquiryId){return fallbackable(()=>BigPawAPI.visit(inquiryId),()=>JSON.parse(localStorage.getItem('bigpaw_visit_v2')||'null'))},
    saveVisit(inquiryId,v){return fallbackable(()=>BigPawAPI.saveVisit(inquiryId,v),()=>{localStorage.setItem('bigpaw_visit_v2',JSON.stringify({...v,inquiry_id:inquiryId}));return v})},
    ensureDeal(inquiryId){return fallbackable(()=>BigPawAPI.ensureDeal(inquiryId),()=>{let d=JSON.parse(localStorage.getItem('bigpaw_deal_v2')||'null');if(!d){d={id:'localdeal',inquiry_id:inquiryId,total_price:258000,reservation_amount:100000,status:'contract_preparing'};localStorage.setItem('bigpaw_deal_v2',JSON.stringify(d))}return d})},
    dealSummary(dealId){return fallbackable(()=>BigPawAPI.dealSummary(dealId),()=>({deal:JSON.parse(localStorage.getItem('bigpaw_deal_v2')||'null'),payment:JSON.parse(localStorage.getItem('bigpaw_payment_v2')||'null'),contract:JSON.parse(localStorage.getItem('bigpaw_contract_v2')||'null'),pickup:JSON.parse(localStorage.getItem('bigpaw_pickup_v2')||'null'),review:JSON.parse(localStorage.getItem('bigpaw_review_v2')||'null')}))},
    payReservation(dealId,amount){return fallbackable(()=>BigPawAPI.payReservation(dealId,amount),()=>{const x={deal_id:dealId,amount,status:'paid'};localStorage.setItem('bigpaw_payment_v2',JSON.stringify(x));return x})},
    signContract(dealId){return fallbackable(()=>BigPawAPI.signContract(dealId),()=>{const x={deal_id:dealId,status:'signed',buyer_signed_at:Date.now()/1000};localStorage.setItem('bigpaw_contract_v2',JSON.stringify(x));return x})},
    savePickup(dealId,v){return fallbackable(()=>BigPawAPI.savePickup(dealId,v),()=>{const x={deal_id:dealId,...v,status:v.complete?'completed':'scheduled'};localStorage.setItem('bigpaw_pickup_v2',JSON.stringify(x));if(v.complete){let d=JSON.parse(localStorage.getItem('bigpaw_deal_v2')||'{}');d.status='completed';localStorage.setItem('bigpaw_deal_v2',JSON.stringify(d))}return x})},
    addReview(dealId,v){return fallbackable(()=>BigPawAPI.addReview(dealId,v),()=>{const x={deal_id:dealId,...v};localStorage.setItem('bigpaw_review_v2',JSON.stringify(x));return x})},
    upload(file,puppyId){
      if(window.BigPawAPI && BigPawAPI.isLive()) return BigPawAPI.upload(file,puppyId);
      return Promise.resolve({url:''});
    }
  };
})();
