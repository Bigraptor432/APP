const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  callClaude:  (params) => ipcRenderer.invoke('call-claude', params),
  callGemma:   (params) => ipcRenderer.invoke('call-gemma', params),
  runTerminal: (cmd)    => ipcRenderer.invoke('run-terminal', cmd),
  mcpGetTools:  (url)    => ipcRenderer.invoke('mcp-get-tools', url),
  validateKey:      (params) => ipcRenderer.invoke('validate-key', params),
  onToolProgress:    (cb)   => ipcRenderer.on('tool-progress', (_, data) => cb(data)),
  offToolProgress:   ()    => ipcRenderer.removeAllListeners('tool-progress'),
  onUpdateAvailable: (cb)  => ipcRenderer.on('update-available', (_, data) => cb(data)),
  checkUpdate:          ()    => ipcRenderer.invoke('check-update'),
  downloadUpdate:       (p)   => ipcRenderer.invoke('download-update', p),
  onDownloadProgress:   (cb)  => ipcRenderer.on('download-progress', (_, d) => cb(d)),
  offDownloadProgress:  ()    => ipcRenderer.removeAllListeners('download-progress'),
  winMinimize: ()       => ipcRenderer.send('win-minimize'),
  winMaximize: ()       => ipcRenderer.send('win-maximize'),
  winClose:    ()       => ipcRenderer.send('win-close'),
  openExternal:(url)    => ipcRenderer.send('open-external', url),
});
