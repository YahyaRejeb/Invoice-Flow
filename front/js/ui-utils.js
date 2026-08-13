/* ==========================================================================
   STEG Facture Platform - UI Utilities Module
   Senior Front-End Architecture
   ========================================================================== */

const UI = {
  // Toast Notification System
  showToast(message, type = 'info', duration = 3500) {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const iconMap = {
      success: '<i class="fa-solid fa-circle-check" style="color: var(--accent-emerald);"></i>',
      danger: '<i class="fa-solid fa-triangle-exclamation" style="color: var(--accent-rose);"></i>',
      warning: '<i class="fa-solid fa-circle-exclamation" style="color: var(--accent-amber);"></i>',
      info: '<i class="fa-solid fa-circle-info" style="color: var(--accent-cyan);"></i>'
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      ${iconMap[type] || iconMap.info}
      <div style="flex: 1; font-weight: 500; font-size: 0.9rem;">${message}</div>
      <button onclick="this.parentElement.remove()" style="background:none; border:none; color:var(--text-muted); cursor:pointer;">
        <i class="fa-solid fa-xmark"></i>
      </button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(50px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },

  // Modal Manager
  openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
  },

  closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
      document.body.style.overflow = '';
    }
  },

  // Format Currency (TND)
  formatTND(amount) {
    return new Intl.NumberFormat('fr-TN', {
      style: 'currency',
      currency: 'TND',
      minimumFractionDigits: 3
    }).format(amount).replace('TND', 'DT');
  },

  // Format Date
  formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    }).format(date);
  },

  // Theme Switcher (Dark / Light)
  toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('steg_theme', newTheme);
    this.updateThemeIcon(newTheme);
    UI.showToast(`Switched to ${newTheme === 'dark' ? 'Dark' : 'Light'} Mode`, 'info');
  },

  updateThemeIcon(theme) {
    const icon = document.getElementById('themeToggleIcon');
    const btn = document.getElementById('themeToggleBtn');
    if (icon) {
      if (theme === 'dark') {
        icon.className = 'fa-solid fa-sun';
        if (btn) btn.setAttribute('title', 'Switch to Light Mode');
      } else {
        icon.className = 'fa-solid fa-moon';
        if (btn) btn.setAttribute('title', 'Switch to Dark Mode');
      }
    }
  },

  initTheme() {
    const savedTheme = localStorage.getItem('steg_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    this.updateThemeIcon(savedTheme);
  }
};

window.UI = UI;

