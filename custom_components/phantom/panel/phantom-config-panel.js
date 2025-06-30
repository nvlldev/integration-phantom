// Phantom Power Monitoring Panel
console.log("[Phantom] Loading panel v2.0...");

class PhantomConfigPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this.devices = [];
    this.upstreamPower = "";
    this.upstreamEnergy = "";
    this.isLoading = true;
    
    console.log("[Phantom] Panel constructor");
  }

  set hass(hass) {
    console.log("[Phantom] Hass object received:", hass);
    this._hass = hass;
    if (!this.hasInitialized) {
      this.hasInitialized = true;
      this.initialize();
    }
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    console.log("[Phantom] Narrow:", value);
  }

  set route(value) {
    console.log("[Phantom] Route:", value);
  }

  set panel(value) {
    console.log("[Phantom] Panel:", value);
  }

  async initialize() {
    console.log("[Phantom] Initializing panel...");
    this.innerHTML = '<div style="padding: 20px;">Loading Phantom configuration...</div>';
    
    // Set up event delegation
    this.addEventListener('click', this.handleClick.bind(this));
    this.addEventListener('change', this.handleChange.bind(this));
    
    try {
      await this.loadConfiguration();
    } catch (error) {
      console.error("[Phantom] Error during initialization:", error);
      this.showError(`Initialization error: ${error.message}`);
    }
  }

  handleClick(event) {
    const target = event.target;
    
    if (target.classList.contains('delete-btn')) {
      const index = parseInt(target.dataset.index);
      this.removeDevice(index);
    } else if (target.closest('.add-device')) {
      this.addDevice();
    } else if (target.classList.contains('btn-primary')) {
      this.saveConfiguration();
    } else if (target.classList.contains('btn-secondary')) {
      this.loadConfiguration();
    }
  }

  handleChange(event) {
    const target = event.target;
    
    if (target.classList.contains('device-name')) {
      const index = parseInt(target.dataset.index);
      this.updateDevice(index, 'name', target.value);
    } else if (target.classList.contains('device-power')) {
      const index = parseInt(target.dataset.index);
      this.updateDevice(index, 'power_entity', target.value);
    } else if (target.classList.contains('device-energy')) {
      const index = parseInt(target.dataset.index);
      this.updateDevice(index, 'energy_entity', target.value);
    } else if (target.classList.contains('upstream-power')) {
      this.updateUpstream('power', target.value);
    } else if (target.classList.contains('upstream-energy')) {
      this.updateUpstream('energy', target.value);
    }
  }

  async loadConfiguration() {
    console.log("[Phantom] Loading configuration...");
    try {
      this.isLoading = true;
      this.render();
      
      const response = await this._hass.callWS({
        type: "phantom/get_config",
      });
      
      console.log("[Phantom] Configuration response:", response);
      
      this.devices = response.devices || [];
      this.upstreamPower = response.upstream_power_entity || "";
      this.upstreamEnergy = response.upstream_energy_entity || "";
      
      this.isLoading = false;
      this.render();
    } catch (error) {
      console.error("[Phantom] Failed to load configuration:", error);
      this.showError(`Failed to load configuration: ${error.message}`);
    }
  }

  async saveConfiguration() {
    console.log("[Phantom] Saving configuration...");
    try {
      await this._hass.callWS({
        type: "phantom/save_config",
        devices: this.devices,
        upstream_power_entity: this.upstreamPower || null,
        upstream_energy_entity: this.upstreamEnergy || null,
      });
      
      this.showToast("Configuration saved successfully!", "success");
    } catch (error) {
      console.error("[Phantom] Failed to save configuration:", error);
      this.showToast(`Failed to save: ${error.message}`, "error");
    }
  }

  showError(message) {
    this.innerHTML = `
      <div style="padding: 20px; color: red; text-align: center;">
        <h2>⚡ Phantom Power Monitoring</h2>
        <p><strong>Error:</strong> ${message}</p>
        <button class="reload-btn">Reload</button>
      </div>
    `;
    // Add click handler for reload button
    const reloadBtn = this.querySelector('.reload-btn');
    if (reloadBtn) {
      reloadBtn.addEventListener('click', () => location.reload());
    }
  }

  showToast(message, type = "info") {
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

  addDevice() {
    this.devices.push({ name: "", power_entity: "", energy_entity: "" });
    this.render();
  }

  removeDevice(index) {
    this.devices.splice(index, 1);
    this.render();
  }

  updateDevice(index, field, value) {
    this.devices[index][field] = value;
  }

  updateUpstream(field, value) {
    if (field === "power") this.upstreamPower = value;
    else if (field === "energy") this.upstreamEnergy = value;
  }

  getPowerEntities() {
    if (!this._hass) return [];
    return Object.values(this._hass.states).filter(
      state => state.entity_id.startsWith("sensor.") && 
               state.attributes.device_class === "power"
    );
  }

  getEnergyEntities() {
    if (!this._hass) return [];
    return Object.values(this._hass.states).filter(
      state => state.entity_id.startsWith("sensor.") && 
               state.attributes.device_class === "energy"
    );
  }

  getUsedEntities(type) {
    return new Set(this.devices
      .map(device => device[`${type}_entity`])
      .filter(entity => entity)
    );
  }

  render() {
    if (this.isLoading) {
      this.innerHTML = '<div style="padding: 20px; text-align: center;">Loading...</div>';
      return;
    }

    const powerEntities = this.getPowerEntities();
    const energyEntities = this.getEnergyEntities();
    const usedPowerEntities = this.getUsedEntities("power");
    const usedEnergyEntities = this.getUsedEntities("energy");

    console.log("[Phantom] Rendering with:", {
      devices: this.devices.length,
      powerEntities: powerEntities.length,
      energyEntities: energyEntities.length
    });

    this.innerHTML = `
      <style>
        .phantom-panel { padding: 16px; max-width: 1200px; margin: 0 auto; font-family: var(--primary-font-family); }
        .section { background: var(--card-background-color); border-radius: 8px; padding: 24px; margin-bottom: 24px; box-shadow: var(--ha-card-box-shadow); }
        .section h2 { margin-top: 0; color: var(--primary-text-color); }
        .device-card { border: 1px solid var(--divider-color); border-radius: 8px; padding: 16px; margin-bottom: 16px; background: var(--secondary-background-color); }
        .device-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .device-row { display: flex; gap: 16px; margin-bottom: 8px; align-items: center; }
        .device-row label { min-width: 120px; color: var(--secondary-text-color); }
        .device-row input, .device-row select { flex: 1; padding: 8px; border: 1px solid var(--divider-color); border-radius: 4px; background: var(--card-background-color); color: var(--primary-text-color); }
        .add-device { border: 2px dashed var(--divider-color); border-radius: 8px; padding: 24px; text-align: center; cursor: pointer; }
        .add-device:hover { border-color: var(--primary-color); }
        .btn { padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; }
        .btn-primary { background: var(--primary-color); color: white; }
        .btn-secondary { background: var(--secondary-background-color); color: var(--primary-text-color); }
        .actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; }
        .delete-btn { background: var(--error-color); color: white; border: none; border-radius: 4px; padding: 8px 12px; cursor: pointer; }
      </style>

      <div class="phantom-panel">
        <h1>⚡ Phantom Power Monitoring</h1>
        <div style="background: var(--info-color, #039be5); color: white; padding: 16px; border-radius: 4px; margin-bottom: 24px;">
          <strong>Note:</strong> This integration currently supports monitoring a single group of devices. 
          All configured devices will be combined into one power monitoring group with total, remainder, and utility meter sensors.
        </div>

        <div class="section">
          <h2>Devices (${this.devices.length})</h2>
          
          ${this.devices.length === 0 ? `
            <p style="text-align: center; color: var(--secondary-text-color); padding: 40px;">
              No devices configured. Add your first device to start monitoring.
            </p>
          ` : this.devices.map((device, index) => `
            <div class="device-card">
              <div class="device-header">
                <strong>Device ${index + 1}: ${device.name || 'Unnamed'}</strong>
                <button class="delete-btn" data-index="${index}">Delete</button>
              </div>
              
              <div class="device-row">
                <label>Name:</label>
                <input class="device-name" data-index="${index}" value="${device.name || ''}" 
                       placeholder="Enter device name">
              </div>
              
              <div class="device-row">
                <label>Power Sensor:</label>
                <select class="device-power" data-index="${index}">
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
                <select class="device-energy" data-index="${index}">
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
          
          <div class="add-device">
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
            <select class="upstream-power">
              <option value="">Select upstream power entity (optional)</option>
              ${powerEntities
                .filter(entity => !usedPowerEntities.has(entity.entity_id))
                .map(entity => 
                  `<option value="${entity.entity_id}" ${this.upstreamPower === entity.entity_id ? 'selected' : ''}>
                    ${entity.attributes.friendly_name || entity.entity_id}
                  </option>`
                ).join('')}
            </select>
          </div>
          
          <div class="device-row">
            <label>Upstream Energy:</label>
            <select class="upstream-energy">
              <option value="">Select upstream energy entity (optional)</option>
              ${energyEntities
                .filter(entity => !usedEnergyEntities.has(entity.entity_id))
                .map(entity => 
                  `<option value="${entity.entity_id}" ${this.upstreamEnergy === entity.entity_id ? 'selected' : ''}>
                    ${entity.attributes.friendly_name || entity.entity_id}
                  </option>`
                ).join('')}
            </select>
          </div>
        </div>

        <div class="actions">
          <button class="btn btn-secondary">Reset</button>
          <button class="btn btn-primary">Save Configuration</button>
        </div>
      </div>
    `;
  }
}

// Register the custom element with a new name to avoid conflicts
if (!customElements.get("phantom-config-panel")) {
  customElements.define("phantom-config-panel", PhantomConfigPanel);
  console.log("[Phantom] Panel registered as phantom-config-panel");
} else {
  console.log("[Phantom] Panel already registered, skipping");
}

console.log("[Phantom] Panel script loaded");