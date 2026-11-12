import React, { useEffect, useState } from 'react';
import { ExternalLink, MessageSquare, Radio, RefreshCw, Send, Trash2 } from 'lucide-react';
import { apiFetch, API_V1 } from '../api/client';

export default function StreamingMessagingView({ user, onOpenWorkspace }) {
  const [data, setData] = useState(null);
  const [topicName, setTopicName] = useState('ues-events');
  const [kafkaMsg, setKafkaMsg] = useState('{"event":"test_pipeline_heartbeat","status":"ok"}');
  const [rabbitQueue, setRabbitQueue] = useState('ues.test.queue');
  const [rabbitMsg, setRabbitMsg] = useState('{"job":"sync_tpch","priority":"normal"}');
  const [statusMsg, setStatusMsg] = useState(null);

  const isAdmin = user?.role === 'admin';

  const loadStreaming = async () => {
    try {
      const res = await apiFetch(`${API_V1}/streaming/overview`);
      setData(res);
    } catch (err) {
      setStatusMsg(err.message);
    }
  };

  useEffect(() => {
    loadStreaming();
    const t = setInterval(loadStreaming, 5000);
    return () => clearInterval(t);
  }, []);

  const createTopic = async () => {
    try {
      await apiFetch(`${API_V1}/streaming/kafka/topics`, {
        method: 'POST',
        body: JSON.stringify({ topic: topicName, partitions: 1 }),
      });
      setStatusMsg(`Topic '${topicName}' created.`);
      loadStreaming();
    } catch (err) {
      setStatusMsg(err.message);
    }
  };

  const produceKafka = async () => {
    try {
      const res = await apiFetch(`${API_V1}/streaming/kafka/produce`, {
        method: 'POST',
        body: JSON.stringify({ topic: topicName, message: kafkaMsg }),
      });
      setStatusMsg(`Sent message to ${res.topic} partition ${res.partition} offset ${res.offset}.`);
      loadStreaming();
    } catch (err) {
      setStatusMsg(err.message);
    }
  };

  const publishRabbit = async () => {
    try {
      await apiFetch(`${API_V1}/streaming/rabbitmq/publish`, {
        method: 'POST',
        body: JSON.stringify({ queue: rabbitQueue, payload: rabbitMsg }),
      });
      setStatusMsg(`Published message to RabbitMQ queue '${rabbitQueue}'.`);
      loadStreaming();
    } catch (err) {
      setStatusMsg(err.message);
    }
  };

  const purgeRabbit = async (q) => {
    try {
      await apiFetch(`${API_V1}/streaming/rabbitmq/queues/${encodeURIComponent(q)}/purge`, { method: 'DELETE' });
      setStatusMsg(`Purged queue '${q}'.`);
      loadStreaming();
    } catch (err) {
      setStatusMsg(err.message);
    }
  };

  const kafka = data?.kafka || {};
  const rabbit = data?.rabbitmq || {};

  return (
    <div className="view-container">
      <div className="section-header">
        <div>
          <h2 className="section-title"><Radio size={18} style={{ color: 'var(--apple-amber)' }} /> Streaming & Messaging</h2>
          <p className="section-subtitle">Unified Redpanda (Kafka-compatible) & RabbitMQ broker telemetry, consumer lag, DLQs, and message testing</p>
        </div>
        <button className="apple-btn apple-btn-secondary" onClick={loadStreaming}><RefreshCw size={12} /> Refresh</button>
      </div>

      {statusMsg && <div className="ues-alert-banner info" style={{ marginBottom: '1rem' }}>{statusMsg}</div>}

      <div className="ues-grid-2">
        {/* Kafka / Redpanda */}
        <div className="studio-section-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="studio-section-title">
              Kafka / Redpanda ({kafka.available ? `Online · Lag: ${kafka.total_consumer_lag}` : 'Offline'})
            </span>
            <button className="apple-btn apple-btn-secondary" style={{ fontSize: '0.72rem' }} onClick={() => onOpenWorkspace?.('/services/eventhub/', 'Redpanda Console')}>
              <ExternalLink size={11} /> Redpanda Console
            </button>
          </div>

          {isAdmin && kafka.available && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', gap: '6px' }}>
                <input className="apple-input" value={topicName} onChange={(e) => setTopicName(e.target.value)} placeholder="Topic name" style={{ flex: 1 }} />
                <button className="apple-btn apple-btn-secondary" onClick={createTopic}>Create Topic</button>
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                <input className="apple-input" value={kafkaMsg} onChange={(e) => setKafkaMsg(e.target.value)} placeholder="JSON payload" style={{ flex: 1 }} />
                <button className="apple-btn apple-btn-primary" onClick={produceKafka}><Send size={11} /> Produce</button>
              </div>
            </div>
          )}

          <span className="studio-section-title">Topics ({kafka.topic_count || 0})</span>
          <table className="apple-table" style={{ marginBottom: '0.75rem' }}>
            <thead><tr><th>Topic</th><th>Partitions</th><th>Messages</th></tr></thead>
            <tbody>
              {(kafka.topics || []).map((t) => (
                <tr key={t.name}>
                  <td><code>{t.name}</code></td>
                  <td>{t.partitions}</td>
                  <td>{t.estimated_messages}</td>
                </tr>
              ))}
              {(!kafka.topics || kafka.topics.length === 0) && <tr><td colSpan={3} style={{ color: 'var(--text-muted)' }}>No topics or Redpanda stopped.</td></tr>}
            </tbody>
          </table>

          <span className="studio-section-title">Consumer Groups & Lag ({kafka.consumer_groups?.length || 0})</span>
          <table className="apple-table">
            <thead><tr><th>Group ID</th><th>Total Lag</th></tr></thead>
            <tbody>
              {(kafka.consumer_groups || []).map((g) => (
                <tr key={g.group_id}>
                  <td><code>{g.group_id}</code></td>
                  <td style={{ color: g.total_lag > 100 ? 'var(--apple-coral)' : 'var(--apple-mint)', fontWeight: 600 }}>{g.total_lag}</td>
                </tr>
              ))}
              {(!kafka.consumer_groups || kafka.consumer_groups.length === 0) && <tr><td colSpan={2} style={{ color: 'var(--text-muted)' }}>No active consumer groups.</td></tr>}
            </tbody>
          </table>
        </div>

        {/* RabbitMQ */}
        <div className="studio-section-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="studio-section-title">
              <MessageSquare size={12} /> RabbitMQ ({rabbit.available ? `v${rabbit.rabbitmq_version} · ${rabbit.total_messages} msgs` : 'Offline'})
            </span>
            <button className="apple-btn apple-btn-secondary" style={{ fontSize: '0.72rem' }} onClick={() => onOpenWorkspace?.('/services/servicebus/', 'RabbitMQ Management')}>
              <ExternalLink size={11} /> RabbitMQ UI
            </button>
          </div>

          <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginBottom: '0.6rem' }}>
            Publish rate: <strong>{rabbit.publish_rate ?? 0}/s</strong> · Deliver rate: <strong>{rabbit.deliver_rate ?? 0}/s</strong> · DLQs: <strong>{rabbit.dlqs?.length || 0}</strong>
          </div>

          {isAdmin && rabbit.available && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', gap: '6px' }}>
                <input className="apple-input" value={rabbitQueue} onChange={(e) => setRabbitQueue(e.target.value)} placeholder="Queue name" style={{ width: '160px' }} />
                <input className="apple-input" value={rabbitMsg} onChange={(e) => setRabbitMsg(e.target.value)} placeholder="Payload" style={{ flex: 1 }} />
                <button className="apple-btn apple-btn-primary" onClick={publishRabbit}><Send size={11} /> Publish</button>
              </div>
            </div>
          )}

          <span className="studio-section-title">Queues & Dead-Letter Queues ({rabbit.queues?.length || 0})</span>
          <table className="apple-table" style={{ marginBottom: '0.75rem' }}>
            <thead><tr><th>Queue</th><th>Ready</th><th>Unacked</th><th>Consumers</th><th>Action</th></tr></thead>
            <tbody>
              {(rabbit.queues || []).map((q) => (
                <tr key={q.name}>
                  <td>
                    <code>{q.name}</code>
                    {q.is_dlq && <span className="hero-pill-badge primary" style={{ marginLeft: '6px' }}>DLQ</span>}
                  </td>
                  <td>{q.messages_ready}</td>
                  <td>{q.messages_unacknowledged}</td>
                  <td>{q.consumers}</td>
                  <td>
                    {isAdmin && (
                      <button className="apple-btn apple-btn-danger" style={{ padding: '2px 6px' }} onClick={() => purgeRabbit(q.name)} title="Purge">
                        <Trash2 size={11} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {(!rabbit.queues || rabbit.queues.length === 0) && <tr><td colSpan={5} style={{ color: 'var(--text-muted)' }}>No queues or RabbitMQ stopped.</td></tr>}
            </tbody>
          </table>

          <span className="studio-section-title">Exchanges ({rabbit.exchanges?.length || 0})</span>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {(rabbit.exchanges || []).map((ex, i) => (
              <span key={i} className="hero-pill-badge secondary">{ex.name} ({ex.type})</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

