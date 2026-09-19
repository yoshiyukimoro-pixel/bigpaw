(function(){'use strict';
const B=Array.isArray(window.BIGPAW_BREEDS)?window.BIGPAW_BREEDS:[];
const q=new URLSearchParams(location.search), key=q.get('breed'), b=B.find(x=>x.key===key);
if(!b){document.querySelector('main').innerHTML='<section class="section"><h1>犬種が見つかりません</h1><a class="btn primary" href="breed-guide.html">犬種ガイドへ戻る</a></section>';return;}
const traits={
'standard-poodle':['非常に学習意欲が高く、人との共同作業を楽しみやすい','多め','定期的なブラッシングとトリミングが必要','抜け毛は比較的少ないが、毛は伸び続けるため継続的な手入れが必要'],
'golden-retriever':['人との関わりを好み、明るく協調的な傾向','多め','週に数回のブラッシング。換毛期は特に丁寧に','ダブルコートで抜け毛は多め'],
'labrador-retriever':['活動的で人と一緒に行動することを好みやすい','多め','短毛だが定期的なブラッシングが必要','ダブルコートで換毛期は抜け毛が増える'],
'bernese-mountain-dog':['穏やかで家族との結びつきを大切にしやすい','中〜多','長い被毛を定期的にブラッシング','ダブルコートで抜け毛は多め'],
'siberian-husky':['活発で持久力があり、自立心も持ち合わせる','かなり多い','換毛期を中心に十分なブラッシング','厚いダブルコート。暑い時期の温度管理が重要'],
'samoyed':['人との交流を好み、活動的な傾向','多め','豊富な被毛をこまめにブラッシング','厚いダブルコートで換毛期の手入れ量は多い']
};
function family(k){
 if(/retriever|pointer|setter|weimaraner/.test(k))return['活動性が高く、人と一緒に作業することを楽しみやすい','多め','犬種の被毛タイプに合わせた定期的なブラッシング','運動とトレーニングを毎日の生活に組み込みたい'];
 if(/mastiff|corso|rottweiler|dobermann|shepherd|schnauzer|hovawart|beauceron|briard|bouvier/.test(k))return['落ち着きや警戒心を持つ個体も多く、早期からの社会化が重要','中〜多','被毛タイプに合わせた定期的なケア','大型で力が強いため、基礎トレーニングと社会化を重視したい'];
 if(/hound|borzoi|saluki|wolfhound|deerhound/.test(k))return['独立心を見せることがあり、穏やかな接し方と継続的なトレーニングが大切','中〜多','被毛タイプに合わせた定期的なケア','安全に走れる環境と、逸走を防ぐ管理を重視したい'];
 if(/husky|malamute|samoyed|akita/.test(k))return['自立心と活動性を持つ傾向があり、十分な社会化が大切','多め','換毛期を中心に十分なブラッシング','運動時間と暑い季節の温度管理を確保したい'];
 return['犬種本来の特性を理解し、子犬期から社会化と基礎トレーニングを続けたい','中〜多','被毛タイプに合わせた定期的なケア','大型犬に必要な運動・生活スペース・継続的な管理を確保したい'];
}
const t=traits[key]||family(key);
document.title=b.ja+'の特徴・飼い方｜大型犬種ガイド｜BIG PAW';
document.querySelector('#breedName').textContent=b.ja;
document.querySelector('#breedLead').textContent=t[0];
document.querySelector('#exercise').textContent=t[1];
document.querySelector('#grooming').textContent=t[2];
document.querySelector('#coat').textContent=t[3];
document.querySelector('#breedPhoto').src='/api/breed-image?key='+encodeURIComponent(key)+'&v=7';
document.querySelector('#breedPhoto').alt=b.ja;
document.querySelector('#searchBreed').href='search.html?breed='+encodeURIComponent(key);
document.querySelector('#training').textContent='体が大きくなる前から、呼び戻し・リード歩行・待つ・人や犬への適切な接し方を少しずつ練習します。力で抑えるのではなく、一貫したルールと褒めるトレーニングを基本にします。';
document.querySelector('#health').textContent='犬種ごとに注意したい遺伝性疾患や関節・眼・心臓などの健康課題があります。子犬を迎える際は、親犬の健康検査、既往歴、飼育環境についてブリーダーに確認することが大切です。';
})();