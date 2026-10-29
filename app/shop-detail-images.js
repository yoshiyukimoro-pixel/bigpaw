/* Manufacturer details for 35 products. Keep specific and shared image scopes separate.
   Generated from the approved ACANA/ORIJEN/ZIWI/CHARM detail-image lists.
   All paths are relative to app/shop.html; no customer data or prices. */
(function(root) {
  'use strict';
  const images = Object.create(null);
  const suffix = '.webp';
  const add = (id, scope, basename, caption) => {
    const brand = ({A:'acana',O:'orijen',Z:'ziwi',C:'charm'})[id[0]];
    if (!brand || !/^[AOZC][0-9]{2}$/.test(id)) throw new Error('Bad catalog product');
    const path = scope === 'specific'
      ? 'assets/shop-details/products/' + id + '/' + basename + suffix
      : 'assets/shop-details/shared/' + brand + '/' + basename + suffix;
    (images[id] ||= []).push(Object.freeze({src:path,caption,scope}));
  };
  const common = (id, rows) => rows.forEach(([file,caption]) => add(id,'brand',file,caption));
  const acanaCommon = [
    ['kitchen','製造施設の紹介'],
    ['brand-info','アカナ・オリジンの特徴'],
    ['feeding-info','給餌量に関するブランド紹介']
  ];
  for (let i=1;i<=14;i++) {
    const id='A'+String(i).padStart(2,'0');
    add(id,'specific','ingredients','原材料に関するメーカー紹介画像');
    if (i===1 || i===2) add(id,'specific','puppy-range','パピーフードのラインナップ');
    if (i===9 || i===12) add(id,'specific','special-1',i===9?'パシフィカの紹介画像':'グラスフェッドラムの紹介画像');
    if (i>=12) add(id,'specific','single-range','シングルシリーズの紹介');
    common(id,acanaCommon);
  }
  const orijenCommon = [
    ['protein','タンパク質に関する紹介'],
    ['kitchen','製造施設の紹介'],
    ['brand-info','アカナ・オリジンの特徴']
  ];
  for (let i=1;i<=8;i++) {
    const id='O'+String(i).padStart(2,'0');
    add(id,'specific','ingredients','原材料に関するメーカー紹介画像');
    if (i===1) add(id,'specific','overview','オリジナルの紹介');
    common(id,orijenCommon);
  }
  const airIntro=['air-dried-introduction','エアドライ製法の紹介'];
  const airOther=[
    ['air-other-9312','エアドライの素材紹介 1'],
    ['air-other-9313','エアドライの素材紹介 2'],
    ['air-other-9314','エアドライの素材紹介 3']
  ];
  const airChicken=[
    ['air-chicken-9312','エアドライ チキンの素材紹介 1'],
    ['air-chicken-9313','エアドライ チキンの素材紹介 2'],
    ['air-chicken-9314','エアドライ チキンの素材紹介 3']
  ];
  const steamCommon=[
    ['steam-ingredients','スチームドライの原材料紹介'],
    ['steam-process','スチームドライの製法紹介'],
    ['steam-vs-air','スチームドライとエアドライの比較'],
    ['steam-lineup','スチームドライのラインナップ']
  ];
  for (let i=1;i<=9;i++) {
    const id='Z'+String(i).padStart(2,'0');
    if(i<=6) {
      add(id,'specific','ingredients','原材料のメーカー紹介画像');
      common(id,[airIntro,...(i===6?airChicken:airOther)]);
    } else {
      if(i===7) add(id,'specific','food','ビーフ＆パンプキンのフード写真');
      common(id,steamCommon);
    }
  }
  const charmCommon=[
    ['ingredients','CHARMシリーズの原材料紹介'],
    ['concept-1','CHARMブランドの特徴①'],
    ['concept-2','CHARMブランドの特徴②'],
    ['concept-3','CHARMブランドの特徴③'],
    ['protect-10','CHARMの特長とラインナップ']
  ];
  for(let i=1;i<=4;i++) {
    const id='C'+String(i).padStart(2,'0');
    add(id,'specific','food','フードの写真');
    common(id,charmCommon);
  }
  for(const key of Object.keys(images)) Object.freeze(images[key]);
  root.BIGPAW_SHOP_DETAIL_IMAGES=Object.freeze(images);
})(window);
