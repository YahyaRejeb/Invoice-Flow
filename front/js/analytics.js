/* ==========================================================================
   STEG InvoiceFlow - Power BI Analytics (Publish to Web)
   --------------------------------------------------------------------------
   This module loads the Power BI "Publish to Web" public embed URL from the
   backend and injects it into the iframe so the user sees the full Power BI
   report with native filters, slicers, and drill-throughs.

   HOW IT WORKS:
     1. User clicks "Analytics" nav tab.
     2. App.switchView("analytics") calls Analytics.loadEmbed().
     3. We call GET /analytics/embed-url on the FastAPI backend.
     4. The backend reads POWERBI_EMBED_URL from the .env file and returns it.
     5. We set that URL as the iframe src — Power BI loads with all its filters.

   TO CONFIGURE:
     Add this line to back/.env (or back/config.py):
       POWERBI_EMBED_URL=https://app.powerbi.com/reportEmbed?reportId=...
     Get the URL from: Power BI Service → File → Embed report → Publish to web
   ========================================================================== */

const Analytics = (() => {
  let _loaded = false;  // avoid redundant reloads in same session

  /* -------------------------------------------------------------------------
     Public: called by App.switchView('analytics')
     ---------------------------------------------------------------------- */
  async function loadEmbed() {
    if (!Auth.isAuthenticated()) return;

    // Already loaded in this session — no need to reload
    if (_loaded) return;

    _setState('loading');

    try {
      const res = await Auth.apiFetch('/analytics/embed-url');
      if (!res.ok) {
        _setState('setup');
        return;
      }
      const data = await res.json();

      if (!data.configured || !data.embed_url) {
        _setState('setup');
        return;
      }

      _injectIframe(data.embed_url);

    } catch (e) {
      console.error('[Analytics] Failed to load embed URL:', e);
      _setState('setup');
    }
  }

  /* -------------------------------------------------------------------------
     Inject the URL into the iframe
     ---------------------------------------------------------------------- */
  function _injectIframe(url) {
    const frame = document.getElementById('powerBiFrame');
    if (!frame) return;

    if (frame.src !== url) {
      frame.src = url;
    }
    _setState('ready');
    _loaded = true;
  }

  /* -------------------------------------------------------------------------
     Public: Refresh button — reloads the iframe
     ---------------------------------------------------------------------- */
  function reload() {
    _loaded = false;
    const frame = document.getElementById('powerBiFrame');
    if (frame && frame.src) {
      _setState('loading');
      frame.src = frame.src; // triggers reload
      frame.onload = () => {
        _setState('ready');
        _loaded = true;
      };
    } else {
      loadEmbed();
    }
  }

  /* -------------------------------------------------------------------------
     Public: Fullscreen button
     ---------------------------------------------------------------------- */
  function toggleFullscreen() {
    const container = document.getElementById('pbiContainer');
    if (!container) return;

    if (!document.fullscreenElement) {
      container.requestFullscreen?.().catch(err => {
        console.warn('[Analytics] Fullscreen request failed:', err);
      });
      const btn = document.getElementById('pbiFullscreenBtn');
      if (btn) btn.innerHTML = '<i class="fa-solid fa-compress"></i> Exit Fullscreen';
    } else {
      document.exitFullscreen?.();
      const btn = document.getElementById('pbiFullscreenBtn');
      if (btn) btn.innerHTML = '<i class="fa-solid fa-expand"></i> Fullscreen';
    }
  }

  /* -------------------------------------------------------------------------
     UI state machine: 'loading' | 'ready' | 'setup'
     ---------------------------------------------------------------------- */
  function _setState(state) {
    const loading   = document.getElementById('pbiLoading');
    const setupCard = document.getElementById('pbiSetupCard');
    const frame     = document.getElementById('powerBiFrame');

    if (loading)   loading.style.display   = state === 'loading' ? 'flex'  : 'none';
    if (setupCard) setupCard.style.display = state === 'setup'   ? 'flex'  : 'none';
    if (frame)     frame.style.display     = state === 'ready'   ? 'block' : 'none';
  }

  // Sync fullscreen button text when user presses Escape
  document.addEventListener('fullscreenchange', () => {
    const btn = document.getElementById('pbiFullscreenBtn');
    if (!btn) return;
    if (!document.fullscreenElement) {
      btn.innerHTML = '<i class="fa-solid fa-expand"></i> Fullscreen';
    }
  });

  /* -------------------------------------------------------------------------
     Public API
     ---------------------------------------------------------------------- */
  return { loadEmbed, reload, toggleFullscreen };
})();
