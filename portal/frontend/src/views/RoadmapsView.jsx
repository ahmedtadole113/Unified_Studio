import React, { useEffect, useState } from 'react';
import { BookOpen, Check, Play, ShieldAlert, Database, Terminal, AlertTriangle } from 'lucide-react';
import { apiFetch, API_V1 } from '../api/client';

function renderMarkdownBlocks(md) {
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
}

export function DeRoadmapBrowser({ onLaunchPractice }) {
  const [roadmap, setRoadmap] = useState(null);
  const [selectedPhase, setSelectedPhase] = useState('all');
  const [selectedDayNum, setSelectedDayNum] = useState(1);
  const [dayNotes, setDayNotes] = useState('');

  const loadDeRoadmap = async () => {
    try {
      const rm = await apiFetch(`${API_V1}/data-engineering/roadmap`);
      setRoadmap(rm);
      setDayNotes(rm.progress?.[selectedDayNum]?.notes || '');
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadDeRoadmap();
  }, []);

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

  const days = roadmap?.days || [];
  const phases = roadmap?.phases || [];
  const progress = roadmap?.progress || {};
  const filteredDays = selectedPhase === 'all' ? days : days.filter((d) => String(d.phase) === String(selectedPhase));
  const activeDay = days.find((d) => d.day === selectedDayNum) || filteredDays[0] || days[0];
  const dayProg = activeDay ? (progress[activeDay.day] || { completed: false, notes: '' }) : { completed: false, notes: '' };
  const completedCount = Object.values(progress).filter((p) => p.completed).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="studio-section-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <span className="studio-section-title"><BookOpen size={12} /> 30-Day Data Engineering Mastery &amp; Interview Roadmap</span>
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
                {onLaunchPractice && activeDay.practice_snippet && ['sql', 'pyspark'].includes(activeDay.practice_type) && (
                  <button className="apple-btn apple-btn-primary" onClick={() => onLaunchPractice(activeDay)}>
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

            <div>{renderMarkdownBlocks(activeDay.lesson_md)}</div>

            {(activeDay.interview_questions || []).length > 0 && (
              <div className="reference-card-item">
                <span className="studio-section-title" style={{ color: 'var(--apple-amber)' }}>
                  DE Interview Questions &amp; Production Scenarios
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
}

export function SreRoadmapBrowser() {
  const [roadmap, setRoadmap] = useState(null);
  const [selectedPhase, setSelectedPhase] = useState('all');
  const [selectedDayNum, setSelectedDayNum] = useState(1);
  const [dayNotes, setDayNotes] = useState('');

  const loadSreRoadmap = async () => {
    try {
      const rm = await apiFetch(`${API_V1}/aiops/roadmap`);
      setRoadmap(rm);
      setDayNotes(rm.progress?.[selectedDayNum]?.notes || '');
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadSreRoadmap();
  }, []);

  const saveDayProgress = async (dayNum, completed, notes) => {
    try {
      await apiFetch(`${API_V1}/aiops/roadmap/${dayNum}/progress`, {
        method: 'PUT',
        body: JSON.stringify({ completed, notes }),
      });
      await loadSreRoadmap();
    } catch (err) {
      alert(err.message);
    }
  };

  const days = roadmap?.days || [];
  const phases = roadmap?.phases || [];
  const progress = roadmap?.progress || {};
  const filteredDays = selectedPhase === 'all' ? days : days.filter((d) => String(d.phase) === String(selectedPhase));
  const activeDay = days.find((d) => d.day === selectedDayNum) || filteredDays[0] || days[0];
  const dayProg = activeDay ? (progress[activeDay.day] || { completed: false, notes: '' }) : { completed: false, notes: '' };
  const completedCount = Object.values(progress).filter((p) => p.completed).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="studio-section-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <span className="studio-section-title"><ShieldAlert size={12} /> 45-Day SRE, DevOps &amp; Kubernetes Mastery Roadmap</span>
          <div style={{ fontSize: '0.78rem', color: 'var(--apple-mint)', marginTop: '2px' }}>
            Progress: {completedCount}/{days.length || 45} Days Completed ({Math.round((completedCount / Math.max(1, days.length)) * 100)}%)
          </div>
        </div>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          <button className={`copilot-chip ${selectedPhase === 'all' ? 'active-chip' : ''}`} onClick={() => setSelectedPhase('all')}>All 45 Days</button>
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
                    <strong style={{ fontSize: '0.78rem' }}>Day {d.day} · Phase {d.phase}</strong>
                    <span style={{ fontSize: '0.68rem', color: done ? 'var(--apple-mint)' : 'var(--text-muted)' }}>
                      {done ? '✓ Done' : 'SRE'}
                    </span>
                  </div>
                  <div className="reference-card-desc" style={{ color: 'var(--text-primary)', marginTop: '2px' }}>
                    {d.title}
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
                <span className="hero-pill-badge primary">Day {activeDay.day} · Phase {activeDay.phase}</span>
                <h3 style={{ fontSize: '1.15rem', marginTop: '6px' }}>{activeDay.title}</h3>
                {activeDay.subtitle && <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>{activeDay.subtitle}</div>}
              </div>
              <button
                className={`apple-btn ${dayProg.completed ? 'apple-btn-primary' : 'apple-btn-secondary'}`}
                onClick={() => saveDayProgress(activeDay.day, !dayProg.completed, dayNotes)}
              >
                <Check size={12} /> {dayProg.completed ? 'Completed' : 'Mark Complete'}
              </button>
            </div>

            <div className="reference-card-item">
              <span className="studio-section-title">Goal &amp; Objective</span>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-primary)', marginTop: '4px' }}><strong>Goal:</strong> {activeDay.goal}</p>
              {activeDay.objective && <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: '1.5' }}>{activeDay.objective}</p>}
              {activeDay.architecture && (
                <div style={{ marginTop: '6px', padding: '6px 10px', background: 'rgba(41,151,255,0.08)', borderRadius: '6px', fontFamily: 'monospace', fontSize: '0.76rem', color: 'var(--apple-cyan)' }}>
                  {activeDay.architecture}
                </div>
              )}
            </div>

            {(activeDay.deep_sections || []).length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                {activeDay.deep_sections.map((sec, idx) => (
                  <div key={idx} className="reference-card-item">
                    <div style={{ fontWeight: 600, fontSize: '0.86rem', color: '#fff', marginBottom: '4px' }}>{sec.title}</div>
                    <div style={{ fontSize: '0.8rem', lineHeight: '1.55', color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>{sec.explanation}</div>
                  </div>
                ))}
              </div>
            )}

            {(activeDay.commands || []).length > 0 && (
              <div className="reference-card-item">
                <span className="studio-section-title"><Terminal size={12} /> Hands-On Commands</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                  {activeDay.commands.map((c, idx) => (
                    <div key={idx} className="copilot-code-box" style={{ margin: 0 }}>
                      <div className="copilot-code-bar"><span>SHELL #{idx + 1}</span></div>
                      <pre className="copilot-code-content"><code>{c.cmd}</code></pre>
                      {c.explain && <div style={{ padding: '4px 10px', fontSize: '0.74rem', color: 'var(--text-secondary)' }}>{c.explain}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(activeDay.scenarios || []).length > 0 && (
              <div className="reference-card-item">
                <span className="studio-section-title" style={{ color: 'var(--apple-coral)' }}><AlertTriangle size={12} /> Production Scenarios</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                  {activeDay.scenarios.map((sc, idx) => (
                    <div key={idx} style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '6px' }}>
                      <div style={{ fontWeight: 600, fontSize: '0.82rem', color: '#fff' }}>{sc.title}</div>
                      {sc.symptom && <div style={{ fontSize: '0.76rem', color: 'var(--apple-amber)', marginTop: '2px' }}><strong>Symptom:</strong> {sc.symptom}</div>}
                      {sc.diagnosis && <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: '2px' }}><strong>Diagnosis:</strong> {sc.diagnosis}</div>}
                      {sc.fix && <div style={{ fontSize: '0.76rem', color: 'var(--apple-mint)', marginTop: '2px' }}><strong>Fix:</strong> {sc.fix}</div>}
                      {sc.resolution && <div style={{ fontSize: '0.76rem', color: 'var(--apple-mint)', marginTop: '2px' }}><strong>Resolution:</strong> {sc.resolution}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(activeDay.interview_qa || []).length > 0 && (
              <div className="reference-card-item">
                <span className="studio-section-title" style={{ color: 'var(--apple-amber)' }}>SRE Interview Q&amp;A</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                  {activeDay.interview_qa.map((qa, idx) => (
                    <div key={idx} style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '6px' }}>
                      <div style={{ fontWeight: 600, fontSize: '0.82rem', color: '#fff' }}>Q{idx + 1}: {qa.q}</div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--apple-mint)', marginTop: '3px' }}><strong>Answer:</strong> {qa.a}</div>
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
                placeholder="Write Linux commands, troubleshooting notes, or interview takeaways for this day..."
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
}

export default function RoadmapsView({ onLaunchDePractice }) {
  const [track, setTrack] = useState('de');

  return (
    <div className="view-container">
      <div className="section-header">
        <div>
          <h2 className="section-title">
            <BookOpen size={18} style={{ color: 'var(--apple-blue)' }} /> Day-Wise Study Roadmaps (DE &amp; SRE)
          </h2>
          <p className="section-subtitle">
            Complete structured daily study plans with hands-on SQL, PySpark, Linux, Kubernetes &amp; production interview scenarios
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className={`apple-btn ${track === 'de' ? 'apple-btn-primary' : 'apple-btn-secondary'}`}
            onClick={() => setTrack('de')}
          >
            <Database size={13} /> Data Engineering (30 Days)
          </button>
          <button
            className={`apple-btn ${track === 'sre' ? 'apple-btn-primary' : 'apple-btn-secondary'}`}
            onClick={() => setTrack('sre')}
          >
            <ShieldAlert size={13} /> SRE &amp; DevOps (45 Days)
          </button>
        </div>
      </div>

      {track === 'de' ? (
        <DeRoadmapBrowser onLaunchPractice={onLaunchDePractice} />
      ) : (
        <SreRoadmapBrowser />
      )}
    </div>
  );
}

