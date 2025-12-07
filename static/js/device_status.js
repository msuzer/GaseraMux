// ============================================================
// Device Status Helpers – safe reads and last-seen caches
// ============================================================

(function(){
  // Last-seen caches to avoid unnecessary UI updates
  window.lastConnOnline = typeof window.lastConnOnline === "boolean" ? window.lastConnOnline : null;
  window.lastUsbMounted = typeof window.lastUsbMounted === "boolean" ? window.lastUsbMounted : null;
  window.lastBuzzerEnabled = typeof window.lastBuzzerEnabled === "boolean" ? window.lastBuzzerEnabled : null;

  function getDeviceStatus(payload){
    return payload && payload.device_status ? payload.device_status : null;
  }

  function getConnectionOnline(payload){
    const ds = getDeviceStatus(payload);
    return ds && typeof ds.connection?.online === "boolean" ? !!ds.connection.online : null;
  }

  function getUsbMounted(payload){
    const ds = getDeviceStatus(payload);
    return ds && typeof ds.usb?.mounted === "boolean" ? !!ds.usb.mounted : null;
  }

  function getBuzzerEnabled(payload){
    const ds = getDeviceStatus(payload);
    return ds && typeof ds.buzzer?.enabled === "boolean" ? !!ds.buzzer.enabled : null;
  }

  function getBuzzerChanged(payload){
    const ds = getDeviceStatus(payload);
    return !!(ds && ds.buzzer && ds.buzzer._changed);
  }

  // Expose helpers globally
  window.DeviceStatus = {
    getDeviceStatus,
    getConnectionOnline,
    getUsbMounted,
    getBuzzerEnabled,
    getBuzzerChanged,
  };
})();
