
import { useEffect, useState } from "react";
import api from "./api";
import Chat from "./Chat";
import "./Dashboard.css";
import Settings from "./Settings";
import ThemeSettings from "./ThemeSettings";
import CompatibilityScores from "./CompatibilityScores";
import Subscription from "./Subscription";

const hiddenFields = ["id", "user", "created_at", "updated_at"];

const emptyForm = {
  full_name: "",
  date_of_birth: "",
  gender: "",
  city: "",
  education: "",
  profession: "",
  about_me: "",
};

const allowedImageTypes = ["image/jpeg", "image/png", "image/webp"];
const MAX_IMAGE_SIZE = 5 * 1024 * 1024;

function getPhotoList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  if (Array.isArray(data?.posts)) return data.posts;
  return [];
}

function getOtherProfileId(match, currentProfileId) {
  if (!match || !currentProfileId) return null;

  const isSender = String(match.sender) === String(currentProfileId);
  const isReceiver = String(match.receiver) === String(currentProfileId);

  if (isSender === isReceiver) return null;

  return isSender ? match.receiver : match.sender;
}

function getUniqueMatches(matchList, currentProfileId) {
  const uniqueMap = new Map();

  const priority = {
    accepted: 3,
    pending: 2,
    rejected: 1,
  };

  matchList.forEach((match) => {
    const otherProfileId = getOtherProfileId(match, currentProfileId);

    if (!otherProfileId) return;

    const key = String(otherProfileId);
    const existing = uniqueMap.get(key);

    if (!existing) {
      uniqueMap.set(key, match);
      return;
    }

    const currentPriority = priority[match.status] || 0;
    const existingPriority = priority[existing.status] || 0;

    const currentDate = new Date(
      match.updated_at || match.created_at || 0,
    ).getTime();

    const existingDate = new Date(
      existing.updated_at || existing.created_at || 0,
    ).getTime();

    if (
      currentPriority > existingPriority ||
      (currentPriority === existingPriority && currentDate > existingDate) ||
      (currentPriority === existingPriority &&
        currentDate === existingDate &&
        Number(match.id) > Number(existing.id))
    ) {
      uniqueMap.set(key, match);
    }
  });

  return Array.from(uniqueMap.values());
}

function getActiveOtherProfileIds(matchList, currentProfileId) {
  return [
    ...new Set(
      matchList
        .filter(
          (match) => match.status === "pending" || match.status === "accepted",
        )
        .map((match) => getOtherProfileId(match, currentProfileId))
        .filter(Boolean)
        .map(String),
    ),
  ];
}

function formatLabel(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "Not provided";
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (Array.isArray(value)) {
    return value.length
      ? value
          .map((item) =>
            typeof item === "object" && item !== null
              ? JSON.stringify(item)
              : String(item),
          )
          .join(", ")
      : "Not provided";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function formatDate(value) {
  if (!value) return "Date unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function getErrorMessage(error, fallback) {
  const data = error.response?.data;

  if (error.response?.status === 401) {
    return "Your session has expired. Please log in again.";
  }

  if (error.response?.status === 403) {
    return (
      data?.error ||
      data?.detail ||
      "This account does not have permission to perform this action."
    );
  }

  if (error.response?.status === 404) {
    return (
      data?.error ||
      data?.detail ||
      "Resource not found. Please check your profile."
    );
  }

  if (data && typeof data === "object") {
    const messages = Object.entries(data).map(([field, value]) => {
      const detail = Array.isArray(value)
        ? value.join(", ")
        : typeof value === "string"
          ? value
          : JSON.stringify(value);

      return `${field}: ${detail}`;
    });

    if (messages.length) {
      return messages.join(" | ");
    }
  }

  return fallback;
}

function Dashboard({ username, userRole, onLogout, theme, onThemeChange }) {
  const [page, setPage] = useState("dashboard");

  const [accountInfo, setAccountInfo] = useState(null);
  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState("");
  const [profileLoading, setProfileLoading] = useState(false);

  const [isEditing, setIsEditing] = useState(false);
  const [profileForm, setProfileForm] = useState(emptyForm);
  const [savingProfile, setSavingProfile] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [saveError, setSaveError] = useState("");

  // Profile photo gallery states
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [photoPreview, setPhotoPreview] = useState("");
  const [myPhotos, setMyPhotos] = useState([]);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [loadingPhoto, setLoadingPhoto] = useState(false);
  const [photoMessage, setPhotoMessage] = useState("");
  const [photoError, setPhotoError] = useState("");
  const [deletingPhotoId, setDeletingPhotoId] = useState(null);

  // Photo Posts states
  const [photoPosts, setPhotoPosts] = useState([]);
  const [photoPostsLoading, setPhotoPostsLoading] = useState(false);
  const [photoPostsError, setPhotoPostsError] = useState("");
  const [photoPostsMessage, setPhotoPostsMessage] = useState("");

  const [selectedPostImage, setSelectedPostImage] = useState(null);
  const [postCaption, setPostCaption] = useState("");
  const [uploadingPost, setUploadingPost] = useState(false);
  const [deletingPostId, setDeletingPostId] = useState(null);

  // Private gallery states
  const [privatePhotos, setPrivatePhotos] = useState([]);
  const [privatePhotosMember, setPrivatePhotosMember] = useState("");
  const [privatePhotosLoading, setPrivatePhotosLoading] = useState(false);
  const [privatePhotosError, setPrivatePhotosError] = useState("");
  const [showPrivateGallery, setShowPrivateGallery] = useState(false);

  // Match request states
  const [matches, setMatches] = useState([]);
  const [currentProfileId, setCurrentProfileId] = useState(null);
  const [presenceStatuses, setPresenceStatuses] = useState({});
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [matchesError, setMatchesError] = useState("");
  const [matchesMessage, setMatchesMessage] = useState("");
  const [matchActionLoading, setMatchActionLoading] = useState(null);

  // Blocked profile states
  const [blockedProfiles, setBlockedProfiles] = useState([]);
  const [blockedProfilesLoading, setBlockedProfilesLoading] = useState(false);
  const [blockedProfilesError, setBlockedProfilesError] = useState("");

  // Block, Unblock, Unfriend and Remove action state
  const [connectionActionLoading, setConnectionActionLoading] = useState(null);

  // Chat state
  const [chatTarget, setChatTarget] = useState(null);

  // Discover profiles states
  const [availableProfiles, setAvailableProfiles] = useState([]);
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [profilesError, setProfilesError] = useState("");
  const [sendingRequestTo, setSendingRequestTo] = useState(null);
  const [requestedProfileIds, setRequestedProfileIds] = useState([]);

  // Subscription access: Host and End User
  const canAccessSubscription = ["host", "end_user"].includes(
    String(userRole || "").trim().toLowerCase(),
  );

  // Load Photo Posts feed.
  const loadPhotoPosts = async () => {
    setPhotoPostsLoading(true);
    setPhotoPostsError("");

    try {
      const response = await api.get("/api/profiles/posts/feed/");
      setPhotoPosts(getPhotoList(response.data));
    } catch (error) {
      setPhotoPosts([]);
      setPhotoPostsError(
        getErrorMessage(error, "Unable to load Photo Posts feed."),
      );
    } finally {
      setPhotoPostsLoading(false);
    }
  };

  // Load current user's profile ID.
  const loadCurrentProfileId = async () => {
    try {
      const response = await api.get("/api/profiles/me/detail/");
      const data = response.data?.profile ?? response.data;

      if (data?.id) {
        setCurrentProfileId(data.id);
      }
    } catch (error) {
      console.error("Unable to load current profile ID:", error);
    }
  };

  // Refresh Photo Posts whenever Dashboard becomes active.
  useEffect(() => {
    if (page === "dashboard") {
      loadPhotoPosts();
      loadCurrentProfileId();
    }
  }, [page]);

  // Keep presence status updated for accepted matches through WebSocket.
  useEffect(() => {
    setPresenceStatuses({});

    if (!currentProfileId) {
      return undefined;
    }

    const initialToken = localStorage.getItem("access_token");

    if (!initialToken) {
      return undefined;
    }

    let backendUrl;

    try {
      backendUrl = new URL(
        api.defaults?.baseURL || window.location.origin,
        window.location.origin,
      );
    } catch (error) {
      console.error("Invalid API base URL for presence WebSocket:", error);
      return undefined;
    }

    const wsProtocol = backendUrl.protocol === "https:" ? "wss:" : "ws:";

    let socket = null;
    let heartbeatTimer = null;
    let reconnectTimer = null;
    let reconnectDelay = 3000;
    let shouldStop = false;

    const clearHeartbeat = () => {
      if (heartbeatTimer !== null) {
        window.clearInterval(heartbeatTimer);
        heartbeatTimer = null;
      }
    };

    const applyPresenceMessage = (message) => {
      if (!message || typeof message !== "object") {
        return;
      }

      if (message.type === "presence_snapshot") {
        const nextStatuses = {};
        const statusList = Array.isArray(message.statuses)
          ? message.statuses
          : [];

        statusList.forEach((status) => {
          if (status?.profile_id === null || status?.profile_id === undefined) {
            return;
          }

          const profileKey = String(status.profile_id);

          nextStatuses[profileKey] = {
            profile_id: status.profile_id,
            is_online: Boolean(status.is_online),
            last_seen: status.last_seen || null,
            profile_name: status.profile_name || "",
          };
        });

        setPresenceStatuses(nextStatuses);
        return;
      }

      if (message.type === "presence_update") {
        if (message.profile_id === null || message.profile_id === undefined) {
          return;
        }

        const profileKey = String(message.profile_id);

        setPresenceStatuses((previous) => ({
          ...previous,
          [profileKey]: {
            ...(previous[profileKey] || {}),
            profile_id: message.profile_id,
            is_online: Boolean(message.is_online),
            last_seen: message.last_seen || null,
            profile_name:
              message.profile_name || previous[profileKey]?.profile_name || "",
          },
        }));
        return;
      }

      if (message.type === "presence_access_revoked") {
        const revokedIds = Array.isArray(message.profile_ids)
          ? message.profile_ids
          : [];

        if (revokedIds.length > 0) {
          setPresenceStatuses((previous) => {
            const nextStatuses = { ...previous };

            revokedIds.forEach((profileId) => {
              delete nextStatuses[String(profileId)];
            });

            return nextStatuses;
          });
        }
      }
    };

    const scheduleReconnect = () => {
      if (shouldStop || reconnectTimer !== null) {
        return;
      }

      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connectPresenceSocket();
      }, reconnectDelay);

      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    };

    const connectPresenceSocket = () => {
      if (shouldStop) {
        return;
      }

      const latestToken = localStorage.getItem("access_token");

      if (!latestToken) {
        return;
      }

      const socketUrl =
        `${wsProtocol}//${backendUrl.host}/ws/presence/` +
        `?token=${encodeURIComponent(latestToken)}`;

      let activeSocket;

      try {
        activeSocket = new WebSocket(socketUrl);
        socket = activeSocket;
      } catch (error) {
        console.error("Unable to create presence WebSocket:", error);
        scheduleReconnect();
        return;
      }

      activeSocket.onopen = () => {
        reconnectDelay = 3000;

        const sendHeartbeat = () => {
          if (activeSocket.readyState === WebSocket.OPEN) {
            activeSocket.send(JSON.stringify({ type: "heartbeat" }));
          }
        };

        sendHeartbeat();
        clearHeartbeat();
        heartbeatTimer = window.setInterval(sendHeartbeat, 25000);
      };

      activeSocket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          applyPresenceMessage(message);
        } catch (error) {
          console.error("Invalid presence WebSocket message:", error);
        }
      };

      activeSocket.onerror = () => {
        if (activeSocket.readyState !== WebSocket.CLOSED) {
          activeSocket.close();
        }
      };

      activeSocket.onclose = () => {
        clearHeartbeat();

        if (!shouldStop) {
          scheduleReconnect();
        }
      };
    };

    connectPresenceSocket();

    return () => {
      shouldStop = true;
      clearHeartbeat();

      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }

      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;

        if (
          socket.readyState === WebSocket.OPEN ||
          socket.readyState === WebSocket.CONNECTING
        ) {
          socket.close();
        }
      }
    };
  }, [currentProfileId]);

  // Load current user's profile and photos.
  const loadProfile = async () => {
    setPage("profile");
    setProfileError("");
    setProfileLoading(true);
    setSaveMessage("");
    setSaveError("");
    setPhotoMessage("");
    setPhotoError("");
    setLoadingPhoto(true);

    try {
      const accountResponse = await api.get("/api/profiles/me/");
      setAccountInfo(accountResponse.data?.profile ?? accountResponse.data);
    } catch (error) {
      setAccountInfo(null);
      setProfileError(
        getErrorMessage(error, "Unable to load your account information."),
      );
    }

    try {
      const response = await api.get("/api/profiles/me/detail/");
      const data = response.data?.profile ?? response.data;

      setProfile(data);
      setCurrentProfileId(data.id ?? null);

      setProfileForm({
        full_name: data.full_name ?? "",
        date_of_birth: data.date_of_birth ?? "",
        gender: data.gender ?? "",
        city: data.city ?? "",
        education: data.education ?? "",
        profession: data.profession ?? "",
        about_me: data.about_me ?? "",
      });

      setProfileError("");
      setIsEditing(false);
    } catch (error) {
      setProfile(null);
      setProfileForm(emptyForm);
      setProfileError(
        getErrorMessage(error, "Unable to load detailed profile information."),
      );
    } finally {
      setProfileLoading(false);
    }

    try {
      const photosResponse = await api.get("/api/profiles/photos/me/");
      const photos = getPhotoList(photosResponse.data);

      setMyPhotos(photos);

      const primaryPhoto =
        photos.find((photo) => photo.is_primary) || photos[0];

      setPhotoPreview(primaryPhoto?.image_url || "");
      setSelectedPhoto(null);
    } catch (error) {
      setMyPhotos([]);
      setPhotoPreview("");
      setPhotoError(
        getErrorMessage(error, "Unable to load your saved profile photos."),
      );
    } finally {
      setLoadingPhoto(false);
    }
  };

  // Load other profiles belonging to the current tenant.
  const loadAvailableProfiles = async (myProfileId) => {
    setProfilesLoading(true);
    setProfilesError("");

    try {
      const response = await api.get("/api/profiles/list/");
      const data = response.data;

      const profileList = Array.isArray(data)
        ? data
        : Array.isArray(data?.results)
          ? data.results
          : Array.isArray(data?.profiles)
            ? data.profiles
            : [];

      setAvailableProfiles(
        profileList.filter((item) => String(item.id) !== String(myProfileId)),
      );
    } catch (error) {
      setAvailableProfiles([]);
      setProfilesError(
        getErrorMessage(error, "Unable to load available profiles."),
      );
    } finally {
      setProfilesLoading(false);
    }
  };

  // Load blocked profiles.
  const loadBlockedProfiles = async () => {
    setBlockedProfilesLoading(true);
    setBlockedProfilesError("");

    try {
      const response = await api.get("/api/profiles/blocks/");
      const data = response.data;

      const blockedList = Array.isArray(data)
        ? data
        : Array.isArray(data?.results)
          ? data.results
          : Array.isArray(data?.blocked_profiles)
            ? data.blocked_profiles
            : Array.isArray(data?.blocks)
              ? data.blocks
              : [];

      const normalizedBlockedProfiles = blockedList
        .map((item) => {
          const blockedId =
            item.blocked_profile_id ??
            item.profile_id ??
            (typeof item.blocked === "object"
              ? item.blocked?.id
              : item.blocked) ??
            item.id;

          return {
            ...item,
            id: blockedId,
            full_name:
              item.full_name ??
              item.blocked_profile_name ??
              item.blocked_name ??
              item.profile_name ??
              item.blocked?.full_name ??
              "Member",
          };
        })
        .filter((item) => item.id !== null && item.id !== undefined);

      setBlockedProfiles(normalizedBlockedProfiles);
    } catch (error) {
      setBlockedProfiles([]);
      setBlockedProfilesError(
        getErrorMessage(error, "Unable to load blocked profiles."),
      );
    } finally {
      setBlockedProfilesLoading(false);
    }
  };

  // Load current user's matches and requests.
  const loadMatches = async (targetPage = "matches") => {
    setPage(targetPage);
    setMatchesLoading(true);
    setMatchesError("");
    setMatchesMessage("");

    try {
      const profileResponse = await api.get("/api/profiles/me/detail/");
      const myProfile = profileResponse.data?.profile ?? profileResponse.data;

      if (!myProfile?.id) {
        throw new Error("Your profile ID could not be found.");
      }

      setCurrentProfileId(myProfile.id);

      const matchesResponse = await api.get("/api/profiles/matches/");
      const responseData = matchesResponse.data;

      const matchList = Array.isArray(responseData)
        ? responseData
        : Array.isArray(responseData?.results)
          ? responseData.results
          : [];

      setMatches(matchList);

      setRequestedProfileIds(getActiveOtherProfileIds(matchList, myProfile.id));

      await loadAvailableProfiles(myProfile.id);
      await loadBlockedProfiles();
    } catch (error) {
      setMatches([]);
      setRequestedProfileIds([]);

      setMatchesError(
        getErrorMessage(
          error,
          error.message || "Unable to load matches. Please try again.",
        ),
      );
    } finally {
      setMatchesLoading(false);
    }
  };

  // Send a match request.
  const handleSendMatchRequest = async (candidate) => {
    if (sendingRequestTo !== null) return;

    setSendingRequestTo(candidate.id);
    setMatchesError("");
    setMatchesMessage("");

    try {
      const response = await api.post("/api/profiles/matches/send/", {
        receiver: candidate.id,
      });

      const newMatch = response.data;

      const updatedMatches = [
        newMatch,
        ...matches.filter((match) => String(match.id) !== String(newMatch.id)),
      ];

      setMatches(updatedMatches);

      setRequestedProfileIds(
        getActiveOtherProfileIds(updatedMatches, currentProfileId),
      );

      setMatchesMessage(
        `Match request sent to ${candidate.full_name || "this member"}.`,
      );
    } catch (error) {
      setMatchesError(getErrorMessage(error, "Unable to send match request."));
    } finally {
      setSendingRequestTo(null);
    }
  };

  // Accept or reject an incoming request.
  const handleMatchStatus = async (matchId, nextStatus) => {
    setMatchActionLoading(matchId);
    setMatchesError("");
    setMatchesMessage("");

    try {
      await api.patch(`/api/profiles/matches/${matchId}/status/`, {
        status: nextStatus,
      });

      const updatedMatches = matches.map((match) =>
        String(match.id) === String(matchId)
          ? { ...match, status: nextStatus }
          : match,
      );

      setMatches(updatedMatches);

      setRequestedProfileIds(
        getActiveOtherProfileIds(updatedMatches, currentProfileId),
      );

      if (nextStatus === "accepted") {
        setMatchesMessage("Match request accepted. Refreshing Photo Posts...");
        await loadPhotoPosts();
      } else {
        setMatchesMessage("Match request rejected.");
      }
    } catch (error) {
      setMatchesError(
        getErrorMessage(error, "Unable to update the match request."),
      );
    } finally {
      setMatchActionLoading(null);
    }
  };

  // Refresh match data after a connection action.
  const refreshAfterConnectionAction = async (successMessage) => {
    await loadMatches(page);
    setMatchesMessage(successMessage);
  };

  // Block a profile.
  const handleBlockProfile = async (profileId, profileName = "this member") => {
    if (!profileId || connectionActionLoading !== null) return;

    const confirmed = window.confirm(
      `Are you sure you want to block ${profileName}? This will remove your existing match connection and hide this profile.`,
    );

    if (!confirmed) return;

    setConnectionActionLoading(`block-${profileId}`);
    setMatchesError("");
    setMatchesMessage("");

    try {
      await api.post(`/api/profiles/blocks/${profileId}/`);

      await refreshAfterConnectionAction(
        `${profileName} has been blocked successfully.`,
      );
    } catch (error) {
      setMatchesError(
        getErrorMessage(error, "Unable to block this profile."),
      );
    } finally {
      setConnectionActionLoading(null);
    }
  };

  // Unblock a profile.
  const handleUnblockProfile = async (profileId, profileName = "this member") => {
    if (!profileId || connectionActionLoading !== null) return;

    setConnectionActionLoading(`unblock-${profileId}`);
    setMatchesError("");
    setMatchesMessage("");

    try {
      await api.delete(`/api/profiles/blocks/${profileId}/`);

      await refreshAfterConnectionAction(
        `${profileName} has been unblocked successfully. You can discover this profile again if they have not blocked you.`,
      );
    } catch (error) {
      setMatchesError(
        getErrorMessage(error, "Unable to unblock this profile."),
      );
    } finally {
      setConnectionActionLoading(null);
    }
  };

  // Unfriend an accepted connection.
  const handleUnfriendProfile = async (
    profileId,
    profileName = "this member",
  ) => {
    if (!profileId || connectionActionLoading !== null) return;

    const confirmed = window.confirm(
      `Are you sure you want to unfriend ${profileName}? This connection will be removed for both users.`,
    );

    if (!confirmed) return;

    setConnectionActionLoading(`unfriend-${profileId}`);
    setMatchesError("");
    setMatchesMessage("");

    try {
      await api.delete(`/api/profiles/matches/${profileId}/unfriend/`);

      await refreshAfterConnectionAction(
        `${profileName} has been removed from your connections.`,
      );
    } catch (error) {
      setMatchesError(
        getErrorMessage(error, "Unable to unfriend this member."),
      );
    } finally {
      setConnectionActionLoading(null);
    }
  };

  // Remove an accepted connection from only the current user's list.
  const handleRemoveConnection = async (
    profileId,
    profileName = "this member",
  ) => {
    if (!profileId || connectionActionLoading !== null) return;

    const confirmed = window.confirm(
      `Remove ${profileName} from your connections? The other user will still see this connection.`,
    );

    if (!confirmed) return;

    setConnectionActionLoading(`remove-${profileId}`);
    setMatchesError("");
    setMatchesMessage("");

    try {
      await api.post(`/api/profiles/matches/${profileId}/remove/`);

      await refreshAfterConnectionAction(
        `${profileName} has been removed from your match list.`,
      );
    } catch (error) {
      setMatchesError(
        getErrorMessage(error, "Unable to remove this connection."),
      );
    } finally {
      setConnectionActionLoading(null);
    }
  };

  // Current user's profile name and request information.
  const getOtherPersonName = (match) => {
    const otherProfileId = getOtherProfileId(match, currentProfileId);

    if (!otherProfileId) return "Member";

    const isIncoming = String(match.receiver) === String(currentProfileId);
    const name = isIncoming ? match.sender_name : match.receiver_name;

    return name || "Member";
  };

  // Open chat for an accepted match.
  const handleOpenChat = (match) => {
    if (match.status !== "accepted") {
      setMatchesError("Chat is available only for accepted matches.");
      return;
    }

    if (!currentProfileId) {
      setMatchesError("Your profile could not be identified. Please refresh.");
      return;
    }

    const otherProfileId = getOtherProfileId(match, currentProfileId);

    if (!otherProfileId) {
      setMatchesError("The other member's profile ID could not be found.");
      return;
    }

    setMatchesError("");

    setChatTarget({
      profileId: otherProfileId,
      profileName: getOtherPersonName(match),
    });
  };

  // Close chat modal.
  const closeChat = () => {
    setChatTarget(null);
  };

  // Open an accepted match's private photo gallery.
  const handleViewPrivatePhotos = async (match) => {
    if (match.status !== "accepted") {
      setMatchesError(
        "Private photos are available only for accepted matches.",
      );
      return;
    }

    if (!currentProfileId) {
      setMatchesError("Your profile could not be identified. Please refresh.");
      return;
    }

    const otherProfileId = getOtherProfileId(match, currentProfileId);

    if (!otherProfileId) {
      setMatchesError("The other member's profile ID could not be found.");
      return;
    }

    setPrivatePhotos([]);
    setPrivatePhotosMember(getOtherPersonName(match));
    setPrivatePhotosError("");
    setPrivatePhotosLoading(true);
    setShowPrivateGallery(true);

    try {
      const response = await api.get(`/api/profiles/photos/${otherProfileId}/`);
      setPrivatePhotos(getPhotoList(response.data));
    } catch (error) {
      setPrivatePhotos([]);
      setPrivatePhotosError(
        getErrorMessage(
          error,
          "Unable to load private photos. You may not have permission to view them.",
        ),
      );
    } finally {
      setPrivatePhotosLoading(false);
    }
  };

  const closePrivateGallery = () => {
    setShowPrivateGallery(false);
    setPrivatePhotos([]);
    setPrivatePhotosError("");
    setPrivatePhotosMember("");
  };

  const handleFormChange = (event) => {
    const { name, value } = event.target;

    setProfileForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  // Save profile changes.
  const handleSaveProfile = async (event) => {
    event.preventDefault();

    if (!profile) {
      setSaveError("A profile must exist before you can update it.");
      return;
    }

    if (!profileForm.full_name.trim()) {
      setSaveError("Full name is required.");
      return;
    }

    setSavingProfile(true);
    setSaveError("");
    setSaveMessage("");

    try {
      const response = await api.patch("/api/profiles/me/detail/", profileForm);

      const updatedProfile = response.data?.profile ?? response.data;

      setProfile(updatedProfile);

      setProfileForm({
        full_name: updatedProfile.full_name ?? "",
        date_of_birth: updatedProfile.date_of_birth ?? "",
        gender: updatedProfile.gender ?? "",
        city: updatedProfile.city ?? "",
        education: updatedProfile.education ?? "",
        profession: updatedProfile.profession ?? "",
        about_me: updatedProfile.about_me ?? "",
      });

      setIsEditing(false);
      setSaveMessage("Profile updated successfully.");
    } catch (error) {
      setSaveError(
        getErrorMessage(error, "Unable to save your profile changes."),
      );
    } finally {
      setSavingProfile(false);
    }
  };

  // Validate a selected image.
  const validateImage = (file) => {
    if (!file) {
      return "Please select an image.";
    }

    if (!allowedImageTypes.includes(file.type)) {
      return "Choose a JPG, PNG or WEBP image.";
    }

    if (file.size > MAX_IMAGE_SIZE) {
      return "Image size must not exceed 5 MB.";
    }

    return "";
  };

  // Select a profile photo.
  const handlePhotoSelection = (event) => {
    const file = event.target.files?.[0];

    setPhotoError("");
    setPhotoMessage("");

    if (!file) return;

    const validationError = validateImage(file);

    if (validationError) {
      setPhotoError(validationError);
      setSelectedPhoto(null);
      event.target.value = "";
      return;
    }

    setSelectedPhoto(file);
    setPhotoPreview(URL.createObjectURL(file));
  };

  // Upload a profile photo.
  const handlePhotoUpload = async () => {
    if (!profile) {
      setPhotoError("Create your profile before uploading a photo.");
      return;
    }

    if (!selectedPhoto) {
      setPhotoError("Please select an image first.");
      return;
    }

    const formData = new FormData();

    formData.append("image", selectedPhoto);
    formData.append("is_primary", myPhotos.length === 0 ? "true" : "false");

    setUploadingPhoto(true);
    setPhotoError("");
    setPhotoMessage("");

    try {
      await api.post("/api/profiles/photos/upload/", formData);

      const photosResponse = await api.get("/api/profiles/photos/me/");
      const photos = getPhotoList(photosResponse.data);

      setMyPhotos(photos);

      const primaryPhoto =
        photos.find((photo) => photo.is_primary) || photos[0];

      setPhotoPreview(primaryPhoto?.image_url || "");
      setSelectedPhoto(null);

      setPhotoMessage("Photo uploaded successfully.");
    } catch (error) {
      setPhotoError(
        getErrorMessage(
          error,
          "Photo upload failed. Please check the server and Cloudinary configuration.",
        ),
      );
    } finally {
      setUploadingPhoto(false);
    }
  };

  // Delete one of the current user's profile photos.
  const handleDeleteProfilePhoto = async (photo) => {
    const confirmed = window.confirm(
      "Are you sure you want to delete this profile photo?",
    );

    if (!confirmed) return;

    setDeletingPhotoId(photo.id);
    setPhotoError("");
    setPhotoMessage("");

    try {
      await api.delete(`/api/profiles/photos/${photo.id}/delete/`);

      const response = await api.get("/api/profiles/photos/me/");
      const updatedPhotos = getPhotoList(response.data);

      setMyPhotos(updatedPhotos);

      const primaryPhoto =
        updatedPhotos.find((item) => item.is_primary) || updatedPhotos[0];

      setPhotoPreview(primaryPhoto?.image_url || "");
      setSelectedPhoto(null);

      setPhotoMessage("Profile photo deleted successfully.");
    } catch (error) {
      setPhotoError(
        getErrorMessage(error, "Unable to delete this profile photo."),
      );
    } finally {
      setDeletingPhotoId(null);
    }
  };

  // Select an image for a Photo Post.
  const handlePostImageSelection = (event) => {
    const file = event.target.files?.[0];

    setPhotoPostsError("");
    setPhotoPostsMessage("");

    if (!file) {
      setSelectedPostImage(null);
      return;
    }

    const validationError = validateImage(file);

    if (validationError) {
      setPhotoPostsError(validationError);
      setSelectedPostImage(null);
      event.target.value = "";
      return;
    }

    setSelectedPostImage(file);
  };

  // Upload a Photo Post with caption.
  const handlePhotoPostUpload = async (event) => {
    event.preventDefault();

    if (!selectedPostImage) {
      setPhotoPostsError("Please select an image for your post.");
      return;
    }

    const formData = new FormData();
    formData.append("image", selectedPostImage);
    formData.append("caption", postCaption.trim());

    setUploadingPost(true);
    setPhotoPostsError("");
    setPhotoPostsMessage("");

    try {
      await api.post("/api/profiles/posts/upload/", formData);

      setSelectedPostImage(null);
      setPostCaption("");

      await loadPhotoPosts();

      setPhotoPostsMessage("Your photo post was uploaded successfully.");
    } catch (error) {
      setPhotoPostsError(
        getErrorMessage(error, "Unable to upload your Photo Post."),
      );
    } finally {
      setUploadingPost(false);
    }
  };

  // Delete a Photo Post.
  const handleDeletePhotoPost = async (post) => {
    const confirmed = window.confirm(
      "Are you sure you want to delete this post?",
    );

    if (!confirmed) return;

    setDeletingPostId(post.id);
    setPhotoPostsError("");
    setPhotoPostsMessage("");

    try {
      await api.delete(`/api/profiles/posts/${post.id}/delete/`);

      setPhotoPosts((previous) =>
        previous.filter((item) => String(item.id) !== String(post.id)),
      );

      setPhotoPostsMessage("Photo post deleted successfully.");
    } catch (error) {
      setPhotoPostsError(
        getErrorMessage(error, "Unable to delete this Photo Post."),
      );
    } finally {
      setDeletingPostId(null);
    }
  };

  const getRequestDirection = (match) => {
    return String(match.receiver) === String(currentProfileId)
      ? "Received request"
      : "Request sent";
  };

  const getStatusLabel = (statusValue) => {
    const labels = {
      pending: "Pending",
      accepted: "Accepted",
      rejected: "Rejected",
    };

    return labels[statusValue] || formatLabel(statusValue || "unknown");
  };

  const displayProfile = profile || accountInfo;

  const profileFields =
    displayProfile &&
    typeof displayProfile === "object" &&
    !Array.isArray(displayProfile)
      ? Object.entries(displayProfile).filter(
          ([key]) => !hiddenFields.includes(key),
        )
      : [];

  const filledFields = profileFields.filter(
    ([, value]) =>
      value !== null &&
      value !== undefined &&
      value !== "" &&
      !(Array.isArray(value) && value.length === 0),
  ).length;

  const completion = profileFields.length
    ? Math.round((filledFields / profileFields.length) * 100)
    : 0;

  // Matches page: show one latest/highest-priority match per member.
  const displayedMatches = getUniqueMatches(matches, currentProfileId);

  // Requests page: show all incoming requests, not outgoing requests.
  const incomingRequests = matches.filter(
    (match) => String(match.receiver) === String(currentProfileId),
  );

  return (
    <>
      <div className="dashboard-layout">
        <aside className="dashboard-sidebar">
          <div className="dashboard-brand">
            <span className="dashboard-brand-icon">♥</span>
            <span>Smart Matrimonial</span>
          </div>

          <p className="sidebar-label">MAIN MENU</p>

          <nav className="dashboard-nav">
            <button
              className={`nav-item ${page === "dashboard" ? "active" : ""}`}
              type="button"
              onClick={() => {
                setPage("dashboard");
                loadPhotoPosts();
              }}
            >
              <span>⌂</span> Dashboard
            </button>

            <button
              className={`nav-item ${page === "profile" ? "active" : ""}`}
              type="button"
              onClick={loadProfile}
            >
              <span>♙</span> My Profile
            </button>

            <button
              className={`nav-item ${page === "matches" ? "active" : ""}`}
              type="button"
              onClick={() => loadMatches("matches")}
            >
              <span>♡</span> Matches
            </button>

            <button
              className={`nav-item ${page === "requests" ? "active" : ""}`}
              type="button"
              onClick={() => loadMatches("requests")}
            >
              <span>✉</span> Requests
            </button>

            <button
              className={`nav-item ${page === "compatibility" ? "active" : ""}`}
              type="button"
              onClick={() => setPage("compatibility")}
            >
              <span>✦</span> Compatibility
            </button>

            {/* Subscription: Host and End User */}
            {canAccessSubscription && (
              <button
                className={`nav-item ${page === "subscription" ? "active" : ""}`}
                type="button"
                onClick={() => setPage("subscription")}
              >
                <span>₹</span> Subscription &amp; Billing
              </button>
            )}

            <button
              className={`nav-item ${page === "settings" ? "active" : ""}`}
              type="button"
              onClick={() => setPage("settings")}
            >
              <span>⚙</span> Settings
            </button>
          </nav>

          <button className="dashboard-logout" type="button" onClick={onLogout}>
            ↪ Logout
          </button>
        </aside>

        <main className="dashboard-main">
          <header className="dashboard-header">
            <div>
              <p className="dashboard-eyebrow">YOUR PERSONAL SPACE</p>

              <h1>
                {page === "dashboard"
                  ? "Dashboard"
                  : page === "profile"
                    ? "My Profile"
                    : page === "matches"
                      ? "Matches"
                      : page === "requests"
                        ? "Requests"
                        : page === "compatibility"
                          ? "Compatibility Scores"
                          : page === "subscription"
                            ? "Subscription & Billing"
                            : "Settings"}
              </h1>
            </div>

            <div className="dashboard-user">
              <div className="dashboard-avatar">
                {photoPreview ? (
                  <img
                    src={photoPreview}
                    alt="Profile"
                    className="dashboard-avatar-image"
                  />
                ) : (
                  username?.charAt(0).toUpperCase() || "U"
                )}
              </div>

              <div>
                <strong>{username}</strong>
                <span>Member</span>
              </div>
            </div>
          </header>

          {/* DASHBOARD HOME */}
          {page === "dashboard" && (
            <>
              <section className="dashboard-welcome">
                <div>
                  <span className="welcome-badge">
                    ♥ YOUR JOURNEY STARTS HERE
                  </span>

                  <h2>Welcome back, {username}!</h2>

                  <p>Build your profile and discover meaningful connections.</p>

                  <button
                    className="dashboard-primary"
                    type="button"
                    onClick={loadProfile}
                    disabled={profileLoading}
                  >
                    View My Profile →
                  </button>
                </div>

                <div className="welcome-heart" aria-hidden="true">
                  ♥
                </div>
              </section>

              <section className="dashboard-section">
                <div className="section-heading">
                  <div>
                    <h2>Get started</h2>
                    <p>Continue your matrimonial journey.</p>
                  </div>
                </div>

                <div className="dashboard-cards">
                  <article className="dashboard-card">
                    <div className="dashboard-card-icon">♙</div>
                    <h3>My Profile</h3>
                    <p>View and update your personal profile information.</p>
                    <button type="button" onClick={loadProfile}>
                      View Profile →
                    </button>
                  </article>

                  <article className="dashboard-card">
                    <div className="dashboard-card-icon">♡</div>
                    <h3>Find Matches</h3>
                    <p>Discover potential matches and manage requests.</p>
                    <button
                      type="button"
                      onClick={() => loadMatches("matches")}
                    >
                      Explore →
                    </button>
                  </article>

                  <article className="dashboard-card">
                    <div className="dashboard-card-icon">✦</div>
                    <h3>Compatibility</h3>
                    <p>
                      View compatibility insights and understand your potential
                      matches.
                    </p>
                    <button
                      type="button"
                      onClick={() => setPage("compatibility")}
                    >
                      View Compatibility →
                    </button>
                  </article>
                </div>
              </section>

              {/* PHOTO POSTS */}
              <section className="dashboard-section photo-posts-section">
                <div className="section-heading">
                  <div>
                    <h2>Photo Posts</h2>
                    <p>
                      Share photos and see posts from your accepted matches.
                    </p>
                  </div>

                  <button
                    className="profile-secondary"
                    type="button"
                    onClick={loadPhotoPosts}
                    disabled={photoPostsLoading}
                  >
                    {photoPostsLoading ? "Refreshing..." : "Refresh Feed"}
                  </button>
                </div>

                <form
                  className="photo-upload-panel"
                  onSubmit={handlePhotoPostUpload}
                >
                  <h3>Create a Photo Post</h3>

                  <p className="profile-subtitle">
                    Select a photo and write a caption.
                  </p>

                  <label className="profile-form-field photo-file-field">
                    Select Image
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handlePostImageSelection}
                    />
                  </label>

                  {selectedPostImage && (
                    <p className="profile-subtitle">
                      Selected: {selectedPostImage.name}
                    </p>
                  )}

                  <label className="profile-form-field">
                    Caption
                    <textarea
                      value={postCaption}
                      onChange={(event) => setPostCaption(event.target.value)}
                      maxLength={500}
                      rows={3}
                      placeholder="Write a caption for your photo..."
                    />
                  </label>

                  <p className="profile-subtitle">
                    {postCaption.length}/500 characters
                  </p>

                  {photoPostsError && (
                    <div className="profile-message profile-error" role="alert">
                      {photoPostsError}
                    </div>
                  )}

                  {photoPostsMessage && (
                    <div
                      className="profile-message profile-success"
                      role="status"
                    >
                      {photoPostsMessage}
                    </div>
                  )}

                  <button
                    className="dashboard-primary"
                    type="submit"
                    disabled={!selectedPostImage || uploadingPost}
                  >
                    {uploadingPost ? "Uploading Post..." : "Publish Post"}
                  </button>
                </form>

                <div style={{ marginTop: "28px" }}>
                  <h3>Latest Posts</h3>

                  {photoPostsLoading && (
                    <p className="profile-message" role="status">
                      Loading Photo Posts...
                    </p>
                  )}

                  {!photoPostsLoading &&
                    !photoPostsError &&
                    photoPosts.length === 0 && (
                      <p className="profile-subtitle">
                        No Photo Posts available yet.
                      </p>
                    )}

                  {!photoPostsLoading && photoPosts.length > 0 && (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "repeat(auto-fill, minmax(230px, 1fr))",
                        gap: "20px",
                        marginTop: "18px",
                      }}
                    >
                      {photoPosts.map((post) => {
                        const isMyPost =
                          currentProfileId &&
                          String(post.profile_id) === String(currentProfileId);

                        return (
                          <article
                            key={post.id}
                            style={{
                              border: "1px solid #e5e7eb",
                              borderRadius: "14px",
                              overflow: "hidden",
                              background: "#fff",
                              boxShadow: "0 3px 12px rgba(0,0,0,0.05)",
                            }}
                          >
                            <img
                              src={post.image_url}
                              alt={post.caption || "Photo post"}
                              style={{
                                width: "100%",
                                height: "230px",
                                objectFit: "cover",
                                display: "block",
                              }}
                            />

                            <div style={{ padding: "14px" }}>
                              <strong>{post.profile_name || "Member"}</strong>

                              <p
                                style={{
                                  margin: "8px 0",
                                  overflowWrap: "anywhere",
                                }}
                              >
                                {post.caption || "No caption"}
                              </p>

                              <small style={{ color: "#777" }}>
                                {formatDate(post.created_at)}
                              </small>

                              {isMyPost && (
                                <div style={{ marginTop: "12px" }}>
                                  <button
                                    type="button"
                                    className="match-reject-button"
                                    disabled={
                                      String(deletingPostId) === String(post.id)
                                    }
                                    onClick={() => handleDeletePhotoPost(post)}
                                  >
                                    {String(deletingPostId) === String(post.id)
                                      ? "Deleting..."
                                      : "Delete Post"}
                                  </button>
                                </div>
                              )}
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  )}
                </div>
              </section>
            </>
          )}

          {/* MY PROFILE */}
          {page === "profile" && (
            <section className="dashboard-profile">
              {profileLoading && (
                <div className="profile-message" role="status">
                  Loading your profile...
                </div>
              )}

              {profileError && (
                <div className="profile-message profile-error" role="alert">
                  {profileError}
                </div>
              )}

              {displayProfile && !profileLoading && (
                <>
                  <div className="profile-heading">
                    <div>
                      <p className="dashboard-eyebrow">YOUR ACCOUNT</p>
                      <h2>Personal Profile</h2>
                      <p className="profile-subtitle">
                        {profile
                          ? "View and manage your matrimonial profile."
                          : "Basic account information returned by your API."}
                      </p>
                    </div>

                    <div className="profile-avatar-large">
                      {username?.charAt(0).toUpperCase() || "U"}
                    </div>
                  </div>

                  <div className="completion-panel">
                    <div className="completion-top">
                      <strong>Profile information</strong>
                      <span>{completion}%</span>
                    </div>

                    <div
                      className="completion-track"
                      role="progressbar"
                      aria-label="Profile information completion"
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={completion}
                    >
                      <div
                        className="completion-fill"
                        style={{ width: `${completion}%` }}
                      />
                    </div>

                    <p>
                      This estimate is based on the non-empty fields returned by
                      the API, not an official backend completion status.
                    </p>
                  </div>

                  {!profile && (
                    <div className="profile-access-note">
                      Detailed profile editing and photo upload require an
                      existing tenant-linked profile and permission from the
                      backend. Basic account information is shown above.
                    </div>
                  )}

                  {profile && !isEditing && (
                    <>
                      <div className="profile-details">
                        {profileFields.map(([key, value]) => (
                          <div className="profile-detail" key={key}>
                            <span>{formatLabel(key)}</span>
                            <strong>{formatValue(value)}</strong>
                          </div>
                        ))}
                      </div>

                      <div className="profile-action-row">
                        <button
                          className="dashboard-primary"
                          type="button"
                          onClick={() => {
                            setProfileForm({
                              full_name: profile.full_name ?? "",
                              date_of_birth: profile.date_of_birth ?? "",
                              gender: profile.gender ?? "",
                              city: profile.city ?? "",
                              education: profile.education ?? "",
                              profession: profile.profession ?? "",
                              about_me: profile.about_me ?? "",
                            });

                            setSaveMessage("");
                            setSaveError("");
                            setIsEditing(true);
                          }}
                        >
                          Edit Profile
                        </button>

                        <button
                          className="profile-secondary"
                          type="button"
                          onClick={loadProfile}
                          disabled={profileLoading}
                        >
                          Refresh Profile
                        </button>
                      </div>
                    </>
                  )}

                  {profile && isEditing && (
                    <form
                      className="profile-editor"
                      onSubmit={handleSaveProfile}
                    >
                      <div className="profile-editor-heading">
                        <h3>Edit Profile</h3>
                        <p>Update your details and save your changes.</p>
                      </div>

                      <div className="profile-form-grid">
                        <label className="profile-form-field">
                          Full Name *
                          <input
                            type="text"
                            name="full_name"
                            value={profileForm.full_name}
                            onChange={handleFormChange}
                            maxLength={150}
                            required
                          />
                        </label>

                        <label className="profile-form-field">
                          Date of Birth
                          <input
                            type="date"
                            name="date_of_birth"
                            value={profileForm.date_of_birth}
                            max={new Date().toISOString().slice(0, 10)}
                            onChange={handleFormChange}
                          />
                        </label>

                        <label className="profile-form-field">
                          Gender
                          <select
                            name="gender"
                            value={profileForm.gender}
                            onChange={handleFormChange}
                          >
                            <option value="">Select gender</option>
                            <option value="male">Male</option>
                            <option value="female">Female</option>
                            <option value="other">Other</option>
                          </select>
                        </label>

                        <label className="profile-form-field">
                          City
                          <input
                            type="text"
                            name="city"
                            value={profileForm.city}
                            onChange={handleFormChange}
                            maxLength={100}
                          />
                        </label>

                        <label className="profile-form-field">
                          Education
                          <input
                            type="text"
                            name="education"
                            value={profileForm.education}
                            onChange={handleFormChange}
                            maxLength={150}
                          />
                        </label>

                        <label className="profile-form-field">
                          Profession
                          <input
                            type="text"
                            name="profession"
                            value={profileForm.profession}
                            onChange={handleFormChange}
                            maxLength={150}
                          />
                        </label>

                        <label className="profile-form-field profile-form-full">
                          About Me
                          <textarea
                            name="about_me"
                            value={profileForm.about_me}
                            onChange={handleFormChange}
                            rows={5}
                            placeholder="Write something about yourself..."
                          />
                        </label>
                      </div>

                      {saveError && (
                        <div
                          className="profile-message profile-error"
                          role="alert"
                        >
                          {saveError}
                        </div>
                      )}

                      {saveMessage && (
                        <div
                          className="profile-message profile-success"
                          role="status"
                        >
                          {saveMessage}
                        </div>
                      )}

                      <div className="profile-action-row">
                        <button
                          className="dashboard-primary"
                          type="submit"
                          disabled={savingProfile}
                        >
                          {savingProfile ? "Saving..." : "Save Changes"}
                        </button>

                        <button
                          className="profile-secondary"
                          type="button"
                          disabled={savingProfile}
                          onClick={() => {
                            setProfileForm({
                              full_name: profile.full_name ?? "",
                              date_of_birth: profile.date_of_birth ?? "",
                              gender: profile.gender ?? "",
                              city: profile.city ?? "",
                              education: profile.education ?? "",
                              profession: profile.profession ?? "",
                              about_me: profile.about_me ?? "",
                            });

                            setSaveError("");
                            setSaveMessage("");
                            setIsEditing(false);
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </form>
                  )}

                  {/* MY PROFILE PHOTO GALLERY */}
                  {profile && (
                    <div className="photo-upload-panel">
                      <div>
                        <h3>Profile Photo Gallery</h3>
                        <p>
                          Upload multiple JPG, PNG or WEBP photos. Maximum size:
                          5 MB per photo.
                        </p>
                      </div>

                      {loadingPhoto && (
                        <p className="profile-subtitle" role="status">
                          Loading your photo gallery...
                        </p>
                      )}

                      {!loadingPhoto && myPhotos.length > 0 && (
                        <>
                          <h4 style={{ marginTop: "18px" }}>
                            Your Photos ({myPhotos.length})
                          </h4>

                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns:
                                "repeat(auto-fill, minmax(130px, 1fr))",
                              gap: "14px",
                              margin: "16px 0",
                            }}
                          >
                            {myPhotos.map((photo) => (
                              <div
                                key={photo.id}
                                style={{
                                  position: "relative",
                                  borderRadius: "12px",
                                  overflow: "hidden",
                                  border: photo.is_primary
                                    ? "2px solid #d94672"
                                    : "1px solid #e5e7eb",
                                  background: "#f8f8f8",
                                }}
                              >
                                <img
                                  src={photo.image_url}
                                  alt="My gallery"
                                  style={{
                                    width: "100%",
                                    height: "150px",
                                    objectFit: "cover",
                                    display: "block",
                                  }}
                                />

                                {photo.is_primary && (
                                  <span
                                    style={{
                                      display: "block",
                                      padding: "6px",
                                      textAlign: "center",
                                      fontSize: "12px",
                                      fontWeight: "600",
                                      color: "#d94672",
                                    }}
                                  >
                                    Primary Photo
                                  </span>
                                )}

                                <button
                                  type="button"
                                  className="match-reject-button"
                                  style={{
                                    width: "100%",
                                    borderRadius: 0,
                                  }}
                                  disabled={
                                    String(deletingPhotoId) === String(photo.id)
                                  }
                                  onClick={() =>
                                    handleDeleteProfilePhoto(photo)
                                  }
                                >
                                  {String(deletingPhotoId) === String(photo.id)
                                    ? "Deleting..."
                                    : "Delete Photo"}
                                </button>
                              </div>
                            ))}
                          </div>
                        </>
                      )}

                      {!loadingPhoto && myPhotos.length === 0 && (
                        <p className="profile-subtitle">
                          No photos uploaded yet.
                        </p>
                      )}

                      {selectedPhoto && (
                        <div style={{ margin: "16px 0" }}>
                          <p className="profile-subtitle">
                            Preview: {selectedPhoto.name}
                          </p>

                          {photoPreview && (
                            <div className="photo-preview">
                              <img src={photoPreview} alt="Selected preview" />
                            </div>
                          )}
                        </div>
                      )}

                      <label className="profile-form-field photo-file-field">
                        Add Photo
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/webp"
                          onChange={handlePhotoSelection}
                        />
                      </label>

                      {photoError && (
                        <div
                          className="profile-message profile-error"
                          role="alert"
                        >
                          {photoError}
                        </div>
                      )}

                      {photoMessage && (
                        <div
                          className="profile-message profile-success"
                          role="status"
                        >
                          {photoMessage}
                        </div>
                      )}

                      <button
                        className="dashboard-primary"
                        type="button"
                        onClick={handlePhotoUpload}
                        disabled={!selectedPhoto || uploadingPhoto}
                      >
                        {uploadingPhoto ? "Uploading..." : "Upload Photo"}
                      </button>
                    </div>
                  )}
                </>
              )}
            </section>
          )}

          {/* MATCHES PAGE */}
          {page === "matches" && (
            <section className="dashboard-profile matches-page">
              <div className="matches-heading">
                <div>
                  <p className="dashboard-eyebrow">YOUR CONNECTIONS</p>
                  <h2>Matches & Requests</h2>
                  <p className="profile-subtitle">
                    Discover profiles, send requests and manage your
                    connections.
                  </p>
                </div>

                <button
                  className="profile-secondary"
                  type="button"
                  onClick={() => loadMatches("matches")}
                  disabled={
                    matchesLoading ||
                    profilesLoading ||
                    matchActionLoading !== null ||
                    connectionActionLoading !== null ||
                    sendingRequestTo !== null
                  }
                >
                  {matchesLoading || profilesLoading
                    ? "Refreshing..."
                    : "Refresh"}
                </button>
              </div>

              {matchesLoading && (
                <div className="profile-message" role="status">
                  Loading your matches...
                </div>
              )}

              {matchesError && (
                <div className="profile-message profile-error" role="alert">
                  {matchesError}
                </div>
              )}

              {matchesMessage && (
                <div className="profile-message profile-success" role="status">
                  {matchesMessage}
                </div>
              )}

              {/* DISCOVER PROFILES */}
              <div className="matches-discover">
                <h3>Discover Profiles</h3>

                <p className="profile-subtitle">
                  Explore other members and send a match request.
                </p>

                {profilesLoading && (
                  <div className="profile-message" role="status">
                    Loading profiles...
                  </div>
                )}

                {profilesError && (
                  <div className="profile-message profile-error" role="alert">
                    {profilesError}
                  </div>
                )}

                {!profilesLoading &&
                  !profilesError &&
                  availableProfiles.length === 0 && (
                    <p className="profile-subtitle">
                      No other profiles are available in your tenant.
                    </p>
                  )}

                {!profilesLoading && availableProfiles.length > 0 && (
                  <div className="matches-list">
                    {availableProfiles.map((candidate) => {
                      const alreadyRequested = requestedProfileIds.includes(
                        String(candidate.id),
                      );

                      const isSending =
                        String(sendingRequestTo) === String(candidate.id);

                      const isBlocking =
                        connectionActionLoading === `block-${candidate.id}`;

                      return (
                        <article className="match-card" key={candidate.id}>
                          <div className="match-avatar" aria-hidden="true">
                            {(candidate.full_name || "M")
                              .charAt(0)
                              .toUpperCase()}
                          </div>

                          <div className="match-card-content">
                            <div className="match-card-top">
                              <div>
                                <h3>{candidate.full_name || "Member"}</h3>

                                <p>
                                  {[
                                    candidate.city,
                                    candidate.profession,
                                    candidate.education,
                                  ]
                                    .filter(Boolean)
                                    .join(" • ") || "Profile available"}
                                </p>
                              </div>
                            </div>

                            <div className="match-actions">
                              <button
                                className="dashboard-primary"
                                type="button"
                                disabled={
                                  alreadyRequested ||
                                  sendingRequestTo !== null ||
                                  connectionActionLoading !== null
                                }
                                onClick={() => handleSendMatchRequest(candidate)}
                              >
                                {isSending
                                  ? "Sending..."
                                  : alreadyRequested
                                    ? "Request Sent"
                                    : "Send Request"}
                              </button>

                              <button
                                className="match-reject-button"
                                type="button"
                                disabled={
                                  connectionActionLoading !== null ||
                                  sendingRequestTo !== null
                                }
                                onClick={() =>
                                  handleBlockProfile(
                                    candidate.id,
                                    candidate.full_name || "this member",
                                  )
                                }
                              >
                                {isBlocking ? "Blocking..." : "Block"}
                              </button>
                            </div>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* EXISTING REQUESTS */}
              <div className="matches-existing">
                <h3>Your Requests</h3>

                {!matchesLoading &&
                  !matchesError &&
                  displayedMatches.length === 0 && (
                    <div className="matches-empty">
                      <div className="matches-empty-icon">♡</div>
                      <h3>No match requests yet</h3>
                      <p>Your sent and received requests will appear here.</p>
                    </div>
                  )}

                {!matchesLoading && displayedMatches.length > 0 && (
                  <div className="matches-list">
                    {displayedMatches.map((match) => {
                      const isIncoming =
                        String(match.receiver) === String(currentProfileId);

                      const isPending = match.status === "pending";
                      const isAccepted = match.status === "accepted";

                      const otherProfileId = getOtherProfileId(
                        match,
                        currentProfileId,
                      );

                      const otherPersonName = getOtherPersonName(match);

                      const isWorking =
                        String(matchActionLoading) === String(match.id);

                      const isBlocking =
                        connectionActionLoading === `block-${otherProfileId}`;

                      const isUnfriending =
                        connectionActionLoading === `unfriend-${otherProfileId}`;

                      const isRemoving =
                        connectionActionLoading === `remove-${otherProfileId}`;

                      return (
                        <article className="match-card" key={match.id}>
                          <div className="match-avatar" aria-hidden="true">
                            {otherPersonName.charAt(0).toUpperCase()}
                          </div>

                          <div className="match-card-content">
                            <div className="match-card-top">
                              <div>
                                <h3>{otherPersonName}</h3>
                                <p>{getRequestDirection(match)}</p>
                              </div>

                              <span
                                className={`match-status match-status-${match.status}`}
                              >
                                {getStatusLabel(match.status)}
                              </span>
                            </div>

                            <p className="match-date">
                              Requested: {formatDate(match.created_at)}
                            </p>

                            {isIncoming && isPending && (
                              <div className="match-actions">
                                <button
                                  className="match-accept-button"
                                  type="button"
                                  disabled={
                                    matchActionLoading !== null ||
                                    connectionActionLoading !== null
                                  }
                                  onClick={() =>
                                    handleMatchStatus(match.id, "accepted")
                                  }
                                >
                                  {isWorking ? "Updating..." : "Accept"}
                                </button>

                                <button
                                  className="match-reject-button"
                                  type="button"
                                  disabled={
                                    matchActionLoading !== null ||
                                    connectionActionLoading !== null
                                  }
                                  onClick={() =>
                                    handleMatchStatus(match.id, "rejected")
                                  }
                                >
                                  {isWorking ? "Updating..." : "Reject"}
                                </button>

                                <button
                                  className="match-reject-button"
                                  type="button"
                                  disabled={connectionActionLoading !== null}
                                  onClick={() =>
                                    handleBlockProfile(
                                      otherProfileId,
                                      otherPersonName,
                                    )
                                  }
                                >
                                  {isBlocking ? "Blocking..." : "Block"}
                                </button>
                              </div>
                            )}

                            {!isIncoming && isPending && (
                              <>
                                <p className="match-help-text">
                                  Waiting for the other member to respond.
                                </p>

                                <div className="match-actions">
                                  <button
                                    className="match-reject-button"
                                    type="button"
                                    disabled={connectionActionLoading !== null}
                                    onClick={() =>
                                      handleBlockProfile(
                                        otherProfileId,
                                        otherPersonName,
                                      )
                                    }
                                  >
                                    {isBlocking ? "Blocking..." : "Block"}
                                  </button>
                                </div>
                              </>
                            )}

                            {isAccepted && (
                              <div
                                className="match-actions"
                                style={{
                                  marginTop: "12px",
                                  display: "flex",
                                  flexWrap: "wrap",
                                  gap: "10px",
                                }}
                              >
                                <button
                                  className="dashboard-primary"
                                  type="button"
                                  disabled={connectionActionLoading !== null}
                                  onClick={() => handleOpenChat(match)}
                                >
                                  Open Chat
                                </button>

                                <button
                                  className="profile-secondary"
                                  type="button"
                                  disabled={connectionActionLoading !== null}
                                  onClick={() =>
                                    handleViewPrivatePhotos(match)
                                  }
                                >
                                  View Private Photos
                                </button>

                                <button
                                  className="match-reject-button"
                                  type="button"
                                  disabled={connectionActionLoading !== null}
                                  onClick={() =>
                                    handleUnfriendProfile(
                                      otherProfileId,
                                      otherPersonName,
                                    )
                                  }
                                >
                                  {isUnfriending ? "Unfriending..." : "Unfriend"}
                                </button>

                                <button
                                  className="profile-secondary"
                                  type="button"
                                  disabled={connectionActionLoading !== null}
                                  onClick={() =>
                                    handleRemoveConnection(
                                      otherProfileId,
                                      otherPersonName,
                                    )
                                  }
                                >
                                  {isRemoving ? "Removing..." : "Remove"}
                                </button>

                                <button
                                  className="match-reject-button"
                                  type="button"
                                  disabled={connectionActionLoading !== null}
                                  onClick={() =>
                                    handleBlockProfile(
                                      otherProfileId,
                                      otherPersonName,
                                    )
                                  }
                                >
                                  {isBlocking ? "Blocking..." : "Block"}
                                </button>
                              </div>
                            )}

                            {!isAccepted && !isPending && (
                              <div className="match-actions">
                                <button
                                  className="match-reject-button"
                                  type="button"
                                  disabled={connectionActionLoading !== null}
                                  onClick={() =>
                                    handleBlockProfile(
                                      otherProfileId,
                                      otherPersonName,
                                    )
                                  }
                                >
                                  {isBlocking ? "Blocking..." : "Block"}
                                </button>
                              </div>
                            )}
                          </div>
                        </article>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* BLOCKED PROFILES */}
              <div className="matches-existing">
                <h3>Blocked Profiles</h3>

                <p className="profile-subtitle">
                  Manage profiles that you have blocked. You can unblock them
                  whenever you want.
                </p>

                {blockedProfilesLoading && (
                  <div className="profile-message" role="status">
                    Loading blocked profiles...
                  </div>
                )}

                {blockedProfilesError && (
                  <div className="profile-message profile-error" role="alert">
                    {blockedProfilesError}
                  </div>
                )}

                {!blockedProfilesLoading &&
                  !blockedProfilesError &&
                  blockedProfiles.length === 0 && (
                    <p className="profile-subtitle">
                      You have not blocked any profiles.
                    </p>
                  )}

                {!blockedProfilesLoading && blockedProfiles.length > 0 && (
                  <div className="matches-list">
                    {blockedProfiles.map((blockedProfile) => {
                      const isUnblocking =
                        connectionActionLoading ===
                        `unblock-${blockedProfile.id}`;

                      return (
                        <article
                          className="match-card"
                          key={blockedProfile.id}
                        >
                          <div className="match-avatar" aria-hidden="true">
                            {(blockedProfile.full_name || "M")
                              .charAt(0)
                              .toUpperCase()}
                          </div>

                          <div className="match-card-content">
                            <div className="match-card-top">
                              <div>
                                <h3>
                                  {blockedProfile.full_name || "Member"}
                                </h3>

                                <p>
                                  Blocked on:{" "}
                                  {formatDate(
                                    blockedProfile.blocked_at ||
                                      blockedProfile.created_at,
                                  )}
                                </p>
                              </div>

                              <span className="match-status match-status-rejected">
                                Blocked
                              </span>
                            </div>

                            <div className="match-actions">
                              <button
                                className="profile-secondary"
                                type="button"
                                disabled={connectionActionLoading !== null}
                                onClick={() =>
                                  handleUnblockProfile(
                                    blockedProfile.id,
                                    blockedProfile.full_name || "this member",
                                  )
                                }
                              >
                                {isUnblocking ? "Unblocking..." : "Unblock"}
                              </button>
                            </div>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                )}
              </div>
            </section>
          )}

          {/* REQUESTS PAGE */}
          {page === "requests" && (
            <section className="dashboard-profile matches-page">
              <div className="matches-heading">
                <div>
                  <p className="dashboard-eyebrow">YOUR CONNECTIONS</p>
                  <h2>Incoming Match Requests</h2>
                  <p className="profile-subtitle">
                    View and respond to requests received from other members.
                  </p>
                </div>

                <button
                  className="profile-secondary"
                  type="button"
                  onClick={() => loadMatches("requests")}
                  disabled={
                    matchesLoading ||
                    profilesLoading ||
                    matchActionLoading !== null ||
                    connectionActionLoading !== null
                  }
                >
                  {matchesLoading ? "Refreshing..." : "Refresh"}
                </button>
              </div>

              {matchesLoading && (
                <div className="profile-message" role="status">
                  Loading incoming requests...
                </div>
              )}

              {matchesError && (
                <div className="profile-message profile-error" role="alert">
                  {matchesError}
                </div>
              )}

              {matchesMessage && (
                <div className="profile-message profile-success" role="status">
                  {matchesMessage}
                </div>
              )}

              {!matchesLoading &&
                !matchesError &&
                incomingRequests.length === 0 && (
                  <div className="matches-empty">
                    <div className="matches-empty-icon">♡</div>
                    <h3>No incoming requests</h3>
                    <p>
                      When someone sends you a match request, it will appear
                      here.
                    </p>
                  </div>
                )}

              {!matchesLoading && incomingRequests.length > 0 && (
                <div className="matches-list">
                  {incomingRequests.map((match) => {
                    const isPending = match.status === "pending";
                    const isAccepted = match.status === "accepted";

                    const otherProfileId = getOtherProfileId(
                      match,
                      currentProfileId,
                    );

                    const otherPersonName = getOtherPersonName(match);

                    const isWorking =
                      String(matchActionLoading) === String(match.id);

                    const isBlocking =
                      connectionActionLoading === `block-${otherProfileId}`;

                    const isUnfriending =
                      connectionActionLoading === `unfriend-${otherProfileId}`;

                    const isRemoving =
                      connectionActionLoading === `remove-${otherProfileId}`;

                    return (
                      <article className="match-card" key={match.id}>
                        <div className="match-avatar" aria-hidden="true">
                          {otherPersonName.charAt(0).toUpperCase()}
                        </div>

                        <div className="match-card-content">
                          <div className="match-card-top">
                            <div>
                              <h3>{otherPersonName}</h3>
                              <p>Received request</p>
                            </div>

                            <span
                              className={`match-status match-status-${match.status}`}
                            >
                              {getStatusLabel(match.status)}
                            </span>
                          </div>

                          <p className="match-date">
                            Requested: {formatDate(match.created_at)}
                          </p>

                          {isPending && (
                            <div className="match-actions">
                              <button
                                className="match-accept-button"
                                type="button"
                                disabled={
                                  matchActionLoading !== null ||
                                  connectionActionLoading !== null
                                }
                                onClick={() =>
                                  handleMatchStatus(match.id, "accepted")
                                }
                              >
                                {isWorking ? "Updating..." : "Accept"}
                              </button>

                              <button
                                className="match-reject-button"
                                type="button"
                                disabled={
                                  matchActionLoading !== null ||
                                  connectionActionLoading !== null
                                }
                                onClick={() =>
                                  handleMatchStatus(match.id, "rejected")
                                }
                              >
                                {isWorking ? "Updating..." : "Reject"}
                              </button>

                              <button
                                className="match-reject-button"
                                type="button"
                                disabled={connectionActionLoading !== null}
                                onClick={() =>
                                  handleBlockProfile(
                                    otherProfileId,
                                    otherPersonName,
                                  )
                                }
                              >
                                {isBlocking ? "Blocking..." : "Block"}
                              </button>
                            </div>
                          )}

                          {isAccepted && (
                            <div
                              className="match-actions"
                              style={{
                                display: "flex",
                                flexWrap: "wrap",
                                gap: "10px",
                              }}
                            >
                              <button
                                className="dashboard-primary"
                                type="button"
                                disabled={connectionActionLoading !== null}
                                onClick={() => handleOpenChat(match)}
                              >
                                Open Chat
                              </button>

                              <button
                                className="profile-secondary"
                                type="button"
                                disabled={connectionActionLoading !== null}
                                onClick={() =>
                                  handleViewPrivatePhotos(match)
                                }
                              >
                                View Private Photos
                              </button>

                              <button
                                className="match-reject-button"
                                type="button"
                                disabled={connectionActionLoading !== null}
                                onClick={() =>
                                  handleUnfriendProfile(
                                    otherProfileId,
                                    otherPersonName,
                                  )
                                }
                              >
                                {isUnfriending ? "Unfriending..." : "Unfriend"}
                              </button>

                              <button
                                className="profile-secondary"
                                type="button"
                                disabled={connectionActionLoading !== null}
                                onClick={() =>
                                  handleRemoveConnection(
                                    otherProfileId,
                                    otherPersonName,
                                  )
                                }
                              >
                                {isRemoving ? "Removing..." : "Remove"}
                              </button>

                              <button
                                className="match-reject-button"
                                type="button"
                                disabled={connectionActionLoading !== null}
                                onClick={() =>
                                  handleBlockProfile(
                                    otherProfileId,
                                    otherPersonName,
                                  )
                                }
                              >
                                {isBlocking ? "Blocking..." : "Block"}
                              </button>
                            </div>
                          )}

                          {!isPending && !isAccepted && (
                            <div className="match-actions">
                              <button
                                className="match-reject-button"
                                type="button"
                                disabled={connectionActionLoading !== null}
                                onClick={() =>
                                  handleBlockProfile(
                                    otherProfileId,
                                    otherPersonName,
                                  )
                                }
                              >
                                {isBlocking ? "Blocking..." : "Block"}
                              </button>
                            </div>
                          )}
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          {/* COMPATIBILITY PAGE */}
          {page === "compatibility" && (
            <CompatibilityScores
              onExploreMatches={() => loadMatches("matches")}
            />
          )}

          {/* SUBSCRIPTION & BILLING PAGE - HOST AND END USER */}
          {page === "subscription" && canAccessSubscription && (
            <Subscription />
          )}

          {/* SETTINGS PAGE */}
          {page === "settings" && (
            <>
              <Settings username={username} onLogout={onLogout} />
              <ThemeSettings
                theme={theme}
                onThemeChange={onThemeChange}
              />
            </>
          )}

          <footer className="dashboard-footer">
            Smart Matrimonial SaaS Platform
          </footer>
        </main>
      </div>

      {/* PRIVATE PHOTO GALLERY MODAL */}
      {showPrivateGallery && (
        <div
          role="presentation"
          onClick={closePrivateGallery}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            background: "rgba(0, 0, 0, 0.65)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            padding: "20px",
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="private-gallery-title"
            onClick={(event) => event.stopPropagation()}
            style={{
              background: "#fff",
              borderRadius: "16px",
              padding: "24px",
              width: "100%",
              maxWidth: "700px",
              maxHeight: "85vh",
              overflowY: "auto",
              position: "relative",
            }}
          >
            <button
              type="button"
              onClick={closePrivateGallery}
              aria-label="Close private gallery"
              style={{
                position: "absolute",
                top: "14px",
                right: "16px",
                border: "none",
                background: "transparent",
                fontSize: "25px",
                cursor: "pointer",
              }}
            >
              ×
            </button>

            <h2 id="private-gallery-title">
              {privatePhotosMember}'s Private Photos
            </h2>

            <p className="profile-subtitle">
              These photos are available because this match is accepted.
            </p>

            {privatePhotosLoading && (
              <p className="profile-message" role="status">
                Loading private photos...
              </p>
            )}

            {privatePhotosError && (
              <div className="profile-message profile-error" role="alert">
                {privatePhotosError}
              </div>
            )}

            {!privatePhotosLoading &&
              !privatePhotosError &&
              privatePhotos.length === 0 && (
                <p className="profile-subtitle">
                  This member has not uploaded any photos yet.
                </p>
              )}

            {!privatePhotosLoading &&
              !privatePhotosError &&
              privatePhotos.length > 0 && (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fill, minmax(150px, 1fr))",
                    gap: "14px",
                    marginTop: "20px",
                  }}
                >
                  {privatePhotos.map((photo) => (
                    <div
                      key={photo.id}
                      style={{
                        borderRadius: "12px",
                        overflow: "hidden",
                        background: "#f5f5f5",
                      }}
                    >
                      <img
                        src={photo.image_url}
                        alt={`${privatePhotosMember}'s private photo`}
                        style={{
                          display: "block",
                          width: "100%",
                          height: "190px",
                          objectFit: "cover",
                        }}
                      />

                      {photo.is_primary && (
                        <p
                          style={{
                            textAlign: "center",
                            padding: "6px",
                            margin: 0,
                            fontSize: "12px",
                            fontWeight: "600",
                          }}
                        >
                          Primary Photo
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
          </section>
        </div>
      )}

      {/* CHAT MODAL */}
      {chatTarget && (
        <Chat
          profileId={chatTarget.profileId}
          profileName={chatTarget.profileName}
          currentProfileId={currentProfileId}
          presenceStatus={presenceStatuses[String(chatTarget.profileId)] || null}
          onClose={closeChat}
        />
      )}
    </>
  );
}

export default Dashboard;
