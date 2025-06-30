// Phantom Power Monitoring Panel
console.log("[Phantom] Loading panel v3.0...");

class PhantomConfigPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this.groups = [];
    this.isLoading = true;
    this.selectedGroupIndex = -1;
    
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
    this.addEventListener('input', this.handleInput.bind(this));
    
    try {
      await this.loadConfiguration();
    } catch (error) {
      console.error("[Phantom] Error during initialization:", error);
      this.showError(`Initialization error: ${error.message}`);
    }
  }

  handleClick(event) {
    const target = event.target;
    
    if (target.classList.contains('add-group-btn')) {
      this.addGroup();
    } else if (target.classList.contains('delete-group-btn')) {
      const index = parseInt(target.dataset.groupIndex);
      this.deleteGroup(index);
    } else if (target.classList.contains('edit-group-btn')) {
      const index = parseInt(target.dataset.groupIndex);
      this.editGroup(index);
    } else if (target.classList.contains('delete-device-btn')) {
      const index = parseInt(target.dataset.index);
      this.removeDevice(index);
    } else if (target.closest('.add-device')) {
      this.addDevice();
    } else if (target.classList.contains('btn-primary')) {
      this.saveConfiguration();
    } else if (target.classList.contains('btn-secondary')) {
      this.loadConfiguration();
    } else if (target.classList.contains('back-btn')) {
      this.selectedGroupIndex = -1;
      this.render();
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

  handleInput(event) {
    const target = event.target;
    
    if (target.classList.contains('group-name-input')) {
      if (this.selectedGroupIndex >= 0) {
        this.groups[this.selectedGroupIndex].name = target.value;
      }
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
      
      this.groups = response.groups || [];
      
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
        groups: this.groups,
      });
      
      this.showToast("Configuration saved successfully!", "success");
      this.selectedGroupIndex = -1;
      this.render();
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

  addGroup() {
    const newGroup = {
      name: `Group ${this.groups.length + 1}`,
      devices: [],
      upstream_power_entity: null,
      upstream_energy_entity: null,
    };
    this.groups.push(newGroup);
    this.selectedGroupIndex = this.groups.length - 1;
    this.render();
  }

  deleteGroup(index) {
    if (confirm(`Are you sure you want to delete "${this.groups[index].name}"?`)) {
      this.groups.splice(index, 1);
      this.render();
    }
  }

  editGroup(index) {
    this.selectedGroupIndex = index;
    this.render();
  }

  addDevice() {
    if (this.selectedGroupIndex >= 0) {
      this.groups[this.selectedGroupIndex].devices.push({ 
        name: "", 
        power_entity: "", 
        energy_entity: "" 
      });
      this.render();
    }
  }

  removeDevice(index) {
    if (this.selectedGroupIndex >= 0) {
      this.groups[this.selectedGroupIndex].devices.splice(index, 1);
      this.render();
    }
  }

  updateDevice(index, field, value) {
    if (this.selectedGroupIndex >= 0) {
      this.groups[this.selectedGroupIndex].devices[index][field] = value;
    }
  }

  updateUpstream(field, value) {
    if (this.selectedGroupIndex >= 0) {
      if (field === "power") {
        this.groups[this.selectedGroupIndex].upstream_power_entity = value || null;
      } else if (field === "energy") {
        this.groups[this.selectedGroupIndex].upstream_energy_entity = value || null;
      }
    }
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
    const used = new Set();
    this.groups.forEach(group => {
      group.devices.forEach(device => {
        const entity = device[`${type}_entity`];
        if (entity) used.add(entity);
      });
    });
    return used;
  }

  render() {
    if (this.isLoading) {
      this.innerHTML = '<div style="padding: 20px; text-align: center;">Loading...</div>';
      return;
    }

    // Show group list or group editor
    if (this.selectedGroupIndex >= 0) {
      this.renderGroupEditor();
    } else {
      this.renderGroupList();
    }
  }

  renderGroupList() {
    this.innerHTML = `
      <style>
        .phantom-panel { padding: 16px; max-width: 1200px; margin: 0 auto; font-family: var(--primary-font-family); }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
        .group-card { background: var(--card-background-color); border-radius: 8px; padding: 24px; margin-bottom: 16px; box-shadow: var(--ha-card-box-shadow); }
        .group-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .group-info { color: var(--secondary-text-color); }
        .btn { padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; }
        .btn-primary { background: var(--primary-color); color: white; }
        .btn-secondary { background: var(--secondary-background-color); color: var(--primary-text-color); margin-right: 8px; }
        .actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; }
        .empty-state { text-align: center; padding: 60px 20px; color: var(--secondary-text-color); }
        .add-group-card { border: 2px dashed var(--divider-color); border-radius: 8px; padding: 40px; text-align: center; cursor: pointer; }
        .add-group-card:hover { border-color: var(--primary-color); }
      </style>

      <div class="phantom-panel">
        <div class="header">
          <h1>⚡ Phantom Power Monitoring</h1>
          <button class="btn btn-primary add-group-btn">Add Group</button>
        </div>

        ${this.groups.length === 0 ? `
          <div class="empty-state">
            <h2>No groups configured</h2>
            <p>Create your first monitoring group to start tracking power consumption.</p>
            <div class="add-group-card add-group-btn" style="margin-top: 24px;">
              <div style="font-size: 48px; color: var(--primary-color); margin-bottom: 16px;">+</div>
              <div style="font-size: 18px;">Create your first group</div>
            </div>
          </div>
        ` : this.groups.map((group, index) => {
          const deviceCount = group.devices.length;
          const hasPower = group.devices.some(d => d.power_entity);
          const hasEnergy = group.devices.some(d => d.energy_entity);
          
          return `
            <div class="group-card">
              <div class="group-header">
                <div>
                  <h2>${group.name}</h2>
                  <div class="group-info">
                    ${deviceCount} device${deviceCount !== 1 ? 's' : ''} • 
                    ${hasPower ? '⚡ Power' : ''} 
                    ${hasPower && hasEnergy ? ' • ' : ''} 
                    ${hasEnergy ? '📊 Energy' : ''}
                    ${!hasPower && !hasEnergy ? 'No sensors configured' : ''}
                  </div>
                </div>
                <div>
                  <button class="btn btn-secondary edit-group-btn" data-group-index="${index}">Edit</button>
                  <button class="btn btn-secondary delete-group-btn" data-group-index="${index}">Delete</button>
                </div>
              </div>
            </div>
          `;
        }).join('')}

        <div class="actions">
          <button class="btn btn-primary">Save Configuration</button>
        </div>
      </div>
    `;
  }

  renderGroupEditor() {
    const group = this.groups[this.selectedGroupIndex];
    const powerEntities = this.getPowerEntities();
    const energyEntities = this.getEnergyEntities();
    const usedPowerEntities = this.getUsedEntities("power");
    const usedEnergyEntities = this.getUsedEntities("energy");

    this.innerHTML = `
      <style>
        .phantom-panel { padding: 16px; max-width: 1200px; margin: 0 auto; font-family: var(--primary-font-family); }
        .header { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
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
        .back-btn { background: transparent; border: none; cursor: pointer; padding: 8px; display: flex; align-items: center; gap: 4px; color: var(--primary-text-color); }
        .group-name-input { background: transparent; border: none; font-size: 28px; font-weight: 500; color: var(--primary-text-color); padding: 0; outline: none; }
        .group-name-input:focus { border-bottom: 2px solid var(--primary-color); }
      </style>

      <div class="phantom-panel">
        <div class="header">
          <button class="back-btn">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
            </svg>
            Back
          </button>
          <input class="group-name-input" value="${group.name}" placeholder="Group name">
        </div>

        <div class="section">
          <h2>Devices (${group.devices.length})</h2>
          
          ${group.devices.length === 0 ? `
            <p style="text-align: center; color: var(--secondary-text-color); padding: 40px;">
              No devices configured. Add your first device to start monitoring.
            </p>
          ` : group.devices.map((device, index) => `
            <div class="device-card">
              <div class="device-header">
                <strong>Device ${index + 1}: ${device.name || 'Unnamed'}</strong>
                <button class="delete-device-btn" data-index="${index}">Delete</button>
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
                  `<option value="${entity.entity_id}" ${group.upstream_power_entity === entity.entity_id ? 'selected' : ''}>
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
                  `<option value="${entity.entity_id}" ${group.upstream_energy_entity === entity.entity_id ? 'selected' : ''}>
                    ${entity.attributes.friendly_name || entity.entity_id}
                  </option>`
                ).join('')}
            </select>
          </div>
        </div>

        <div class="actions">
          <button class="btn btn-secondary back-btn">Cancel</button>
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