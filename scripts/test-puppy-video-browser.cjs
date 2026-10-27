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
  // Keep this local browser test deterministic: mock only external Stream
  // documents. The browser still enforces our real Content Security Policy.
  const streamHtml='<!doctype html><html><body><button type="button">Mock Stream playback</button></body></html>';
  await context.route('https://videodelivery.net/**',route=>
    route.fulfill({status:200,contentType:'text/html',body:streamHtml}));
  await context.route('https://customer-test.cloudflarestream.com/**',route=>
    route.fulfill({status:200,contentType:'text/html',body:streamHtml}));
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
    // Login performs an intentional unauthenticated /api/me probe before the
    // session is established. Do not treat that expected 401 as a video error.
    errors.length=0;
    const note=await page.locator('#puppyVideoBox').innerText();
    check(note.includes('動画を追加（1本まで）'),name+': one-video wording missing');
    check(note.includes('60秒以内'),name+': 60-second wording missing');
    const policy=await page.evaluate(()=>({
      max:window.BigPawPuppyVideo?.maxSeconds,
      at60:window.BigPawPuppyVideo?.durationAllowed(60),
      over:window.BigPawPuppyVideo?.durationAllowed(60.01)
    }));
    check(policy.max===60&&policy.at60===true&&policy.over===false,name+': JS duration boundary wrong');
    // The production Cloudflare response now uses upload.cloudflarestream.com.
    // Regressions must exercise this real hostname, not only the legacy domain.
    // Static host safety is checked without a browser fetch, so browser
    // testing remains focused on the live upload/reopen path.
    const source=require('fs').readFileSync('app/assets/puppy-video.js','utf8');
    const acceptedHosts=source.includes("'upload.cloudflarestream.com','upload.videodelivery.net'") &&
      source.includes("target.protocol!=='https:'") &&
      source.includes('target.username||target.password');
    check(acceptedHosts,name+': strict allowlist missing actual Cloudflare upload host');

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

    // Reproduce the production symptom: on an existing puppy, selecting a video
    // must upload immediately and persist across editor reload, not only preview.
    console.log('VIDEO_BROWSER_STAGE',name,'existing-puppy-autosave-and-reload');
    let attachedUid='';
    let ticketCount=0;
    let attachCount=0;
    const uid='browserVideoAuto12345';
    await page.route('**/api/breeder/puppies',async route=>{
      const upstream=await route.fetch();
      const data=await upstream.json();
      const updated=Array.isArray(data)?data.map(p=>
        String(p.id)==='p1'&&attachedUid?
          {...p,videoUid:attachedUid,videoStatus:'ready',videoEmbedUrl:'https://videodelivery.net/'+attachedUid+'/iframe'}:p
      ):data;
      await route.fulfill({response:upstream,json:updated});
    });
    await page.route('**/api/puppies/p1/video-tus-upload',async route=>{
      ticketCount+=1;
      await route.fulfill({status:201,contentType:'application/json',body:JSON.stringify({
        uid,uploadURL:'https://upload.cloudflarestream.com/tus/mock-stream-direct-upload',maxSeconds:60,protocol:'tus'
      })});
    });
    let uploadCount=0;
    await page.route('https://upload.cloudflarestream.com/tus/mock-stream-direct-upload',async route=>{
      const req=route.request();
      // Cross-origin PATCH requires CORS preflight on Chromium and Safari.
      // Cloudflare accepts tus headers; the fixture must do the same.
      if(req.method()==='OPTIONS'){
        return route.fulfill({status:204,headers:{
          'Access-Control-Allow-Origin':'*',
          'Access-Control-Allow-Methods':'PATCH,HEAD,OPTIONS',
          'Access-Control-Allow-Headers':'tus-resumable,upload-offset,content-type',
          'Access-Control-Max-Age':'600'
        }});
      }
      if(req.method()==='HEAD'){
        return route.fulfill({status:200,headers:{
          'Access-Control-Allow-Origin':'*','Access-Control-Expose-Headers':'Upload-Offset',
          'Tus-Resumable':'1.0.0','Upload-Offset':String(uploadCount?shortVideo.buffer.length:0)
        }});
      }
      // Cloudflare's resumable upload is a direct binary PATCH to an origin
      // outside BIG PAW, with response offset proving real bytes were sent.
      check(req.method()==='PATCH',name+': Stream tus upload must PATCH');
      const body=req.postDataBuffer();
      check((req.headers()['content-type']||'').includes('application/offset+octet-stream'),name+': tus binary type missing');
      check(req.headers()['tus-resumable']==='1.0.0',name+': tus protocol header missing');
      // Playwright's WebKit interception cannot read Blob-backed PATCH payloads
      // (postDataBuffer() is null) even when fetch was passed a valid Blob.
      // The browser-side probe below asserts the actual Blob byte length/prefix.
      if(body!==null)check(body.length===shortVideo.buffer.length,
        name+': intercepted tus body length incorrect: '+body.length);
      else check(name==='webkit-iphone',name+': empty tus payload not expected on Chromium');
      await new Promise(resolve=>setTimeout(resolve,2300));
      uploadCount+=1;
      await route.fulfill({status:204,headers:{
        'Access-Control-Allow-Origin':'*','Access-Control-Expose-Headers':'Upload-Offset',
        'Tus-Resumable':'1.0.0','Upload-Offset':String(shortVideo.buffer.length)
      },body:''});
    });
    await page.route('**/api/puppies/p1/video',async route=>{
      if(!uploadCount){
        await route.fulfill({status:409,contentType:'application/json',
          body:JSON.stringify({error:'video_upload_not_received'})});
        return;
      }
      attachCount+=1;
      attachedUid=uid;
      await route.fulfill({status:201,contentType:'application/json',body:JSON.stringify({
        id:'p1',videoUid:uid,videoStatus:'ready',
        videoEmbedUrl:'https://videodelivery.net/'+uid+'/iframe'
      })});
    });
    // Inspect the real File.slice Blob in the Safari page before handing
    // it to native fetch. WebKit Playwright cannot expose Blob postDataBuffer.
    await page.addInitScript(()=>{
      const orig=window.fetch.bind(window);
      window.fetch=async (url,opts)=>{
        if(opts?.method==='PATCH'&&String(url).includes('upload.cloudflarestream.com/tus/')){
          const buffer=await opts.body.arrayBuffer();
          const bytes=new Uint8Array(buffer);
          window.__bigpawTusByteProbe={length:bytes.byteLength,prefix:Array.from(bytes.slice(0,16))};
        }
        return orig(url,opts);
      };
    });
    await page.goto(base+'/breeder-puppy-new.html?id=p1',{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>document.querySelector('h1')?.textContent==='掲載内容を編集',null,{timeout:15000});
    await page.setInputFiles('#puppyVideo',shortVideo);
    // A small file may skip straight from preparing to received; the durable
    // race invariant is that Save is disabled immediately on file selection.
    await page.waitForFunction(()=>document.querySelector('.btn-main.btn-wide')?.disabled===true,null,{timeout:15000});
    check(await page.locator('.btn-main.btn-wide').isDisabled(),name+': Save must be disabled while iPhone video is still uploading');
    await page.waitForTimeout(400);
    check(page.url().includes('breeder-puppy-new.html?id=p1'),name+': editor navigated before upload receipt');
    check(!uploadCount&&!attachCount,name+': mock must still be uploading before receipt');
    try{
      await page.waitForFunction(()=>document.querySelector('#puppyVideoStatus')?.textContent.includes('動画を登録しました。'),null,{timeout:20000});
    }catch(e){
      const status=await page.locator('#puppyVideoStatus').innerText().catch(()=>'-');
      throw new Error(name+': tus upload did not finish: status='+status+
        ' tickets='+ticketCount+' patches='+uploadCount+' attaches='+attachCount+
        ' browserErrors='+errors.slice(-4).join('; ')+' error='+e.message);
    }
    const byteProbe=await page.evaluate(()=>window.__bigpawTusByteProbe);
    check(byteProbe?.length===shortVideo.buffer.length&&
      JSON.stringify(byteProbe.prefix)===JSON.stringify([...shortVideo.buffer.slice(0,16)]),
      name+': iPhone Blob handed to tus fetch does not contain the source video bytes');
    check(!(await page.locator('.btn-main.btn-wide').isDisabled()),name+': Save must be enabled after video is really attached');
    check(ticketCount===1&&uploadCount===1&&attachCount===1,name+': resumable tus upload must reach Stream and attach once');
    check(await page.locator('#puppyVideoExisting iframe').count()===1,name+': saved video not displayed');
    await page.reload({waitUntil:'domcontentloaded'});
    await page.waitForSelector('#puppyVideoExisting iframe',{timeout:15000});
    check(await page.locator('#puppyVideoExisting iframe').getAttribute('src')==='https://videodelivery.net/'+uid+'/iframe',
      name+': video missing after reopening editor');
    // The seeded puppy predates required sales-policy fields injected by the
    // production Docker build. Fill these to exercise a valid ordinary form save.
    await page.locator('#breedingAllowed').selectOption({index:1});
    await page.locator('#breederSaleAllowed').selectOption({index:1});
    // Ordinary form Save must not initiate a duplicate upload or remove the video.
    const formState=await page.evaluate(()=>{
      const button=document.querySelector('.btn-main.btn-wide');
      const form=button?.form;
      return {
        type:button?.type,hasForm:!!form,valid:form?.checkValidity(),
        submitHandler:typeof window.savePuppy,
        invalid:form?Array.from(form.elements).filter(e=>e.checkValidity&&!e.checkValidity())
          .map(e=>({id:e.id,value:e.value,reason:e.validationMessage})):[],
      };
    });
    console.log('VIDEO_BROWSER_FORM_STATE',name,JSON.stringify(formState));
    check(formState.hasForm&&formState.valid,name+': breeder form invalid before video-safe save: '+JSON.stringify(formState));
    let saveDialog='';
    page.once('dialog',async dialog=>{saveDialog=dialog.message();await dialog.accept()});
    try{
      await Promise.all([
        page.waitForURL(/\/admin\.html(?:$|\?)/,{waitUntil:'domcontentloaded',timeout:15000}),
        page.locator('.btn-main.btn-wide').click()
      ]);
    }catch(e){
      const diag=await page.evaluate(()=>({
        href:location.href,saveLabel:document.querySelector('.btn-main.btn-wide')?.textContent,
        videoStatus:document.getElementById('puppyVideoStatus')?.textContent
      })).catch(x=>({error:String(x)}));
      throw new Error(name+': form Save did not navigate: dialog='+saveDialog+' diag='+JSON.stringify(diag)+'; '+e.message);
    }
    check(saveDialog.includes('変更を保存しました'),name+': unexpected save message: '+saveDialog);
    check(ticketCount===1&&attachCount===1,name+': form Save repeated video upload');
    // Persistence was already verified with a real editor reload above. A
    // second forced goto here races Safari's unrelated post-save login redirect.
    console.log('PUPPY_VIDEO_AUTOSAVE_RELOAD_OK',name);

    // Public renderer is additive. Stub only the pre-existing data bridge so this
    // browser check stays focused on the new video renderer rather than unrelated app state.
    console.log('VIDEO_BROWSER_STAGE',name,'public-render');
    const raw=await context.request.get(base+'/puppy-detail.html?id=p1');
    check(raw.ok(),name+': public detail HTTP failed');
    const csp=raw.headers()['content-security-policy']||'';
    check(csp.includes('frame-src')&&csp.includes('cloudflarestream.com'),name+': CSP frame-src missing Stream');
    check(csp.includes('https://videodelivery.net'),name+': CSP blocks apex videodelivery.net Stream fallback iframe');
    check(csp.includes('connect-src')&&csp.includes('videodelivery.net'),name+': CSP connect-src missing direct upload');
    check(csp.includes('media-src')&&csp.includes('blob:'),name+': CSP media-src must allow local video metadata preview');
    check(csp.includes("form-action 'self' https://upload.cloudflarestream.com https://upload.videodelivery.net"),name+': CSP blocks native Stream upload');

    const detail=await context.newPage();
    await detail.goto(base+'/puppy-detail.html?id=p1',{waitUntil:'domcontentloaded'});
    // The video renderer must really load from the public page. Its fixture data
    // is independent of the legacy bridge's initialization timing on Safari.
    // A missing renderer still fails the test (and emits useful diagnostics).
    try{
      await detail.waitForFunction(()=>typeof window.BigPawPuppyVideoPublic?.render==='function',null,{timeout:30000});
    }catch(e){
      const diag=await detail.evaluate(()=>({
        href:location.href,
        ready:document.readyState,
        scripts:Array.from(document.scripts).map(s=>s.src).filter(s=>s.includes('puppy-video')||s.includes('bridge'))
      })).catch(err=>({error:String(err)}));
      throw new Error(name+': public video script failed to initialize: '+JSON.stringify(diag)+'; '+e.message);
    }
    const rendered=await detail.evaluate(async()=>{
      window.BigPawBridge=window.BigPawBridge||{};
      window.BigPawBridge.puppy=async()=>({
        id:'p1',
        videoEmbedUrl:'https://customer-test.cloudflarestream.com/testvideo123/iframe'
      });
      const existing=document.getElementById('bigpawPuppyVideoSection');
      if(existing)existing.remove();
      await window.BigPawPuppyVideoPublic.render();
      const frame=document.querySelector('#bigpawPuppyVideoSection iframe');
      return frame?frame.getAttribute('src'):'';
    });
    check(rendered.includes('cloudflarestream.com/testvideo123/iframe'),name+': public video iframe not rendered');
    await detail.close();

    // A stalled mobile upload must never trap the user on a disabled Save
    // button; cancellation must keep any previously saved video intact.
    console.log('VIDEO_BROWSER_STAGE',name,'cancel-stalled-upload');
    await page.goto(base+'/breeder-puppy-new.html?id=p1',{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>document.querySelector('h1')?.textContent==='掲載内容を編集',null,{timeout:15000});
    await page.setInputFiles('#puppyVideo',shortVideo);
    await page.locator('#cancelPuppyVideoUploadBtn').waitFor({state:'visible',timeout:15000});
    check(await page.locator('.btn-main.btn-wide').isDisabled(),name+': Save should be disabled during active tus PATCH');
    await page.locator('#cancelPuppyVideoUploadBtn').click();
    await page.waitForFunction(()=>document.querySelector('#puppyVideoStatus')?.textContent.includes('通常の内容は保存できます'),null,{timeout:15000});
    check(!(await page.locator('.btn-main.btn-wide').isDisabled()),name+': Save did not unlock after cancelling tus');
    check(await page.locator('#puppyVideoExisting iframe').count()===1,name+': existing saved video was lost on cancel');

    // The mock deliberately responds 409 while the native multipart form is
    // still starting. It is an expected, retried "pending upload" state.
    const serious=errors.filter(x=>!x.includes('cloudflarestream.com')&&!x.includes('ERR_NAME_NOT_RESOLVED')&&!x.includes('409 (Conflict)'));
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
