// Configure the shared token in the extension's options before use.
const isFirefox = typeof browser !== 'undefined' && /Firefox/i.test(navigator.userAgent);
const api = typeof browser !== 'undefined' ? browser : chrome;
const process = isFirefox ? 'firefox.exe' : 'brave.exe';
async function sync() {
  try {
    const {token} = await api.storage.local.get('token');
    if (!token) return;
    const tabs = await api.tabs.query({active: true, lastFocusedWindow: true});
    const url = tabs[0]?.url;
    if (!/^https?:\/\//.test(url || '')) return;
    await fetch('http://127.0.0.1:8765/active', {
      method: 'POST', headers: {'Content-Type':'application/json','X-squidz-Token':token},
      body: JSON.stringify({process, url})
    });
  } catch (_) { /* Desktop app may be stopped. */ }
}
api.tabs.onActivated.addListener(sync);
api.tabs.onUpdated.addListener(sync);
api.windows.onFocusChanged.addListener(sync);
api.alarms.create('sync', {periodInMinutes: 0.05});
api.alarms.onAlarm.addListener(sync);
sync();
