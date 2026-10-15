/* Operator-only proxy listing: show the actual kennel, never silently use DOG44 defaults. */
(async function(){
  let me;
  try{me=await BigPawAPI.me()}catch(_){return}
  if(!me||me.role!=='operator'||editId)return;
  const selectedId=new URLSearchParams(location.search).get('breederId')||'';
  const form=document.querySelector('form');
  const submit=form&&form.querySelector('button.btn-wide');
  if(!form||!submit)return;
  submit.disabled=true;
  const notice=document.createElement('div');
  notice.className='notice';
  notice.id='operatorProxyListingNotice';
  notice.style.margin='0 0 18px';
  form.insertBefore(notice,form.firstChild);
  if(!selectedId){
    notice.textContent='運営代理掲載：掲載先が未選択です。運営のブリーダー管理画面から対象の犬舎を選択してください。';
    return;
  }
  try{
    const target=await BigPawAPI.request('/breeder-profile?id='+encodeURIComponent(selectedId));
    if(!target||String(target.id)!==String(selectedId)||target.review_status!=='approved')
      throw new Error('承認済みブリーダーを選択してください。');
    notice.textContent='運営代理掲載：'+target.kennel_name+'（'+target.prefecture+'）の掲載犬として登録します。';
    document.querySelector('h1').textContent='代理掲載｜'+target.kennel_name;
    // A newly selected kennel must not inherit DOG44 puppy details or parents.
    for(const id of ['color','birth','price','weight','adultMin','adultMax','desc','puppyName']){
      const input=document.getElementById(id);if(input)input.value='';
    }
    for(const id of ['father','mother']){
      const select=document.getElementById(id);
      if(select){select.replaceChildren(new Option('未登録','未登録'));}
    }
    for(const control of document.querySelectorAll('.fact input[type="checkbox"]'))control.checked=false;
    const breeds=document.getElementById('breed');
    if(breeds){breeds.insertBefore(new Option('犬種を選択してください',''),breeds.firstChild);breeds.value='';breeds.required=true}
    submit.disabled=false;
  }catch(e){
    notice.textContent='代理掲載先の確認に失敗しました。ブリーダー登録・承認状態を確認してください。';
    submit.disabled=true;
  }
})();