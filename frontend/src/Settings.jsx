import { useEffect, useState } from "react";
import api from "./api";
import "./Settings.css";

const DEFAULT_PREFERENCES = {
  profileVisible: true,
  showOnlineStatus: true,
  allowPrivatePhotos: true,
  emailNotifications: true,
  matchNotifications: true,
  chatNotifications: true,
};

function getAccountName(account, username) {
  return (
    account?.username ||
    account?.user?.username ||
    account?.full_name ||
    username ||
    "Member"
  );
}

function getAccountEmail(account) {
  return (
    account?.email ||
    account?.user?.email ||
    account?.user_email ||
    "Not available"
  );
}

function Settings({ username, onLogout }) {
  const storageKey = `matrimonial-settings-${username || "member"}`;

  const [account, setAccount] = useState(null);
  const [accountLoading, setAccountLoading] = useState(true);
  const [accountError, setAccountError] = useState("");

  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
  const [preferencesMessage, setPreferencesMessage] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");

  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const loadSettings = async () => {
      setAccountLoading(true);
      setAccountError("");

      try {
        const response = await api.get("/api/profiles/me/");

        if (isMounted) {
          setAccount(response.data?.profile ?? response.data);
        }
      } catch (error) {
        if (isMounted) {
          setAccount(null);
          setAccountError(
            error.response?.data?.detail ||
              error.response?.data?.error ||
              "Unable to load account details.",
          );
        }
      } finally {
        if (isMounted) {
          setAccountLoading(false);
        }
      }
    };

    loadSettings();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    try {
      const savedPreferences = localStorage.getItem(storageKey);

      if (savedPreferences) {
        const parsedPreferences = JSON.parse(savedPreferences);

        setPreferences({
          ...DEFAULT_PREFERENCES,
          ...parsedPreferences,
        });
      }
    } catch (error) {
      console.error("Unable to load saved settings:", error);
    }
  }, [storageKey]);

  const handlePreferenceChange = (event) => {
    const { name, checked } = event.target;

    setPreferences((previous) => ({
      ...previous,
      [name]: checked,
    }));

    setPreferencesMessage("");
  };

  const handleSavePreferences = (event) => {
    event.preventDefault();

    try {
      localStorage.setItem(storageKey, JSON.stringify(preferences));
      setPreferencesMessage(
        "Preferences saved in this browser successfully.",
      );
    } catch (error) {
      setPreferencesMessage(
        "Unable to save preferences in this browser.",
      );
    }
  };

  const handlePasswordSubmit = (event) => {
    event.preventDefault();

    setPasswordError("");
    setPasswordMessage("");

    if (!currentPassword || !newPassword || !confirmPassword) {
      setPasswordError("Please fill in all password fields.");
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError("New password must contain at least 8 characters.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirm password do not match.");
      return;
    }

    setPasswordError(
      "Password change is not connected yet. A backend password API is required.",
    );
  };

  const handleDeleteAccount = () => {
    setShowDeleteConfirmation(false);

    window.alert(
      "Account deletion is not connected yet. A secure backend API and confirmation flow are required.",
    );
  };

  const accountName = getAccountName(account, username);
  const accountEmail = getAccountEmail(account);

  return (
    <section className="settings-page">
      <div className="settings-intro">
        <div>
          <p className="dashboard-eyebrow">ACCOUNT PREFERENCES</p>
          <h2>Settings</h2>
          <p className="settings-subtitle">
            Manage your account information, privacy and notifications.
          </p>
        </div>

        <div className="settings-profile-icon" aria-hidden="true">
          {accountName.charAt(0).toUpperCase()}
        </div>
      </div>

      {/* ACCOUNT INFORMATION */}
      <section className="settings-card">
        <div className="settings-card-heading">
          <div className="settings-icon">♙</div>
          <div>
            <h3>Account Information</h3>
            <p>Your basic account details.</p>
          </div>
        </div>

        {accountLoading && (
          <p className="settings-info-message" role="status">
            Loading account information...
          </p>
        )}

        {accountError && (
          <div className="settings-message settings-error" role="alert">
            {accountError}
          </div>
        )}

        {!accountLoading && (
          <div className="settings-account-grid">
            <div className="settings-detail">
              <span>Username</span>
              <strong>{accountName}</strong>
            </div>

            <div className="settings-detail">
              <span>Email Address</span>
              <strong>{accountEmail}</strong>
            </div>

            <div className="settings-detail">
              <span>Account Type</span>
              <strong>Member</strong>
            </div>

            <div className="settings-detail">
              <span>Account Status</span>
              <strong className="settings-status-active">Active session</strong>
            </div>
          </div>
        )}

        <p className="settings-note">
          Account details are displayed from the available account API.
          Editing account information can be connected separately.
        </p>
      </section>

      {/* PRIVACY SETTINGS */}
      <form className="settings-card" onSubmit={handleSavePreferences}>
        <div className="settings-card-heading">
          <div className="settings-icon">♧</div>
          <div>
            <h3>Privacy Settings</h3>
            <p>Choose how other members can interact with your profile.</p>
          </div>
        </div>

        <div className="settings-options">
          <label className="settings-option">
            <span>
              <strong>Profile Visibility</strong>
              <small>Allow your profile to appear in Discover Profiles.</small>
            </span>

            <input
              type="checkbox"
              name="profileVisible"
              checked={preferences.profileVisible}
              onChange={handlePreferenceChange}
            />
          </label>

          <label className="settings-option">
            <span>
              <strong>Online Status</strong>
              <small>Allow other members to see your online status.</small>
            </span>

            <input
              type="checkbox"
              name="showOnlineStatus"
              checked={preferences.showOnlineStatus}
              onChange={handlePreferenceChange}
            />
          </label>

          <label className="settings-option">
            <span>
              <strong>Private Photo Access</strong>
              <small>
                Allow accepted matches to view your private photos.
              </small>
            </span>

            <input
              type="checkbox"
              name="allowPrivatePhotos"
              checked={preferences.allowPrivatePhotos}
              onChange={handlePreferenceChange}
            />
          </label>
        </div>

        <p className="settings-note">
          These privacy preferences are currently saved only in this browser.
          They do not change backend visibility or photo permissions yet.
        </p>

        {preferencesMessage && (
          <div className="settings-message settings-success" role="status">
            {preferencesMessage}
          </div>
        )}

        <button className="settings-primary-button" type="submit">
          Save Preferences
        </button>
      </form>

      {/* NOTIFICATION SETTINGS */}
      <form className="settings-card" onSubmit={handleSavePreferences}>
        <div className="settings-card-heading">
          <div className="settings-icon">♧</div>
          <div>
            <h3>Notification Preferences</h3>
            <p>Choose which notifications you would like to receive.</p>
          </div>
        </div>

        <div className="settings-options">
          <label className="settings-option">
            <span>
              <strong>Email Notifications</strong>
              <small>Receive important updates through email.</small>
            </span>

            <input
              type="checkbox"
              name="emailNotifications"
              checked={preferences.emailNotifications}
              onChange={handlePreferenceChange}
            />
          </label>

          <label className="settings-option">
            <span>
              <strong>Match Request Notifications</strong>
              <small>Get updates when someone sends you a match request.</small>
            </span>

            <input
              type="checkbox"
              name="matchNotifications"
              checked={preferences.matchNotifications}
              onChange={handlePreferenceChange}
            />
          </label>

          <label className="settings-option">
            <span>
              <strong>Chat Notifications</strong>
              <small>Get updates about new chat messages.</small>
            </span>

            <input
              type="checkbox"
              name="chatNotifications"
              checked={preferences.chatNotifications}
              onChange={handlePreferenceChange}
            />
          </label>
        </div>

        <p className="settings-note">
          Notification preferences are saved locally for now. Actual email
          and in-app notifications require backend integration.
        </p>

        {preferencesMessage && (
          <div className="settings-message settings-success" role="status">
            {preferencesMessage}
          </div>
        )}

        <button className="settings-primary-button" type="submit">
          Save Notifications
        </button>
      </form>

      {/* CHANGE PASSWORD */}
      <form className="settings-card" onSubmit={handlePasswordSubmit}>
        <div className="settings-card-heading">
          <div className="settings-icon">♢</div>
          <div>
            <h3>Change Password</h3>
            <p>Update your account password securely.</p>
          </div>
        </div>

        <div className="settings-password-grid">
          <label className="settings-field">
            Current Password
            <input
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              placeholder="Enter current password"
            />
          </label>

          <label className="settings-field">
            New Password
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              placeholder="Enter new password"
            />
          </label>

          <label className="settings-field">
            Confirm New Password
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              placeholder="Confirm new password"
            />
          </label>
        </div>

        {passwordError && (
          <div className="settings-message settings-error" role="alert">
            {passwordError}
          </div>
        )}

        {passwordMessage && (
          <div className="settings-message settings-success" role="status">
            {passwordMessage}
          </div>
        )}

        <p className="settings-note">
          Password updates are not active yet. Do not enter a real password
          until the backend password-change API is connected.
        </p>

        <button className="settings-primary-button" type="submit">
          Update Password
        </button>
      </form>

      {/* DANGER ZONE */}
      <section className="settings-card settings-danger-card">
        <div className="settings-card-heading">
          <div className="settings-icon settings-danger-icon">!</div>
          <div>
            <h3>Danger Zone</h3>
            <p>Account actions that need extra care.</p>
          </div>
        </div>

        <div className="settings-danger-content">
          <div>
            <strong>Delete Account</strong>
            <p>
              Permanently deleting an account should remove its data after
              secure confirmation.
            </p>
          </div>

          <button
            className="settings-delete-button"
            type="button"
            onClick={() => setShowDeleteConfirmation(true)}
          >
            Delete Account
          </button>
        </div>

        <p className="settings-note">
          Account deletion is not active. A backend endpoint and secure
          confirmation process must be implemented first.
        </p>
      </section>

      {/* LOGOUT */}
      <section className="settings-logout-card">
        <div>
          <h3>Sign out</h3>
          <p>Log out of your Smart Matrimonial account on this device.</p>
        </div>

        <button
          className="settings-logout-button"
          type="button"
          onClick={onLogout}
        >
          Logout
        </button>
      </section>

      {/* DELETE CONFIRMATION MODAL */}
      {showDeleteConfirmation && (
        <div
          className="settings-modal-overlay"
          role="presentation"
          onClick={() => setShowDeleteConfirmation(false)}
        >
          <section
            className="settings-confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-account-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="settings-confirm-icon">!</div>

            <h3 id="delete-account-title">Delete Account?</h3>

            <p>
              Account deletion is not connected yet. No account data will be
              deleted by this prototype.
            </p>

            <div className="settings-confirm-actions">
              <button
                className="settings-cancel-button"
                type="button"
                onClick={() => setShowDeleteConfirmation(false)}
              >
                Cancel
              </button>

              <button
                className="settings-delete-button"
                type="button"
                onClick={handleDeleteAccount}
              >
                Continue
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

export default Settings;