/* Browser regression and visual inspection suite. All inputs are local. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');
(async () => {
 const [fixture, output, executablePath] = process.argv.slice(2);
 fs.mkdirSync(output, {recursive:true});
 const browser = await chromium.launch({headless:true, ...(executablePath ? {executablePath} : {})});
 try {
  const page = await browser.newPage({viewport:{width:820,height:1000}});
  const errors=[], requests=[];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => {if (/^https?:/.test(r.url())) requests.push(r.url());});
  await page.route('https://**/*', route => route.abort());
  await page.route('http://**/*', route => route.abort());
  await page.goto(pathToFileURL(path.resolve(fixture)).href);
  async function checkReadingHeights(surface) {
   await surface.evaluate(() => {
    const style=document.createElement('style');
    style.textContent='button { height: 60px; padding: 20px; margin: 15px; font-size: 24px; line-height: 3; }';
    document.head.appendChild(style);
    const host=document.createElement('div');host.className='akb-root';document.body.appendChild(host);
    window.AutoKanjiBreakdown.render(host,{version:1,entries:[{char:'強',readings:{on:['キョウ','ゴウ'],kun:['つよ.い','つよ.まる','つよ.める','し.いる','こわ.い']}}]});
    const on=host.querySelector('.akb-on'),kun=host.querySelector('.akb-kun');
    if(!kun.querySelector('.akb-more'))throw Error('Missing reading reveal fixture');
    if(Math.abs(on.getBoundingClientRect().height-kun.getBoundingClientRect().height)>1)throw Error('Reading reveal inflates chip height');
    kun.querySelector('.akb-more').click();
    if(kun.querySelector('.akb-more').getAttribute('aria-expanded')!=='true')throw Error('Reading reveal stopped working');
    host.remove();style.remove();
   });
  }
  await checkReadingHeights(page);
  async function checkBranchAlignment(surface) {
   await surface.evaluate(() => {
    const style=document.createElement('style');
    style.textContent='button { margin: 20px 8px; min-height: 80px; height: 80px; line-height: 4; }';
    const host=document.createElement('div');host.className='akb-root';document.body.appendChild(host);
    window.AutoKanjiBreakdown.render(host,{entries:[{char:'歯',children:[
     {char:'止',children:[{char:'卜',children:[{char:'丨'}]}]}, {char:'米'}, {char:'凵'}]}]});
    host.querySelectorAll('button').forEach(button=>button.click());
    const compactHeight=host.getBoundingClientRect().height;
    document.head.appendChild(style);
    if(Math.abs(host.getBoundingClientRect().height-compactHeight)>1)throw Error('Card button styling adds empty vertical space');
    host.querySelectorAll('.akb-component-char').forEach(char=>{
     const rect=char.getBoundingClientRect(),line=getComputedStyle(char,'::before');
     if(line.content!=='""'||Math.abs(parseFloat(line.top)-rect.height/2)>1)throw Error('Branch connector is not centered on its character');
    });
    host.remove();style.remove();
   });
  }
  await checkBranchAlignment(page);
  async function checkOpenSources(surface, area) {
   const panel=area.locator('.akb-sources-panel');
   const root=await area.boundingBox(), first=await area.locator('.akb-card').first().boundingBox(), box=await panel.boundingBox();
   assert.ok(Math.abs(first.y-root.y-(root.y+root.height-box.y-box.height))<1,'Balanced expanded Sources inset');
   for(const link of await panel.getByRole('link').all()) {
    assert.ok(await link.getAttribute('href'));
    assert.equal(await link.evaluate(e=>getComputedStyle(e).textDecorationLine),'underline');
   }
   assert.equal(await panel.locator('div').first().evaluate(e=>getComputedStyle(e).textDecorationLine),'none');
   const link=panel.getByRole('link',{name:'Project on GitHub'});
   await surface.keyboard.press('Tab');
   await link.focus();
   assert.equal(await link.evaluate(e=>getComputedStyle(e).outlineStyle),'solid');
   assert.equal(await link.evaluate(e=>getComputedStyle(e).outlineWidth),'2px');
   await link.hover();
   assert.equal(await link.evaluate(e=>getComputedStyle(e).textDecorationThickness),'2px');
  }
  async function checkSources(surface, touch=false) {
   const area=surface.locator('.akb-root').first(), button=area.locator('.akb-sources-toggle');
   assert.equal(await button.count(),1);
   assert.equal(await button.textContent(),'ⓘ');
   assert.equal(await button.getAttribute('title'),'Sources & licences');
   assert.equal(await button.getAttribute('aria-label'),'Sources and licences');
   const bounds=await button.boundingBox(), footer=await area.locator('.akb-sources').boundingBox();
   assert.ok(Math.abs(bounds.x+bounds.width-footer.x-footer.width)<1,'Sources must align right');
   assert.ok(bounds.width>=(touch?44:28) && bounds.height>=(touch?44:28),'Sources touch target');
   const last=await area.locator('.akb-card').last().boundingBox(), rootBox=await area.boundingBox();
   assert.ok(bounds.y-last.y-last.height>=5 && bounds.y-last.y-last.height<=7,'Compact breathing room');
   assert.ok(rootBox.y+rootBox.height-bounds.y-bounds.height<=6,'Compact bottom inset');
   const main=area.locator('.akb-main-toggle').first(), before=await main.getAttribute('aria-expanded');
   assert.equal(await button.getAttribute('aria-expanded'),'false');
   if(touch) await button.tap(); else {await button.focus();await surface.keyboard.press('Enter');}
   const panel=area.locator('.akb-sources-panel');
   assert.equal(await panel.isVisible(),true);
   assert.match(await panel.innerText(),/Electronic Dictionary Research and Development Group/);
   assert.match(await panel.innerText(),/Ulrich Apel and contributors/);
   assert.match(await panel.innerText(),/Nik Dhanda/);
   assert.deepEqual(await panel.locator('.akb-source-heading').allTextContents(),
    ['Kanji data','Structure data','Auto Kanji Breakdown','This breakdown']);
   assert.match(await panel.innerText(),/Software licence: AGPL-3.0-or-later/);
   assert.match(await panel.innerText(),/Combined adapted database: CC BY-SA 4.0/);
   assert.equal(await panel.getByRole('link',{name:'Project on GitHub'}).getAttribute('href'),
    'https://github.com/NikhilDhanda/Auto-Kanji-Breakdown');
   assert.match(await panel.innerText(),/KANJIDIC2 snapshot: 2026-09-10/);
   assert.ok((await panel.locator('a').evaluateAll(a=>a.map(e=>e.href))).every(url=>url.startsWith('https://')));
   assert.equal(await main.getAttribute('aria-expanded'),before);
   await checkOpenSources(surface,area);
   if(touch) await button.tap(); else {await button.focus();await surface.keyboard.press('Space');}
   assert.equal(await panel.isVisible(),false);
  }
  await checkSources(page);
  const roots=page.locator('.akb-root'), samples=roots.nth(0), cards=samples.locator('.akb-card');
  assert.deepEqual(await cards.locator('.akb-main-char').allTextContents(), Array.from('階建語人水𠮟㐆鬱'));
  for (const toggle of await page.locator('.akb-main-toggle').all()) assert.equal(await toggle.getAttribute('aria-expanded'),'false');
  assert.equal(await cards.nth(0).locator(':scope > .akb-tree').isVisible(),false);
  assert.equal(await cards.nth(0).evaluate(e=>getComputedStyle(e).cursor),'pointer');
  assert.notEqual(await cards.nth(3).evaluate(e=>getComputedStyle(e).cursor),'pointer');
  const main=cards.nth(0).locator('.akb-main-toggle');
  const beforeHover=await cards.nth(0).evaluate(e=>getComputedStyle(e).backgroundColor);
  await cards.nth(0).hover(); await page.waitForTimeout(160);
  const hover=await cards.nth(0).evaluate(e=>getComputedStyle(e).backgroundColor);
  assert.notEqual(hover,beforeHover);
  await page.mouse.down(); await page.waitForTimeout(160);
  assert.notEqual(await cards.nth(0).evaluate(e=>getComputedStyle(e).backgroundColor),hover);
  await page.mouse.up();
  // Reset incidental click, then exercise whole-card, Enter and Space independently.
  await page.evaluate(()=>document.querySelectorAll('.akb-main-toggle[aria-expanded="true"]').forEach(b=>b.click()));
  await cards.nth(0).locator('.akb-main-char').click(); assert.equal(await main.getAttribute('aria-expanded'),'true');
  await cards.nth(0).locator('.akb-main-char').click(); assert.equal(await main.getAttribute('aria-expanded'),'false');
  await main.focus(); await page.keyboard.press('Enter'); assert.equal(await main.getAttribute('aria-expanded'),'true');
  await page.keyboard.press('Space'); assert.equal(await main.getAttribute('aria-expanded'),'false');
  await page.keyboard.press('Enter');
  assert.equal(await cards.nth(0).locator('.akb-component-char').first().textContent(),'⻖');
  assert.match(await cards.nth(0).innerText(),/hill/);
  await cards.nth(1).locator('.akb-main-toggle').click();
  assert.match(await cards.nth(1).innerText(),/brush/); assert.match(await cards.nth(1).innerText(),/long stride; stretching/);
  for (const i of [3,4,6]) assert.equal(await cards.nth(i).locator('.akb-main-toggle').count(),0);
  assert.equal(await cards.nth(6).locator('.akb-meta-chip').count(),1);
  assert.equal(await cards.nth(3).locator('[aria-label="Radical"]').count(),1);
  assert.equal(await cards.nth(3).locator('.akb-heading').evaluate(e=>e.classList.contains('akb-radical')),true);
  assert.match(await cards.nth(0).locator('.akb-meta').innerText(),/Freq #/);
  assert.equal(await cards.nth(0).locator('[title="Frequency rank"]').count(),1);
  const nested=cards.nth(0).locator('.akb-component-row button').first();
  await nested.focus(); await page.keyboard.press('Enter');
  assert.equal(await nested.getAttribute('aria-expanded'),'true'); assert.equal(await main.getAttribute('aria-expanded'),'true');
  await nested.click(); assert.equal(await nested.getAttribute('aria-expanded'),'false'); assert.equal(await main.getAttribute('aria-expanded'),'true');
  assert.equal(await nested.evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
  const long=roots.nth(3), life=long.locator('.akb-card').nth(0), breath=long.locator('.akb-card').nth(1);
  const readings=life.locator('.akb-kun .akb-more');
  assert.match(await readings.textContent(),/^\+\d+$/);
  const shortReading=await life.locator('.akb-kun .akb-list-text').textContent();
  await readings.click(); assert.equal(await readings.getAttribute('aria-expanded'),'true');
  assert.ok((await life.locator('.akb-kun .akb-list-text').textContent()).length>shortReading.length);
  assert.equal(await life.locator('.akb-main-toggle').count(),0);
  await readings.click(); assert.equal(await life.locator('.akb-kun .akb-list-text').textContent(),shortReading);
  assert.equal(await cards.nth(3).locator('.akb-reading .akb-more').count(),0);
  const meanings=breath.locator('.akb-main-meaning .akb-more');
  const shortMeaning=await breath.locator('.akb-main-meaning .akb-list-text').textContent();
  await meanings.click(); assert.ok((await breath.locator('.akb-main-meaning .akb-list-text').textContent()).length>shortMeaning.length);
  assert.equal(await breath.locator('.akb-main-toggle').getAttribute('aria-expanded'),'false');
  await meanings.click();
  // Selecting text and interacting with an unrelated child link must not toggle the card.
  await cards.nth(0).evaluate(card=>{
   const sel=getSelection(), range=document.createRange(); sel.removeAllRanges(); range.selectNodeContents(card.querySelector('.akb-main-meaning')); sel.addRange(range);
   card.dispatchEvent(new MouseEvent('click',{bubbles:true})); sel.removeAllRanges();
   const link=document.createElement('a'); link.textContent='test'; link.href='#'; link.addEventListener('click',e=>e.preventDefault());card.append(link);link.click();link.remove();
  });
  assert.equal(await main.getAttribute('aria-expanded'),'true');
  const inspection=roots.nth(2);
  assert.deepEqual(await inspection.locator('.akb-main-char').allTextContents(),Array.from('麗麻薬常習学校娘息蹴磨風邪'));
  const palettes=[];
  for (const theme of ['light','dark','classic','brown','matcha','matcha-dark','sakura-light','sakura']) {
   await page.setViewportSize({width:820,height:1000});
   await page.evaluate(theme=>{
    document.querySelectorAll('.akb-root').forEach(r=>r.setAttribute('data-akb-theme',theme));
    document.querySelectorAll('.akb-toggle[aria-expanded="true"]').forEach(b=>b.click());
   },theme);
   await page.waitForTimeout(160); // Let palette transitions settle before screenshots.
   palettes.push(await samples.evaluate(e=>getComputedStyle(e).backgroundColor));
   const contrasts=await samples.evaluate(root=>{
    const style=getComputedStyle(root);
    function luminance(name) {
     const hex=style.getPropertyValue(name).trim().slice(1);
     const rgb=[0,2,4].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4));
     return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;
    }
    return [['--akb-accent','--akb-bg'],['--akb-text','--akb-card'],['--akb-gloss','--akb-card'],['--akb-secondary','--akb-chip'],
            ['--akb-text','--akb-on-bg'],['--akb-text','--akb-kun-bg'],['--akb-green','--akb-card']].map(pair=>{
      const a=luminance(pair[0]),b=luminance(pair[1]);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
    });
   });
   assert.ok(contrasts.every(ratio=>ratio>=4.5),theme+' text contrast '+contrasts.join(','));
   await samples.locator('.akb-sources-toggle').click();
   assert.equal(await samples.locator('.akb-sources-panel').isVisible(),true);
   await checkOpenSources(page,samples);
   await samples.locator('.akb-sources-panel').screenshot({path:path.join(output,theme+'-sources.png')});
   await samples.locator('.akb-sources-toggle').click();
   await inspection.screenshot({path:path.join(output,theme+'-collapsed.png')});
   await page.evaluate(()=>document.querySelectorAll('.akb-toggle[aria-expanded="false"]').forEach(b=>b.click()));
   await inspection.screenshot({path:path.join(output,theme+'-expanded.png')});
   if(theme==='classic') {
    for(const card of await inspection.locator('.akb-card').all()) {
     const char=await card.locator('.akb-main-char').textContent();
     await card.screenshot({path:path.join(output,'detail-'+char+'.png')});
    }
    await samples.screenshot({path:path.join(output,'radicals-and-dictionary-only.png')});
    await roots.nth(1).screenshot({path:path.join(output,'sentence.png')});
    await long.screenshot({path:path.join(output,'long-lists-compact.png')});
    await long.locator('.akb-more').evaluateAll(bs=>bs.forEach(b=>{if(b.getAttribute('aria-expanded')==='false')b.click();}));
    await long.screenshot({path:path.join(output,'long-lists-full.png')});
   }
   for(const width of [360,390,430]) {
    await page.setViewportSize({width,height:844});
    await samples.locator('.akb-sources-toggle').click();
    await checkOpenSources(page,samples);
    if(width===390) await samples.screenshot({path:path.join(output,theme+'-sources-mobile.png')});
    await samples.locator('.akb-sources-toggle').click();
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),theme+' overflow '+width);
   }
   await page.setViewportSize({width:390,height:844});
   await inspection.screenshot({path:path.join(output,theme+'-phone.png')});
   await inspection.locator('.akb-card').nth(9).screenshot({path:path.join(output,theme+'-phone-deep.png')});
  }
  assert.equal(new Set(palettes).size,8);
  await page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await main.locator('.akb-chevron').evaluate(e=>getComputedStyle(e).transitionDuration),'0s');
  await page.evaluate(()=>{
   const api=window.AutoKanjiBreakdown,host=document.createElement('div');host.className='akb-root';document.body.appendChild(host);
   api.render(host,api.parse(JSON.stringify({version:1,entries:[{char:'人',meanings:['</script><img src=x onerror="window.pwned=true">'],children:[{char:'⻖',base:'阜',meanings:['hill'],radical:'nelson',via:[{position:'right'}]}]}]})));
   if(host.querySelector('img,script')||window.pwned)throw Error('HTML injection');
   if(host.querySelector('.akb-radical'))throw Error('Wrong radical convention');
   if(host.querySelector('.akb-position').textContent!=='right')throw Error('via');
   if(host.querySelector('.akb-component-char').textContent!=='⻖')throw Error('variant');
   if(!host.querySelector('.akb-sources-panel').textContent.includes('snapshot details unavailable'))throw Error('Legacy provenance fabricated');
   ['', '{','{"version":2,"entries":[]}','{"version":1,"entries":[]}'].forEach(s=>{api.render(host,api.parse(s));if(host.childNodes.length)throw Error('Invalid/empty payload rendered');});
   host.innerHTML='<div class="akb-root" data-akb-owner="test"><script class="akb-data" type="application/json">{"version":1,"entries":[{"char":"水"}]}</script></div>'.repeat(2);
   api.mountAll(document);api.mountAll(document);
   if(host.querySelectorAll('.akb-root').length!==1||host.querySelectorAll('.akb-card').length!==1)throw Error('duplicate mounting');
   host.remove();
  });
  // Actual coarse-pointer context exercises touch rather than emulated mouse click.
  const touch=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
  const phone=await touch.newPage();
  phone.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
  await phone.goto(pathToFileURL(path.resolve(fixture)).href);
  await checkReadingHeights(phone);
  await checkBranchAlignment(phone);
  await checkSources(phone,true);
  const phoneCard=phone.locator('.akb-card').first();await phoneCard.locator('.akb-main-char').tap();
  assert.equal(await phoneCard.locator('.akb-main-toggle').getAttribute('aria-expanded'),'true');
  const phoneNested=phoneCard.locator('.akb-component-row button').first();
  const target=await phoneNested.boundingBox();assert.ok(target.width>=44&&target.height>=44);
  await phoneNested.tap();assert.equal(await phoneNested.getAttribute('aria-expanded'),'true');
  assert.equal(await phoneCard.locator('.akb-main-toggle').getAttribute('aria-expanded'),'true');
  assert.ok(await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await touch.close();
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
  console.log('Browser suite passed: collapsed/whole-card/keyboard/touch/nested, compact/full lists, eight themes, 360–430px, security, ownership mounting, no network.');
  console.log('Screenshots: '+path.resolve(output));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

