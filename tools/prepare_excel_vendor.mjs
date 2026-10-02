import { mkdir, copyFile } from "node:fs/promises";
const target = new URL("../web/vendor/exceljs/",import.meta.url);
await mkdir(target,{recursive:true});
await copyFile(new URL("../node_modules/exceljs/dist/exceljs.min.js",import.meta.url),new URL("exceljs.min.js",target));
await copyFile(new URL("../node_modules/exceljs/LICENSE",import.meta.url),new URL("LICENSE",target));
