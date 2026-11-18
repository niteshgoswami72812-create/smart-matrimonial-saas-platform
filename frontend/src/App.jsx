
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "./api";
import "./App.css";
import Dashboard from "./Dashboard";
import AIChatbot from "./AIChatbot";

const emptyProfile = {
  full_name: "",
  date_of_birth: "",
  gender: "",
  city: "",
  education: "",
  profession: "",
  about_me: "",
};

const initialSignupData = {
  username: "",
  email: "",
  password: "",
  tenant_slug: "second-matrimony",
};

function App() {
  const [screen, setScreen] = useState(() =>
    localStorage.getItem("access_token") ||
    localStorage.getItem("refresh_token")
      ? "checking"
      : "login",
  );

  const [username, setUsername] = useState(
    () => localStorage.getItem("username") || "",
  );

  // User role for role-based Dashboard features
  const [userRole, setUserRole] = useState("");

  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("error");
  const [loading, setLoading] = useState(false);

  const [signupData, setSignupData] = useState(initialSignupData);
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);

  const [profileForm, setProfileForm] = useState(emptyProfile);

  // Application-wide Dark / Light Theme
  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem("app_theme");
    return savedTheme === "dark" ? "dark" : "light";
  });

  // Apply theme globally and save preference
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("app_theme", theme);
  }, [theme]);

  const showMessage = (text, type = "error") => {
    setMessage(text);
    setMessageType(type);
  };

  // Verify account, get role and check whether matrimonial profile exists.
  const checkProfileAndRoute = async (fallbackUsername = "") => {
    const accountResponse = await api.get("/api/profiles/me/");
    const account = accountResponse.data?.profile ?? accountResponse.data;

    // Read the logged-in user's role from the backend
    const role = account.role ?? account.user_profile?.role ?? "";
    setUserRole(String(role).trim().toLowerCase());

    const currentUsername = account.username || fallbackUsername;

    if (currentUsername) {
      setUsername(currentUsername);
      localStorage.setItem("username", currentUsername);
    }

    try {
      await api.get("/api/profiles/me/detail/");
      setScreen("dashboard");
      setMessage("");
    } catch (error) {
      if (error.response?.status === 404) {
        setProfileForm(emptyProfile);
        setScreen("create-profile");
        setMessage("");
        return;
      }

      if (error.response?.status === 403) {
        showMessage(
          error.response.data?.detail ||
          error.response.data?.error ||
          "This account cannot access the member profile.",
        );
        setScreen("session-error");
        return;
      }

      throw error;
    }
  };

  // Restore session after page refresh.
  useEffect(() => {
    let cancelled = false;

    const restoreSession = async () => {
      const accessToken = localStorage.getItem("access_token");
      const refreshToken = localStorage.getItem("refresh_token");
      const savedUsername = localStorage.getItem("username") || "";

      if (!accessToken && !refreshToken) {
        setScreen("login");
        return;
      }

      try {
        if (accessToken) {
          try {
            await checkProfileAndRoute(savedUsername);
            return;
          } catch (error) {
            if (error.response?.status !== 401) {
              throw error;
            }
          }
        }

        if (refreshToken) {
          const response = await api.post("/api/token/refresh/", {
            refresh: refreshToken,
          });

          if (response.data.access) {
            localStorage.setItem("access_token", response.data.access);
          }

          if (response.data.refresh) {
            localStorage.setItem("refresh_token", response.data.refresh);
          }

          await checkProfileAndRoute(savedUsername);
        } else {
          throw { response: { status: 401 } };
        }
      } catch (error) {
        if (cancelled) return;

        if (error.response?.status === 401) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("username");

          setUsername("");
          setUserRole("");
          setScreen("login");
          showMessage("Your session expired. Please log in again.");
        } else {
          setScreen("session-error");
          showMessage(
            "Unable to verify your profile. Check that the Django server is running, then retry.",
          );
        }
      }
    };

    restoreSession();

    return () => {
      cancelled = true;
    };
  }, []);

  // Login.
  const handleLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    setMessage("");

    let loginSucceeded = false;

    try {
      const response = await api.post("/api/token/", {
        username,
        password,
      });

      loginSucceeded = true;

      localStorage.setItem("access_token", response.data.access);
      localStorage.setItem("refresh_token", response.data.refresh);
      localStorage.setItem("username", username);

      await checkProfileAndRoute(username);
      setPassword("");
    } catch (error) {
      if (loginSucceeded) {
        setScreen("session-error");
        showMessage(
          "Login succeeded, but the profile could not be checked. Please retry.",
        );
      } else if (error.response?.status === 401) {
        showMessage("Invalid username or password.");
      } else {
        showMessage(
          "Login failed. Please check whether the Django server is running.",
        );
      }
    } finally {
      setLoading(false);
    }
  };

  // Signup: all normal new accounts use Second Matrimony.
  const handleSignup = async (event) => {
    event.preventDefault();

    if (!acceptTerms || !acceptPrivacy) {
      showMessage("Please accept the Terms & Conditions and Privacy Policy.");
      return;
    }

    setLoading(true);
    setMessage("");

    try {
      const payload = {
        ...signupData,
        tenant_slug: "second-matrimony",
        accept_terms: acceptTerms,
        accept_privacy: acceptPrivacy,
      };

      const response = await api.post("/api/accounts/signup/", payload);

      setUsername(signupData.username);
      setPassword("");
      setSignupData(initialSignupData);

      setAcceptTerms(false);
      setAcceptPrivacy(false);

      setScreen("login");
      showMessage(
        response.data.message || "Account created. Please log in.",
        "success",
      );
    } catch (error) {
      const data = error.response?.data;

      const errorText =
        data && typeof data === "object"
          ? Object.entries(data)
              .map(
                ([field, value]) =>
                  `${field}: ${
                    Array.isArray(value) ? value.join(", ") : String(value)
                  }`,
              )
              .join(" | ")
          : "Signup failed. Please try again.";

      showMessage(errorText);
    } finally {
      setLoading(false);
    }
  };

  // Create matrimonial profile.
  const handleCreateProfile = async (event) => {
    event.preventDefault();
    setLoading(true);
    setMessage("");

    if (!profileForm.full_name.trim()) {
      showMessage("Full name is required.");
      setLoading(false);
      return;
    }

    try {
      const payload = {
        ...profileForm,
        full_name: profileForm.full_name.trim(),
        date_of_birth: profileForm.date_of_birth || null,
      };

      await api.post("/api/profiles/create/", payload);

      setScreen("dashboard");
      setProfileForm(emptyProfile);
      showMessage("Profile created successfully.", "success");
    } catch (error) {
      const data = error.response?.data;

      const errorText =
        data && typeof data === "object"
          ? Object.entries(data)
              .map(
                ([field, value]) =>
                  `${field}: ${
                    Array.isArray(value) ? value.join(", ") : String(value)
                  }`,
              )
              .join(" | ")
          : "Unable to create your profile. Please try again.";

      showMessage(errorText);
    } finally {
      setLoading(false);
    }
  };

  // Logout.
  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("username");

    setUsername("");
    setUserRole("");
    setPassword("");
    setMessage("");
    setProfileForm(emptyProfile);
    setScreen("login");
  };

  const changeProfileField = (event) => {
    const { name, value } = event.target;

    setProfileForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  if (screen === "checking") {
    return (
      <main className="auth-page">
        <section className="form-panel">
          <div className="form-container">
            <h2>Checking your account...</h2>
            <p>Please wait while we verify your profile.</p>
          </div>
        </section>
      </main>
    );
  }

  if (screen === "dashboard") {
    return (
      <>
        {message && (
          <p
            className={`notice ${
              messageType === "success"
                ? "success-notice"
                : "error-notice"
            }`}
            role="status"
          >
            {message}
          </p>
        )}

        <Dashboard
          username={username}
          userRole={userRole}
          onLogout={handleLogout}
          theme={theme}
          onThemeChange={setTheme}
        />

        <AIChatbot />
      </>
    );
  }

  const isSignup = screen === "signup";
  const isCreateProfile = screen === "create-profile";
  const isSessionError = screen === "session-error";

  return (
    <main className="auth-page">
      <section className="auth-shell">
        <aside className="welcome-panel">
          <div className="brand">
            <span className="brand-icon">♥</span>
            <span>Smart Matrimonial</span>
          </div>

          <div className="welcome-content">
            <span className="eyebrow">YOUR JOURNEY, YOUR STORY</span>

            <h1>
              Some connections
              <br />
              are <span>meant to be.</span>
            </h1>

            <p>
              Discover meaningful connections and take the next step towards a
              beautiful future with someone special.
            </p>
          </div>

          <div className="welcome-footer">
            <span>Made for meaningful relationships.</span>

            <div className="legal-footer">
              <Link to="/terms">Terms &amp; Conditions</Link>
              <span>·</span>
              <Link to="/privacy">Privacy Policy</Link>
            </div>
          </div>
        </aside>

        <section className="form-panel">
          <div className="form-container">
            <div className="mobile-brand">
              <span className="brand-icon">♥</span>
              Smart Matrimonial
            </div>

            {isSessionError ? (
              <>
                <div className="form-heading">
                  <span className="form-kicker">ACCOUNT CHECK</span>
                  <h2>We couldn't verify your profile</h2>
                  <p>Please retry or sign in again.</p>
                </div>

                {message && (
                  <p className="notice error-notice" role="alert">
                    {message}
                  </p>
                )}

                <button
                  className="primary-button"
                  type="button"
                  onClick={async () => {
                    setScreen("checking");

                    try {
                      await checkProfileAndRoute(username);
                    } catch {
                      setScreen("session-error");
                      showMessage(
                        "Profile check failed. Check the server and try again.",
                      );
                    }
                  }}
                >
                  Retry Profile Check
                </button>

                <button
                  className="profile-secondary"
                  type="button"
                  onClick={handleLogout}
                >
                  Logout
                </button>
              </>
            ) : isCreateProfile ? (
              <>
                <div className="form-heading">
                  <span className="form-kicker">ONE LAST STEP</span>
                  <h2>Create your profile</h2>
                  <p>Complete your details to start discovering matches.</p>
                </div>

                <form onSubmit={handleCreateProfile} className="login-form">
                  <div className="field-group">
                    <label htmlFor="full_name">Full Name *</label>
                    <input
                      id="full_name"
                      name="full_name"
                      type="text"
                      value={profileForm.full_name}
                      onChange={changeProfileField}
                      maxLength={150}
                      required
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="date_of_birth">Date of Birth</label>
                    <input
                      id="date_of_birth"
                      name="date_of_birth"
                      type="date"
                      max={new Date().toISOString().slice(0, 10)}
                      value={profileForm.date_of_birth}
                      onChange={changeProfileField}
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="gender">Gender</label>
                    <select
                      id="gender"
                      name="gender"
                      value={profileForm.gender}
                      onChange={changeProfileField}
                    >
                      <option value="">Select gender</option>
                      <option value="male">Male</option>
                      <option value="female">Female</option>
                      <option value="other">Other</option>
                    </select>
                  </div>

                  <div className="field-group">
                    <label htmlFor="city">City</label>
                    <input
                      id="city"
                      name="city"
                      value={profileForm.city}
                      onChange={changeProfileField}
                      maxLength={100}
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="education">Education</label>
                    <input
                      id="education"
                      name="education"
                      value={profileForm.education}
                      onChange={changeProfileField}
                      maxLength={150}
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="profession">Profession</label>
                    <input
                      id="profession"
                      name="profession"
                      value={profileForm.profession}
                      onChange={changeProfileField}
                      maxLength={150}
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="about_me">About Me</label>
                    <textarea
                      id="about_me"
                      name="about_me"
                      rows={4}
                      value={profileForm.about_me}
                      onChange={changeProfileField}
                      placeholder="Write something about yourself..."
                    />
                  </div>

                  {message && (
                    <p className="notice error-notice" role="alert">
                      {message}
                    </p>
                  )}

                  <button
                    className="primary-button"
                    type="submit"
                    disabled={loading}
                  >
                    {loading ? "Creating profile..." : "Create Profile →"}
                  </button>
                </form>

                <button
                  className="profile-secondary"
                  type="button"
                  onClick={handleLogout}
                >
                  Logout
                </button>
              </>
            ) : isSignup ? (
              <>
                <div className="form-heading">
                  <span className="form-kicker">GET STARTED</span>
                  <h2>Create your account</h2>
                  <p>Sign up to begin your matrimonial journey.</p>
                </div>

                <form onSubmit={handleSignup} className="login-form">
                  <div className="field-group">
                    <label htmlFor="signup-username">Username</label>
                    <input
                      id="signup-username"
                      value={signupData.username}
                      onChange={(event) =>
                        setSignupData({
                          ...signupData,
                          username: event.target.value,
                        })
                      }
                      autoComplete="username"
                      required
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="signup-email">Email</label>
                    <input
                      id="signup-email"
                      type="email"
                      value={signupData.email}
                      onChange={(event) =>
                        setSignupData({
                          ...signupData,
                          email: event.target.value,
                        })
                      }
                      autoComplete="email"
                      required
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="signup-password">Password</label>
                    <input
                      id="signup-password"
                      type="password"
                      value={signupData.password}
                      onChange={(event) =>
                        setSignupData({
                          ...signupData,
                          password: event.target.value,
                        })
                      }
                      autoComplete="new-password"
                      required
                    />
                  </div>

                  {/* Mandatory Terms and Privacy consent */}
                  <div className="consent-group">
                    <div className="consent-row">
                      <label htmlFor="accept-terms">
                        <input
                          id="accept-terms"
                          type="checkbox"
                          checked={acceptTerms}
                          onChange={(event) =>
                            setAcceptTerms(event.target.checked)
                          }
                          required
                        />
                        <span>I agree to the</span>
                      </label>

                      <Link to="/terms">Terms &amp; Conditions</Link>
                      <span>.</span>
                    </div>

                    <div className="consent-row">
                      <label htmlFor="accept-privacy">
                        <input
                          id="accept-privacy"
                          type="checkbox"
                          checked={acceptPrivacy}
                          onChange={(event) =>
                            setAcceptPrivacy(event.target.checked)
                          }
                          required
                        />
                        <span>I acknowledge the</span>
                      </label>

                      <Link to="/privacy">Privacy Policy</Link>
                      <span>.</span>
                    </div>
                  </div>

                  {message && (
                    <p
                      className={`notice ${
                        messageType === "success"
                          ? "success-notice"
                          : "error-notice"
                      }`}
                      role="alert"
                    >
                      {message}
                    </p>
                  )}

                  <button
                    className="primary-button"
                    type="submit"
                    disabled={loading}
                  >
                    {loading ? "Creating account..." : "Sign Up →"}
                  </button>
                </form>

                <p className="form-note">
                  Already have an account?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setMessage("");
                      setScreen("login");
                    }}
                  >
                    Sign In
                  </button>
                </p>
              </>
            ) : (
              <>
                <div className="form-heading">
                  <span className="form-kicker">WELCOME BACK</span>
                  <h2>Sign in to your account</h2>
                  <p>Enter your details to continue your journey.</p>
                </div>

                <form onSubmit={handleLogin} className="login-form">
                  <div className="field-group">
                    <label htmlFor="username">Username</label>
                    <input
                      id="username"
                      type="text"
                      value={username}
                      onChange={(event) => setUsername(event.target.value)}
                      placeholder="Enter your username"
                      autoComplete="username"
                      required
                    />
                  </div>

                  <div className="field-group">
                    <label htmlFor="password">Password</label>
                    <input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder="Enter your password"
                      autoComplete="current-password"
                      required
                    />
                  </div>

                  {message && (
                    <p
                      className={`notice ${
                        messageType === "success"
                          ? "success-notice"
                          : "error-notice"
                      }`}
                      role="alert"
                    >
                      {message}
                    </p>
                  )}

                  <button
                    className="primary-button"
                    type="submit"
                    disabled={loading}
                  >
                    {loading ? "Signing in..." : "Sign In →"}
                  </button>
                </form>

                <p className="form-note">
                  Don't have an account?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setMessage("");
                      setAcceptTerms(false);
                      setAcceptPrivacy(false);
                      setScreen("signup");
                    }}
                  >
                    Create Account
                  </button>
                </p>
              </>
            )}
          </div>
        </section>
      </section>
    </main>
  );
}

export default App;
