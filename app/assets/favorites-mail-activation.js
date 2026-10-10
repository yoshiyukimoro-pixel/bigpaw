/* An explicit single-click subscription for users who already saved favorites.
   No automatic enrollment for previously registered users or opted-out buyers. */
(async function(){
  const box=document.getElementById('favoriteMailActivation');
  if(!box||!window.BigPawAPI)return;
  try{
    const [favs,pref]=await Promise.all([
      BigPawAPI.favorites(),
      BigPawAPI.request('/favorite-notifications/settings')
    ]);
    if(!Array.isArray(favs)||!favs.length||pref.enabled)return;
    box.style.display='block';
    const title=document.createElement('strong');
    title.textContent='お気に入りの子犬の更新をメールで受け取りませんか？';
    const details=document.createElement('p');
    details.className='muted';
    details.textContent='受信を申し込むと、登録済みの子犬の写真・価格・紹介文・募集状況が変更されたときにメールが届きます。いつでもアカウント設定から停止できます。';
    const btn=document.createElement('button');
    btn.type='button';btn.className='btn btn-main';
    btn.textContent='変更メールを受け取る（同意して有効にする）';
    box.append(title,details,btn);
    btn.addEventListener('click',async function(){
      btn.disabled=true;
      try{
        const saved=await BigPawAPI.request('/favorite-notifications/settings',
          {method:'PATCH',body:{enabled:true}});
        if(!saved.enabled)throw new Error('subscription_not_enabled');
        box.textContent='✓ 更新メールを受け取る設定になりました。';
      }catch(_e){
        details.textContent='設定を保存できませんでした。もう一度お試しください。';
        btn.disabled=false;
      }
    });
  }catch(_e){ /* Do not display misleading mail promises when not authenticated. */ }
})();
