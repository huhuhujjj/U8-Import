import fs from 'node:fs';import ts from 'typescript';import assert from 'node:assert/strict';
fs.mkdirSync('.test-build',{recursive:true});
fs.writeFileSync('.test-build/parser.js',ts.transpileModule(fs.readFileSync('src/u8/parser.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText);
const {autoMapping,rowsFromSheet}=await import('../.test-build/parser.js');
const mapping=autoMapping(['数量','备注','单价','物料编码']);
assert.deepEqual(mapping,{inventory_code:'D',quantity:'A',price:'C'});
assert.deepEqual(autoMapping(['物料编码','数量','单价（元）','含税金额（元）']),{inventory_code:'A',quantity:'B',price:'C'});
const rows=rowsFromSheet({name:'Sheet1',rows:[['数量','备注','单价','物料编码'],['2','','3.50','001'],[],['4','','5','002']]},0,mapping);
assert.equal(rows.length,2);assert.equal(rows[1].source_row,4);assert.equal(rows[0].normalized_data.inventory_code,'001');
console.log('Parser mapping and row identity tests passed');
const {parseFile,detectHeader,rowErrors}=await import('../.test-build/parser.js');
const XLSX=await import('xlsx');
for(const n of [10,100,300]){
 const raw=XLSX.read(fs.readFileSync(`../test-data/test_${n}.xlsx`));
 fs.writeFileSync(`../test-data/test_${n}.xls`,XLSX.write(raw,{type:'buffer',bookType:'biff8'}));
 for(const ext of ['xlsx','xls','csv','tsv']){
  const name=`test_${n}.${ext}`,start=performance.now();
  const sheets=await parseFile(new File([fs.readFileSync(`../test-data/${name}`)],name));
  const h=detectHeader(sheets[0]);const map=autoMapping(sheets[0].rows[h]);const records=rowsFromSheet(sheets[0],h,map);
  assert.equal(records.length,n);assert.equal(rowErrors(records).filter(e=>e.length).length,0);
  assert.deepEqual(map,{inventory_code:'F',quantity:'I',price:'J'});
  if(ext==='xlsx')fs.writeFileSync(`../test-data/payload_${n}.json`,JSON.stringify({file_name:name,mapping:map,rows:records,parse_ms:performance.now()-start}));
 }
}
const multi=XLSX.utils.book_new();XLSX.utils.book_append_sheet(multi,XLSX.utils.aoa_to_sheet([['说明'],['料号','Qty','Price'],['001','2','5']]),'第二行表头');XLSX.utils.book_append_sheet(multi,XLSX.utils.aoa_to_sheet([['物料编码','数量','单价'],['002','3','6']]),'另一工作表');
const parsed=await parseFile(new File([XLSX.write(multi,{type:'buffer',bookType:'xlsx'})],'sheets.xlsx'));
assert.equal(parsed.length,2);assert.equal(detectHeader(parsed[0]),1);
assert.deepEqual(rowErrors([{normalized_data:{inventory_code:'A',quantity:'0',price:'x'}}])[0],['数量必须大于零','单价必须为非负数字']);
console.log('12 real file parses (XLSX/XLS/CSV/TSV × 10/100/300), sheet/header detection and validation passed');


const {isAmountHeader, priceBasis}=await import('../.test-build/parser.js');
for(const name of ['Amount','Total Amount','Grand Total','money','sum','Tax Amount','含税金额'])assert.equal(isAmountHeader(name),true);
assert.equal(isAmountHeader('Unit Price'),false);
assert.equal(priceBasis('不含税单价'),'EXCLUSIVE');
assert.equal(priceBasis('Tax Inclusive Unit Price'),'INCLUSIVE');
assert.deepEqual(autoMapping(['物料编码','数量','Unit Price']),{inventory_code:'A',quantity:'B',price:'C'});
console.log('Amount semantics and price basis tests passed');
