import React, { useEffect, useState } from 'react';
import {
  BookOpen,
  Calendar,
  Check,
  Database,
  ExternalLink,
  Layers,
  Play,
  RefreshCw,
  Sparkles,
  Terminal,
  CheckCircle2,
  FolderOpen,
} from 'lucide-react';
import { apiFetch, API_V1 } from '../api/client';

const SAMPLE_SQL = `SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name;`;

const SAMPLE_PYSPARK = `from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("UES_Quick_Check").getOrCreate()
df = spark.createDataFrame([(1, "bronze"), (2, "silver"), (3, "gold")], ["id", "layer"])
df.show()
print("Spark version:", spark.version)
spark.stop()`;

export default function DataEngineeringView({ user }) {
  const [subTab, setSubTab] = useState('sql');
  const [overview, setOverview] = useState(null);
  const [sqlText, setSqlText] = useState(SAMPLE_SQL);
  const [sqlResult, setSqlResult] = useState(null);
  const [sqlError, setSqlError] = useState(null);
  const [pysparkCode, setPysparkCode] = useState(SAMPLE_PYSPARK);
  const [pysparkResult, setPysparkResult] = useState(null);
  const [previewObj, setPreviewObj] = useState(null);
  const [notebookUrl, setNotebookUrl] = useState('/services/databricks/');
  const [roadmap, setRoadmap] = useState(null);
  const [selectedPhase, setSelectedPhase] = useState('all');
  const [selectedDayNum, setSelectedDayNum] = useState(1);
  const [dayNotes, setDayNotes] = useState('');
  const [busy, setBusy] = useState(false);

  const isAdmin = user?.role === 'admin';

  const loadDE = async () => {
    try {
      const data = await apiFetch(`${API_V1}/data-engineering/overview`);
      setOverview(data);
    } catch (err) {
      console.error(err);
    }
  };

  const loadDeRoadmap = async () => {
    try {
      const rm = await apiFetch(`${API_V1}/data-engineering/roadmap`);
      setRoadmap(rm);
      const existing = rm.progress?.[selectedDayNum];
      setDayNotes(existing?.notes || '');
    } catch (err) {
      console.error(err);
    }
  };

  const saveDayProgress = async (dayNum, completed, notes) => {
    try {
      await apiFetch(`${API_V1}/data-engineering/roadmap/${dayNum}/progress`, {
        method: 'PUT',
        body: JSON.stringify({ completed, notes }),
      });
      await loadDeRoadmap();
    } catch (err) {
      alert(err.message);
    }
  };

  const launchPracticeSnippet = (dayObj) => {
    if (!dayObj?.practice_snippet) return;
    if (dayObj.practice_type === 'pyspark') {
      setPysparkCode(dayObj.practice_snippet);
      setSubTab('pyspark');
    } else {
      setSqlText(dayObj.practice_snippet);
      setSubTab('sql');
    }
  };

  useEffect(() => {
    loadDE();
  }, []);

  const runSql = async () => {
    setBusy(true);
    setSqlError(null);
    try {
      const res = await apiFetch(`${API_V1}/data-engineering/sql/execute`, {
        method: 'POST',
        body: JSON.stringify({ sql: sqlText, limit: 200 }),
      });
      setSqlResult(res);
    } catch (err) {
      setSqlError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const runPySpark = async () => {
    setBusy(true);
    try {
      const res = await apiFetch(`${API_V1}/spark/execute`, {
        method: 'POST',
        body: JSON.stringify({ code: pysparkCode, app_name: 'UES_PySpark_Studio' }),
      });
      setPysparkResult(res);
    } catch (err) {
      setPysparkResult({ status: 'error', stderr: err.message });
    } finally {
      setBusy(false);
    }
  };

  const triggerDag = async (dagId) => {
    setBusy(true);
    try {
      await apiFetch(`${API_V1}/airflow/dags/${dagId}/trigger`, { method: 'POST' });
      await loadDE();
    } catch (err) {
      alert(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handlePreviewObject = async (bucket, key) => {
    try {
      const res = await apiFetch(`${API_V1}/data-engineering/datalake/preview?bucket=${encodeURIComponent(bucket)}&key=${encodeURIComponent(key)}`);
      setPreviewObj(res);
    } catch (err) {
      alert(err.message);
    }
  };

  const pg = overview?.postgres_dw || {};
  const medallion = overview?.medallion || {};
  const spark = overview?.spark || {};
  const airflow = overview?.airflow || {};

  return (
    <div className="view-container">
      <div className="section-header">
        <div>
          <h2 className="section-title"><Database size={18} style={{ color: 'var(--apple-coral)' }} /> Data Engineering Studio</h2>
          <p className="section-subtitle">SQL Studio · PySpark 4.2 · Spark & Iceberg · Airflow · JupyterLab · MinIO Medallion · Data Quality & CDC</p>
        </div>
        <button className="apple-btn apple-btn-secondary" onClick={loadDE}><RefreshCw size={12} /> Refresh</button>
      </div>

      <div className="ues-subtabs">
        {[
          { id: 'sql', label: 'SQL Studio (Postgres DW)' },
          { id: 'pyspark', label: 'PySpark & Iceberg / Delta' },
          { id: 'airflow', label: 'Airflow & DAGs' },
          { id: 'lakehouse', label: 'MinIO & Medallion / DQ / CDC' },
          { id: 'jupyter', label: 'JupyterLab Notebooks' },
          { id: 'roadmap', label: '30-Day DE Roadmap & Interviews' },
        ].map((t) => (
          <button
            key={t.id}
            className={`ues-subtab ${subTab === t.id ? 'active' : ''}`}
            onClick={() => {
              setSubTab(t.id);
              if (t.id === 'roadmap' && !roadmap) loadDeRoadmap();
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {subTab === 'sql' && (
        <div className="ues-grid-2">
          <div className="studio-section-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="studio-section-title">PostgreSQL DW SQL Studio ({pg.available ? `Connected · ${pg.latency_ms}ms` : 'Offline'})</span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                Conns: {pg.connections || 0}/{pg.max_connections || 0} ({pg.connection_utilization_pct || 0}%)
              </span>
            </div>
            <textarea className="copilot-textarea" rows={7} value={sqlText} onChange={(e) => setSqlText(e.target.value)} style={{ fontFamily: 'monospace', fontSize: '0.8rem' }} />
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <button className="apple-btn apple-btn-primary" onClick={runSql} disabled={busy}>
                <Play size={12} /> Run Query
              </button>
              <button className="apple-btn apple-btn-secondary" onClick={() => setSqlText('SELECT * FROM synapse_dw.fact_customer_revenue LIMIT 25;')}>
                Fact Revenue
              </button>
              <button className="apple-btn apple-btn-secondary" onClick={() => setSqlText('SELECT * FROM synapse_dw.fact_transactions ORDER BY transaction_id DESC LIMIT 25;')}>
                Fact Transactions
              </button>
              <button className="apple-btn apple-btn-secondary" onClick={() => setSqlText('SELECT pid, usename, state, query FROM pg_stat_activity WHERE datname = current_database();')}>
                pg_stat_activity
              </button>
              <a href="/services/synapse/" target="_blank" rel="noreferrer" className="apple-btn apple-btn-secondary">
                <ExternalLink size={12} /> pgAdmin 4
              </a>
            </div>
            {sqlError && <div className="ues-alert-banner danger">{sqlError}</div>}
            {sqlResult && (
              <div style={{ maxHeight: '300px', overflow: 'auto', marginTop: '0.5rem' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--apple-mint)', marginBottom: '4px' }}>
                  {sqlResult.row_count} rows · {sqlResult.duration_ms} ms
                </div>
                {sqlResult.columns?.length > 0 ? (
                  <table className="apple-table">
                    <thead>
                      <tr>{sqlResult.columns.map((c) => <th key={c}>{c}</th>)}</tr>
                    </thead>
                    <tbody>
                      {sqlResult.rows.map((r, i) => (
                        <tr key={i}>{sqlResult.columns.map((c) => <td key={c}>{r[c] ?? 'NULL'}</td>)}</tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div style={{ fontSize: '0.8rem' }}>{sqlResult.message}</div>
                )}
              </div>
            )}
          </div>

          <div className="studio-section-card">
            <span className="studio-section-title">Warehouse Tables ({pg.tables?.length || 0})</span>
            <table className="apple-table">
              <thead>
                <tr><th>Schema</th><th>Table</th><th>Type</th></tr>
              </thead>
              <tbody>
                {(pg.tables || []).map((t, i) => (
                  <tr key={i} style={{ cursor: 'pointer' }} onClick={() => setSqlText(`SELECT * FROM ${t.schema}.${t.name} LIMIT 50;`)}>
                    <td><code>{t.schema}</code></td>
                    <td style={{ fontWeight: 600 }}>{t.name}</td>
                    <td style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{t.type}</td>
                  </tr>
                ))}
                {(!pg.tables || pg.tables.length === 0) && (
                  <tr><td colSpan={3} style={{ color: 'var(--text-muted)' }}>No user tables yet — run Medallion or Incremental DAG/Notebook.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {subTab === 'pyspark' && (
        <div className="ues-grid-2">
          <div className="studio-section-card">
            <span className="studio-section-title">PySpark 4.2 Studio (Executes inside spark-processing container)</span>
            <textarea className="copilot-textarea" rows={10} value={pysparkCode} onChange={(e) => setPysparkCode(e.target.value)} style={{ fontFamily: 'monospace', fontSize: '0.78rem' }} />
            <div style={{ display: 'flex', gap: '8px' }}>
              {isAdmin && (
                <button className="apple-btn apple-btn-primary" onClick={runPySpark} disabled={busy}>
                  <Play size={12} /> Execute PySpark
                </button>
              )}
              <a href="http://localhost:8080" target="_blank" rel="noreferrer" className="apple-btn apple-btn-secondary">
                <ExternalLink size={12} /> Spark UI (:8080)
              </a>
            </div>
            {pysparkResult && (
              <pre className="ues-terminal-out" style={{ marginTop: '0.75rem' }}>
                {pysparkResult.stdout || ''}
                {pysparkResult.stderr ? `\n[STDERR]\n${pysparkResult.stderr}` : ''}
              </pre>
            )}
          </div>

          <div className="studio-section-card">
            <span className="studio-section-title">Apache Iceberg REST Catalog & Spark Applications</span>
            <div style={{ fontSize: '0.78rem', marginBottom: '0.75rem' }}>
              Spark Status: <strong style={{ color: spark.spark_available ? 'var(--apple-mint)' : 'var(--apple-coral)' }}>{spark.spark_available ? 'Available' : 'Stopped (Start Profile 2)'}</strong>
              {' · '}Iceberg REST: <strong style={{ color: spark.iceberg_available ? 'var(--apple-mint)' : 'var(--apple-coral)' }}>{spark.iceberg_available ? 'Connected' : 'Unavailable'}</strong>
            </div>
            {(spark.iceberg_namespaces || []).map((ns) => (
              <div key={ns.namespace} className="reference-card-item" style={{ marginBottom: '0.5rem' }}>
                <div className="reference-card-title">Namespace: {ns.namespace}</div>
                <div className="reference-card-desc">Tables: {ns.tables.length ? ns.tables.join(', ') : 'None yet'}</div>
              </div>
            ))}
            <span className="studio-section-title" style={{ marginTop: '0.5rem' }}>Active / Completed Spark Apps ({spark.applications?.length || 0})</span>
            {(spark.applications || []).map((app, i) => (
              <div key={i} className="reference-card-item">
                <div className="reference-card-title">{app.name || app.id}</div>
                <div className="reference-card-desc">State: {app.state || 'RUNNING'} · ID: {app.id}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {subTab === 'airflow' && (
        <div className="studio-section-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <span className="studio-section-title">
              Apache Airflow Orchestration ({airflow.available ? 'Connected' : 'Offline — Start Profile 2'})
            </span>
            <a href="/services/airflow/" target="_blank" rel="noreferrer" className="apple-btn apple-btn-secondary">
              <ExternalLink size={12} /> Open Airflow UI
            </a>
          </div>
          <table className="apple-table">
            <thead>
              <tr><th>DAG ID</th><th>Schedule</th><th>Paused</th><th>Last Run State</th><th>Action</th></tr>
            </thead>
            <tbody>
              {(airflow.dags || []).map((d) => (
                <tr key={d.dag_id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{d.dag_id}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{d.description}</div>
                  </td>
                  <td style={{ fontSize: '0.74rem' }}>{d.schedule || 'Manual'}</td>
                  <td>{d.is_paused === null ? '-' : d.is_paused ? 'Paused' : 'Active'}</td>
                  <td>
                    <span className={`hero-pill-badge ${d.last_run_state === 'success' ? 'primary' : 'secondary'}`}>
                      {d.last_run_state}
                    </span>
                  </td>
                  <td>
                    {isAdmin && airflow.available && (
                      <button className="apple-btn apple-btn-primary" disabled={busy} onClick={() => triggerDag(d.dag_id)} style={{ padding: '4px 10px', fontSize: '0.72rem' }}>
                        <Play size={11} /> Trigger
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {subTab === 'lakehouse' && (
        <div className="ues-grid-2">
          <div className="studio-section-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="studio-section-title">MinIO Medallion Architecture (Bronze / Silver / Gold / Warehouse)</span>
              <a href="/services/datalake/" target="_blank" rel="noreferrer" className="apple-btn apple-btn-secondary">
                <ExternalLink size={12} /> MinIO Console
              </a>
            </div>
            {['bronze', 'silver', 'gold', 'warehouse'].map((b) => {
              const info = medallion[b] || { object_count: 0, size_mb: 0, objects: [] };
              return (
                <div key={b} className="reference-card-item" style={{ marginBottom: '0.6rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <strong style={{ textTransform: 'uppercase' }}>{b} Layer</strong>
                    <span style={{ fontSize: '0.74rem', color: 'var(--apple-blue)' }}>{info.object_count} objects · {info.size_mb} MB</span>
                  </div>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '0.4rem' }}>
                    {(info.objects || []).slice(0, 8).map((o) => (
                      <button key={o.key} className="copilot-chip" onClick={() => handlePreviewObject(b, o.key)}>
                        <FolderOpen size={10} /> {o.key}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
            {previewObj && (
              <div style={{ marginTop: '0.75rem' }}>
                <div style={{ fontSize: '0.74rem', color: 'var(--apple-mint)', marginBottom: '4px' }}>
                  Preview: {previewObj.bucket}/{previewObj.key}
                </div>
                <pre className="ues-terminal-out">{previewObj.content}</pre>
              </div>
            )}
          </div>

          <div className="studio-section-card">
            <span className="studio-section-title">Data Quality Rules & CDC Pipelines</span>
            {(overview?.data_quality || []).map((dq, i) => (
              <div key={i} className="reference-card-item" style={{ marginBottom: '0.5rem' }}>
                <div className="reference-card-title">
                  <CheckCircle2 size={13} style={{ color: dq.status === 'pass' ? 'var(--apple-mint)' : 'var(--apple-amber)' }} />
                  {dq.rule} ({dq.layer})
                </div>
                <div className="reference-card-desc">{dq.detail}</div>
              </div>
            ))}
            <span className="studio-section-title" style={{ marginTop: '0.75rem' }}>CDC & Streaming Pipelines</span>
            {(overview?.cdc_pipelines || []).map((p, i) => (
              <div key={i} className="reference-card-item" style={{ marginBottom: '0.5rem' }}>
                <div className="reference-card-title">{p.name}</div>
                <div className="reference-card-desc">Status: {p.status} · {p.target_table || p.notebook}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {subTab === 'jupyter' && (
        <div className="ues-grid-2" style={{ gridTemplateColumns: '320px 1fr' }}>
          <div className="studio-section-card">
            <span className="studio-section-title">TPC-H & Lab Notebooks ({spark.notebooks?.length || 0})</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', maxHeight: '620px', overflowY: 'auto' }}>
              {(spark.notebooks || []).map((nb) => (
                <div key={nb.name} className="reference-card-item" onClick={() => setNotebookUrl(nb.url)}>
                  <div className="reference-card-title"><Sparkles size={12} style={{ color: 'var(--apple-coral)' }} /> {nb.name}</div>
                  <div className="reference-card-desc">{nb.size_kb} KB</div>
                </div>
              ))}
            </div>
          </div>
          <div className="studio-section-card" style={{ padding: 0, overflow: 'hidden', minHeight: '620px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.6rem 0.9rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{notebookUrl}</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <a href={notebookUrl} target="_blank" rel="noreferrer" className="apple-btn apple-btn-primary" style={{ padding: '4px 10px', fontSize: '0.72rem' }}>
                  <ExternalLink size={12} /> Open in New Tab
                </a>
                <a href="/services/databricks/tree" target="_blank" rel="noreferrer" className="apple-btn apple-btn-secondary" style={{ padding: '4px 10px', fontSize: '0.72rem' }}>
                  <ExternalLink size={12} /> Full File Tree
                </a>
              </div>
            </div>
            <iframe src={notebookUrl} title="JupyterLab" style={{ width: '100%', height: '620px', border: 'none', background: '#111' }} />
          </div>
        </div>
      )}

      {subTab === 'roadmap' && (() => {
        const days = roadmap?.days || [];
        const phases = roadmap?.phases || [];
        const progress = roadmap?.progress || {};
        const filteredDays = selectedPhase === 'all' ? days : days.filter((d) => String(d.phase) === String(selectedPhase));
        const activeDay = days.find((d) => d.day === selectedDayNum) || filteredDays[0] || days[0];
        const dayProg = activeDay ? (progress[activeDay.day] || { completed: false, notes: '' }) : { completed: false, notes: '' };
        const completedCount = Object.values(progress).filter((p) => p.completed).length;

        const renderLessonBlocks = (md) => {
          if (!md) return null;
          return md.split(/(```[\s\S]*?```)/g).map((part, idx) => {
            if (part.startsWith('```')) {
              const lines = part.split('\n');
              const lang = lines[0].slice(3).trim() || 'code';
              const body = lines.slice(1, -1).join('\n');
              return (
                <div key={idx} className="copilot-code-box" style={{ margin: '0.6rem 0' }}>
                  <div className="copilot-code-bar"><span>{lang.toUpperCase()}</span></div>
                  <pre className="copilot-code-content"><code>{body}</code></pre>
                </div>
              );
            }
            return (
              <div key={idx} style={{ whiteSpace: 'pre-wrap', fontSize: '0.82rem', lineHeight: '1.6', color: 'var(--text-primary)' }}>
                {part}
              </div>
            );
          });
        };

        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div className="studio-section-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <span className="studio-section-title"><BookOpen size={12} /> 30-Day Data Engineering Mastery & Interview Roadmap</span>
                <div style={{ fontSize: '0.78rem', color: 'var(--apple-mint)', marginTop: '2px' }}>
                  Progress: {completedCount}/{days.length || 30} Days Completed ({Math.round((completedCount / Math.max(1, days.length)) * 100)}%)
                </div>
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                <button className={`copilot-chip ${selectedPhase === 'all' ? 'active-chip' : ''}`} onClick={() => setSelectedPhase('all')}>All 30 Days</button>
                {phases.map((p) => (
                  <button key={p.id} className={`copilot-chip ${String(selectedPhase) === String(p.id) ? 'active-chip' : ''}`} onClick={() => setSelectedPhase(p.id)}>
                    P{p.id}: {p.days}
                  </button>
                ))}
              </div>
            </div>

            <div className="ues-grid-2" style={{ gridTemplateColumns: '320px 1fr' }}>
              <div className="studio-section-card" style={{ maxHeight: '720px', overflowY: 'auto' }}>
                <span className="studio-section-title">Daily Curriculum ({filteredDays.length})</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {filteredDays.map((d) => {
                    const done = Boolean(progress[d.day]?.completed);
                    return (
                      <div
                        key={d.day}
                        className="reference-card-item"
                        style={{ borderColor: activeDay?.day === d.day ? 'var(--apple-blue)' : undefined }}
                        onClick={() => {
                          setSelectedDayNum(d.day);
                          setDayNotes(progress[d.day]?.notes || '');
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <strong style={{ fontSize: '0.78rem' }}>Day {d.day}</strong>
                          <span style={{ fontSize: '0.68rem', color: done ? 'var(--apple-mint)' : 'var(--text-muted)' }}>
                            {done ? '✓ Done' : `${d.estimated_minutes}m`}
                          </span>
                        </div>
                        <div className="reference-card-desc" style={{ color: 'var(--text-primary)', marginTop: '2px' }}>
                          {d.title.replace(/^Day \d+\s*[–-]\s*/, '')}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {activeDay && (
                <div className="studio-section-card" style={{ maxHeight: '720px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', flexWrap: 'wrap' }}>
                    <div>
                      <span className="hero-pill-badge primary">Phase {activeDay.phase} · ~{activeDay.estimated_minutes} mins</span>
                      <h3 style={{ fontSize: '1.15rem', marginTop: '6px' }}>{activeDay.title}</h3>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      {activeDay.practice_snippet && ['sql', 'pyspark'].includes(activeDay.practice_type) && (
                        <button className="apple-btn apple-btn-primary" onClick={() => launchPracticeSnippet(activeDay)}>
                          <Play size={12} /> Try in {activeDay.practice_type === 'pyspark' ? 'PySpark' : 'SQL'} Studio
                        </button>
                      )}
                      <button
                        className={`apple-btn ${dayProg.completed ? 'apple-btn-primary' : 'apple-btn-secondary'}`}
                        onClick={() => saveDayProgress(activeDay.day, !dayProg.completed, dayNotes)}
                      >
                        <Check size={12} /> {dayProg.completed ? 'Completed' : 'Mark Complete'}
                      </button>
                    </div>
                  </div>

                  <div className="reference-card-item">
                    <span className="studio-section-title">Goals of Day {activeDay.day}</span>
                    <ul style={{ paddingLeft: '1.1rem', fontSize: '0.8rem', lineHeight: '1.55', marginTop: '4px' }}>
                      {(activeDay.goals || []).map((g, i) => <li key={i}>{g}</li>)}
                    </ul>
                  </div>

                  <div>{renderLessonBlocks(activeDay.lesson_md)}</div>

                  {(activeDay.interview_questions || []).length > 0 && (
                    <div className="reference-card-item">
                      <span className="studio-section-title" style={{ color: 'var(--apple-amber)' }}>
                        DE Interview Questions & Production Scenarios
                      </span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.5rem' }}>
                        {activeDay.interview_questions.map((iq, idx) => (
                          <div key={idx} style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.6rem' }}>
                            <div style={{ fontWeight: 600, fontSize: '0.84rem', color: '#fff' }}>Q{idx + 1}: {iq.question}</div>
                            <div style={{ fontSize: '0.79rem', color: 'var(--apple-mint)', marginTop: '4px' }}><strong>Answer:</strong> {iq.answer}</div>
                            {iq.scenario && (
                              <div style={{ fontSize: '0.75rem', color: 'var(--apple-cyan)', marginTop: '3px' }}><strong>Interview Scenario:</strong> {iq.scenario}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="reference-card-item">
                    <span className="studio-section-title">Your Study Notes (Persisted in SQLite)</span>
                    <textarea
                      className="copilot-textarea"
                      rows={3}
                      placeholder="Write key takeaways, SQL solutions, or interview notes for this day..."
                      value={dayNotes}
                      onChange={(e) => setDayNotes(e.target.value)}
                    />
                    <button
                      className="apple-btn apple-btn-secondary"
                      style={{ marginTop: '6px' }}
                      onClick={() => saveDayProgress(activeDay.day, dayProg.completed, dayNotes)}
                    >
                      Save Notes
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

