import Papa from 'papaparse'
import * as XLSX from 'xlsx'
export type Mapping = Record<'inventory_code'|'quantity'|'price', string>
export type Sheet = { name:string; rows:string[][] }
export type Row = { source_row:number; line_reference:string; raw_data:Record<string,string>; normalized_data:Record<string,string> }
export const fields = ['inventory_code','quantity','price'] as const
export const labels:Record<string,string>={inventory_code:'物料编码',quantity:'数量',price:'单价'}
export const letter=(i:number)=>XLSX.utils.encode_col(i)
const normalizeHeader=(value:string)=>String(value).trim().toLowerCase().replace(/[（）()]/g,'').replace(/[\s_]/g,'')
export function isAmountHeader(value:string):boolean {
  const name=normalizeHeader(value).replace(/-/g,'')
  return /金额|合计|总额|税额|amount|total|money/.test(name)||['sum','tax'].includes(name)
}
export function priceBasis(value:string):'EXCLUSIVE'|'INCLUSIVE'|null {
  const name=normalizeHeader(value).replace(/-/g,'')
  if(/不含税|未税|无税|excludingtax|exclusivetax|taxexclusive|excltax|netamount|netprice/.test(name)||name==='money')return 'EXCLUSIVE'
  if(/含税|includingtax|inclusivetax|taxinclusive|incltax|gross|taxprice/.test(name)||name==='sum')return 'INCLUSIVE'
  return null
}
export async function parseFile(file:File):Promise<Sheet[]> {
  const ext=file.name.split('.').pop()?.toLowerCase()
  if(!['xlsx','xls','csv','tsv'].includes(ext||'')) throw new Error('请选择 XLSX、XLS、CSV 或 TSV 文件')
  if(file.size>20*1024*1024) throw new Error('文件超过20 MB，请拆分后导入')
  if(ext==='csv'||ext==='tsv') {
    const parsed=Papa.parse<string[]>(await file.text(),{delimiter:ext==='tsv'?'\t':'',skipEmptyLines:false})
    const serious=parsed.errors.filter(e=>e.code!=='UndetectableDelimiter')
    if(serious.length) throw new Error(serious.map(e=>e.message).join('；'))
    return [{name:file.name,rows:parsed.data}]
  }
  const book=XLSX.read(await file.arrayBuffer(),{type:'array',cellText:true})
  return book.SheetNames.map(name=>({name,rows:XLSX.utils.sheet_to_json<string[]>(book.Sheets[name],{header:1,raw:false,defval:'',blankrows:true})}))
}
export function autoMapping(headers:string[]):Mapping {
  const aliases:Record<string,string[]>={inventory_code:['物料编码','存货编码','料号','inventory_code','itemcode'],quantity:['数量','采购数量','quantity','qty'],price:['单价','单价(元)','含税单价','含税单价(元)','price','taxprice','unit price','不含税单价','不含税单价(元)','未税单价','Unit Price Excluding Tax','Tax Inclusive Unit Price']}
  const normalizedAliases=Object.fromEntries(Object.entries(aliases).map(([key,values])=>[key,new Set(values.map(normalizeHeader))]))
  const mapping:Mapping={inventory_code:'',quantity:'',price:''}
  for(const field of fields){
    const matches=headers.map((h,i)=>normalizedAliases[field].has(normalizeHeader(h))?i:-1).filter(i=>i>=0)
    if(matches.length===1) mapping[field]=letter(matches[0])
  }
  return mapping
}
export function detectHeader(sheet:Sheet):number {
  let index=0,score=-1
  sheet.rows.slice(0,20).forEach((row,i)=>{const count=Object.values(autoMapping(row)).filter(Boolean).length;if(count>score){score=count;index=i}})
  return index
}
export function rowsFromSheet(sheet:Sheet,header:number,mapping:Mapping):Row[] {
  return sheet.rows.slice(header+1).flatMap((cells,i)=>{
    if(!cells.some(v=>String(v).trim()))return []
    const raw_data=Object.fromEntries(cells.map((v,c)=>[letter(c),String(v)]))
    return [{source_row:header+i+2,line_reference:String(header+i+2),raw_data,normalized_data:Object.fromEntries(fields.map(f=>[f,raw_data[mapping[f]]||'']))}]
  })
}
export function rowErrors(rows:Row[]):string[][] {
  const seen=new Set<string>()
  return rows.map(row=>{
    const v=row.normalized_data;const errors:string[]=[]
    if(!v.inventory_code.trim())errors.push('物料编码为空')
    if(!v.quantity.trim()||!Number.isFinite(Number(v.quantity))||Number(v.quantity)<=0)errors.push('数量必须大于零')
    if(!v.price.trim()||!Number.isFinite(Number(v.price))||Number(v.price)<0)errors.push('单价必须为非负数字')
    const key=JSON.stringify([v.inventory_code.trim(),Number(v.quantity),Number(v.price)])
    if(seen.has(key))errors.push('文件内重复明细');seen.add(key)
    return errors
  })
}
