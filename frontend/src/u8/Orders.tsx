import {useEffect,useState} from 'react'
import {ArrowLeft, ChevronLeft, ChevronRight, RefreshCw, Search, PlugZap} from 'lucide-react'

type RecordData = Record<string, string | number | null>
type Order = Record<string, unknown> & {entry: RecordData[]}
type ImportHistory = {erp_code?: string|null; header?: Record<string, unknown>}
type Page = {items: RecordData[]; page: number; pages: number; total: number}
export async function api<T>(path:string, body?:unknown):Promise<T> {
  const response=await fetch('/api'+path, body===undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  const value=await response.json().catch(()=>({detail:'服务未响应，请检查后端'}))
  if(!response.ok) throw new Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail))
  return value
}
const text=(value:unknown)=>value===null||value===undefined||value===''?'-':String(value)
const amountFormat=new Intl.NumberFormat('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2,useGrouping:false})
const unitPriceFormat=new Intl.NumberFormat('zh-CN',{maximumFractionDigits:4,useGrouping:false})
const quantityFormat=new Intl.NumberFormat('zh-CN',{maximumFractionDigits:8,useGrouping:false})
const rateFormat=new Intl.NumberFormat('zh-CN',{maximumFractionDigits:2,useGrouping:false})
const numericFormats:Record<string,Intl.NumberFormat>={
  quantity:quantityFormat,price:unitPriceFormat,taxprice:unitPriceFormat,
  money:amountFormat,tax:amountFormat,sum:amountFormat,
  taxrate:rateFormat,currency_rate:quantityFormat,
}
function displayValue(key:string,value:unknown){
  if(key==='remark'&&typeof value==='string'){
    return text(value.replace(/\s*\[U8IMPORT:[a-f0-9]{24}\]\s*$/,'').trim())
  }
  const formatter=numericFormats[key]
  if(!formatter||value===null||value===undefined||String(value).trim()==='')return text(value)
  const number=Number(value)
  return Number.isFinite(number)?formatter.format(number):text(value)
}

export default function Orders({initialCode=''}:{initialCode?:string}){
  const [kind,setKind]=useState('orders'),[page,setPage]=useState<Page|null>(null),[detail,setDetail]=useState<Order|null>(null)
  const [code,setCode]=useState(initialCode),[name,setName]=useState(''),[begin,setBegin]=useState(''),[end,setEnd]=useState('')
  const [busy,setBusy]=useState(!!initialCode),[error,setError]=useState(''),[connection,setConnection]=useState('尚未检查')
  async function loadOrder(orderCode:string){
    const order=await api<Order>('/u8/orders/'+encodeURIComponent(orderCode))
    const history=await api<ImportHistory[]>('/imports')
    const source=history.find(item=>String(item.erp_code||'')===orderCode)?.header||{}
    return {...order,
      currency_name: order.currency_name ?? source.currency ?? '人民币',
      currency_rate: order.currency_rate ?? source.exchange_rate ?? '1',
      paycondition: order.paycondition ?? source.pay_condition,
      contractcode: order.contractcode ?? order.define1 ?? source.contract_no,
      remark: order.remark || source.remark,
    }
  }
  useEffect(()=>{
    if(!initialCode)return
    let active=true
    void loadOrder(initialCode).then(value=>{if(active)setDetail(value)}).catch(e=>{if(active)setError(String(e))}).finally(()=>{if(active)setBusy(false)})
    return()=>{active=false}
  },[initialCode])
  async function run(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn()}catch(e){setError(String(e instanceof Error?e.message:e))}finally{setBusy(false)}}
  async function load(index=1){await run(async()=>{
    const query=new URLSearchParams({page:String(index),code})
    if(kind==='orders'){query.set('vendor',name);query.set('date_begin',begin);query.set('date_end',end)}else query.set('name',name)
    setPage(await api<Page>((kind==='orders'?'/u8/orders':'/u8/master/'+kind)+'?'+query));setDetail(null)
  })}
  const columns=kind==='orders'?[['code','订单编号'],['date','订单日期'],['vendorname','供应商'],['state','状态'],['sum','价税合计']]:[['code','编码'],['name','名称'],['specs','规格型号'],['end_date','停用日期']]
  const entries=[['inventorycode','存货编码'],['inventoryname','存货名称'],['inventorystd','规格型号'],['unitname','单位'],['quantity','数量'],['price','不含税单价'],['taxprice','含税单价'],['money','金额'],['tax','税额'],['sum','价税合计'],['taxrate','税率'],['arrivedate','计划到货日期']]
  return <>
    <section className="connection-panel"><div><h2>真实 U8 · 账套 999</h2><p role="status">{connection}</p></div><button disabled={busy} onClick={()=>void run(async()=>{const c=await api<{account:string;name:string}>('/u8/connection');setConnection(`已连接 · ${c.account} · ${c.name}`)})}><PlugZap size={16}/>检查连接</button></section>
    {error&&<div role="alert" className="alert">{error}</div>}
    <div className="view-tabs" role="tablist">{[['orders','采购订单'],['vendor','供应商'],['inventory','存货']].map(([value,label])=><button role="tab" aria-selected={kind===value} className={kind===value?'selected':'secondary'} disabled={busy} key={value} onClick={()=>{setKind(value);setPage(null);setDetail(null);setCode('');setName('');setError('')}}>{label}</button>)}</div>
    {detail?<section>
      <div className="section-title"><h2>采购订单 {text(detail.code)}</h2><button className="secondary" onClick={()=>setDetail(null)}><ArrowLeft size={16}/>返回列表</button></div>
      <dl className="order-header">{[['vendorname','供应商'],['date','订单日期'],['operation_type_code','业务类型'],['purchase_type_name','采购类型'],['deptname','部门'],['personname','业务员'],['currency_name','币种'],['currency_rate','汇率'],['contractcode','合同编号'],['paycondition','付款条件'],['state','状态'],['maker','制单人'],['remark','备注']].map(([key,label])=><div key={key}><dt>{label}</dt><dd>{displayValue(key,key==='contractcode' ? (detail.contractcode ?? detail.define1) : detail[key])}</dd></div>)}</dl>
      <div className="table-wrap"><table><thead><tr><th>行号</th>{entries.map(([key,label])=><th key={key}>{label}</th>)}</tr></thead><tbody>{detail.entry.map((row,i)=><tr key={i}><td>{i+1}</td>{entries.map(([key])=><td key={key} title={numericFormats[key]?text(row[key]):undefined}>{displayValue(key,row[key])}</td>)}</tr>)}</tbody></table></div>
      <p>明细 {detail.entry.length} 条</p>
    </section>:<section>
      <form className="inline filters" onSubmit={e=>{e.preventDefault();void load()}}>
        <label>{kind==='orders'?'订单编号':'编码'}<input value={code} onChange={e=>setCode(e.target.value)} /></label>
        <label>{kind==='orders'?'供应商名称':'名称'}<input value={name} onChange={e=>setName(e.target.value)}/></label>
        {kind==='orders'&&<><label>开始日期<input type="date" value={begin} onChange={e=>setBegin(e.target.value)}/></label><label>结束日期<input type="date" min={begin} value={end} onChange={e=>setEnd(e.target.value)}/></label></>}
        <button disabled={busy}><Search size={16}/>{busy?'查询中':'查询'}</button>
      </form>
      <div className="section-title"><span>{page?`共 ${page.total} 条`:'尚未查询'}</span><button aria-label="刷新查询" title="刷新查询" className="secondary icon-button" disabled={busy} onClick={()=>void load(page?.page||1)}><RefreshCw size={16}/></button></div>
      <div className="table-wrap"><table><thead><tr>{columns.map(([key,label])=><th key={key}>{label}</th>)}{kind==='orders'&&<th>操作</th>}</tr></thead><tbody>{page?.items.map((row,i)=><tr key={i}>{columns.map(([key])=><td key={key}>{displayValue(key,row[key])}</td>)}{kind==='orders'&&<td><button className="secondary" disabled={busy} onClick={()=>void run(async()=>setDetail(await loadOrder(String(row.code))))}>查看明细</button></td>}</tr>)}</tbody></table></div>
      {page&&!page.items.length&&<p className="empty">没有符合条件的数据</p>}
      {page&&<div className="pagination"><button title="上一页" aria-label="上一页" className="secondary icon-button" disabled={busy||page.page<=1} onClick={()=>void load(page.page-1)}><ChevronLeft size={16}/></button><span>{page.page} / {Math.max(1,page.pages)}</span><button title="下一页" aria-label="下一页" className="secondary icon-button" disabled={busy||page.page>=page.pages} onClick={()=>void load(page.page+1)}><ChevronRight size={16}/></button></div>}
    </section>}
  </>
}
