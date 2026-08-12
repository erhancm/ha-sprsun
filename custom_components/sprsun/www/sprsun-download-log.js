/**
 * Lovelace card: one-click download of the SPRSUN live log to the user's PC.
 * Type: custom:sprsun-download-log-card
 */
class SprsunDownloadLogCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) {
      this._built = true;
      this._build();
    }
  }

  _build() {
    const name = this._config.name || "Save to PC";
    const icon = this._config.icon || "mdi:download";

    const card = document.createElement("ha-card");
    card.style.cssText =
      "cursor:pointer;text-align:center;padding:12px 8px;height:100%;box-sizing:border-box;";

    const ic = document.createElement("ha-icon");
    ic.setAttribute("icon", icon);
    ic.style.cssText = "display:block;margin:0 auto 4px;--mdc-icon-size:24px;";

    const label = document.createElement("div");
    label.textContent = name;
    label.style.cssText = "font-size:14px;line-height:1.2;";

    card.appendChild(ic);
    card.appendChild(label);
    card.addEventListener("click", () => this._download());
    this.appendChild(card);
  }

  async _download() {
    if (!this._hass || this._busy) return;
    this._busy = true;
    try {
      const resp = await this._hass.fetchWithAuth("/api/sprsun/live_log");
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const blob = await resp.blob();
      const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
      const filename = `sprsun_live_${stamp}.log`;

      // Chromium: real Save As picker. Fallback: browser download.
      if (typeof window.showSaveFilePicker === "function") {
        try {
          const handle = await window.showSaveFilePicker({
            suggestedName: filename,
            types: [
              {
                description: "Log file",
                accept: { "text/plain": [".log", ".txt"] },
              },
            ],
          });
          const writable = await handle.createWritable();
          await writable.write(blob);
          await writable.close();
          return;
        } catch (pickerErr) {
          if (pickerErr && pickerErr.name === "AbortError") {
            return; // user cancelled
          }
          // Fall through to anchor download
        }
      }

      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("SPRSUN log download failed", err);
      // eslint-disable-next-line no-alert
      alert(`Could not download live log: ${err.message || err}`);
    } finally {
      this._busy = false;
    }
  }

  getCardSize() {
    return 1;
  }

  static getStubConfig() {
    return { name: "Save to PC", icon: "mdi:download" };
  }
}

if (!customElements.get("sprsun-download-log-card")) {
  customElements.define("sprsun-download-log-card", SprsunDownloadLogCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "sprsun-download-log-card")) {
  window.customCards.push({
    type: "sprsun-download-log-card",
    name: "SPRSUN Save Live Log",
    description: "Download the SPRSUN in-memory live log to your PC",
  });
}