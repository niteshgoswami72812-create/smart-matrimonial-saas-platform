import "./ThemeSettings.css";

function ThemeSettings({ theme = "light", onThemeChange }) {
  const activeTheme = theme === "dark" ? "dark" : "light";

  return (
    <section
      className="theme-settings-card"
      aria-labelledby="theme-settings-title"
    >
      <div className="theme-settings-heading">
        <div>
          <p className="theme-settings-eyebrow">APPEARANCE</p>
          <h2 id="theme-settings-title">Display Theme</h2>
          <p>Choose the appearance you prefer for your dashboard.</p>
        </div>
        <span className="theme-settings-current">
          {activeTheme === "dark" ? "Dark mode" : "Light mode"}
        </span>
      </div>

      <div className="theme-settings-options" role="group" aria-label="Choose display theme">
        <button
          className={`theme-settings-option ${activeTheme === "light" ? "active" : ""}`}
          type="button"
          aria-pressed={activeTheme === "light"}
          disabled={!onThemeChange}
          onClick={() => onThemeChange?.("light")}
        >
          <span className="theme-preview theme-preview-light" aria-hidden="true">
            <span />
          </span>
          <span className="theme-settings-option-label">Light</span>
          <span className="theme-settings-check" aria-hidden="true">
            {activeTheme === "light" ? "✓" : ""}
          </span>
        </button>

        <button
          className={`theme-settings-option ${activeTheme === "dark" ? "active" : ""}`}
          type="button"
          aria-pressed={activeTheme === "dark"}
          disabled={!onThemeChange}
          onClick={() => onThemeChange?.("dark")}
        >
          <span className="theme-preview theme-preview-dark" aria-hidden="true">
            <span />
          </span>
          <span className="theme-settings-option-label">Dark</span>
          <span className="theme-settings-check" aria-hidden="true">
            {activeTheme === "dark" ? "✓" : ""}
          </span>
        </button>
      </div>

      <p className="theme-settings-help">
        Your choice is saved in this browser and applies to the dashboard.
      </p>
    </section>
  );
}

export default ThemeSettings;
