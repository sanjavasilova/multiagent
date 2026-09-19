import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [tab, setTab] = useState('analysis')
  const [questions, setQuestions] = useState([])
  const [runs, setRuns] = useState([])
  const [run, setRun] = useState(null)
  const [comparison, setComparison] = useState(null)
  const [question, setQuestion] = useState('')
  const [mode, setMode] = useState('debate')
  const [rounds, setRounds] = useState(2)
  const [compareCount, setCompareCount] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const refresh = () => fetch(`${API}/experiments`).then(r => r.json()).then(setRuns)
  useEffect(() => { fetch(`${API}/questions`).then(r => r.json()).then(setQuestions); refresh() }, [])

  const execute = async () => {
    setLoading(true); setError('')
    try {
      const body = { mode, rounds, question_ids: question.trim() ? undefined : questions.map(q => q.id), question: question.trim() || undefined, name: question.trim() || 'Dataset evaluation' }
      const response = await fetch(`${API}/experiments/run`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Experiment failed')
      setRun(data); refresh(); setTab('evaluation')
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }

  const compare = async () => {
    setLoading(true); setError(''); setComparison(null); setRun(null); setTab('evaluation')
    try {
      const count = compareCount ?? questions.length
      const response = await fetch(`${API}/experiments/compare`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ rounds, question_ids: questions.slice(0, Math.max(1, Math.min(count, questions.length))).map(q => q.id), name: 'Paired comparison' }) })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || 'Comparison failed')
      setComparison(data); setRun(data.debate); refresh(); setTab('evaluation')
    } catch (err) { setError(err.message); setTab('evaluation') } finally { setLoading(false) }
  }

  return <div><header><div className="brand">✦ UniEval</div><nav>
    <button className={tab === 'analysis' ? 'active' : ''} onClick={() => setTab('analysis')}>Analysis</button>
    <button className={tab === 'evaluation' ? 'active' : ''} onClick={() => setTab('evaluation')}>Evaluation</button>
  </nav><span className="status">● {import.meta.env.VITE_API_URL ? 'Configured API' : 'Demo provider'}</span></header>
  <main>{tab === 'analysis' ? <section><div className="hero"><p className="eyebrow">RESEARCH WORKBENCH</p><h1>Measure reasoning,<br/><em>not just answers.</em></h1><p>Compare a direct answer with an inspectable solver–critic–revision–judge debate.</p></div>
    <div className="card controls"><label>Question (optional)<textarea value={question} onChange={e => setQuestion(e.target.value)} placeholder="Leave blank to run the 65-question dataset" /></label>
      <label>Method<select value={mode} onChange={e => setMode(e.target.value)}><option value="debate">Multi-agent debate</option><option value="single">Single agent</option></select></label>
      <label>Rounds<input type="number" min="1" max="5" value={rounds} onChange={e => setRounds(Number(e.target.value))}/></label>
      <label>Comparison size<input type="number" min="1" max={questions.length || 65} value={compareCount ?? (questions.length || 65)} onChange={e => setCompareCount(Number(e.target.value))} title="How many questions the paired comparison should run" /></label>
      <button className="primary" onClick={execute} disabled={loading}>{loading ? 'Running…' : 'Run analysis →'}</button>
      <button className="secondary" onClick={compare} disabled={loading}>Run paired comparison</button></div>
    {error && <div className="error">{error}</div>}<div className="grid"><div className="card"><small>QUESTION BANK</small><strong>{questions.length}</strong><span>seeded reference questions</span></div><div className="card"><small>PIPELINE</small><strong>{mode === 'debate' ? '4 agents' : '1 agent'}</strong><span>outputs stored for inspection</span></div><div className="card"><small>STORAGE</small><strong>SQLite</strong><span>reproducible experiment records</span></div></div></section>
    : <section><div className="section-head"><div><p className="eyebrow">RESULTS</p><h2>Evaluation runs</h2></div>{run && <div className="score">{run.summary}</div>}</div>
      {loading && <div className="card progress"><b>Running paired comparison...</b><span>Both methods are being evaluated on the selected questions. This can take time with a hosted provider.</span></div>}
      {error && <div className="error">{error}</div>}
      {comparison && <Comparison data={comparison} />}{run ? <Results run={run} /> : !loading && <div className="empty">Run an experiment to inspect agent outputs and objective matching.</div>}
      <h3>Previous experiments</h3><div className="table">{runs.map(r => <div className="row" key={r.id}><span>#{r.id} {r.name}</span><span>{r.mode} · {r.created_at.slice(0, 10)}</span></div>)}</div></section>}</main></div>
}

function Comparison({ data }) {
  const rows = [['Accuracy', `${data.single.metrics.accuracy}%`, `${data.debate.metrics.accuracy}%`], ['Avg. time', `${data.single.metrics.avg_time_ms} ms`, `${data.debate.metrics.avg_time_ms} ms`], ['LLM calls', data.single.metrics.avg_llm_calls, data.debate.metrics.avg_llm_calls], ['Avg. tokens', data.single.metrics.avg_tokens, data.debate.metrics.avg_tokens]]
  return <div className="comparison card"><h3>Paired method comparison</h3><div className="metrics-table"><div><b>Metric</b><b>Single agent</b><b>Debate</b></div>{rows.map(row => <div key={row[0]}><span>{row[0]}</span><span>{row[1]}</span><span>{row[2]}</span></div>)}</div><p className="delta">Accuracy change: <b>{data.comparison.accuracy_change_percentage_points > 0 ? '+' : ''}{data.comparison.accuracy_change_percentage_points} percentage points</b>; debate cost changed by {data.comparison.call_change_percentage}% calls.</p></div>
}

function Results({ run }) {
  return <><div className="metric-strip">{Object.entries(run.metrics || {}).map(([key, value]) => <div key={key}><small>{key.replaceAll('_', ' ')}</small><b>{value}{key === 'accuracy' ? '%' : ''}</b></div>)}</div><div className="results">{run.outputs.map(o => <details key={o.question_id}><summary><b>Q{o.question_id}</b> {o.question}<span className={o.status === 'error' ? 'bad' : o.evaluated ? (o.correct ? 'good' : 'bad') : 'neutral'}>{o.status === 'error' ? 'ERROR' : o.evaluated ? (o.correct ? 'MATCH' : 'MISS') : 'NOT EVALUATED'}</span></summary><div className="answer"><p><b>Final answer:</b> {o.final_answer}</p><p><b>Reference:</b> {o.reference_answer || 'Not available for custom question'}</p><p className="metadata">{o.execution_time_ms} ms · {o.llm_calls} calls · {o.token_usage} tokens · {o.category}</p>{Object.entries(o.agents || {}).map(([k, v]) => <div className="agent" key={k}><small>{k === 'rounds' ? 'Debate rounds (answer → critique → revision)' : k}</small><pre>{typeof v === 'string' ? v : JSON.stringify(v, null, 2)}</pre></div>)}</div></details>)}</div></>
}

createRoot(document.getElementById('root')).render(<App />)
