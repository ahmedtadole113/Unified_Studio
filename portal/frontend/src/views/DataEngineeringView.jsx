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
import { DeRoadmapBrowser } from './RoadmapsView';

const SAMPLE_SQL = `SELECT n.n_name AS nation, c.c_mktsegment, COUNT(o.o_orderkey) AS orders, ROUND(SUM(o.o_totalprice), 2) AS total_revenue
FROM synapse_dw.customer c
JOIN synapse_dw.orders o ON c.c_custkey = o.o_custkey
JOIN synapse_dw.nation n ON c.c_nationkey = n.n_nationkey
GROUP BY n.n_name, c.c_mktsegment
ORDER BY total_revenue DESC
LIMIT 15;`;

const SAMPLE_PYSPARK = `from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.appName("UES_Practice_TPCH").getOrCreate()
cust = spark.table("demo.practice.customer")
orders = spark.table("demo.practice.orders")
nation = spark.table("demo.practice.nation")

agg = (
    cust.join(orders, cust.c_custkey == orders.o_custkey)
    .join(nation, cust.c_nationkey == nation.n_nationkey)
    .groupBy(nation.n_name.alias("nation"), cust.c_mktsegment)
    .agg(F.count("o_orderkey").alias("orders"), F.round(F.sum("o_totalprice"), 2).alias("total_revenue"))
    .orderBy(F.desc("total_revenue"))
)
agg.show(15, truncate=False)
spark.stop()`;

export default function DataEngineeringView({ user, pendingPractice, onClearPendingPractice, onOpenWorkspace }) {
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

  useEffect(() => {
    if (pendingPractice?.practice_snippet) {
      if (pendingPractice.practice_type === 'pyspark') {
        setPysparkCode(pendingPractice.practice_snippet);
        setSubTab('pyspark');
      } else {
        setSqlText(pendingPractice.practice_snippet);
        setSubTab('sql');
      }
      onClearPendingPractice?.();
    }
  }, [pendingPractice]);

  const loadDE = async () => {
    try {
      const data = await apiFetch(`${API_V1}/data-engineering/overview`);
      setOverview(data);
    } catch (err) {
      console.error(err);
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
          { id: 'roadmap', label: '60-Day DE + Azure Roadmap' },
        ].map((t) => (
          <button
            key={t.id}
            className={`ues-subtab ${subTab === t.id ? 'active' : ''}`}
            onClick={() => setSubTab(t.id)}
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
            <div style={{ fontSize: '0.72rem', color: 'var(--apple-cyan)', marginBottom: '0.45rem' }}>
              Shared Practice Dataset active: <code>synapse_dw.&#123;customer, orders, lineitem, part, partsupp, supplier, nation, region&#125;</code> (matches Iceberg <code>demo.practice.*</code>)
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <button className="apple-btn apple-btn-primary" onClick={runSql} disabled={busy}>
                <Play size={12} /> Run Query
              </button>
              <button className="apple-btn apple-btn-secondary" onClick={() => setSqlText(SAMPLE_SQL)}>
                Nation Revenue Join
              </button>
              <button className="apple-btn apple-btn-secondary" onClick={() => setSqlText("SELECT c.c_mktsegment, COUNT(DISTINCT c.c_custkey) AS customers, COUNT(o.o_orderkey) AS orders, ROUND(SUM(o.o_totalprice), 2) AS revenue FROM synapse_dw.customer c JOIN synapse_dw.orders o ON c.c_custkey = o.o_custkey GROUP BY c.c_mktsegment ORDER BY revenue DESC;")}>
                Segment Aggregation
              </button>
              <button className="apple-btn apple-btn-secondary" onClick={() => setSqlText("SELECT o_custkey, o_orderkey, o_orderdate, o_totalprice, RANK() OVER (PARTITION BY o_custkey ORDER BY o_totalprice DESC) AS rnk FROM synapse_dw.orders ORDER BY o_custkey, rnk LIMIT 30;")}>
                Window Rank
              </button>
              <button className="apple-btn apple-btn-secondary" onClick={() => setSqlText('SELECT * FROM synapse_dw.fact_customer_revenue LIMIT 25;')}>
                Fact Revenue
              </button>
              <button className="apple-btn apple-btn-secondary" onClick={() => onOpenWorkspace?.('/services/synapse/', 'pgAdmin 4 (SQL DW)')}>
                <ExternalLink size={12} /> pgAdmin 4 (Same Window)
              </button>
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
            <div style={{ fontSize: '0.72rem', color: 'var(--apple-cyan)', marginBottom: '0.45rem' }}>
              Same data synced across engines: <code>demo.practice.*</code> (Iceberg), <code>/home/iceberg/data/*.csv</code>, <code>synapse_dw.*</code> (Postgres)
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {isAdmin && (
                <button className="apple-btn apple-btn-primary" onClick={runPySpark} disabled={busy}>
                  <Play size={12} /> Execute PySpark
                </button>
              )}
              <button className="apple-btn apple-btn-secondary" onClick={() => setPysparkCode(SAMPLE_PYSPARK)}>
                Nation Revenue Join
              </button>
              <button className="apple-btn apple-btn-secondary" onClick={() => setPysparkCode(`from pyspark.sql import SparkSession\nfrom pyspark.sql import functions as F\nfrom pyspark.sql.window import Window\nspark = SparkSession.builder.appName("UES_Window").getOrCreate()\norders = spark.table("demo.practice.orders")\nw = Window.partitionBy("o_custkey").orderBy(F.desc("o_totalprice"))\norders.withColumn("rnk", F.rank().over(w)).select("o_custkey", "o_orderkey", "o_orderdate", "o_totalprice", "rnk").show(20)\nspark.stop()`)}>
                Window Rank
              </button>
              <button className="apple-btn apple-btn-secondary" onClick={() => setPysparkCode(`from pyspark.sql import SparkSession\nspark = SparkSession.builder.appName("UES_CSV_Parquet").getOrCreate()\ndf = spark.read.csv("/home/iceberg/data/customer.csv", header=True, inferSchema=True)\nprint("Customers:", df.count())\ndf.groupBy("c_mktsegment").count().show()\nspark.stop()`)}>
                Read CSV / GroupBy
              </button>
              <button className="apple-btn apple-btn-secondary" onClick={() => onOpenWorkspace?.('/services/spark/', 'Spark Master Web UI')}>
                <ExternalLink size={12} /> Spark UI (Same Window)
              </button>
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
              Apache Airflow Orchestration ({airflow.available ? 'Connected' : 'Offline'})
            </span>
            <button className="apple-btn apple-btn-secondary" onClick={() => onOpenWorkspace?.('/services/airflow/', 'Apache Airflow UI')}>
              <ExternalLink size={12} /> Open Airflow UI (Same Window)
            </button>
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
              <button className="apple-btn apple-btn-secondary" onClick={() => onOpenWorkspace?.('/services/datalake/', 'MinIO Data Lake Console')}>
                <ExternalLink size={12} /> MinIO Console (Same Window)
              </button>
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
                <button className="apple-btn apple-btn-primary" style={{ padding: '4px 10px', fontSize: '0.72rem' }} onClick={() => onOpenWorkspace?.(notebookUrl, 'JupyterLab Workspace')}>
                  <ExternalLink size={12} /> Full Workspace (Same Window)
                </button>
                <button className="apple-btn apple-btn-secondary" style={{ padding: '4px 10px', fontSize: '0.72rem' }} onClick={() => setNotebookUrl('/services/databricks/tree')}>
                  <FolderOpen size={12} /> Root Tree Here
                </button>
              </div>
            </div>
            <iframe src={notebookUrl} title="JupyterLab" style={{ width: '100%', height: '620px', border: 'none', background: '#111' }} />
          </div>
        </div>
      )}

      {subTab === 'roadmap' && <DeRoadmapBrowser onLaunchPractice={launchPracticeSnippet} />}
    </div>
  );
}

