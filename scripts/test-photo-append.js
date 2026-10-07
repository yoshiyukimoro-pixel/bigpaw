const fs=require('fs');
const vm=require('vm');
const code=fs.readFileSync('app/breeder-editor-safety-fix.js','utf8');

const fields={
  breed:{value:'スタンダードプードル'},
  gender:{value:'男の子'},
  color:{value:'ブラック'},
  birth:{value:'2026-07-01'},
  price:{value:'220000'},
  weight:{value:'10.0'},
  adultMin:{value:'28'},
  adultMax:{value:'32'},
  father:{value:'クラージュ'},
  mother:{value:'ミルク'},
  health:{checked:true},
  appealPoint:{value:'元気です'},
  desc:{value:'テスト'},
  status:{value:'募集中'},
  photo:{files:[{name:'new.jpg'}]}
};
const calls={uploads:[],orders:[],updates:[],deletes:[]};
const old=[
  {id:'old1',url:'/uploads/old1.jpg',isMain:true},
  {id:'old2',url:'/uploads/old2.jpg',isMain:false},
  {id:'old3',url:'/uploads/old3.jpg',isMain:false}
];
global.window={};
global.document={getElementById:id=>fields[id]||null};
global.location={search:'?id=p1',href:''};
global.sessionStorage={removeItem(){}};
global.alert=()=>{};
global.BigPawAPI={
  request:async(path,opt={})=>{
    if(path==='/puppies/p1/photos'&&!opt.method)return JSON.parse(JSON.stringify(old));
    if(path==='/puppies/p1/photos/order'&&opt.method==='PATCH'){
      calls.orders.push(opt.body.ids.slice()); return {ok:true};
    }
    if(opt.method==='DELETE'){calls.deletes.push(path); return {ok:true};}
    throw new Error('unexpected request '+path+' '+JSON.stringify(opt));
  }
};
global.BigPawBridge={
  updatePuppy:async(id,data)=>{calls.updates.push({id,data});return {id};},
  addPuppy:async()=>{throw new Error('must edit existing puppy')},
  upload:async(file,pid)=>{
    calls.uploads.push({file,pid});
    return {id:'new1',url:'/uploads/new1.jpg'};
  },
  breederPuppies:async()=>[{id:'p1',appealPoint:'元気です'}]
};
vm.runInThisContext(code,{filename:'breeder-editor-safety-fix.js'});
(async()=>{
  let prevented=false;
  await window.savePuppy({
    preventDefault(){prevented=true},
    submitter:{disabled:false,textContent:'保存'}
  });
  if(!prevented)throw new Error('submit not prevented');
  if(calls.uploads.length!==1)throw new Error('expected exactly one new upload');
  if(calls.deletes.length!==0)throw new Error('existing photos must not be deleted');
  const expected=['old1','old2','old3','new1'];
  if(calls.orders.length!==1||JSON.stringify(calls.orders[0])!==JSON.stringify(expected)){
    throw new Error('photo order mismatch '+JSON.stringify(calls.orders));
  }
  const imageChanges=calls.updates.filter(x=>Object.prototype.hasOwnProperty.call(x.data||{},'imageUrl'));
  if(imageChanges.length)throw new Error('existing main photo must remain unchanged');
  console.log('PHOTO_APPEND_BEHAVIOR_OK|existing=3|added=1|final=4|main_preserved=1|deleted=0');
})().catch(e=>{console.error(e);process.exit(1)});