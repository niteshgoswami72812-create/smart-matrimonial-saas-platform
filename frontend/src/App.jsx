
import { useState } from "react";
import api from "./api";

function App() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [loading, setLoading] = useState(false);

  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState("");
  const [profileLoading, setProfileLoading] = useState(false);

  // Login using Django JWT API
  const handleLogin = async (e) => {
    e.preventDefault();
    setMessage("");
    setLoading(true);
    setProfile(null);
    setProfileError("");

    try {
      const response = await api.post("/api/token/", {
        username,
        password,
      });

      localStorage.setItem("access_token", response.data.access);
      localStorage.setItem("refresh_token", response.data.refresh);

      setLoggedIn(true);
      setMessage("Login successful!");
    } catch (error) {
      if (error.response?.status === 401) {
        setMessage("Invalid username or password.");
      } else {
        setMessage(
          "Login failed. Please check whether Django server is running."
        );
      }
    } finally {
      setLoading(false);
    }
  };

  // Load authenticated user's profile
  const handleGetProfile = async () => {
    setProfileError("");
    setProfileLoading(true);

    try {
      const response = await api.get("/api/profiles/me/");
      setProfile(response.data);
    } catch (error) {
      setProfile(null);

      if (error.response?.status === 401) {
        setProfileError("Session expired. Please log in again.");
      } else {
        setProfileError(
          "Unable to load profile. Please check the backend server."
        );
      }
    } finally {
      setProfileLoading(false);
    }
  };

  // Logout
  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");

    setLoggedIn(false);
    setPassword("");
    setProfile(null);
    setProfileError("");
    setMessage("Logged out successfully.");
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>Smart Matrimonial</h1>

        <p style={styles.subtitle}>
          Find your perfect match
        </p>

        {loggedIn ? (
          <div>
            <h2 style={styles.heading}>
              Login Successful 🎉
            </h2>

            <p style={styles.welcome}>
              Welcome, {username}!
            </p>

            <button
              style={styles.button}
              onClick={handleGetProfile}
              disabled={profileLoading}
            >
              {profileLoading ? "Loading..." : "Load My Profile"}
            </button>

            {profileError && (
              <p style={styles.error} role="alert">
                {profileError}
              </p>
            )}

            {profile && (
              <div style={styles.profileBox}>
                <h3 style={styles.profileTitle}>My Profile</h3>

                <p>
                  <strong>Username:</strong> {profile.username}
                </p>

                <p>
                  <strong>User ID:</strong> {profile.user_id}
                </p>

                <p style={styles.success}>
                  {profile.message}
                </p>
              </div>
            )}

            <button
              style={styles.logoutButton}
              onClick={handleLogout}
            >
              Logout
            </button>
          </div>
        ) : (
          <form onSubmit={handleLogin}>
            <label style={styles.label} htmlFor="username">
              Username
            </label>

            <input
              id="username"
              style={styles.input}
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              autoComplete="username"
              required
            />

            <label style={styles.label} htmlFor="password">
              Password
            </label>

            <input
              id="password"
              style={styles.input}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              autoComplete="current-password"
              required
            />

            <button
              style={styles.button}
              type="submit"
              disabled={loading}
            >
              {loading ? "Logging in..." : "Login"}
            </button>
          </form>
        )}

        {message && (
          <p
            role="status"
            style={
              message === "Login successful!"
                ? styles.success
                : styles.info
            }
          >
            {message}
          </p>
        )}
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    background: "#f5f6fa",
    fontFamily: "Arial, sans-serif",
    padding: "20px",
    boxSizing: "border-box",
  },

  card: {
    width: "100%",
    maxWidth: "400px",
    padding: "30px",
    background: "#ffffff",
    borderRadius: "14px",
    boxShadow: "0 8px 30px rgba(0, 0, 0, 0.08)",
    boxSizing: "border-box",
  },

  title: {
    color: "#e85d75",
    textAlign: "center",
    marginBottom: "8px",
  },

  subtitle: {
    textAlign: "center",
    color: "#666",
    marginBottom: "25px",
  },

  heading: {
    color: "#333",
    textAlign: "center",
  },

  welcome: {
    textAlign: "center",
    color: "#555",
  },

  label: {
    display: "block",
    marginBottom: "8px",
    marginTop: "15px",
    color: "#333",
  },

  input: {
    width: "100%",
    boxSizing: "border-box",
    padding: "12px",
    border: "1px solid #ddd",
    borderRadius: "7px",
    fontSize: "15px",
    outlineColor: "#e85d75",
  },

  button: {
    width: "100%",
    marginTop: "22px",
    padding: "12px",
    background: "#e85d75",
    color: "#fff",
    border: "none",
    borderRadius: "7px",
    cursor: "pointer",
    fontSize: "16px",
  },

  logoutButton: {
    width: "100%",
    marginTop: "12px",
    padding: "12px",
    background: "#333",
    color: "#fff",
    border: "none",
    borderRadius: "7px",
    cursor: "pointer",
    fontSize: "16px",
  },

  profileBox: {
    marginTop: "20px",
    padding: "15px",
    background: "#fff5f7",
    border: "1px solid #f4d2da",
    borderRadius: "8px",
    overflowWrap: "anywhere",
  },

  profileTitle: {
    color: "#e85d75",
    marginTop: "0",
  },

  success: {
    color: "#16803c",
    fontSize: "14px",
    overflowWrap: "anywhere",
  },

  error: {
    color: "#c62828",
    fontSize: "14px",
    overflowWrap: "anywhere",
  },

  info: {
    color: "#555",
    fontSize: "14px",
    overflowWrap: "anywhere",
  },
};

export default App;
