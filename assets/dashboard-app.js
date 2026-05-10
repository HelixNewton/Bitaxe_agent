    const editable = [
      "MINER_NAME", "MINER_URL", "MINER_API_PROFILE", "MINER_INFO_PATH", "MINER_ASIC_PATH", "MINER_SETTINGS_PATH", "MINER_RESTART_PATH",
      "MINER_FREQUENCY_FIELD", "MINER_VOLTAGE_FIELD", "MINER_FAN_SPEED_FIELD", "MINER_AUTO_FAN_FIELD",
      "MINER_STATUS_FILE", "MINER_LEARNING_FILE", "MINER_SWARM_FILE", "MINER_UI_HOST", "MINER_UI_PORT",
      "NERDMINER_SERIAL_PORT", "NERDMINER_CONFIG_FILE", "NERDMINER_URL",
      "BITAXE_URL", "BITAXE_MODE", "BITAXE_DRY_RUN", "BITAXE_AUTO_FAN", "BITAXE_LOOP_SECONDS",
      "BITAXE_MIN_FREQUENCY", "BITAXE_MAX_FREQUENCY", "BITAXE_ABSOLUTE_MAX_FREQUENCY", "BITAXE_FREQ_STEP", "BITAXE_MIN_VOLTAGE",
      "BITAXE_MAX_VOLTAGE", "BITAXE_ABSOLUTE_MAX_VOLTAGE", "BITAXE_VOLTAGE_STEP", "BITAXE_TARGET_TEMP_C", "BITAXE_HOT_TEMP_C",
      "BITAXE_EMERGENCY_TEMP_C", "BITAXE_ABSOLUTE_MAX_EMERGENCY_TEMP_C", "BITAXE_COOL_TEMP_C", "BITAXE_MAX_VR_TEMP_C",
      "BITAXE_ABSOLUTE_MAX_VR_TEMP_C", "BITAXE_MIN_INPUT_VOLTAGE_MV", "BITAXE_MAX_POWER_W", "BITAXE_ABSOLUTE_MAX_POWER_W",
      "BITAXE_CLIMB_POWER_RATIO",
      "BITAXE_MAX_ERROR_PERCENTAGE", "BITAXE_MAX_DOMAIN_SPREAD_PERCENTAGE", "BITAXE_CRITICAL_DOMAIN_SPREAD_PERCENTAGE",
      "BITAXE_DOMAIN_SPREAD_POLLS", "BITAXE_LEARNING_ENABLED", "BITAXE_LEARNING_MIN_SAMPLES", "BITAXE_LEARNING_BAD_LIMIT",
      "BITAXE_LEARNING_RESTORE_MARGIN", "BITAXE_LEARNING_EFFICIENCY_WEIGHT", "BITAXE_ADAPTIVE_COOLDOWN_ENABLED",
      "BITAXE_ADAPTIVE_MIN_COOLDOWN_SECONDS", "BITAXE_ADAPTIVE_MAX_COOLDOWN_SECONDS", "BITAXE_ADAPTIVE_STABLE_SAMPLES",
      "BITAXE_MIN_FAN_PERCENT", "BITAXE_MAX_FAN_PERCENT",
      "BITAXE_STEP_COOLDOWN_SECONDS", "BITAXE_USE_ASIC_OPTIONS"
    ];
    const groups = {
      "Miner": ["MINER_NAME", "MINER_URL", "MINER_API_PROFILE", "MINER_INFO_PATH", "MINER_ASIC_PATH", "MINER_SETTINGS_PATH", "MINER_RESTART_PATH", "MINER_STATUS_FILE", "MINER_LEARNING_FILE", "MINER_SWARM_FILE", "MINER_UI_HOST", "MINER_UI_PORT", "NERDMINER_SERIAL_PORT", "NERDMINER_CONFIG_FILE", "NERDMINER_URL"],
      "Write Mapping": ["MINER_FREQUENCY_FIELD", "MINER_VOLTAGE_FIELD", "MINER_FAN_SPEED_FIELD", "MINER_AUTO_FAN_FIELD"],
      "Control": ["BITAXE_URL", "BITAXE_MODE", "BITAXE_DRY_RUN", "BITAXE_AUTO_FAN", "BITAXE_LOOP_SECONDS"],
      "Frequency": ["BITAXE_MIN_FREQUENCY", "BITAXE_MAX_FREQUENCY", "BITAXE_ABSOLUTE_MAX_FREQUENCY", "BITAXE_FREQ_STEP", "BITAXE_USE_ASIC_OPTIONS"],
      "Voltage": ["BITAXE_MIN_VOLTAGE", "BITAXE_MAX_VOLTAGE", "BITAXE_ABSOLUTE_MAX_VOLTAGE", "BITAXE_VOLTAGE_STEP"],
      "Thermal": ["BITAXE_TARGET_TEMP_C", "BITAXE_HOT_TEMP_C", "BITAXE_EMERGENCY_TEMP_C", "BITAXE_ABSOLUTE_MAX_EMERGENCY_TEMP_C", "BITAXE_COOL_TEMP_C", "BITAXE_MAX_VR_TEMP_C", "BITAXE_ABSOLUTE_MAX_VR_TEMP_C"],
      "Power And Stability": ["BITAXE_MIN_INPUT_VOLTAGE_MV", "BITAXE_MAX_POWER_W", "BITAXE_ABSOLUTE_MAX_POWER_W", "BITAXE_CLIMB_POWER_RATIO", "BITAXE_MAX_ERROR_PERCENTAGE", "BITAXE_MAX_DOMAIN_SPREAD_PERCENTAGE", "BITAXE_CRITICAL_DOMAIN_SPREAD_PERCENTAGE", "BITAXE_DOMAIN_SPREAD_POLLS", "BITAXE_LEARNING_ENABLED", "BITAXE_LEARNING_MIN_SAMPLES", "BITAXE_LEARNING_BAD_LIMIT", "BITAXE_LEARNING_RESTORE_MARGIN", "BITAXE_LEARNING_EFFICIENCY_WEIGHT", "BITAXE_ADAPTIVE_COOLDOWN_ENABLED", "BITAXE_ADAPTIVE_MIN_COOLDOWN_SECONDS", "BITAXE_ADAPTIVE_MAX_COOLDOWN_SECONDS", "BITAXE_ADAPTIVE_STABLE_SAMPLES", "BITAXE_MIN_FAN_PERCENT", "BITAXE_MAX_FAN_PERCENT", "BITAXE_STEP_COOLDOWN_SECONDS"]
    };
    const presets = {
      cool: {
        BITAXE_MAX_FREQUENCY: "525",
        BITAXE_MAX_VOLTAGE: "1060",
        BITAXE_COOL_TEMP_C: "61",
        BITAXE_MAX_POWER_W: "15.5",
        BITAXE_MAX_ERROR_PERCENTAGE: "10",
        BITAXE_STEP_COOLDOWN_SECONDS: "240"
      },
      balanced: {
        BITAXE_MAX_FREQUENCY: "535",
        BITAXE_MAX_VOLTAGE: "1090",
        BITAXE_COOL_TEMP_C: "63",
        BITAXE_MAX_POWER_W: "16.5",
        BITAXE_MAX_ERROR_PERCENTAGE: "20",
        BITAXE_STEP_COOLDOWN_SECONDS: "180"
      },
      performance: {
        BITAXE_MAX_FREQUENCY: "575",
        BITAXE_MAX_VOLTAGE: "1125",
        BITAXE_COOL_TEMP_C: "64",
        BITAXE_MAX_POWER_W: "17.5",
        BITAXE_MAX_ERROR_PERCENTAGE: "25",
        BITAXE_STEP_COOLDOWN_SECONDS: "120"
      }
    };
    const historyBuffer = [];
    const activityLog = [];
    const maxHistoryPoints = 60;
    const maxActivityItems = 18;
    let refreshIntervalMs = 5000;
    let refreshTimer = null;
    let refreshPaused = false;
    let chartVisible = false;
    let lastConfigSignature = "";
    let lastOverviewSignature = "";
    let lastNerdminerConfig = null;
    let reconnectAttempts = 0;

    const dom = {
      overview: document.getElementById("overview"),
      health: document.getElementById("health"),
      heroText: document.getElementById("heroText"),
      updatedAt: document.getElementById("updatedAt"),
      updatedChip: document.getElementById("updatedChip"),
      modeChip: document.getElementById("modeChip"),
      modeStripChip: document.getElementById("modeStripChip"),
      dryRunChip: document.getElementById("dryRunChip"),
      fanChip: document.getElementById("fanChip"),
      fanStripChip: document.getElementById("fanStripChip"),
      stabilityChip: document.getElementById("stabilityChip"),
      domainGuardChip: document.getElementById("domainGuardChip"),
      decisionReason: document.getElementById("decisionReason"),
      decisionPatch: document.getElementById("decisionPatch"),
      decisionHint: document.getElementById("decisionHint"),
      actionMessage: document.getElementById("actionMessage"),
      historyChart: document.getElementById("historyChart"),
      chartTooltip: document.getElementById("chartTooltip"),
      latestHashrate: document.getElementById("latestHashrate"),
      latestTemp: document.getElementById("latestTemp"),
      latestPower: document.getElementById("latestPower"),
      thermalLabel: document.getElementById("thermalLabel"),
      thermalBar: document.getElementById("thermalBar"),
      thermalHint: document.getElementById("thermalHint"),
      powerLabel: document.getElementById("powerLabel"),
      powerBar: document.getElementById("powerBar"),
      powerHint: document.getElementById("powerHint"),
      nextStepCountdown: document.getElementById("nextStepCountdown"),
      nextStepAt: document.getElementById("nextStepAt"),
      nextStepHint: document.getElementById("nextStepHint"),
      tuningLabel: document.getElementById("tuningLabel"),
      efficiencyNow: document.getElementById("efficiencyNow"),
      energyCostInput: document.getElementById("energyCostInput"),
      targetEfficiencyInput: document.getElementById("targetEfficiencyInput"),
      efficiencyUnitSelect: document.getElementById("efficiencyUnitSelect"),
      dailyCostValue: document.getElementById("dailyCostValue"),
      efficiencyAdvice: document.getElementById("efficiencyAdvice"),
      domainAlert: document.getElementById("domainAlert"),
      domainGrid: document.getElementById("domainGrid"),
      profileAdvisor: document.getElementById("profileAdvisor"),
      advisorTitle: document.getElementById("advisorTitle"),
      advisorText: document.getElementById("advisorText"),
      advisorBadge: document.getElementById("advisorBadge"),
      presetStatus: document.getElementById("presetStatus"),
      details: document.getElementById("details"),
      errorValue: document.getElementById("errorValue"),
      expectedValue: document.getElementById("expectedValue"),
      bestDiffValue: document.getElementById("bestDiffValue"),
      bestDiffSubvalue: document.getElementById("bestDiffSubvalue"),
      soloOddsValue: document.getElementById("soloOddsValue"),
      soloOddsSubvalue: document.getElementById("soloOddsSubvalue"),
      responseValue: document.getElementById("responseValue"),
      statusFreshnessValue: document.getElementById("statusFreshnessValue"),
      statusFreshnessSubvalue: document.getElementById("statusFreshnessSubvalue"),
      advancedHealthValue: document.getElementById("advancedHealthValue"),
      advancedHealthSubvalue: document.getElementById("advancedHealthSubvalue"),
      climbValue: document.getElementById("climbValue"),
      climbSubvalue: document.getElementById("climbSubvalue"),
      decisionCountValue: document.getElementById("decisionCountValue"),
      decisionCountSubvalue: document.getElementById("decisionCountSubvalue"),
      guardrailValue: document.getElementById("guardrailValue"),
      guardrailSubvalue: document.getElementById("guardrailSubvalue"),
      swarmOnline: document.getElementById("swarmOnline"),
      swarmHashrate: document.getElementById("swarmHashrate"),
      swarmPower: document.getElementById("swarmPower"),
      swarmEfficiency: document.getElementById("swarmEfficiency"),
      swarmGrid: document.getElementById("swarmGrid"),
      swarmAddForm: document.getElementById("swarmAddForm"),
      discoveryNotice: document.getElementById("discoveryNotice"),
      showHashrateToggle: document.getElementById("showHashrateToggle"),
      showTempToggle: document.getElementById("showTempToggle"),
      showPowerToggle: document.getElementById("showPowerToggle"),
      updateStrip: document.getElementById("updateStrip"),
      updateStatus: document.getElementById("updateStatus"),
      updateDetails: document.getElementById("updateDetails"),
      esp32Status: document.getElementById("esp32Status"),
      esp32RootValue: document.getElementById("esp32RootValue"),
      esp32RootHint: document.getElementById("esp32RootHint"),
      esp32PortsValue: document.getElementById("esp32PortsValue"),
      esp32PortsHint: document.getElementById("esp32PortsHint"),
      esp32EnvsValue: document.getElementById("esp32EnvsValue"),
      esp32EnvsHint: document.getElementById("esp32EnvsHint"),
      esp32BundlesValue: document.getElementById("esp32BundlesValue"),
      esp32BundlesHint: document.getElementById("esp32BundlesHint"),
      esp32ApiPatchValue: document.getElementById("esp32ApiPatchValue"),
      esp32ApiPatchHint: document.getElementById("esp32ApiPatchHint"),
      nerdminerConfigForm: document.getElementById("nerdminerConfigForm"),
      nerdminerConfigMessage: document.getElementById("nerdminerConfigMessage"),
      nerdminerConfigPreview: document.getElementById("nerdminerConfigPreview"),
      configForm: document.getElementById("configForm"),
      saveMessage: document.getElementById("saveMessage"),
      logServiceSelect: document.getElementById("logServiceSelect"),
      serialLogPortSelect: document.getElementById("serialLogPortSelect"),
      logsMessage: document.getElementById("logsMessage"),
      serviceLogs: document.getElementById("serviceLogs"),
      decision: document.getElementById("decision"),
      raw: document.getElementById("raw"),
      activityLog: document.getElementById("activityLog"),
      refreshSelect: document.getElementById("refreshSelect"),
      pauseRefreshBtn: document.getElementById("pauseRefreshBtn"),
      search: document.getElementById("sectionSearch")
    };

    function prettyBool(value) {
      return String(value) === "true" || value === true ? "On" : "Off";
    }

    function formatKey(key) {
      return key.replace("BITAXE_", "").replaceAll("_", " ");
    }

    function formatSeconds(totalSeconds) {
      const seconds = Math.max(0, Math.floor(totalSeconds));
      const years = Math.floor(seconds / 31536000);
      if (years >= 1) return `${years}y ${Math.floor((seconds % 31536000) / 86400)}d`;
      const days = Math.floor(seconds / 86400);
      if (days >= 1) return `${days}d ${Math.floor((seconds % 86400) / 3600)}h`;
      const hours = Math.floor(seconds / 3600);
      if (hours >= 1) return `${hours}h ${Math.floor((seconds % 3600) / 60)}m`;
      const minutes = Math.floor(seconds / 60);
      const remain = seconds % 60;
      return `${minutes}m ${remain}s`;
    }

    function formatCompactNumber(value) {
      const number = Number(value) || 0;
      if (number >= 1e9) return `${(number / 1e9).toFixed(2)} G`;
      if (number >= 1e6) return `${(number / 1e6).toFixed(2)} M`;
      if (number >= 1e3) return `${(number / 1e3).toFixed(2)} K`;
      return `${number.toFixed(0)}`;
    }

    function formatPercent(value) {
      const number = Number(value) || 0;
      return `${number.toFixed(4)}%`;
    }

    function formatOdds(value) {
      const percent = (Number(value) || 0) * 100;
      if (percent >= 1) return `${percent.toFixed(2)}%`;
      if (percent >= 0.01) return `${percent.toFixed(4)}%`;
      return `${percent.toFixed(6)}%`;
    }

    function formatRatio(value) {
      const number = Number(value);
      return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : "-";
    }

    function temperatureWidget(current, vrm, target, critical, updatedAt) {
      const temp = Number(current);
      const vrmTemp = Number(vrm);
      const marker = Number.isFinite(temp) && critical ? Math.max(0, Math.min(100, (temp / critical) * 100)) : 0;
      const targetStop = critical ? Math.max(0, Math.min(100, (Number(target) / critical) * 100)) : 65;
      const tip = `ASIC ${Number.isFinite(temp) ? temp.toFixed(1) : "-"}C / VRM ${Number.isFinite(vrmTemp) ? vrmTemp.toFixed(1) : "-"}C / ${updatedAt || "no timestamp"}`;
      const vrmMarkup = Number.isFinite(vrmTemp)
        ? `<div class="temp-widget mini" title="${tip}"><div class="temp-zone" style="--target:${targetStop}%"><span class="temp-marker" style="left:${Math.max(0, Math.min(100, (vrmTemp / critical) * 100))}%"></span></div></div>`
        : "";
      return `
        <div class="temp-widget" title="${tip}">
          <div class="temp-zone" style="--target:${targetStop}%"><span class="temp-marker" style="left:${marker}%"></span></div>
          <div class="temp-widget-label"><span>Target ${target ?? "-"}C</span><span>Critical ${critical ?? "-"}C</span></div>
        </div>
        ${vrmMarkup}
      `;
    }

    function blockOdds(hashrateGh, difficulty, seconds) {
      const hashPerSecond = Number(hashrateGh) * 1e9;
      const diff = Number(difficulty);
      if (!hashPerSecond || !diff) return 0;
      const expectedSeconds = (diff * 4294967296) / hashPerSecond;
      return 1 - Math.exp(-seconds / expectedSeconds);
    }

    async function fetchJson(path, options = {}, retries = 2) {
      for (let attempt = 0; attempt <= retries; attempt += 1) {
        try {
          const response = await fetch(path, options);
          if (!response.ok) throw new Error(await response.text());
          reconnectAttempts = 0;
          return response.json();
        } catch (error) {
          if (attempt >= retries) throw error;
          await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
        }
      }
      throw new Error("request failed");
    }

    async function postAction(action) {
      return fetchJson("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action })
      });
    }

    function pushActivity(title, text) {
      activityLog.unshift({ title, text, at: new Date().toLocaleTimeString() });
      while (activityLog.length > maxActivityItems) activityLog.pop();
      dom.activityLog.innerHTML = activityLog.map((item) => `
        <div class="activity-item">
          <strong>${item.title}</strong>
          <div>${item.text}</div>
          <div class="muted">${item.at}</div>
        </div>
      `).join("");
    }

    function addHistoryPoint(state, status) {
      if (!state || typeof state.temperature_c !== "number") return;
      historyBuffer.push({
        temp: Number(state.temperature_c) || 0,
        hash: Number(state.hashrate_gh) || 0,
        power: Number(state.power_w) || 0,
        target: Number(status?.config?.target_temp_c) || 0,
        at: status?.updated_at || new Date().toISOString()
      });
      while (historyBuffer.length > maxHistoryPoints) historyBuffer.shift();
    }

    function normalizeSeries(values, width, height, padding, minOverride, maxOverride) {
      if (!values.length) return [];
      const min = Number.isFinite(minOverride) ? minOverride : Math.min(...values);
      const max = Number.isFinite(maxOverride) ? maxOverride : Math.max(...values);
      const span = max - min || 1;
      return values.map((value, index) => {
        const x = padding + ((width - padding * 2) * index / Math.max(1, values.length - 1));
        const y = height - padding - (((value - min) / span) * (height - padding * 2));
        return { x, y };
      });
    }

    function smoothPath(points) {
      if (!points.length) return "";
      if (points.length === 1) return `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
      const commands = [`M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`];
      for (let index = 0; index < points.length - 1; index += 1) {
        const current = points[index];
        const next = points[index + 1];
        const previous = points[index - 1] || current;
        const after = points[index + 2] || next;
        const tension = 0.18;
        const cp1x = current.x + (next.x - previous.x) * tension;
        const cp1y = current.y + (next.y - previous.y) * tension;
        const cp2x = next.x - (after.x - current.x) * tension;
        const cp2y = next.y - (after.y - current.y) * tension;
        commands.push(`C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${next.x.toFixed(2)} ${next.y.toFixed(2)}`);
      }
      return commands.join(" ");
    }

    function areaPath(points, height, padding) {
      if (!points.length) return "";
      const line = smoothPath(points);
      const first = points[0];
      const last = points[points.length - 1];
      const floor = height - padding;
      return `${line} L ${last.x.toFixed(2)} ${floor.toFixed(2)} L ${first.x.toFixed(2)} ${floor.toFixed(2)} Z`;
    }

    function renderHistoryChart() {
      if (!chartVisible) return;
      if (!historyBuffer.length) {
        dom.historyChart.innerHTML = "";
        return;
      }
      const width = 960;
      const height = 280;
      const padding = 18;
      const showHash = dom.showHashrateToggle?.checked !== false;
      const showTemp = dom.showTempToggle?.checked !== false;
      const showPower = dom.showPowerToggle?.checked !== false;
      const temps = historyBuffer.map((point) => point.temp);
      const hashes = historyBuffer.map((point) => point.hash);
      const powers = historyBuffer.map((point) => point.power);
      const latest = historyBuffer[historyBuffer.length - 1];
      dom.latestHashrate.textContent = `Hashrate ${(latest.hash || 0).toFixed(1)} GH/s`;
      dom.latestTemp.textContent = `Temp ${(latest.temp || 0).toFixed(1)}C`;
      dom.latestPower.textContent = `Power ${(latest.power || 0).toFixed(2)}W`;
      const tempMin = Math.min(...temps, ...historyBuffer.map((point) => point.target || point.temp));
      const tempMax = Math.max(...temps, ...historyBuffer.map((point) => point.target || point.temp), 1);
      const hashPoints = showHash ? normalizeSeries(hashes, width, height, padding) : [];
      const tempPoints = showTemp ? normalizeSeries(temps, width, height, padding, tempMin, tempMax) : [];
      const powerPoints = showPower ? normalizeSeries(powers, width, height, padding) : [];
      const hashPath = smoothPath(hashPoints);
      const tempPath = smoothPath(tempPoints);
      const powerPath = smoothPath(powerPoints);
      const segmentWidth = (width - padding * 2) / Math.max(1, historyBuffer.length - 1);
      const heatBands = historyBuffer.map((point, index) => {
        if (!point.target || point.temp <= point.target) return "";
        const x = Math.max(0, padding + (segmentWidth * index) - segmentWidth / 2);
        return `<rect class="chart-heat" x="${x.toFixed(2)}" y="16" width="${Math.max(6, segmentWidth).toFixed(2)}" height="${height - 34}" rx="9"></rect>`;
      }).join("");
      const grid = [0.2, 0.4, 0.6, 0.8].map((ratio) => {
        const y = (height * ratio).toFixed(2);
        return `<line class="chart-grid" x1="${padding}" y1="${y}" x2="${width - padding}" y2="${y}" />`;
      }).join("");
      dom.historyChart.innerHTML = `
        <defs>
          <linearGradient id="hashFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f9bff" stop-opacity=".38"/><stop offset="1" stop-color="#2f9bff" stop-opacity="0"/></linearGradient>
          <linearGradient id="tempFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#30e69b" stop-opacity=".34"/><stop offset="1" stop-color="#30e69b" stop-opacity="0"/></linearGradient>
          <linearGradient id="powerFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff8a22" stop-opacity=".42"/><stop offset="1" stop-color="#ff8a22" stop-opacity="0"/></linearGradient>
          <filter id="lineGlow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        ${heatBands}
        ${grid}
        ${showHash ? `<path class="chart-area hash" d="${areaPath(hashPoints, height, padding)}"></path><path class="chart-line hash" d="${hashPath}"></path>` : ""}
        ${showPower ? `<path class="chart-area power" d="${areaPath(powerPoints, height, padding)}"></path><path class="chart-line power" d="${powerPath}"></path>` : ""}
        ${showTemp ? `<path class="chart-area temp" d="${areaPath(tempPoints, height, padding)}"></path><path class="chart-line temp" d="${tempPath}"></path>` : ""}
        <text class="chart-axis left" x="${padding}" y="20">Hashrate GH/s</text>
        <text class="chart-axis right" x="${width - 128}" y="20">Temp C / Power W</text>
      `;
    }

    function renderChartTooltip(event) {
      if (!historyBuffer.length) return;
      const rect = dom.historyChart.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      const index = Math.round(ratio * (historyBuffer.length - 1));
      const point = historyBuffer[index];
      dom.chartTooltip.classList.remove("hidden");
      dom.chartTooltip.style.left = `${Math.max(12, Math.min(rect.width - 180, event.clientX - rect.left + 12))}px`;
      dom.chartTooltip.style.top = `${Math.max(12, event.clientY - rect.top - 18)}px`;
      dom.chartTooltip.innerHTML = `
        <strong>${point.at ? new Date(point.at).toLocaleTimeString() : "Reading"}</strong>
        <span>Hashrate ${(point.hash || 0).toFixed(1)} GH/s</span>
        <span>Temp ${(point.temp || 0).toFixed(1)}C</span>
        <span>Power ${(point.power || 0).toFixed(2)}W</span>
      `;
    }

    function restoreEfficiencySettings() {
      dom.energyCostInput.value = localStorage.getItem("bitaxe.energyCost") || dom.energyCostInput.value;
      dom.targetEfficiencyInput.value = localStorage.getItem("bitaxe.targetJth") || dom.targetEfficiencyInput.value;
      dom.efficiencyUnitSelect.value = localStorage.getItem("bitaxe.efficiencyUnit") || dom.efficiencyUnitSelect.value;
    }

    function saveEfficiencySettings() {
      localStorage.setItem("bitaxe.energyCost", dom.energyCostInput.value);
      localStorage.setItem("bitaxe.targetJth", dom.targetEfficiencyInput.value);
      localStorage.setItem("bitaxe.efficiencyUnit", dom.efficiencyUnitSelect.value);
    }

    function renderEfficiencyPanel(state, status) {
      const hashrate = Number(state.hashrate_gh) || 0;
      const power = Number(state.power_w) || 0;
      const ghPerW = hashrate && power ? hashrate / power : 0;
      const jPerTh = ghPerW ? 1000 / ghPerW : 0;
      const cost = Number(dom.energyCostInput.value) || 0;
      const target = Number(dom.targetEfficiencyInput.value) || 20;
      const dailyCost = (power * 24 / 1000) * cost;
      const unit = dom.efficiencyUnitSelect.value;
      dom.efficiencyNow.textContent = ghPerW ? (unit === "ghw" ? `${ghPerW.toFixed(2)} GH/W` : `${jPerTh.toFixed(1)} J/TH`) : "-";
      dom.dailyCostValue.textContent = power ? `$${dailyCost.toFixed(2)} / day` : "-";
      if (!ghPerW) {
        dom.efficiencyAdvice.textContent = "Waiting for hashrate and power telemetry.";
        return;
      }
      if (jPerTh <= target) {
        dom.efficiencyAdvice.textContent = `Efficiency is inside target. Current ${jPerTh.toFixed(1)} J/TH is at or below ${target.toFixed(1)} J/TH.`;
      } else if (Number(state.temperature_c) > Number(status.config?.target_temp_c || 0)) {
        dom.efficiencyAdvice.textContent = `Efficiency is above target and thermals are warm. Prefer lower frequency or more cooling before raising voltage.`;
      } else {
        dom.efficiencyAdvice.textContent = `Efficiency is above target. Try a small voltage reduction first, then watch hashrate stability for a few cycles.`;
      }
    }

    function setBar(node, ratio, variant) {
      node.className = `bar ${variant || ""}`.trim();
      node.querySelector("span").style.width = `${Math.max(0, Math.min(100, ratio))}%`;
    }

    function healthState(temp, target, emergency, lastError) {
      if (lastError) return { className: "status-pill hot", label: "Controller Error" };
      if (temp >= emergency) return { className: "status-pill hot", label: "Emergency Thermal" };
      if (temp >= target) return { className: "status-pill warn", label: "Thermal Watch" };
      return { className: "status-pill ok", label: "Online" };
    }

    function explainTuning(state, status) {
      const temp = Number(state.temperature_c) || 0;
      const power = Number(state.power_w) || 0;
      const cool = Number(status.config?.cool_temp_c) || 0;
      const powerGate = (Number(status.config?.max_power_w) || 0) * 0.9;
      const err = Number(state.error_percentage) || 0;
      const errCap = Number(status.config?.max_error_percentage) || 0;
      if (errCap && err >= errCap) return `Holding because error rate ${err.toFixed(2)}% is above the ${errCap}% guardrail.`;
      if (temp <= cool && power < powerGate) return "The miner is inside the climb window and can step up when cooldown allows.";
      if (temp > cool) return `Holding because temperature ${temp.toFixed(1)}C is above the cool threshold of ${cool}C.`;
      return `Holding because power draw ${power.toFixed(2)}W is above the climb gate of ${powerGate.toFixed(2)}W.`;
    }

    function friendlyDecisionTitle(reason) {
      const text = String(reason || "").toLowerCase();
      if (!text || text === "hold") return "Monitoring normally";
      if (text.includes("cooldown")) return "Cooling down before the next change";
      if (text.includes("emergency") || text.includes("over") || text.includes("hot")) return "Protecting the miner from heat";
      if (text.includes("raise frequency")) return "Performance can increase soon";
      if (text.includes("lower frequency") || text.includes("rollback")) return "Reducing speed for stability";
      if (text.includes("voltage")) return "Adjusting power for stability";
      if (text.includes("learning")) return "Using learned safe settings";
      return reason;
    }

    function friendlyPatch(patch) {
      const entries = Object.entries(patch || {}).filter(([, value]) => value !== null && value !== undefined);
      if (!entries.length) {
        return `<div class="decision-summary"><strong>No manual change needed</strong><span>The agent is watching temperature, power, and stability.</span></div>`;
      }
      const labels = {
        frequency: "Frequency",
        coreVoltage: "Core voltage",
        fanspeed: "Fan speed",
        autofanspeed: "Auto fan"
      };
      return `
        <div class="decision-summary">
          <strong>Planned adjustment</strong>
          <div class="decision-pills">
            ${entries.map(([key, value]) => `<span>${labels[key] || key}: ${value === true ? "On" : value === false ? "Off" : value}</span>`).join("")}
          </div>
        </div>
      `;
    }

    function getDomainGuardState(state, status) {
      const spread = Number(state.domain_spread_percentage) || 0;
      const offline = Number(state.offline_domain_count) || 0;
      const maxSpread = Number(status.config?.max_domain_spread_percentage) || 0;
      const criticalSpread = Number(status.config?.critical_domain_spread_percentage) || 0;
      if (offline > 0 || (criticalSpread && spread >= criticalSpread)) return { label: "Rollback Armed", className: "chip hot" };
      if (maxSpread && spread >= maxSpread) return { label: "Watch", className: "chip warn" };
      return { label: "Stable", className: "chip ok" };
    }

    function renderOverview(state, status) {
      const expected = Number(state.raw?.expectedHashrate) || 0;
      const tempPanel = temperatureWidget(state.temperature_c, state.vr_temperature_c, status.config?.target_temp_c, status.config?.emergency_temp_c, status.updated_at);
      const next = [
        { label: "Temp", value: state.temperature_c?.toFixed?.(1) ?? "-", suffix: "C", sub: `Target ${status.config?.target_temp_c ?? "-"}C`, extra: tempPanel },
        { label: "Hashrate", value: state.hashrate_gh?.toFixed?.(1) ?? "-", suffix: " GH/s", sub: `Expected ${expected ? expected.toFixed(1) : "-"} GH/s` },
        { label: "Power", value: state.power_w?.toFixed?.(2) ?? "-", suffix: " W", sub: `Cap ${status.config?.max_power_w ?? "-"} W` },
        { label: "Frequency", value: state.frequency_mhz ?? "-", suffix: " MHz", sub: `Range ${status.config?.min_frequency ?? "-"}-${status.config?.max_frequency ?? "-"}` }
      ];
      const signature = JSON.stringify(next);
      if (signature === lastOverviewSignature) return;
      lastOverviewSignature = signature;
      dom.overview.innerHTML = next.map((item) => `
        <div class="panel stat-card">
          <div class="panel-body">
            <div class="eyebrow">${item.label}</div>
            <div class="stat-value">${item.value}${item.suffix}</div>
            ${item.extra || ""}
            <div class="stat-foot"><span>${item.sub}</span><span class="chip ok">Live</span></div>
          </div>
        </div>
      `).join("");
    }

    function renderDomains(state) {
      const domains = state.raw?.hashrateMonitor?.asics?.[0]?.domains || [];
      if (!domains.length) {
        dom.domainAlert.textContent = "Domain telemetry is not available yet.";
        dom.domainGrid.innerHTML = `<div class="domain-card"><div class="muted">No domain data in the current payload.</div></div>`;
        return;
      }
      const numeric = domains.map((value) => Number(value) || 0);
      const active = numeric.filter((value) => value > 0);
      const offline = numeric.length - active.length;
      const average = active.length ? active.reduce((sum, value) => sum + value, 0) / active.length : 0;
      const weakest = active.length ? Math.min(...active) : 0;
      const spread = average > 0 ? ((average - weakest) / average) * 100 : 0;
      if (offline > 0) {
        dom.domainAlert.textContent = `${offline} domain ${offline === 1 ? "is" : "are"} offline. Stability rollback risk is active.`;
      } else if (spread >= 18) {
        dom.domainAlert.textContent = `Domain imbalance is critical at ${spread.toFixed(1)}%. The weakest lane is materially underperforming.`;
      } else if (spread >= 10) {
        dom.domainAlert.textContent = `Domain spread is elevated at ${spread.toFixed(1)}%. Watch for a developing weak lane.`;
      } else {
        dom.domainAlert.textContent = `Domain spread is stable at ${spread.toFixed(1)}% across ${numeric.length} active lanes.`;
      }
      dom.domainGrid.innerHTML = numeric.map((value, index) => {
        const deviation = average > 0 ? ((average - value) / average) * 100 : 0;
        const isOffline = value <= 0;
        const stateClass = isOffline ? "hot" : deviation >= 18 ? "hot" : deviation >= 10 ? "warn" : "";
        const stateText = isOffline ? "offline" : deviation >= 18 ? "weak" : deviation >= 10 ? "watch" : "healthy";
        return `
          <div class="domain-card ${isOffline ? "offline" : stateClass}">
            <div class="mini-label">Domain ${index + 1}</div>
            <div class="domain-value">${value.toFixed(1)}</div>
            <div class="muted">GH/s</div>
            <div class="domain-state ${stateClass}">${stateText}</div>
          </div>
        `;
      }).join("");
    }

    function renderSwarm(swarm) {
      const summary = swarm.summary || {};
      const miners = swarm.miners || [];
      dom.swarmOnline.textContent = `${summary.online_miners ?? 0}/${summary.total_miners ?? 0}`;
      dom.swarmHashrate.textContent = `${(Number(summary.total_hashrate_gh) || 0).toFixed(1)} GH/s`;
      dom.swarmPower.textContent = `${(Number(summary.total_power_w) || 0).toFixed(2)} W`;
      dom.swarmEfficiency.textContent = summary.efficiency_gh_per_w ? `${Number(summary.efficiency_gh_per_w).toFixed(2)} GH/W` : "-";
      if (!miners.length) {
        dom.swarmGrid.innerHTML = `<div class="swarm-miner"><strong>No miners configured</strong><span class="muted">Create swarm.json or keep using the primary miner.</span></div>`;
        return;
      }
      dom.swarmGrid.innerHTML = miners.map((miner) => {
        const state = miner.online ? "online" : miner.stale ? "stale" : "offline";
        const removable = miner.id !== "primary";
        const temp = miner.temperature_c === null || miner.temperature_c === undefined ? "-" : `${Number(miner.temperature_c).toFixed(1)}C`;
        const hash = miner.hashrate_gh === null || miner.hashrate_gh === undefined ? "-" : `${Number(miner.hashrate_gh).toFixed(1)} GH/s`;
        const power = miner.power_w === null || miner.power_w === undefined ? "-" : `${Number(miner.power_w).toFixed(2)} W`;
        const efficiency = Number(miner.hashrate_gh) && Number(miner.power_w) ? `${(Number(miner.hashrate_gh) / Number(miner.power_w)).toFixed(2)} GH/W` : "-";
        const spread = miner.domain_spread_percentage === null || miner.domain_spread_percentage === undefined ? "-" : `${Number(miner.domain_spread_percentage).toFixed(1)}%`;
        return `
          <div class="swarm-miner ${state}">
            <div class="swarm-miner-head">
              <strong>${miner.name}</strong>
              <span class="chip ${miner.online ? "ok" : "warn"}">${state}</span>
            </div>
            <div class="muted">${miner.url || "local status"} / ${miner.api_profile || "profile"}</div>
            <div class="swarm-metrics">
              <span><b>${hash}</b><small>Hashrate</small></span>
              <span><b>${temp}</b><small>Temp</small></span>
              <span><b>${power}</b><small>Power</small></span>
              <span><b>${efficiency}</b><small>Efficiency</small></span>
            </div>
            <div class="swarm-miner-foot">
              <span class="muted">${miner.last_error || (miner.status_age_seconds === null ? "Waiting for status." : `status age ${formatSeconds(miner.status_age_seconds)} / spread ${spread}`)}</span>
              <div class="swarm-actions">
                <button type="button" class="btn-secondary reconnect-miner" data-miner-id="${miner.id}">Reconnect</button>
                ${removable ? `<button type="button" class="btn-secondary remove-miner" data-miner-id="${miner.id}" data-miner-name="${miner.name}">Remove</button>` : ""}
              </div>
            </div>
          </div>
        `;
      }).join("");
    }

    function renderUpdateStatus(update) {
      dom.updateStrip.className = `update-strip ${update.update_available ? "warn" : ""}`;
      dom.updateStatus.textContent = update.message || "Update check complete.";
      dom.updateDetails.textContent = `${update.branch || "branch"} @ ${update.current || "unknown"} / behind ${update.behind || 0} / ahead ${update.ahead || 0}`;
    }

    function renderEsp32Status(status) {
      dom.esp32Status.textContent = status.message || "ESP32 status checked.";
      dom.esp32RootValue.textContent = status.available ? "Found" : "Missing";
      dom.esp32RootHint.textContent = status.root || "Set NERDMINER_ROOT to your NerdMiner_v2 folder.";
      const ports = status.ports || [];
      const envs = status.envs || [];
      const bundles = status.firmware_bundles || [];
      const apiPatch = status.config_api_patch || {};
      dom.esp32PortsValue.textContent = String(ports.length);
      dom.esp32PortsHint.textContent = ports.length ? ports.map((port) => port.device || port.name).slice(0, 3).join(", ") : "No serial ports detected.";
      dom.serialLogPortSelect.innerHTML = ports.length
        ? ports.map((port) => `<option value="${port.device || port.name}">${port.device || port.name}</option>`).join("")
        : `<option value="">Auto detect port</option>`;
      dom.esp32EnvsValue.textContent = String(envs.length);
      dom.esp32EnvsHint.textContent = envs.length ? envs.slice(0, 4).join(", ") : "No PlatformIO environments found yet.";
      dom.esp32BundlesValue.textContent = String(bundles.length);
      dom.esp32BundlesHint.textContent = bundles.length ? bundles.slice(0, 3).map((bundle) => bundle.name).join(", ") : "No prebuilt firmware bundles found.";
      const hasFirmwareDefaults = Boolean(apiPatch.checks?.local_defaults);
      dom.esp32ApiPatchValue.textContent = apiPatch.installed ? (hasFirmwareDefaults ? "Ready" : "Installed") : "Missing";
      dom.esp32ApiPatchHint.textContent = hasFirmwareDefaults
        ? "API patch and private firmware defaults are present. Rebuild and flash once."
        : (apiPatch.message || "Install patch, rebuild, and flash once.");
    }

    async function refreshEsp32Status() {
      dom.esp32Status.textContent = "Checking ESP32 tooling...";
      try {
        const status = await fetchJson("/api/esp32/status", {}, 0);
        renderEsp32Status(status);
      } catch (error) {
        dom.esp32Status.textContent = `ESP32 check failed: ${error.message}`;
      }
    }

    function renderNerdminerConfig(payload) {
      lastNerdminerConfig = payload || {};
      const values = lastNerdminerConfig.values || {};
      ["DeviceUrl", "SSID", "PoolUrl", "PoolPort", "BtcWallet", "Timezone"].forEach((key) => {
        if (dom.nerdminerConfigForm.elements[key]) dom.nerdminerConfigForm.elements[key].value = values[key] ?? "";
      });
      dom.nerdminerConfigForm.elements.WifiPW.value = "";
      dom.nerdminerConfigForm.elements.PoolPassword.value = "";
      dom.nerdminerConfigForm.elements.SaveStats.checked = values.SaveStats === true || String(values.SaveStats).toLowerCase() === "true";
      const passwordNote = [
        lastNerdminerConfig.has_wifi_password ? "Wi-Fi password saved" : "Wi-Fi password empty",
        lastNerdminerConfig.has_pool_password ? "pool password saved" : "pool password empty"
      ].join(" / ");
      dom.nerdminerConfigMessage.textContent = `${lastNerdminerConfig.exists ? "Local NerdMiner config loaded" : "No local NerdMiner config yet"} at ${lastNerdminerConfig.config_file || "nerdminer-config.json"}. ${passwordNote}.`;
      const preview = {
        SSID: values.SSID || "",
        WifiPW: lastNerdminerConfig.has_wifi_password ? "[saved password]" : "",
        PoolUrl: values.PoolUrl || "",
        PoolPassword: lastNerdminerConfig.has_pool_password ? "[saved password]" : "",
        BtcWallet: values.BtcWallet || "",
        PoolPort: Number(values.PoolPort) || 21496,
        Timezone: Number(values.Timezone) || 2,
        SaveStats: Boolean(values.SaveStats)
      };
      dom.nerdminerConfigPreview.textContent = JSON.stringify(preview, null, 2);
    }

    function collectNerdminerConfig() {
      const form = dom.nerdminerConfigForm;
      return {
        DeviceUrl: form.elements.DeviceUrl.value,
        SSID: form.elements.SSID.value,
        WifiPW: form.elements.WifiPW.value,
        PoolUrl: form.elements.PoolUrl.value,
        PoolPort: form.elements.PoolPort.value,
        PoolPassword: form.elements.PoolPassword.value,
        BtcWallet: form.elements.BtcWallet.value,
        Timezone: form.elements.Timezone.value,
        SaveStats: form.elements.SaveStats.checked
      };
    }

    async function refreshNerdminerConfig() {
      try {
        const config = await fetchJson("/api/nerdminer/config", {}, 0);
        renderNerdminerConfig(config);
      } catch (error) {
        dom.nerdminerConfigMessage.textContent = `NerdMiner settings failed to load: ${error.message}`;
      }
    }

    async function refreshLogs() {
      const service = dom.logServiceSelect.value || "controller";
      dom.logsMessage.textContent = "Loading service logs...";
      try {
        const params = new URLSearchParams({ service, lines: "140" });
        if (service === "nerdminer" && dom.serialLogPortSelect.value) params.set("port", dom.serialLogPortSelect.value);
        const payload = await fetchJson(`/api/logs?${params.toString()}`, {}, 0);
        dom.logsMessage.textContent = `${payload.message || "Logs loaded."} ${payload.port ? `(${payload.port})` : payload.unit ? `(${payload.unit})` : ""}`;
        dom.serviceLogs.textContent = (payload.lines || []).join("\n") || "No log lines returned.";
      } catch (error) {
        dom.logsMessage.textContent = `Log request failed: ${error.message}`;
        dom.serviceLogs.textContent = "";
      }
    }

    function presetDistance(config, preset) {
      return Object.entries(preset).reduce((score, [key, value]) => {
        if (String(config[key] ?? "") === String(value)) return score;
        return score + 1;
      }, 0);
    }

    function renderPresetStatus(config) {
      const candidates = Object.entries(presets).map(([name, preset]) => ({ name, distance: presetDistance(config, preset) }));
      candidates.sort((a, b) => a.distance - b.distance);
      const active = candidates[0];
      document.querySelectorAll("[data-preset-card]").forEach((card) => {
        card.classList.toggle("active", card.dataset.presetCard === active.name);
      });
      const total = Object.keys(presets[active.name]).length;
      const matched = total - active.distance;
      dom.presetStatus.textContent = active.distance === 0
        ? `Current preset: ${active.name}. Saved config exactly matches the profile.`
        : `Closest preset: ${active.name}. ${matched}/${total} profile fields match the saved rails.`;
    }

    function renderProfileAdvisor(state, status) {
      const temp = Number(state.temperature_c);
      const power = Number(state.power_w);
      const fan = Number(state.fan_percent);
      const spread = Number(state.domain_spread_percentage);
      const maxSpread = Number(status.config?.max_domain_spread_percentage) || 12;
      const target = Number(status.config?.target_temp_c) || 65;
      const powerCap = Number(status.config?.max_power_w) || 16.5;
      const best = status.learning?.best_stable;
      let tone = "ok";
      let title = "Hold Balanced";
      let text = "Learning data says the miner is inside daily operating rails. Keep collecting samples.";
      let badge = "Balanced";

      if (!Number.isFinite(temp) || !Number.isFinite(power)) {
        tone = "sync";
        title = "Waiting for telemetry";
        text = "The advisor will activate once status.json includes live temperature, power, and learning data.";
        badge = "Sync";
      } else if (spread >= maxSpread || fan >= 98 || temp >= target || power >= powerCap * 0.96) {
        tone = "warn";
        title = "Cooling Headroom Tight";
        text = `Hold or step down if this persists. Fan ${Number.isFinite(fan) ? fan.toFixed(0) : "-"}%, temp ${temp.toFixed(1)}C, domain spread ${Number.isFinite(spread) ? spread.toFixed(1) : "-"}%.`;
        badge = "Watch";
      } else if (best && Number(best.frequency_mhz) <= Number(state.frequency_mhz || 0)) {
        tone = "ok";
        title = "Best Learned Range";
        text = `Best stable target is ${best.frequency_mhz} MHz / ${best.voltage_mv} mV with ${Number(best.best_hashrate_gh || 0).toFixed(1)} GH/s observed.`;
        badge = "Learned";
      } else if (temp < target - 4 && power < powerCap * 0.9 && spread < maxSpread * 0.75) {
        tone = "boost";
        title = "Room to Test Upward";
        text = "Thermal, power, and domain spread are clean enough for one cautious step after cooldown.";
        badge = "Test";
      }

      dom.profileAdvisor.className = `advisor-card ${tone}`;
      dom.advisorTitle.textContent = title;
      dom.advisorText.textContent = text;
      dom.advisorBadge.textContent = badge;
    }

    function renderConfig(config) {
      const signature = JSON.stringify(config);
      if (signature === lastConfigSignature) return;
      lastConfigSignature = signature;
      dom.configForm.innerHTML = Object.entries(groups).map(([title, keys]) => `
        <div class="config-group">
          <h3>${title}</h3>
          <div class="config-grid">
            ${keys.map((key) => `
              <label>
                <span class="mini-label mono">${formatKey(key)}</span>
                <input name="${key}" value="${config[key] ?? ""}">
              </label>
            `).join("")}
          </div>
        </div>
      `).join("");
      dom.configForm.onsubmit = async (event) => {
        event.preventDefault();
        const payload = {};
        for (const key of editable) payload[key] = dom.configForm.elements[key].value;
        try {
          await fetchJson("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });
          dom.saveMessage.textContent = "Saved. Restart the controller to apply immediately.";
          pushActivity("Config", "Control rails were written to .env.");
          lastConfigSignature = "";
          await refresh();
        } catch (error) {
          dom.saveMessage.textContent = error.message;
        }
      };
    }

    function renderInfoRows(state, status, config) {
      const best = status.learning?.best_stable;
      const health = status.health || {};
      const metrics = status.metrics || {};
      const guardrails = status.guardrails || {};
      const rows = [
        ["Voltage", `${state.voltage_mv ?? "-"} mV`],
        ["Fan", `${state.fan_percent ?? "-"}%`],
        ["Input Voltage", `${state.input_voltage_mv ?? "-"} mV`],
        ["Mode", `${status.config?.mode ?? "-"}`],
        ["Auto Fan", prettyBool(config.BITAXE_AUTO_FAN)],
        ["Dry Run", prettyBool(status.config?.dry_run)],
        ["Error Limit", `${status.config?.max_error_percentage ?? "-"}%`],
        ["Domain Spread Limit", `${status.config?.max_domain_spread_percentage ?? "-"}%`],
        ["Climb Power Gate", status.climb_power_gate_w ? `${status.climb_power_gate_w.toFixed(2)} W` : "-"],
        ["Learning", prettyBool(status.config?.learning_enabled)],
        ["Best Learned", best ? `${best.frequency_mhz} MHz / ${best.voltage_mv} mV / ${best.best_hashrate_gh.toFixed(1)} GH/s` : "none yet"],
        ["Efficiency", status.efficiency_gh_per_w ? `${status.efficiency_gh_per_w.toFixed(2)} GH/W` : "-"],
        ["Score", status.performance_score ? `${status.performance_score.toFixed(2)}` : "-"],
        ["Score Penalty", status.performance_metrics?.total_penalty ? `${status.performance_metrics.total_penalty.toFixed(2)}` : "0.00"],
        ["Can Climb", guardrails.can_climb === undefined ? "-" : prettyBool(guardrails.can_climb)],
        ["Power Gate", guardrails.can_climb_by_power === undefined ? "-" : prettyBool(guardrails.can_climb_by_power)],
        ["Health", health.status || (status.last_error ? "degraded" : "healthy")],
        ["Decisions", metrics.total_decisions ?? "-"],
        ["Error Rate", metrics.error_rate === undefined ? "-" : `${(Number(metrics.error_rate) * 100).toFixed(2)}%`],
        ["Active Cooldown", `${status.active_cooldown_seconds ?? status.config?.step_cooldown_seconds ?? "-"} s`],
        ["Cooldown", `${status.config?.step_cooldown_seconds ?? "-"} s`],
        ["Last Error", `${status.last_error || "none"}`]
      ];
      dom.details.innerHTML = rows.map(([label, value]) => `
        <div class="info-row">
          <span class="mini-label">${label}</span>
          <strong>${value}</strong>
        </div>
      `).join("");
    }

    function applyLiveText(node, value) {
      if (node.textContent === value) return;
      node.textContent = value;
      node.classList.remove("updated");
      void node.offsetWidth;
      node.classList.add("updated");
      setTimeout(() => node.classList.remove("updated"), 220);
    }

    async function applyPreset(name) {
      const preset = presets[name];
      if (!preset) return;
      setActionMessage(`Applying ${name} preset...`);
      try {
        await fetchJson("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(preset)
        });
        setActionMessage(`${name} preset saved. Restart the controller to apply immediately.`);
        pushActivity("Preset", `${name} preset saved to the control rails.`);
        lastConfigSignature = "";
        await refresh();
      } catch (error) {
        setActionMessage(error.message, true);
      }
    }

    function setActionMessage(message, isError = false) {
      dom.actionMessage.textContent = message;
      dom.actionMessage.style.color = isError ? "var(--hot)" : "var(--soft)";
    }

    function scheduleRefresh() {
      if (refreshTimer) clearInterval(refreshTimer);
      if (!refreshPaused) refreshTimer = setInterval(refresh, refreshIntervalMs);
    }

    async function refresh() {
      let status;
      let config;
      let swarm;
      try {
        [status, config, swarm] = await Promise.all([fetchJson("/api/status"), fetchJson("/api/config"), fetchJson("/api/swarm")]);
      } catch (error) {
        reconnectAttempts += 1;
        dom.health.className = "status-pill hot";
        dom.health.innerHTML = `<span class="pulse"></span><span>Connection Lost</span>`;
        dom.updatedAt.textContent = `Retrying dashboard connection (${reconnectAttempts})`;
        setActionMessage("Lost connection to the UI server. Retrying...", true);
        return;
      }
      if (dom.actionMessage.textContent.startsWith("Lost connection")) {
        setActionMessage("Dashboard connection restored.");
      }
      const state = status.state || {};
      const decision = status.last_decision || {};
      const expected = Number(state.raw?.expectedHashrate) || 0;
      const ratio = expected > 0 ? ((Number(state.hashrate_gh) || 0) / expected) * 100 : 0;
      const health = healthState(Number(state.temperature_c) || 0, Number(status.config?.target_temp_c) || 60, Number(status.config?.emergency_temp_c) || 68, status.last_error);
      const domainGuard = getDomainGuardState(state, status);
      const thermalRatio = (Number(state.temperature_c) || 0) && status.config?.emergency_temp_c ? ((Number(state.temperature_c) || 0) / Number(status.config.emergency_temp_c)) * 100 : 0;
      const powerRatio = (Number(state.power_w) || 0) && status.config?.max_power_w ? ((Number(state.power_w) || 0) / Number(status.config.max_power_w)) * 100 : 0;
      const thermalVariant = thermalRatio >= 100 ? "hot" : thermalRatio >= 85 ? "warn" : "";
      const powerVariant = powerRatio >= 100 ? "hot" : powerRatio >= 90 ? "warn" : "";

      addHistoryPoint(state, status);
      renderHistoryChart();
      renderOverview(state, status);
      renderDomains(state);
      renderSwarm(swarm);
      renderPresetStatus(config);
      renderProfileAdvisor(state, status);
      renderEfficiencyPanel(state, status);
      renderConfig(config);
      renderInfoRows(state, status, config);

      dom.health.className = health.className;
      dom.health.innerHTML = `<span class="pulse"></span><span>${health.label}</span>`;
      dom.updatedAt.textContent = status.updated_at || "Awaiting status";
      dom.updatedChip.textContent = `Updated: ${status.updated_at || "-"}`;
      dom.modeChip.textContent = `Mode: ${status.config?.mode || "-"}`;
      dom.modeStripChip.textContent = `Mode: ${status.config?.mode || "-"}`;
      dom.dryRunChip.textContent = `Dry Run: ${prettyBool(status.config?.dry_run)}`;
      dom.fanChip.textContent = `Fan: ${prettyBool(config.BITAXE_AUTO_FAN)} / ${state.fan_percent ?? "-"}%`;
      dom.fanStripChip.textContent = `Fan: ${prettyBool(config.BITAXE_AUTO_FAN)} / ${state.fan_percent ?? "-"}%`;
      dom.stabilityChip.textContent = `Stability: ${ratio ? ratio.toFixed(1) : "-"}% expected`;
      dom.domainGuardChip.className = domainGuard.className;
      dom.domainGuardChip.textContent = `Domain Guard: ${domainGuard.label}`;
      dom.heroText.textContent = `Miner ${config.BITAXE_URL || "-"} is running at ${state.frequency_mhz ?? "-"} MHz, ${state.voltage_mv ?? "-"} mV, ${state.temperature_c?.toFixed?.(1) ?? "-"}C, and ${state.hashrate_gh?.toFixed?.(1) ?? "-"} GH/s on the 1-minute window.`;
      dom.decisionReason.textContent = friendlyDecisionTitle(decision.reason);
      dom.decisionPatch.innerHTML = friendlyPatch(decision.patch);
      dom.decisionHint.textContent = explainTuning(state, status);
      dom.decision.textContent = JSON.stringify(decision, null, 2);
      dom.raw.textContent = JSON.stringify(status, null, 2);
      dom.thermalLabel.textContent = `${state.temperature_c?.toFixed?.(1) ?? "-"}C / ${status.config?.emergency_temp_c ?? "-"}C`;
      dom.powerLabel.textContent = `${state.power_w?.toFixed?.(2) ?? "-"}W / ${status.config?.max_power_w ?? "-"}W`;
      dom.thermalHint.textContent = `Target ${status.config?.target_temp_c ?? "-"}C. Hot ${status.config?.hot_temp_c ?? "-"}C. Emergency ${status.config?.emergency_temp_c ?? "-"}C.`;
      dom.powerHint.textContent = `Climb gate is 90% of cap: ${((Number(status.config?.max_power_w) || 0) * 0.9).toFixed(2)}W.`;
      dom.tuningLabel.textContent = decision.reason || "Hold";
      dom.nextStepHint.textContent = explainTuning(state, status);
      setBar(dom.thermalBar, thermalRatio, thermalVariant);
      setBar(dom.powerBar, powerRatio, powerVariant);

      const nextStepEpoch = status.next_change_at_epoch;
      if (nextStepEpoch) {
        const remaining = nextStepEpoch - (Date.now() / 1000);
        dom.nextStepCountdown.textContent = remaining > 0 ? formatSeconds(remaining) : "Ready now";
        dom.nextStepAt.textContent = `Next change allowed after ${new Date(nextStepEpoch * 1000).toLocaleTimeString()}`;
      } else {
        dom.nextStepCountdown.textContent = "Ready now";
        dom.nextStepAt.textContent = "No recent frequency or voltage change is blocking the next step.";
      }

      const bestDiff = Number(state.raw?.bestDiff) || 0;
      const bestSessionDiff = Number(state.raw?.bestSessionDiff) || 0;
      const networkDifficulty = Number(state.raw?.networkDifficulty) || 0;
      const uptimeSeconds = Number(state.raw?.uptimeSeconds) || 0;
      const oddsHashrate = Number(state.hashrate_10m_gh) || Number(state.hashrate_gh) || 0;
      const expectedBlockSeconds = oddsHashrate && networkDifficulty ? (networkDifficulty * 4294967296) / (oddsHashrate * 1e9) : 0;
      const statusAgeSeconds = status.updated_at ? Math.max(0, (Date.now() - Date.parse(status.updated_at)) / 1000) : null;
      const healthInfo = status.health || {};
      const metricsInfo = status.metrics || {};
      const guardrailsInfo = status.guardrails || {};
      const allTimePercent = networkDifficulty > 0 ? (bestDiff / networkDifficulty) * 100 : 0;
      applyLiveText(dom.errorValue, `${state.error_percentage?.toFixed?.(2) ?? "-"}%`);
      applyLiveText(dom.expectedValue, `${expected ? expected.toFixed(1) : "-"} GH/s`);
      applyLiveText(dom.bestDiffValue, `bestDiff ${formatCompactNumber(bestDiff)}`);
      dom.bestDiffSubvalue.innerHTML = `bestSessionDiff ${formatCompactNumber(bestSessionDiff)} (${formatSeconds(uptimeSeconds)})<br>all-time progress ${formatPercent(allTimePercent)}`;
      applyLiveText(dom.soloOddsValue, networkDifficulty && oddsHashrate ? formatOdds(blockOdds(oddsHashrate, networkDifficulty, 86400)) : "-");
      dom.soloOddsSubvalue.textContent = expectedBlockSeconds ? `per day / ${formatOdds(blockOdds(oddsHashrate, networkDifficulty, 31536000))} per year / avg ${formatSeconds(expectedBlockSeconds)}` : "Waiting for difficulty and hashrate.";
      applyLiveText(dom.responseValue, `${state.raw?.responseTime?.toFixed?.(1) ?? "-"} ms`);
      applyLiveText(dom.statusFreshnessValue, statusAgeSeconds === null ? "-" : formatSeconds(statusAgeSeconds));
      dom.statusFreshnessSubvalue.textContent = statusAgeSeconds === null ? "No status timestamp yet." : (statusAgeSeconds > 120 ? "Status is stale. Check controller service." : "Status stream is fresh.");
      applyLiveText(dom.advancedHealthValue, healthInfo.status || (status.last_error ? "degraded" : "healthy"));
      dom.advancedHealthSubvalue.textContent = `actions ${healthInfo.successful_actions ?? "-"} / uptime ${formatSeconds(healthInfo.uptime_seconds || 0)}`;
      applyLiveText(dom.climbValue, guardrailsInfo.can_climb === undefined ? "-" : (guardrailsInfo.can_climb ? "Allowed" : "Blocked"));
      dom.climbSubvalue.textContent = `power ${guardrailsInfo.can_climb_by_power === undefined ? "-" : (guardrailsInfo.can_climb_by_power ? "ok" : "blocked")} / gate ${(status.climb_power_gate_w ?? guardrailsInfo.climb_power_gate_w ?? 0).toFixed?.(2) ?? "-"}W`;
      applyLiveText(dom.decisionCountValue, `${metricsInfo.total_decisions ?? "-"}`);
      dom.decisionCountSubvalue.textContent = `errors ${metricsInfo.error_count ?? 0} / avg latency ${(Number(metricsInfo.avg_api_latency) || 0).toFixed(2)}s`;
      applyLiveText(dom.guardrailValue, formatRatio(guardrailsInfo.power_ratio));
      dom.guardrailSubvalue.textContent = `domain ${formatRatio(guardrailsInfo.domain_spread_ratio)} / error ${formatRatio(guardrailsInfo.error_ratio)}`;
    }

    function setupObservers() {
      if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver((entries) => {
          entries.forEach((entry) => {
            if (entry.target.id === "historyChart" && entry.isIntersecting) {
              chartVisible = true;
              renderHistoryChart();
            }
            if (entry.isIntersecting) {
              document.querySelectorAll("[data-nav]").forEach((link) => {
                link.classList.toggle("active", link.dataset.nav === entry.target.id);
              });
            }
          });
        }, { threshold: 0.2 });
        document.querySelectorAll(".section-card").forEach((section) => observer.observe(section));
        observer.observe(dom.historyChart);
      } else {
        chartVisible = true;
      }
    }

    function setupSearch() {
      dom.search.addEventListener("input", () => {
        const query = dom.search.value.trim().toLowerCase();
        document.querySelectorAll(".section-card").forEach((section) => {
          const text = section.textContent.toLowerCase();
          section.classList.toggle("hidden", query && !text.includes(query));
        });
      });
    }

    document.getElementById("restartControllerBtn").onclick = async () => {
      setActionMessage("Restarting controller...");
      try {
        await postAction("restart-controller");
        setActionMessage("Controller restart requested.");
        pushActivity("Controller", "Controller restart requested from the dashboard.");
      } catch (error) {
        setActionMessage(error.message, true);
      }
    };

    document.getElementById("restartMinerBtn").onclick = async () => {
      setActionMessage("Restarting miner...");
      try {
        await postAction("restart-miner");
        setActionMessage("Miner restart requested. The Bitaxe may be unavailable briefly.");
        pushActivity("Miner", "Miner reboot requested from the dashboard.");
      } catch (error) {
        setActionMessage(error.message, true);
      }
    };

    document.getElementById("applySafeBtn").onclick = () => applyPreset("cool");

    document.getElementById("checkUpdatesBtn").onclick = async () => {
      dom.updateStatus.textContent = "Checking GitHub...";
      dom.updateDetails.textContent = "Fetching upstream commit metadata.";
      try {
        const update = await fetchJson("/api/update-check", {}, 0);
        renderUpdateStatus(update);
        pushActivity("Updates", update.message || "Update check finished.");
      } catch (error) {
        dom.updateStrip.className = "update-strip warn";
        dom.updateStatus.textContent = "Update check failed";
        dom.updateDetails.textContent = error.message;
      }
    };

    document.getElementById("esp32RefreshBtn").onclick = refreshEsp32Status;
    document.getElementById("nerdminerRefreshConfigBtn").onclick = refreshNerdminerConfig;
    document.getElementById("installNerdminerApiPatchBtn").onclick = async () => {
      dom.nerdminerConfigMessage.textContent = "Installing config API patch into the NerdMiner_v2 workspace...";
      try {
        const result = await fetchJson("/api/esp32/api-patch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}"
        }, 0);
        dom.nerdminerConfigMessage.textContent = result.message || "Firmware API patch installed. Rebuild and flash NerdMiner_v2 next.";
        pushActivity("NerdMiner", "Config API patch installed into the local NerdMiner_v2 workspace.");
        refreshEsp32Status();
      } catch (error) {
        dom.nerdminerConfigMessage.textContent = `Patch failed: ${error.message}`;
      }
    };
    document.getElementById("refreshLogsBtn").onclick = refreshLogs;
    dom.logServiceSelect.onchange = refreshLogs;
    dom.serialLogPortSelect.onchange = () => {
      if (dom.logServiceSelect.value === "nerdminer") refreshLogs();
    };

    dom.nerdminerConfigForm.onsubmit = async (event) => {
      event.preventDefault();
      dom.nerdminerConfigMessage.textContent = "Saving NerdMiner provisioning settings...";
      try {
        const result = await fetchJson("/api/nerdminer/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(collectNerdminerConfig())
        }, 0);
        renderNerdminerConfig(result);
        dom.nerdminerConfigMessage.textContent = result.apply_hint || "Saved locally.";
        pushActivity("NerdMiner", "Pool, Wi-Fi, and wallet settings were saved locally.");
      } catch (error) {
        dom.nerdminerConfigMessage.textContent = `Save failed: ${error.message}`;
      }
    };

    document.getElementById("buildNerdminerFirmwareDefaultsBtn").onclick = async () => {
      const values = collectNerdminerConfig();
      if (!values.SSID) {
        dom.nerdminerConfigMessage.textContent = "Enter the Wi-Fi name before building it into firmware.";
        return;
      }
      dom.nerdminerConfigMessage.textContent = "Writing private defaults and config API patch into the NerdMiner_v2 firmware workspace...";
      try {
        const result = await fetchJson("/api/nerdminer/firmware-defaults", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(values)
        }, 0);
        dom.nerdminerConfigMessage.textContent = result.message || "Firmware defaults written. Rebuild and flash NerdMiner_v2 once.";
        pushActivity("NerdMiner", "Firmware defaults were written into the local NerdMiner_v2 workspace.");
        refreshEsp32Status();
      } catch (error) {
        dom.nerdminerConfigMessage.textContent = `Firmware config build failed: ${error.message}`;
      }
    };

    document.getElementById("applyNerdminerLiveConfigBtn").onclick = async () => {
      dom.nerdminerConfigMessage.textContent = "Sending settings to patched NerdMiner firmware...";
      try {
        const result = await fetchJson("/api/nerdminer/apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(collectNerdminerConfig())
        }, 0);
        dom.nerdminerConfigMessage.textContent = result.message || "Config sent to patched NerdMiner firmware.";
        pushActivity("NerdMiner", `Config sent to ${result.url || "NerdMiner"}.`);
      } catch (error) {
        dom.nerdminerConfigMessage.textContent = `Live apply failed: ${error.message}`;
      }
    };

    document.getElementById("copyNerdminerConfigBtn").onclick = async () => {
      const values = collectNerdminerConfig();
      if (!values.WifiPW && lastNerdminerConfig?.has_wifi_password) {
        dom.nerdminerConfigMessage.textContent = "Enter the Wi-Fi password before copying; hidden saved passwords are not exposed in the browser.";
        return;
      }
      if (!values.PoolPassword && lastNerdminerConfig?.has_pool_password) {
        dom.nerdminerConfigMessage.textContent = "Enter the pool password before copying; hidden saved passwords are not exposed in the browser.";
        return;
      }
      values.PoolPort = Number(values.PoolPort) || 21496;
      values.Timezone = Number(values.Timezone) || 2;
      delete values.DeviceUrl;
      try {
        await navigator.clipboard.writeText(JSON.stringify(values, null, 2));
        dom.nerdminerConfigMessage.textContent = "SD-card config JSON copied. Save it as /config.json on the card for stock NerdMiner_v2.";
      } catch (error) {
        dom.nerdminerConfigMessage.textContent = "Clipboard copy failed.";
      }
    };

    dom.swarmAddForm.onsubmit = async (event) => {
      event.preventDefault();
      const form = new FormData(dom.swarmAddForm);
      const payload = Object.fromEntries(form.entries());
      dom.discoveryNotice.classList.remove("hidden");
      dom.discoveryNotice.textContent = "Adding miner to swarm.json...";
      try {
        const result = await fetchJson("/api/swarm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }, 0);
        dom.discoveryNotice.textContent = `Added ${result.miner?.name || "miner"}. The dashboard will use a local status file when available, or a live probe for ESP32/NerdMiner devices.`;
        dom.swarmAddForm.reset();
        pushActivity("Swarm", `Added ${result.miner?.url || payload.url} to swarm configuration.`);
        refresh();
      } catch (error) {
        dom.discoveryNotice.textContent = `Add failed: ${error.message}`;
      }
    };

    document.getElementById("rescanNetworkBtn").onclick = async () => {
      dom.discoveryNotice.classList.remove("hidden");
      dom.discoveryNotice.textContent = "Scanning local /24 subnet for Bitaxe devices...";
      try {
        const result = await fetchJson("/api/discover", {}, 0);
        const devices = result.devices || [];
        dom.discoveryNotice.innerHTML = devices.length
          ? devices.map((device) => `<button type="button" class="discovered-device" data-url="${device.url}" data-name="${device.name}">${device.name} <span>${device.url}${device.registered ? " / registered" : ""}</span></button>`).join("")
          : (result.message || "No new devices found.");
        pushActivity("Discovery", result.message || "Network scan finished.");
      } catch (error) {
        dom.discoveryNotice.textContent = `Discovery failed: ${error.message}`;
      }
    };

    dom.discoveryNotice.onclick = (event) => {
      const button = event.target.closest(".discovered-device");
      if (!button) return;
      dom.swarmAddForm.elements.name.value = button.dataset.name || "";
      dom.swarmAddForm.elements.url.value = button.dataset.url || "";
    };

    dom.swarmGrid.onclick = (event) => {
      const removeButton = event.target.closest(".remove-miner");
      if (removeButton) {
        const name = removeButton.dataset.minerName || removeButton.dataset.minerId;
        if (!confirm(`Remove ${name} from the fleet?`)) return;
        fetchJson("/api/swarm/remove", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: removeButton.dataset.minerId })
        }, 0).then(() => {
          pushActivity("Swarm", `${name} removed from swarm configuration.`);
          refresh();
        }).catch((error) => {
          setActionMessage(`Remove failed: ${error.message}`, true);
        });
        return;
      }
      if (event.target.closest(".reconnect-miner")) {
        pushActivity("Swarm", "Reconnect requested; refreshing fleet status now.");
        refresh();
      }
    };

    dom.showHashrateToggle.onchange = renderHistoryChart;
    dom.showTempToggle.onchange = renderHistoryChart;
    dom.showPowerToggle.onchange = renderHistoryChart;
    dom.historyChart.addEventListener("mousemove", renderChartTooltip);
    dom.historyChart.addEventListener("mouseleave", () => dom.chartTooltip.classList.add("hidden"));
    [dom.energyCostInput, dom.targetEfficiencyInput, dom.efficiencyUnitSelect].forEach((control) => {
      control.onchange = () => {
        saveEfficiencySettings();
        refresh();
      };
    });

    document.querySelectorAll("[data-preset]").forEach((button) => {
      button.onclick = () => applyPreset(button.dataset.preset);
    });

    dom.refreshSelect.onchange = (event) => {
      refreshIntervalMs = Number(event.target.value);
      scheduleRefresh();
      pushActivity("Refresh", `Auto-refresh set to ${refreshIntervalMs / 1000}s.`);
    };

    dom.pauseRefreshBtn.onclick = () => {
      refreshPaused = !refreshPaused;
      dom.pauseRefreshBtn.textContent = refreshPaused ? "Resume Refresh" : "Pause Refresh";
      scheduleRefresh();
      pushActivity("Refresh", refreshPaused ? "Live refresh paused." : "Live refresh resumed.");
    };

    document.getElementById("copyStatusBtn").onclick = async () => {
      try {
        await navigator.clipboard.writeText(dom.raw.textContent);
        setActionMessage("Status JSON copied to clipboard.");
      } catch (error) {
        setActionMessage("Clipboard copy failed.", true);
      }
    };

    setupObservers();
    setupSearch();
    restoreEfficiencySettings();
    refreshEsp32Status();
    refreshNerdminerConfig();
    refreshLogs();
    refresh();
    scheduleRefresh();
