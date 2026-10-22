import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'
import { motion } from 'framer-motion'
import { Area, AreaChart, ResponsiveContainer } from 'recharts'
import { AlertCircle, ArrowDownRight, ArrowUpRight, LoaderCircle, Plus, Sparkles } from 'lucide-react'
import { money } from '../lib/api'

export function Button({ children, variant='primary', className='', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary'|'secondary'|'ghost'|'danger' }) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>
}

export function SectionTitle({ title, subtitle, action }: {title:string; subtitle?:string; action?:ReactNode}) {
  return <div className="section-title"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>
}

export function Panel({ children, className='', ...props }: HTMLAttributes<HTMLDivElement>) {
  return <section className={`panel ${className}`} {...props}>{children}</section>
}

export function EmptyState({ title='Rien à afficher', text='Les informations apparaîtront ici dès qu’elles seront disponibles.', icon: Icon=Sparkles }: {title?:string;text?:string;icon?:typeof Sparkles}) {
  return <div className="empty-state"><div className="empty-icon"><Icon size={21}/></div><strong>{title}</strong><p>{text}</p></div>
}

export function LoadingState() {
  return <div className="loading-state"><LoaderCircle className="spin" size={20}/> Chargement de vos données…</div>
}

export function ErrorState({ error }: {error:unknown}) {
  return <div className="error-state"><AlertCircle size={17}/><span>{error instanceof Error ? error.message : 'Une erreur est survenue.'}</span></div>
}

export function Modal({ title, subtitle, onClose, children, wide=false }: {title:string;subtitle?:string;onClose:()=>void;children:ReactNode;wide?:boolean}) {
  return <div className="modal-overlay" role="presentation" onMouseDown={e => e.target === e.currentTarget && onClose()}><motion.div className={`modal-card ${wide?'modal-wide':''}`} initial={{opacity:0,y:12,scale:.98}} animate={{opacity:1,y:0,scale:1}} exit={{opacity:0,y:8}} role="dialog" aria-modal="true" aria-label={title}><div className="modal-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button className="icon-button" onClick={onClose} aria-label="Fermer">×</button></div>{children}</motion.div></div>
}

export function MetricCard({ label, value, numeric, change, detail, color='orange', data=[] }: {label:string;value:string;numeric?:number;change?:number|null;detail?:string;color?:'orange'|'green'|'ink'|'blue';data?:number[]}) {
  const rising = (change ?? 0) >= 0
  const chartData = (data.length ? data : [24,30,22,36,32,45,41,52]).map((v,i) => ({i,v}))
  return <motion.div className={`metric-card metric-${color}`} initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} transition={{duration:.35}} whileHover={{y:-4,transition:{duration:.18}}}>
    <div className="metric-top"><span>{label}</span><span className="metric-more">•••</span></div>
    <div className="metric-value">{numeric !== undefined ? <AnimatedNumber value={numeric}/> : value}</div>
    <div className="metric-foot"><div className={`metric-change ${change === null || change === undefined ? 'neutral' : rising ? 'positive' : 'negative'}`}>{change === null || change === undefined ? <span>—</span> : rising ? <ArrowUpRight size={13}/> : <ArrowDownRight size={13}/>}<span>{change === null || change === undefined ? 'Nouvelle période' : `${Math.abs(change)} %`}</span></div><span className="metric-detail">{detail || 'vs période précédente'}</span></div>
    <div className="metric-spark"><ResponsiveContainer width="100%" height="43"><AreaChart data={chartData}><defs><linearGradient id={`metric-${label.replace(/\W/g,'')}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="currentColor" stopOpacity={.21}/><stop offset="100%" stopColor="currentColor" stopOpacity={0}/></linearGradient></defs><Area type="monotone" dataKey="v" stroke="currentColor" strokeWidth={1.7} fill={`url(#metric-${label.replace(/\W/g,'')})`} dot={false}/></AreaChart></ResponsiveContainer></div>
  </motion.div>
}

function AnimatedNumber({ value }: {value:number}) {
  return <motion.span initial={{opacity:.4}} animate={{opacity:1}} key={value} transition={{duration:.28}}>{new Intl.NumberFormat('fr-FR',{maximumFractionDigits:0}).format(value)} <small>FCFA</small></motion.span>
}

export function Money({ value, className='' }: {value:number;className?:string}) { return <span className={className}>{money(value)}</span> }

export function AddButton({ children='Nouvelle entrée', ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <Button {...props}><Plus size={16}/>{children}</Button>
}

