// Phantom Power Monitoring Panel
console.log("Loading Phantom panel...");

// Panel configuration
const PANEL_CONFIG = {
  title: "Phantom Power Monitoring",
  icon: "mdi:flash",
  url_path: "phantom"
};

// Wait for Home Assistant to be ready
function waitForHass() {
  return new Promise((resolve) => {
    // Check various possible locations for hass connection
    const checkLocations = [
      () => window.hassConnection,
      () => window.parent && window.parent.hassConnection,
      () => window.top && window.top.hassConnection,
      () => document.querySelector("home-assistant") && document.querySelector("home-assistant").hass,
      () => window.hassEl && window.hassEl.hass
    ];
    
    // Try immediate resolution
    for (const check of checkLocations) {
      try {
        const result = check();
        if (result) {
          resolve(result);
          return;
        }
      } catch (e) {
        // Ignore errors, continue checking
      }
    }
    
    // Wait for it to be available
    const checkInterval = setInterval(() => {
      for (const check of checkLocations) {
        try {
          const result = check();
          if (result) {
            clearInterval(checkInterval);
            resolve(result);
            return;
          }
        } catch (e) {
          // Ignore errors, continue checking
        }
      }
    }, 100);
    
    // Fallback timeout
    setTimeout(() => {
      clearInterval(checkInterval);
      console.error("Could not find hassConnection after 15 seconds");
      resolve(null);
    }, 15000);
  });
}

// Get hass object from connection
async function getHass() {
  const connection = await waitForHass();
  if (!connection) return null;
  
  // Try to get hass from various locations
  const hassLocations = [
    () => connection.hass,
    () => connection,
    () => window.hass,
    () => window.parent && window.parent.hass,
    () => window.top && window.top.hass,
    () => document.querySelector("home-assistant") && document.querySelector("home-assistant").hass,
    () => window.hassEl && window.hassEl.hass
  ];
  
  for (const getHassObj of hassLocations) {
    try {
      const hass = getHassObj();
      if (hass && hass.callWS) {
        return hass;
      }
    } catch (e) {
      // Ignore errors, continue checking
    }
  }
  
  console.error("Could not find hass object with callWS method");
  return null;
}

// Panel component
class PhantomPanel extends HTMLElement {
  constructor() {
    super();
    this.hass = null;
    this.devices = [];
    this.upstreamPower = "";
    this.upstreamEnergy = "";
    this.isLoading = true;
    
    console.log("PhantomPanel constructor");
  }

  async connectedCallback() {
    console.log("PhantomPanel connected");
    this.innerHTML = '<div style="padding: 20px;">Loading Phantom configuration...</div>';
    
    try {
      this.hass = await getHass();
      if (this.hass) {
        console.log("Got hass object:", this.hass);
        await this.loadConfiguration();
      } else {
        this.showError("Could not connect to Home Assistant");
      }
    } catch (error) {
      console.error("Error in connectedCallback:", error);
      this.showError(`Connection error: ${error.message}`);
    }
  }

  async loadConfiguration() {
    console.log("Loading configuration...");
    try {
      this.isLoading = true;
      this.render();
      
      const response = await this.hass.callWS({
        type: "phantom/get_config",
      });
      
      console.log("Configuration response:", response);
      
      this.devices = response.devices || [];
      this.upstreamPower = response.upstream_power_entity || "";
      this.upstreamEnergy = response.upstream_energy_entity || "";
      
      this.isLoading = false;
      this.render();
    } catch (error) {
      console.error("Failed to load configuration:", error);
      this.showError(`Failed to load configuration: ${error.message}`);
    }
  }

  async saveConfiguration() {
    console.log("Saving configuration...");
    try {
      await this.hass.callWS({
        type: "phantom/save_config",
        devices: this.devices,
        upstream_power_entity: this.upstreamPower || null,
        upstream_energy_entity: this.upstreamEnergy || null,
      });
      
      this.showToast("Configuration saved successfully!", "success");
    } catch (error) {
      console.error("Failed to save configuration:", error);
      this.showToast(`Failed to save: ${error.message}`, "error");
    }
  }

  showError(message) {
    this.innerHTML = `
      <div style="padding: 20px; color: red; text-align: center;">
        <h2>⚡ Phantom Power Monitoring</h2>
        <p><strong>Error:</strong> ${message}</p>
        <button onclick="location.reload()">Reload</button>
      </div>
    `;
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
    if (!this.hass) return [];
    return Object.values(this.hass.states).filter(
      state => state.entity_id.startsWith("sensor.") && 
               state.attributes.device_class === "power"
    );
  }

  getEnergyEntities() {
    if (!this.hass) return [];
    return Object.values(this.hass.states).filter(
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

    console.log("Rendering with:", {
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
                <button class="delete-btn" onclick="phantomPanel.removeDevice(${index})">Delete</button>
              </div>
              
              <div class="device-row">
                <label>Name:</label>
                <input value="${device.name || ''}" 
                       onchange="phantomPanel.updateDevice(${index}, 'name', this.value)"
                       placeholder="Enter device name">
              </div>
              
              <div class="device-row">
                <label>Power Sensor:</label>
                <select onchange="phantomPanel.updateDevice(${index}, 'power_entity', this.value)">
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
                <select onchange="phantomPanel.updateDevice(${index}, 'energy_entity', this.value)">
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
          
          <div class="add-device" onclick="phantomPanel.addDevice()">
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
            <select onchange="phantomPanel.updateUpstream('power', this.value)">
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
            <select onchange="phantomPanel.updateUpstream('energy', this.value)">
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
          <button class="btn btn-secondary" onclick="phantomPanel.loadConfiguration()">Reset</button>
          <button class="btn btn-primary" onclick="phantomPanel.saveConfiguration()">Save Configuration</button>
        </div>
      </div>
    `;
  }
}

// Register the custom element
customElements.define("phantom-panel", PhantomPanel);

// Initialize when DOM is ready
function initPanel() {
  console.log("Initializing Phantom panel...");
  
  // Try to find the appropriate container
  const containerSelectors = [
    "ha-panel-custom",
    "[data-panel='phantom']", 
    "#view",
    "partial-panel-resolver",
    "app-drawer-layout"
  ];
  
  let panelContainer = null;
  for (const selector of containerSelectors) {
    panelContainer = document.querySelector(selector);
    if (panelContainer) {
      console.log(`Found panel container: ${selector}`);
      break;
    }
  }
  
  // Fallback to body if no container found
  if (!panelContainer) {
    console.log("No specific panel container found, using body");
    panelContainer = document.body;
  }
  
  // Create and add our panel
  const phantomPanel = new PhantomPanel();
  window.phantomPanel = phantomPanel;
  
  // Clear any existing content and add our panel
  if (panelContainer !== document.body) {
    panelContainer.innerHTML = "";
  }
  panelContainer.appendChild(phantomPanel);
  
  console.log("Phantom panel setup complete");
}

// Wait for DOM to be ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initPanel);
} else {
  initPanel();
}