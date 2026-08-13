/* ==========================================================================
   STEG Facture Platform - Auth & Role Manager
   --------------------------------------------------------------------------
   Connected to FastAPI backend & SQL Server (SSMS) database.
   JWT Tokens are stored in localStorage and passed via Authorization headers.
   ========================================================================== */

const Auth = {
  TOKEN_KEY: 'steg_token',
  USER_KEY: 'steg_user',

  currentUser: null, // null => guest (no session)

  async init() {
    this.bindForms();
    this.bindProfileForm();
    await this.restoreSession();
    this.updateRoleUI();

    if (window.App) {
      window.App.onAuthStateChanged();
    } else if (this.isGuest()) {
      this.openAuth();
    }
  },

  /* ------------------------------------------------------------------------
     Token & Header Helpers
     ------------------------------------------------------------------------ */
  getToken() {
    return localStorage.getItem(this.TOKEN_KEY);
  },

  getAuthHeaders() {
    const token = this.getToken();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  },

  async apiFetch(url, options = {}) {
    const headers = {
      ...this.getAuthHeaders(),
      ...(options.headers || {})
    };
    if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }
    return fetch(url, { ...options, headers });
  },

  async restoreSession() {
    const token = this.getToken();
    if (!token) {
      this.currentUser = null;
      return;
    }

    try {
      const response = await this.apiFetch('/auth/me');
      if (response.ok) {
        const user = await response.json();
        this.currentUser = {
          id: user.user_id,
          name: user.full_name,
          email: user.email,
          role: user.role,
          accountStatus: user.account_status || 'pending',
          createdAt: user.created_at || null
        };
        localStorage.setItem(this.USER_KEY, JSON.stringify(this.currentUser));
      } else {
        this.clearSession();
      }
    } catch (e) {
      console.warn('Backend reachability check failed, trying cached session', e);
      const cached = localStorage.getItem(this.USER_KEY);
      if (cached) {
        try { this.currentUser = JSON.parse(cached); } catch (err) {}
      }
    }
  },

  clearSession() {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
    this.currentUser = null;
  },

  /* ------------------------------------------------------------------------
     State Helpers
     ------------------------------------------------------------------------ */
  isGuest() {
    return !this.currentUser;
  },

  isAuthenticated() {
    return !!this.currentUser;
  },

  /* ------------------------------------------------------------------------
     Auth Modal Controls
     ------------------------------------------------------------------------ */
  openAuth() {
    const modal = document.getElementById('authModal');
    if (modal) {
      modal.classList.add('active');
      document.body.style.overflow = 'hidden';
      this.clearAuthError();
    }
  },

  closeAuth() {
    const modal = document.getElementById('authModal');
    if (modal) {
      modal.classList.remove('active');
      document.body.style.overflow = '';
      this.clearAuthError();
    }
  },

  clearAuthError() {
    const errorBox = document.getElementById('authErrorBox');
    if (errorBox) {
      errorBox.textContent = '';
      errorBox.style.display = 'none';
    }
  },

  showAuthError(message) {
    const errorBox = document.getElementById('authErrorBox');
    if (errorBox) {
      errorBox.textContent = message;
      errorBox.style.display = 'block';
    }
    UI.showToast(message, 'danger');
  },

  switchAuthTab(tab) {
    const isLogin = tab === 'login';
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    if (loginForm) loginForm.style.display = isLogin ? 'block' : 'none';
    if (registerForm) registerForm.style.display = isLogin ? 'none' : 'block';
    document.querySelectorAll('.auth-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.authTab === tab);
    });
  },

  bindForms() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const modal = document.getElementById('authModal');

    if (loginForm) {
      loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const email = document.getElementById('loginEmail').value.trim();
        const password = document.getElementById('loginPassword').value;
        this.login(email, password);
      });
    }

    if (registerForm) {
      registerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const name = document.getElementById('registerName').value.trim();
        const email = document.getElementById('registerEmail').value.trim();
        const password = document.getElementById('registerPassword').value;
        const confirm = document.getElementById('registerConfirm').value;
        this.register(name, email, password, confirm);
      });
    }

    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) {
          e.stopPropagation();
        }
      });
    }
  },

  bindProfileForm() {
    const form = document.getElementById('profileEditForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (this.isGuest()) return;

      const input = document.getElementById('profileFullNameInput');
      const fullName = input?.value.trim();
      if (!fullName) {
        UI.showToast('Please enter a full name.', 'warning');
        return;
      }

      try {
        const response = await this.apiFetch('/auth/me', {
          method: 'PATCH',
          body: JSON.stringify({ full_name: fullName })
        });
        const data = await response.json();
        if (!response.ok) {
          UI.showToast(data.detail || 'Unable to update profile.', 'danger');
          return;
        }

        this.currentUser = {
          ...this.currentUser,
          name: data.full_name,
          email: data.email,
          role: data.role,
          accountStatus: data.account_status || 'pending',
          createdAt: data.created_at || this.currentUser?.createdAt || null
        };
        localStorage.setItem(this.USER_KEY, JSON.stringify(this.currentUser));
        this.populateProfileModal();
        this.updateRoleUI();
        UI.showToast('Profile updated successfully.', 'success');
      } catch (err) {
        console.error('Profile update error:', err);
        UI.showToast('Unable to reach the backend.', 'danger');
      }
    });
  },

  async updateProfile(fullName) {
    if (this.isGuest()) return;
    try {
      const response = await this.apiFetch('/auth/me', {
        method: 'PATCH',
        body: JSON.stringify({ full_name: fullName })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Unable to update profile.');
      }
      this.currentUser = {
        ...this.currentUser,
        name: data.full_name,
        email: data.email,
        role: data.role,
        accountStatus: data.account_status || 'pending',
        createdAt: data.created_at || this.currentUser?.createdAt || null
      };
      localStorage.setItem(this.USER_KEY, JSON.stringify(this.currentUser));
      this.populateProfileModal();
      this.updateRoleUI();
      return true;
    } catch (err) {
      console.error('Profile update error:', err);
      return false;
    }
  },

  /* ------------------------------------------------------------------------
     Authentication Actions (Connected to FastAPI + SSMS SQL Server)
     ------------------------------------------------------------------------ */
  async login(email, password) {
    if (!email || !password) {
      this.showAuthError('Please enter both email and password.');
      return;
    }

    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      const data = await response.json();
      if (!response.ok) {
        const errorMsg = data.detail || 'Invalid email or password.';
        this.showAuthError(errorMsg);
        return;
      }

      const user = data.user;
      this.currentUser = {
        id: user.user_id,
        name: user.full_name,
        email: user.email,
        role: user.role,
        accountStatus: user.account_status || 'pending',
        createdAt: user.created_at || null
      };
      localStorage.setItem(this.TOKEN_KEY, data.access_token);
      localStorage.setItem(this.USER_KEY, JSON.stringify(this.currentUser));

      this.resetRoleSwitcher();
      this.updateRoleUI();
      this.closeAuth();

      UI.showToast(`Welcome back, ${this.currentUser.name.split(' ')[0]}!`, 'success');
      if (window.App) window.App.onAuthStateChanged();
    } catch (err) {
      console.error('Login error:', err);
      this.showAuthError('Unable to connect to backend server. Make sure FastAPI server is running.');
    }
  },

  async register(name, email, password, confirm) {
    if (!name || !email || !password) {
      this.showAuthError('Please fill in all required fields.');
      return;
    }
    if (password.length < 6) {
      this.showAuthError('Password must be at least 6 characters.');
      return;
    }
    if (password !== confirm) {
      this.showAuthError('Passwords do not match.');
      return;
    }

    try {
      const response = await fetch('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: name, email, password })
      });

      const data = await response.json();
      if (!response.ok) {
        const errorMsg = data.detail || 'Registration failed.';
        this.showAuthError(errorMsg);
        return;
      }

      const user = data.user;
      if (!data.access_token) {
        this.clearSession();
        this.resetRoleSwitcher();
        this.updateRoleUI();
        this.closeAuth();
        UI.showToast('Account created successfully. Your account is pending admin approval.', 'info');
        return;
      }

      this.currentUser = {
        id: user.user_id,
        name: user.full_name,
        email: user.email,
        role: user.role,
        accountStatus: user.account_status || 'pending',
        createdAt: user.created_at || null
      };
      localStorage.setItem(this.TOKEN_KEY, data.access_token);
      localStorage.setItem(this.USER_KEY, JSON.stringify(this.currentUser));

      this.resetRoleSwitcher();
      this.updateRoleUI();
      this.closeAuth();

      UI.showToast(`Account created in StegDB! Welcome, ${name.split(' ')[0]}!`, 'success');
      if (window.App) window.App.onAuthStateChanged();
    } catch (err) {
      console.error('Register error:', err);
      this.showAuthError('Unable to connect to backend server.');
    }
  },

  continueAsGuest() {
    this.clearSession();
    this.updateRoleUI();
    this.closeAuth();
    UI.showToast('Continuing as guest.', 'info');
    if (window.App) window.App.onAuthStateChanged();
  },

  logout() {
    this.clearSession();
    this.resetRoleSwitcher();
    this.updateRoleUI();

    UI.showToast('Logged out successfully.', 'info');
    if (window.App) window.App.onAuthStateChanged();
  },

  resetRoleSwitcher() {
    document.querySelectorAll('.role-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.role === (this.currentUser?.role || 'user'));
    });
  },

  openProfile() {
    if (this.isGuest()) return;
    this.populateProfileModal();
    UI.openModal('profileModal');
  },

  closeProfile() {
    UI.closeModal('profileModal');
  },

  populateProfileModal() {
    const initials = (name) => name ? name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() : 'US';

    const profileAvatar = document.getElementById('profileAvatar');
    const profileName = document.getElementById('profileName');
    const profileRole = document.getElementById('profileRole');
    const profileFullName = document.getElementById('profileFullName');
    const profileEmail = document.getElementById('profileEmail');
    const profileCreatedAt = document.getElementById('profileCreatedAt');
    const profileRoleValue = document.getElementById('profileRoleValue');
    const profileFullNameInput = document.getElementById('profileFullNameInput');

    if (this.isGuest()) {
      if (profileAvatar) profileAvatar.textContent = 'GU';
      if (profileName) profileName.textContent = 'Guest User';
      if (profileRole) profileRole.textContent = 'VISITOR';
      if (profileFullName) profileFullName.textContent = '-';
      if (profileEmail) profileEmail.textContent = '-';
      if (profileCreatedAt) profileCreatedAt.textContent = '-';
      if (profileRoleValue) profileRoleValue.textContent = '-';
      if (profileFullNameInput) profileFullNameInput.value = '';
      return;
    }

    if (profileAvatar) profileAvatar.textContent = initials(this.currentUser.name);
    if (profileName) profileName.textContent = this.currentUser.name || 'User';
    if (profileRole) profileRole.textContent = (this.currentUser.role || 'user').toUpperCase();
    if (profileFullName) profileFullName.textContent = this.currentUser.name || '-';
    if (profileEmail) profileEmail.textContent = this.currentUser.email || '-';
    if (profileCreatedAt) profileCreatedAt.textContent = this.currentUser.createdAt ? UI.formatDate(this.currentUser.createdAt) : '-';
    if (profileRoleValue) profileRoleValue.textContent = (this.currentUser.role || 'user').toUpperCase();
    if (profileFullNameInput) profileFullNameInput.value = this.currentUser.name || '';
  },

  /* ------------------------------------------------------------------------
     UI State Sync (Guest vs Authenticated)
     ------------------------------------------------------------------------ */
  updateRoleUI() {
    const initials = (name) => name ? name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() : 'US';

    // Topbar: login button vs session pill
    const btnLogin = document.getElementById('btnAuthLogin');
    if (btnLogin) btnLogin.style.display = this.isGuest() ? 'inline-flex' : 'none';

    const sessionPill = document.getElementById('sessionPill');
    if (sessionPill) {
      sessionPill.style.display = this.isGuest() ? 'none' : 'flex';
      const sessionName = document.getElementById('sessionName');
      const sessionAvatar = document.getElementById('sessionAvatar');
      if (this.currentUser) {
        if (sessionName) sessionName.textContent = this.currentUser.name;
        if (sessionAvatar) sessionAvatar.textContent = initials(this.currentUser.name);
      }
    }

    // Hero greeting on the overview dashboard
    const heroGreeting = document.getElementById('heroUserGreeting');
    if (heroGreeting) {
      heroGreeting.textContent = this.isGuest() ? 'Guest' : (this.currentUser?.name || 'User');
    }

    this.populateProfileModal();

    // Sidebar navigation visibility (guests only keep the upload preview)
    document.querySelectorAll('.nav-link').forEach(link => {
      const view = link.dataset.view;
      let show = false;
      if (this.isGuest()) {
        show = view === 'upload';
      } else {
        if (this.currentUser.role === 'admin') {
          show = view === 'dashboard' || view === 'analytics' || view === 'admin' || view === 'ocr-admin' || view === 'user-admin';
        } else {
          show = view === 'dashboard' || view === 'upload' || view === 'analytics' || view === 'demands' || view === 'ocr-admin';
        }
      }
      link.style.display = show ? 'flex' : 'none';
    });

    // Guest lock banner on the upload dropzone
    const lockBanner = document.getElementById('guestLockBanner');
    if (lockBanner) lockBanner.style.display = this.isGuest() ? 'inline-flex' : 'none';
  }
};

window.Auth = Auth;

