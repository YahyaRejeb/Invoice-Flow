/* ==========================================================================
   STEG Facture Platform - Application Controller & Router
   ========================================================================== */

const App = {
  activeView: 'dashboard',
  currentExtractedData: null,
  currentPreviewUrl: null,

  async init() {
    UI.initTheme();

    this.bindNavigation();
    this.bindDropzone();
    this.bindVerificationForm();
    this.bindFocusMode();

    Dashboard.init();
    Admin.init();

    // MUST await Auth.init() — it restores the session asynchronously.
    // Without await, isAuthenticated() is always false at the check below.
    try {
      await Auth.init();
    } catch (err) {
      console.error('Auth initialization failed:', err);
      UI.showToast('Session restore failed. Please sign in again.', 'warning');
      Auth.openAuth();
      return;
    }

    const savedFocusMode = localStorage.getItem('steg_focus_mode') === '1';
    this.toggleFocusMode(false, false);
    if (savedFocusMode) {
      document.body.classList.remove('focus-mode');
    }

    if (Auth.isAuthenticated()) {
      const hashView = window.location.hash ? window.location.hash.replace('#', '') : '';
      const initialView = hashView && document.getElementById(`view-${hashView}`) ? hashView : 'dashboard';
      this.switchView(initialView);
    } else {
      this.showView('dashboard');
      Auth.openAuth();
    }
  },

  bindFocusMode() {
    document.addEventListener('keydown', (event) => {
      const isCtrl = event.ctrlKey || event.metaKey;
      const isMinusKey = event.key === '-' || event.key === '_' || event.code === 'Minus';

      if (isCtrl && isMinusKey) {
        event.preventDefault();
        this.toggleFocusMode();
      }

      if (event.key === 'Escape' && document.body.classList.contains('focus-mode')) {
        event.preventDefault();
        this.toggleFocusMode(false);
      }
    });
  },

  toggleFocusMode(forceState = null, persist = true) {
    const shouldEnable = typeof forceState === 'boolean' ? forceState : !document.body.classList.contains('focus-mode');
    document.body.classList.toggle('focus-mode', shouldEnable);

    if (persist) {
      localStorage.setItem('steg_focus_mode', shouldEnable ? '1' : '0');
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
    if (Auth.currentUser?.role !== 'admin' && viewId === 'ocr-admin') {
      UI.showToast('OCR management is handled from the Overview directory.', 'info');
      viewId = 'dashboard';
    }
    if (Auth.currentUser?.role !== 'admin' && viewId === 'chatbot') {
      UI.showToast('This feature is only accessible for administrator accounts.', 'warning');
      viewId = 'dashboard';
    }

    this.activeView = viewId;
    this.showView(viewId);

    if (viewId === 'dashboard') {
      Dashboard.renderStats();
      Dashboard.renderFacturesTable();
      if (window.Analytics) window.Analytics.loadEmbed();
    } else if (viewId === 'admin') {
      Admin.renderQueue();
      Admin.renderAuditLogs();
    } else if (viewId === 'ocr-admin' && Auth.isAuthenticated()) {
      Admin.fetchAdminInvoices();
    } else if (viewId === 'user-admin' && Auth.currentUser?.role === 'admin') {
      Admin.fetchAdminUsers();
    } else if (viewId === 'chatbot' && Auth.currentUser?.role === 'admin') {
      if (window.Chatbot) window.Chatbot.init();
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
      admin: 'System Audit & Audit Log',
      'ocr-admin': 'OCR Management',
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
          <td><strong style="font-family: var(--font-mono);">${UI.formatTND(d.net_a_payer)}</strong></td>
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
    const adminViews = ['admin', 'user-admin', 'ocr-admin', 'chatbot', 'analytics'];
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
        // Check if multiple files selected
        if (fileInput.files.length > 1) {
          this.processBatchFiles(Array.from(fileInput.files));
        } else {
          this.processFile(fileInput.files[0]);
        }
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
    this.switchView('dashboard');
  },

  async processFile(file) {
    if (!Auth.isAuthenticated()) {
      UI.showToast('Authentication required — sign in or create an account to process factures.', 'warning');
      Auth.openAuth();
      return;
    }
    if (Auth.currentUser?.role === 'admin') {
      UI.showToast('Only user accounts can upload factures.', 'warning');
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
      net_a_payer: ''
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
          return Math.abs(parseFloat(String(val).replace(',', '.').replace(/\s/g, ''))) || '';
        };
        data.amount_excl_tax = parseOcrNum(ocrData.montant_ht);
        data.net_a_payer = parseOcrNum(ocrData.net_a_payer || ocrData.montant_ttc);

        // Tariff detail breakdown (from backend invoice model or ocrData)
        const inv = uploadData?.invoice || {};
        const cd = ocrData.consommation_detaillee || {};
        const pu = ocrData.prix_unitaire || {};
        const md = ocrData.montant_detaille || {};

        data.consumption_jour = inv.consumption_jour ?? cd.jour ?? 0;
        data.consumption_pointe = inv.consumption_pointe ?? cd.pointe ?? 0;
        data.consumption_soiree = inv.consumption_soiree ?? cd.soiree ?? 0;
        data.consumption_nuit = inv.consumption_nuit ?? cd.nuit ?? 0;
        data.kwh_consumed = data.consumption_jour + data.consumption_pointe
          + data.consumption_soiree + data.consumption_nuit;

        data.pu_jour = inv.pu_jour ?? pu.jour ?? 0;
        data.pu_pointe = inv.pu_pointe ?? pu.pointe ?? 0;
        data.pu_soiree = inv.pu_soiree ?? pu.soiree ?? 0;
        data.pu_nuit = inv.pu_nuit ?? pu.nuit ?? 0;

        data.montant_jour = inv.montant_jour ?? md.jour ?? 0;
        data.montant_pointe = inv.montant_pointe ?? md.pointe ?? 0;
        data.montant_soiree = inv.montant_soiree ?? md.soiree ?? 0;
        data.montant_nuit = inv.montant_nuit ?? md.nuit ?? 0;

        data.sous_total = inv.sous_total ?? ocrData.sous_total ?? 0;
        data.total_1 = inv.total_1 ?? ocrData.total_1 ?? 0;
        data.total_2 = inv.total_2 ?? ocrData.total_2 ?? 0;
        data.total_3 = inv.total_3 ?? ocrData.total_3 ?? 0;
        data.net_a_payer = inv.net_a_payer ?? ocrData.net_a_payer ?? 0;
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

        // Update OCR confidence & processing time badges
        const confidenceEl = document.getElementById('ocrConfidenceBadge');
        const timeEl = document.getElementById('ocrTimeBadge');
        const timeVal = document.getElementById('ocrTimeValue');

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

        const timeDisplay = ocrData?.time_taken || (ocrData?.processing_time !== undefined && ocrData?.processing_time !== null ? `${ocrData.processing_time}s` : null);

        if (timeEl && timeDisplay) {
          timeEl.style.display = 'inline-flex';
          if (timeVal) timeVal.textContent = timeDisplay;
        } else if (timeEl) {
          timeEl.style.display = 'none';
        }
      }

      if (uploadSuccess && ocrData) {
        const timeDisplay = ocrData?.time_taken || (ocrData?.processing_time !== undefined && ocrData?.processing_time !== null ? `${ocrData.processing_time}s` : null);
        const timeMsg = timeDisplay ? ` in ${timeDisplay}` : '';
        UI.showToast(`OCR extraction complete${timeMsg} — verify values below.`, 'success');
      } else if (uploadSuccess) {
        UI.showToast('Document uploaded. OCR extraction unavailable — please fill in values manually.', 'warning');
      }
    }, 400);
  },

  // Process multiple files in a batch
  async processBatchFiles(files) {
    if (!Auth.isAuthenticated()) {
      UI.showToast('Authentication required — sign in or create an account to process factures.', 'warning');
      Auth.openAuth();
      return;
    }
    if (!files || files.length === 0) return;

    const dropzone = document.getElementById('factureDropzone');
    const progressCard = document.getElementById('ocrProgressCard');
    const progressBar = document.getElementById('ocrProgressBar');
    const progressStatus = document.getElementById('ocrProgressStatus');
    const splitContainer = document.getElementById('splitVerificationContainer');

    dropzone.style.display = 'none';
    progressCard.style.display = 'block';
    splitContainer.style.display = 'none';

    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    try {
      if (progressStatus) progressStatus.textContent = `Uploading ${files.length} documents & running OCR...`;
      if (progressBar) progressBar.style.width = '30%';

      const uploadRes = await Auth.apiFetch('/invoices/upload-batch', {
        method: 'POST',
        body: formData
      });

      if (progressBar) progressBar.style.width = '80%';
      if (progressStatus) progressStatus.textContent = 'Processing OCR results...';

      let batchResult = null;
      if (uploadRes.ok) {
        batchResult = await uploadRes.json();
        await Dashboard.fetchDataFromBackend();
      } else {
        const errorData = await uploadRes.json().catch(() => ({}));
        UI.showToast(errorData.detail || 'Failed to upload documents', 'danger');
        this.resetUploadWorkspace();
        return;
      }

      if (progressBar) progressBar.style.width = '100%';

      const successfulResults = batchResult?.results?.filter(r => r.success) || [];

      if (batchResult && batchResult.successful > 0) {
        // Hide progress, show batch summary panel
        progressCard.style.display = 'none';
        this.showBatchResultsPanel(batchResult, successfulResults);
      } else {
        UI.showToast('All files failed. Check the format and try again.', 'danger');
        this.resetUploadWorkspace();
      }
    } catch (e) {
      console.error('Batch upload error:', e);
      UI.showToast('Could not connect to backend server', 'warning');
      this.resetUploadWorkspace();
    }
  },

  // Show a panel with all uploaded invoices for individual validation
  showBatchResultsPanel(batchResult, successfulResults) {
    const splitContainer = document.getElementById('splitVerificationContainer');
    const dropzone = document.getElementById('factureDropzone');

    // Hide the original split container so it doesn't show a single invoice
    splitContainer.style.display = 'none';

    // Build a list of validated invoice cards
    const container = document.getElementById('batchResultsPanel');
    if (!container) return;
    container.style.display = 'block';

    const createOcrDisplay = (ocrData) => {
      if (!ocrData) return '<span class="text-muted">No OCR data</span>';
      return `
        <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
          <span style="font-size: 0.85rem; color: var(--text-muted);">Invoice #</span>
          <strong>${ocrData.facture || 'N/A'}</strong>
          <span style="color: var(--text-dim);">|</span>
          <span style="font-size: 0.85rem; color: var(--text-muted);">${ocrData.date || 'N/A'}</span>
        </div>
      `;
    };

    container.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:1.5rem; flex-wrap:wrap; gap:1rem;">
        <div>
          <h3 class="gradient-text" style="margin:0; font-size:1.4rem;">Batch Upload Results</h3>
          <p style="color:var(--text-muted); margin-top:0.5rem;">
            <strong style="color:var(--accent-emerald);">${batchResult.successful}</strong> succeeded,
            <strong style="color:var(--accent-red);">${batchResult.failed}</strong> failed
          </p>
          <div style="display:flex; gap:0.5rem; margin-top:0.5rem;">
            ${batchResult.failed > 0 ? `
              <button class="btn btn-sm btn-secondary" onclick="App.showBatchFailures()">
                <i class="fa-solid fa-triangle-exclamation"></i> View Failed
              </button>
            ` : ''}
          </div>
        </div>
        <button class="btn btn-primary btn-sm" onclick="App.dismissBatchResults()">
          <i class="fa-solid fa-check-double"></i> Done — Back to Dashboard
        </button>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.2rem; margin-top: 1rem;">
        ${successfulResults.map(result => `
          <div class="glass-card" style="padding:1.5rem; border-radius: var(--radius-md); border:1px solid var(--border-color); display:flex; flex-direction:column; gap:0.75rem;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:0.5rem;">
              <div style="min-width:0;">
                <strong style="font-size:0.95rem; display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${result.filename}">
                  <i class="fa-solid fa-file-pdf" style="color:var(--accent-cyan); margin-right:0.4rem;"></i>${result.filename}
                </strong>
                ${result.invoice?.invoice_no ? `<span style="color:var(--accent-cyan); font-family:var(--font-mono); font-size:0.8rem;">${result.invoice.invoice_no}</span>` : ''}
              </div>
              <span class="badge badge-validated"><i class="fa-solid fa-circle-check"></i> Extracted</span>
            </div>

            <div style="font-size:0.85rem; color:var(--text-muted);">
              <div style="display:flex; justify-content:space-between; padding:0.25rem 0;">
                <span>Invoice No:</span><strong>${result.invoice?.invoice_no || '-'}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; padding:0.25rem 0;">
                <span>Date:</span><strong>${result.invoice?.invoice_date || '-'}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; padding:0.25rem 0;">
                <span>Amount:</span><strong class="text-emerald">${UI.formatTND(result.invoice?.net_a_payer || 0)}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; padding:0.25rem 0;">
                <span>Consumed:</span><strong>${result.invoice?.kwh_consumed || 0} kWh</strong>
              </div>
            </div>

            <button class="btn btn-primary btn-sm" onclick="App.openBatchVerification('${result.invoice?.invoice_id}', '${result.filename}')">
              <i class="fa-solid fa-circle-check"></i> Validate Invoice
            </button>
          </div>
        `).join('')}
      </div>
    `;
  },

  openBatchVerification(invoiceId, filename) {
    // Reuse the edit/inspect modal for validation
    if (window.Dashboard) {
      Dashboard.openEditModal(invoiceId);
      UI.showToast(`Validating: ${filename}`, 'info');
    }
  },

  showBatchFailures() {
    // Placeholder — can list failed files and reasons if needed later
  },

  dismissBatchResults() {
    const container = document.getElementById('batchResultsPanel');
    if (container) container.style.display = 'none';
    this.resetUploadWorkspace();
    this.switchView('dashboard');
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
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = (val !== null && val !== undefined) ? val : '';
    };

    setVal('inputSupplier', data.supplier || 'STEG');
    setVal('inputAddress', data.address || '');
    setVal('inputInvoiceNo', data.invoice_no || '');
    setVal('inputInvoiceDate', data.invoice_date || '');
    setVal('inputAmountExclTax', data.amount_excl_tax || '');

    // Tariff breakdown parameters
    setVal('inputConsJour', data.consumption_jour ?? 0);
    setVal('inputConsPointe', data.consumption_pointe ?? 0);
    setVal('inputConsSoiree', data.consumption_soiree ?? 0);
    setVal('inputConsNuit', data.consumption_nuit ?? 0);
    setVal('inputKwhConsumed', data.kwh_consumed ?? 0);

    const updateTotalKwh = () => {
      const total = ['inputConsJour', 'inputConsPointe', 'inputConsSoiree', 'inputConsNuit']
        .reduce((sum, id) => sum + (parseInt(document.getElementById(id)?.value, 10) || 0), 0);
      const totalEl = document.getElementById('inputKwhConsumed');
      if (totalEl) totalEl.value = total;
    };
    ['inputConsJour', 'inputConsPointe', 'inputConsSoiree', 'inputConsNuit']
      .forEach(id => document.getElementById(id)?.addEventListener('input', updateTotalKwh));
    updateTotalKwh();

    setVal('inputPuJour', data.pu_jour ?? 0);
    setVal('inputPuPointe', data.pu_pointe ?? 0);
    setVal('inputPuSoiree', data.pu_soiree ?? 0);
    setVal('inputPuNuit', data.pu_nuit ?? 0);

    setVal('inputMontantJour', data.montant_jour ?? 0);
    setVal('inputMontantPointe', data.montant_pointe ?? 0);
    setVal('inputMontantSoiree', data.montant_soiree ?? 0);
    setVal('inputMontantNuit', data.montant_nuit ?? 0);

    setVal('inputSousTotal', data.sous_total ?? 0);
    setVal('inputTotal1', data.total_1 ?? 0);
    setVal('inputTotal2', data.total_2 ?? 0);
    setVal('inputTotal3', data.total_3 ?? 0);
    setVal('inputNetAPayer', data.net_a_payer ?? 0);

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

      this.currentExtractedData.supplier = document.getElementById('inputSupplier').value;
      this.currentExtractedData.address = document.getElementById('inputAddress').value.trim() || null;
      this.currentExtractedData.invoice_no = document.getElementById('inputInvoiceNo').value;

      let dateVal = document.getElementById('inputInvoiceDate').value;
      if (dateVal && dateVal.length === 7) {
        dateVal += '-01';
      }
      this.currentExtractedData.invoice_date = dateVal;

      this.currentExtractedData.amount_excl_tax = getNum('inputAmountExclTax');

      // Tariff parameters
      this.currentExtractedData.consumption_jour = getInt('inputConsJour');
      this.currentExtractedData.consumption_pointe = getInt('inputConsPointe');
      this.currentExtractedData.consumption_soiree = getInt('inputConsSoiree');
      this.currentExtractedData.consumption_nuit = getInt('inputConsNuit');
      this.currentExtractedData.kwh_consumed = [
        this.currentExtractedData.consumption_jour,
        this.currentExtractedData.consumption_pointe,
        this.currentExtractedData.consumption_soiree,
        this.currentExtractedData.consumption_nuit,
      ].reduce((sum, value) => sum + value, 0);

      this.currentExtractedData.pu_jour = getNum('inputPuJour');
      this.currentExtractedData.pu_pointe = getNum('inputPuPointe');
      this.currentExtractedData.pu_soiree = getNum('inputPuSoiree');
      this.currentExtractedData.pu_nuit = getNum('inputPuNuit');

      this.currentExtractedData.montant_jour = getNum('inputMontantJour');
      this.currentExtractedData.montant_pointe = getNum('inputMontantPointe');
      this.currentExtractedData.montant_soiree = getNum('inputMontantSoiree');
      this.currentExtractedData.montant_nuit = getNum('inputMontantNuit');

      this.currentExtractedData.sous_total = getNum('inputSousTotal');
      this.currentExtractedData.total_1 = getNum('inputTotal1');
      this.currentExtractedData.total_2 = getNum('inputTotal2');
      this.currentExtractedData.total_3 = getNum('inputTotal3');
      this.currentExtractedData.net_a_payer = getNum('inputNetAPayer');

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
