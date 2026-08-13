/* ==========================================================================
   STEG Facture Platform - Application Controller & Router
   ========================================================================== */

const App = {
  activeView: 'dashboard',
  currentExtractedData: null,

  init() {
    UI.initTheme();
    Auth.init();
    Dashboard.init();
    Admin.init();

    this.bindNavigation();
    this.bindDropzone();
    this.bindVerificationForm();

    this.switchView(Auth.isGuest() ? 'upload' : 'dashboard');
  },

  bindNavigation() {
    document.querySelectorAll('.nav-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetView = link.getAttribute('data-view');
        if (targetView) {
          this.switchView(targetView);
        }
      });
    });
  },

  switchView(viewId) {
    // Guests have no access to any feature view except the upload preview
    if (Auth.isGuest() && viewId !== 'upload') {
      UI.showToast('Authentication required — sign in to access this feature.', 'warning');
      Auth.openAuth();
      return;
    }

    // Admins cannot access the upload workspace (facture upload is for regular users only)
    if (Auth.currentUser?.role === 'admin' && viewId === 'upload') {
      UI.showToast('Upload workspace is not available for admin accounts.', 'warning');
      this.switchView('admin');
      return;
    }

    this.activeView = viewId;

    document.querySelectorAll('.nav-link').forEach(link => {
      if (link.getAttribute('data-view') === viewId) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });

    document.querySelectorAll('.view-section').forEach(sec => {
      if (sec.id === `view-${viewId}`) {
        sec.style.display = 'block';
      } else {
        sec.style.display = 'none';
      }
    });

    const pageTitle = document.getElementById('pageTitle');
    const titles = {
      dashboard: 'Overview',
      upload: 'Upload & Verification Workspace',
      demands: 'My Demands',
      admin: 'Admin Review Queue',
      'ocr-admin': 'OCR Management',
      'user-admin': 'User Administration',
      analytics: 'Power BI Analytics'
    };
    if (pageTitle) pageTitle.textContent = titles[viewId] || 'Overview';

    if (viewId === 'dashboard') {
      Dashboard.renderStats();
      Dashboard.renderFacturesTable();
      Dashboard.initCharts();
    } else if (viewId === 'admin') {
      Admin.renderQueue();
      Admin.renderAuditLogs();
    } else if (viewId === 'ocr-admin' && Auth.isAuthenticated()) {
      Admin.fetchAdminInvoices();
    } else if (viewId === 'user-admin' && Auth.currentUser?.role === 'admin') {
      Admin.fetchAdminUsers();
    } else if (viewId === 'demands') {
      (async () => {
        if (window.Dashboard) await window.Dashboard.fetchDataFromBackend();
        await this.renderUserDemandsTable();
      })();
    }
  },

  async renderUserDemandsTable() {
    const tbody = document.getElementById('userDemandsTableBody');
    if (!tbody) return;

    // Show a loading state while fetching
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color: var(--text-dim);">Loading demands…</td></tr>`;

    try {
      // Fetch ONLY from the backend — strictly filtered by the logged-in user's ID
      const res = await Auth.apiFetch('/demands/mine');
      if (!res.ok) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color: var(--accent-red);">Failed to load demands. Please try again.</td></tr>`;
        return;
      }

      const demands = await res.json(); // list[MyDemandOut]

      if (!demands || demands.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color: var(--text-dim);">No submitted demands yet.</td></tr>`;
        return;
      }

      tbody.innerHTML = demands.map(d => `
        <tr>
          <td><strong style="color: var(--accent-cyan); font-family:var(--font-heading);">DEM-${d.demand_id}</strong></td>
          <td>${d.invoice_no ?? '—'}</td>
          <td>${d.supplier ?? 'STEG'}</td>
          <td><strong style="font-family: var(--font-mono);">${UI.formatTND(d.amount_incl_tax)}</strong></td>
          <td><span class="badge badge-${d.status}">${d.status.toUpperCase()}</span></td>
          <td>${UI.formatDate(d.submitted_at)}</td>
          <td style="text-align: right; display: flex; gap: 0.35rem; justify-content: flex-end;">
            <button class="btn btn-secondary btn-sm" onclick="Dashboard.openEditModal('${d.invoice_id}')" title="Modify Facture & Demand">
              <i class="fa-solid fa-pen-to-square"></i> Modify
            </button>
            <button class="btn btn-danger btn-sm" onclick="Dashboard.deleteDemand('${d.demand_id}')" title="Delete Demand" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.4);">
              <i class="fa-solid fa-trash-can"></i>
            </button>
          </td>
        </tr>
      `).join('');
    } catch (e) {
      console.error('Failed to fetch demands:', e);
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color: var(--accent-red);">Network error loading demands.</td></tr>`;
    }
  },

  onRoleChanged(newRole) {
    const adminViews = ['admin', 'ocr-admin', 'user-admin'];
    if (newRole === 'admin' && !adminViews.includes(this.activeView)) {
      this.switchView('admin');
    } else if (newRole === 'user' && adminViews.includes(this.activeView)) {
      this.switchView('dashboard');
    }
  },

  bindDropzone() {
    const dropzone = document.getElementById('factureDropzone');
    const fileInput = document.getElementById('factureFileInput');

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => {
      if (Auth.isGuest()) {
        UI.showToast('Authentication required — sign in or create an account to process factures.', 'warning');
        Auth.openAuth();
        return;
      }
      fileInput.click();
    });

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('drag-over');
    });

    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
      if (e.dataTransfer.files.length > 0) {
        this.processFile(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files.length > 0) {
        this.processFile(fileInput.files[0]);
      }
    });
  },

  onAuthStateChanged() {
    // Guests are confined to the upload preview
    if (Auth.isGuest()) {
      this.switchView('upload');
      return;
    }
    // Authenticated users land on the overview dashboard
    if (window.Dashboard) window.Dashboard.fetchDataFromBackend();
    if (window.Admin && Auth.currentUser?.role === 'admin') {
      window.Admin.fetchQueueFromBackend();
      window.Admin.fetchAdminUsers();
      window.Admin.fetchAdminInvoices();
    }
    this.switchView(Auth.currentUser?.role === 'admin' ? 'admin' : 'dashboard');
  },

  async processFile(file) {
    // Guests can preview the workspace but must sign in before uploading.
    if (Auth.isGuest()) {
      UI.showToast('Authentication required — sign in or create an account to process factures.', 'warning');
      Auth.openAuth();
      return;
    }

    const dropzone = document.getElementById('factureDropzone');
    const progressCard = document.getElementById('ocrProgressCard');
    const progressBar = document.getElementById('ocrProgressBar');
    const progressStatus = document.getElementById('ocrProgressStatus');
    const splitContainer = document.getElementById('splitVerificationContainer');

    dropzone.style.display = 'none';
    progressCard.style.display = 'block';
    if (splitContainer) splitContainer.style.display = 'none';

    // Upload file to backend /invoices/upload to store in SQL Server StegDB
    let serverInvoiceId = null;
    try {
      const formData = new FormData();
      formData.append('file', file);
      const uploadRes = await Auth.apiFetch('/invoices/upload', {
        method: 'POST',
        body: formData
      });
      if (uploadRes.ok) {
        const uploadData = await uploadRes.json();
        serverInvoiceId = uploadData.invoice?.invoice_id;
      }
    } catch (e) {
      console.warn('Backend upload notice:', e);
    }

    await OCRSimulator.runExtraction(
      file,
      (statusText, percent) => {
        if (progressStatus) progressStatus.textContent = statusText;
        if (progressBar) progressBar.style.width = `${percent}%`;
      },
      (data) => {
        if (serverInvoiceId) data.id = serverInvoiceId;
        this.currentExtractedData = data;
        progressCard.style.display = 'none';
        if (splitContainer) {
          splitContainer.style.display = 'grid';
          this.populateVerificationForm(data);
        }
        UI.showToast(`OCR parsed values for ${data.invoice_no}`, 'success');
      }
    );
  },

  populateVerificationForm(data) {
    document.getElementById('inputSupplier').value = data.supplier || 'STEG';
    document.getElementById('inputInvoiceNo').value = data.invoice_no;
    document.getElementById('inputInvoiceDate').value = data.invoice_date;
    document.getElementById('inputAmountExclTax').value = data.amount_excl_tax;
    document.getElementById('inputTva').value = data.tva;
    document.getElementById('inputAmountInclTax').value = data.amount_incl_tax;

    const confidenceEl = document.getElementById('ocrConfidenceBadge');
    if (confidenceEl) {
      confidenceEl.textContent = `${data.confidence}% Accuracy (${data.is_digital ? 'Text Layer' : 'Tesseract Scan'})`;
    }

    document.querySelectorAll('.ocr-input-field').forEach(input => {
      input.addEventListener('focus', () => {
        const fieldKey = input.dataset.field;
        OCRSimulator.highlightBox(fieldKey);
      });
    });
  },

  bindVerificationForm() {
    const form = document.getElementById('ocrVerificationForm');
    if (!form) return;

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      if (!this.currentExtractedData) return;

      this.currentExtractedData.supplier = document.getElementById('inputSupplier').value;
      this.currentExtractedData.invoice_no = document.getElementById('inputInvoiceNo').value;
      this.currentExtractedData.invoice_date = document.getElementById('inputInvoiceDate').value;
      this.currentExtractedData.amount_excl_tax = parseFloat(document.getElementById('inputAmountExclTax').value) || 0;
      this.currentExtractedData.tva = parseFloat(document.getElementById('inputTva').value) || 0;
      this.currentExtractedData.amount_incl_tax = parseFloat(document.getElementById('inputAmountInclTax').value) || 0;

      Dashboard.saveUserValidation(this.currentExtractedData);

      document.getElementById('splitVerificationContainer').style.display = 'none';
      document.getElementById('factureDropzone').style.display = 'block';

      this.switchView('dashboard');
    });
  }
};

document.addEventListener('DOMContentLoaded', () => {
  window.App = App;
  App.init();
});

