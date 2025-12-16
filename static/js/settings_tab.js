// Settings tab logic (WiFi manager + service/device actions)
// Uses global safeFetch() from core_index.js and global API_PATHS from api_routes.js

async function apiJSON(url, options = {}) {
  const opts = {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  };
  const res = await window.safeFetch(url, opts);
  // Some endpoints may return empty body on power actions; handle safely.
  const text = await res.text();
  try { return text ? JSON.parse(text) : {}; } catch { return { raw: text }; }
}

function wifiSignalBars(sig) {
  if (sig == null) return '░░░░░';
  if (sig >= 90) return '█████';
  if (sig >= 75) return '████░';
  if (sig >= 50) return '███░░';
  if (sig >= 25) return '██░░░';
  return '█░░░░';
}

function wifiSort(a, b) {
  if (!!a.active !== !!b.active) return a.active ? -1 : 1;
  if (!!a.saved !== !!b.saved) return a.saved ? -1 : 1;
  const as = (a.signal ?? -1);
  const bs = (b.signal ?? -1);
  if (bs !== as) return bs - as;
  return String(a.ssid || '').localeCompare(String(b.ssid || ''));
}

function mergeWifi(scanList, savedList) {
  // savedList is authoritative for "saved" and "active".
  const savedMap = new Map();
  (savedList || []).forEach(p => savedMap.set(p.ssid, p));

  const out = [];
  const seen = new Set();

  // 1) Start with saved profiles; attach scan info if present
  for (const p of (savedList || [])) {
    const match = (scanList || []).find(n => n.ssid === p.ssid);
    out.push({
      ssid: p.ssid,
      saved: true,
      active: !!p.active,
      secured: p.secured ?? true,
      signal: match?.signal ?? null,
      band: match?.band ?? null,
      channel: match?.channel ?? null,
    });
    seen.add(p.ssid);
  }

  // 2) Append available networks not already in saved list
  for (const n of (scanList || [])) {
    if (!n?.ssid || seen.has(n.ssid)) continue;
    out.push({
      ssid: n.ssid,
      saved: !!n.saved,
      active: !!n.in_use,
      secured: !!n.secured,
      signal: n.signal ?? null,
      band: n.band ?? null,
      channel: n.channel ?? null,
    });
  }

  // 3) Ensure active comes first if scan says active but saved list didn't catch it
  // (can happen if profile name differs slightly). Keep as-is for now.

  return out.sort(wifiSort);
}

function initSettingsTab() {
  const simulatorToggle = document.getElementById('simulatorToggle');
  const btnRestartService = document.getElementById('btnRestartService');
  const btnDeviceRestart = document.getElementById('btnDeviceRestart');
  const btnDeviceShutdown = document.getElementById('btnDeviceShutdown');

  // WiFi UI
  const btnScanWifi = document.getElementById('btnScanWifi');
  const chkShowWeak = document.getElementById('wifiShowWeak');
  const wifiList = document.getElementById('wifiNetworks');
  const wifiStatus = document.getElementById('wifiStatus');
  const btnShowMore = document.getElementById('wifiShowMore');
  const connTitle = document.getElementById('wifiConnTitle');
  const connSub = document.getElementById('wifiConnSub');

  const MAX_VISIBLE = 8;
  let wifiAll = [];
  let showAll = false;

  function setWifiStatus(msg) {
    if (wifiStatus) wifiStatus.textContent = msg || '';
  }

  function setConnHeader(activeNet) {
    if (!connTitle || !connSub) return;
    if (!activeNet) {
      connTitle.textContent = 'WiFi';
      connSub.textContent = 'Not connected';
      return;
    }
    const lock = activeNet.secured ? '🔒' : '🔓';
    const bars = wifiSignalBars(activeNet.signal);
    const band = activeNet.band ? ` ${activeNet.band}` : '';
    connTitle.textContent = `Connected: ${activeNet.ssid}`;
    connSub.textContent = `${bars} ${lock}${band}`;
  }

  function renderWifiList() {
    if (!wifiList) return;
    wifiList.innerHTML = '';

    const showWeak = !!chkShowWeak?.checked;
    const filtered = wifiAll.filter(n => {
      const s = n.signal ?? 0;
      return showWeak ? true : s >= 25;
    });

    const visible = showAll ? filtered : filtered.slice(0, MAX_VISIBLE);

    // Update show-more button
    if (btnShowMore) {
      const hiddenCount = Math.max(0, filtered.length - visible.length);
      if (hiddenCount > 0) {
        btnShowMore.classList.remove('d-none');
        btnShowMore.textContent = showAll ? 'Show less' : `Show more (${hiddenCount})`;
      } else {
        btnShowMore.classList.add('d-none');
      }
    }

    // Active header
    const active = filtered.find(n => n.active) || null;
    setConnHeader(active);

    for (const n of visible) {
      wifiList.appendChild(renderWifiRow(n));
    }

    setWifiStatus(filtered.length ? `Showing ${visible.length} of ${filtered.length}` : 'No networks found');
  }

  function makeBtn(text, className, onClick) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = className;
    btn.textContent = text;
    btn.addEventListener('click', onClick);
    return btn;
  }

  async function doRefreshScan() {
    if (!btnScanWifi) return;
    btnScanWifi.disabled = true;
    btnScanWifi.textContent = 'Scanning…';
    setWifiStatus('Scanning…');

    try {
      const [scan, saved] = await Promise.all([
        apiJSON(API_PATHS?.wifi?.scan || '/settings/wifi/scan'),
        apiJSON(API_PATHS?.wifi?.saved || '/settings/wifi/saved'),
      ]);

      const merged = mergeWifi(scan.networks || [], saved.profiles || []);
      wifiAll = merged;
      showAll = false;
      renderWifiList();

    } catch (e) {
      console.error('[wifi] scan failed', e);
      setWifiStatus('Scan failed');
    } finally {
      btnScanWifi.disabled = false;
      btnScanWifi.textContent = 'Scan';
    }
  }

  function renderWifiRow(n) {
    const li = document.createElement('li');
    li.className = 'list-group-item d-flex justify-content-between align-items-center';

    if (n.active) li.classList.add('list-group-item-success');

    const left = document.createElement('div');
    left.className = 'me-2';

    const name = document.createElement('div');
    name.className = 'fw-semibold';
    name.textContent = `${n.saved ? '★ ' : ''}${n.ssid || 'unknown'}`;

    const meta = document.createElement('div');
    meta.className = 'small text-muted';
    const bars = wifiSignalBars(n.signal);
    const lock = n.secured ? '🔒' : '🔓';
    const band = n.band ? ` ${n.band}` : '';
    const activeTag = n.active ? ' • Active' : (n.saved ? ' • Saved' : '');
    meta.textContent = `${bars} ${lock}${band}${activeTag}`;

    left.appendChild(name);
    left.appendChild(meta);

    const right = document.createElement('div');
    right.className = 'd-flex gap-2 align-items-center';

    // Buttons depend on state
    if (n.active) {
      const b = document.createElement('span');
      b.className = 'badge bg-success';
      b.textContent = 'Connected';
      right.appendChild(b);
    } else if (n.saved) {
      const btnSwitch = makeBtn('Switch', 'btn btn-sm btn-outline-primary', () => {
        window.showConfirmModal?.({
          title: 'Switch WiFi',
          message: `Switch to ${n.ssid}?`,
          confirmText: 'Switch',
          confirmClass: 'btn-primary',
          headerClass: 'bg-primary-subtle',
          onConfirm: async () => {
            await runRowAction(n.ssid, async () => {
              const resp = await apiJSON(API_PATHS?.wifi?.switch || '/settings/wifi/switch', {
                method: 'POST',
                body: JSON.stringify({ conn: n.conn || n.ssid }),
              });

              if (resp && resp.ok === false) {
                console.warn('[wifi][switch] backend reported failure:', resp.out || resp.error);
              }
            });
          }
        });
      });

      const btnForget = makeBtn('Forget', 'btn btn-sm btn-outline-danger', () => {
        window.showConfirmModal?.({
          title: 'Forget Network',
          message: `Forget saved network ${n.ssid}?`,
          confirmText: 'Forget',
          confirmClass: 'btn-danger',
          headerClass: 'bg-danger-subtle',
          onConfirm: async () => {
            await runRowAction(n.ssid, async () => {
              console.log('[wifi][forget] sending request:', {
                conn: n.conn || n.ssid,
                endpoint: API_PATHS?.wifi?.forget || '/settings/wifi/forget'
              });

              const resp = await apiJSON(
                API_PATHS?.wifi?.forget || '/settings/wifi/forget',
                {
                  method: 'POST',
                  body: JSON.stringify({ conn: n.conn || n.ssid }),
                }
              );

              if (resp && resp.ok === false) {
                console.warn('[wifi][forget] backend reported failure:', resp.out || resp.error);
              }
            });
          }
        });
      });


      right.appendChild(btnSwitch);
      right.appendChild(btnForget);

    } else {
      const btnConnect = makeBtn('Connect', 'btn btn-sm btn-outline-primary', () => {
        if (n.secured) {
          window.showConfirmModal?.({
            title: 'Connect to WiFi',
            message: `Enter password for ${n.ssid}`,
            confirmText: 'Connect',
            confirmClass: 'btn-primary',
            headerClass: 'bg-primary-subtle',
            inputEnabled: true,
            inputType: 'password',
            inputPlaceholder: 'Password',
            onConfirm: async (pwd) => {
              if (!pwd) return;
              await runRowAction(n.ssid, async () => {
                const resp = await apiJSON(API_PATHS?.wifi?.connect || '/settings/wifi/connect', {
                  method: 'POST',
                  body: JSON.stringify({ ssid: n.ssid, password: pwd }),
                });
                if (resp && resp.ok === false) {
                  console.warn('[wifi][connect] backend reported failure:', resp.out || resp.error);
                }
              });
            }
          });
        } else {
          window.showConfirmModal?.({
            title: 'Connect to WiFi',
            message: `Connect to open network ${n.ssid}?`,
            confirmText: 'Connect',
            confirmClass: 'btn-primary',
            headerClass: 'bg-primary-subtle',
            onConfirm: async () => {
              await runRowAction(n.ssid, async () => {
                await apiJSON(API_PATHS?.wifi?.connect || '/settings/wifi/connect', {
                  method: 'POST',
                  body: JSON.stringify({ ssid: n.ssid }),
                });
              });
            }
          });
        }
      });
      right.appendChild(btnConnect);
    }

    li.appendChild(left);
    li.appendChild(right);

    return li;
  }

  async function runRowAction(ssid, fn) {
    // Light polish: show per-action status and re-scan afterwards.
    setWifiStatus(`Working on ${ssid}…`);
    try {
      await fn();
      setWifiStatus(`Done: ${ssid}`);
    } catch (e) {
      console.error('[wifi] action failed', e);
      setWifiStatus(`Failed: ${ssid}`);
      return;
    }
    // Refresh to update active/saved states
    await doRefreshScan();
  }

  // ----------- Settings status (simulator toggle)
  apiJSON(API_PATHS?.ui?.status || '/settings/status')
    .then(st => {
      if (simulatorToggle) simulatorToggle.checked = !!st.simulator_enabled;
    })
    .catch(() => { /* safeFetch already shows banner */ });

  btnRestartService?.addEventListener('click', () => {
    const useSimulator = simulatorToggle?.checked;
    window.showConfirmModal?.({
      title: 'Restart Service',
      message: useSimulator ? 'Restart gasera.service using Simulator (127.0.0.1)?' : 'Restart gasera.service now?',
      confirmText: 'Restart',
      confirmClass: 'btn-primary',
      headerClass: 'bg-primary-subtle',
      onConfirm: async () => {
        btnRestartService.disabled = true;
        try {
          const resp = await apiJSON(API_PATHS?.ui?.service_restart || '/settings/service/restart', {
            method: 'POST',
            body: JSON.stringify({ useSimulator: !!useSimulator })
          });

          if (resp) {
            if (resp.ok === false) {
              showToast({
                title: 'Action blocked',
                message: resp.toast || resp.error,
                variant: 'warning',
                position: 'corner'
              });

              console.warn('[service][restart] backend reported failure:', resp.out || resp.error);
            } else {
              // Optionally show a toast that restart is in progress
              showToast({
                title: 'Restarting',
                message: 'Service is restarting now.',
                variant: 'success',
                position: 'corner',
                autohide: true,
                delay: 5000
              });
            }
          }

        } finally {
          setTimeout(() => { btnRestartService.disabled = false; }, 2000);
        }
      }
    });
  });

  btnDeviceRestart?.addEventListener('click', () => {
    window.showConfirmModal?.({
      title: 'Restart Device',
      message: 'Restart Controller Device now?',
      confirmText: 'Restart',
      confirmClass: 'btn-warning',
      headerClass: 'bg-warning-subtle',
      onConfirm: async () => {
        const resp = await apiJSON(API_PATHS?.ui?.device_restart || '/settings/device/restart', { method: 'POST', body: '{}' });
        if (resp) {
          if (resp.ok === false) {
            showToast({
              title: 'Action blocked',
              message: resp.toast || resp.error,
              variant: 'warning',
              position: 'corner'
            });

            console.warn('[device][restart] backend reported failure:', resp.out || resp.error);
          } else {
            // Optionally show a toast that restart is in progress
            showToast({
              title: 'Restarting',
              message: 'Device is restarting now.',
              variant: 'success',
              position: 'corner',
              autohide: true,
              delay: 5000
            });
          }
        }
      }
    });
  });

  btnDeviceShutdown?.addEventListener('click', () => {
    window.showConfirmModal?.({
      title: 'Shutdown Device',
      message: 'Shutdown Controller Device now?',
      confirmText: 'Shutdown',
      confirmClass: 'btn-danger',
      headerClass: 'bg-danger-subtle',
      onConfirm: async () => {
        const resp = await apiJSON(API_PATHS?.ui?.device_shutdown || '/settings/device/shutdown', { method: 'POST', body: '{}' });
        if (resp) {
          if (resp.ok === false) {
            showToast({
              title: 'Action blocked',
              message: resp.toast || resp.error,
              variant: 'warning',
              position: 'corner'
            });

            console.warn('[device][shutdown] backend reported failure:', resp.out || resp.error);
          } else {
            // Optionally show a toast that restart is in progress
            showToast({
              title: 'Shutting down',
              message: 'Device is shutting down now.',
              variant: 'success',
              position: 'corner',
              autohide: true,
              delay: 5000
            });
          }
        }
      }
    });
  });

  // ----------- WiFi events
  btnScanWifi?.addEventListener('click', doRefreshScan);
  chkShowWeak?.addEventListener('change', () => { showAll = false; renderWifiList(); });
  btnShowMore?.addEventListener('click', () => { showAll = !showAll; renderWifiList(); });

  // Optional: initial load
  // doRefreshScan();
}

// Auto-init when Settings tab is shown or on load if already active
document.addEventListener('DOMContentLoaded', () => {
  const tabEl = document.querySelector('#settings-tab-btn');
  if (tabEl) {
    tabEl.addEventListener('shown.bs.tab', initSettingsTab, { once: true });
    const active = document.querySelector('#tab-settings.show.active');
    if (active) initSettingsTab();
  } else {
    if (document.getElementById('settings-tab')) initSettingsTab();
  }
});
