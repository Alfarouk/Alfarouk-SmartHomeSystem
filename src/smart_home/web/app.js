"use strict";
let state = null;
let busy = false;
const icons = {light:"☀",door:"▣",curtain:"▤",fan:"✣",bin:"▱",alarm:"◇"};
const $ = (id) => document.getElementById(id);
function element(tag, cls, text) { const el=document.createElement(tag); if(cls)el.className=cls; if(text!==undefined)el.textContent=text; return el; }
function feedback(message, ok=true) { $("feedback").textContent=message; $("feedback").className=ok?"success":"error"; }
function getCode() {
  return new Promise((resolve) => {
    const dialog=$("code-dialog"), form=$("code-form"), input=$("control-code"); input.value="";
    const finish=(value)=>{ form.removeEventListener("submit",submit); dialog.removeEventListener("cancel",cancel); $("cancel-code").onclick=null; dialog.close(); input.value=""; resolve(value); };
    const submit=(e)=>{e.preventDefault();finish(input.value);};
    const cancel=(e)=>{if(e)e.preventDefault();finish(null);};
    form.addEventListener("submit",submit); dialog.addEventListener("cancel",cancel); $("cancel-code").onclick=()=>cancel();dialog.showModal();input.focus();
  });
}
async function request(path,payload,protectedAction=false) {
  if(busy)return;
  busy=true;
  try {
    if(protectedAction) {const code=await getCode();if(code===null){feedback("Cancelled. No device state changed.");return;}payload.code=code;}
    const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const data=await r.json();
    if(!r.ok)throw new Error(data.message||"The command could not be processed.");
    state=data.state;render();feedback(data.result.message,data.result.ok);
  } catch(e) {feedback(e.message||"The local server is unavailable.",false);} finally {busy=false;}
}
function button(label,action,selected=false) { const b=element("button",selected?"selected":"",label);b.type="button";b.addEventListener("click",action);return b; }
function operate(d,command,value) {request("/api/device",{device_id:d.id,command,value},["unlock","disarm"].includes(command));}
function range(d,command,value) {
  const row=element("label","range"), input=element("input"),out=element("output",null,value+"%"); input.type="range";input.min="0";input.max="100";input.value=value;input.setAttribute("aria-label",d.name+" "+(command==="dim"?"brightness":command==="set_speed"?"speed":"position"));
  input.addEventListener("input",()=>out.textContent=input.value+"%");input.addEventListener("change",()=>operate(d,command,Number(input.value)));row.append(input,out);return row;
}
function render() {
  const selected=$("room").value,rooms=[...new Set(state.devices.map(d=>d.room))];
  $("device-count").textContent=state.devices.length+" devices";$("room-count").textContent=rooms.length+" rooms";
  if($("room").options.length!==rooms.length+1){$("room").replaceChildren(new Option("All rooms",""),...rooms.map(r=>new Option(r,r)));$("room").value=selected;}
  const grid=$("devices");grid.replaceChildren();
  state.devices.filter(d=>!selected||d.room===selected).forEach(d=>{
    const active=["on","open","armed"].includes(d.state),card=element("article","device"+(active?" active":""));
    const top=element("div","device-top"),badge=element("span","state",d.type==="door"?(d.locked?"locked":"unlocked")+" · "+d.state:d.state);
    top.append(element("span","device-icon",icons[d.type]||"◇"),badge);card.append(top,element("h3",null,d.name),element("p","room-name",d.room));
    const controls=element("div","device-controls");
    if(["light","fan"].includes(d.type)){controls.append(button("On",()=>operate(d,"turn_on"),d.state==="on"),button("Off",()=>operate(d,"turn_off"),d.state==="off"));controls.append(range(d,d.type==="light"?"dim":"set_speed",d.type==="light"?d.brightness:d.speed));}
    else if(d.type==="door"){controls.append(button(d.locked?"Unlock":"Lock",()=>operate(d,d.locked?"unlock":"lock")),button(d.state==="open"?"Close":"Open",()=>operate(d,d.state==="open"?"close":"open")));}
    else if(d.type==="curtain"){controls.append(button("Open",()=>operate(d,"open"),d.position===100),button("Close",()=>operate(d,"close"),d.position===0),range(d,"set_position",d.position));}
    else if(d.type==="bin"){controls.append(button(d.state==="open"?"Close":"Open",()=>operate(d,d.state==="open"?"close":"open")));}
    else if(d.type==="alarm"){controls.append(button(d.state==="armed"?"Disarm":"Arm",()=>operate(d,d.state==="armed"?"disarm":"arm")));}
    card.append(controls);grid.append(card);
  });
  const names={movie_time:["◐","Movie time","Dim the main light, close the curtain and slow the fan."],good_morning:["☀","Good morning","Turn on both lights and open the curtain."],night_mode:["☾","Night mode","Lights and fan off. Curtain closed. Front door locked."]};
  $("scenes").replaceChildren();Object.keys(state.scenes).forEach(name=>{const [icon,title,desc]=names[name]||["◇",name.replaceAll("_"," "),"Run this scene."];const b=element("button","scene"),text=element("span");b.type="button";text.append(element("strong",null,title),element("small",null,desc));b.append(element("span","scene-icon",icon),text);b.onclick=()=>request("/api/scene",{name});$("scenes").append(b);});
  $("activity").replaceChildren();if(!state.events.length)$("activity").append(element("li",null,"No changes yet."));state.events.slice(0,6).forEach(e=>{const li=element("li"),time=element("time",null,new Date(e.time*1000).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit",second:"2-digit"}));li.append(time,document.createTextNode(e.message));$("activity").append(li);});
}
$("command-form").addEventListener("submit",e=>{e.preventDefault();const text=$("command").value;request("/api/command",{text},/\b(unlock|unsecure|disarm)\b|\b(disable|deactivate|turn off|unset)\b.*\b(alarm|security)\b/i.test(text));});
document.querySelectorAll("[data-example]").forEach(b=>b.addEventListener("click",()=>{$("command").value=b.dataset.example;$("command").focus();}));
$("room").addEventListener("change",()=>{if(state)render();});
async function refresh(){if(busy||$("code-dialog").open)return;try{const r=await fetch("/api/state");const data=await r.json();if(!r.ok)throw Error(data.message||"The local server is unavailable.");if(!state||data.instance_id!==state.instance_id||data.revision!==state.revision){state=data;render();}}catch(e){feedback(e.message||"The local server is unavailable. Restart it to continue.",false);}}
refresh();setInterval(refresh,1000);
