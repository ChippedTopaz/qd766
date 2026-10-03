import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
const base=new URL("../../netlify-public/",import.meta.url);
async function list(url,prefix=""){
  let result=[];
  for(const entry of await readdir(url,{withFileTypes:true})){
    assert.equal(entry.isSymbolicLink(),false);
    const name=prefix+entry.name;
    if(entry.isDirectory())result.push(...await list(new URL(entry.name+"/",url),name+"/"));
    else result.push(name);
  }
  return result;
}
const files=await list(base);
assert(files.includes("index.html"));
assert(files.includes("dist/app.js"));
assert(files.includes("dist/login-url.js"));
assert(files.includes("bento.css"));
assert(files.includes("collection.css"));
assert(files.includes("admin.html"));
assert(files.includes("admin.css"));
assert(files.includes("dist/admin.js"));
assert(files.includes("dist/bento.js"));
assert(files.includes("vendor/exceljs/exceljs.min.js"));
assert(files.every(name=>["index.html","styles.css","bento.css","collection.css","admin.html","admin.css"].includes(name)||/^dist\/.*\.js$/.test(name)||/^vendor\/.*(\.(js|css)|LICENSE[^/]*)$/.test(name)));
assert(files.every(name=>!name.endsWith(".map")&&!name.includes("snapshots")&&!name.includes(".env")));
assert.match(await readFile(new URL("index.html",base),"utf8"),/qd766-deployment" content="public/);
const app=await readFile(new URL("dist/app.js",base),"utf8");
assert.match(app,/productionSite && policy.publicReadOnly !== true/);
assert.match(app,/publicReadOnly \|\| productionSite/);
console.log("NETLIFY_TEST_OK: asset allowlist, production guard, no fixtures/secrets/maps");
