const { chromium, webkit } = require('playwright');

const base=(process.argv[2]||'http://127.0.0.1:18106').replace(/\/$/,'');
const shortVideo=process.argv[3]||'/tmp/bp-short.mp4';
const longVideo=process.argv[4]||'/tmp/bp-long.mp4';

function check(ok,msg){if(!ok)throw new Error(msg)}

async function run(engine,name,contextOptions,launchOptions={}){
  const browser=await engine.launch({headless:true,...launchOptions});
  const context=await browser.newContext(contextOptions);
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push('pageerror:'+e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push('console:'+m.text())});
  try{
    await page.goto(base+'/login.html',{waitUntil:'domcontentloaded'});
    await page.fill('#email','dog44@bigpaw.jp');
    await page.fill('#password','demo1234');
    await Promise.all([
      page.waitForURL(/\/admin\.html(?:$|\?)/,{timeout:15000}),
      page.click('form button[type="submit"], form button')
    ]);

    await page.goto(base+'/breeder-puppy-new.html',{waitUntil:'domcontentloaded'});
    await page.waitForSelector('#puppyVideo',{state:'visible'});
    const note=await page.locator('#puppyVideoBox').innerText();
    check(note.includes('動画を追加（1本まで）'),name+': one-video wording missing');
    check(note.includes('60秒以内'),name+': 60-second wording missing');
    const policy=await page.evaluate(()=>({
      max:window.BigPawPuppyVideo?.maxSeconds,
      at60:window.BigPawPuppyVideo?.durationAllowed(60),
      over:window.BigPawPuppyVideo?.durationAllowed(60.01)
    }));
    check(policy.max===60&&policy.at60===true&&policy.over===false,name+': JS duration boundary wrong');

    await page.setInputFiles('#puppyVideo',longVideo);
    await page.waitForFunction(()=>document.querySelector('#puppyVideoStatus')?.textContent.includes('60秒以内に編集'),null,{timeout:15000});
    check(await page.locator('#puppyVideo').evaluate(el=>el.files.length)===0,name+': overlong video input was not cleared');
    check((await page.locator('#puppyVideoStatus').innerText()).includes('60秒以内に編集'),name+': overlong guidance missing');

    await page.setInputFiles('#puppyVideo',shortVideo);
    await page.waitForFunction(()=>document.querySelector('#puppyVideoStatus')?.textContent.includes('60秒以内です'),null,{timeout:15000});
    check(await page.locator('#puppyVideo').evaluate(el=>el.files.length)===1,name+': valid video not retained');
    check(await page.locator('#puppyVideoPreview video').count()===1,name+': valid video preview missing');

    // Public renderer is additive and uses a Cloudflare iframe only when the puppy API exposes one.
    const detail=await context.newPage();
    const response=await detail.goto(base+'/puppy-detail.html?id=p1',{waitUntil:'domcontentloaded'});
    const csp=(response&&response.headers()['content-security-policy'])||'';
    check(csp.includes('frame-src')&&csp.includes('cloudflarestream.com'),name+': CSP frame-src missing Stream');
    check(csp.includes('connect-src')&&csp.includes('videodelivery.net'),name+': CSP connect-src missing direct upload');
    await detail.waitForFunction(()=>window.BigPawBridge&&typeof window.BigPawBridge.puppy==='function');
    await detail.evaluate(()=>{
      window.BigPawBridge.puppy=async()=>({
        id:'p1',
        videoEmbedUrl:'https://customer-test.cloudflarestream.com/testvideo123/iframe'
      });
      window.dispatchEvent(new Event('pageshow'));
    });
    await detail.waitForSelector('#bigpawPuppyVideoSection iframe',{timeout:5000});
    const src=await detail.locator('#bigpawPuppyVideoSection iframe').getAttribute('src');
    check(src.includes('cloudflarestream.com/testvideo123/iframe'),name+': public video iframe not rendered');
    await detail.close();

    const serious=errors.filter(x=>!x.includes('cloudflarestream.com')&&!x.includes('ERR_NAME_NOT_RESOLVED'));
    check(serious.length===0,name+': browser errors: '+serious.join(' | '));
    console.log('PUPPY_VIDEO_BROWSER_OK',name);
  }finally{
    await context.close();
    await browser.close();
  }
}

(async()=>{
  const chromePath=process.env.BIGPAW_CHROME_PATH||'';
  await run(chromium,'chromium-desktop',{viewport:{width:1365,height:900}},chromePath?{executablePath:chromePath}:{});
  await run(webkit,'webkit-iphone',{
    viewport:{width:390,height:844},
    userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1',
    isMobile:true,
    hasTouch:true
  });
})().catch(e=>{console.error(e);process.exit(1)});
