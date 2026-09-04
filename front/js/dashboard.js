/* ==========================================================================
   STEG Facture Platform - Dashboard & Data Management
   ========================================================================== */

const Dashboard = {
  // In-Memory Data Store (Synchronized with SQL Server via FastAPI)
  factures: [], // Always populated from the backend; never hardcoded.

  backendStats: null,

  init() {
    this.renderStats();
    this.renderFacturesTable();
    if (window.Analytics) window.Analytics.loadEmbed();
    if (window.Auth && window.Auth.isAuthenticated()) {
      this.fetchDataFromBackend();
    }
  },

  async fetchDataFromBackend() {
    if (!window.Auth || !Auth.isAuthenticated()) return;

    try {
      // 1. Fetch user's invoices from SQL Server via FastAPI
      const invRes = await Auth.apiFetch('/invoices/mine');
      if (invRes.ok) {
        const invData = await invRes.json();
        // Always replace factures with real data (even an empty list),
        // so no hardcoded demo records ever leak through to real users.
        this.factures = (invData.invoices || []).map(i => ({
          id: i.invoice_id,
          supplier: i.supplier || "STEG",
          address: i.address || "",
          invoice_no: i.invoice_no || `INV-${i.invoice_id}`,
          invoice_date: i.invoice_date || i.uploaded_at?.split('T')[0] || null,
          amount_excl_tax: i.amount_excl_tax || 0,
          net_a_payer: i.net_a_payer || 0,
          currency: i.currency || "TND",
          kwh_consumed: i.kwh_consumed || 0,
           status: i.status || "uploaded",
           uploaded_at: i.uploaded_at,
           file_path: i.file_path,
          demand_id: i.demand_id ? `DEM-${i.demand_id}` : null,
          raw_demand_id: i.demand_id,

          // 17 Detailed tariff breakdown fields (STEG OCR Expansion)
          consumption_jour: i.consumption_jour ?? 0,
          consumption_pointe: i.consumption_pointe ?? 0,
          consumption_soiree: i.consumption_soiree ?? 0,
          consumption_nuit: i.consumption_nuit ?? 0,
          pu_jour: i.pu_jour ?? 0,
          pu_pointe: i.pu_pointe ?? 0,
          pu_soiree: i.pu_soiree ?? 0,
          pu_nuit: i.pu_nuit ?? 0,
          montant_jour: i.montant_jour ?? 0,
          montant_pointe: i.montant_pointe ?? 0,
          montant_soiree: i.montant_soiree ?? 0,
          montant_nuit: i.montant_nuit ?? 0,
          sous_total: i.sous_total ?? 0,
          total_1: i.total_1 ?? 0,
          total_2: i.total_2 ?? 0,
          total_3: i.total_3 ?? 0,
          net_a_payer: i.net_a_payer ?? 0
        }));
      }

      // 2. Fetch dashboard stats
      const statsRes = await Auth.apiFetch('/dashboard/me');
      if (statsRes.ok) {
        this.backendStats = await statsRes.json();
      }

      this.renderStats();
      this.renderFacturesTable();
    } catch (e) {
      console.warn('Dashboard fetch warning:', e);
    }
  },

  renderStats() {
    let totalFactures = this.factures.length;
    let pendingDemands = this.factures.filter(f => f.status === 'pending').length;
    let validatedDemands = this.factures.filter(f => f.status === 'approved').length;
    let totalKwh = this.factures.reduce((sum, f) => sum + (f.kwh_consumed || 0), 0);

    if (this.backendStats) {
      totalFactures = this.backendStats.total_invoices ?? totalFactures;
      pendingDemands = this.backendStats.pending_demands ?? pendingDemands;
      validatedDemands = this.backendStats.validated_demands ?? validatedDemands;
      totalKwh = this.backendStats.total_kwh ?? totalKwh;
    }

    const elTotal = document.getElementById('statTotalFactures');
    const elPending = document.getElementById('statPendingDemands');
    const elValidated = document.getElementById('statValidatedDemands');
    const elKwh = document.getElementById('statTotalKwh');

    if (elTotal) elTotal.textContent = totalFactures;
    if (elPending) elPending.textContent = pendingDemands;
    if (elValidated) elValidated.textContent = validatedDemands;
    if (elKwh) elKwh.textContent = totalKwh.toLocaleString() + ' kWh';
  },

  renderFacturesTable() {
    const tbody = document.getElementById('facturesTableBody');
    if (!tbody) return;

    if (this.factures.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color: var(--text-dim);">No invoices uploaded yet.</td></tr>`;
      return;
    }

    const statusBadgeMap = {
      uploaded: '<span class="badge badge-uploaded"><i class="fa-solid fa-cloud-arrow-up"></i> Uploaded</span>',
      pending: '<span class="badge badge-pending"><i class="fa-solid fa-hourglass-half"></i> Admin Pending</span>',
      approved: '<span class="badge badge-validated"><i class="fa-solid fa-circle-check"></i> Approved</span>',
      validated: '<span class="badge badge-validated"><i class="fa-solid fa-circle-check"></i> Approved</span>',
      rejected: '<span class="badge badge-rejected"><i class="fa-solid fa-circle-xmark"></i> Rejected</span>'
    };

    tbody.innerHTML = this.factures.map(f => `
      <tr>
        <td>
          <strong style="color: var(--accent-cyan); font-family:var(--font-heading);">${f.invoice_no}</strong>
          <div style="font-size: 0.75rem; color: var(--text-dim);">${f.supplier}</div>
        </td>
        <td>${UI.formatDate(f.invoice_date)}</td>
        <td><strong>${f.kwh_consumed} kWh</strong></td>
        <td><span style="font-family: var(--font-mono); font-weight:800; color:var(--text-main);">${UI.formatTND(f.net_a_payer)}</span></td>
        <td>${statusBadgeMap[f.status] || f.status}</td>
        <td style="text-align: right; display: flex; gap: 0.35rem; justify-content: flex-end;">
           <button class="btn btn-secondary btn-sm" onclick="Dashboard.openInspectModal('${f.id}')" title="View invoice details">
             <i class="fa-solid fa-eye"></i> Details
           </button>
           <button class="btn btn-secondary btn-sm" onclick="Dashboard.viewInvoiceFile('${f.id}')" title="View PDF File">
             <i class="fa-solid fa-file-pdf"></i> View PDF File
           </button>
           <button class="btn btn-secondary btn-sm" onclick="Dashboard.openEditModal('${f.id}')" title="Verify or edit OCR values">
             <i class="fa-solid fa-pen-to-square"></i> Verify / Edit
          </button>
          <button class="btn btn-danger btn-sm" onclick="Dashboard.deleteInvoice('${f.id}')" title="Delete Facture" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.4);">
            <i class="fa-solid fa-trash-can"></i>
          </button>
          ${!f.raw_demand_id && f.status !== 'pending' && f.status !== 'approved' && f.status !== 'rejected' ? `
            <button class="btn btn-primary btn-sm" onclick="Dashboard.submitDemand('${f.id}')">
              <i class="fa-solid fa-paper-plane"></i> Submit Demand
            </button>
          ` : ''}
        </td>
      </tr>
    `).join('');
  },

  async viewInvoiceFile(invoiceId) {
    const invoice = this.factures.find(f => String(f.id) === String(invoiceId));
    if (!invoice?.file_path) {
      UI.showToast('No scanned file is linked to this invoice.', 'warning');
      return;
    }
    const url = '/' + String(invoice.file_path).replace(/^\/+/, '');
    try {
      const head = await fetch(url, { method: 'HEAD' });
      if (!head.ok) {
        UI.showToast('Scanned file not found on the server.', 'warning');
        return;
      }
    } catch (e) {
      console.warn('File reachability check failed, opening anyway:', e);
    }
    window.open(url, '_blank', 'noopener');
  },

  // Save User Validated OCR Fields (Persisted to backend if server available)
  async saveUserValidation(factureData) {
    factureData.status = 'uploaded';

    if (factureData.id && typeof factureData.id === 'number') {
      try {
        const payload = {
          supplier: factureData.supplier,
          address: factureData.address || null,
          invoice_no: factureData.invoice_no,
          invoice_date: factureData.invoice_date,
          amount_excl_tax: factureData.amount_excl_tax,
          currency: factureData.currency || 'TND',
          kwh_consumed: factureData.kwh_consumed || 0,

          // 17 Tariff fields
          consumption_jour: factureData.consumption_jour ?? 0,
          consumption_pointe: factureData.consumption_pointe ?? 0,
          consumption_soiree: factureData.consumption_soiree ?? 0,
          consumption_nuit: factureData.consumption_nuit ?? 0,
          pu_jour: factureData.pu_jour ?? 0,
          pu_pointe: factureData.pu_pointe ?? 0,
          pu_soiree: factureData.pu_soiree ?? 0,
          pu_nuit: factureData.pu_nuit ?? 0,
          montant_jour: factureData.montant_jour ?? 0,
          montant_pointe: factureData.montant_pointe ?? 0,
          montant_soiree: factureData.montant_soiree ?? 0,
          montant_nuit: factureData.montant_nuit ?? 0,
          sous_total: factureData.sous_total ?? 0,
          total_1: factureData.total_1 ?? 0,
          total_2: factureData.total_2 ?? 0,
          total_3: factureData.total_3 ?? 0,
          net_a_payer: factureData.net_a_payer ?? 0
        };
        const res = await Auth.apiFetch(`/invoices/${factureData.id}/values`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          await this.fetchDataFromBackend();
          if (window.Admin) window.Admin.fetchQueueFromBackend();
          UI.showToast(`Invoice ${factureData.invoice_no} confirmed & submitted to Admin Queue!`, 'success');
          return true;
        }
        const err = await res.json().catch(() => ({}));
        UI.showToast(err.detail || 'Could not save invoice values.', 'danger');
      } catch (e) {
        console.warn('Backend update failed', e);
        UI.showToast('Backend unreachable — values not saved', 'danger');
      }
    }

    return false;
  },

  // Submit Demand for Admin Approval (Connected to /demands POST)
  async submitDemand(factureId) {
    const numId = Number(factureId);
    try {
      const res = await Auth.apiFetch('/demands', {
        method: 'POST',
        body: JSON.stringify({ invoice_id: numId })
      });

      if (res.ok) {
        const demand = await res.json();
        UI.showToast(`Demand DEM-${demand.demand_id} submitted to STEG Admin!`, 'success');
        await this.fetchDataFromBackend();
        if (window.Admin) window.Admin.fetchQueueFromBackend();
        return;
      } else {
        const err = await res.json();
        UI.showToast(err.detail || 'Failed to submit demand.', 'danger');
      }
    } catch (e) {
      console.warn('Submit demand API error', e);
      UI.showToast('Backend unreachable — demand not submitted', 'danger');
    }
  },

  async openEditModal(factureId) {
    if (!factureId) {
      UI.showToast('Invalid invoice ID.', 'danger');
      return;
    }

    let item = this.factures.find(f => f.id == factureId);

    if (!item && window.Auth && Auth.isAuthenticated()) {
      try {
        const res = await Auth.apiFetch(`/invoices/${factureId}`);
        if (res.ok) {
          const i = await res.json();
          item = {
            id: i.invoice_id,
            supplier: i.supplier || "STEG",
            address: i.address || "",
            invoice_no: i.invoice_no || `INV-${i.invoice_id}`,
            invoice_date: i.invoice_date || i.uploaded_at?.split('T')[0] || null,
            amount_excl_tax: i.amount_excl_tax || 0,
          net_a_payer: i.net_a_payer || 0,
            currency: i.currency || "TND",
            kwh_consumed: i.kwh_consumed || 0,
            status: i.status || "uploaded",
            uploaded_at: i.uploaded_at,
            demand_id: i.demand_id ? `DEM-${i.demand_id}` : null,
            raw_demand_id: i.demand_id,

            consumption_jour: i.consumption_jour ?? 0,
            consumption_pointe: i.consumption_pointe ?? 0,
            consumption_soiree: i.consumption_soiree ?? 0,
            consumption_nuit: i.consumption_nuit ?? 0,
            pu_jour: i.pu_jour ?? 0,
            pu_pointe: i.pu_pointe ?? 0,
            pu_soiree: i.pu_soiree ?? 0,
            pu_nuit: i.pu_nuit ?? 0,
            montant_jour: i.montant_jour ?? 0,
            montant_pointe: i.montant_pointe ?? 0,
            montant_soiree: i.montant_soiree ?? 0,
            montant_nuit: i.montant_nuit ?? 0,
            sous_total: i.sous_total ?? 0,
            total_1: i.total_1 ?? 0,
            total_2: i.total_2 ?? 0,
            total_3: i.total_3 ?? 0,
            net_a_payer: i.net_a_payer ?? 0
          };
        }
      } catch (err) {
        console.error('Failed to fetch invoice for editing:', err);
      }
    }

    if (!item) {
      UI.showToast('Could not load invoice details for editing.', 'danger');
      return;
    }

    const formatDateForInput = (dStr) => {
      if (!dStr) return '';
      const raw = String(dStr).trim();
      const datePart = raw.includes('T') ? raw.split('T')[0] : raw;
      if (!datePart) return '';
      const date = new Date(`${datePart}T12:00:00`);
      if (Number.isNaN(date.getTime())) return datePart;
      const normalized = new Date(date.getFullYear(), date.getMonth(), 1);
      return normalized.toISOString().split('T')[0];
    };
    const formatDateForMonthInput = (dStr) => dStr ? String(dStr).split('T')[0].substring(0, 7) : '';
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = (val !== null && val !== undefined) ? val : '';
    };

    setVal('editInvoiceId', item.id);
    setVal('editSupplier', item.supplier || 'STEG');
    setVal('editAddress', item.address || '');
    setVal('editInvoiceNo', item.invoice_no || '');
    setVal('editInvoiceDate', formatDateForInput(item.invoice_date || item.uploaded_at));
    setVal('editUploadedAt', item.uploaded_at ? item.uploaded_at.split('T')[0] + ' ' + item.uploaded_at.split('T')[1]?.slice(0, 5) : '');
    setVal('editAmountExclTax', item.amount_excl_tax || 0);
    setVal('editKwhConsumed', item.kwh_consumed || 0);

    // Populate tariff fields in edit modal
    setVal('editConsJour', item.consumption_jour ?? 0);
    setVal('editConsPointe', item.consumption_pointe ?? 0);
    setVal('editConsSoiree', item.consumption_soiree ?? 0);
    setVal('editConsNuit', item.consumption_nuit ?? 0);

    setVal('editPuJour', item.pu_jour ?? 0);
    setVal('editPuPointe', item.pu_pointe ?? 0);
    setVal('editPuSoiree', item.pu_soiree ?? 0);
    setVal('editPuNuit', item.pu_nuit ?? 0);

    setVal('editMontantJour', item.montant_jour ?? 0);
    setVal('editMontantPointe', item.montant_pointe ?? 0);
    setVal('editMontantSoiree', item.montant_soiree ?? 0);
    setVal('editMontantNuit', item.montant_nuit ?? 0);

    setVal('editSousTotal', item.sous_total ?? 0);
    setVal('editTotal1', item.total_1 ?? 0);
    setVal('editTotal2', item.total_2 ?? 0);
    setVal('editTotal3', item.total_3 ?? 0);
    setVal('editNetAPayer', item.net_a_payer ?? 0);

    UI.openModal('editInvoiceModal');
  },

  async saveInvoiceEdit(e) {
    e.preventDefault();
    const invoiceId = document.getElementById('editInvoiceId').value;
    if (!invoiceId) return;

    let dateVal = document.getElementById('editInvoiceDate').value;
    if (dateVal) {
      const dateObj = new Date(`${dateVal}T12:00:00`);
      if (!Number.isNaN(dateObj.getTime())) {
        dateObj.setDate(1);
        dateVal = `${dateObj.getFullYear()}-${String(dateObj.getMonth() + 1).padStart(2, '0')}-01`;
      }
    }

    const getNum = (id, defaultVal = 0) => {
      const el = document.getElementById(id);
      if (!el || el.value === '') return defaultVal;
      return parseFloat(el.value) || defaultVal;
    };
    const getInt = (id, defaultVal = 0) => {
      const el = document.getElementById(id);
      if (!el || el.value === '') return defaultVal;
      return parseInt(el.value, 10) || defaultVal;
    };

    const payload = {
      supplier: document.getElementById('editSupplier').value,
      address: document.getElementById('editAddress').value.trim() || null,
      invoice_no: document.getElementById('editInvoiceNo').value,
      invoice_date: dateVal || null,
      amount_excl_tax: getNum('editAmountExclTax'),
      currency: 'TND',
      kwh_consumed: getInt('editKwhConsumed'),

      // Tariff fields
      consumption_jour: getInt('editConsJour'),
      consumption_pointe: getInt('editConsPointe'),
      consumption_soiree: getInt('editConsSoiree'),
      consumption_nuit: getInt('editConsNuit'),

      pu_jour: getNum('editPuJour'),
      pu_pointe: getNum('editPuPointe'),
      pu_soiree: getNum('editPuSoiree'),
      pu_nuit: getNum('editPuNuit'),

      montant_jour: getNum('editMontantJour'),
      montant_pointe: getNum('editMontantPointe'),
      montant_soiree: getNum('editMontantSoiree'),
      montant_nuit: getNum('editMontantNuit'),

      sous_total: getNum('editSousTotal'),
      total_1: getNum('editTotal1'),
      total_2: getNum('editTotal2'),
      total_3: getNum('editTotal3'),
      net_a_payer: getNum('editNetAPayer')
    };

    try {
      const res = await Auth.apiFetch(`/invoices/${invoiceId}/values`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const updatedInvoice = await res.json();
        UI.closeModal('editInvoiceModal');
        await this.fetchDataFromBackend();

        if (window.Admin && Auth.currentUser?.role === 'admin') {
          window.Admin.fetchQueueFromBackend();
          window.Admin.fetchAuditLogs();
        }

        if (updatedInvoice.demand_id) {
          UI.showToast(`Invoice updated! Demand DEM-${updatedInvoice.demand_id} reset to Pending Admin Review.`, 'info');
        } else {
          UI.showToast(`Invoice ${updatedInvoice.invoice_no} updated successfully!`, 'success');
        }
        if (window.App) window.App.renderUserDemandsTable();
      } else {
        const err = await res.json();
        UI.showToast(err.detail || 'Failed to update invoice.', 'danger');
      }
    } catch (err) {
      console.error('Error saving invoice edit:', err);
      UI.showToast('Network error while saving invoice changes.', 'danger');
    }
  },

  async deleteInvoice(factureId) {
    if (!confirm(`Are you sure you want to delete invoice #${factureId}? This action cannot be undone.`)) {
      return;
    }

    try {
      const res = await Auth.apiFetch(`/invoices/${factureId}`, {
        method: 'DELETE'
      });

      if (res.ok) {
        UI.showToast(`Invoice #${factureId} deleted.`, 'success');
        await this.fetchDataFromBackend();
        if (window.App) window.App.renderUserDemandsTable();
        if (window.Admin && Auth.currentUser?.role === 'admin') {
          window.Admin.fetchQueueFromBackend();
        }
      } else {
        const err = await res.json();
        UI.showToast(err.detail || 'Failed to delete invoice.', 'danger');
      }
    } catch (err) {
      console.error('Error deleting invoice:', err);
      UI.showToast('Network error while deleting invoice.', 'danger');
    }
  },

  async deleteDemand(demandId) {
    if (!confirm(`Are you sure you want to delete demand DEM-${demandId}?`)) {
      return;
    }

    try {
      const res = await Auth.apiFetch(`/demands/${demandId}`, {
        method: 'DELETE'
      });

      if (res.ok) {
        UI.showToast(`Demand DEM-${demandId} deleted.`, 'success');
        await this.fetchDataFromBackend();
        if (window.App) window.App.renderUserDemandsTable();
        if (window.Admin && Auth.currentUser?.role === 'admin') {
          window.Admin.fetchQueueFromBackend();
        }
      } else {
        const err = await res.json();
        UI.showToast(err.detail || 'Failed to delete demand.', 'danger');
      }
    } catch (err) {
      console.error('Error deleting demand:', err);
      UI.showToast('Network error while deleting demand.', 'danger');
    }
  },

  openInspectModal(factureId) {
    const item = this.factures.find(f => f.id == factureId);
    if (!item) return;

    const modalBody = document.getElementById('inspectModalBody');
    if (modalBody) {
      modalBody.innerHTML = `
        <div style="display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 1.5rem;">
          <div>
            <h4 style="margin-bottom:1rem; color:var(--accent-cyan);" class="gradient-text">Invoice Financial Breakdown</h4>
            <table style="width:100%; border-collapse:collapse; font-size:0.88rem;">
              <tr><td style="padding:0.4rem 0; color:var(--text-muted);">Supplier:</td><td><strong>${item.supplier}</strong></td></tr>
              <tr><td style="padding:0.4rem 0; color:var(--text-muted);">Address:</td><td><strong>${item.address || '-'}</strong></td></tr>
              <tr><td style="padding:0.4rem 0; color:var(--text-muted);">Invoice No:</td><td><strong>${item.invoice_no}</strong></td></tr>
              <tr><td style="padding:0.4rem 0; color:var(--text-muted);">Invoice Date:</td><td>${item.invoice_date}</td></tr>
              <tr><td style="padding:0.4rem 0; color:var(--text-muted);">Amount Excl. Tax (HT):</td><td>${UI.formatTND(item.amount_excl_tax)}</td></tr>
              <tr><td style="padding:0.4rem 0; color:var(--text-muted);">NET A PAYER (TTC):</td><td><strong style="font-family:var(--font-mono); font-size:1.1rem; color:var(--accent-emerald);">${UI.formatTND(item.net_a_payer)}</strong></td></tr>
              <tr><td style="padding:0.4rem 0; color:var(--text-muted);">Currency:</td><td>${item.currency}</td></tr>
            </table>

            <h5 style="margin-top:1.2rem; margin-bottom:0.5rem; color:var(--accent-cyan); font-size:0.85rem;">Tariff Breakdown (Tableau de Consommation)</h5>
            <table style="width:100%; border-collapse:collapse; font-size:0.8rem; border:1px solid var(--border-color); border-radius:var(--radius-sm);">
              <thead>
                <tr style="background:rgba(255,255,255,0.03); color:var(--text-muted);">
                  <th style="padding:0.3rem 0.5rem; text-align:left;">Période</th>
                  <th style="padding:0.3rem 0.5rem; text-align:right;">kWh</th>
                  <th style="padding:0.3rem 0.5rem; text-align:right;">P.U.</th>
                  <th style="padding:0.3rem 0.5rem; text-align:right;">Montant</th>
                </tr>
              </thead>
              <tbody>
                <tr><td style="padding:0.25rem 0.5rem; color:var(--text-dim);">Jour</td><td style="text-align:right;">${item.consumption_jour || 0}</td><td style="text-align:right;">${item.pu_jour || 0}</td><td style="text-align:right; font-family:var(--font-mono);">${UI.formatTND(item.montant_jour)}</td></tr>
                <tr><td style="padding:0.25rem 0.5rem; color:var(--text-dim);">Pointe</td><td style="text-align:right;">${item.consumption_pointe || 0}</td><td style="text-align:right;">${item.pu_pointe || 0}</td><td style="text-align:right; font-family:var(--font-mono);">${UI.formatTND(item.montant_pointe)}</td></tr>
                <tr><td style="padding:0.25rem 0.5rem; color:var(--text-dim);">Soirée</td><td style="text-align:right;">${item.consumption_soiree || 0}</td><td style="text-align:right;">${item.pu_soiree || 0}</td><td style="text-align:right; font-family:var(--font-mono);">${UI.formatTND(item.montant_soiree)}</td></tr>
                <tr><td style="padding:0.25rem 0.5rem; color:var(--text-dim);">Nuit</td><td style="text-align:right;">${item.consumption_nuit || 0}</td><td style="text-align:right;">${item.pu_nuit || 0}</td><td style="text-align:right; font-family:var(--font-mono);">${UI.formatTND(item.montant_nuit)}</td></tr>
              </tbody>
            </table>
          </div>
          <div style="background:var(--bg-primary); padding:1.5rem; border-radius:var(--radius-md); border:1px solid var(--border-color); display:flex; flex-direction:column; align-items:center; justify-content:center;">
            <i class="fa-solid fa-file-pdf" style="font-size:4rem; color:var(--accent-cyan); margin-bottom:1rem;"></i>
            <p style="font-size:0.85rem; color:var(--text-muted); text-align:center;">Source File Reference</p>
            <p style="font-family:var(--font-mono); font-size:0.8rem;">Invoice #${item.id}</p>
            <span class="badge badge-validated" style="margin-top:1rem;">Verified Document</span>
          </div>
        </div>
      `;
      UI.openModal('inspectModal');
    }
  }
};

window.Dashboard = Dashboard;
