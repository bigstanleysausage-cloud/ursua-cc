// ULQF v0.4.0 — bound Google Apps Script collector
// Paste into Extensions > Apps Script in GLAIR. Run setupULQF once.
const ULQF = {dailyCap: 5000, canary: "ulqf-canary", source: "pages-browser-v1"};
function setupULQF() {
  const book = SpreadsheetApp.getActiveSpreadsheet();
  if (!book || !book.getSheetByName("ClickEvents") || !book.getSheetByName("Aliases")) throw Error("Open the GLAIR workbook first");
  PropertiesService.getScriptProperties().setProperty("ULQF_BOOK_ID", book.getId());
  return "ULQF collector configured; deploy as Web app.";
}
function reply_(obj) { return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON); }
function doGet() { return reply_({service:"ULQF",version:"0.4.0",mode:"POST_ONLY",configured:!!PropertiesService.getScriptProperties().getProperty("ULQF_BOOK_ID")}); }
function doPost(e) {
  let p;
  try {
    const raw=e && e.postData && e.postData.contents;
    if(typeof raw!=="string" || raw.length>1024) return reply_({ok:false,reason:"invalid"});
    p=JSON.parse(raw);
    if(!p || typeof p!=="object" || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(p.id||"") || typeof p.alias!=="string") return reply_({ok:false,reason:"invalid"});
    p.id=p.id.toLowerCase();
    const code=p.alias.toLowerCase();
    if(code!==ULQF.canary && !/^[a-z0-9]{4}(?:[a-z0-9]{2})?$/.test(code)) return reply_({ok:false,reason:"invalid"});
    const props=PropertiesService.getScriptProperties();
    const bookId=props.getProperty("ULQF_BOOK_ID");
    if(!bookId) return reply_({ok:false,reason:"unconfigured"});
    const lock=LockService.getScriptLock();
    if(!lock.tryLock(3000)) return reply_({ok:false,reason:"busy"});
    try {
      const now=new Date().toISOString(), day=now.slice(0,10);
      const prev=props.getProperty("ULQF_DAY"), count=prev===day?Number(props.getProperty("ULQF_COUNT")||0):0;
      if(!Number.isFinite(count)||count>=ULQF.dailyCap) return reply_({ok:false,reason:"daily_cap"});
      const book=SpreadsheetApp.openById(bookId), events=book.getSheetByName("ClickEvents");
      let aliasId="", destId="", kind="test";
      if(code!==ULQF.canary){
        const aliases=book.getSheetByName("Aliases");
        const rows=aliases.getLastRow()>1?aliases.getRange(2,1,aliases.getLastRow()-1,8).getDisplayValues():[];
        const matches=rows.filter(r=>r[4].toLowerCase()==="ursua.cc" && r[5].toLowerCase()===code && ["ISSUED","VERIFIED","ACTIVE"].includes(r[7]));
        if(matches.length!==1)return reply_({ok:false,reason:"unknown_alias"});
        aliasId=matches[0][0]; destId=matches[0][1]; kind="observed";
      }
      const last=events.getLastRow(), n=Math.min(1000,Math.max(0,last-1));
      if(n && events.getRange(last-n+1,1,n,1).getDisplayValues().some(r=>r[0]===p.id))return reply_({ok:true,duplicate:true});
      const ref=typeof p.ref==="string"&&p.ref.length<=253&&/^[a-z0-9][a-z0-9.-]*$/i.test(p.ref)?p.ref.toLowerCase():"";
      const device=["mobile","tablet","desktop","unknown"].includes(p.device)?p.device:"unknown";
      if(last>=events.getMaxRows())events.insertRowsAfter(events.getMaxRows(),1000);
      // Alias codes and referrer begin with alphanumeric characters; no user-entered formulas.
      events.appendRow([p.id.toLowerCase(),now,day,code,aliasId,destId,kind,ref,device,ULQF.source]);
      SpreadsheetApp.flush();
      props.setProperties({ULQF_DAY:day,ULQF_COUNT:String(count+1)});
      return reply_({ok:true,event_class:kind});
    } finally { lock.releaseLock(); }
  } catch (_) { return reply_({ok:false,reason:"collector_error"}); }
}
