/* ==========================================================================
   STEG Facture Platform - Application Controller & Router
   ========================================================================== */

const App = {
  activeView: 'dashboard',
  currentExtractedData: null,
  currentPreviewUrl: null,

  init() {
    UI.initTheme();

    this.bindNavigation();
    this.bindDropzone();
    this.bindVerificationForm();

    Dashboard.init();
    Admin.init();
    Auth.init().catch((err) => {
      console.error('Auth initialization failed:', err);
      UI.showToast('Session restore failed. Please sign in again.', 'warning');
      Auth.openAuth();
    });

    if (Auth.isAuthenticated()) {
      this.switchView(Auth.currentUser?.role === 'admin' ? 'admin' : 'dashboard');
    } else {
      this.showView('dashboard');
      Auth.openAuth();
    }
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
    if (!Auth.isAuthenticated()) {
      UI.showToast('Authentication required — sign in to access InvoiceFlow.', 'warning');
      Auth.openAuth();
      return;
    }

    // Admins cannot access the upload workspace (facture upload is for regular users only)
    if (Auth.currentUser?.role === 'admin' && viewId === 'upload') {
      UI.showToast('Upload workspace is not available for admin accounts.', 'warning');
      this.switchView('admin');
      return;
    }

    if (Auth.currentUser?.role !== 'admin' && viewId === 'demands') {
      viewId = 'ocr-admin';
    }

    this.activeView = viewId;
    this.showView(viewId);

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

  showView(viewId) {
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
      'ocr-admin': Auth.currentUser?.role === 'admin' ? 'OCR Management' : 'My Invoices & Demands',
      'user-admin': 'User Administration',
      analytics: 'Power BI Analytics'
    };
    if (pageTitle) pageTitle.textContent = titles[viewId] || 'Overview';
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
    const adminViews = ['admin', 'user-admin'];
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
      if (!Auth.isAuthenticated()) {
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
    if (!Auth.isAuthenticated()) {
      Auth.openAuth();
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
    if (!Auth.isAuthenticated()) {
      UI.showToast('Authentication required — sign in or create an account to process factures.', 'warning');
      Auth.openAuth();
      return;
    }

    // Update document viewer topbar name and icon
    const nameEl = document.getElementById('ocrFileNameDisplay');
    const iconEl = document.getElementById('ocrFileIcon');
    const imgEl = document.getElementById('ocrDocumentImage');
    const pdfEl = document.getElementById('ocrDocumentPdf');
    const fallbackEl = document.getElementById('ocrDocumentFallback');

    if (this.currentPreviewUrl) {
      URL.revokeObjectURL(this.currentPreviewUrl);
    }
    this.currentPreviewUrl = URL.createObjectURL(file);

    if (nameEl) nameEl.textContent = file.name;
    
    const isImage = file.type.startsWith('image/');
    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    if (iconEl) {
      iconEl.className = isImage ? 'fa-solid fa-file-image text-cyan' : 'fa-solid fa-file-pdf text-cyan';
    }

    if (imgEl) {
      imgEl.src = isImage ? this.currentPreviewUrl : '';
      imgEl.style.display = isImage ? 'block' : 'none';
    }
    if (pdfEl) {
      pdfEl.src = isPdf ? this.currentPreviewUrl : '';
      pdfEl.style.display = isPdf ? 'block' : 'none';
    }
    if (fallbackEl) {
      fallbackEl.style.display = !isImage && !isPdf ? 'flex' : 'none';
    }

    if (isImage && imgEl) {
      imgEl.style.display = 'block';
    }

    const dropzone = document.getElementById('factureDropzone');
    const progressCard = document.getElementById('ocrProgressCard');
    const progressBar = document.getElementById('ocrProgressBar');
    const progressStatus = document.getElementById('ocrProgressStatus');
    const splitContainer = document.getElementById('splitVerificationContainer');

    dropzone.style.display = 'none';
    progressCard.style.display = 'block';
    if (progressStatus) progressStatus.textContent = 'Uploading document to server...';
    if (progressBar) progressBar.style.width = '20%';
    if (splitContainer) splitContainer.style.display = 'none';

    // Upload file directly to backend /invoices/upload (OCR runs server-side)
    let serverInvoiceId = null;
    let uploadSuccess = false;
    let ocrData = null;
    let uploadData = null;
    try {
      if (progressStatus) progressStatus.textContent = 'Uploading & running OCR extraction engine...';
      if (progressBar) progressBar.style.width = '40%';

      const formData = new FormData();
      formData.append('file', file);
      const uploadRes = await Auth.apiFetch('/invoices/upload', {
        method: 'POST',
        body: formData
      });

      if (progressBar) progressBar.style.width = '80%';
      if (progressStatus) progressStatus.textContent = 'Processing OCR results...';

      if (uploadRes.ok) {
        uploadData = await uploadRes.json();
        serverInvoiceId = uploadData.invoice?.invoice_id;
        ocrData = uploadData.ocr_data || null;
        uploadSuccess = true;
        await Dashboard.fetchDataFromBackend();
      } else {
        const errorData = await uploadRes.json().catch(() => ({}));
        UI.showToast(errorData.detail || 'Failed to upload document', 'danger');
      }
    } catch (e) {
      console.warn('Backend upload notice:', e);
      UI.showToast('Could not connect to backend server', 'warning');
    }

    if (progressBar) progressBar.style.width = '100%';

    // Build data from OCR results or empty defaults
    const data = {
      id: serverInvoiceId || ("FACT-" + Math.floor(1000 + Math.random() * 9000)),
      supplier: 'STEG',
      address: '',
      invoice_no: '',
      invoice_date: '',
      amount_excl_tax: '',
      tva: '',
      amount_incl_tax: ''
    };

    // Auto-populate from OCR data if available
    if (ocrData) {
      try {
        data.supplier = ocrData.consomateur && ocrData.consomateur !== 'Not Found' ? ocrData.consomateur : 'STEG';
        data.address = ocrData.address && ocrData.address !== 'Not Found' ? ocrData.address : '';
        data.invoice_no = ocrData.facture && ocrData.facture !== 'Not Found' ? ocrData.facture : '';

        data.invoice_date = this.normalizeOcrDate(ocrData.date) || uploadData?.invoice?.invoice_date || '';

        // OCR engines occasionally return a number instead of text.
        const parseOcrNum = (val) => {
          if (val === null || val === undefined || val === '' || val === 'Not Found' || val === '0') return '';
          return parseFloat(String(val).replace(',', '.').replace(/\s/g, '')) || '';
        };
        data.amount_excl_tax = parseOcrNum(ocrData.montant_ht);
        data.tva = parseOcrNum(ocrData.total_3_taxes);
        data.amount_incl_tax = parseOcrNum(ocrData.montant_ttc);
      } catch (e) {
        console.warn('OCR values could not be prepared for review:', e);
        UI.showToast('Document uploaded. Please review and complete the values manually.', 'warning');
      }
    }

    this.currentExtractedData = data;

    setTimeout(() => {
      progressCard.style.display = 'none';
      if (splitContainer) {
        splitContainer.style.display = 'grid';
        this.populateVerificationForm(data);

        // Update OCR confidence badge
        const confidenceEl = document.getElementById('ocrConfidenceBadge');
        if (confidenceEl && ocrData) {
          const statusMap = {
            'validate': { text: '✅ OCR Verified', cls: 'badge-validated' },
            'review': { text: '⚠️ Needs Review', cls: 'badge-pending' },
            'invalid': { text: '❌ Low Confidence', cls: 'badge-rejected' }
          };
          const statusInfo = statusMap[ocrData.ocr_status] || { text: 'Document Uploaded', cls: 'badge-uploaded' };
          confidenceEl.textContent = statusInfo.text;
          confidenceEl.className = `badge ${statusInfo.cls}`;
        } else if (confidenceEl) {
          confidenceEl.textContent = 'Document Uploaded';
          confidenceEl.className = 'badge badge-uploaded';
        }
      }

      if (uploadSuccess && ocrData) {
        UI.showToast('OCR extraction complete — verify the extracted values below.', 'success');
      } else if (uploadSuccess) {
        UI.showToast('Document uploaded. OCR extraction unavailable — please fill in values manually.', 'warning');
      }
    }, 400);
  },

  normalizeOcrDate(rawDate) {
    if (!rawDate || rawDate === 'Not Found') return '';
    const value = String(rawDate).trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;

    let match = value.match(/^(\d{1,2})\/(\d{4})$/);
    if (match) {
      const [, month, year] = match;
      return `${year}-${month.padStart(2, '0')}-01`;
    }

    match = value.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (match) {
      const [, day, month, year] = match;
      return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
    }

    return '';
  },

  resetUploadWorkspace() {
    this.currentExtractedData = null;
    document.getElementById('splitVerificationContainer').style.display = 'none';
    document.getElementById('ocrProgressCard').style.display = 'none';
    document.getElementById('factureDropzone').style.display = 'block';
    const fileInput = document.getElementById('factureFileInput');
    if (fileInput) fileInput.value = '';
  },

  populateVerificationForm(data = {}) {
    document.getElementById('inputSupplier').value = data.supplier || 'STEG';
    document.getElementById('inputAddress').value = data.address || '';
    document.getElementById('inputInvoiceNo').value = data.invoice_no || '';
    document.getElementById('inputInvoiceDate').value = data.invoice_date || '';
    document.getElementById('inputAmountExclTax').value = data.amount_excl_tax || '';
    document.getElementById('inputTva').value = data.tva || '';
    document.getElementById('inputAmountInclTax').value = data.amount_incl_tax || '';

    const confidenceEl = document.getElementById('ocrConfidenceBadge');
    if (confidenceEl) {
      confidenceEl.textContent = 'Document Uploaded';
    }
  },

  bindVerificationForm() {
    const form = document.getElementById('ocrVerificationForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!this.currentExtractedData) return;
      const submitBtn = document.getElementById('btnConfirmOcrSave');
      const originalSubmitHtml = submitBtn?.innerHTML;

      this.currentExtractedData.supplier = document.getElementById('inputSupplier').value;
      this.currentExtractedData.address = document.getElementById('inputAddress').value.trim() || null;
      this.currentExtractedData.invoice_no = document.getElementById('inputInvoiceNo').value;
      
      let dateVal = document.getElementById('inputInvoiceDate').value;
      if (dateVal && dateVal.length === 7) {
        dateVal += '-01';
      }
      this.currentExtractedData.invoice_date = dateVal;
      
      this.currentExtractedData.amount_excl_tax = parseFloat(document.getElementById('inputAmountExclTax').value) || 0;
      this.currentExtractedData.tva = parseFloat(document.getElementById('inputTva').value) || 0;
      this.currentExtractedData.amount_incl_tax = parseFloat(document.getElementById('inputAmountInclTax').value) || 0;

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
      }
      const saved = await Dashboard.saveUserValidation(this.currentExtractedData);
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalSubmitHtml;
      }
      if (!saved) return;

      await Dashboard.fetchDataFromBackend();
      this.resetUploadWorkspace();
    });
  }
};

document.addEventListener('DOMContentLoaded', () => {
  window.App = App;
  App.init();
});
