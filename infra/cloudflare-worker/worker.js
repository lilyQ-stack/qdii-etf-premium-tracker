/* Direct Cloudflare Worker capture: Tencent same-snapshot reference candidates.
   NOT exchange-certified IOPV, no investment ratings. */
const SYMBOLS={"513650":"sh513650","513870":"sh513870","159612":"sz159612","159696":"sz159696"};
const ROOT="https://api.github.com/repos/lilyQ-stack/qdii-etf-premium-tracker/contents/";
const PREFIX="data/cloudflare_reference_candidates/";
const fmt=new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit",weekday:"short",hourCycle:"h23"});
function parts(date){const p=Object.fromEntries(fmt.formatToParts(date).map(x=>[x.type,x.value]));p.ymd=p.year+p.month+p.day;p.date=p.year+"-"+p.month+"-"+p.day;return p;}
function sourceDate(stamp){
  if(!/^\d{14}$/.test(stamp)) throw Error("bad source timestamp");
  const y=+stamp.slice(0,4),m=+stamp.slice(4,6),d=+stamp.slice(6,8),h=+stamp.slice(8,10),mi=+stamp.slice(10,12),s=+stamp.slice(12,14);
  const t=new Date(Date.UTC(y,m-1,d,h-8,mi,s));const p=parts(t);
  if(p.ymd!==stamp.slice(0,8)||p.hour!==stamp.slice(8,10)||p.minute!==stamp.slice(10,12)||p.second!==stamp.slice(12,14)) throw Error("invalid date");
  return t;
}
function num(value,label){const x=Number(value);if(value===""||!Number.isFinite(x))throw Error("non_numeric_"+label);return x;}
function parseQuote(text,now){
 const p=parts(now),out={},errors={};
 for(const [code,sym] of Object.entries(SYMBOLS)){
  try{
   const m=text.match(new RegExp('(?:^|[;\\n])\\s*v_'+sym+'\\s*=\\s*"([^"]*)"'));
   if(!m)throw Error("missing quote");
   const f=m[1].split("~");
   if(f.length<83||f[2]!==code||!f[1])throw Error("wrong fund identity");
   const st=sourceDate(f[30]),sp=parts(st),lag=(now.getTime()-st.getTime())/1000;
   if(sp.ymd!==p.ymd||sp.hour!=="14"||+sp.minute>35||lag< -15||lag>180)throw Error("stale or wrong session");
   const price=num(f[3],"price"),ref=num(f[78],"reference"),premium=num(f[77],"premium");
   const nav=f[81] ? num(f[81],"historic_nav"):null;
   if(price<=0.1||price>=100||ref<=0.1||ref>=100)throw Error("implausible values");
   if(nav!==null&&(nav<=0.1||nav>=100))throw Error("implausible historic NAV");
   const computed=(price/ref-1)*100;
   if(Math.abs(computed-premium)>0.1)throw Error("feed arithmetic mismatch");
   out[code]={code:code,source_timestamp_cst:sp.date+"T"+sp.hour+":"+sp.minute+":"+sp.second+"+08:00",
     snapshot_price_cny:f[3],reference_value_cny:f[78],feed_premium_pct:f[77],
     recalculated_premium_pct:Math.round(computed*1e4)/1e4,historical_nav_candidate_cny:f[81]||null,
     data_quality:"Tencent_same_snapshot_coherent_unofficial_reference"};
  }catch(e){errors[code]=String(e.message||e);}
 }
 if(Object.keys(out).length!==4)throw Error("partial_batch_rejected: "+JSON.stringify(errors));
 const clocks=Object.values(out).map(x=>Date.parse(x.source_timestamp_cst));
 if(Math.max(...clocks)-Math.min(...clocks)>90000)throw Error("fund timestamps more than 90s apart");
 return out;
}
async function save(env,path,data){
 if(!env.GITHUB_TOKEN)throw Error("missing GITHUB_TOKEN secret");
 const bytes=new TextEncoder().encode(JSON.stringify(data,null,2)+"\n");
 let str="";for(const b of bytes)str+=String.fromCharCode(b);
 const r=await fetch(ROOT+path,{method:"PUT",headers:{
  Authorization:"Bearer "+env.GITHUB_TOKEN,Accept:"application/vnd.github+json",
  "X-GitHub-Api-Version":"2022-11-28","User-Agent":"qdii-etf-direct-capture",
  "Content-Type":"application/json"},
  body:JSON.stringify({message:"Record QDII same-snapshot reference candidate "+data.captured_at_cst,content:btoa(str),branch:"main"})});
 if(!r.ok)throw Error("GitHub write "+r.status+": "+(await r.text()).slice(0,300));
}
export default {
 async scheduled(event,env){
  try{
   const now=new Date(),p=parts(now),scheduled=parts(new Date(event.scheduledTime));
   if(!["Mon","Tue","Wed","Thu","Fri"].includes(p.weekday)||
      p.ymd!==scheduled.ymd||scheduled.hour!=="14"||
      !["04","09","14"].includes(scheduled.minute)||
      p.hour!=="14"||+p.minute<2||+p.minute>35){
    console.log(JSON.stringify({status:"skip_window",now:p,scheduled:scheduled}));return;
   }
   const url="https://qt.gtimg.cn/q="+Object.values(SYMBOLS).join(",");
   const response=await fetch(url,{headers:{"Referer":"https://gu.qq.com/","User-Agent":"Mozilla/5.0"}});
   if(!response.ok)throw Error("Tencent HTTP "+response.status);
   const text=new TextDecoder("gb18030").decode(await response.arrayBuffer());
   const records=parseQuote(text,now);
   const stamp=p.ymd+"-"+p.hour+p.minute+p.second;
   const path=PREFIX+p.date+"/"+stamp+".json";
   const captured=p.date+"T"+p.hour+":"+p.minute+":"+p.second+"+08:00";
   await save(env,path,{schema_version:1,source:"Tencent Finance",
     captured_at_cst:captured,scheduled_at_utc:new Date(event.scheduledTime).toISOString(),
     source_field_indexes:{price:3,timestamp:30,premium:77,reference:78,historic_nav:81},
     official_iopv_verified:false,exact_1400_minute_bar:false,
     warning:"UNOFFICIAL vendor reference premium candidate; NOT exchange IOPV or trading signal",instruments:records});
   console.log(JSON.stringify({status:"saved",path:path,codes:Object.keys(records)}));
  }catch(e){console.error(JSON.stringify({status:"failed",reason:String(e.message||e)}));throw e;}
 }
};