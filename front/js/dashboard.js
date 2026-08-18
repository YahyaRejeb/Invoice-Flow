/* ==========================================================================
   STEG Facture Platform - Dashboard & Data Management
   ========================================================================== */

const Dashboard = {
  // In-Memory Data Store (Synchronized with SQL Server via FastAPI)
  factures: [], // Always populated from the backend; never hardcoded.

  backendStats: null,
  charts: {},

  init() {
    this.renderStats();
    this.renderFacturesTable();
    this.initCharts();
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
          tva: i.tva || 0,
          amount_incl_tax: i.amount_incl_tax || 0,
          currency: i.currency || "TND",
          kwh_consumed: i.kwh_consumed || 0,
          due_date: i.due_date || i.invoice_date || null,
          status: i.status || "uploaded",
          uploaded_at: i.uploaded_at,
          demand_id: i.demand_id ? `DEM-${i.demand_id}` : null,
          raw_demand_id: i.demand_id
        }));
      }

      // 2. Fetch dashboard stats
      const statsRes = await Auth.apiFetch('/dashboard/me');
      if (statsRes.ok) {
        this.backendStats = await statsRes.json();
      }

      this.renderStats();
      this.renderFacturesTable();
      this.initCharts();
    } catch (e) {
      console.warn('Dashboard fetch warning:', e);
    }
  },

  renderStats() {
    let totalFactures = this.factures.length;
    let pendingDemands = this.factures.filter(f => f.status === 'pending').length;
    let validatedDemands = this.factures.filter(f => f.status === 'validated').length;
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
        <td><span style="font-family: var(--font-mono); font-weight:800; color:var(--text-main);">${UI.formatTND(f.amount_incl_tax)}</span></td>
        <td>${UI.formatDate(f.due_date)}</td>
        <td>${statusBadgeMap[f.status] || f.status}</td>
        <td style="text-align: right; display: flex; gap: 0.35rem; justify-content: flex-end;">
          <button class="btn btn-secondary btn-sm" onclick="Dashboard.openInspectModal('${f.id}')" title="Inspect">
            <i class="fa-solid fa-eye"></i>
          </button>
          <button class="btn btn-secondary btn-sm" onclick="Dashboard.openEditModal('${f.id}')" title="Edit Facture">
            <i class="fa-solid fa-pen-to-square"></i> Edit
          </button>
          <button class="btn btn-danger btn-sm" onclick="Dashboard.deleteInvoice('${f.id}')" title="Delete Facture" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.4);">
            <i class="fa-solid fa-trash-can"></i>
          </button>
          ${!f.raw_demand_id && f.status !== 'pending' && f.status !== 'approved' && f.status !== 'validated' && f.status !== 'rejected' ? `
            <button class="btn btn-primary btn-sm" onclick="Dashboard.submitDemand('${f.id}')">
              <i class="fa-solid fa-paper-plane"></i> Submit Demand
            </button>
          ` : ''}
        </td>
      </tr>
    `).join('');
  },

  initCharts() {
    const kwhChartCtx = document.getElementById('kwhConsumptionChart');
    if (kwhChartCtx && window.Chart) {
      if (this.charts.kwh) this.charts.kwh.destroy();

      const gradientCyan = kwhChartCtx.getContext('2d').createLinearGradient(0, 0, 0, 250);
      gradientCyan.addColorStop(0, 'rgba(0, 242, 254, 0.85)');
      gradientCyan.addColorStop(1, 'rgba(127, 0, 255, 0.15)');

      const labels = this.factures.slice(0, 4).map(f => f.invoice_no).reverse();
      const kwhData = this.factures.slice(0, 4).map(f => f.kwh_consumed || 0).reverse();

      this.charts.kwh = new Chart(kwhChartCtx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Consumption (kWh)',
            data: kwhData,
            backgroundColor: gradientCyan,
            borderColor: 'var(--accent-cyan)',
            borderWidth: 2,
            borderRadius: 10
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: 'var(--text-muted)', font: { family: 'Outfit', weight: '600' } } }
          },
          scales: {
            x: { ticks: { color: 'var(--text-muted)' }, grid: { color: 'rgba(255,255,255,0.05)' } },
            y: { ticks: { color: 'var(--text-muted)' }, grid: { color: 'rgba(255,255,255,0.05)' } }
          }
        }
      });
    }

    const costChartCtx = document.getElementById('costDistributionChart');
    if (costChartCtx && window.Chart) {
      if (this.charts.cost) this.charts.cost.destroy();

      const latest = this.factures[0] || {};
      const ht = latest.amount_excl_tax || 0;
      const tva = latest.tva || 0;
      const total = latest.amount_incl_tax || 0;
      const extra = Math.max(0, total - (ht + tva));

      this.charts.cost = new Chart(costChartCtx, {
        type: 'doughnut',
        data: {
          labels: ['Amount Excl. Tax (HT)', 'TVA Tax Amount', 'Fixed Service Rates'],
          datasets: [{
            data: [ht, tva, extra],
            backgroundColor: ['var(--accent-cyan)', 'var(--accent-violet)', 'var(--accent-emerald)'],
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom', labels: { color: 'var(--text-muted)', font: { family: 'Plus Jakarta Sans' } } }
          }
        }
      });
    }
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
          tva: factureData.tva,
          amount_incl_tax: factureData.amount_incl_tax,
          currency: factureData.currency || 'TND',
          kwh_consumed: factureData.kwh_consumed || 0,
          due_date: factureData.due_date || factureData.invoice_date
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
            tva: i.tva || 0,
            amount_incl_tax: i.amount_incl_tax || 0,
            currency: i.currency || "TND",
            kwh_consumed: i.kwh_consumed || 0,
            due_date: i.due_date || i.invoice_date || null,
            status: i.status || "uploaded",
            uploaded_at: i.uploaded_at,
            demand_id: i.demand_id ? `DEM-${i.demand_id}` : null,
            raw_demand_id: i.demand_id
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

    const formatDateForInput = (dStr) => dStr ? String(dStr).split('T')[0] : '';
    const formatDateForMonthInput = (dStr) => dStr ? String(dStr).split('T')[0].substring(0, 7) : '';

    document.getElementById('editInvoiceId').value = item.id;
    document.getElementById('editSupplier').value = item.supplier || 'STEG';
    document.getElementById('editAddress').value = item.address || '';
    document.getElementById('editInvoiceNo').value = item.invoice_no || '';
    document.getElementById('editInvoiceDate').value = formatDateForMonthInput(item.invoice_date);
    document.getElementById('editDueDate').value = formatDateForInput(item.due_date);
    document.getElementById('editAmountExclTax').value = item.amount_excl_tax || 0;
    document.getElementById('editTva').value = item.tva || 0;
    document.getElementById('editAmountInclTax').value = item.amount_incl_tax || 0;
    document.getElementById('editKwhConsumed').value = item.kwh_consumed || 0;

    UI.openModal('editInvoiceModal');
  },

  async saveInvoiceEdit(e) {
    e.preventDefault();
    const invoiceId = document.getElementById('editInvoiceId').value;
    if (!invoiceId) return;

    let dateVal = document.getElementById('editInvoiceDate').value;
    if (dateVal && dateVal.length === 7) {
      dateVal += '-01';
    }

    const payload = {
      supplier: document.getElementById('editSupplier').value,
      address: document.getElementById('editAddress').value.trim() || null,
      invoice_no: document.getElementById('editInvoiceNo').value,
      invoice_date: dateVal || null,
      due_date: document.getElementById('editDueDate').value || null,
      amount_excl_tax: parseFloat(document.getElementById('editAmountExclTax').value) || 0,
      tva: parseFloat(document.getElementById('editTva').value) || 0,
      amount_incl_tax: parseFloat(document.getElementById('editAmountInclTax').value) || 0,
      currency: 'TND',
      kwh_consumed: parseInt(document.getElementById('editKwhConsumed').value, 10) || 0
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
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
          <div>
            <h4 style="margin-bottom:1rem; color:var(--accent-cyan);" class="gradient-text">Invoice Financial Breakdown</h4>
            <table style="width:100%; border-collapse:collapse; font-size:0.9rem;">
              <tr><td style="padding:0.5rem 0; color:var(--text-muted);">Supplier:</td><td><strong>${item.supplier}</strong></td></tr>
              <tr><td style="padding:0.5rem 0; color:var(--text-muted);">Address:</td><td><strong>${item.address || '-'}</strong></td></tr>
              <tr><td style="padding:0.5rem 0; color:var(--text-muted);">Invoice No:</td><td><strong>${item.invoice_no}</strong></td></tr>
              <tr><td style="padding:0.5rem 0; color:var(--text-muted);">Invoice Date:</td><td>${item.invoice_date}</td></tr>
              <tr><td style="padding:0.5rem 0; color:var(--text-muted);">Amount Excl. Tax (HT):</td><td>${UI.formatTND(item.amount_excl_tax)}</td></tr>
              <tr><td style="padding:0.5rem 0; color:var(--text-muted);">TVA Tax Amount:</td><td>${UI.formatTND(item.tva)}</td></tr>
              <tr><td style="padding:0.5rem 0; color:var(--text-muted);">Total Incl. Tax (TTC):</td><td><strong style="font-family:var(--font-mono); font-size:1.1rem; color:var(--accent-emerald);">${UI.formatTND(item.amount_incl_tax)}</strong></td></tr>
              <tr><td style="padding:0.5rem 0; color:var(--text-muted);">Currency:</td><td>${item.currency}</td></tr>
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

