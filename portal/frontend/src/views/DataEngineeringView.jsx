import React, { useEffect, useState } from 'react';
import {
  Calendar,
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
        ].map((t) => (
          <button key={t.id} className={`ues-subtab ${subTab === t.id ? 'active' : ''}`} onClick={() => setSubTab(t.id)}>
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
            <iframe src={notebookUrl} title="JupyterLab" style={{ width: '100%', height: '620px', border: 'none', background: '#111' }} />
          </div>
        </div>
      )}
    </div>
  );
}

