(async()=>{
 const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const names={buyer_pending:'購入希望者の確認待ち',operator_review:'運営確認中',unanswered:'未回答・運営確認中',closed:'取引終了',continued:'中止申請は差し戻し・取引継続',sale_review:'成約・お迎え報告が必要'};
 const id=new URLSearchParams(location.search).get('inquiry');let busy=false;
 const msg=s=>$('message').textContent=s;
 if(!id){msg('問い合わせ管理から対象の取引を選んでください。');return}
 async function load(){try{const r=await BigPawAPI.request('/inquiries/'+encodeURIComponent(id)+'/cancellation');$('puppy').textContent=r.puppy_name;const c=r.request;
  $('current').innerHTML=c?`<p class="status">${esc(names[c.state])}</p><p>申請理由：${esc(c.breeder_reason_label)}</p><p>${esc(c.breeder_note)}</p>${c.review_note?`<p>運営から：${esc(c.review_note)}</p>`:''}`:'';
  $('form').hidden=!!c&&!['continued','sale_review'].includes(c.state);
  $('reason').innerHTML='<option value="">選択してください</option>'+Object.entries(r.breederReasons).map(([k,v])=>`<option value="${esc(k)}">${esc(v)}</option>`).join('');
  $('listingAction').innerHTML=c?.state==='closed'?'<a class="btn btn-sub" href="admin.html">子犬の募集状況を確認・変更する</a>':'';
 }catch(e){msg(e.status===401||e.status===403?'ブリーダーアカウントでログインしてください。':e.message);$('current').innerHTML='<a class="btn btn-sub" href="login.html?next='+encodeURIComponent(location.pathname+location.search)+'">ログイン</a>'}}
 $('form').onsubmit=async e=>{e.preventDefault();if(busy)return;if($('reason').value==='other'&&!$('note').value.trim())return msg('「その他」の内容を入力してください。');if(!confirm('この内容で取引中止を申請し、購入希望者へ確認メールを送りますか？'))return;busy=true;$('submit').disabled=true;
 try{await BigPawAPI.request('/inquiries/'+encodeURIComponent(id)+'/cancellation',{method:'POST',body:{reason:$('reason').value,note:$('note').value,agreeAccurateReporting:$('accurate').checked}});msg('申請しました。購入希望者の確認待ちです。');await load()}catch(e){msg(e.message)}finally{busy=false;$('submit').disabled=false}};
 await load();
})();
