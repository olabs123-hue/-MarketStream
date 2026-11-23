import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Activity, ArrowDownRight, ArrowUpRight, CircleDot, RefreshCw, Wifi, WifiOff} from 'lucide-react';
import {AreaChart, Area, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip} from 'recharts';
import './style.css';

type Tick={symbol:string;sequence:number;timestamp:string;price:number;change_pct:number;bids:number[][];asks:number[][];spread:number;processor?:string;simulated:boolean};
const symbols=['BTC-USD','ETH-USD','SOL-USD'];
const money=(n:number)=>n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
function App(){
 const [symbol,setSymbol]=useState('BTC-USD'),[tick,setTick]=useState<Tick|null>(null),[connected,setConnected]=useState(false),[history,setHistory]=useState<{n:number;price:number}[]>([]),[error,setError]=useState('');
 useEffect(()=>{
  let active=true;let socket:WebSocket|null=null;let timeout:number|undefined;let attempt=0;
  setTick(null);setHistory([]);setConnected(false);setError('');
  const protocol=location.protocol==='https:'?'wss':'ws';
  const base=import.meta.env.VITE_WS_URL || `${protocol}://${location.host}`;
  const connect=()=>{
   if(!active)return;
   socket=new WebSocket(`${base}/ws/${symbol}`);
   socket.onopen=()=>{if(active){setConnected(true);setError('');attempt=0}};
   socket.onmessage=(event)=>{try{const next:Tick=JSON.parse(event.data);if(!active||next.symbol!==symbol)return;setTick(next);setHistory(h=>[...h.slice(-59),{n:next.sequence,price:next.price}])}catch{setError('Invalid stream message')}};
   socket.onerror=()=>{if(active)setError('Stream connection interrupted')};
   socket.onclose=()=>{if(active){setConnected(false);attempt++;timeout=window.setTimeout(connect,Math.min(1000*2**attempt,10000))}};
  };
  connect();return()=>{active=false;if(timeout!==undefined)clearTimeout(timeout);socket?.close()};
 },[symbol]);
 const rising=(tick?.change_pct??0)>=0;
 return <div className="app"><aside><div className="logo"><Activity size={25}/> Market<span>Stream</span></div><div className="nav-caption">SIMULATION TERMINAL</div><div className="nav-selected"><CircleDot size={16}/> Markets</div><div className="nav-foot">A portfolio engineering demo.<br/>Not a trading platform.</div></aside><main>
 <header><div><p className="eyebrow">MARKET DATA / OVERVIEW</p><h1>Market overview</h1><p className="subtitle">Streaming, simulated order-book data</p></div><div className={'connection '+(connected?'online':'offline')}>{connected?<Wifi size={16}/>:<WifiOff size={16}/>} {connected?'Stream connected':'Reconnecting'}</div></header>
 <div className="warning">SIMULATED DATA ONLY · Not live market prices · Not financial advice</div>
 <div className="selectors">{symbols.map(s=><button key={s} className={s===symbol?'selected':''} onClick={()=>setSymbol(s)}>{s}</button>)}</div>
 <section className="hero"><div><p className="eyebrow">{symbol} / DEMO PRICE</p><div className="price">{tick?'$'+money(tick.price):'Connecting…'}</div><div className={'delta '+(rising?'up':'down')}>{rising?<ArrowUpRight size={18}/>:<ArrowDownRight size={18}/>} {tick?`${tick.change_pct.toFixed(3)}% vs mock reference`:'Awaiting first tick'}</div></div><div className="meta"><span>Latest event</span><strong>{tick?new Date(tick.timestamp).toLocaleTimeString():'—'}</strong><span>Sequence</span><strong>{tick?.sequence??'—'}</strong><span>Bid–ask spread</span><strong>{tick?'$'+money(tick.spread):'—'}</strong></div></section>
 <div className="columns"><section className="panel"><div className="panel-title"><div><h2>Price movement</h2><p>Last {history.length} streamed observations</p></div><RefreshCw size={17}/></div><div className="chart">{history.length?<ResponsiveContainer width="100%" height="100%"><AreaChart data={history} margin={{top:20,right:12,left:-20,bottom:0}}><defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#5f8bff" stopOpacity={.3}/><stop offset="1" stopColor="#5f8bff" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#263148" strokeDasharray="3 3"/><XAxis dataKey="n" stroke="#8a9bb9" tick={{fontSize:11}}/><YAxis domain={['auto','auto']} stroke="#8a9bb9" tick={{fontSize:11}} tickFormatter={(n:number)=>n.toFixed(0)}/><Tooltip formatter={(v)=>'$'+money(Number(v))}/><Area type="monotone" dataKey="price" stroke="#5f8bff" strokeWidth={2.5} fill="url(#fill)" isAnimationActive={false}/></AreaChart></ResponsiveContainer>:<div className="empty">Waiting for streaming observations…</div>}</div></section>
 <section className="panel book"><div className="panel-title"><div><h2>Order-book depth</h2><p>Synthetic level-2 snapshot</p></div><span className="small-tag">8 levels</span></div><div className="book-head"><span>Bid price</span><span>Size</span><span>Ask price</span><span>Size</span></div>{Array.from({length:8},(_,i)=><div className="book-row" key={i}><span className="bid">{tick?money(tick.bids[i][0]):'—'}</span><span>{tick?tick.bids[i][1]:'—'}</span><span className="ask">{tick?money(tick.asks[i][0]):'—'}</span><span>{tick?tick.asks[i][1]:'—'}</span></div>)}</section></div>
 {error&&<div className="error">{error}. The client will reconnect automatically.</div>}
 <footer>MarketStream v0.6 · Simulated shared WebSocket feed · C++ order-book validation · Bounded replay</footer>
 </main></div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
