import React, { useState, useEffect } from 'react';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [leads, setLeads] = useState([]);
  const [selectedLeadId, setSelectedLeadId] = useState(null);
  const [selectedLead, setSelectedLead] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  
  // Pipeline config and toast status
  const [systemConfig, setSystemConfig] = useState({ mode: 'Mock Mode', model: 'mock-adk-model', is_mock: true });
  const [showToast, setShowToast] = useState(false);
  
  // Intake Form
  const [showIntakeModal, setShowIntakeModal] = useState(false);
  const [newLeadText, setNewLeadText] = useState('');
  const [newLeadSource, setNewLeadSource] = useState('webform');
  const [intakeLoading, setIntakeLoading] = useState(false);

  // Edit draft states
  const [editSubject, setEditSubject] = useState('');
  const [editEmailBody, setEditEmailBody] = useState('');
  const [editWhatsappBody, setEditWhatsappBody] = useState('');
  const [editAction, setEditAction] = useState('');
  const [editDetails, setEditDetails] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Filter state
  const [filterTab, setFilterTab] = useState('pending'); // pending, approved, rejected, all
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch leads queue
  const fetchLeads = async (showRefreshIndicator = false) => {
    if (showRefreshIndicator) setRefreshing(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/leads`);
      if (res.ok) {
        const data = await res.json();
        setLeads(data);
      }
    } catch (err) {
      console.error("Error fetching leads:", err);
    } finally {
      setRefreshing(false);
    }
  };

  // Auto select first lead if none selected
  useEffect(() => {
    if (leads.length > 0 && !selectedLeadId) {
      setSelectedLeadId(leads[0].id);
    }
  }, [leads, selectedLeadId]);

  // Fetch selected lead details
  const fetchLeadDetails = async (id) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/leads/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedLead(data);
        // Initialize editor inputs
        setEditSubject(data.draft?.email_subject || '');
        setEditEmailBody(data.draft?.email_body || '');
        setEditWhatsappBody(data.draft?.whatsapp_body || '');
        setEditAction(data.recommendation?.action || '');
        setEditDetails(data.recommendation?.details || '');
      }
    } catch (err) {
      console.error("Error fetching lead details:", err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch system configuration
  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/config`);
      if (res.ok) {
        const data = await res.json();
        setSystemConfig(data);
        setShowToast(true);
      }
    } catch (err) {
      console.error("Error fetching config:", err);
    }
  };

  // Poll leads and fetch configuration on mount
  useEffect(() => {
    fetchLeads();
    fetchConfig();
    const interval = setInterval(() => fetchLeads(), 5000);
    return () => clearInterval(interval);
  }, []);

  // Toast self-dismiss timer
  useEffect(() => {
    if (showToast) {
      const timer = setTimeout(() => setShowToast(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [showToast]);

  // Fetch lead details when selection changes
  useEffect(() => {
    if (selectedLeadId) {
      fetchLeadDetails(selectedLeadId);
    } else {
      setSelectedLead(null);
    }
  }, [selectedLeadId]);

  // Handle lead intake submission
  const handleIntakeSubmit = async (e) => {
    e.preventDefault();
    if (!newLeadText.trim()) return;
    
    setIntakeLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/leads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_text: newLeadText, source: newLeadSource }),
      });
      if (res.ok) {
        const data = await res.json();
        setNewLeadText('');
        setShowIntakeModal(false);
        // Select the newly created lead
        if (data.lead_id) {
          setSelectedLeadId(data.lead_id);
        }
        await fetchLeads();
      }
    } catch (err) {
      console.error("Error submitting lead:", err);
      alert("Error submitting lead. Please make sure the FastAPI server is running.");
    } finally {
      setIntakeLoading(false);
    }
  };

  // Handle saving changes
  const handleSaveChanges = async () => {
    if (!selectedLead) return;
    setIsSaving(true);
    try {
      const updates = {
        draft: {
          email_subject: editSubject,
          email_body: editEmailBody,
          whatsapp_body: editWhatsappBody,
          status: selectedLead.draft?.status || 'pending_approval'
        },
        recommendation: {
          action: editAction,
          details: editDetails,
          calendar_event: selectedLead.recommendation?.calendar_event
        }
      };

      const res = await fetch(`${API_BASE_URL}/api/leads/${selectedLead.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      if (res.ok) {
        const data = await res.json();
        setSelectedLead(data);
        await fetchLeads();
        alert("Changes saved successfully!");
      }
    } catch (err) {
      console.error("Error saving lead changes:", err);
      alert("Failed to save changes.");
    } finally {
      setIsSaving(false);
    }
  };

  // Approve drafts
  const handleApproveDraft = async () => {
    if (!selectedLead) return;
    setActionLoading(true);
    try {
      // First save any current changes in the textareas
      const updates = {
        draft: {
          email_subject: editSubject,
          email_body: editEmailBody,
          whatsapp_body: editWhatsappBody,
          status: 'pending_approval'
        },
        recommendation: {
          action: editAction,
          details: editDetails,
          calendar_event: selectedLead.recommendation?.calendar_event
        }
      };
      
      await fetch(`${API_BASE_URL}/api/leads/${selectedLead.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });

      // Then trigger approve
      const res = await fetch(`${API_BASE_URL}/api/leads/${selectedLead.id}/approve`, {
        method: 'POST'
      });
      if (res.ok) {
        alert("Draft approved and sent successfully via Gmail and WhatsApp MCP!");
        await fetchLeadDetails(selectedLead.id);
        await fetchLeads();
      }
    } catch (err) {
      console.error("Error approving draft:", err);
      alert("Approval action failed.");
    } finally {
      setActionLoading(false);
    }
  };

  // Reject drafts
  const handleRejectDraft = async () => {
    if (!selectedLead) return;
    if (!confirm("Are you sure you want to reject and archive this communication draft?")) return;
    
    setActionLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/leads/${selectedLead.id}/reject`, {
        method: 'POST'
      });
      if (res.ok) {
        alert("Draft rejected and marked as archived.");
        await fetchLeadDetails(selectedLead.id);
        await fetchLeads();
      }
    } catch (err) {
      console.error("Error rejecting draft:", err);
    } finally {
      setActionLoading(false);
    }
  };

  // Filter leads by tab and query
  const filteredLeads = leads.filter(lead => {
    const draftStatus = lead.draft?.status || 'pending_approval';
    const matchesTab = 
      filterTab === 'all' ||
      (filterTab === 'pending' && draftStatus === 'pending_approval') ||
      (filterTab === 'approved' && draftStatus === 'approved') ||
      (filterTab === 'rejected' && draftStatus === 'rejected');
      
    const matchesSearch = 
      lead.raw_text.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (lead.extracted_data?.course || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (lead.id || '').includes(searchQuery);

    return matchesTab && matchesSearch;
  });

  const getHeatColor = (category) => {
    if (category === 'HOT') return 'var(--hot)';
    if (category === 'WARM') return 'var(--warm)';
    return 'var(--cold)';
  };

  const getHeatGlow = (category) => {
    if (category === 'HOT') return 'glow-card-hot';
    if (category === 'WARM') return 'glow-card-warm';
    return 'glow-card-cold';
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <style>{`
        @keyframes slideDown {
          from { transform: translate(-50%, -20px); opacity: 0; }
          to { transform: translate(-50%, 0); opacity: 1; }
        }
      `}</style>

      {/* Mode Status Toast Alert */}
      {showToast && (
        <div style={{
          position: 'fixed',
          top: '24px',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 1000,
          background: systemConfig.is_mock ? 'rgba(30, 41, 59, 0.95)' : 'rgba(6, 78, 59, 0.95)',
          color: '#fff',
          border: `1px solid ${systemConfig.is_mock ? 'rgba(148, 163, 184, 0.3)' : 'rgba(52, 211, 153, 0.4)'}`,
          boxShadow: `0 10px 25px ${systemConfig.is_mock ? 'rgba(0,0,0,0.5)' : 'rgba(16,185,129,0.3)'}`,
          padding: '12px 24px',
          borderRadius: '12px',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          animation: 'slideDown 0.3s ease-out'
        }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: systemConfig.is_mock ? '#94a3b8' : '#34d399',
            boxShadow: `0 0 8px ${systemConfig.is_mock ? '#94a3b8' : '#34d399'}`
          }} />
          <span style={{ fontSize: '13px', fontWeight: 600 }}>
            Active Pipeline Mode: <span style={{ color: systemConfig.is_mock ? '#38bdf8' : '#34d399' }}>{systemConfig.mode}</span>
          </span>
          <span style={{ fontSize: '11px', opacity: 0.7, marginLeft: '4px' }}>
            ({systemConfig.model})
          </span>
          <button 
            onClick={() => setShowToast(false)} 
            style={{
              background: 'none',
              border: 'none',
              color: '#fff',
              cursor: 'pointer',
              padding: 0,
              marginLeft: '12px',
              fontSize: '16px',
              lineHeight: 1,
              opacity: 0.7
            }}
            onMouseEnter={e => e.currentTarget.style.opacity = 1}
            onMouseLeave={e => e.currentTarget.style.opacity = 0.7}
          >
            ×
          </button>
        </div>
      )}

      {/* Top Header */}
      <header style={{
        padding: '16px 32px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid var(--border-color)',
        background: 'rgba(10, 11, 18, 0.8)',
        backdropFilter: 'blur(10px)',
        position: 'sticky',
        top: 0,
        zIndex: 50
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px var(--primary-glow)'
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          </div>
          <div>
            <h1 style={{ fontSize: '20px', fontWeight: 800, letterSpacing: '-0.5px' }}>
              LeadFlow <span style={{ color: 'var(--primary)' }}>AI</span>
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
              <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: 0 }}>Education Multi-Agent Portal</p>
              <span style={{
                fontSize: '9px',
                padding: '2px 6px',
                borderRadius: '8px',
                background: systemConfig.is_mock ? 'rgba(148, 163, 184, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                color: systemConfig.is_mock ? '#94a3b8' : '#34d399',
                border: `1px solid ${systemConfig.is_mock ? 'rgba(148, 163, 184, 0.25)' : 'rgba(16, 185, 129, 0.25)'}`,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}>
                {systemConfig.mode}
              </span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button 
            onClick={() => fetchLeads(true)}
            disabled={refreshing}
            className="glass-panel"
            style={{
              padding: '8px 16px',
              fontSize: '13px',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <svg 
              className={refreshing ? "spin" : ""}
              width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              style={{ transition: 'transform 0.5s ease', transform: refreshing ? 'rotate(360deg)' : 'none' }}
            >
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
            </svg>
            {refreshing ? 'Syncing...' : 'Sync Queue'}
          </button>
          
          <button 
            onClick={() => setShowIntakeModal(true)}
            style={{
              padding: '10px 20px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, var(--primary) 0%, #4f46e5 100%)',
              color: '#fff',
              border: 'none',
              fontWeight: 600,
              fontSize: '13px',
              cursor: 'pointer',
              boxShadow: '0 4px 15px var(--primary-glow)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'transform var(--transition-fast)'
            }}
            onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.03)'}
            onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14"/></svg>
            Add Incoming Lead
          </button>
        </div>
      </header>

      {/* Stats Summary Panel */}
      <section style={{
        padding: '24px 32px 12px 32px',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '16px'
      }}>
        <div className="glass-panel" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>Total Ingested Leads</p>
            <h3 style={{ fontSize: '28px', fontWeight: 800, marginTop: '4px' }}>{leads.length}</h3>
          </div>
          <div style={{ color: 'var(--primary)', opacity: 0.8 }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>Pending Review</p>
            <h3 style={{ fontSize: '28px', fontWeight: 800, marginTop: '4px', color: 'var(--warm)' }}>
              {leads.filter(l => (l.draft?.status || 'pending_approval') === 'pending_approval').length}
            </h3>
          </div>
          <div style={{ color: 'var(--warm)', opacity: 0.8 }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>Hot Leads (🚀)</p>
            <h3 style={{ fontSize: '28px', fontWeight: 800, marginTop: '4px', color: 'var(--hot)' }}>
              {leads.filter(l => l.score?.category === 'HOT').length}
            </h3>
          </div>
          <div style={{ color: 'var(--hot)', opacity: 0.8 }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>Dispatched Messages</p>
            <h3 style={{ fontSize: '28px', fontWeight: 800, marginTop: '4px', color: 'var(--secondary)' }}>
              {leads.filter(l => l.draft?.status === 'approved').length}
            </h3>
          </div>
          <div style={{ color: 'var(--secondary)', opacity: 0.8 }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
          </div>
        </div>
      </section>

      {/* Main Workspace */}
      <main style={{
        flex: 1,
        padding: '16px 32px 32px 32px',
        display: 'grid',
        gridTemplateColumns: '380px 1fr',
        gap: '24px',
        height: 'calc(100vh - 200px)',
        overflow: 'hidden'
      }}>
        {/* Left Side: Lead Queue */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%', overflow: 'hidden' }}>
          {/* Tab Filters */}
          <div style={{
            display: 'flex',
            background: 'rgba(255, 255, 255, 0.03)',
            borderRadius: '12px',
            padding: '4px',
            border: '1px solid var(--border-color)'
          }}>
            {['pending', 'approved', 'rejected', 'all'].map((tab) => (
              <button
                key={tab}
                onClick={() => setFilterTab(tab)}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '8px',
                  border: 'none',
                  background: filterTab === tab ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                  color: filterTab === tab ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'capitalize',
                  cursor: 'pointer',
                  transition: 'background var(--transition-fast)'
                }}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Search bar */}
          <div style={{ position: 'relative' }}>
            <input
              type="text"
              placeholder="Search leads, courses..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 16px 10px 38px',
                borderRadius: '10px',
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                outline: 'none',
                fontSize: '13px'
              }}
            />
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2.5"
              style={{ position: 'absolute', left: '14px', top: '13px' }}>
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </div>

          {/* Leads Card Container */}
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px', paddingRight: '4px' }}>
            {filteredLeads.length === 0 ? (
              <div style={{
                padding: '32px 16px',
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: '13px',
                border: '1.5px dashed var(--border-color)',
                borderRadius: '16px'
              }}>
                No leads match current filters.
              </div>
            ) : (
              filteredLeads.map((lead) => {
                const isSelected = lead.id === selectedLeadId;
                const scoreCat = lead.score?.category || 'COLD';
                const scoreVal = lead.score?.points || 0;
                
                return (
                  <div
                    key={lead.id}
                    onClick={() => setSelectedLeadId(lead.id)}
                    className={`glass-panel ${getHeatGlow(scoreCat)} animate-fade`}
                    style={{
                      padding: '16px',
                      cursor: 'pointer',
                      borderLeft: `4px solid ${getHeatColor(scoreCat)}`,
                      borderColor: isSelected ? 'var(--primary)' : undefined,
                      transform: isSelected ? 'scale(0.99)' : 'none',
                      background: isSelected ? 'rgba(99, 102, 241, 0.07)' : undefined
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{
                          fontSize: '9px',
                          fontWeight: 700,
                          padding: '3px 6px',
                          borderRadius: '4px',
                          background: 'rgba(255, 255, 255, 0.05)',
                          color: 'var(--text-secondary)'
                        }}>
                          {lead.source.toUpperCase()}
                        </span>
                        
                        {/* Status dot */}
                        <span 
                          className="pulse-dot"
                          style={{
                            width: '6px',
                            height: '6px',
                            borderRadius: '50%',
                            background: lead.draft?.status === 'approved' ? 'var(--secondary)' : 'var(--warm)'
                          }}
                        />
                      </div>
                      
                      {/* Lead score and classification */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontSize: '11px', fontWeight: 800, color: getHeatColor(scoreCat) }}>
                          {scoreCat}
                        </span>
                        <span style={{
                          fontSize: '11px',
                          fontWeight: 800,
                          padding: '2px 5px',
                          borderRadius: '4px',
                          background: getHeatColor(scoreCat) + '20',
                          color: getHeatColor(scoreCat)
                        }}>
                          {scoreVal}
                        </span>
                      </div>
                    </div>

                    <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
                      Course: {lead.extracted_data?.course || 'Processing...'}
                    </h4>

                    <p style={{
                      fontSize: '12px',
                      color: 'var(--text-secondary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      marginBottom: '8px'
                    }}>
                      {lead.raw_text.startsWith('msg-') ? 'Reading original email body...' : lead.raw_text}
                    </p>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '10px', color: 'var(--text-muted)' }}>
                      <span>Timeline: {lead.extracted_data?.timeline || 'Pending'}</span>
                      <span>{new Date(lead.updated_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </section>

        {/* Right Side: Lead Workspace */}
        <section className="glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
          {!selectedLead ? (
            <div style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
              gap: '12px'
            }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
              <p style={{ fontSize: '14px' }}>Select a lead from the queue to start processing details.</p>
            </div>
          ) : loading ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyItems: 'center', justifyContent: 'center' }}>
              <div className="spinner">Analyzing Lead Data...</div>
            </div>
          ) : (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
              {/* Workspace Header */}
              <div style={{
                padding: '20px 24px',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexShrink: 0
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: '6px',
                      background: 'rgba(255, 255, 255, 0.05)',
                      color: 'var(--text-secondary)'
                    }}>
                      Source: {selectedLead.source.toUpperCase()}
                    </span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      ID: {selectedLead.id.substring(0, 8)}...
                    </span>
                  </div>
                  <h2 style={{ fontSize: '18px', fontWeight: 800 }}>Lead Processing Workspace</h2>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <span style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontWeight: 700,
                    background: getHeatColor(selectedLead.score?.category) + '15',
                    color: getHeatColor(selectedLead.score?.category),
                    border: `1px solid ${getHeatColor(selectedLead.score?.category)}30`
                  }}>
                    {selectedLead.score?.category || 'COLD'} ({selectedLead.score?.points || 0} pts)
                  </span>
                  
                  <span style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontWeight: 700,
                    background: selectedLead.draft?.status === 'approved' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                    color: selectedLead.draft?.status === 'approved' ? 'var(--secondary)' : 'var(--warm)',
                    border: `1px solid ${selectedLead.draft?.status === 'approved' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                    textTransform: 'uppercase'
                  }}>
                    {selectedLead.draft?.status ? selectedLead.draft.status.replace('_', ' ') : 'Processing'}
                  </span>
                </div>
              </div>

              {/* Workspace Content Scrollable Area */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'grid', gridTemplateColumns: '320px 1fr', gap: '24px' }}>
                
                {/* Left Side: Metadata & Reasoning */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* Raw Enquiry */}
                  <div className="glass-panel" style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.01)' }}>
                    <h3 style={{ fontSize: '12px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Original Inquiry</h3>
                    <p style={{ fontSize: '13px', lineHeight: 1.5, color: 'var(--text-primary)', wordBreak: 'break-word', maxHeight: '120px', overflowY: 'auto' }}>
                      {selectedLead.raw_text}
                    </p>
                  </div>

                  {/* Structured Details */}
                  <div className="glass-panel" style={{ padding: '16px' }}>
                    <h3 style={{ fontSize: '12px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '12px' }}>AI Extracted Fields</h3>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      <div>
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Interested Course</span>
                        <p style={{ fontSize: '13px', fontWeight: 600 }}>{selectedLead.extracted_data?.course || 'Unknown'}</p>
                      </div>
                      <div>
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Start Timeline</span>
                        <p style={{ fontSize: '13px', fontWeight: 600 }}>{selectedLead.extracted_data?.timeline || 'Flexible'}</p>
                      </div>
                      <div>
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Budget</span>
                        <p style={{ fontSize: '13px', fontWeight: 600 }}>{selectedLead.extracted_data?.budget || 'Unknown'}</p>
                      </div>
                      <div>
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Contact Channel</span>
                        <p style={{ fontSize: '13px', fontWeight: 600 }}>{selectedLead.extracted_data?.contact_channel || 'Email'}</p>
                      </div>
                      {selectedLead.lead_email && (
                        <div>
                          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Enquiry Email</span>
                          <p style={{ fontSize: '13px', fontWeight: 600, wordBreak: 'break-all' }}>{selectedLead.lead_email}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Recommendation actions */}
                  <div className="glass-panel" style={{ padding: '16px' }}>
                    <h3 style={{ fontSize: '12px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '12px' }}>Admissions Recommendation</h3>
                    
                    <div style={{ marginBottom: '10px' }}>
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Next Action</span>
                      <input 
                        type="text"
                        value={editAction}
                        onChange={(e) => setEditAction(e.target.value)}
                        style={{
                          width: '100%',
                          background: 'rgba(255, 255, 255, 0.03)',
                          border: '1px solid var(--border-color)',
                          color: 'var(--text-primary)',
                          borderRadius: '6px',
                          padding: '6px 10px',
                          fontSize: '13px',
                          marginTop: '4px',
                          outline: 'none'
                        }}
                      />
                    </div>

                    <div>
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Action Context</span>
                      <textarea
                        rows="3"
                        value={editDetails}
                        onChange={(e) => setEditDetails(e.target.value)}
                        style={{
                          width: '100%',
                          background: 'rgba(255, 255, 255, 0.03)',
                          border: '1px solid var(--border-color)',
                          color: 'var(--text-primary)',
                          borderRadius: '6px',
                          padding: '6px 10px',
                          fontSize: '12px',
                          marginTop: '4px',
                          resize: 'none',
                          outline: 'none'
                        }}
                      />
                    </div>

                    {selectedLead.recommendation?.calendar_event && (
                      <div style={{
                        marginTop: '12px',
                        padding: '10px',
                        borderRadius: '8px',
                        background: 'rgba(16, 185, 129, 0.08)',
                        border: '1.5px solid rgba(16, 185, 129, 0.2)'
                      }}>
                        <p style={{ fontSize: '10px', color: 'var(--secondary)', fontWeight: 700, textTransform: 'uppercase' }}>Calendar Slot Scheduled</p>
                        <p style={{ fontSize: '11px', fontWeight: 600, marginTop: '2px' }}>{selectedLead.recommendation.calendar_event.start_time}</p>
                        <a href={selectedLead.recommendation.calendar_event.meet_link} target="_blank" rel="noreferrer" style={{ fontSize: '11px', color: 'var(--primary)', textDecoration: 'none', display: 'block', marginTop: '4px', fontWeight: 600 }}>
                          Join Meet Session ↗
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                {/* Right Side: Communication Drafts & History */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* Email Draft Workspace */}
                  <div className="glass-panel" style={{ padding: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                      <div style={{ width: '20px', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '4px', background: 'rgba(99, 102, 241, 0.15)', color: 'var(--primary)' }}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                      </div>
                      <h3 style={{ fontSize: '14px', fontWeight: 700 }}>Email Outreach Workspace</h3>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      <div>
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Subject Line</label>
                        <input
                          type="text"
                          value={editSubject}
                          onChange={(e) => setEditSubject(e.target.value)}
                          style={{
                            width: '100%',
                            background: 'rgba(255, 255, 255, 0.02)',
                            border: '1px solid var(--border-color)',
                            color: 'var(--text-primary)',
                            borderRadius: '8px',
                            padding: '10px',
                            fontSize: '13px',
                            marginTop: '4px',
                            outline: 'none'
                          }}
                        />
                      </div>
                      <div>
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Email Body</label>
                        <textarea
                          rows="6"
                          value={editEmailBody}
                          onChange={(e) => setEditEmailBody(e.target.value)}
                          style={{
                            width: '100%',
                            background: 'rgba(255, 255, 255, 0.02)',
                            border: '1px solid var(--border-color)',
                            color: 'var(--text-primary)',
                            borderRadius: '8px',
                            padding: '12px',
                            fontSize: '13px',
                            lineHeight: 1.5,
                            marginTop: '4px',
                            outline: 'none',
                            fontFamily: 'inherit'
                          }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* WhatsApp Draft Workspace */}
                  <div className="glass-panel" style={{ padding: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                      <div style={{ width: '20px', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: 'var(--secondary)' }}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
                      </div>
                      <h3 style={{ fontSize: '14px', fontWeight: 700 }}>WhatsApp Chat Workspace</h3>
                    </div>

                    <div>
                      <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>WhatsApp Message Draft</label>
                      <textarea
                        rows="3"
                        value={editWhatsappBody}
                        onChange={(e) => setEditWhatsappBody(e.target.value)}
                        style={{
                          width: '100%',
                          background: 'rgba(255, 255, 255, 0.02)',
                          border: '1px solid var(--border-color)',
                          color: 'var(--text-primary)',
                          borderRadius: '8px',
                          padding: '12px',
                          fontSize: '13px',
                          lineHeight: 1.5,
                          marginTop: '4px',
                          outline: 'none',
                          fontFamily: 'inherit'
                        }}
                      />
                    </div>
                  </div>

                  {/* History Timeline */}
                  <div className="glass-panel" style={{ padding: '20px' }}>
                    <h3 style={{ fontSize: '12px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '12px' }}>Audit Trail & Execution Steps</h3>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {selectedLead.history?.map((step, idx) => (
                        <div key={idx} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                          <div style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            background: step.event.includes('fail') ? 'var(--hot)' : 'var(--primary)',
                            marginTop: '4px',
                            flexShrink: 0
                          }}/>
                          <div>
                            <p style={{ fontSize: '12px', fontWeight: 600 }}>{step.event.replace(/_/g, ' ')}</p>
                            <p style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                              {step.details} • {new Date(step.timestamp).toLocaleTimeString()}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

              </div>

              {/* Workspace Action Footer */}
              <div style={{
                padding: '16px 24px',
                borderTop: '1px solid var(--border-color)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: 'rgba(10, 11, 18, 0.5)',
                flexShrink: 0
              }}>
                <button
                  onClick={handleRejectDraft}
                  disabled={actionLoading || selectedLead.draft?.status === 'rejected'}
                  style={{
                    padding: '10px 20px',
                    borderRadius: '8px',
                    background: 'transparent',
                    border: '1.5px solid rgba(244, 63, 94, 0.4)',
                    color: 'var(--hot)',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontSize: '13px'
                  }}
                >
                  Reject & Archive
                </button>

                <div style={{ display: 'flex', gap: '12px' }}>
                  <button
                    onClick={handleSaveChanges}
                    disabled={isSaving}
                    style={{
                      padding: '10px 20px',
                      borderRadius: '8px',
                      background: 'rgba(255,255,255,0.05)',
                      border: '1px solid var(--border-color)',
                      color: 'var(--text-primary)',
                      fontWeight: 600,
                      cursor: 'pointer',
                      fontSize: '13px'
                    }}
                  >
                    {isSaving ? 'Saving...' : 'Save Draft Edits'}
                  </button>

                  <button
                    onClick={handleApproveDraft}
                    disabled={actionLoading || selectedLead.draft?.status === 'approved'}
                    style={{
                      padding: '10px 24px',
                      borderRadius: '8px',
                      background: 'linear-gradient(135deg, var(--secondary) 0%, #059669 100%)',
                      border: 'none',
                      color: '#fff',
                      fontWeight: 700,
                      cursor: 'pointer',
                      fontSize: '13px',
                      boxShadow: '0 4px 15px var(--secondary-glow)'
                    }}
                  >
                    {actionLoading ? 'Dispatched...' : selectedLead.draft?.status === 'approved' ? 'Comms Dispatched ✅' : 'Approve & Dispatch Outreach'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>
      </main>

      {/* Lead Intake Modal */}
      {showIntakeModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.6)',
          backdropFilter: 'blur(5px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100
        }}>
          <div className="glass-panel" style={{
            width: '500px',
            padding: '24px',
            boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
            border: '1px solid rgba(255,255,255,0.1)'
          }}>
            <h2 style={{ fontSize: '18px', fontWeight: 800, marginBottom: '16px' }}>Simulate New Lead Entry</h2>
            
            <form onSubmit={handleIntakeSubmit}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>Lead Ingest Channel</label>
                <select
                  value={newLeadSource}
                  onChange={(e) => setNewLeadSource(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid var(--border-color)',
                    color: '#fff',
                    borderRadius: '8px',
                    padding: '10px',
                    outline: 'none',
                    fontSize: '13px'
                  }}
                >
                  <option style={{ background: '#121420' }} value="webform">Website Form Inquiry</option>
                  <option style={{ background: '#121420' }} value="whatsapp">WhatsApp Message</option>
                  <option style={{ background: '#121420' }} value="email">Email Message (Gmail MCP)</option>
                </select>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  {newLeadSource === 'email' ? 'Email Message Identifier' : 'Raw Lead Content'}
                </label>
                {newLeadSource === 'email' && systemConfig.is_mock ? (
                  <select
                    value={newLeadText}
                    onChange={(e) => setNewLeadText(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'rgba(255,255,255,0.05)',
                      border: '1px solid var(--border-color)',
                      color: '#fff',
                      borderRadius: '8px',
                      padding: '10px',
                      outline: 'none',
                      fontSize: '13px'
                    }}
                    required
                  >
                    <option value="">-- Select Email Template from Inbox --</option>
                    <option style={{ background: '#121420' }} value="msg-001">msg-001 (John's AI Course Enquiry)</option>
                    <option style={{ background: '#121420' }} value="msg-002">msg-002 (Sarah's Data Science Bootcamp Enquiry)</option>
                  </select>
                ) : (
                  <textarea
                    rows="4"
                    placeholder={newLeadSource === 'email' ? "Enter search keyword, sender email, or Subject line of the email in your Gmail inbox..." : "Enter details, e.g.: I want to enroll in the AI course tomorrow. Budget is $1000. Send information."}
                    value={newLeadText}
                    onChange={(e) => setNewLeadText(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'rgba(255,255,255,0.02)',
                      border: '1px solid var(--border-color)',
                      color: '#fff',
                      borderRadius: '8px',
                      padding: '12px',
                      outline: 'none',
                      fontSize: '13px',
                      resize: 'vertical'
                    }}
                    required
                  />
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowIntakeModal(false)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    background: 'transparent',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-secondary)',
                    cursor: 'pointer',
                    fontSize: '13px'
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={intakeLoading}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    background: 'var(--primary)',
                    border: 'none',
                    color: '#fff',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontSize: '13px'
                  }}
                >
                  {intakeLoading ? 'Ingesting...' : 'Run Agents Pipeline'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
