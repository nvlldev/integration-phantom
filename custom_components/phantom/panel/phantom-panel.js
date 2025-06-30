class PhantomPanel extends HTMLElement {
  constructor() {
    super();
    this._devices = [];
    this._upstreamPower = "";
    this._upstreamEnergy = "";
    this._isLoading = true;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._loadConfiguration();
    }
  }

  connectedCallback() {
    this.innerHTML = this._getLoadingHTML();
  }

  async _loadConfiguration() {
    try {
      this._isLoading = true;
      this._render();
      
      const response = await this._hass.callWS({
        type: "phantom/get_config",
      });
      
      if (response) {
        this._devices = response.devices || [];
        this._upstreamPower = response.upstream_power_entity || "";
        this._upstreamEnergy = response.upstream_energy_entity || "";
      }
    } catch (error) {
      console.error("Failed to load Phantom configuration:", error);
    } finally {
      this._isLoading = false;
      this._render();
    }
  }

  async _saveConfiguration() {
    try {
      await this._hass.callWS({
        type: "phantom/save_config",
        devices: this._devices,
        upstream_power_entity: this._upstreamPower || null,
        upstream_energy_entity: this._upstreamEnergy || null,
      });
      
      this._showToast("Configuration saved successfully!", "success");
    } catch (error) {
      console.error("Failed to save configuration:", error);
      this._showToast("Failed to save configuration", "error");
    }
  }

  _showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.textContent = message;
    toast.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 24px;
      border-radius: 4px;
      color: white;
      font-weight: 500;
      z-index: 1000;
      background: ${type === "success" ? "#4caf50" : type === "error" ? "#f44336" : "#2196f3"};
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  _getPowerEntities() {
    if (!this._hass) return [];
    return Object.values(this._hass.states).filter(
      state => state.entity_id.startsWith("sensor.") && 
               state.attributes.device_class === "power"
    );
  }

  _getEnergyEntities() {
    if (!this._hass) return [];
    return Object.values(this._hass.states).filter(
      state => state.entity_id.startsWith("sensor.") && 
               state.attributes.device_class === "energy"
    );
  }

  _addDevice() {
    this._devices = [...this._devices, {
      name: "",
      power_entity: "",
      energy_entity: ""
    }];
    this._render();
  }

  _removeDevice(index) {
    this._devices = this._devices.filter((_, i) => i !== index);
    this._render();
  }

  _updateDevice(index, field, value) {
    const devices = [...this._devices];
    devices[index] = { ...devices[index], [field]: value };
    this._devices = devices;
  }

  _updateUpstream(field, value) {
    if (field === "power") {
      this._upstreamPower = value;
    } else if (field === "energy") {
      this._upstreamEnergy = value;
    }
  }

  _getUsedEntities(type) {
    return new Set(this._devices
      .map(device => device[`${type}_entity`])
      .filter(entity => entity)
    );
  }

  _getLoadingHTML() {
    return `
      <div style="display: flex; justify-content: center; align-items: center; padding: 48px;">
        <div>Loading...</div>
      </div>
    `;
  }

  _getEntityOptionsHTML(entities, selected = "", excludeSet = new Set()) {
    return entities
      .filter(entity => !excludeSet.has(entity.entity_id))
      .map(entity => `
        <option value="${entity.entity_id}" ${selected === entity.entity_id ? 'selected' : ''}>
          ${entity.attributes.friendly_name || entity.entity_id}
        </option>
      `).join('');
  }

  _render() {
    if (this._isLoading) {
      this.innerHTML = this._getLoadingHTML();
      return;
    }

    const powerEntities = this._getPowerEntities();
    const energyEntities = this._getEnergyEntities();
    const usedPowerEntities = this._getUsedEntities("power");
    const usedEnergyEntities = this._getUsedEntities("energy");

    this.innerHTML = `
      <style>
        .phantom-panel {
          padding: 16px;
          max-width: 1200px;
          margin: 0 auto;
          font-family: var(--paper-font-body1_-_font-family);
        }

        .header {
          display: flex;
          align-items: center;
          margin-bottom: 32px;
          padding-bottom: 16px;
          border-bottom: 1px solid var(--divider-color);
        }

        .header h1 {
          margin: 0;
          font-size: 32px;
          font-weight: 400;
          color: var(--primary-text-color);
        }

        .section {
          background: var(--card-background-color);
          border-radius: 8px;
          padding: 24px;
          margin-bottom: 24px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
        }

        .section h2 {
          margin-top: 0;
          margin-bottom: 16px;
          font-size: 20px;
          font-weight: 500;
          color: var(--primary-text-color);
        }

        .device-card {
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 16px;
          background: var(--primary-background-color);
        }

        .device-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .device-name {
          font-weight: 500;
          font-size: 16px;
          color: var(--primary-text-color);
        }

        .delete-button {
          background: var(--error-color);
          color: white;
          border: none;
          border-radius: 4px;
          padding: 8px 12px;
          cursor: pointer;
          font-size: 14px;
        }

        .device-row {
          display: flex;
          gap: 16px;
          margin-bottom: 8px;
          align-items: center;
        }

        .device-row label {
          min-width: 120px;
          font-size: 14px;
          color: var(--secondary-text-color);
        }

        .device-row input, .device-row select {
          flex: 1;
          padding: 8px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font-size: 14px;
        }

        .add-device {
          border: 2px dashed var(--divider-color);
          border-radius: 8px;
          padding: 24px;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
          background: var(--primary-background-color);
        }

        .add-device:hover {
          border-color: var(--primary-color);
        }

        .actions {
          display: flex;
          gap: 12px;
          justify-content: flex-end;
          margin-top: 24px;
        }

        .btn {
          padding: 12px 24px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 500;
        }

        .btn-primary {
          background: var(--primary-color);
          color: white;
        }

        .btn-secondary {
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color);
        }

        .empty-state {
          text-align: center;
          padding: 48px 24px;
          color: var(--secondary-text-color);
        }
      </style>

      <div class="phantom-panel">
        <div class="header">
          <h1>⚡ Phantom Power Monitoring</h1>
        </div>

        <div class="section">
          <h2>Devices</h2>
          
          ${this._devices.length === 0 ? `
            <div class="empty-state">
              <h3>No devices configured</h3>
              <p>Add your first device to start monitoring power and energy consumption.</p>
            </div>
          ` : this._devices.map((device, index) => `
            <div class="device-card">
              <div class="device-header">
                <div class="device-name">Device ${index + 1}</div>
                <button class="delete-button" onclick="phantomPanel._removeDevice(${index})">
                  Delete
                </button>
              </div>
              
              <div class="device-row">
                <label>Device Name:</label>
                <input
                  type="text"
                  value="${device.name || ''}"
                  onchange="phantomPanel._updateDevice(${index}, 'name', this.value)"
                  placeholder="Enter device name"
                >
              </div>
              
              <div class="device-row">
                <label>Power Sensor:</label>
                <select onchange="phantomPanel._updateDevice(${index}, 'power_entity', this.value)">
                  <option value="">Select power sensor (optional)</option>
                  ${this._getEntityOptionsHTML(powerEntities, device.power_entity)}
                </select>
              </div>
              
              <div class="device-row">
                <label>Energy Sensor:</label>
                <select onchange="phantomPanel._updateDevice(${index}, 'energy_entity', this.value)">
                  <option value="">Select energy sensor (optional)</option>
                  ${this._getEntityOptionsHTML(energyEntities, device.energy_entity)}
                </select>
              </div>
            </div>
          `).join('')}
          
          <div class="add-device" onclick="phantomPanel._addDevice()">
            <div style="font-size: 24px; color: var(--primary-color);">+</div>
            <div>Add Device</div>
          </div>
        </div>

        <div class="section">
          <h2>Upstream Entities</h2>
          <p style="color: var(--secondary-text-color); margin-bottom: 16px;">
            Configure upstream entities to calculate remainder values (upstream - group total).
          </p>
          
          <div class="device-row">
            <label>Upstream Power:</label>
            <select onchange="phantomPanel._updateUpstream('power', this.value)">
              <option value="">Select upstream power entity (optional)</option>
              ${this._getEntityOptionsHTML(powerEntities, this._upstreamPower, usedPowerEntities)}
            </select>
          </div>
          
          <div class="device-row">
            <label>Upstream Energy:</label>
            <select onchange="phantomPanel._updateUpstream('energy', this.value)">
              <option value="">Select upstream energy entity (optional)</option>
              ${this._getEntityOptionsHTML(energyEntities, this._upstreamEnergy, usedEnergyEntities)}
            </select>
          </div>
        </div>

        <div class="actions">
          <button class="btn btn-secondary" onclick="phantomPanel._loadConfiguration()">
            Reset
          </button>
          <button class="btn btn-primary" onclick="phantomPanel._saveConfiguration()">
            Save Configuration
          </button>
        </div>
      </div>
    `;
  }
}

// Make the panel globally accessible for event handlers
window.phantomPanel = null;

customElements.define("phantom-panel", PhantomPanel);

// Store reference when element is created
document.addEventListener('DOMContentLoaded', () => {
  const panel = document.querySelector('phantom-panel');
  if (panel) {
    window.phantomPanel = panel;
  }
});

// Also handle dynamic creation
const observer = new MutationObserver((mutations) => {
  mutations.forEach((mutation) => {
    mutation.addedNodes.forEach((node) => {
      if (node.tagName === 'PHANTOM-PANEL') {
        window.phantomPanel = node;
      }
    });
  });
});

observer.observe(document.body, { childList: true, subtree: true });