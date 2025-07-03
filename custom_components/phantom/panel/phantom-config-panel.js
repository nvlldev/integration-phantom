// Phantom Power Monitoring Panel

class PhantomConfigPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this.groups = [];
    this.tariff = null;
    this.isLoading = true;
    this.selectedGroupIndex = -1;
    this.showTariffConfig = false;
    
    // console.log("[Phantom] Panel constructor");
  }

  set hass(hass) {
    // console.log("[Phantom] Hass object received:", hass);
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
    // console.log("[Phantom] Narrow:", value);
  }

  set route(value) {
    // console.log("[Phantom] Route:", value);
  }

  set panel(value) {
    // console.log("[Phantom] Panel:", value);
  }

  async initialize() {
    // console.log("[Phantom] Initializing panel...");
    this.innerHTML = '<div style="padding: 20px;">Loading Phantom configuration...</div>';
    
    // Set up event delegation
    this.addEventListener('click', this.handleClick.bind(this));
    this.addEventListener('change', this.handleChange.bind(this));
    this.addEventListener('input', this.handleInput.bind(this));
    
    try {
      await this.loadConfiguration();
    } catch (error) {
      // console.error("[Phantom] Error during initialization:", error);
      this.showError(`Initialization error: ${error.message}`);
    }
  }

  handleClick(event) {
    let target = event.target;
    let action = target.dataset.action;
    
    // Check parent elements for data-action if not found on target
    if (!action && target.parentElement) {
      target = target.parentElement;
      action = target.dataset.action;
    }
    
    // All buttons now use data-action attributes
    if (action) {
      this.handleAction(action, target);
    }
  }
  
  handleAction(action, target) {
    switch (action) {
      case 'add-tou-period':
        this.addTouPeriod();
        break;
      case 'add-device':
        this.addDevice();
        break;
      case 'add-group':
        this.addGroup();
        break;
      case 'delete-group':
        const groupIndex = parseInt(target.dataset.groupIndex);
        this.deleteGroup(groupIndex);
        break;
      case 'edit-group':
        const editIndex = parseInt(target.dataset.groupIndex);
        this.editGroup(editIndex);
        break;
      case 'delete-device':
        const deviceIndex = parseInt(target.dataset.index);
        if (target.dataset.touIndex !== undefined) {
          this.removeTouPeriod(parseInt(target.dataset.touIndex));
        } else {
          this.removeDevice(deviceIndex);
        }
        break;
      case 'reload':
        this.loadConfiguration();
        break;
      case 'tariff-config':
        this.showTariffConfig = true;
        this.render();
        break;
      case 'back':
        this.selectedGroupIndex = -1;
        this.showTariffConfig = false;
        this.render();
        break;
      case 'save':
        this.saveConfiguration();
        break;
      default:
        console.log("[Phantom] Unknown action:", action);
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
    } else if (target.classList.contains('tariff-enabled')) {
      this.updateTariffEnabled(target.checked);
    } else if (target.classList.contains('tariff-currency')) {
      this.updateTariffCurrency(target.value);
    } else if (target.classList.contains('tariff-rate-type')) {
      this.updateTariffRateType(target.value);
    } else if (target.classList.contains('tariff-flat-rate')) {
      this.updateTariffFlatRate(parseFloat(target.value));
    } else if (target.classList.contains('tou-name')) {
      const index = parseInt(target.dataset.index);
      this.updateTouPeriod(index, 'name', target.value);
    } else if (target.classList.contains('tou-rate')) {
      const index = parseInt(target.dataset.index);
      this.updateTouPeriod(index, 'rate', parseFloat(target.value));
    } else if (target.classList.contains('tou-start')) {
      const index = parseInt(target.dataset.index);
      this.updateTouPeriod(index, 'start_time', target.value);
    } else if (target.classList.contains('tou-end')) {
      const index = parseInt(target.dataset.index);
      this.updateTouPeriod(index, 'end_time', target.value);
    } else if (target.classList.contains('tou-day')) {
      const index = parseInt(target.dataset.index);
      const day = parseInt(target.dataset.day);
      this.updateTouDays(index, day, target.checked);
    } else if (target.classList.contains('tariff-mode')) {
      this.updateTariffMode(target.value);
    } else if (target.classList.contains('tariff-rate-entity')) {
      this.updateTariffRateEntity(target.value);
    } else if (target.classList.contains('tariff-period-entity')) {
      this.updateTariffPeriodEntity(target.value);
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
    // console.log("[Phantom] Loading configuration...");
    try {
      this.isLoading = true;
      this.render();
      
      const response = await this._hass.callWS({
        type: "phantom/get_config",
      });
      
      // console.log("[Phantom] Configuration response:", response);
      
      this.groups = response.groups || [];
      this.tariff = response.tariff || null;
      
      this.isLoading = false;
      this.render();
    } catch (error) {
      // console.error("[Phantom] Failed to load configuration:", error);
      this.showError(`Failed to load configuration: ${error.message}`);
    }
  }

  async saveConfiguration() {
    try {
      // Validate tariff configuration before saving
      const validation = this.validateTariffConfig();
      if (!validation.valid) {
        this.showToast(validation.error, "error");
        return;
      }

      await this._hass.callWS({
        type: "phantom/save_config",
        groups: this.groups,
        tariff: this.tariff,
      });
      
      this.showToast("Configuration saved successfully!", "success");
      this.selectedGroupIndex = -1;
      this.showTariffConfig = false;
      this.render();
    } catch (error) {
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

  // ============================
  // TARIFF STATE MANAGEMENT - REWRITTEN
  // ============================

  /**
   * Ensures tariff object exists with proper structure
   */
  ensureTariffExists() {
    if (!this.tariff) {
      this.tariff = this.getDefaultTariff();
    }
    return this.tariff;
  }

  /**
   * Get the current tariff mode (internal/external)
   */
  getTariffMode() {
    if (!this.tariff) return 'internal';
    
    // Check for explicit mode first
    if (this.tariff.mode) {
      return this.tariff.mode;
    }
    
    // Fallback: infer from presence of external sensor fields
    if (this.tariff.rate_entity || this.tariff.period_entity) {
      return 'external';
    }
    
    return 'internal';
  }

  /**
   * Enable/disable tariff tracking
   */
  updateTariffEnabled(enabled) {
    this.ensureTariffExists();
    this.tariff.enabled = enabled;
    
    // Initialize default structure when first enabled
    if (enabled && this.getTariffMode() === 'internal' && !this.tariff.rate_structure) {
      this.tariff.rate_structure = {
        type: 'flat',
        flat_rate: 0.10,
        tou_rates: []
      };
    }
    
    this.render();
  }

  /**
   * Update currency settings
   */
  updateTariffCurrency(currency) {
    this.ensureTariffExists();
    this.tariff.currency = currency;
    this.tariff.currency_symbol = this.getCurrencySymbol(currency);
  }

  /**
   * Get currency symbol for a currency code
   */
  getCurrencySymbol(currency) {
    const symbols = {
      'USD': '$',
      'EUR': '€',
      'GBP': '£',
      'CAD': '$',
      'AUD': '$',
      'JPY': '¥'
    };
    return symbols[currency] || '$';
  }

  /**
   * Switch between flat rate and time-of-use pricing
   */
  updateTariffRateType(type) {
    this.ensureTariffExists();
    
    // Only update rate type if we're in internal mode
    if (this.getTariffMode() !== 'internal') {
      console.log("[Phantom] Ignoring rate type change in external mode");
      return;
    }
    
    // Ensure rate_structure exists
    if (!this.tariff.rate_structure) {
      this.tariff.rate_structure = {
        type: 'flat',
        flat_rate: 0.10,
        tou_rates: []
      };
    }
    
    this.tariff.rate_structure.type = type;
    
    // Initialize TOU rates array if switching to TOU
    if (type === 'tou' && !this.tariff.rate_structure.tou_rates) {
      this.tariff.rate_structure.tou_rates = [];
    }
    
    this.render();
  }

  /**
   * Update flat rate value
   */
  updateTariffFlatRate(rate) {
    this.ensureTariffExists();
    if (!this.tariff.rate_structure) {
      this.tariff.rate_structure = { type: 'flat', flat_rate: 0.10, tou_rates: [] };
    }
    this.tariff.rate_structure.flat_rate = rate;
  }

  /**
   * Add a new TOU period
   */
  addTouPeriod() {
    this.ensureTariffExists();
    
    // Ensure rate_structure exists
    if (!this.tariff.rate_structure) {
      this.tariff.rate_structure = {
        type: 'flat',
        flat_rate: 0.10,
        tou_rates: []
      };
    }
    
    if (!this.tariff.rate_structure.tou_rates) {
      this.tariff.rate_structure.tou_rates = [];
    }
    
    // Switch to TOU rate type when adding a TOU period
    this.tariff.rate_structure.type = 'tou';
    
    this.tariff.rate_structure.tou_rates.push({
      name: '',
      rate: 0.10,
      start_time: '00:00',
      end_time: '06:00',
      days: [0, 1, 2, 3, 4, 5, 6] // All days by default
    });
    
    this.render();
  }

  /**
   * Remove a TOU period
   */
  removeTouPeriod(index) {
    if (this.tariff?.rate_structure?.tou_rates) {
      this.tariff.rate_structure.tou_rates.splice(index, 1);
      this.render();
    }
  }

  updateTouPeriod(index, field, value) {
    if (this.tariff && this.tariff.rate_structure && this.tariff.rate_structure.tou_rates) {
      const period = this.tariff.rate_structure.tou_rates[index];
      if (period) {
        period[field] = value;
      }
    }
  }

  updateTouDays(index, day, checked) {
    if (this.tariff && this.tariff.rate_structure && this.tariff.rate_structure.tou_rates) {
      const period = this.tariff.rate_structure.tou_rates[index];
      if (period) {
        if (!period.days) {
          period.days = [];
        }
        if (checked) {
          if (!period.days.includes(day)) {
            period.days.push(day);
            period.days.sort();
          }
        } else {
          period.days = period.days.filter(d => d !== day);
        }
      }
    }
  }

  getDefaultTariff() {
    return {
      enabled: false,
      mode: 'internal',
      currency: 'USD',
      currency_symbol: '$',
      rate_structure: {
        type: 'flat',
        flat_rate: 0.10,
        tou_rates: []
      }
    };
  }

  /**
   * Validate tariff configuration before saving
   */
  validateTariffConfig() {
    if (!this.tariff || !this.tariff.enabled) {
      return { valid: true }; // Not enabled, so no validation needed
    }

    const mode = this.getTariffMode();
    
    if (mode === 'external') {
      if (!this.tariff.rate_entity) {
        return { valid: false, error: 'Rate sensor is required for external mode' };
      }
    } else {
      // Internal mode validation
      if (!this.tariff.rate_structure) {
        return { valid: false, error: 'Rate structure is required for internal mode' };
      }
      
      if (this.tariff.rate_structure.type === 'flat') {
        if (!this.tariff.rate_structure.flat_rate || this.tariff.rate_structure.flat_rate <= 0) {
          return { valid: false, error: 'Flat rate must be greater than 0' };
        }
      } else if (this.tariff.rate_structure.type === 'tou') {
        if (!this.tariff.rate_structure.tou_rates || this.tariff.rate_structure.tou_rates.length === 0) {
          return { valid: false, error: 'At least one TOU period is required' };
        }
        
        // Validate each TOU period
        for (let i = 0; i < this.tariff.rate_structure.tou_rates.length; i++) {
          const period = this.tariff.rate_structure.tou_rates[i];
          if (!period.name || period.name.trim() === '') {
            return { valid: false, error: `TOU period ${i + 1} name is required` };
          }
          if (!period.rate || period.rate <= 0) {
            return { valid: false, error: `TOU period ${i + 1} rate must be greater than 0` };
          }
          if (!period.days || period.days.length === 0) {
            return { valid: false, error: `TOU period ${i + 1} must have at least one day selected` };
          }
        }
      }
    }
    
    return { valid: true };
  }

  /**
   * Switch between internal configuration and external sensors
   */
  updateTariffMode(mode) {
    this.ensureTariffExists();
    
    // Store the previous mode
    const previousMode = this.getTariffMode();
    
    if (mode === 'external') {
      this.tariff.mode = 'external';
      
      // Initialize external sensor fields if they don't exist
      if (!this.tariff.rate_entity) {
        this.tariff.rate_entity = '';
      }
      if (!this.tariff.period_entity) {
        this.tariff.period_entity = '';
      }
      
      // Preserve rate_structure as fallback - don't modify it
      // This allows users to switch back to internal mode without losing their configuration
    } else {
      this.tariff.mode = 'internal';
      
      // Clear external sensor references but don't delete them entirely
      // This preserves the values if user switches back
      if (previousMode === 'external') {
        // Don't delete, just ensure internal rate structure exists
        if (!this.tariff.rate_structure) {
          this.tariff.rate_structure = {
            type: 'flat',
            flat_rate: 0.10,
            tou_rates: []
          };
        }
      }
    }
    
    this.render();
  }

  /**
   * Set external rate sensor
   */
  updateTariffRateEntity(entityId) {
    this.ensureTariffExists();
    this.tariff.rate_entity = entityId || null;
  }

  /**
   * Set external TOU period sensor
   */
  updateTariffPeriodEntity(entityId) {
    this.ensureTariffExists();
    this.tariff.period_entity = entityId || null;
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

  /**
   * Get numeric entities for rate sensor selection
   */
  getNumericEntities() {
    if (!this._hass || !this._hass.states) return [];
    
    return Object.values(this._hass.states).filter(entity => {
      const domain = entity.entity_id.split('.')[0];
      return ['sensor', 'input_number', 'number'].includes(domain) &&
             entity.state !== 'unavailable' &&
             entity.state !== 'unknown' &&
             !isNaN(parseFloat(entity.state));
    });
  }

  /**
   * Get text/string entities for period sensor selection
   */
  getTextEntities() {
    if (!this._hass || !this._hass.states) return [];
    
    return Object.values(this._hass.states).filter(entity => {
      const domain = entity.entity_id.split('.')[0];
      return ['sensor', 'input_text', 'text'].includes(domain) &&
             entity.state !== 'unavailable' &&
             entity.state !== 'unknown';
    });
  }

  getUsedEntities(type) {
    const used = new Set();
    this.groups.forEach(group => {
      group.devices.forEach(device => {
        const entity = device[`${type}_entity`];
        if (entity) used.add(entity);
      });
      // Also include upstream entities
      if (type === 'power' && group.upstream_power_entity) {
        used.add(group.upstream_power_entity);
      }
      if (type === 'energy' && group.upstream_energy_entity) {
        used.add(group.upstream_energy_entity);
      }
    });
    return used;
  }

  getUsedEntitiesInCurrentGroup(type) {
    const used = new Set();
    if (this.selectedGroupIndex >= 0) {
      const group = this.groups[this.selectedGroupIndex];
      
      // Add all device entities of this type
      group.devices.forEach(device => {
        const entity = device[`${type}_entity`];
        if (entity) used.add(entity);
      });
      
      // Add upstream entities
      if (type === 'power' && group.upstream_power_entity) {
        used.add(group.upstream_power_entity);
      }
      if (type === 'energy' && group.upstream_energy_entity) {
        used.add(group.upstream_energy_entity);
      }
    }
    return used;
  }

  isEntityFromPhantom(entity) {
    // Check if this entity is created by our integration
    // Entity IDs follow pattern: sensor.phantom_{group}_{type}
    // Also check attributes to be more accurate
    if (entity.entity_id.startsWith("sensor.phantom_")) {
      return true;
    }
    
    // Also check if the entity belongs to a Phantom device
    if (entity.attributes && entity.attributes.device_class) {
      const device_id = entity.attributes.device_id;
      if (device_id && this._hass && this._hass.devices) {
        const device = this._hass.devices[device_id];
        if (device && device.manufacturer === "Phantom") {
          return true;
        }
      }
    }
    
    return false;
  }

  filterEntitiesForDevice(entities, type, currentDeviceIndex) {
    const usedInGroup = this.getUsedEntitiesInCurrentGroup(type);
    const group = this.groups[this.selectedGroupIndex];
    const currentDevice = group.devices[currentDeviceIndex];
    const currentValue = currentDevice[`${type}_entity`];
    
    return entities.filter(entity => {
      // Exclude entities from our own integration
      if (this.isEntityFromPhantom(entity)) return false;
      
      // Include the currently selected entity
      if (entity.entity_id === currentValue) return true;
      
      // Exclude entities already used in this group
      if (usedInGroup.has(entity.entity_id)) return false;
      
      return true;
    });
  }

  filterEntitiesForUpstream(entities, type) {
    const usedInGroup = this.getUsedEntitiesInCurrentGroup(type);
    const group = this.groups[this.selectedGroupIndex];
    const currentValue = type === 'power' ? group.upstream_power_entity : group.upstream_energy_entity;
    
    return entities.filter(entity => {
      // Exclude entities from our own integration
      if (this.isEntityFromPhantom(entity)) return false;
      
      // Include the currently selected entity
      if (entity.entity_id === currentValue) return true;
      
      // Exclude entities already used as devices in this group
      let usedAsDevice = false;
      group.devices.forEach(device => {
        if (device[`${type}_entity`] === entity.entity_id) {
          usedAsDevice = true;
        }
      });
      if (usedAsDevice) return false;
      
      return true;
    });
  }

  render() {
    if (this.isLoading) {
      this.innerHTML = '<div style="padding: 20px; text-align: center;">Loading...</div>';
      return;
    }

    console.log("[Phantom] Rendering - showTariffConfig:", this.showTariffConfig, "selectedGroupIndex:", this.selectedGroupIndex);

    // Show appropriate view
    if (this.showTariffConfig) {
      console.log("[Phantom] Rendering tariff config");
      this.renderTariffConfig();
    } else if (this.selectedGroupIndex >= 0) {
      console.log("[Phantom] Rendering group editor");
      this.renderGroupEditor();
    } else {
      console.log("[Phantom] Rendering group list");
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
          <div style="display: flex; gap: 12px;">
            <button class="btn btn-secondary" data-action="tariff-config">💰 Tariff Settings</button>
            <button class="btn btn-primary" data-action="add-group">Add Group</button>
          </div>
        </div>
        
        ${(this.tariff && this.tariff.enabled) ? `
          <div style="background: var(--success-color, #4caf50); color: white; padding: 12px; border-radius: 4px; margin-bottom: 16px;">
            <strong>Tariff Tracking Active:</strong> ${this.tariff.rate_entity ? 'Using external sensors' : `${this.tariff.currency_symbol || '$'}/kWh rates configured`}
          </div>
        ` : ''}

        ${this.groups.length === 0 ? `
          <div class="empty-state">
            <h2>No groups configured</h2>
            <p>Create your first monitoring group to start tracking power consumption.</p>
            <div class="add-group-card" data-action="add-group" style="margin-top: 24px; cursor: pointer;">
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
                  <button class="btn btn-secondary" data-action="edit-group" data-group-index="${index}">Edit</button>
                  <button class="btn btn-secondary" data-action="delete-group" data-group-index="${index}">Delete</button>
                </div>
              </div>
            </div>
          `;
        }).join('')}

        <div class="actions">
          <button class="btn btn-primary" data-action="save">Save Configuration</button>
        </div>
      </div>
    `;
  }

  renderGroupEditor() {
    const group = this.groups[this.selectedGroupIndex];
    const powerEntities = this.getPowerEntities();
    const energyEntities = this.getEnergyEntities();

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
          <button class="back-btn" data-action="back">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
            </svg>
            Back
          </button>
          <input class="group-name-input" value="${group.name}" placeholder="Group name">
        </div>
        
        <div style="background: var(--info-color, #039be5); color: white; padding: 12px; border-radius: 4px; margin-bottom: 16px; font-size: 14px;">
          <strong>Note:</strong> Renaming a group will create new sensors and remove the old ones. Entity history will be preserved in the database but won't be associated with the new sensors.
        </div>

        <div class="section">
          <h2>Devices (${group.devices.length})</h2>
          
          ${group.devices.length === 0 ? `
            <p style="text-align: center; color: var(--secondary-text-color); padding: 40px;">
              No devices configured. Add your first device to start monitoring.
            </p>
          ` : group.devices.map((device, index) => {
            const filteredPowerEntities = this.filterEntitiesForDevice(powerEntities, 'power', index);
            const filteredEnergyEntities = this.filterEntitiesForDevice(energyEntities, 'energy', index);
            
            return `
              <div class="device-card">
                <div class="device-header">
                  <strong>Device ${index + 1}: ${device.name || 'Unnamed'}</strong>
                  <button class="btn btn-secondary" data-action="delete-device" data-index="${index}">Delete</button>
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
                    ${filteredPowerEntities.map(entity => 
                      `<option value="${entity.entity_id}" ${device.power_entity === entity.entity_id ? 'selected' : ''}>
                        ${entity.attributes.friendly_name ? `${entity.attributes.friendly_name} (${entity.entity_id})` : entity.entity_id}
                      </option>`
                    ).join('')}
                  </select>
                </div>
                
                <div class="device-row">
                  <label>Energy Sensor:</label>
                  <select class="device-energy" data-index="${index}">
                    <option value="">Select energy sensor (optional)</option>
                    ${filteredEnergyEntities.map(entity => 
                      `<option value="${entity.entity_id}" ${device.energy_entity === entity.entity_id ? 'selected' : ''}>
                        ${entity.attributes.friendly_name ? `${entity.attributes.friendly_name} (${entity.entity_id})` : entity.entity_id}
                      </option>`
                    ).join('')}
                  </select>
                </div>
              </div>
            `;
          }).join('')}
          
          <div class="add-device" data-action="add-device">
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
              ${this.filterEntitiesForUpstream(powerEntities, 'power')
                .map(entity => 
                  `<option value="${entity.entity_id}" ${group.upstream_power_entity === entity.entity_id ? 'selected' : ''}>
                    ${entity.attributes.friendly_name ? `${entity.attributes.friendly_name} (${entity.entity_id})` : entity.entity_id}
                  </option>`
                ).join('')}
            </select>
          </div>
          
          <div class="device-row">
            <label>Upstream Energy:</label>
            <select class="upstream-energy">
              <option value="">Select upstream energy entity (optional)</option>
              ${this.filterEntitiesForUpstream(energyEntities, 'energy')
                .map(entity => 
                  `<option value="${entity.entity_id}" ${group.upstream_energy_entity === entity.entity_id ? 'selected' : ''}>
                    ${entity.attributes.friendly_name ? `${entity.attributes.friendly_name} (${entity.entity_id})` : entity.entity_id}
                  </option>`
                ).join('')}
            </select>
          </div>
        </div>

        <div class="actions">
          <button class="btn btn-secondary" data-action="back">Cancel</button>
          <button class="btn btn-primary" data-action="save">Save Configuration</button>
        </div>
      </div>
    `;
  }

  /**
   * Render the complete tariff configuration section
   */
  renderTariffConfiguration(tariff) {
    if (!tariff) {
      tariff = this.getDefaultTariff();
    }

    const mode = this.getTariffMode();

    return `
      <div class="section">
        <h2>🔌 Electricity Rate Settings</h2>
        <p style="color: var(--secondary-text-color); margin-bottom: 24px;">
          Configure electricity rates to track energy costs across all device groups.
          Choose between internal rate configuration or external Home Assistant sensors.
        </p>
        
        <!-- Enable/Disable Toggle -->
        <div class="device-row">
          <label>Enable Tariff Tracking:</label>
          <input type="checkbox" class="tariff-enabled" ${tariff.enabled ? 'checked' : ''}>
          <span style="color: var(--secondary-text-color); font-size: 0.9em; margin-left: 8px;">
            Track energy costs for all devices and groups
          </span>
        </div>
        
        ${tariff.enabled ? this.renderActiveTariffConfig(tariff, mode) : this.renderDisabledTariffMessage()}
      </div>
    `;
  }

  renderDisabledTariffMessage() {
    return `
      <div style="padding: 24px; background: var(--secondary-background-color); border-radius: 8px; margin-top: 16px;">
        <p style="color: var(--secondary-text-color); margin: 0; text-align: center;">
          💡 Enable tariff tracking above to configure electricity rates and track energy costs.
        </p>
      </div>
    `;
  }

  renderActiveTariffConfig(tariff, mode) {
    return `
      <!-- Mode Selection -->
      <div class="device-row">
        <label>Configuration Mode:</label>
        <select class="tariff-mode">
          <option value="internal" ${mode === 'internal' ? 'selected' : ''}>📊 Configure rates here</option>
          <option value="external" ${mode === 'external' ? 'selected' : ''}>🔗 Use external sensors</option>
        </select>
        <span style="color: var(--secondary-text-color); font-size: 0.9em; margin-left: 8px;">
          ${mode === 'internal' ? 'Set up rates manually' : 'Use Home Assistant sensors for dynamic rates'}
        </span>
      </div>

      <!-- Currency Selection -->
      <div class="device-row">
        <label>Currency:</label>
        <select class="tariff-currency">
          <option value="USD" ${tariff.currency === 'USD' ? 'selected' : ''}>🇺🇸 USD ($)</option>
          <option value="EUR" ${tariff.currency === 'EUR' ? 'selected' : ''}>🇪🇺 EUR (€)</option>
          <option value="GBP" ${tariff.currency === 'GBP' ? 'selected' : ''}>🇬🇧 GBP (£)</option>
          <option value="CAD" ${tariff.currency === 'CAD' ? 'selected' : ''}>🇨🇦 CAD ($)</option>
          <option value="AUD" ${tariff.currency === 'AUD' ? 'selected' : ''}>🇦🇺 AUD ($)</option>
          <option value="JPY" ${tariff.currency === 'JPY' ? 'selected' : ''}>🇯🇵 JPY (¥)</option>
        </select>
      </div>

      ${mode === 'internal' ? this.renderInternalRateConfig(tariff) : this.renderExternalSensorConfig(tariff)}
    `;
  }

  renderInternalRateConfig(tariff) {
    // Ensure rate_structure exists with defaults
    if (!tariff.rate_structure) {
      tariff.rate_structure = {
        type: 'flat',
        flat_rate: 0.10,
        tou_rates: []
      };
    }
    
    const rateType = tariff.rate_structure.type || 'flat';
    
    return `
      <!-- Rate Type Selection -->
      <div class="device-row">
        <label>Rate Structure:</label>
        <select class="tariff-rate-type">
          <option value="flat" ${rateType === 'flat' ? 'selected' : ''}>📊 Flat Rate</option>
          <option value="tou" ${rateType === 'tou' ? 'selected' : ''}>⏰ Time of Use (TOU)</option>
        </select>
        <span style="color: var(--secondary-text-color); font-size: 0.9em; margin-left: 8px;">
          ${rateType === 'flat' ? 'Single rate for all times' : 'Different rates by time period'}
        </span>
      </div>

      ${rateType === 'flat' ? this.renderFlatRateConfig(tariff) : this.renderTouRateConfig(tariff)}
    `;
  }

  renderFlatRateConfig(tariff) {
    const rate = tariff.rate_structure?.flat_rate || 0.10;
    
    return `
      <div class="device-row">
        <label>Electricity Rate:</label>
        <div style="display: flex; align-items: center; gap: 8px;">
          <input type="number" class="tariff-flat-rate" value="${rate}" 
                 step="0.001" min="0" placeholder="0.10" style="width: 120px;">
          <span>${tariff.currency_symbol || '$'}/kWh</span>
        </div>
        <span style="color: var(--secondary-text-color); font-size: 0.9em; margin-left: 8px;">
          Cost per kilowatt-hour
        </span>
      </div>
    `;
  }

  renderTouRateConfig(tariff) {
    const touRates = tariff.rate_structure?.tou_rates || [];
    
    return `
      <div class="tou-rates">
        <h3>⏰ Time of Use Periods</h3>
        <p style="color: var(--secondary-text-color); font-size: 0.9em; margin-bottom: 16px;">
          Set different electricity rates for different times of day and days of the week.
        </p>
        
        ${touRates.map((rate, index) => this.renderTouPeriodCard(rate, index, tariff.currency_symbol)).join('')}
        
        <div class="add-device" data-action="add-tou-period" style="margin-top: 16px;">
          <div style="font-size: 24px; color: var(--primary-color);">+</div>
          <div>Add TOU Period</div>
        </div>
        
        ${touRates.length === 0 ? `
          <div style="padding: 16px; background: var(--warning-color); color: white; border-radius: 8px; margin-top: 16px;">
            ⚠️ Add at least one TOU period to use time-based pricing.
          </div>
        ` : ''}
      </div>
    `;
  }

  renderTouPeriodCard(rate, index, currencySymbol) {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    
    return `
      <div class="device-card" style="margin-bottom: 16px;">
        <div class="device-header">
          <strong>${rate.name || `Period ${index + 1}`}</strong>
          <button class="btn btn-secondary" data-action="delete-device" data-tou-index="${index}">
            🗑️ Delete
          </button>
        </div>
        
        <div class="device-row">
          <label>Period Name:</label>
          <input class="tou-name" data-index="${index}" value="${rate.name || ''}" 
                 placeholder="e.g., Off-Peak, Shoulder, Peak">
        </div>
        
        <div class="device-row">
          <label>Rate:</label>
          <div style="display: flex; align-items: center; gap: 8px;">
            <input type="number" class="tou-rate" data-index="${index}" value="${rate.rate || 0.10}" 
                   step="0.001" min="0" placeholder="0.10" style="width: 120px;">
            <span>${currencySymbol || '$'}/kWh</span>
          </div>
        </div>
        
        <div class="device-row">
          <label>Time Range:</label>
          <div style="display: flex; align-items: center; gap: 8px;">
            <input type="time" class="tou-start" data-index="${index}" value="${rate.start_time || '00:00'}">
            <span>to</span>
            <input type="time" class="tou-end" data-index="${index}" value="${rate.end_time || '06:00'}">
          </div>
        </div>
        
        <div class="device-row">
          <label>Active Days:</label>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            ${days.map((day, dayIndex) => `
              <label style="display: flex; align-items: center; gap: 4px; padding: 4px 8px; background: var(--secondary-background-color); border-radius: 4px;">
                <input type="checkbox" class="tou-day" data-index="${index}" data-day="${dayIndex}" 
                       ${rate.days?.includes(dayIndex) ? 'checked' : ''}>
                ${day}
              </label>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  renderExternalSensorConfig(tariff) {
    return `
      <div style="padding: 16px; background: var(--secondary-background-color); border-radius: 8px; margin: 16px 0;">
        <h4 style="margin-top: 0;">🔗 External Sensor Configuration</h4>
        <p style="color: var(--secondary-text-color); font-size: 0.9em;">
          Use Home Assistant sensors to provide dynamic electricity rates. This is useful for 
          integrations with utility companies or smart meters that provide real-time pricing.
        </p>
      </div>

      <div class="device-row">
        <label>Rate Sensor: <span style="color: red;">*</span></label>
        <select class="tariff-rate-entity">
          <option value="">Select rate sensor (provides $/kWh)</option>
          ${this.getNumericEntities().map(entity => 
            `<option value="${entity.entity_id}" ${tariff.rate_entity === entity.entity_id ? 'selected' : ''}>
              ${entity.attributes.friendly_name || entity.entity_id} (${entity.state})
            </option>`
          ).join('')}
        </select>
        <span style="color: var(--secondary-text-color); font-size: 0.9em; margin-left: 8px;">
          Required: Numeric sensor providing current electricity rate
        </span>
      </div>
      
      <div class="device-row">
        <label>TOU Period Sensor:</label>
        <select class="tariff-period-entity">
          <option value="">Select TOU period sensor (optional)</option>
          ${this.getTextEntities().map(entity => 
            `<option value="${entity.entity_id}" ${tariff.period_entity === entity.entity_id ? 'selected' : ''}>
              ${entity.attributes.friendly_name || entity.entity_id} (${entity.state})
            </option>`
          ).join('')}
        </select>
        <span style="color: var(--secondary-text-color); font-size: 0.9em; margin-left: 8px;">
          Optional: Text sensor providing current TOU period name
        </span>
      </div>

      ${!tariff.rate_entity ? `
        <div style="padding: 16px; background: var(--warning-color); color: white; border-radius: 8px; margin-top: 16px;">
          ⚠️ Rate sensor is required for external mode to function properly.
        </div>
      ` : ''}
    `;
  }

  renderTariffConfig() {
    const tariff = this.tariff || this.getDefaultTariff();
    
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
      </style>

      <div class="phantom-panel">
        <div class="header">
          <button class="back-btn" data-action="back">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
            </svg>
            Back
          </button>
          <h1>💰 Tariff Configuration</h1>
        </div>
        
        ${this.renderTariffConfiguration(tariff)}

        <div class="actions">
          <button class="btn btn-secondary" data-action="back">⬅️ Back to Groups</button>
          <button class="btn btn-primary" data-action="save">💾 Save Configuration</button>
        </div>
      </div>
    `;
  }
}

// Register the custom element with a new name to avoid conflicts
if (!customElements.get("phantom-config-panel")) {
  customElements.define("phantom-config-panel", PhantomConfigPanel);
  // console.log("[Phantom] Panel registered as phantom-config-panel");
} else {
  // console.log("[Phantom] Panel already registered, skipping");
}

// console.log("[Phantom] Panel script loaded");