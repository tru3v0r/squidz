const api = typeof browser !== 'undefined' ? browser : chrome;
api.storage.local.get('token').then(({token}) => document.getElementById('token').value = token || '');
document.getElementById('save').onclick = async () => {
  await api.storage.local.set({token: document.getElementById('token').value.trim()});
  document.getElementById('status').textContent = 'Jeton enregistré.';
};
