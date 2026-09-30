// Drawing functions depend on i18n.js; no report requests or application state.
function svgNode(name,attrs={},text='') {const element=document.createElementNS('http://www.w3.org/2000/svg',name);for(const [key,value] of Object.entries(attrs))element.setAttribute(key,String(value));if(text)element.textContent=text;return element;}
function drawBars(id,rows) {
  const svg=document.getElementById(id);svg.replaceChildren();const height=Math.max(100,rows.length*(id==='quota-bars'?118:46)+20);svg.setAttribute('viewBox',`0 0 800 ${height}`);
  if(!rows.length){svg.append(svgNode('text',{x:20,y:45,class:'chart-label'},t('Недостаточно данных для диаграммы')));return;}
  const maximum=Math.max(...rows.map(r=>r.value),0.001);
  rows.forEach((row,i)=>{const y=16+i*(id==='quota-bars'?118:46);svg.append(svgNode('text',{x:8,y:y+18,class:'chart-label'},row.label));svg.append(svgNode('rect',{x:220,y,width:Math.max(1,row.value/maximum*395),height:27,rx:5,class:row.label.includes('astra')?'bar-astra':'bar-sol'}));svg.append(svgNode('text',{x:630,y:y+18,class:'chart-value'},row.display));if(row.detail){svg.append(svgNode('text',{x:220,y:y+47,class:'chart-label'},row.detail));if(row.components){row.components.forEach((part,index)=>{const x=220+index*190;svg.append(svgNode('text',{x,y:y+71,class:'chart-component-label'},part.label));svg.append(svgNode('text',{x,y:y+94,class:'chart-component-value'},number(part.value)));});}const title=svgNode('title',{},row.label+': '+row.display+'; '+row.detail+(row.components?'; '+row.components.map(part=>part.label+': '+number(part.value)).join('; '):''));svg.append(title);}});
}
const hiddenCurveSeries=new Set();
const themeColor = name => getComputedStyle(document.documentElement).getPropertyValue('--'+name).trim();
function curveModelColor(model) {
  if(model.includes('astra'))return themeColor('orange');
  if(model==='gpt-6.1-sol')return themeColor('purple');
  const palette=['curve-pink','curve-lime','curve-brown','curve-cyan','curve-red'].map(themeColor);
  let hash=0;for(const char of model)hash=(hash*31+char.charCodeAt(0))>>>0;
  return palette[hash%palette.length];
}
function smoothCurvePath(coords) {
  // Reduce subpixel jitter, preserving endpoints. Controls stay within each segment's
  // values so curves cannot overshoot the observed range or create negative tokens.
  const samples=[];
  for(let i=0;i<coords.length;i++){
    const point=coords[i],last=samples.at(-1);
    if(samples.length>1&&Math.floor((point[0]-coords[0][0])/5)===Math.floor((last[0]-coords[0][0])/5)&&i<coords.length-1)samples[samples.length-1]=point;
    else if(last&&point[0]===last[0])samples[samples.length-1]=point;
    else samples.push(point);
  }
  if(!samples.length)return '';
  let path=`M ${samples[0][0]} ${samples[0][1]}`;
  const slope=(a,b)=>(b[1]-a[1])/Math.max(0.001,b[0]-a[0]);
  const tangent=i=>{
    if(i===0)return slope(samples[0],samples[1]);
    if(i===samples.length-1)return slope(samples[i-1],samples[i]);
    const a=slope(samples[i-1],samples[i]),b=slope(samples[i],samples[i+1]);
    return a*b<=0?0:Math.sign(a)*Math.min(Math.abs((a+b)/2),3*Math.abs(a),3*Math.abs(b));
  };
  for(let i=1;i<samples.length;i++){
    const a=samples[i-1],b=samples[i],dx=(b[0]-a[0])/3;
    const clamp=value=>Math.max(Math.min(a[1],b[1]),Math.min(Math.max(a[1],b[1]),value));
    path+=` C ${a[0]+dx} ${clamp(a[1]+tangent(i-1)*dx)} ${b[0]-dx} ${clamp(b[1]-tangent(i)*dx)} ${b[0]} ${b[1]}`;
  }
  return path;
}
function drawCurve(points, bounds) {
  const svg=document.getElementById('quota-curve');svg.replaceChildren();svg.setAttribute('viewBox','0 0 800 260');
  svg.onpointermove=null;svg.onpointerleave=null;
  const tooltip=document.getElementById('curve-tooltip');tooltip.hidden=true;
  const legend=document.getElementById('curve-legend');legend.replaceChildren();
  const tokenPoints=bounds?.tokens?.points||[],models=bounds?.tokens?.models||[];
  if(!points.length&&!tokenPoints.length){svg.append(svgNode('text',{x:20,y:45,class:'chart-label'},t('Недостаточно данных для диаграммы')));return;}
  const left=55,right=700,top=35,bottom=215;
  const first=bounds?.first_time??points[0]?.timestamp??tokenPoints[0].timestamp,last=bounds?.final_time??points.at(-1)?.timestamp??tokenPoints.at(-1).timestamp;
  const remaining=point=>Math.max(0,Math.min(100,100-point.used_percent));
  const quotaValues=hiddenCurveSeries.has('quota')?[]:points.map(remaining);
  const quotaLow=quotaValues.length?Math.min(...quotaValues):0;
  const quotaHigh=quotaValues.length?Math.max(...quotaValues):100;
  const quotaPadding=Math.max(1,(quotaHigh-quotaLow)*0.1);
  const quotaFloor=Math.max(0,Math.floor(quotaLow-quotaPadding));
  const quotaCeiling=Math.min(100,Math.ceil(quotaHigh+quotaPadding));
  const series=[{key:'tokens:total',label:t('Всего токенов'),color:themeColor('green'),get:p=>p.total},...models.map(model=>({key:'tokens:'+model,label:model,color:curveModelColor(model),get:p=>p.models[model]||0}))];
  let tokenMax=1;
  for(const row of series) if(!hiddenCurveSeries.has(row.key)) for(const point of tokenPoints) tokenMax=Math.max(tokenMax,row.get(point));
  // log1p preserves zero and remains linear near zero; all token lines share one scale.
  const tokenKnee=1000;
  const tokenTop=Math.log1p(tokenMax/tokenKnee)*1.04;
  const tokenValue=fraction=>tokenKnee*Math.expm1(fraction*tokenTop);
  const compact=value=>new Intl.NumberFormat(locale(),{notation:'compact',maximumFractionDigits:1}).format(value);
  const x=ts=>left+(ts-first)/Math.max(1,last-first)*(right-left),y=value=>bottom-(value-quotaFloor)/(quotaCeiling-quotaFloor)*(bottom-top),ty=value=>bottom-Math.log1p(value/tokenKnee)/tokenTop*(bottom-top);
  const defs=svgNode('defs'),areas=svgNode('g',{'aria-hidden':'true','pointer-events':'none'});svg.append(defs,areas);
  let gradientIndex=0;
  const shadedPath=(coords,color,opacity)=>{
    const path=smoothCurvePath(coords),id='curve-gradient-'+gradientIndex++;
    const gradient=svgNode('linearGradient',{id,gradientUnits:'userSpaceOnUse',x1:0,x2:0,y1:top,y2:bottom});
    gradient.append(svgNode('stop',{offset:'0%','stop-color':color,'stop-opacity':opacity}),svgNode('stop',{offset:'100%','stop-color':color,'stop-opacity':0.015}));defs.append(gradient);
    if(coords.length>1)areas.append(svgNode('path',{d:path+` L ${coords.at(-1)[0]} ${bottom} L ${coords[0][0]} ${bottom} Z`,fill:`url(#${id})`}));
    return path;
  };
  svg.append(svgNode('text',{x:left,y:16,class:'chart-axis-title'},t('Остаток · слева')));
  svg.append(svgNode('text',{x:right,y:16,'text-anchor':'end',class:'chart-axis-title'},t('Токены · логарифмическая шкала')));
  for(const fraction of [0,0.25,0.5,0.75,1]){const yy=bottom-fraction*(bottom-top);svg.append(svgNode('line',{x1:left,x2:right,y1:yy,y2:yy,class:'chart-grid'}));if(quotaValues.length)svg.append(svgNode('text',{x:3,y:yy+4,class:'chart-label'},percent(quotaFloor+(quotaCeiling-quotaFloor)*fraction)));if(tokenPoints.length)svg.append(svgNode('text',{x:right+12,y:yy+4,class:'chart-label'},compact(tokenValue(fraction))));}
  const addLegend=(key,label,color,value)=>{
    const button=document.createElement('button');button.type='button';button.className='curve-series';button.setAttribute('aria-pressed',String(!hiddenCurveSeries.has(key)));
    const swatch=document.createElement('span');swatch.className='curve-swatch';swatch.style.backgroundColor=color;
    const caption=document.createElement('span');caption.textContent=label;
    const amount=document.createElement('strong');amount.textContent=value;
    button.append(swatch,caption,amount);button.addEventListener('click',()=>{if(hiddenCurveSeries.has(key))hiddenCurveSeries.delete(key);else hiddenCurveSeries.add(key);drawCurve(points,bounds);});legend.append(button);
  };
  const hoverSeries=[];
  if(points.length){
    addLegend('quota',t('Остаток лимита'),themeColor('blue'),percent(remaining(points.at(-1))));
    if(!hiddenCurveSeries.has('quota')){
      const groups=new Map();for(const point of points){if(!groups.has(point.reset_at))groups.set(point.reset_at,[]);groups.get(point.reset_at).push(point);}
      for(let i=1;i<points.length;i++){
        const before=points[i-1],after=points[i];
        if(before.reset_at===after.reset_at || remaining(after)<=remaining(before))continue;
        const resetTime=before.reset_at>=before.timestamp && before.reset_at<=after.timestamp?before.reset_at:after.timestamp;
        const marker=svgNode('line',{x1:x(resetTime),x2:x(resetTime),y1:y(remaining(before)),y2:y(remaining(after)),class:'quota-reset'});
        marker.append(svgNode('title',{},t('Сброс недельного лимита')+' · '+dateTime(new Date(resetTime*1000))));
        svg.append(marker);
      }
      for(const values of groups.values()){const line=svgNode('path',{d:shadedPath(values.map(p=>[x(p.timestamp),y(remaining(p))]),themeColor('blue'),0.10),class:'quota-line'});svg.append(line);hoverSeries.push({line,label:t('Остаток лимита'),color:themeColor('blue'),first:x(values[0].timestamp),last:x(values.at(-1).timestamp),format:yy=>percent(quotaFloor+(bottom-yy)/(bottom-top)*(quotaCeiling-quotaFloor))});const lastPoint=values.at(-1);svg.append(svgNode('circle',{cx:x(lastPoint.timestamp),cy:y(remaining(lastPoint)),r:4,class:'quota-point'}));}
    }
  }else{const note=document.createElement('p');note.className='note';note.textContent=t('Снимков недельного счётчика за этот период нет');legend.append(note);}
  if(tokenPoints.length){
    for(const row of series){
      addLegend(row.key,row.label,row.color,number(row.get(tokenPoints.at(-1))));
      if(hiddenCurveSeries.has(row.key))continue;
      const line=svgNode('path',{d:shadedPath(tokenPoints.map(point=>[x(point.timestamp),ty(row.get(point))]),row.color,row.key==='tokens:total'?0.18:0.10),fill:'none',stroke:row.color,'stroke-width':row.key==='tokens:total'?2.7:2,class:'token-line'});
      svg.append(line);
      hoverSeries.push({line,label:row.label,color:row.color,first:x(tokenPoints[0].timestamp),last:x(tokenPoints.at(-1).timestamp),format:yy=>'≈ '+number(Math.max(0,Math.round(tokenValue((bottom-yy)/(bottom-top)))))});
    }
  }else{const note=document.createElement('p');note.className='note';note.textContent=t('Токенов за интервал в локальных журналах нет');legend.append(note);}
  const tickCount=5,shortRange=last-first<=86400;
  for(let i=0;i<=tickCount;i++){
    const ts=first+(last-first)*i/tickCount,xx=x(ts),date=new Date(ts*1000);
    svg.append(svgNode('line',{x1:xx,x2:xx,y1:top,y2:bottom,class:'chart-grid chart-time-grid'}));
    const options={timeZone:'Europe/Moscow',...(shortRange?{hour:'2-digit',minute:'2-digit',hour12:clockFormat===12}:{day:'2-digit',month:'2-digit'})};
    svg.append(svgNode('text',{x:xx,y:238,'text-anchor':i===0?'start':i===tickCount?'end':'middle',class:'chart-time-label'},date.toLocaleString(locale(),options)));
    if(shortRange&&[0,tickCount].includes(i))svg.append(svgNode('text',{x:xx,y:255,'text-anchor':i===0?'start':'end',class:'chart-time-date'},date.toLocaleDateString(locale(),{timeZone:'Europe/Moscow',day:'2-digit',month:'2-digit'})));
  }
  const crosshair=svgNode('g',{'pointer-events':'none',visibility:'hidden','aria-hidden':'true'});svg.append(crosshair);
  const hideHover=()=>{crosshair.setAttribute('visibility','hidden');tooltip.hidden=true;};
  svg.onpointerleave=hideHover;
  svg.onpointermove=event=>{
    const rect=svg.getBoundingClientRect(),xx=(event.clientX-rect.left)/rect.width*800,yy=(event.clientY-rect.top)/rect.height*260;
    if(xx<left||xx>right||yy<top||yy>bottom){hideHover();return;}
    crosshair.replaceChildren(svgNode('line',{x1:xx,x2:xx,y1:top,y2:bottom,class:'curve-crosshair'}));crosshair.setAttribute('visibility','visible');
    const stamp=first+(xx-left)/(right-left)*(last-first);
    const heading=document.createElement('div');heading.className='curve-tooltip-time';heading.textContent=new Date(stamp*1000).toLocaleString(locale(),{timeZone:'Europe/Moscow',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',hour12:clockFormat===12});tooltip.replaceChildren(heading);
    let count=0;
    for(const row of hoverSeries){
      if(xx<row.first||xx>row.last)continue;
      let low=0,high=row.line.getTotalLength();
      for(let i=0;i<22;i++){const mid=(low+high)/2;if(row.line.getPointAtLength(mid).x<xx)low=mid;else high=mid;}
      const point=row.line.getPointAtLength((low+high)/2);
      crosshair.append(svgNode('circle',{cx:xx,cy:point.y,r:4,fill:row.color,stroke:'white','stroke-width':2}));
      const item=document.createElement('div');item.className='curve-tooltip-row';
      const swatch=document.createElement('span');swatch.className='curve-swatch';swatch.style.backgroundColor=row.color;
      const label=document.createElement('span');label.textContent=row.label;
      const value=document.createElement('strong');value.textContent=row.format(point.y);item.append(swatch,label,value);tooltip.append(item);count++;
    }
    if(!count){hideHover();return;}
    tooltip.hidden=false;
    const plot=svg.parentElement.getBoundingClientRect(),px=event.clientX-plot.left,py=event.clientY-plot.top;
    tooltip.style.left=Math.max(0,Math.min(plot.width-tooltip.offsetWidth,px+18+tooltip.offsetWidth>plot.width?px-tooltip.offsetWidth-18:px+18))+'px';
    tooltip.style.top=Math.max(0,Math.min(plot.height-tooltip.offsetHeight,py-tooltip.offsetHeight-12))+'px';
  };
}
function drawQuotaModels(rows) {
  const container=document.getElementById('quota-bars');container.replaceChildren();
  if(!rows.length){const empty=document.createElement('p');empty.className='note';empty.textContent=t('Недостаточно данных для диаграммы');container.append(empty);return;}
  const maximum=Math.max(...rows.map(row=>row.value),0.001);
  for(const row of rows){
    const card=document.createElement('article');card.className='model-usage '+(row.label.includes('astra')?'model-astra':'model-sol');
    const header=document.createElement('div');header.className='model-usage-heading';
    const name=document.createElement('h3');name.textContent=row.label;
    const share=document.createElement('strong');share.className='model-usage-share';share.textContent=row.display;header.append(name,share);
    const track=document.createElement('div');track.className='model-usage-track';track.setAttribute('aria-hidden','true');
    const bar=document.createElement('div');bar.className='model-usage-fill';bar.style.width=(row.value/maximum*100)+'%';track.append(bar);
    const components=document.createElement('dl');components.className='model-usage-components';
    for(const part of [{label:t('Всего'),value:row.total},...row.components]){const cell=document.createElement('div');const label=document.createElement('dt');label.textContent=part.label;const value=document.createElement('dd');value.textContent=number(part.value);cell.append(label,value);components.append(cell);}
    card.append(header,track,components);container.append(card);
  }
}
