// Phantom Power Monitoring Panel for Home Assistant
console.log("[Phantom] Loading panel...");

class HaPanelPhantom extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._narrow = false;
    this._devices = [];
    this._upstreamPower = "";
    this._upstreamEnergy = "";
    this._isLoading = true;
    
    console.log("[Phantom] Panel constructor called");
  }

  set hass(hass) {
    console.log("[Phantom] Received hass object:", hass);
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._loadConfiguration();
    }
  }

  set narrow(narrow) {
    this._narrow = narrow;
  }

  set route(route) {
    // Handle route changes if needed
  }

  set panel(panel) {
    // Handle panel config if needed
  }

  connectedCallback() {
    console.log("[Phantom] Panel connected to DOM");
    this._render();
  }

  disconnectedCallback() {
    console.log("[Phantom] Panel disconnected from DOM");
  }

  async _loadConfiguration() {
    console.log("[Phantom] Loading configuration...");
    try {
      this._isLoading = true;
      this._render();
      
      if (!this._hass) {
        throw new Error("No hass object available");
      }
      
      const response = await this._hass.callWS({
        type: "phantom/get_config",
      });
      
      console.log("[Phantom] Configuration loaded:", response);
      
      this._devices = response.devices || [];
      this._upstreamPower = response.upstream_power_entity || "";
      this._upstreamEnergy = response.upstream_energy_entity || "";
      
      this._isLoading = false;
      this._render();
    } catch (error) {
      console.error("[Phantom] Failed to load configuration:", error);
      this._showError(`Failed to load configuration: ${error.message}`);
    }
  }

  async _saveConfiguration() {
    console.log("[Phantom] Saving configuration...");
    try {
      if (!this._hass) {
        throw new Error("No hass object available");
      }
      
      await this._hass.callWS({
        type: "phantom/save_config",
        devices: this._devices,
        upstream_power_entity: this._upstreamPower || null,
        upstream_energy_entity: this._upstreamEnergy || null,
      });
      
      this._showToast("Configuration saved successfully!", "success");
    } catch (error) {
      console.error("[Phantom] Failed to save configuration:", error);
      this._showToast(`Failed to save: ${error.message}`, "error");
    }
  }

  _showError(message) {
    this.innerHTML = `
      <style>
        .error-container {
          padding: 20px;
          color: var(--error-color);
          text-align: center;
          font-family: var(--primary-font-family);
        }
        .error-container h2 {
          color: var(--primary-text-color);
        }
        .error-container button {
          margin-top: 12px;
          padding: 8px 16px;
          background: var(--primary-color);
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
        }
      </style>
      <div class="error-container">
        <h2>⚡ Phantom Power Monitoring</h2>
        <p><strong>Error:</strong> ${message}</p>
        <button onclick="location.reload()">Reload</button>
      </div>
    `;
  }

  _showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.textContent = message;
    toast.style.cssText = `
      position: fixed; top: 20px; right: 20px; padding: 12px 24px;
      border-radius: 4px; color: white; font-weight: 500; z-index: 1000;
      background: ${type === "success" ? "#4caf50" : type === "error" ? "#f44336" : "#2196f3"};
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  _addDevice() {
    this._devices.push({ name: "", power_entity: "", energy_entity: "" });
    this._render();
  }

  _removeDevice(index) {
    this._devices.splice(index, 1);
    this._render();
  }

  _updateDevice(index, field, value) {
    this._devices[index][field] = value;
  }

  _updateUpstream(field, value) {
    if (field === "power") this._upstreamPower = value;
    else if (field === "energy") this._upstreamEnergy = value;
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

  _getUsedEntities(type) {
    return new Set(this._devices
      .map(device => device[`${type}_entity`])
      .filter(entity => entity)
    );
  }

  _render() {
    if (!this._hass) {
      this.innerHTML = '<div style="padding: 20px; text-align: center;">Waiting for connection...</div>';
      return;
    }

    if (this._isLoading) {
      this.innerHTML = '<div style="padding: 20px; text-align: center;">Loading...</div>';
      return;
    }

    const powerEntities = this._getPowerEntities();
    const energyEntities = this._getEnergyEntities();
    const usedPowerEntities = this._getUsedEntities("power");
    const usedEnergyEntities = this._getUsedEntities("energy");

    console.log("[Phantom] Rendering with:", {
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
          font-family: var(--primary-font-family); 
        }
        .section { 
          background: var(--card-background-color); 
          border-radius: 8px; 
          padding: 24px; 
          margin-bottom: 24px; 
          box-shadow: var(--ha-card-box-shadow); 
        }
        .section h2 { 
          margin-top: 0; 
          color: var(--primary-text-color); 
        }
        .device-card { 
          border: 1px solid var(--divider-color); 
          border-radius: 8px; 
          padding: 16px; 
          margin-bottom: 16px; 
          background: var(--secondary-background-color); 
        }
        .device-header { 
          display: flex; 
          justify-content: space-between; 
          align-items: center; 
          margin-bottom: 12px; 
        }
        .device-row { 
          display: flex; 
          gap: 16px; 
          margin-bottom: 8px; 
          align-items: center; 
        }
        .device-row label { 
          min-width: 120px; 
          color: var(--secondary-text-color); 
        }
        .device-row input, .device-row select { 
          flex: 1; 
          padding: 8px; 
          border: 1px solid var(--divider-color); 
          border-radius: 4px; 
          background: var(--card-background-color); 
          color: var(--primary-text-color); 
        }
        .add-device { 
          border: 2px dashed var(--divider-color); 
          border-radius: 8px; 
          padding: 24px; 
          text-align: center; 
          cursor: pointer; 
        }
        .add-device:hover { 
          border-color: var(--primary-color); 
        }
        .btn { 
          padding: 12px 24px; 
          border: none; 
          border-radius: 4px; 
          cursor: pointer; 
          font-weight: 500; 
        }
        .btn-primary { 
          background: var(--primary-color); 
          color: white; 
        }
        .btn-secondary { 
          background: var(--secondary-background-color); 
          color: var(--primary-text-color); 
        }
        .actions { 
          display: flex; 
          gap: 12px; 
          justify-content: flex-end; 
          margin-top: 24px; 
        }
        .delete-btn { 
          background: var(--error-color); 
          color: white; 
          border: none; 
          border-radius: 4px; 
          padding: 8px 12px; 
          cursor: pointer; 
        }
      </style>

      <div class="phantom-panel">
        <h1>⚡ Phantom Power Monitoring</h1>

        <div class="section">
          <h2>Devices (${this._devices.length})</h2>
          
          ${this._devices.length === 0 ? `
            <p style="text-align: center; color: var(--secondary-text-color); padding: 40px;">
              No devices configured. Add your first device to start monitoring.
            </p>
          ` : this._devices.map((device, index) => `
            <div class="device-card">
              <div class="device-header">
                <strong>Device ${index + 1}: ${device.name || 'Unnamed'}</strong>
                <button class="delete-btn" onclick="this.getRootNode().host._removeDevice(${index})">Delete</button>
              </div>
              
              <div class="device-row">
                <label>Name:</label>
                <input value="${device.name || ''}" 
                       onchange="this.getRootNode().host._updateDevice(${index}, 'name', this.value)"
                       placeholder="Enter device name">
              </div>
              
              <div class="device-row">
                <label>Power Sensor:</label>
                <select onchange="this.getRootNode().host._updateDevice(${index}, 'power_entity', this.value)">
                  <option value="">Select power sensor (optional)</option>
                  ${powerEntities.map(entity => 
                    `<option value="${entity.entity_id}" ${device.power_entity === entity.entity_id ? 'selected' : ''}>
                      ${entity.attributes.friendly_name || entity.entity_id}
                    </option>`
                  ).join('')}
                </select>
              </div>
              
              <div class="device-row">
                <label>Energy Sensor:</label>
                <select onchange="this.getRootNode().host._updateDevice(${index}, 'energy_entity', this.value)">
                  <option value="">Select energy sensor (optional)</option>
                  ${energyEntities.map(entity => 
                    `<option value="${entity.entity_id}" ${device.energy_entity === entity.entity_id ? 'selected' : ''}>
                      ${entity.attributes.friendly_name || entity.entity_id}
                    </option>`
                  ).join('')}
                </select>
              </div>
            </div>
          `).join('')}
          
          <div class="add-device" onclick="this.getRootNode().host._addDevice()">
            <div style="font-size: 24px; color: var(--primary-color);">+</div>
            <div>Add Device</div>
          </div>
        </div>

        <div class="section">
          <h2>Upstream Entities</h2>
          <p style="color: var(--secondary-text-color);">
            Configure upstream entities to calculate remainder values (upstream - group total).
          </p>
          
          <div class="device-row">
            <label>Upstream Power:</label>
            <select onchange="this.getRootNode().host._updateUpstream('power', this.value)">
              <option value="">Select upstream power entity (optional)</option>
              ${powerEntities
                .filter(entity => !usedPowerEntities.has(entity.entity_id))
                .map(entity => 
                  `<option value="${entity.entity_id}" ${this._upstreamPower === entity.entity_id ? 'selected' : ''}>
                    ${entity.attributes.friendly_name || entity.entity_id}
                  </option>`
                ).join('')}
            </select>
          </div>
          
          <div class="device-row">
            <label>Upstream Energy:</label>
            <select onchange="this.getRootNode().host._updateUpstream('energy', this.value)">
              <option value="">Select upstream energy entity (optional)</option>
              ${energyEntities
                .filter(entity => !usedEnergyEntities.has(entity.entity_id))
                .map(entity => 
                  `<option value="${entity.entity_id}" ${this._upstreamEnergy === entity.entity_id ? 'selected' : ''}>
                    ${entity.attributes.friendly_name || entity.entity_id}
                  </option>`
                ).join('')}
            </select>
          </div>
        </div>

        <div class="actions">
          <button class="btn btn-secondary" onclick="this.getRootNode().host._loadConfiguration()">Reset</button>
          <button class="btn btn-primary" onclick="this.getRootNode().host._saveConfiguration()">Save Configuration</button>
        </div>
      </div>
    `;
  }
}

// Register the custom element with the proper naming convention
customElements.define("ha-panel-phantom", HaPanelPhantom);

console.log("[Phantom] Panel registration complete");