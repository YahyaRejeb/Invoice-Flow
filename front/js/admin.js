/* ==========================================================================
   STEG Facture Platform - Admin Review Pipeline & Audit System
   ========================================================================== */

const Admin = {
  adminInvoices: [],
  adminUsers: [],
  auditLogs: [],

  init() {
    this.bindAdminForms();
    this.renderQueue();
    this.renderAuditLogs();
    if (window.Auth && window.Auth.isAuthenticated() && window.Auth.currentUser?.role === 'admin') {
      this.fetchQueueFromBackend();
      this.fetchAdminUsers();
      this.fetchAdminInvoices();
    }
  },

  bindAdminForms() {
    const userForm = document.getElementById('adminUserForm');
    const invoiceForm = document.getElementById('adminInvoiceForm');

    if (userForm) {
      userForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.saveUser();
      });
    }

    if (invoiceForm) {
      invoiceForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.saveInvoice();
      });

      // Auto-compute total consumption for admin invoice form
      const updateAdminTotalKwh = () => {
        const total = ['adminConsJour', 'adminConsPointe', 'adminConsSoiree', 'adminConsNuit']
          .reduce((sum, id) => sum + (parseInt(document.getElementById(id)?.value, 10) || 0), 0);
        const totalEl = document.getElementById('adminInvoiceKwh');
        if (totalEl) totalEl.value = total;
      };
      ['adminConsJour', 'adminConsPointe', 'adminConsSoiree', 'adminConsNuit']
        .forEach(id => document.getElementById(id)?.addEventListener('input', updateAdminTotalKwh));
    }
  },

  resetUserForm() {
    document.getElementById('adminUserId').value = '';
    document.getElementById('adminUserName').value = '';
    document.getElementById('adminUserEmail').value = '';
    document.getElementById('adminUserRole').value = 'user';
    document.getElementById('adminUserStatus').value = 'pending';
    document.getElementById('adminUserPassword').value = '';
  },

  resetInvoiceForm() {
    document.getElementById('adminInvoiceId').value = '';
    const userIdInput = document.getElementById('adminInvoiceUserId');
    if (userIdInput) {
      if (Auth.currentUser?.role === 'admin') {
        userIdInput.value = '';
        userIdInput.readOnly = false;
      } else {
        userIdInput.value = Auth.currentUser?.id || '';
        userIdInput.readOnly = true;
      }
    }
    document.getElementById('adminInvoiceSupplier').value = 'STEG';
    document.getElementById('adminInvoiceAddress').value = '';
    document.getElementById('adminInvoiceNo').value = '';
    document.getElementById('adminInvoiceDate').value = '';
    document.getElementById('adminInvoiceStatus').value = 'uploaded';
    document.getElementById('adminInvoiceAmountExclTax').value = '';
    document.getElementById('adminInvoiceNetAPayer').value = '';
    document.getElementById('adminInvoiceCurrency').value = 'TND';
    document.getElementById('adminInvoiceKwh').value = '';
    document.getElementById('adminInvoicePath').value = '';

    document.getElementById('adminConsJour').value = 0;
    document.getElementById('adminConsPointe').value = 0;
    document.getElementById('adminConsSoiree').value = 0;
    document.getElementById('adminConsNuit').value = 0;
    document.getElementById('adminPuJour').value = 0;
    document.getElementById('adminPuPointe').value = 0;
    document.getElementById('adminPuSoiree').value = 0;
    document.getElementById('adminPuNuit').value = 0;
    document.getElementById('adminMontantJour').value = 0;
    document.getElementById('adminMontantPointe').value = 0;
    document.getElementById('adminMontantSoiree').value = 0;
    document.getElementById('adminMontantNuit').value = 0;
    document.getElementById('adminSousTotal').value = 0;
    document.getElementById('adminTotal1').value = 0;
    document.getElementById('adminTotal2').value = 0;
    document.getElementById('adminTotal3').value = 0;
  },

  async saveUser() {
    if (!window.Auth || !Auth.isAuthenticated() || Auth.currentUser?.role !== 'admin') return;

    const id = document.getElementById('adminUserId').value;
    const payload = {
      full_name: document.getElementById('adminUserName').value.trim(),
      email: document.getElementById('adminUserEmail').value.trim(),
      role: document.getElementById('adminUserRole').value,
      account_status: document.getElementById('adminUserStatus').value,
    };
    const password = document.getElementById('adminUserPassword').value;
    if (password) payload.password = password;

    try {
      const res = id
        ? await Auth.apiFetch(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
        : await Auth.apiFetch('/admin/users', { method: 'POST', body: JSON.stringify(payload) });
      if (!res.ok) {
        const err = await res.json();
        UI.showToast(err.detail || 'Failed to save user', 'danger');
        return;
      }
      this.resetUserForm();
      await this.fetchAdminUsers();
      UI.showToast(id ? 'User updated.' : 'User created.', 'success');
    } catch (e) {
      console.warn('Save user failed:', e);
      UI.showToast('Unable to save user.', 'danger');
    }
  },

  async saveInvoice() {
    if (!window.Auth || !Auth.isAuthenticated()) return;
    const isAdmin = Auth.currentUser?.role === 'admin';
    const id = document.getElementById('adminInvoiceId').value;

    const num = (elId) => {
      const el = document.getElementById(elId);
      if (!el) return null;
      const v = el.value;
      return v === '' || v === null ? null : Number(v);
    };

    if (isAdmin) {
      let dateVal = document.getElementById('adminInvoiceDate').value;
      if (dateVal && dateVal.length === 7) {
        dateVal += '-01';
      }

      const payload = {
        user_id: Number(document.getElementById('adminInvoiceUserId').value) || Auth.currentUser.id,
        supplier: document.getElementById('adminInvoiceSupplier').value.trim() || 'STEG',
        address: document.getElementById('adminInvoiceAddress').value.trim() || null,
        invoice_no: document.getElementById('adminInvoiceNo').value.trim() || null,
        invoice_date: dateVal || null,
        status: document.getElementById('adminInvoiceStatus').value,
        amount_excl_tax: num('adminInvoiceAmountExclTax'),
        net_a_payer: num('adminInvoiceNetAPayer'),
        currency: document.getElementById('adminInvoiceCurrency').value.trim() || 'TND',
        kwh_consumed: num('adminInvoiceKwh'),
        file_path: document.getElementById('adminInvoicePath').value.trim() || 'uploads/unknown.pdf',
        // Detailed fields:
        consumption_jour: num('adminConsJour'),
        consumption_pointe: num('adminConsPointe'),
        consumption_soiree: num('adminConsSoiree'),
        consumption_nuit: num('adminConsNuit'),
        pu_jour: num('adminPuJour'),
        pu_pointe: num('adminPuPointe'),
        pu_soiree: num('adminPuSoiree'),
        pu_nuit: num('adminPuNuit'),
        montant_jour: num('adminMontantJour'),
        montant_pointe: num('adminMontantPointe'),
        montant_soiree: num('adminMontantSoiree'),
        montant_nuit: num('adminMontantNuit'),
        sous_total: num('adminSousTotal'),
        total_1: num('adminTotal1'),
        total_2: num('adminTotal2'),
        total_3: num('adminTotal3'),
      };

      try {
        const res = id
          ? await Auth.apiFetch(`/admin/invoices/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
          : await Auth.apiFetch('/admin/invoices', { method: 'POST', body: JSON.stringify(payload) });
        if (!res.ok) {
          const err = await res.json();
          UI.showToast(err.detail || 'Failed to save invoice', 'danger');
          return;
        }
        this.resetInvoiceForm();
        await this.fetchAdminInvoices();
        UI.showToast(id ? 'Invoice updated.' : 'Invoice created.', 'success');
      } catch (e) {
        console.warn('Save invoice failed:', e);
        UI.showToast('Unable to save invoice.', 'danger');
      }
    } else {
      // Regular User modifying invoice in OCR Management interface
      if (!id) {
        UI.showToast('Please select an invoice from the table to edit.', 'warning');
        return;
      }

      const payload = {
        supplier: document.getElementById('adminInvoiceSupplier').value.trim() || 'STEG',
        address: document.getElementById('adminInvoiceAddress').value.trim() || null,
        invoice_no: document.getElementById('adminInvoiceNo').value.trim() || null,
        invoice_date: document.getElementById('adminInvoiceDate').value || null,
        amount_excl_tax: num('adminInvoiceAmountExclTax') || 0,
        net_a_payer: num('adminInvoiceNetAPayer') || 0,
        currency: document.getElementById('adminInvoiceCurrency').value.trim() || 'TND',
        kwh_consumed: num('adminInvoiceKwh') || 0,
        // Detailed fields:
        consumption_jour: num('adminConsJour'),
        consumption_pointe: num('adminConsPointe'),
        consumption_soiree: num('adminConsSoiree'),
        consumption_nuit: num('adminConsNuit'),
        pu_jour: num('adminPuJour'),
        pu_pointe: num('adminPuPointe'),
        pu_soiree: num('adminPuSoiree'),
        pu_nuit: num('adminPuNuit'),
        montant_jour: num('adminMontantJour'),
        montant_pointe: num('adminMontantPointe'),
        montant_soiree: num('adminMontantSoiree'),
        montant_nuit: num('adminMontantNuit'),
        sous_total: num('adminSousTotal'),
        total_1: num('adminTotal1'),
        total_2: num('adminTotal2'),
        total_3: num('adminTotal3'),
      };

      try {
        const res = await Auth.apiFetch(`/invoices/${id}/values`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const err = await res.json();
          UI.showToast(err.detail || 'Failed to save invoice changes', 'danger');
          return;
        }

        const updated = await res.json();
        this.resetInvoiceForm();
        await this.fetchAdminInvoices();
        if (window.Dashboard) window.Dashboard.fetchDataFromBackend();
        if (window.App) window.App.renderUserDemandsTable();

        if (updated.demand_id) {
          UI.showToast(`Invoice updated! Demand DEM-${updated.demand_id} automatically reset to Pending Admin Review.`, 'info');
        } else {
          UI.showToast(`Invoice ${updated.invoice_no} updated successfully!`, 'success');
        }
      } catch (e) {
        console.warn('Save invoice failed:', e);
        UI.showToast('Unable to save invoice.', 'danger');
      }
    }
  },

  async fetchQueueFromBackend() {
    if (!window.Auth || !Auth.isAuthenticated() || Auth.currentUser?.role !== 'admin') return;

    try {
      const res = await Auth.apiFetch('/admin/demands');
      if (res.ok) {
        const demands = await res.json();
        const pendingDemands = demands.filter(d => d.status === 'pending');
        const queueTbody = document.getElementById('adminQueueTableBody');
        const navCount = document.getElementById('navPendingCount');
        if (navCount) navCount.textContent = pendingDemands.length;
        const overviewCount = document.getElementById('statUntreatedDemands');
        const navDemandCount = document.getElementById('navUntreatedDemands');
        if (overviewCount) overviewCount.textContent = pendingDemands.length;
        if (navDemandCount) navDemandCount.textContent = pendingDemands.length;

        if (queueTbody) {
          if (pendingDemands.length === 0) {
            queueTbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color: var(--text-dim);">No pending demands requiring admin review.</td></tr>`;
          } else {
            queueTbody.innerHTML = pendingDemands.map(d => `
              <tr>
                <td>
                  <strong style="color: var(--accent-amber); font-family:var(--font-heading);">DEM-${d.demand_id}</strong>
                  <div style="font-size:0.75rem; color:var(--text-dim);">INV #${d.invoice_id}</div>
                </td>
                <td>${d.user_name || 'User'} (${d.user_email || `usr_${d.user_id}`})</td>
                <td><strong style="color:var(--accent-cyan);">${d.invoice_no || `INV-${d.invoice_id}`}</strong></td>
                <td>${d.supplier || 'STEG'}</td>
                <td><strong style="font-family: var(--font-mono); color:var(--text-main);">${UI.formatTND(d.net_a_payer ?? d.amount_incl_tax ?? 0)}</strong></td>
                <td><span class="badge badge-pending"><i class="fa-solid fa-hourglass"></i> Pending Review</span></td>
                <td style="text-align: right;">
                  <button class="btn btn-success btn-sm" onclick="Admin.reviewDemand(${d.demand_id}, 'approved')">
                    <i class="fa-solid fa-check"></i> Approve
                  </button>
                  <button class="btn btn-danger btn-sm" onclick="Admin.reviewDemand(${d.demand_id}, 'rejected')">
                    <i class="fa-solid fa-xmark"></i> Reject
                  </button>
                  <button class="btn btn-secondary btn-sm" onclick="Admin.inspectInvoice(${d.invoice_id})">
                    <i class="fa-solid fa-magnifying-glass"></i> Inspect
                  </button>
                </td>
              </tr>
            `).join('');
          }
        }
      }

      const auditRes = await Auth.apiFetch('/admin/audit');
      if (auditRes.ok) {
        const logs = await auditRes.json();
        this.auditLogs = logs.map(l => ({
          audit_log_id: `LOG-${l.audit_id}`,
          demand_id: `DEM-${l.demand_id}`,
          actor_id: `Admin #${l.actor_id}`,
          action: l.action,
          field_changed: l.field_changed || 'status',
          old_value: l.old_value || 'pending',
          new_value: l.new_value,
          timestamp: l.timestamp
        }));
        this.renderAuditLogs();
      }
    } catch (e) {
      console.warn('Admin queue fetch warning:', e);
    }
  },

  async fetchAdminUsers() {
    if (!window.Auth || !Auth.isAuthenticated() || Auth.currentUser?.role !== 'admin') return;
    try {
      const res = await Auth.apiFetch('/admin/users');
      if (!res.ok) return;
      const users = await res.json();
      this.adminUsers = users;
      const untreatedAccounts = users.filter(u => (u.account_status || 'pending') === 'pending').length;
      const overviewCount = document.getElementById('statUntreatedAccounts');
      const navCount = document.getElementById('navUntreatedAccounts');
      if (overviewCount) overviewCount.textContent = untreatedAccounts;
      if (navCount) navCount.textContent = untreatedAccounts;
      const tbody = document.getElementById('adminUsersTableBody');
      if (!tbody) return;
      if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 1.2rem; color: var(--text-dim);">No users found.</td></tr>';
        return;
      }
      tbody.innerHTML = users.map(user => {
        const status = user.account_status || 'pending';
        const statusClass = status === 'active' ? 'validated' : status === 'inactive' ? 'rejected' : 'pending';
        const statusLabel = status === 'active' ? 'active' : status === 'inactive' ? 'banned' : 'pending';

        let actions = '';
        if (status === 'pending') {
          actions += `<button class="btn btn-success btn-sm" onclick="Admin.approveUser(${user.user_id})">Approve</button>`;
          actions += `<button class="btn btn-warning btn-sm" onclick="Admin.rejectUser(${user.user_id})">Reject</button>`;
        } else if (status === 'active') {
          actions += `<button class="btn btn-warning btn-sm" onclick="Admin.rejectUser(${user.user_id})">Ban</button>`;
        } else if (status === 'inactive') {
          actions += `<button class="btn btn-success btn-sm" onclick="Admin.approveUser(${user.user_id})">Unban</button>`;
        }
        actions += `<button class="btn btn-secondary btn-sm" onclick="Admin.editUser(${user.user_id}, '${user.full_name.replace(/'/g, "\\'")}', '${user.email}', '${user.role}', '${status}')">Edit</button>`;
        actions += `<button class="btn btn-danger btn-sm" onclick="Admin.deleteUser(${user.user_id})">Delete</button>`;

        return `
        <tr>
          <td>${user.user_id}</td>
          <td>${user.full_name}</td>
          <td>${user.email}</td>
          <td><span class="badge badge-pending">${user.role}</span></td>
          <td><span class="badge badge-${statusClass}">${statusLabel}</span></td>
          <td>${UI.formatDate(user.created_at)}</td>
          <td style="text-align:right; white-space:nowrap;">${actions}</td>
        </tr>
      `;
      }).join('');
    } catch (e) {
      console.warn('Failed to load users:', e);
    }
  },

  editUser(id, name, email, role, status) {
    document.getElementById('adminUserId').value = id;
    document.getElementById('adminUserName').value = name;
    document.getElementById('adminUserEmail').value = email;
    document.getElementById('adminUserRole').value = role;
    document.getElementById('adminUserStatus').value = status || 'pending';
    document.getElementById('adminUserPassword').value = '';
    document.getElementById('adminUserName').focus();
  },

  async approveUser(userId) {
    const wasBanned = this.adminUsers?.find(u => u.user_id === userId)?.account_status === 'inactive';
    try {
      const res = await Auth.apiFetch(`/admin/users/${userId}`, { method: 'PATCH', body: JSON.stringify({ account_status: 'active' }) });
      if (!res.ok) {
        const err = await res.json();
        UI.showToast(err.detail || 'Failed to approve user', 'danger');
        return;
      }
      UI.showToast(wasBanned ? 'User unbanned and reactivated.' : 'Account approved and activated.', 'success');
      await this.fetchAdminUsers();
    } catch (e) {
      console.warn('Approve user failed:', e);
      UI.showToast('Unable to approve user.', 'danger');
    }
  },

  async rejectUser(userId) {
    const wasActive = this.adminUsers?.find(u => u.user_id === userId)?.account_status === 'active';
    try {
      const res = await Auth.apiFetch(`/admin/users/${userId}`, { method: 'PATCH', body: JSON.stringify({ account_status: 'inactive' }) });
      if (!res.ok) {
        const err = await res.json();
        UI.showToast(err.detail || 'Failed to reject user', 'danger');
        return;
      }
      UI.showToast(wasActive ? 'User banned.' : 'Account creation rejected.', 'warning');
      await this.fetchAdminUsers();
    } catch (e) {
      console.warn('Reject user failed:', e);
      UI.showToast('Unable to reject user.', 'danger');
    }
  },

  async deleteUser(userId) {
    if (!confirm('Delete this user account?')) return;
    try {
      const res = await Auth.apiFetch(`/admin/users/${userId}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json();
        UI.showToast(err.detail || 'Failed to delete user', 'danger');
        return;
      }
      UI.showToast('User deleted.', 'success');
      await this.fetchAdminUsers();
    } catch (e) {
      console.warn('Delete user failed:', e);
      UI.showToast('Unable to delete user.', 'danger');
    }
  },

  async fetchAdminInvoices() {
    if (!window.Auth || !Auth.isAuthenticated()) return;
    const isAdmin = Auth.currentUser?.role === 'admin';
    const endpoint = isAdmin ? '/admin/invoices' : '/invoices/mine';

    try {
      const res = await Auth.apiFetch(endpoint);
      if (!res.ok) return;

      let rawInvoices = [];
      if (isAdmin) {
        rawInvoices = await res.json();
      } else {
        const data = await res.json();
        rawInvoices = data.invoices || [];
      }

      this.adminInvoices = rawInvoices.map(i => ({
        ...i,
        invoice_id: i.invoice_id,
        user_id: i.user_id || Auth.currentUser.id,
        user_name: i.user_name || Auth.currentUser.name,
        user_email: i.user_email || Auth.currentUser.email,
        file_name: i.file_name,
        file_path: i.file_path,
        supplier: i.supplier || 'STEG',
        address: i.address || '',
        invoice_no: i.invoice_no || `INV-${i.invoice_id}`,
        invoice_date: i.invoice_date || null,
        amount_excl_tax: i.amount_excl_tax || 0,
        net_a_payer: i.net_a_payer || 0,
        currency: i.currency || 'TND',
        kwh_consumed: i.kwh_consumed || 0,
        status: i.status || 'uploaded',
        uploaded_at: i.uploaded_at,
        demand_id: i.demand_id,
        demand_status: i.demand_status
      }));

      const tbody = document.getElementById('adminInvoicesTableBody');
      if (!tbody) return;

      if (this.adminInvoices.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 1.2rem; color: var(--text-dim);">No invoices found.</td></tr>';
        return;
      }

      tbody.innerHTML = this.adminInvoices.map(invoice => `
        <tr>
          <td><strong>#${invoice.invoice_id}</strong></td>
          <td>${invoice.user_name || invoice.user_email || ('User #' + invoice.user_id)}</td>
          <td>
            <strong style="color:var(--accent-cyan);">${invoice.invoice_no || '-'}</strong>
            <div style="font-size:0.75rem; color:var(--text-dim); max-width:240px;">${invoice.address || '-'}</div>
          </td>
          <td>${UI.formatDate(invoice.invoice_date)}</td>
          <td>${this.demandStatusBadge(invoice.demand_id, invoice.demand_status)}</td>
          <td><strong style="font-family:var(--font-mono);">${UI.formatTND(invoice.net_a_payer || 0)}</strong></td>
          <td style="text-align:right;">
            <button class="btn btn-secondary btn-sm" onclick="Admin.inspectInvoice(${invoice.invoice_id})">Inspect</button>
            <button class="btn btn-secondary btn-sm" onclick="Admin.viewInvoiceFile(${invoice.invoice_id})">View File</button>
            <button class="btn btn-secondary btn-sm" onclick="Admin.editInvoice(${invoice.invoice_id})">Edit</button>
            <button class="btn btn-danger btn-sm" onclick="Admin.deleteInvoice(${invoice.invoice_id})" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.4);">Delete</button>
            ${isAdmin && invoice.demand_id && invoice.demand_status === 'pending' ? `
              <button class="btn btn-success btn-sm" onclick="Admin.reviewDemand(${invoice.demand_id}, 'approved')" title="Approve Demand">
                <i class="fa-solid fa-check"></i> Approve
              </button>
              <button class="btn btn-danger btn-sm" onclick="Admin.reviewDemand(${invoice.demand_id}, 'rejected')" title="Reject Demand">
                <i class="fa-solid fa-xmark"></i> Reject
              </button>
            ` : ''}
            ${!isAdmin && !invoice.demand_id ? `
              <button class="btn btn-primary btn-sm" onclick="Dashboard.submitDemand('${invoice.invoice_id}')">
                <i class="fa-solid fa-paper-plane"></i> Submit Demand
              </button>
            ` : ''}
          </td>
        </tr>
      `).join('');
    } catch (e) {
      console.warn('Failed to load invoices:', e);
    }
  },

  demandStatusBadge(demandId, demandStatus) {
    if (!demandId) return '<span class="badge badge-uploaded">NOT SUBMITTED</span>';

    const status = demandStatus || 'pending';
    return `<span class="badge badge-${status}">DEM-${demandId} ${this.demandStatusLabel(status)}</span>`;
  },

  demandStatusLabel(status) {
    return {
      pending: 'PENDING',
      validated: 'APPROVED',
      rejected: 'REJECTED'
    }[status] || (status || 'pending').toUpperCase();
  },

  editInvoice(id) {
    const invoice = this.adminInvoices?.find(i => i.invoice_id === id);
    if (!invoice) return;
    const isAdmin = Auth.currentUser?.role === 'admin';

    const toDateInputValue = (rawValue) => {
      if (!rawValue) return '';
      const str = String(rawValue).trim();
      const datePart = str.includes('T') ? str.split('T')[0] : str;
      if (!datePart) return '';
      const date = new Date(`${datePart}T12:00:00`);
      if (Number.isNaN(date.getTime())) return datePart;
      const normalized = new Date(date.getFullYear(), date.getMonth(), 1);
      return normalized.toISOString().split('T')[0];
    };

    document.getElementById('adminInvoiceId').value = invoice.invoice_id;

    // Lock User ID field for regular users — they cannot reassign an invoice
    const userIdInput = document.getElementById('adminInvoiceUserId');
    userIdInput.value = invoice.user_id;
    userIdInput.readOnly = !isAdmin;
    userIdInput.style.opacity = isAdmin ? '' : '0.5';
    userIdInput.style.cursor = isAdmin ? '' : 'not-allowed';

    document.getElementById('adminInvoiceSupplier').value = invoice.supplier || 'STEG';
    document.getElementById('adminInvoiceAddress').value = invoice.address || '';
    document.getElementById('adminInvoiceNo').value = invoice.invoice_no || '';
    document.getElementById('adminInvoiceDate').value = toDateInputValue(invoice.invoice_date) || toDateInputValue(invoice.uploaded_at) || '';
    document.getElementById('adminInvoiceStatus').value = invoice.status === 'validated_by_user' ? 'uploaded' : (invoice.status || 'uploaded');
    document.getElementById('adminInvoiceAmountExclTax').value = invoice.amount_excl_tax != null ? invoice.amount_excl_tax : '';
    document.getElementById('adminInvoiceNetAPayer').value = invoice.net_a_payer != null ? invoice.net_a_payer : '';
    document.getElementById('adminInvoiceCurrency').value = invoice.currency || 'TND';
    document.getElementById('adminInvoiceKwh').value = invoice.kwh_consumed != null ? invoice.kwh_consumed : '';
    document.getElementById('adminInvoicePath').value = invoice.file_path || '';

    document.getElementById('adminConsJour').value = invoice.consumption_jour ?? 0;
    document.getElementById('adminConsPointe').value = invoice.consumption_pointe ?? 0;
    document.getElementById('adminConsSoiree').value = invoice.consumption_soiree ?? 0;
    document.getElementById('adminConsNuit').value = invoice.consumption_nuit ?? 0;
    document.getElementById('adminPuJour').value = invoice.pu_jour ?? 0;
    document.getElementById('adminPuPointe').value = invoice.pu_pointe ?? 0;
    document.getElementById('adminPuSoiree').value = invoice.pu_soiree ?? 0;
    document.getElementById('adminPuNuit').value = invoice.pu_nuit ?? 0;
    document.getElementById('adminMontantJour').value = invoice.montant_jour ?? 0;
    document.getElementById('adminMontantPointe').value = invoice.montant_pointe ?? 0;
    document.getElementById('adminMontantSoiree').value = invoice.montant_soiree ?? 0;
    document.getElementById('adminMontantNuit').value = invoice.montant_nuit ?? 0;
    document.getElementById('adminSousTotal').value = invoice.sous_total ?? 0;
    document.getElementById('adminTotal1').value = invoice.total_1 ?? 0;
    document.getElementById('adminTotal2').value = invoice.total_2 ?? 0;
    document.getElementById('adminTotal3').value = invoice.total_3 ?? 0;

    // Focus the first editable field, not the locked User ID
    document.getElementById('adminInvoiceSupplier').focus();
  },

  normalizeFileUrl(filePath) {
    if (!filePath) return '';
    const clean = String(filePath).replace(/\\/g, '/').replace(/^\/+/, '');
    return clean.startsWith('uploads/') || clean.startsWith('uploads\\') ? `/${clean}` : `/${clean}`;
  },

  async viewInvoiceFile(invoiceId) {
    const invoice = this.adminInvoices?.find(i => i.invoice_id === invoiceId);
    const path = invoice?.file_path || invoice?.file_name;
    if (!path) {
      UI.showToast('No file is linked to this invoice.', 'warning');
      return;
    }
    const url = this.normalizeFileUrl(path);
    try {
      const head = await fetch(url, { method: 'HEAD' });
      if (!head.ok) {
        UI.showToast('Scanned file not found on the server.', 'warning');
        return;
      }
    } catch (e) {
      console.warn('File reachability check failed, opening anyway:', e);
    }
    window.open(url, '_blank');
  },

  inspectInvoice(invoiceId) {
    const invoice = this.adminInvoices?.find(i => i.invoice_id === invoiceId);
    if (!invoice) return;
    const modalBody = document.getElementById('inspectModalBody');
    if (!modalBody) return;

    const rows = [
      ['Invoice ID', invoice.invoice_id],
      ['Submitted By', invoice.user_name || '-'],
      ['User Email', invoice.user_email || '-'],
      ['Supplier', invoice.supplier || '-'],
      ['Address', invoice.address || '-'],
      ['Invoice No', invoice.invoice_no || '-'],
      ['Invoice Date', invoice.invoice_date || '-'],
      ['Amount Excl. Tax (HT)', UI.formatTND(invoice.amount_excl_tax || 0)],
      ['NET A PAYER (TTC)', UI.formatTND(invoice.net_a_payer || 0)],
      ['Currency', invoice.currency || '-'],
      ['File', invoice.file_path ? `<a href="${this.normalizeFileUrl(invoice.file_path)}" target="_blank" rel="noopener">${invoice.file_name || invoice.file_path}</a>` : 'No file attached'],
      ['Uploaded At', UI.formatDate(invoice.uploaded_at)],
      ['Demand Status', invoice.demand_id ? `DEM-${invoice.demand_id} ${this.demandStatusLabel(invoice.demand_status)}` : 'Not submitted'],
    ];

    modalBody.innerHTML = `
      <table class="custom-table" style="width:100%;">
        ${rows.map(([k, v]) => `
          <tr>
            <td style="padding:0.5rem 0; color:var(--text-muted); width:40%;">${k}:</td>
            <td style="padding:0.5rem 0;"><strong style="color:var(--text-main);">${v}</strong></td>
          </tr>`).join('')}
      </table>
      
      <h5 style="margin-top:1.2rem; margin-bottom:0.5rem; color:var(--accent-cyan); font-size:0.85rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.3rem;">
        <i class="fa-solid fa-table-list"></i> Tariff Breakdown (Tableau de Consommation)
      </h5>
      <table class="custom-table" style="width:100%; font-size:0.8rem; border-collapse:collapse;">
        <thead>
          <tr style="color:var(--text-muted); border-bottom:1px solid rgba(255,255,255,0.05);">
            <th style="padding:0.4rem; text-align:left;">Période</th>
            <th style="padding:0.4rem; text-align:center;">Consommation (kWh)</th>
            <th style="padding:0.4rem; text-align:center;">P.U. (millimes)</th>
            <th style="padding:0.4rem; text-align:right;">Montant (TND)</th>
          </tr>
        </thead>
        <tbody>
          <tr style="border-bottom:1px solid rgba(255,255,255,0.03);">
            <td style="padding:0.4rem; color:var(--text-dim); font-weight:600;">Jour</td>
            <td style="padding:0.4rem; text-align:center; color:var(--text-main);">${invoice.consumption_jour ?? 0}</td>
            <td style="padding:0.4rem; text-align:center; color:var(--text-main);">${invoice.pu_jour ?? 0}</td>
            <td style="padding:0.4rem; text-align:right; font-family:var(--font-mono); color:var(--text-main);">${UI.formatTND(invoice.montant_jour || 0)}</td>
          </tr>
          <tr style="border-bottom:1px solid rgba(255,255,255,0.03);">
            <td style="padding:0.4rem; color:var(--text-dim); font-weight:600;">Pointe</td>
            <td style="padding:0.4rem; text-align:center; color:var(--text-main);">${invoice.consumption_pointe ?? 0}</td>
            <td style="padding:0.4rem; text-align:center; color:var(--text-main);">${invoice.pu_pointe ?? 0}</td>
            <td style="padding:0.4rem; text-align:right; font-family:var(--font-mono); color:var(--text-main);">${UI.formatTND(invoice.montant_pointe || 0)}</td>
          </tr>
          <tr style="border-bottom:1px solid rgba(255,255,255,0.03);">
            <td style="padding:0.4rem; color:var(--text-dim); font-weight:600;">Soirée</td>
            <td style="padding:0.4rem; text-align:center; color:var(--text-main);">${invoice.consumption_soiree ?? 0}</td>
            <td style="padding:0.4rem; text-align:center; color:var(--text-main);">${invoice.pu_soiree ?? 0}</td>
            <td style="padding:0.4rem; text-align:right; font-family:var(--font-mono); color:var(--text-main);">${UI.formatTND(invoice.montant_soiree || 0)}</td>
          </tr>
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:0.4rem; color:var(--text-dim); font-weight:600;">Nuit</td>
            <td style="padding:0.4rem; text-align:center; color:var(--text-main);">${invoice.consumption_nuit ?? 0}</td>
            <td style="padding:0.4rem; text-align:center; color:var(--text-main);">${invoice.pu_nuit ?? 0}</td>
            <td style="padding:0.4rem; text-align:right; font-family:var(--font-mono); color:var(--text-main);">${UI.formatTND(invoice.montant_nuit || 0)}</td>
          </tr>
        </tbody>
      </table>
      
      <div style="margin-top:0.8rem; display:grid; grid-template-columns:1fr 1fr; gap:0.4rem; font-size:0.75rem; background:rgba(0,242,254,0.02); padding:0.5rem; border-radius:var(--radius-sm); border:1px solid rgba(0,242,254,0.05);">
        <div>Sous Total: <strong style="font-family:var(--font-mono); color:var(--text-main);">${UI.formatTND(invoice.sous_total || 0)}</strong></div>
        <div>Total 1: <strong style="font-family:var(--font-mono); color:var(--text-main);">${UI.formatTND(invoice.total_1 || 0)}</strong></div>
        <div>Total 2: <strong style="font-family:var(--font-mono); color:var(--text-main);">${UI.formatTND(invoice.total_2 || 0)}</strong></div>
        <div>Total 3 / Taxes: <strong style="font-family:var(--font-mono); color:var(--text-main);">${UI.formatTND(invoice.total_3 || 0)}</strong></div>
      </div>

      <div style="margin-top:1rem; display:flex; gap:0.75rem; flex-wrap:wrap;">
        <button class="btn btn-glow-primary btn-sm" onclick="Admin.viewInvoiceFile(${invoice.invoice_id})">
          <i class="fa-solid fa-file-pdf"></i> View Scanned File
        </button>
        <button class="btn btn-secondary btn-sm" onclick="Admin.editInvoice(${invoice.invoice_id}); UI.closeModal('inspectModal');">
          <i class="fa-solid fa-pen"></i> Edit Record
        </button>
        ${invoice.demand_id ? `<button class="btn btn-success btn-sm" onclick="Admin.reviewDemand(${invoice.demand_id}, 'approved'); UI.closeModal('inspectModal');">
          <i class="fa-solid fa-check"></i> Approve Demand
        </button>` : ''}
      </div>
    `;
    UI.openModal('inspectModal');
  },

  async deleteInvoice(invoiceId) {
    if (!confirm('Delete this invoice record?')) return;
    const isAdmin = Auth.currentUser?.role === 'admin';
    const endpoint = isAdmin ? `/admin/invoices/${invoiceId}` : `/invoices/${invoiceId}`;

    try {
      const res = await Auth.apiFetch(endpoint, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json();
        UI.showToast(err.detail || 'Failed to delete invoice', 'danger');
        return;
      }
      UI.showToast('Invoice deleted.', 'success');
      await this.fetchAdminInvoices();
      if (window.Dashboard) window.Dashboard.fetchDataFromBackend();
      if (window.App) window.App.renderUserDemandsTable();
    } catch (e) {
      console.warn('Delete invoice failed:', e);
      UI.showToast('Unable to delete invoice.', 'danger');
    }
  },

  renderQueue() {
    const queueTbody = document.getElementById('adminQueueTableBody');
    if (!queueTbody) return;

    const pendingFactures = Dashboard.factures.filter(f => f.status === 'pending');

    const navCount = document.getElementById('navPendingCount');
    if (navCount) navCount.textContent = pendingFactures.length;

    if (pendingFactures.length === 0) {
      queueTbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color: var(--text-dim);">No pending demands requiring admin review.</td></tr>`;
      return;
    }

    queueTbody.innerHTML = pendingFactures.map(f => `
      <tr>
        <td>
          <strong style="color: var(--accent-amber); font-family:var(--font-heading);">${f.demand_id || 'DEM-NEW'}</strong>
          <div style="font-size:0.75rem; color:var(--text-dim);">${f.id}</div>
        </td>
        <td>Sami Rejeb (usr_101)</td>
        <td><strong style="color:var(--accent-cyan);">${f.invoice_no}</strong></td>
        <td>${f.supplier}</td>
        <td><strong style="font-family: var(--font-mono); color:var(--text-main);">${UI.formatTND(f.net_a_payer)}</strong></td>
        <td><span class="badge badge-pending"><i class="fa-solid fa-hourglass"></i> Pending Review</span></td>
        <td style="text-align: right;">
          <button class="btn btn-success btn-sm" onclick="Admin.reviewDemand('${f.id}', 'approved')">
            <i class="fa-solid fa-check"></i> Approve
          </button>
          <button class="btn btn-danger btn-sm" onclick="Admin.reviewDemand('${f.id}', 'rejected')">
            <i class="fa-solid fa-xmark"></i> Reject
          </button>
        </td>
      </tr>
    `).join('');
  },

  async reviewDemand(demandId, newStatus) {
    const isNum = typeof demandId === 'number' || (typeof demandId === 'string' && /^\d+$/.test(demandId));
    if (!isNum) {
      UI.showToast('Invalid demand ID', 'danger');
      return;
    }

    try {
      const res = await Auth.apiFetch(`/admin/demands/${demandId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus })
      });
      if (res.ok) {
        UI.showToast(`Demand DEM-${demandId} marked as ${newStatus.toUpperCase()} in StegDB`, newStatus === 'approved' ? 'success' : 'danger');
        await this.fetchQueueFromBackend();
        await this.fetchAdminInvoices();
        if (window.Dashboard) window.Dashboard.fetchDataFromBackend();
      } else {
        const err = await res.json();
        UI.showToast(err.detail || 'Failed to review demand', 'danger');
      }
    } catch (e) {
      console.warn('Backend review failed', e);
      UI.showToast('Backend unreachable — demand not updated', 'danger');
    }
  },

  renderAuditLogs() {
    const tbody = document.getElementById('auditLogsTableBody');
    if (!tbody) return;

    if (this.auditLogs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 2rem; color: var(--text-dim);">No audit logs recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = this.auditLogs.map(log => `
      <tr>
        <td><span style="font-family:var(--font-mono); font-weight:700; color:var(--text-muted);">${log.audit_log_id}</span></td>
        <td><strong style="color:var(--accent-cyan);">${log.demand_id}</strong></td>
        <td>${log.actor_id}</td>
        <td><span class="badge badge-${log.new_value === 'approved' ? 'validated' : 'rejected'}">  ${log.action}</span></td>
        <td><span style="color:var(--text-dim);">${log.old_value}</span> &rarr; <strong style="color:var(--text-main);">${log.new_value}</strong></td>
        <td>${UI.formatDate(log.timestamp)}</td>
      </tr>
    `).join('');
  }
};

window.Admin = Admin;
