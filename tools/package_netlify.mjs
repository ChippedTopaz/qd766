import { mkdir, readdir, readFile, writeFile, copyFile } from "node:fs/promises";
import { resolve, relative, join } from "node:path";

const root=resolve(import.meta.dirname,"..");
const output=join(root,"netlify-public");
// Fresh CI checkout only: refuse old output instead of deleting arbitrary paths.
try {
  await readdir(output);
  throw new Error("netlify-public already exists. Use a fresh checkout/build directory.");
} catch(error) {
  if(error.code!=="ENOENT")throw error;
}
await mkdir(output,{recursive:true});
async function assets(source,destination,allowed){
  await mkdir(destination,{recursive:true});
  for(const item of await readdir(source,{withFileTypes:true})){
    if(item.isSymbolicLink())throw new Error("Symlink assets are not allowed");
    if(item.isDirectory())await assets(join(source,item.name),join(destination,item.name),allowed);
    else if(item.isFile()&&allowed(item.name)){
      const target=join(destination,item.name);
      await copyFile(join(source,item.name),target);
      if(item.name.endsWith(".js")){
        const content=await readFile(target,"utf8");
        await writeFile(target,content.replace(/^\/\/# sourceMappingURL=.*$/gm,""));
      }
    }
  }
}
let html=await readFile(join(root,"web/index.html"),"utf8");
html=html.replace("<head>",'<head>\n    <meta name="qd766-deployment" content="public" />');
await writeFile(join(output,"index.html"),html);
await copyFile(join(root,"web/styles.css"),join(output,"styles.css"));
await copyFile(join(root,"web/bento.css"),join(output,"bento.css"));
await assets(join(root,"web/dist"),join(output,"dist"),name=>name.endsWith(".js"));
await assets(join(root,"web/vendor"),join(output,"vendor"),name=>/\.(js|css)$/.test(name)||/^LICENSE/i.test(name));
console.log(`NETLIFY_PACKAGE_OK: ${relative(root,output)}; no fixtures, secrets or source maps`);
