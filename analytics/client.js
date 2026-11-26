/* ULQF v0.4.0 browser redirect; analytics is optional and fail-open. */
(function(){
  "use strict";
  const script=document.currentScript;
  const config=Object.freeze({endpoint:"https://script.google.com/macros/s/AKfycbzqXmGU6W-T6EdSLY2v1xeDOF90eJQnypcb5MnSOfBj8M6J0vb-urukZ7NUjy_Q_UbRvQ/exec"}); // Canary-only acceptance stage; production disabled.
  function track(code){
    try{
      if(code.toLowerCase()!=="ulqf-canary")return;
      if(!config.endpoint || !/^https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]+\/exec$/.test(config.endpoint))return;
      if(navigator.globalPrivacyControl===true || navigator.doNotTrack==="1")return;
      if(!globalThis.crypto || typeof crypto.randomUUID!=="function")return;
      let ref=""; try{ref=document.referrer?new URL(document.referrer).hostname:"";}catch(_){}
      const ua=navigator.userAgent||"";
      const device=/iPad|Tablet/i.test(ua)?"tablet":/Mobile|Android|iPhone/i.test(ua)?"mobile":ua?"desktop":"unknown";
      const body=JSON.stringify({id:crypto.randomUUID(),alias:code.toLowerCase(),ref,device});
      return fetch(config.endpoint,{method:"POST",headers:{"Content-Type":"text/plain;charset=UTF-8"},body,mode:"no-cors",keepalive:true,credentials:"omit"}).catch(()=>{});
    }catch(_){}
  }
  function go(code,target){
    let navigated=false;
    const finish=()=>{if(!navigated){navigated=true;location.replace(target);}};
    try{const pending=track(code);if(!pending){finish();return;}setTimeout(finish,900);Promise.resolve(pending).then(finish,finish);}catch(_){finish();}
  }
  window.ULQF={go};
  if(script && script.dataset.alias && script.dataset.target)go(script.dataset.alias,script.dataset.target);
})();
