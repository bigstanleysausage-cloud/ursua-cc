/* ULQF v0.4.0 browser redirect; analytics is optional and fail-open. */
(function(){
  "use strict";
  const script=document.currentScript;
  const config=Object.freeze({endpoint:""}); // Set only after verified Apps Script deployment.
  function track(code){
    try{
      if(!config.endpoint || !/^https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]+\/exec$/.test(config.endpoint))return;
      if(navigator.globalPrivacyControl===true || navigator.doNotTrack==="1")return;
      if(!globalThis.crypto || typeof crypto.randomUUID!=="function")return;
      let ref=""; try{ref=document.referrer?new URL(document.referrer).hostname:"";}catch(_){}
      const ua=navigator.userAgent||"";
      const device=/iPad|Tablet/i.test(ua)?"tablet":/Mobile|Android|iPhone/i.test(ua)?"mobile":ua?"desktop":"unknown";
      const body=JSON.stringify({id:crypto.randomUUID(),alias:code.toLowerCase(),ref,device});
      if(typeof navigator.sendBeacon==="function"&&navigator.sendBeacon(config.endpoint,body))return;
      fetch(config.endpoint,{method:"POST",body,mode:"no-cors",keepalive:true,credentials:"omit"}).catch(()=>{});
    }catch(_){}
  }
  function go(code,target){
    try{track(code);}finally{location.replace(target);}
  }
  window.ULQF={go};
  if(script && script.dataset.alias && script.dataset.target)go(script.dataset.alias,script.dataset.target);
})();
