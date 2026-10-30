import { beforeEach, describe, expect, it, vi } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

let loaded
const ASSETS=resolve(dirname(fileURLToPath(import.meta.url)),'../../../backend/traffic_api/candidate_static')
async function api() {
  const file = resolve(ASSETS,'viewer.mjs')
  expect(existsSync(file), 'isolated viewer module must exist').toBe(true)
  // Read the actual standalone module; missing source is a test failure, not collection failure.
  loaded ??= import(/* @vite-ignore */ `data:text/javascript;base64,${Buffer.from(readFileSync(file)).toString('base64')}`)
  return loaded
}
const stamp = i => `2026-01-01T00:${String(i).padStart(2,'0')}:00.000000`
const proof = {run:'NOT_PROVIDED',inputs:'NOT_PROVIDED',combined:'NOT_PROVIDED'}
const common = {schema_version:1,evidence_kind:'SYNTHETIC_ONLY',policy_status:'AUDIT_ONLY',time_basis:'synthetic_source_clock',selected_policy:'P_U'}
function catalog(ids=['saved-if','saved-history']) {
  return {schema_version:1,evidence_kind:'SYNTHETIC_ONLY',policy_status:'AUDIT_ONLY',scope:'SYNTHETIC_SAVED_RUN_INSPECTION_ONLY',
    items:ids.map(run_id=>({run_id,model_profile_id:'candidate-test',method:'iforest',history_window:null,
      selected_policy:'P_U',minute_count:3,score_valid_count:1,source_replay:{...proof}}))}
}
function series(id='saved-if',page=1,page_size=100,start=null,end=null) {
  const normalized=value=>value===null?null:value.slice(0,16)+':00.000000'
  const value={...common,run_id:id,source_replay:'NOT_PROVIDED',range:{start:normalized(start),end:normalized(end)},page,page_size,total:3,returned:3,
    items:[0,1,2].map(i=>({source_index:i,timestamp:stamp(i),segment_id:'s',partition:'test',current_input_valid:true,
      valid:i===2,score:i===2?0:null,alarm:i===2?false:null,threshold:.5,
      history_invalid_reason:{'15':i===0?'warmup':null,'30':i<2?'warmup':null},break_before:i===0})),
    evaluation_reference:{scope:'FULL_STORED_RUN',run_id:id,artifact:{sha256:'a'.repeat(64),byte_count:300}}}
  value.items=value.items.filter(row=>(!value.range.start||row.timestamp>=value.range.start)&&(!value.range.end||row.timestamp<value.range.end))
  value.total=value.items.length;value.items=value.items.slice((page-1)*page_size,page*page_size);value.returned=value.items.length
  return value
}
function detail(id='saved-if',timestamp=stamp(1)) {
  const valid=timestamp===stamp(2)
  return {...common,run_id:id,source_replay:{...proof},feature_names:Array.from({length:13},(_,i)=>'feature_'+i),
    point:{timestamp,segment_id:'s',partition:'test',valid,score:valid?0:null,alarm:valid?false:null,threshold:.5},
    inputs:{raw:{valid:true,values:Array(13).fill(1)},prepared:{valid:true,values:Array(13).fill(0)}},
    histories:{'15':{valid:true,invalid_reason:null,residual:Array(13).fill(0)},
      '30':{valid,invalid_reason:valid?null:'warmup',residual:Array(13).fill(valid?0:null)}},
    labels:{policies:{P_U:'unknown',P_B:'normal',P_A:'attack'},source_attack_label_present:true},
    reconstruction:{current:{status:'NOT_APPLICABLE',value:null},history_deviation:{status:'NOT_APPLICABLE',value:null},
      per_feature:{status:'NOT_STORED',values:null}}}
}
const ok=value=>({ok:true,status:200,json:async()=>value})
const bad=code=>({ok:false,status:422,json:async()=>({error:code,private:'secret'})})
async function tick(){for(let i=0;i<18;i++)await Promise.resolve()}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}}
function automatic(url){const parsed=new URL(url,'http://local');const ids=parsed.pathname.split('/');const id=decodeURIComponent(ids[4]||'')
  if(parsed.pathname==='/candidate/v1/runs')return ok(catalog())
  if(parsed.pathname.endsWith('/detail'))return ok(detail(id,parsed.searchParams.get('timestamp')))
  return ok(series(id,Number(parsed.searchParams.get('page')||1),Number(parsed.searchParams.get('page_size')||100),
    parsed.searchParams.get('start'),parsed.searchParams.get('end')))}
async function mount(fetcher=vi.fn(async url=>automatic(url))){const module=await api();const root=document.createElement('main');document.body.append(root)
  const handle=module.mountViewer(root,{fetcher});await tick();return{root,handle,fetcher}}
function el(id){return document.getElementById(id)}
async function select(id='saved-if'){el('run-select').value=id;el('run-select').dispatchEvent(new Event('change'));await tick()}
function click(id){el(id).click()}
async function minute(index=1){document.querySelectorAll('button[data-timestamp]')[index].click();await tick()}
beforeEach(()=>{document.body.replaceChildren()})

describe('candidate static viewer',()=>{
  it('has fixed same-origin asset URLs and evidence text',async()=>{await api();const html=readFileSync(resolve(ASSETS,'index.html'),'utf8')
    expect(html).toContain('/candidate/viewer.mjs');expect(html).toContain('/candidate/viewer.css');expect(html).not.toMatch(/https?:\/\/|cdn/i)
    const {root}=await mount();expect(root.textContent).toContain('SYNTHETIC_ONLY');expect(root.textContent).toContain('AUDIT_ONLY');expect(root.textContent).toContain('synthetic_source_clock')})
  it('selects catalog IDs and preserves all rows, null, zero and false',async()=>{const {fetcher}=await mount();await select('saved-history')
    expect(fetcher.mock.calls[1][0]).toContain('/saved-history/series');expect(el('minute-rows').children).toHaveLength(3)
    expect(el('minute-rows').textContent).toContain('未评分');expect(el('minute-rows').textContent).toContain('未报警');expect(el('minute-rows').textContent).not.toContain('正常候选')
    expect(el('saved-threshold').textContent).toContain('0.5');expect(el('source-proof').textContent).toContain('NOT_PROVIDED')})
  it('keeps 13 channels and partial H15 independent of unscored H30',async()=>{await mount();await select();await minute(1)
    expect(el('feature-rows').children).toHaveLength(13);expect(el('feature-rows').children[0].textContent).toContain('feature_0')
    expect([...el('feature-rows').children[0].children].map(x=>x.textContent)).toEqual(['feature_0','1','0','0','未提供'])
    expect(el('minute-detail').textContent).toContain('NOT_STORED');expect(el('minute-detail').textContent).toContain('NOT_APPLICABLE');expect(el('minute-detail').textContent).toContain('P_U: unknown')})
  it('distinguishes applicable missing scalar from not applicable',async()=>{await mount(async url=>{
    if(url.includes('/detail')){const value=detail();value.reconstruction.current={status:'APPLICABLE',value:null};value.reconstruction.history_deviation={status:'APPLICABLE',value:0};return ok(value)}return automatic(url)})
    await select();await minute();expect(el('reconstruction').textContent).toContain('APPLICABLE · 未提供');expect(el('reconstruction').textContent).toContain('APPLICABLE · 0')})
  it('uses text nodes for server feature text',async()=>{await mount(async url=>{if(url.includes('/detail')){const value=detail();value.feature_names[0]='<img src=x onerror=alert(1)>';return ok(value)}return automatic(url)})
    await select();await minute();expect(el('feature-rows').textContent).toContain('<img');expect(el('feature-rows').querySelector('img')).toBeNull()})
  it('separates draft range from applied paging and resets on apply',async()=>{const {fetcher}=await mount();await select();const old=el('series-summary').textContent
    el('range-start').value='2026-01-01T00:01';expect(el('series-summary').textContent).toBe(old)
    el('page-size').value='1';el('range-form').dispatchEvent(new Event('submit',{cancelable:true}));await tick()
    const last=fetcher.mock.calls.at(-1)[0];expect(last).toContain('page=1');expect(last).toContain('start=2026-01-01T00%3A01');expect(last).toContain('page_size=1')
    el('range-start').value='2026-01-01T00:02';click('next-page');await tick();expect(fetcher.mock.calls.at(-1)[0]).toContain('start=2026-01-01T00%3A01')})
  it('clears old threshold and detail on an empty page but keeps full evaluation identity',async()=>{let empty=false;await mount(async url=>{if(empty&&url.includes('/series')){const value=series();value.items=[];value.returned=0;value.total=0;return ok(value)}return automatic(url)})
    await select();await minute();empty=true;el('range-form').dispatchEvent(new Event('submit',{cancelable:true}));await tick()
    expect(el('minute-rows').children).toHaveLength(0);expect(el('score-chart').children).toHaveLength(0);expect(el('saved-threshold').textContent).not.toContain('0.5')
    expect(el('minute-detail').textContent).toContain('选择分钟');expect(el('evaluation-reference').textContent).toContain('FULL_STORED_RUN')})
  it.each(['catalog','series','detail'])('shows safe %s error without private response body',async phase=>{await mount(async url=>{
    if(phase==='catalog'&&url.endsWith('/runs')||phase==='series'&&url.includes('/series')||phase==='detail'&&url.includes('/detail'))return bad('private-exception')
    return automatic(url)})
    if(phase!=='catalog')await select();if(phase==='detail')await minute();expect(document.body.textContent).toContain('读取失败');expect(document.body.textContent).not.toContain('private-exception')})
  it.each(['run_id','evidence_kind','time_basis'])('rejects incompatible series %s',async field=>{await mount(async url=>{if(url.includes('/series'))return ok({...series(),[field]:'private-wrong'});return automatic(url)})
    await select();expect(el('series-error').textContent).toContain('结果格式不匹配');expect(el('minute-rows').children).toHaveLength(0)})
  it('rejects mismatched detail timestamp and invalid finite/null vectors',async()=>{await mount(async url=>url.includes('/detail')?ok(detail('saved-if',stamp(2))):automatic(url));await select();await minute(1)
    expect(el('detail-error').textContent).toContain('结果格式不匹配')})
  it('handles a current AbortError as a failure instead of hiding it',async()=>{await mount(async url=>{if(url.includes('/series'))throw new DOMException('private','AbortError');return automatic(url)})
    await select();expect(el('series-error').textContent).toContain('读取失败')})
  it('clears previous run values immediately during a new request',async()=>{const pending=deferred();await mount(async url=>url.includes('saved-history/series')?pending.promise:automatic(url))
    await select();await minute();await select('saved-history');expect(el('minute-rows').children).toHaveLength(0);expect(el('minute-detail').textContent).toContain('选择分钟');expect(el('series-status').textContent).toContain('读取中')})
  it.each(['success','failure'])('discards old series %s and finally while newer load is pending',async outcome=>{const a=deferred(),b=deferred();await mount(async url=>url.includes('/series')?(url.includes('saved-history')?b.promise:a.promise):automatic(url))
    await select();await select('saved-history');outcome==='success'?a.resolve(ok(series())):a.reject(Error('private-old'));await tick()
    expect(el('series-status').textContent).toContain('读取中');expect(el('series-error').textContent).toBe('');expect(el('minute-rows').children).toHaveLength(0)
    b.resolve(ok(series('saved-history')));await tick();expect(el('series-summary').textContent).toContain('saved-history')})
  it.each(['success','failure'])('discards old detail %s after another minute selection',async outcome=>{const a=deferred(),b=deferred();await mount(async url=>url.includes('/detail')?(url.includes('00%3A01')?a.promise:b.promise):automatic(url))
    await select();await minute(1);await minute(2);outcome==='success'?a.resolve(ok(detail())):a.reject(Error('private-old'));await tick()
    expect(el('detail-status').textContent).toContain('读取中');expect(el('detail-error').textContent).toBe('')
    b.resolve(ok(detail('saved-if',stamp(2))));await tick();expect(el('minute-detail').textContent).toContain(stamp(2))})
  it('invalidates a pending detail on range changes',async()=>{const d=deferred();await mount(async url=>url.includes('/detail')?d.promise:automatic(url));await select();await minute()
    el('range-form').dispatchEvent(new Event('submit',{cancelable:true}));await tick();d.resolve(ok(detail()));await tick();expect(el('minute-detail').textContent).toContain('选择分钟')})
  it.each(['success','failure'])('catalog retries discard late %s',async outcome=>{const a=deferred(),b=deferred();let count=0;const {handle}=await mount(()=>++count===1?a.promise:b.promise)
    const second=handle.reloadCatalog();outcome==='success'?a.resolve(ok(catalog(['old-run']))):a.reject(Error('private-old'));await tick()
    expect(el('catalog-status').textContent).toContain('读取中');b.resolve(ok(catalog(['new-run'])));await second
    expect([...el('run-select').options].map(o=>o.value)).toEqual(['','new-run']);expect(el('catalog-error').textContent).toBe('')})
  it('dispose aborts and ignores later responses',async()=>{const d=deferred();const {root,handle}=await mount(()=>d.promise);handle.dispose();d.resolve(ok(catalog()));await tick();expect(root.children).toHaveLength(0)})
  it('draws all returned finite points with null and explicit breaks',async()=>{const {chartGeometry}=await api();const rows=series().items
    rows.push({...rows[2],source_index:3,score:.2,break_before:true});const geometry=chartGeometry(rows)
    expect(geometry.scorePaths).toHaveLength(2);expect(geometry.points).toHaveLength(2);expect(geometry.thresholdPaths).toHaveLength(2)
    expect(JSON.stringify(geometry)).not.toMatch(/NaN|Infinity/);expect(chartGeometry([]).points).toEqual([])})
  it('single-point threshold segments have independent visible markers',async()=>{const {chartGeometry}=await api();const row={...series().items[2],break_before:true}
    for(const rows of [[row],[row,{...row,source_index:3,timestamp:stamp(3)}]]){
      const geometry=chartGeometry(rows);expect(geometry.thresholdPoints).toHaveLength(rows.length)
      expect(geometry.thresholdPaths).toHaveLength(rows.length)
      expect(geometry.thresholdPoints.every(point=>Number.isFinite(point.x)&&Number.isFinite(point.y))).toBe(true)
    }})
  it('single-point threshold is rendered as a visible hollow SVG marker',async()=>{await mount();await select()
    el('range-start').value='2026-01-01T00:02';el('page-size').value='1';el('range-form').dispatchEvent(new Event('submit',{cancelable:true}));await tick()
    const markers=el('score-chart').querySelectorAll('circle.threshold-point');expect(markers).toHaveLength(1)
    expect(Number(markers[0].getAttribute('r'))).toBeGreaterThan(0);expect(el('chart-scale').textContent).toContain('空心点')})
  it.each([0,1,-1,1e308])('handles single/constant chart values %s with finite geometry',async value=>{const {chartGeometry}=await api();const row={...series().items[2],score:value,threshold:value,break_before:false}
    for(const rows of [[row],[row,row]])expect(JSON.stringify(chartGeometry(rows))).not.toMatch(/NaN|Infinity/)})
})
