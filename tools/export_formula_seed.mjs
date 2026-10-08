// Mechanical export: preserve the current reference and its original document rows.
import {writeFileSync} from 'node:fs';
import {defaultFormulaConfiguration} from '../web/dist/formula-reference.js';
writeFileSync(new URL('../src/qd766/backend/formula_seed.json',import.meta.url),JSON.stringify(defaultFormulaConfiguration(),null,2)+'\n','utf8');
