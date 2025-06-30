import { LitElement, html, css } from "https://unpkg.com/[email protected]/lit-element.js?module";

class PhantomPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      route: { type: Object },
      panel: { type: Object },
      _devices: { type: Array },
      _upstreamPower: { type: String },
      _upstreamEnergy: { type: String },
      _isLoading: { type: Boolean },
    };
  }

  static get styles() {
    return css`
      :host {
        padding: 16px;
        display: block;
        max-width: 1200px;
        margin: 0 auto;
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
        justify-content: between;
        align-items: center;
        margin-bottom: 12px;
      }

      .device-name {
        font-weight: 500;
        font-size: 16px;
        color: var(--primary-text-color);
        flex: 1;
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

      .delete-button:hover {
        background: var(--error-color);
        opacity: 0.9;
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

      .device-row select {
        flex: 1;
        padding: 8px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        background: var(--primary-background-color);
        color: var(--primary-text-color);
        font-size: 14px;
      }

      .device-row input {
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
        background: var(--state-icon-active-color);
      }

      .add-device-text {
        color: var(--secondary-text-color);
        font-size: 16px;
        margin-bottom: 8px;
      }

      .add-device-icon {
        font-size: 24px;
        color: var(--primary-color);
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
        transition: all 0.2s;
      }

      .btn-primary {
        background: var(--primary-color);
        color: white;
      }

      .btn-primary:hover {
        background: var(--primary-color);
        opacity: 0.9;
      }

      .btn-secondary {
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
        border: 1px solid var(--divider-color);
      }

      .btn-secondary:hover {
        background: var(--divider-color);
      }

      .empty-state {
        text-align: center;
        padding: 48px 24px;
        color: var(--secondary-text-color);
      }

      .empty-state h3 {
        margin-bottom: 8px;
        color: var(--primary-text-color);
      }

      .loading {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 48px;
      }

      @media (max-width: 768px) {
        :host {
          padding: 8px;
        }

        .device-row {
          flex-direction: column;
          align-items: stretch;
          gap: 8px;
        }

        .device-row label {
          min-width: auto;
        }

        .actions {
          flex-direction: column;
        }
      }
    `;
  }

  constructor() {
    super();
    this._devices = [];
    this._upstreamPower = "";
    this._upstreamEnergy = "";
    this._isLoading = true;
  }

  firstUpdated() {
    this._loadConfiguration();
  }

  async _loadConfiguration() {
    try {
      this._isLoading = true;
      const response = await this.hass.callWS({
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
    }
  }

  async _saveConfiguration() {
    try {
      await this.hass.callWS({
        type: "phantom/save_config",
        devices: this._devices,
        upstream_power_entity: this._upstreamPower || null,
        upstream_energy_entity: this._upstreamEnergy || null,
      });
      
      // Show success message
      this._showToast("Configuration saved successfully!", "success");
    } catch (error) {
      console.error("Failed to save configuration:", error);
      this._showToast("Failed to save configuration", "error");
    }
  }

  _showToast(message, type = "info") {
    // Create a simple toast notification
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
    return Object.values(this.hass.states).filter(
      state => state.entity_id.startsWith("sensor.") && 
               state.attributes.device_class === "power"
    );
  }

  _getEnergyEntities() {
    return Object.values(this.hass.states).filter(
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
  }

  _removeDevice(index) {
    this._devices = this._devices.filter((_, i) => i !== index);
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

  render() {
    if (this._isLoading) {
      return html`
        <div class="loading">
          <ha-circular-progress active></ha-circular-progress>
        </div>
      `;
    }

    const powerEntities = this._getPowerEntities();
    const energyEntities = this._getEnergyEntities();
    const usedPowerEntities = this._getUsedEntities("power");
    const usedEnergyEntities = this._getUsedEntities("energy");

    return html`
      <div class="header">
        <h1>⚡ Phantom Power Monitoring</h1>
      </div>

      <div class="section">
        <h2>Devices</h2>
        
        ${this._devices.length === 0 ? html`
          <div class="empty-state">
            <h3>No devices configured</h3>
            <p>Add your first device to start monitoring power and energy consumption.</p>
          </div>
        ` : html`
          ${this._devices.map((device, index) => html`
            <div class="device-card">
              <div class="device-header">
                <div class="device-name">Device ${index + 1}</div>
                <button class="delete-button" @click=${() => this._removeDevice(index)}>
                  Delete
                </button>
              </div>
              
              <div class="device-row">
                <label>Device Name:</label>
                <input
                  type="text"
                  .value=${device.name}
                  @input=${(e) => this._updateDevice(index, "name", e.target.value)}
                  placeholder="Enter device name"
                >
              </div>
              
              <div class="device-row">
                <label>Power Sensor:</label>
                <select
                  .value=${device.power_entity}
                  @change=${(e) => this._updateDevice(index, "power_entity", e.target.value)}
                >
                  <option value="">Select power sensor (optional)</option>
                  ${powerEntities.map(entity => html`
                    <option value=${entity.entity_id}>
                      ${entity.attributes.friendly_name || entity.entity_id}
                    </option>
                  `)}
                </select>
              </div>
              
              <div class="device-row">
                <label>Energy Sensor:</label>
                <select
                  .value=${device.energy_entity}
                  @change=${(e) => this._updateDevice(index, "energy_entity", e.target.value)}
                >
                  <option value="">Select energy sensor (optional)</option>
                  ${energyEntities.map(entity => html`
                    <option value=${entity.entity_id}>
                      ${entity.attributes.friendly_name || entity.entity_id}
                    </option>
                  `)}
                </select>
              </div>
            </div>
          `)}
        `}
        
        <div class="add-device" @click=${this._addDevice}>
          <div class="add-device-icon">+</div>
          <div class="add-device-text">Add Device</div>
        </div>
      </div>

      <div class="section">
        <h2>Upstream Entities</h2>
        <p style="color: var(--secondary-text-color); margin-bottom: 16px;">
          Configure upstream entities to calculate remainder values (upstream - group total).
        </p>
        
        <div class="device-row">
          <label>Upstream Power:</label>
          <select
            .value=${this._upstreamPower}
            @change=${(e) => this._updateUpstream("power", e.target.value)}
          >
            <option value="">Select upstream power entity (optional)</option>
            ${powerEntities
              .filter(entity => !usedPowerEntities.has(entity.entity_id))
              .map(entity => html`
                <option value=${entity.entity_id}>
                  ${entity.attributes.friendly_name || entity.entity_id}
                </option>
              `)}
          </select>
        </div>
        
        <div class="device-row">
          <label>Upstream Energy:</label>
          <select
            .value=${this._upstreamEnergy}
            @change=${(e) => this._updateUpstream("energy", e.target.value)}
          >
            <option value="">Select upstream energy entity (optional)</option>
            ${energyEntities
              .filter(entity => !usedEnergyEntities.has(entity.entity_id))
              .map(entity => html`
                <option value=${entity.entity_id}>
                  ${entity.attributes.friendly_name || entity.entity_id}
                </option>
              `)}
          </select>
        </div>
      </div>

      <div class="actions">
        <button class="btn btn-secondary" @click=${this._loadConfiguration}>
          Reset
        </button>
        <button class="btn btn-primary" @click=${this._saveConfiguration}>
          Save Configuration
        </button>
      </div>
    `;
  }
}

customElements.define("phantom-panel", PhantomPanel);