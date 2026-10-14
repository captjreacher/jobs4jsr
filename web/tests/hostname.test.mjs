import test from "node:test";
import assert from "node:assert/strict";
import { handle } from "../worker.mjs";

const env = { LEGACY_REDIRECT_ENABLED: "true" };
test("legacy hostname redirects safe paths and query strings without sessions", async () => {
  const r = await handle(new Request("https://jess.maximisedai.com/jobs?tab=saved", {headers:{Cookie:"access=private; refresh=private"}}),env);
  assert.equal(r.status,301);
  assert.equal(r.headers.get("Location"),"https://jess.funkmybrand.com/jobs?tab=saved#");
  assert.match(r.headers.get("Set-Cookie"),/Max-Age=0/);
  assert.doesNotMatch(r.headers.get("Location"),/private/);
});
test("legacy authentication material is removed and POST credentials never redirect", async () => {
  for (const query of ["access_token=private", "code=private&state=x", "q=eyJabc.def.ghi"]){
    const r=await handle(new Request("https://jess.maximisedai.com/?"+query),env);
    assert.equal(r.headers.get("Location"),"https://jess.funkmybrand.com/#");
  }
  const r=await handle(new Request("https://jess.maximisedai.com/api/login",{method:"POST",body:'{"password":"private"}'}),env);
  assert.equal(r.status,409);assert.equal(r.headers.get("Location"),null);
});
test("transition keeps old hostname operational and canonical hostname does not redirect", async()=>{
  const assets={fetch:async()=>new Response("live assets")};
  for(const [host,flag] of [["jess.maximisedai.com","false"],["jess.funkmybrand.com","true"]]){
    const r=await handle(new Request('https://'+host),{LEGACY_REDIRECT_ENABLED:flag,ASSETS:assets});
    assert.equal(r.status,200);assert.equal(await r.text(),"live assets");
  }
});
