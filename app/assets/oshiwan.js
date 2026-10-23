/* BIG PAW 「今の推しワン！」 breed-by-breed public spotlight. */
(function(){
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money = n => Number(n || 0).toLocaleString('ja-JP');
  const style = document.createElement('style');
  style.textContent = [
    '#bpOshiwan{background:linear-gradient(180deg,#fff8fa,#fff0f6);padding:36px 0 52px}',
    '#bpOshiwan h2{font-size:28px;margin:0 0 6px}',
    '#bpOshiwan .bp-oshi-intro{color:#685b68;margin:0 0 22px;font-size:14px}',
    '#bpOshiwan .bp-oshi-breed{margin:24px 0 10px;font-size:19px}',
    '#bpOshiwan .bp-oshi-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}',
    '#bpOshiwan .bp-oshi-card{display:block;overflow:hidden;border-radius:16px;background:white;border:1px solid #edcfdf;box-shadow:0 2px 9px #e8cad841;color:inherit;text-decoration:none;min-width:0}',
    '#bpOshiwan .bp-oshi-img{position:relative;aspect-ratio:4/3;background:#fbe4ef;display:grid;place-items:center}',
    '#bpOshiwan .bp-oshi-img img{width:100%;height:100%;object-fit:cover;position:absolute;inset:0}',
    '#bpOshiwan .bp-oshi-flag{position:absolute;top:8px;left:8px;background:#fff;color:#a73c74;border-radius:20px;padding:4px 9px;font-size:11px;font-weight:bold}',
    '#bpOshiwan .bp-oshi-info{padding:10px 11px}',
    '#bpOshiwan .bp-oshi-name{font-size:13px;font-weight:800;line-height:1.4}',
    '#bpOshiwan .bp-oshi-meta{font-size:12px;color:#6b6069;margin-top:6px}',
    '#bpOshiwan .bp-oshi-price{font-size:16px;font-weight:800;margin-top:8px;color:#a73c74}',
    '#bpOshiwan .bp-oshi-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}',
    '#bpOshiwan .bp-oshi-pr{border:1px solid #a69aa0;font-size:10px;border-radius:4px;padding:1px 5px;color:#685b68}',
    '@media(max-width:900px){#bpOshiwan .bp-oshi-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}',
    '@media(max-width:600px){#bpOshiwan h2{font-size:23px}#bpOshiwan .bp-oshi-grid{display:grid;grid-auto-flow:column;grid-auto-columns:70%;grid-template-columns:none;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:12px}#bpOshiwan .bp-oshi-card{scroll-snap-align:start}}'
  ].join('');
  document.head.appendChild(style);

  function makeCard(p){
    const url = 'puppy-detail.html?id=' + encodeURIComponent(p.id);
    const image = p.imageUrl ? '<img loading="lazy" src="' + esc(p.imageUrl) + '" alt="' + esc(p.breed) + 'の子犬">' : '🐾';
    return '<a class="bp-oshi-card" href="' + url + '">' +
      '<div class="bp-oshi-img">' + image + '<span class="bp-oshi-flag">🐾 推しワン</span></div>' +
      '<div class="bp-oshi-info"><div class="bp-oshi-name">' + esc(p.name || (p.breed + 'の子犬')) + '</div>' +
      '<div class="bp-oshi-meta">' + esc(p.gender || '') + '・' + esc(p.color || '') + '</div>' +
      '<div class="bp-oshi-meta">' + esc(p.area || '') + '</div>' +
      '<div class="bp-oshi-price">¥' + money(p.price) + '</div></div></a>';
  }
  async function load(){
    try{
      const res = await fetch('/api/oshiwan', {credentials:'same-origin',cache:'no-store'});
      if(!res.ok) return;
      const obj = await res.json();
      const groups = (obj.groups || []).filter(g => Array.isArray(g.puppies) && g.puppies.length);
      if(!groups.length) return; // Empty until breeders opt in; never show fake puppies.
      const ref = document.getElementById('breeds');
      if(!ref) return;
      const section = document.createElement('section');
      section.id = 'bpOshiwan';
      section.setAttribute('aria-label', '今の推しワン');
      section.innerHTML = '<div class="wrap"><div class="bp-oshi-head"><h2>🐾 今の推しワン！</h2><span class="bp-oshi-pr">PR</span></div>' +
        '<p class="bp-oshi-intro">ブリーダーさんが選んだ、とっておきの子犬たち。犬種ごとにご紹介します。</p>' +
        groups.map(g => '<h3 class="bp-oshi-breed">' + esc(g.breed) + '</h3>' +
          '<div class="bp-oshi-grid">' + g.puppies.map(makeCard).join('') + '</div>').join('') +
        '</div>';
      ref.insertAdjacentElement('afterend',section);
    }catch(e){console.warn('推しワン読み込み未完了', e);}
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded',load);
  else load();
})();
