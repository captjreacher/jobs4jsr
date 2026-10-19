// Run npm run preview first. Supply PLAYWRIGHT_MODULE if Playwright is bundled elsewhere.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
const browser = await chromium.launch({headless:true,channel:"msedge"});
await mkdir('tmp/catalogue-evidence',{recursive:true});
for (const width of [1280,390]) {
 const page = await browser.newPage({viewport:{width,height:900}});
 const errors=[]; page.on('pageerror', e=>errors.push(e.message));
 const now = new Date().toLocaleDateString('en-CA',{timeZone:'Pacific/Auckland'});
 const rows = [
 {id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',seen_at:null,vacancy:{location:'Auckland CBD',distance:1,job_type:'Part-time',source:'Demonstration',last_verified:now,why:'Fictional preview of customer service and teamwork matching.',employer:'Fictional New Restaurant',title:'Waiter',found:now,match:85,url:'https://example.org',vacancy_state:'open'}},
 {id:'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',saved:true,seen_at:'2026-01-01',vacancy:{location:'Auckland CBD',distance:1,job_type:'Part-time',source:'Demonstration',last_verified:now,why:'Fictional preview of customer service and teamwork matching.',employer:'Fictional Hotel',title:'Waiter',found:now,match:90,recommended:true,vacancy_state:'open'}},
 {id:'cccccccc-cccc-cccc-cccc-cccccccccccc',seen_at:'2026-01-01',vacancy:{location:'Auckland CBD',distance:1,job_type:'Part-time',source:'Demonstration',last_verified:now,why:'Fictional preview of customer service and teamwork matching.',employer:'Fictional Cafe',title:'Cafe Assistant',found:'2020-01-01',match:70,vacancy_state:'open'}}];
 await page.route('**/api/**',async route=>{
  const request=route.request();
  if(request.url().endsWith('/decision')){
   const j=rows.find(j=>j.id===request.url().split('/').at(-2));
   const action=request.postDataJSON().action;
   const map={seen:['seen_at',new Date().toISOString()],save:['saved',true],unsave:['saved',false],applied:['applied',true],dismiss:['dismissed',true],restore:['dismissed',false]};
   const [field,value]=map[action];j[field]=value;
   return route.fulfill({json:{ok:true}});
  }
  return route.fulfill({json:request.url().endsWith('/health')?{sync:[{last_successful_sync:new Date().toISOString()}],sources:[]}:rows});
 });
 await page.goto('http://127.0.0.1:8790');
 await page.locator('#board').waitFor({state:'visible'});
 assert.deepEqual(await page.locator('#jobs details').evaluateAll(ds=>ds.map(d=>d.open)),[true,true,false]);
 assert.equal(await page.locator('#jobs article').count(),3);
 for (const header of await page.locator('#jobs summary').all()) assert.ok((await header.boundingBox()).height >=44);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:`tmp/catalogue-evidence/${width}.png`,fullPage:true});
 const newHeader = page.locator('#jobs details').first().locator('summary');
 await newHeader.click();
 await newHeader.scrollIntoViewIfNeeded();
 await page.waitForTimeout(1200);
 assert.equal(rows[0].seen_at, null, 'collapsed unseen card must remain unseen');
 await newHeader.focus();
 await page.keyboard.press('Enter');
 assert.equal(await page.locator('#jobs details').first().evaluate(d=>d.open), true);
 await page.locator('#jobs details').nth(2).locator('summary').click();
 assert.equal(await page.locator('#jobs details').nth(2).evaluate(d=>d.open),true);
 await page.locator('[data-tab=saved]').click();
 assert.equal(await page.locator('#jobs article').count(),1);
 await page.locator('[data-tab=all]').click();
 assert.equal(await page.locator('#jobs details').nth(2).evaluate(d=>d.open),true);
 const card=page.locator('#jobs article').filter({hasText:'Fictional New Restaurant'});
 const seenResponse = page.waitForResponse(r=>r.url().endsWith('/decision') && r.request().postDataJSON()?.action==='seen',{timeout:10000});
 await card.scrollIntoViewIfNeeded();
 await seenResponse;
 assert.equal(await card.count(),1);
 await card.getByRole('button',{name:'Save',exact:true}).click();
 await page.locator('[data-tab=saved]').click();
 assert.equal(await page.locator('#jobs article').count(),2);
 await card.getByRole('button',{name:'Applied',exact:true}).click();
 await page.locator('[data-tab=applied]').click();
 assert.equal(await page.locator('#jobs article').count(),1);
 await card.getByRole('button',{name:'Dismiss',exact:true}).click();
 await page.locator('[data-tab=dismissed]').click();
 assert.equal(await page.locator('#jobs article').count(),1);
 await card.getByRole('button',{name:'Restore',exact:true}).click();
 await page.locator('[data-tab=all]').click();
 assert.equal(await card.count(),1);
 assert.deepEqual(errors,[]);
 console.log(`PASS ${width}px: defaults, touch targets, overflow, keyboard, collapsed unseen, toggle persistence, seen, Saved/Applied/Dismissed/Restore`);
 // A fresh visit reads the persisted seen state.
 await page.reload();
 await page.locator('#board').waitFor({state:'visible'});
 assert.equal(await page.locator('#jobs details').first().locator('article').count(),0);
 console.log(`PASS ${width}px: viewed job leaves NEW on next visit`);
 await page.close();


}
await browser.close();
