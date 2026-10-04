/* Restore the missing guide entry point using the existing breed catalogue. */
(()=>{
  const key=new URLSearchParams(location.search).get('breed')||'';
  const breed=(window.BIGPAW_BREEDS||[]).find(b=>b.key===key);
  const text=(id,value)=>{const e=document.getElementById(id);if(e)e.textContent=value};
  const photo=document.getElementById('breedPhoto');
  if(photo){photo.hidden=true;photo.alt=breed?.ja||'犬種写真';}
  if(!breed){
    text('breedName','犬種を選択してください');
    text('breedLead','大型犬種ガイドの一覧から、確認したい犬種を選んでください。');
    const grid=document.querySelector('.guide-grid');if(grid){grid.hidden=true;grid.style.display='none'}
    const search=document.getElementById('searchBreed');if(search){search.href='breed-guide.html';search.textContent='大型犬種ガイドへ戻る'}
    return;
  }
  text('breedName',breed.ja);
  text('breedLead','親犬の体格・性格や実際のお世話の内容を、掲載ブリーダーに確認しましょう。');
  text('exercise','日々の散歩・遊びの時間と内容を確認し、家族の生活で確保できるか考えましょう。');
  text('coat','被毛の長さや抜け毛、お手入れの頻度を確認しましょう。');
  text('grooming','ブラッシングやトリミングの内容、頻度、費用を確認しましょう。');
  text('training','子犬の性格や育った環境、人・犬との関わり方を確認しましょう。');
  text('health','親犬・子犬の健康状態や検査記録を確認しましょう。個体ごとの情報は掲載ブリーダーにお問い合わせください。');
  const search=document.getElementById('searchBreed');if(search)search.href='search.html?breed='+encodeURIComponent(breed.key);
})();
