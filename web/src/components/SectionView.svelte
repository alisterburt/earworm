<script>
  import { onMount } from "svelte";
  import { get } from "svelte/store";
  import { transport } from "../lib/engine.js";
  import { zoomBars, relativeMode, selectedStem, cleanMidi } from "../lib/stores.js";
  import { notePc, pcColor, degreeLabel, keyScalePcs, chordRootPc, chordName, chordColorAt } from "../lib/sonofield.js";
  import { melodicStems } from "../lib/stems.js";
  import { playNote } from "../lib/synth.js";

  let { song, engine } = $props();
  const stems = melodicStems(song);
  let canvas, wrap;
  let width = $state(900);
  let height = $state(460); // bound to the container; the piano roll grows to fill

  // regions — fixed lanes at top/bottom; the piano roll takes the slack between.
  const CH_Y = 0, CH_H = 54, LP_Y = 54, LP_H = 14, LY_Y = 68, LY_H = 20;
  const ROLL_Y = 88, KB_H = 132;
  let KB_Y = 0, ROLL_H = 0; // computed per-frame from height (also read by pointer handlers)
  const GUT = 52, LBL = 24, PHF = 0.2;
  const LYRIC_OFFSET = 0.0; // word timings repaired upstream (lyrics.fix_word_timing)
  const WHITE = new Set([0,2,4,5,7,9,11]);
  const MONO = new Set(["vocals","bass"]);
  const C = { text:"#eef1f6", dim:"#9aa3b2", faint:"#6b7280", panel:"#15171c",
              rowA:"#171a21", rowB:"#11141a", beat:"#20242d", bar:"#39414f", ph:"#ff5d5d", loop:"#6a7bff" };

  const tonicPc = notePc(song.key?.tonic || "C");
  const mode = song.key?.mode || "major";
  const scale = keyScalePcs(tonicPc, mode);
  const downbeats = song.downbeats || [], beats = song.beats || [];
  const barDur = downbeats.length > 1
    ? (downbeats.slice(1).map((b,i)=>b-downbeats[i]).sort((a,b)=>a-b)[downbeats.length>>1] || 2) : 2;
  const words = (song.lyrics?.segments || []).flatMap((s) =>
    (s.words?.length ? s.words : [{ start:s.start, end:s.end, word:s.text }]))
    .map((w) => ({ ...w, start: w.start + LYRIC_OFFSET, end: w.end + LYRIC_OFFSET }));
  const chords = song.chords || [];
  const selOr = () => get(selectedStem) || stems[0];
  const notesFor = () => song.stems[selOr()]?.[get(cleanMidi) ? "notes_clean" : "notes"] || [];
  const noteColor = (n) => MONO.has(selOr()) ? pcColor(((n.pitch%12)+12)%12, tonicPc)
                          : (chordColorAt(chords, n.s, tonicPc) || pcColor(((n.pitch%12)+12)%12, tonicPc));

  function roundRect(ctx,x,y,w,h,r){ r=Math.max(0,Math.min(r,h/2,w/2)); ctx.beginPath();
    ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r);
    ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath(); }
  function gnote(ctx,x,y,w,h,color,glow){ if(glow){ctx.shadowColor=color;ctx.shadowBlur=9;}
    roundRect(ctx,x,y,w,h,Math.min(4,h/2)); ctx.fillStyle=color; ctx.fill(); ctx.shadowBlur=0;
    ctx.fillStyle="rgba(255,255,255,0.16)"; roundRect(ctx,x,y,w,Math.max(1,h*0.4),Math.min(4,h/2)); ctx.fill(); }
  function keyLayout(lo,hi,W){ const whites=[]; for(let p=lo;p<=hi;p++) if(WHITE.has(((p%12)+12)%12)) whites.push(p);
    const ww=W/Math.max(1,whites.length), bw=ww*0.6, map={};
    whites.forEach((p,i)=>map[p]={x:i*ww,w:ww,white:true});
    for(let p=lo;p<=hi;p++){ if(map[p])continue; const b=map[p-1]; map[p]={x:b?b.x+ww-bw/2:0,w:bw,white:false}; }
    return map; }

  let view={}, raf, loopDrag=null;
  // View mapping: time<->x. No loop = fixed playhead at PHF, roll scrolls. Loop
  // active = fixed window framing the loop (playhead moves across it).
  let geom={originT:0,originX:0,pps:1};
  function draw(){
    if(!canvas) return;
    const H=height; KB_Y=H-KB_H; ROLL_H=Math.max(60,KB_Y-ROLL_Y);
    const t=get(transport), now=t.time, zb=get(zoomBars), rel=get(relativeMode), lp=t.loop;
    // pps is zoom-controlled in both modes. Loop = view centred on the loop centre
    // (playhead moves); no loop = playhead fixed at PHF, roll scrolls.
    let originT, originX, pps=width/(zb*barDur);
    if(frozenView){ ({originT,originX,pps}=frozenView); }
    else if(lp){ originT=(lp.start+lp.end)/2; originX=width/2; }
    else { originT=now; originX=width*PHF; }
    geom={originT,originX,pps};
    const X=(ta)=>originX+(ta-originT)*pps;
    const t0=originT-originX/pps, t1=originT+(width-originX)/pps;
    const phX=X(now); // playhead x (fixed at PHF when scrolling; moves within a loop)
    const dpr=window.devicePixelRatio||1; canvas.width=width*dpr; canvas.height=H*dpr;
    canvas.style.width=width+"px"; canvas.style.height=H+"px";
    const ctx=canvas.getContext("2d"); ctx.scale(dpr,dpr); ctx.clearRect(0,0,width,H);
    ctx.fillStyle=C.panel; ctx.fillRect(0,0,width,H);
    const PHB = ROLL_Y+ROLL_H; // playhead bottom

    // grid
    ctx.strokeStyle=C.beat; ctx.lineWidth=1; ctx.beginPath();
    for(const b of beats) if(b>=t0&&b<=t1){const x=Math.round(X(b))+.5; ctx.moveTo(x,0); ctx.lineTo(x,PHB);} ctx.stroke();
    ctx.strokeStyle=C.bar; ctx.lineWidth=1.5; ctx.fillStyle=C.faint; ctx.font="11px system-ui";
    downbeats.forEach((db,i)=>{ if(db<t0||db>t1)return; const x=Math.round(X(db))+.5;
      ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,PHB); ctx.stroke(); ctx.fillText(String(i+1),x+4,12); });

    // chords (dual names)
    for(const c of chords){ if(c.end<t0||c.start>t1||c.label==="N")continue;
      const x0=X(c.start), w=X(c.end)-x0, root=chordRootPc(c.label);
      const col=root==null?"#555b66":pcColor(root,tonicPc);
      ctx.fillStyle=col+"2e"; roundRect(ctx,x0+2,CH_Y+4,Math.max(2,w-4),CH_H-8,6); ctx.fill();
      ctx.fillStyle=col; ctx.fillRect(x0+2,CH_Y+4,3,CH_H-8);
      if(w>22){ const pri=chordName(c.label,tonicPc,mode,rel)||c.label, sec=chordName(c.label,tonicPc,mode,!rel);
        ctx.fillStyle=C.text; ctx.font="650 15px system-ui"; ctx.fillText(pri,x0+9,CH_Y+28);
        if(sec&&sec!==pri){ ctx.fillStyle=C.dim; ctx.font="400 11px system-ui"; ctx.fillText(sec,x0+9,CH_Y+44);} } }

    // loop lane (under chords)
    ctx.fillStyle="#0e1016"; ctx.fillRect(0,LP_Y,width,LP_H);
    ctx.fillStyle=C.faint; ctx.font="9px system-ui"; ctx.fillText("⟳ loop", 6, LP_Y+11);

    // lyrics
    for(const wd of words){ if(wd.end<t0||wd.start>t1)continue; const x=X(wd.start);
      const active=now>=wd.start&&now<wd.end;
      ctx.fillStyle=active?C.text:(wd.end<=now?C.faint:C.dim);
      ctx.font=(active?"700 ":"400 ")+"13px system-ui"; ctx.fillText(wd.word.trim(),x,LY_Y+16); }

    // piano roll
    const notes=notesFor(); let lo=127,hi=0; for(const n of notes){if(n.pitch<lo)lo=n.pitch;if(n.pitch>hi)hi=n.pitch;}
    if(lo>hi){lo=48;hi=72;} lo-=1; hi+=1; const span=hi-lo, rowH=ROLL_H/(span+1);
    const Y=(p)=>ROLL_Y+ROLL_H-(p-lo+1)*rowH;
    for(let p=lo;p<=hi;p++){ const pc=((p%12)+12)%12; ctx.fillStyle=WHITE.has(pc)?C.rowA:C.rowB; ctx.fillRect(0,Y(p),width,rowH); }
    for(const n of notes){ if(n.e<t0||n.s>t1)continue; const x=X(n.s), w=Math.max(3,(n.e-n.s)*pps);
      ctx.globalAlpha=0.6+0.4*(n.vel/127); gnote(ctx,x,Y(n.pitch)+1,w,Math.max(3,rowH-2),noteColor(n),w>6); ctx.globalAlpha=1; }
    // gutter keyboard ON TOP (notes slide behind), labels left of keys
    ctx.fillStyle=C.panel; ctx.fillRect(0,ROLL_Y,GUT,ROLL_H);
    for(let p=lo;p<=hi;p++){ const pc=((p%12)+12)%12, y=Y(p), inKey=scale.has(pc);
      ctx.fillStyle=WHITE.has(pc)?"#e9edf3":"#15181f"; roundRect(ctx,LBL+1,y+0.5,GUT-LBL-2,rowH-1,2); ctx.fill();
      if(inKey){ ctx.fillStyle=pcColor(pc,tonicPc); roundRect(ctx,LBL+2,y+1,4,rowH-2,1.5); ctx.fill(); }
      if(pc===0){ ctx.fillStyle=C.dim; ctx.font="9px system-ui"; ctx.fillText("C"+(Math.floor(p/12)-1),1,y+rowH-1); }
      else if(inKey&&rowH>10){ ctx.fillStyle=pcColor(pc,tonicPc); ctx.font="600 9px system-ui"; ctx.fillText(degreeLabel(pc,tonicPc),2,y+rowH-2); } }

    // ---- keyboard: name on every key, colored degree badge on in-scale keys
    // (incl. black keys), tonic underline. Range padded to whole octaves and
    // widened with extra notes so keys never get too wide. ----
    const whitesIn=(a,b)=>{let c=0;for(let q=a;q<=b;q++)if(WHITE.has(((q%12)+12)%12))c++;return c;};
    let klo=Math.floor(lo/12)*12, khi=Math.floor(hi/12)*12+11;
    while(whitesIn(klo,khi) < width/74){ khi+=12; if(whitesIn(klo,khi) < width/74 && klo>12) klo-=12; if(khi>=120) break; }
    const layout=keyLayout(klo,khi,width), activeP=new Set();
    for(const n of notes) if(now>=n.s&&now<n.e) activeP.add(n.pitch);
    const NM=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"], oct=(p)=>Math.floor(p/12)-1;
    const bh=Math.round(KB_H*0.62), wr=Math.max(8,Math.min(14,(width/whitesIn(klo,khi))*0.21));
    const badge=(cx,cy,r,col,txt)=>{ ctx.beginPath(); ctx.arc(cx,cy,r,0,6.2832); ctx.fillStyle=col; ctx.fill();
      ctx.fillStyle="#fff"; ctx.font=`800 ${Math.round(r*1.05)}px system-ui`; ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.fillText(txt,cx,cy+0.5); };
    ctx.fillStyle="#0c0e12"; ctx.fillRect(0,KB_Y-6,width,H-KB_Y+6);
    // white keys
    for(let p=klo;p<=khi;p++){ const k=layout[p]; if(!k.white)continue; const pc=((p%12)+12)%12, on=activeP.has(p)||heldP.has(p), inK=scale.has(pc), cx=k.x+k.w/2;
      const g=ctx.createLinearGradient(0,KB_Y,0,KB_Y+KB_H);
      g.addColorStop(0,"#f4f1e9"); g.addColorStop(1,"#dcd7c8");
      ctx.fillStyle=g; roundRect(ctx,k.x+1,KB_Y,k.w-2,KB_H-2,5); ctx.fill();
      if(on){ ctx.globalAlpha=0.42; ctx.fillStyle=pcColor(pc,tonicPc); roundRect(ctx,k.x+1,KB_Y,k.w-2,KB_H-2,5); ctx.fill(); ctx.globalAlpha=1; }
      if(inK) badge(cx,KB_Y+KB_H-23-wr,wr,pcColor(pc,tonicPc),degreeLabel(pc,tonicPc)); // just above the key label
      ctx.fillStyle="#6b7280"; ctx.font="600 10px system-ui"; ctx.textAlign="center"; ctx.textBaseline="alphabetic"; ctx.fillText(NM[pc]+oct(p),cx,KB_Y+KB_H-8);
      if(pc===tonicPc){ ctx.fillStyle="#f3ac60"; roundRect(ctx,cx-(k.w-2)*0.28,KB_Y+KB_H-5,(k.w-2)*0.56,3,1.5); ctx.fill(); } }
    // black keys (on top)
    for(let p=klo;p<=khi;p++){ const k=layout[p]; if(k.white)continue; const pc=((p%12)+12)%12, on=activeP.has(p)||heldP.has(p), inK=scale.has(pc), cx=k.x+k.w/2;
      const g=ctx.createLinearGradient(0,KB_Y,0,KB_Y+bh);
      g.addColorStop(0,"#2c333f"); g.addColorStop(1,"#10141b");
      ctx.fillStyle=g; roundRect(ctx,k.x,KB_Y,k.w,bh,4); ctx.fill();
      if(on){ ctx.globalAlpha=0.6; ctx.fillStyle=pcColor(pc,tonicPc); roundRect(ctx,k.x,KB_Y,k.w,bh,4); ctx.fill(); ctx.globalAlpha=1; }
      {const br=Math.max(7,wr-2); if(inK) badge(cx,KB_Y+bh-16-br,br,pcColor(pc,tonicPc),degreeLabel(pc,tonicPc));} // just above the key label
      ctx.fillStyle="#aab0bd"; ctx.font="600 9px system-ui"; ctx.textAlign="center"; ctx.textBaseline="alphabetic"; ctx.fillText(NM[pc]+oct(p),cx,KB_Y+bh-6); }
    ctx.textAlign="left"; ctx.textBaseline="alphabetic";

    // loop region overlay
    if(t.loop){ ctx.fillStyle="rgba(106,123,255,.16)"; ctx.fillRect(X(t.loop.start),0,X(t.loop.end)-X(t.loop.start),PHB);
      ctx.strokeStyle=C.loop; ctx.lineWidth=2; for(const e of [t.loop.start,t.loop.end]){const x=X(e);ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,PHB);ctx.stroke();} }
    if(loopDrag){ const a=X(loopDrag.a),b=X(loopDrag.b); ctx.fillStyle="rgba(106,123,255,.18)"; ctx.fillRect(Math.min(a,b),LP_Y,Math.abs(b-a),PHB-LP_Y); }

    // playhead
    ctx.strokeStyle=C.ph; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(phX,0); ctx.lineTo(phX,PHB); ctx.stroke();

    view={lo,hi,rowH,layout,kbLo:klo,kbHi:khi}; raf=requestAnimationFrame(draw);
  }

  const snapBar=(t)=> downbeats.length?downbeats.reduce((p,c)=>Math.abs(c-t)<Math.abs(p-t)?c:p):t;
  const snapBeat=(t)=> beats.length?beats.reduce((p,c)=>Math.abs(c-t)<Math.abs(p-t)?c:p):snapBar(t);
  function ptTime(e){ const r=wrap.getBoundingClientRect(); return geom.originT+((e.clientX-r.left)-geom.originX)/geom.pps; }
  let scrub=null, moved=false;
  // "Sweep to collect": dragging accumulates every note in the swept time range
  // and keeps those keys lit on the keyboard until the next plain click / drag.
  let heldP=new Set(), dragLo=0, dragHi=0;
  // Dragging a loop edge: freeze the view mapping so resizing doesn't re-centre
  // the loop-framed view under the cursor (which would cause feedback drift).
  let loopEdge=null, frozenView=null;
  function down(e){ if(e.target!==canvas) return; // let overlay buttons (zoom, loop) handle their own clicks
    const r=wrap.getBoundingClientRect(); const x=e.clientX-r.left, y=e.clientY-r.top;
    const lp0=get(transport).loop, Xt=(tt)=>geom.originX+(tt-geom.originT)*geom.pps;
    // grab a loop edge to resize (freeze the view so it doesn't drift while dragging)
    if(lp0 && y<KB_Y){
      if(Math.abs(x-Xt(lp0.start))<=7){ loopEdge={which:"start"}; frozenView={...geom}; wrap.setPointerCapture(e.pointerId); return; }
      if(Math.abs(x-Xt(lp0.end))<=7){ loopEdge={which:"end"}; frozenView={...geom}; wrap.setPointerCapture(e.pointerId); return; } }
    // loop lane: drag a loop region (snaps to beats live)
    if(y>=LP_Y && y<LP_Y+LP_H){ const t=snapBeat(ptTime(e)); loopDrag={a:t,b:t}; wrap.setPointerCapture(e.pointerId); return; }
    // gutter: click a row to hear that pitch
    if(y>=ROLL_Y && y<ROLL_Y+ROLL_H && x<GUT){ const p=Math.round(view.lo+(ROLL_Y+ROLL_H-y)/view.rowH-1); if(p>=view.lo&&p<=view.hi) playNote(p); return; }
    // on-screen keyboard
    if(y>=KB_Y){ let hit=null;
      for(let p=view.kbLo;p<=view.kbHi;p++){const k=view.layout[p]; if(!k.white&&x>=k.x&&x<=k.x+k.w&&y<=KB_Y+KB_H*0.62){hit=p;break;}}
      if(hit==null) for(let p=view.kbLo;p<=view.kbHi;p++){const k=view.layout[p]; if(k.white&&x>=k.x&&x<k.x+k.w){hit=p;break;}}
      if(hit!=null) playNote(hit); return; }
    // roll body: click a note to hear it (exact drawn-rectangle hit-test)
    if(y>=ROLL_Y && y<ROLL_Y+ROLL_H && x>=GUT){
      const Xt=(t)=>geom.originX+(t-geom.originT)*geom.pps, Yp=(pit)=>ROLL_Y+ROLL_H-(pit-view.lo+1)*view.rowH;
      for(const n of notesFor()){ const nx=Xt(n.s), nw=Math.max(3,(n.e-n.s)*geom.pps), ny=Yp(n.pitch);
        if(x>=nx-2 && x<=nx+nw+2 && y>=ny-1 && y<=ny+view.rowH+1){ playNote(n.pitch); return; } } }
    // start a drag (also sweep-collects notes). In a loop the view is fixed so the
    // playhead follows the cursor (seek); otherwise we grab + pan the timeline.
    moved=false; heldP=new Set();
    const lp=get(transport).loop;
    if(lp){ const tt=Math.max(lp.start,Math.min(lp.end,ptTime(e))); engine.seek(tt); scrub={seek:true}; dragLo=dragHi=tt; }
    else { scrub={grabT:ptTime(e)}; dragLo=dragHi=get(transport).time; }
    wrap.setPointerCapture(e.pointerId); }
  function move(e){
    if(loopEdge){ const lp=get(transport).loop; if(lp){ const t=snapBeat(ptTime(e));
        if(loopEdge.which==="start") engine.setLoop({start:Math.min(t,lp.end-0.1), end:lp.end});
        else engine.setLoop({start:lp.start, end:Math.max(t,lp.start+0.1)}); } return; }
    if(loopDrag){ loopDrag.b=snapBeat(ptTime(e)); return; }
    if(scrub){ moved=true; const cx=e.clientX-wrap.getBoundingClientRect().left, lp=get(transport).loop;
      let t=scrub.seek ? geom.originT+(cx-geom.originX)/geom.pps
                       : scrub.grabT-(cx-geom.originX)/geom.pps;
      if(scrub.seek && lp) t=Math.max(lp.start,Math.min(lp.end,t));
      engine.seek(t); dragLo=Math.min(dragLo,t); dragHi=Math.max(dragHi,t);
      const hp=new Set(); for(const n of notesFor()) if(n.s<dragHi && n.e>dragLo) hp.add(n.pitch); heldP=hp; return; }
    // idle hover: show a resize cursor near a loop edge
    const lp=get(transport).loop;
    if(lp){ const r=wrap.getBoundingClientRect(), x=e.clientX-r.left, y=e.clientY-r.top, Xt=(tt)=>geom.originX+(tt-geom.originT)*geom.pps;
      wrap.style.cursor = (y<KB_Y && (Math.abs(x-Xt(lp.start))<=7||Math.abs(x-Xt(lp.end))<=7)) ? "ew-resize" : ""; }
    else wrap.style.cursor=""; }
  function up(e){
    if(loopEdge){ loopEdge=null; frozenView=null; wrap.releasePointerCapture?.(e.pointerId); return; }
    if(loopDrag){ const a=snapBeat(loopDrag.a),b=snapBeat(loopDrag.b);
      if(Math.abs(b-a)>0.1) engine.setLoop({start:Math.min(a,b),end:Math.max(a,b)});
      loopDrag=null; wrap.releasePointerCapture?.(e.pointerId); return; }
    if(scrub){ if(!moved && !scrub.seek) engine.seek(scrub.grabT); heldP=new Set(); scrub=null; wrap.releasePointerCapture?.(e.pointerId); } }
  // Continuous horizontal zoom: mouse wheel or trackpad pinch (ctrlKey, smaller deltas).
  function wheel(e){ e.preventDefault();
    const k = e.ctrlKey ? 0.012 : 0.0015;
    zoomBars.update((z)=> Math.max(2, Math.min(64, z*Math.exp(e.deltaY*k)))); }

  onMount(()=>{ const ro=new ResizeObserver(()=>{width=wrap.clientWidth; height=wrap.clientHeight;});
    ro.observe(wrap); width=wrap.clientWidth; height=wrap.clientHeight; draw();
    const unsub=selectedStem.subscribe(()=>{heldP=new Set();}); // clear sweep on stem change
    return ()=>{cancelAnimationFrame(raf); ro.disconnect(); unsub();}; });
</script>

<div class="wrap" bind:this={wrap} onpointerdown={down} onpointermove={move} onpointerup={up} onwheel={wheel}>
  <canvas bind:this={canvas}></canvas>
  <div class="bars">
    <span>{Math.max(4, Math.floor($zoomBars / 4) * 4)}<br>bars</span>
  </div>
  {#if $transport.loop}
    <button class="clearloop" title="clear loop" onclick={(e)=>{e.stopPropagation(); engine.setLoop(null);}}>✕</button>
  {/if}
</div>

<style>
  .wrap { position: relative; height: 100%; min-height: 0; border-radius: var(--r-md);
    overflow: hidden; border: 1px solid var(--border); cursor: grab; background: var(--panel, #15171c); }
  .wrap:active { cursor: grabbing; }
  canvas { display: block; }
  .bars { position: absolute; top: 8px; right: 8px;
    display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 3px 4px;
    background: color-mix(in srgb, var(--surface) 82%, transparent);
    border: 1px solid var(--border); border-radius: var(--r-sm); backdrop-filter: blur(6px);
    color: var(--text-dim); font-size: 10px; text-align: center; }
  .bars button { padding: 1px 6px; line-height: 1.3; background: none; border: none; font-size: 13px; }
  .bars button:hover { color: var(--text); }
  .bars span { font-variant-numeric: tabular-nums; line-height: 1; }
  .clearloop { position: absolute; left: 50px; top: 56px; width: 16px; height: 16px; padding: 0;
    display: grid; place-items: center; font-size: 9px; line-height: 1; border-radius: 50%;
    background: var(--accent); color: var(--accent-contrast); border-color: var(--accent); }
  .clearloop:hover { filter: brightness(1.1); border-color: var(--accent); }
</style>
