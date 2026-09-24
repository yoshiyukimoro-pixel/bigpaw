(function(){
  const K={puppies:'bigpaw_puppies_v1',users:'bigpaw_users_v1',current:'bigpaw_current_user_v1',favorites:'bigpaw_favorites_v1',inquiries:'bigpaw_inquiries_v1'};
  const seedPuppies=[
    {id:'p1',name:'ブラックの男の子',breed:'スタンダードプードル',breedKey:'standard',gender:'男の子',genderKey:'male',color:'ブラック',price:258000,status:'募集中',area:'埼玉県',areaKey:'saitama',breeder:'DOG44',weight:10.5,adultMin:28,adultMax:32,health:true,birth:'2026-07-01',desc:'人が大好きで穏やかな男の子です。親犬情報・健康情報も公開しています。',createdAt:'2026-09-16T10:00:00+09:00'},
    {id:'p2',name:'ゴールドの女の子',breed:'ゴールデンレトリバー',breedKey:'golden',gender:'女の子',genderKey:'female',color:'ゴールド',price:328000,status:'募集中',area:'東京都',areaKey:'tokyo',breeder:'サンプル犬舎A',weight:8.2,adultMin:25,adultMax:30,health:true,birth:'2026-07-12',desc:'明るく人懐こい女の子。',createdAt:'2026-09-15T10:00:00+09:00'},
    {id:'p3',name:'トライカラーの男の子',breed:'バーニーズ・マウンテン・ドッグ',breedKey:'bernese',gender:'男の子',genderKey:'male',color:'トライカラー',price:398000,status:'募集中',area:'神奈川県',areaKey:'kanagawa',breeder:'サンプル犬舎B',weight:12.1,adultMin:38,adultMax:45,health:true,birth:'2026-07-05',desc:'骨格がしっかりした大型犬らしい男の子。',createdAt:'2026-09-14T10:00:00+09:00'},
    {id:'p4',name:'ホワイトの男の子',breed:'サモエド',breedKey:'samoyed',gender:'男の子',genderKey:'male',color:'ホワイト',price:420000,status:'商談中',area:'千葉県',areaKey:'chiba',breeder:'サンプル犬舎C',weight:9.7,adultMin:23,adultMax:30,health:true,birth:'2026-07-18',desc:'ふわふわのホワイトコート。',createdAt:'2026-09-13T10:00:00+09:00'},
    {id:'p5',name:'ブラックの女の子',breed:'ラブラドールレトリバー',breedKey:'labrador',gender:'女の子',genderKey:'female',color:'ブラック',price:298000,status:'募集中',area:'群馬県',areaKey:'gunma',breeder:'サンプル犬舎D',weight:9.4,adultMin:24,adultMax:29,health:true,birth:'2026-07-22',desc:'遊び好きで人との関わりが大好きです。',createdAt:'2026-09-12T10:00:00+09:00'},
    {id:'p6',name:'シルバーの女の子',breed:'シベリアンハスキー',breedKey:'husky',gender:'女の子',genderKey:'female',color:'シルバー&ホワイト',price:348000,status:'募集中',area:'栃木県',areaKey:'tochigi',breeder:'サンプル犬舎E',weight:8.8,adultMin:20,adultMax:25,health:true,birth:'2026-07-25',desc:'活発で表情豊かな女の子。',createdAt:'2026-09-11T10:00:00+09:00'}
  ];
  const seedUsers=[{id:'u_demo',last:'山田',first:'太郎',email:'demo@bigpaw.jp',password:'demo',role:'buyer'}];
  function read(k,fallback){try{const v=localStorage.getItem(k);return v?JSON.parse(v):fallback}catch(e){return fallback}}
  function write(k,v){localStorage.setItem(k,JSON.stringify(v));return v}
  function ensure(){if(!localStorage.getItem(K.puppies))write(K.puppies,seedPuppies);if(!localStorage.getItem(K.users))write(K.users,seedUsers);if(!localStorage.getItem(K.favorites))write(K.favorites,[]);if(!localStorage.getItem(K.inquiries))write(K.inquiries,[])}
  function esc(s){return String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
  function breedKey(name){const m={'スタンダードプードル':'standard','ゴールデンレトリバー':'golden','ラブラドールレトリバー':'labrador','バーニーズ・マウンテン・ドッグ':'bernese','バーニーズ':'bernese','シベリアンハスキー':'husky','サモエド':'samoyed','グレートピレニーズ':'pyrenees','ボルゾイ':'borzoi'};return m[name]||'other'}
  function areaKey(name){const m={'埼玉県':'saitama','東京都':'tokyo','神奈川県':'kanagawa','千葉県':'chiba','群馬県':'gunma','栃木県':'tochigi'};return m[name]||'other'}
  ensure();
  window.BigPaw={
    esc,
    getPuppies:()=>read(K.puppies,seedPuppies),
    savePuppies:p=>write(K.puppies,p),
    addPuppy(data){const p=this.getPuppies();const obj={id:'p'+Date.now(),createdAt:new Date().toISOString(),status:'募集中',area:'埼玉県',areaKey:'saitama',breeder:'DOG44',health:true,...data};obj.breedKey=obj.breedKey||breedKey(obj.breed);obj.genderKey=obj.gender==='女の子'?'female':'male';p.unshift(obj);write(K.puppies,p);return obj},
    updatePuppy(id,patch){const p=this.getPuppies();const i=p.findIndex(x=>String(x.id)===String(id));if(i>=0){p[i]={...p[i],...patch};write(K.puppies,p);return p[i]}},
    getPuppy:id=>read(K.puppies,seedPuppies).find(x=>String(x.id)===String(id)),
    getFavorites:()=>read(K.favorites,[]),
    isFavorite(id){return this.getFavorites().includes(String(id))},
    toggleFavorite(id){let f=this.getFavorites();id=String(id);f=f.includes(id)?f.filter(x=>x!==id):[...f,id];write(K.favorites,f);return f.includes(id)},
    register(user){const users=read(K.users,seedUsers);if(users.some(u=>u.email.toLowerCase()===user.email.toLowerCase()))throw new Error('このメールアドレスは登録済みです');const u={id:'u'+Date.now(),role:'buyer',...user};users.push(u);write(K.users,users);write(K.current,{id:u.id,email:u.email,last:u.last,first:u.first,role:u.role});return u},
    login(email,password){const u=read(K.users,seedUsers).find(x=>x.email.toLowerCase()===email.toLowerCase()&&x.password===password);if(!u)throw new Error('メールアドレスまたはパスワードが違います');write(K.current,{id:u.id,email:u.email,last:u.last,first:u.first,role:u.role});return u},
    currentUser:()=>read(K.current,null),
    logout(){localStorage.removeItem(K.current)},
    addInquiry(data){const list=read(K.inquiries,[]);const q={id:'q'+Date.now(),createdAt:new Date().toISOString(),status:'未返信',...data};list.unshift(q);write(K.inquiries,list);return q},
    getInquiries:()=>read(K.inquiries,[]),
    updateInquiry(id,patch){const q=read(K.inquiries,[]);const i=q.findIndex(x=>x.id===id);if(i>=0){q[i]={...q[i],...patch};write(K.inquiries,q)}return q[i]},
    currency:n=>Number(n||0).toLocaleString('ja-JP')+'円',
    resetDemo(){Object.values(K).forEach(k=>localStorage.removeItem(k));ensure();location.reload()}
  }
})();
