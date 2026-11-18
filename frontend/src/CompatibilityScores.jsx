import { useEffect, useState } from "react";
import api from "./api";
import "./CompatibilityScores.css";

function getList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  if (Array.isArray(data?.profiles)) return data.profiles;
  if (Array.isArray(data?.data)) return data.data;
  return [];
}

function getProfileId(profile) {
  return (
    profile?.id ??
    profile?.profile_id ??
    profile?.profile?.id ??
    profile?.user_profile?.id ??
    null
  );
}

function getProfileName(profile) {
  const firstName = profile?.first_name ?? "";
  const lastName = profile?.last_name ?? "";

  return (
    profile?.full_name ||
    profile?.name ||
    `${firstName} ${lastName}`.trim() ||
    profile?.user?.username ||
    profile?.username ||
    "Member"
  );
}

function getScore(data) {
  const values = [
    data?.compatibility_score,
    data?.score,
    data?.data?.compatibility_score,
    data?.data?.score,
    data?.result?.compatibility_score,
  ];

  for (const value of values) {
    if (value !== null && value !== undefined && value !== "") {
      const number = Number(value);

      if (Number.isFinite(number)) {
        return Math.max(0, Math.min(100, number));
      }
    }
  }

  return null;
}

function getScoreLabel(score) {
  if (score >= 80) return "Excellent Compatibility";
  if (score >= 60) return "Good Compatibility";
  if (score >= 40) return "Moderate Compatibility";
  return "Explore Compatibility";
}

function getFactors(data) {
  const factors =
    data?.breakdown ??
    data?.factors ??
    data?.score_breakdown ??
    data?.data?.breakdown ??
    data?.data?.factors ??
    null;

  if (!factors || typeof factors !== "object" || Array.isArray(factors)) {
    return [];
  }

  return Object.entries(factors).map(([key, value]) => {
    if (typeof value === "object" && value !== null) {
      return {
        name: key,
        value:
          value.score ?? value.percentage ?? value.value ?? value.match ?? null,
      };
    }

    return { name: key, value };
  });
}

function getExplanation(data) {
  return (
    data?.ai_match_explanation ||
    data?.match_explanation ||
    data?.explanation ||
    data?.reason ||
    data?.data?.ai_match_explanation ||
    data?.data?.explanation ||
    ""
  );
}

function formatFactorName(value) {
  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatFactorValue(value) {
  if (value === null || value === undefined || value === "") {
    return "Not provided by API";
  }

  if (typeof value === "number") {
    return `${value}%`;
  }

  return String(value);
}

function CompatibilityScores({ onExploreMatches = () => {} }) {
  const [scores, setScores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadScores = async () => {
    setLoading(true);
    setError("");

    try {
      // 1. Current user's profile.
      const myProfileResponse = await api.get("/api/profiles/me/detail/");
      const myProfile =
        myProfileResponse.data?.profile ?? myProfileResponse.data;

      const myProfileId = getProfileId(myProfile);

      if (!myProfileId) {
        throw new Error("Your profile ID could not be found.");
      }

      // 2. Load profiles available to this user.
      const profilesResponse = await api.get("/api/profiles/list/");
      const allProfiles = getList(profilesResponse.data);

      // 3. Remove the current user's own profile.
      const otherProfiles = allProfiles.filter((profile) => {
        const profileId = getProfileId(profile);

        return profileId !== null && String(profileId) !== String(myProfileId);
      });

      if (otherProfiles.length === 0) {
        setScores([]);
        return;
      }

      // 4. Calculate compatibility for each available profile.
      const results = await Promise.all(
        otherProfiles.map(async (profile) => {
          const profileId = getProfileId(profile);

          try {
            const response = await api.post(
              `/api/profiles/compatibility/${profileId}/`,
              {},
            );

            const result = response.data;

            return {
              id: profileId,
              name: getProfileName(profile),
              city: profile?.city || profile?.user?.city || "",
              profession:
                profile?.profession || profile?.user?.profession || "",
              education: profile?.education || profile?.user?.education || "",
              score: getScore(result),
              factors: getFactors(result),
              explanation: getExplanation(result),
              calculatedAt:
                result?.calculated_at || result?.data?.calculated_at || null,
              error: "",
            };
          } catch (requestError) {
            return {
              id: profileId,
              name: getProfileName(profile),
              city: profile?.city || "",
              profession: profile?.profession || "",
              education: profile?.education || "",
              score: null,
              factors: [],
              explanation: "",
              calculatedAt: null,
              error:
                requestError.response?.data?.detail ||
                requestError.response?.data?.error ||
                "Compatibility score could not be calculated.",
            };
          }
        }),
      );

      results.sort((a, b) => {
        if (a.score === null) return 1;
        if (b.score === null) return -1;
        return b.score - a.score;
      });

      setScores(results);
    } catch (requestError) {
      setScores([]);

      setError(
        requestError.response?.data?.detail ||
          requestError.response?.data?.error ||
          requestError.message ||
          "Unable to load compatibility scores.",
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    let ignore = false;

    const load = async () => {
      await loadScores();

      if (ignore) return;
    };

    load();

    return () => {
      ignore = true;
    };
    // Load scores when this page is mounted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadScores();
  };

  const scoredProfiles = scores.filter((item) => item.score !== null);

  const averageScore =
    scoredProfiles.length > 0
      ? Math.round(
          scoredProfiles.reduce((total, item) => total + item.score, 0) /
            scoredProfiles.length,
        )
      : null;

  return (
    <div className="compatibility-page">
      <div className="compatibility-header">
        <div>
          <span className="compatibility-eyebrow">
            SMART MATRIMONIAL PLATFORM
          </span>

          <h2>Compatibility Scores</h2>

          <p>
            Understand how well your profile matches with other available
            profiles.
          </p>
        </div>

        <div className="compatibility-header-icon">✦</div>
      </div>

      {/* SUMMARY CARDS */}
      <div className="compatibility-summary-grid">
        <article className="compatibility-summary-card">
          <div className="compatibility-summary-icon">♡</div>
          <div>
            <p>Profiles Found</p>
            <h3>{loading ? "—" : scores.length}</h3>
          </div>
        </article>

        <article className="compatibility-summary-card">
          <div className="compatibility-summary-icon">%</div>
          <div>
            <p>Average Score</p>
            <h3>
              {loading || averageScore === null ? "—" : `${averageScore}%`}
            </h3>
          </div>
        </article>

        <article className="compatibility-summary-card">
          <div className="compatibility-summary-icon">✧</div>
          <div>
            <p>Scores Calculated</p>
            <h3>{loading ? "—" : scoredProfiles.length}</h3>
          </div>
        </article>
      </div>

      {/* INTRO CARD */}
      <section className="compatibility-overview">
        <div className="compatibility-overview-icon">♡</div>

        <div className="compatibility-overview-content">
          <span className="compatibility-eyebrow">YOUR MATCH INSIGHTS</span>

          <h3>Discover meaningful connections</h3>

          <p>
            Compare available profiles using the compatibility score calculated
            by your backend.
          </p>

          <div className="compatibility-actions">
            <button
              type="button"
              className="compatibility-primary-button"
              onClick={handleRefresh}
              disabled={loading || refreshing}
            >
              {refreshing ? "Calculating..." : "Calculate Compatibility"}
            </button>

            <button
              type="button"
              className="compatibility-refresh-button"
              onClick={handleRefresh}
              disabled={loading || refreshing}
            >
              {refreshing ? "Refreshing..." : "↻ Refresh Scores"}
            </button>
          </div>
        </div>
      </section>

      {/* PROFILE RESULTS */}
      <div className="compatibility-section-heading">
        <div>
          <h3>Profile Compatibility</h3>
          <p>Compatibility results for profiles available to your account.</p>
        </div>

        {!loading && (
          <span className="compatibility-count">
            {scoredProfiles.length} scored
          </span>
        )}
      </div>

      {loading && (
        <div className="compatibility-state">
          <div className="compatibility-spinner" />
          <h3>Calculating Compatibility</h3>
          <p>Please wait while we load profiles and calculate scores.</p>
        </div>
      )}

      {!loading && error && (
        <div className="compatibility-state compatibility-error-state">
          <div className="compatibility-state-icon">!</div>
          <h3>Unable to Load Compatibility</h3>
          <p>{error}</p>

          <button
            type="button"
            className="compatibility-primary-button"
            onClick={handleRefresh}
          >
            Try Again
          </button>
        </div>
      )}

      {!loading && !error && scores.length === 0 && (
        <div className="compatibility-state">
          <div className="compatibility-state-icon">♡</div>
          <h3>No Other Profiles Available</h3>
          <p>
            The profile list API did not return any other profiles. Make sure
            other profiles are available in your tenant.
          </p>

          <button
            type="button"
            className="compatibility-primary-button"
            onClick={onExploreMatches}
          >
            Explore Matches →
          </button>
        </div>
      )}

      {!loading && !error && scores.length > 0 && (
        <div className="compatibility-results-grid">
          {scores.map((item) => (
            <article className="compatibility-profile-card" key={item.id}>
              <div className="compatibility-profile-header">
                <div className="compatibility-profile-avatar">
                  {item.name.charAt(0).toUpperCase()}
                </div>

                <div className="compatibility-profile-info">
                  <h3>{item.name}</h3>
                  <p>
                    {[item.city, item.profession].filter(Boolean).join(" • ") ||
                      "Profile available"}
                  </p>
                </div>

                <span className="compatibility-profile-star">✦</span>
              </div>

              {item.score !== null ? (
                <>
                  <div className="compatibility-score-row">
                    <div>
                      <span className="compatibility-score-caption">
                        Compatibility
                      </span>

                      <h4>{getScoreLabel(item.score)}</h4>
                    </div>

                    <strong className="compatibility-score-number">
                      {item.score}%
                    </strong>
                  </div>

                  <div
                    className="compatibility-progress-track"
                    role="progressbar"
                    aria-label={`${item.name} compatibility`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={item.score}
                  >
                    <div
                      className="compatibility-progress-fill"
                      style={{ width: `${item.score}%` }}
                    />
                  </div>

                  {item.calculatedAt && (
                    <p className="compatibility-calculated-date">
                      Calculated:{" "}
                      {new Date(item.calculatedAt).toLocaleDateString("en-IN")}
                    </p>
                  )}

                  {item.factors.length > 0 && (
                    <div className="compatibility-breakdown">
                      <h4>Score Breakdown</h4>

                      {item.factors.map((factor) => (
                        <div className="compatibility-factor" key={factor.name}>
                          <span>{formatFactorName(factor.name)}</span>
                          <strong>{formatFactorValue(factor.value)}</strong>
                        </div>
                      ))}
                    </div>
                  )}

                  {item.explanation && (
                    <div className="compatibility-explanation">
                      <h4>✧ AI Match Explanation</h4>
                      <p>{item.explanation}</p>
                    </div>
                  )}
                </>
              ) : (
                <div className="compatibility-unavailable">
                  <strong>Score Unavailable</strong>
                  <p>{item.error || "The API did not return a score."}</p>
                </div>
              )}
            </article>
          ))}
        </div>
      )}

      {/* INFORMATION CARDS */}
      <div className="compatibility-info-grid">
        <article className="compatibility-info-card">
          <div className="compatibility-info-icon">📊</div>
          <h3>Score Breakdown</h3>
          <p>
            If the backend returns individual matching factors, they will be
            displayed inside each profile card.
          </p>
        </article>

        <article className="compatibility-info-card">
          <div className="compatibility-info-icon">✧</div>
          <h3>AI Match Explanation</h3>
          <p>
            If the compatibility API returns an AI explanation, it will appear
            with the relevant profile. No explanation is invented when the API
            does not provide one.
          </p>
        </article>
      </div>
    </div>
  );
}

export default CompatibilityScores;
