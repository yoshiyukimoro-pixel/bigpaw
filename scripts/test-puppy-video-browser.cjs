const { chromium, webkit } = require('playwright');

const base=(process.argv[2]||'http://127.0.0.1:18106').replace(/\/$/,'');
const SHORT_WEBM='GkXfo59ChoEBQveBAULygQRC84EIQoKEd2VibUKHgQJChYECGFOAZwEAAAAAAAH+EU2bdLpNu4tTq4QVSalmU6yBoU27i1OrhBZUrmtTrIHWTbuMU6uEElTDZ1OsggEjTbuMU6uEHFO7a1OsggHo7AEAAAAAAABZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVSalmsCrXsYMPQkBNgIxMYXZmNjEuNy4xMDNXQYxMYXZmNjEuNy4xMDNEiYhAn0AAAAAAABZUrmvIrgEAAAAAAAA/14EBc8WIkfNJWIh6s6acgQAitZyDdW5kiIEAhoVWX1ZQOYOBASPjg4Q7msoA4JCwgRC6gRCagQJVsIRVuYEBElTDZ0B/c3OfY8CAZ8iZRaOHRU5DT0RFUkSHjExhdmY2MS43LjEwM3Nz2mPAi2PFiJHzSViIerOmZ8ilRaOHRU5DT0RFUkSHmExhdmM2MS4xOS4xMDEgbGlidnB4LXZwOWfIoUWjiERVUkFUSU9ORIeTMDA6MDA6MDIuMDAwMDAwMDAwAB9DtnW754EAo6GBAACAgkmDQgAA8AD2ADgkHBhCAAAwYAAAEL///YsqAACjk4ED6ACGAECSnABJQAADYAAAQkAcU7trkbuPs4EAt4r3gQHxggGo8IED';
const LONG_WEBM='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';
const shortVideo={name:'short.webm',mimeType:'video/webm',buffer:Buffer.from(SHORT_WEBM,'base64')};
const longVideo={name:'long.webm',mimeType:'video/webm',buffer:Buffer.from(LONG_WEBM,'base64')};

function check(ok,msg){if(!ok)throw new Error(msg)}

async function run(engine,name,contextOptions,launchOptions={}){
  const browser=await engine.launch({headless:true,...launchOptions});
  const context=await browser.newContext(contextOptions);
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push('pageerror:'+e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push('console:'+m.text())});
  try{
    console.log('VIDEO_BROWSER_STAGE',name,'login');
    await page.goto(base+'/login.html',{waitUntil:'domcontentloaded'});
    await page.fill('#email','dog44@bigpaw.jp');
    await page.fill('#password','demo1234');
    await Promise.all([
      page.waitForURL(/\/admin\.html(?:$|\?)/,{timeout:15000}),
      page.click('form button[type="submit"], form button')
    ]);

    console.log('VIDEO_BROWSER_STAGE',name,'editor');
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

    console.log('VIDEO_BROWSER_STAGE',name,'overlong');
    await page.setInputFiles('#puppyVideo',longVideo);
    await page.waitForFunction(()=>document.querySelector('#puppyVideoStatus')?.textContent.includes('60秒以内に編集'),null,{timeout:15000});
    check(await page.locator('#puppyVideo').evaluate(el=>el.files.length)===0,name+': overlong video input was not cleared');
    check((await page.locator('#puppyVideoStatus').innerText()).includes('60秒以内に編集'),name+': overlong guidance missing');

    console.log('VIDEO_BROWSER_STAGE',name,'short');
    await page.setInputFiles('#puppyVideo',shortVideo);
    await page.waitForFunction(()=>document.querySelector('#puppyVideoStatus')?.textContent.includes('60秒以内です'),null,{timeout:15000});
    check(await page.locator('#puppyVideo').evaluate(el=>el.files.length)===1,name+': valid video not retained');
    check(await page.locator('#puppyVideoPreview video').count()===1,name+': valid video preview missing');

    // Public renderer is additive. Stub only the pre-existing data bridge so this
    // browser check stays focused on the new video renderer rather than unrelated app state.
    console.log('VIDEO_BROWSER_STAGE',name,'public-render');
    const raw=await context.request.get(base+'/puppy-detail.html?id=p1');
    check(raw.ok(),name+': public detail HTTP failed');
    const csp=raw.headers()['content-security-policy']||'';
    check(csp.includes('frame-src')&&csp.includes('cloudflarestream.com'),name+': CSP frame-src missing Stream');
    check(csp.includes('connect-src')&&csp.includes('videodelivery.net'),name+': CSP connect-src missing direct upload');
    check(csp.includes('media-src')&&csp.includes('blob:'),name+': CSP media-src must allow local video metadata preview');

    const detail=await context.newPage();
    await detail.route('**/puppy-detail.html?id=p1',route=>route.fulfill({
      status:200,
      contentType:'text/html; charset=utf-8',
      body:`<!doctype html><html><body><main><div id="bigpawDetailMore"></div></main>
      <script>window.BigPawBridge={puppy:async()=>({id:'p1',videoEmbedUrl:'https://customer-test.cloudflarestream.com/testvideo123/iframe'})};<\/script>
      <script src="/assets/puppy-video-public.js?v=20261026-1"><\/script></body></html>`
    }));
    await detail.goto(base+'/puppy-detail.html?id=p1',{waitUntil:'domcontentloaded'});
    await detail.waitForSelector('#bigpawPuppyVideoSection iframe',{timeout:10000});
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
