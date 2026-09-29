// Apply before styles load so a saved dark theme never flashes light.
(() => {
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let preference = 'system';
  try { preference = localStorage.getItem('codex-usage-theme') || 'system'; } catch {}
  if (!['system', 'light', 'dark'].includes(preference)) preference = 'system';
  function apply() {
    document.documentElement.dataset.theme = preference === 'system'
      ? (system.matches ? 'dark' : 'light') : preference;
    document.getElementById('theme')?.setAttribute('aria-checked',
      String(document.documentElement.dataset.theme === 'dark'));
    window.dispatchEvent(new Event('themechange'));
  }
  apply();
  system.addEventListener('change', () => { if (preference === 'system') apply(); });
  document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('theme');
    toggle.setAttribute('aria-checked', String(document.documentElement.dataset.theme === 'dark'));
    toggle.addEventListener('click', () => {
      preference = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('codex-usage-theme', preference); } catch {}
      apply();
    });
  });
})();
