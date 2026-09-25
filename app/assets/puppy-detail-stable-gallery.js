(()=>{
'use strict';
const puppyId=new URLSearchParams(location.search).get('id');
if(!puppyId)return;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function collectUrls(p){
  const out=[];
  const add=u=>{if(typeof u==='string'&&u.trim()&&!out.includes(u.trim()))out.push(u.trim())};
  add(p&&p.imageUrl);
  [p&&p.photos,p&&p.images,p&&p.imageUrls,p&&p.photoUrls].forEach(a=>{
    if(!Array.isArray(a))return;
    a.forEach(x=>add(typeof x==='string'?x:(x&&(x.url||x.imageUrl||x.path))));
  });
  return out;
}
function installStyle(){
  if(document.getElementById('bigpawStableGalleryStyle'))return;
  const st=document.createElement('style');st.id='bigpawStableGalleryStyle';st.textContent=`
#bigpawStableGallery{margin:0 0 16px;width:100%}
#bigpawStableGallery .bpsg-stage{position:relative;width:min(100%,680px);aspect-ratio:4/5;margin:0 auto;border-radius:20px;overflow:hidden;background:#f7edf2;box-shadow:0 3px 14px rgba(70,45,58,.08)}
#bigpawStableGallery .bpsg-stage img{display:block;width:100%;height:100%;object-fit:contain;object-position:center;background:#f7edf2}
#bigpawStableGallery .bpsg-arrow{position:absolute;z-index:4;top:50%;transform:translateY(-50%);width:46px;height:46px;border:0;border-radius:50%;background:rgba(255,255,255,.94);color:#604b57;font-size:30px;line-height:1;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 10px rgba(0,0,0,.17);-webkit-tap-highlight-color:transparent}
#bigpawStableGallery .bpsg-prev{left:10px}#bigpawStableGallery .bpsg-next{right:10px}
#bigpawStableGallery .bpsg-count{position:absolute;z-index:4;right:12px;bottom:12px;padding:5px 10px;border-radius:999px;background:rgba(20,20,20,.58);color:#fff;font-size:12px;font-weight:800}
#bigpawStableGallery .bpsg-loading{position:absolute;z-index:3;inset:0;display:flex;align-items:center;justify-content:center;background:#f7edf2;color:#7a6570;font-weight:800;font-size:14px}
#bigpawStableGallery .bpsg-empty{display:grid;place-items:center;width:100%;height:100%;font-size:74px}
#bigpawStableGallery .bpsg-help{text-align:center;color:#85727c;font-size:12px;margin-top:7px}
#bigpawStableGallery + #bigpawFavButton{display:block;width:100%;margin:0 0 16px;padding:14px;border:1px solid #ef7fa8;border-radius:14px;background:#fff;color:#b85d82;font-weight:900;font-size:16px}
@media(max-width:520px){#bigpawStableGallery .bpsg-stage{width:100%;border-radius:18px}#bigpawStableGallery .bpsg-arrow{width:44px;height:44px}}
`;
  document.head.appendChild(st);
}
async function init(){
  if(!window.BigPawBridge){setTimeout(init,40);return}
  if(document.getElementById('bigpawStableGallery'))return;
  let p;
  try{p=await BigPawBridge.puppy(puppyId)}catch(_e){return}
  const old=document.querySelector('.gallery,#bigpawRealGallery');
  if(!old)return;
  installStyle();
  const urls=collectUrls(p||{});
  const root=document.createElement('section');root.id='bigpawStableGallery';root.setAttribute('aria-label','子犬の写真');
  const stage=document.createElement('div');stage.className='bpsg-stage';
  if(!urls.length){
    stage.innerHTML='<div class="bpsg-empty">🐩</div>';
    root.appendChild(stage);old.replaceWith(root);return;
  }
  const loading=document.createElement('div');loading.className='bpsg-loading';loading.textContent='写真を読み込み中…';
  const img=document.createElement('img');img.alt=(p&&p.breed?p.breed:'子犬')+'の写真';img.loading='eager';img.decoding='async';img.fetchPriority='high';
  const prev=document.createElement('button');prev.type='button';prev.className='bpsg-arrow bpsg-prev';prev.setAttribute('aria-label','前の写真');prev.textContent='‹';
  const next=document.createElement('button');next.type='button';next.className='bpsg-arrow bpsg-next';next.setAttribute('aria-label','次の写真');next.textContent='›';
  const count=document.createElement('div');count.className='bpsg-count';
  stage.append(img,loading,prev,next,count);root.appendChild(stage);
  const help=document.createElement('div');help.className='bpsg-help';help.textContent=urls.length>1?'左右の矢印で写真を切り替えられます':'メイン写真';root.appendChild(help);
  old.replaceWith(root);
  let index=0,loadToken=0,startX=null,startY=null;
  function show(n){
    index=(n+urls.length)%urls.length;
    const token=++loadToken;
    loading.style.display='flex';
    count.textContent=(index+1)+' / '+urls.length;
    const one=urls.length<2;prev.style.display=one?'none':'flex';next.style.display=one?'none':'flex';
    img.onload=()=>{if(token===loadToken)loading.style.display='none'};
    img.onerror=()=>{if(token===loadToken){loading.textContent='写真を読み込めませんでした';loading.style.display='flex'}};
    img.src=urls[index];
  }
  prev.onclick=e=>{e.preventDefault();e.stopPropagation();show(index-1)};
  next.onclick=e=>{e.preventDefault();e.stopPropagation();show(index+1)};
  stage.addEventListener('touchstart',e=>{if(e.touches.length!==1)return;startX=e.touches[0].clientX;startY=e.touches[0].clientY},{passive:true});
  stage.addEventListener('touchend',e=>{if(startX==null||!e.changedTouches.length)return;const dx=e.changedTouches[0].clientX-startX,dy=e.changedTouches[0].clientY-startY;startX=startY=null;if(Math.abs(dx)>45&&Math.abs(dx)>Math.abs(dy)*1.3)show(index+(dx<0?1:-1))},{passive:true});
  const fav=document.getElementById('bigpawFavButton')||document.createElement('button');
  if(!fav.id){fav.id='bigpawFavButton';fav.type='button';fav.textContent='♡ お気に入りに保存';root.insertAdjacentElement('afterend',fav)}
  show(0);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
