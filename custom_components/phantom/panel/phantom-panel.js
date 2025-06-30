console.log("Phantom panel script loading...");

class PhantomPanel extends HTMLElement {
  constructor() {
    super();
    this._devices = [];
    this._upstreamPower = "";
    this._upstreamEnergy = "";
    this._isLoading = true;
    this._initialized = false;
    
    console.log("PhantomPanel constructor called");
  }

  set hass(hass) {
    console.log("Setting hass object:", hass);
    this._hass = hass;
    if (!this._initialized && hass) {
      this._initialized = true;
      this._loadConfiguration();
    }
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    console.log("PhantomPanel connected to DOM");
    this.innerHTML = `
      <div style="padding: 20px; text-align: center;">
        <h1>⚡ Phantom Power Monitoring</h1>
        <p>Loading configuration...</p>
      </div>
    `;
    
    // Try to get hass from various sources
    this._tryGetHass();
  }

  _tryGetHass() {
    // Try multiple ways to get the hass object
    let attempts = 0;
    const maxAttempts = 20;
    
    const tryGet = () => {
      attempts++;
      console.log(`Attempt ${attempts} to get hass object`);
      
      // Try to get from window
      if (window.hass) {
        console.log("Found hass in window");
        this.hass = window.hass;
        return;
      }
      
      // Try to get from parent window
      if (window.parent && window.parent.hass) {
        console.log("Found hass in parent window");
        this.hass = window.parent.hass;
        return;
      }
      
      // Try to get from document
      if (document.querySelector("home-assistant")) {
        const ha = document.querySelector("home-assistant");
        if (ha && ha.hass) {
          console.log("Found hass in home-assistant element");
          this.hass = ha.hass;
          return;
        }
      }
      
      if (attempts < maxAttempts) {
        setTimeout(tryGet, 500);
      } else {
        console.error("Could not find hass object after", maxAttempts, "attempts");
        this._showError("Could not connect to Home Assistant. Please refresh the page.");
      }
    };
    
    setTimeout(tryGet, 100);
  }

  async _loadConfiguration() {
    console.log("Loading configuration...");
    try {
      this._isLoading = true;
      this._render();
      
      if (!this._hass || !this._hass.callWS) {
        throw new Error("Home Assistant connection not available");
      }
      
      const response = await this._hass.callWS({
        type: "phantom/get_config",
      });
      
      console.log("Configuration loaded:", response);
      
      if (response) {
        this._devices = response.devices || [];
        this._upstreamPower = response.upstream_power_entity || "";
        this._upstreamEnergy = response.upstream_energy_entity || "";
      }
    } catch (error) {
      console.error("Failed to load Phantom configuration:", error);
      this._showError(`Failed to load configuration: ${error.message}`);
    } finally {
      this._isLoading = false;
      this._render();
    }
  }

  async _saveConfiguration() {
    console.log("Saving configuration...", this._devices);
    try {
      if (!this._hass || !this._hass.callWS) {
        throw new Error("Home Assistant connection not available");
      }
      
      await this._hass.callWS({
        type: "phantom/save_config",
        devices: this._devices,
        upstream_power_entity: this._upstreamPower || null,
        upstream_energy_entity: this._upstreamEnergy || null,
      });
      
      this._showToast("Configuration saved successfully!", "success");
    } catch (error) {
      console.error("Failed to save configuration:", error);
      this._showToast(`Failed to save configuration: ${error.message}`, "error");
    }
  }

  _showError(message) {
    this.innerHTML = `
      <div style="padding: 20px; text-align: center; color: red;">
        <h1>⚡ Phantom Power Monitoring</h1>
        <p><strong>Error:</strong> ${message}</p>
        <button onclick="location.reload()">Reload Page</button>
      </div>
    `;
  }

  _showToast(message, type = "info") {
    console.log("Toast:", type, message);
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
    console.log("Adding device");
    this._devices = [...this._devices, {
      name: "",
      power_entity: "",
      energy_entity: ""
    }];
    this._render();
  }

  _removeDevice(index) {
    console.log("Removing device", index);
    this._devices = this._devices.filter((_, i) => i !== index);
    this._render();
  }

  _updateDevice(index, field, value) {
    console.log("Updating device", index, field, value);
    const devices = [...this._devices];
    devices[index] = { ...devices[index], [field]: value };
    this._devices = devices;
  }

  _updateUpstream(field, value) {
    console.log("Updating upstream", field, value);
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
    console.log("Rendering panel, isLoading:", this._isLoading);
    
    if (this._isLoading) {
      this.innerHTML = `
        <div style="padding: 20px; text-align: center;">
          <h1>⚡ Phantom Power Monitoring</h1>
          <p>Loading configuration...</p>
        </div>
      `;
      return;
    }

    if (!this._hass) {
      this.innerHTML = `
        <div style="padding: 20px; text-align: center;">
          <h1>⚡ Phantom Power Monitoring</h1>
          <p>Connecting to Home Assistant...</p>
        </div>
      `;
      return;
    }

    const powerEntities = this._getPowerEntities();
    const energyEntities = this._getEnergyEntities();
    const usedPowerEntities = this._getUsedEntities("power");
    const usedEnergyEntities = this._getUsedEntities("energy");

    console.log("Rendering with:", {
      devices: this._devices.length,
      powerEntities: powerEntities.length,
      energyEntities: energyEntities.length
    });

    this.innerHTML = `
      <style>
        .phantom-panel {
          padding: 16px;
          max-width: 1200px;
          margin: 0 auto;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        .header {
          margin-bottom: 32px;
          padding-bottom: 16px;
          border-bottom: 1px solid #e0e0e0;
        }

        .header h1 {
          margin: 0;
          font-size: 32px;
          font-weight: 400;
          color: #333;
        }

        .section {
          background: white;
          border-radius: 8px;
          padding: 24px;
          margin-bottom: 24px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          border: 1px solid #e0e0e0;
        }

        .section h2 {
          margin-top: 0;
          margin-bottom: 16px;
          font-size: 20px;
          font-weight: 500;
          color: #333;
        }

        .device-card {
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 16px;
          background: #f9f9f9;
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
          color: #333;
        }

        .delete-button {
          background: #f44336;
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
          color: #666;
        }

        .device-row input, .device-row select {
          flex: 1;
          padding: 8px;
          border: 1px solid #ccc;
          border-radius: 4px;
          background: white;
          color: #333;
          font-size: 14px;
        }

        .add-device {
          border: 2px dashed #ccc;
          border-radius: 8px;
          padding: 24px;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
          background: #f9f9f9;
        }

        .add-device:hover {
          border-color: #2196f3;
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
          background: #2196f3;
          color: white;
        }

        .btn-secondary {
          background: #f5f5f5;
          color: #333;
          border: 1px solid #ccc;
        }

        .empty-state {
          text-align: center;
          padding: 48px 24px;
          color: #666;
        }
      </style>

      <div class="phantom-panel">
        <div class="header">
          <h1>⚡ Phantom Power Monitoring</h1>
        </div>

        <div class="section">
          <h2>Devices (${this._devices.length})</h2>
          
          ${this._devices.length === 0 ? `
            <div class="empty-state">
              <h3>No devices configured</h3>
              <p>Add your first device to start monitoring power and energy consumption.</p>
            </div>
          ` : this._devices.map((device, index) => `
            <div class="device-card">
              <div class="device-header">
                <div class="device-name">Device ${index + 1}: ${device.name || 'Unnamed'}</div>
                <button class="delete-button" onclick="window.phantomPanel._removeDevice(${index})">
                  Delete
                </button>
              </div>
              
              <div class="device-row">
                <label>Device Name:</label>
                <input
                  type="text"
                  value="${device.name || ''}"
                  onchange="window.phantomPanel._updateDevice(${index}, 'name', this.value)"
                  placeholder="Enter device name"
                >
              </div>
              
              <div class="device-row">
                <label>Power Sensor:</label>
                <select onchange="window.phantomPanel._updateDevice(${index}, 'power_entity', this.value)">
                  <option value="">Select power sensor (optional)</option>
                  ${this._getEntityOptionsHTML(powerEntities, device.power_entity)}
                </select>
              </div>
              
              <div class="device-row">
                <label>Energy Sensor:</label>
                <select onchange="window.phantomPanel._updateDevice(${index}, 'energy_entity', this.value)">
                  <option value="">Select energy sensor (optional)</option>
                  ${this._getEntityOptionsHTML(energyEntities, device.energy_entity)}
                </select>
              </div>
            </div>
          `).join('')}
          
          <div class="add-device" onclick="window.phantomPanel._addDevice()">
            <div style="font-size: 24px; color: #2196f3;">+</div>
            <div>Add Device</div>
          </div>
        </div>

        <div class="section">
          <h2>Upstream Entities</h2>
          <p style="color: #666; margin-bottom: 16px;">
            Configure upstream entities to calculate remainder values (upstream - group total).
          </p>
          
          <div class="device-row">
            <label>Upstream Power:</label>
            <select onchange="window.phantomPanel._updateUpstream('power', this.value)">
              <option value="">Select upstream power entity (optional)</option>
              ${this._getEntityOptionsHTML(powerEntities, this._upstreamPower, usedPowerEntities)}
            </select>
          </div>
          
          <div class="device-row">
            <label>Upstream Energy:</label>
            <select onchange="window.phantomPanel._updateUpstream('energy', this.value)">
              <option value="">Select upstream energy entity (optional)</option>
              ${this._getEntityOptionsHTML(energyEntities, this._upstreamEnergy, usedEnergyEntities)}
            </select>
          </div>
        </div>

        <div class="actions">
          <button class="btn btn-secondary" onclick="window.phantomPanel._loadConfiguration()">
            Reset
          </button>
          <button class="btn btn-primary" onclick="window.phantomPanel._saveConfiguration()">
            Save Configuration
          </button>
        </div>
      </div>
    `;
  }
}

customElements.define("phantom-panel", PhantomPanel);

// Store global reference for event handlers
window.phantomPanel = null;

// Wait for DOM and create/find the panel
function initPanel() {
  console.log("Initializing panel...");
  let panel = document.querySelector('phantom-panel');
  
  if (!panel) {
    console.log("Creating phantom-panel element");
    panel = document.createElement('phantom-panel');
    document.body.appendChild(panel);
  }
  
  window.phantomPanel = panel;
  console.log("Panel reference stored globally:", panel);
  
  // Try to get hass if it's available
  if (window.hass) {
    panel.hass = window.hass;
  } else if (window.parent && window.parent.hass) {
    panel.hass = window.parent.hass;
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPanel);
} else {
  initPanel();
}

console.log("Phantom panel script loaded successfully");