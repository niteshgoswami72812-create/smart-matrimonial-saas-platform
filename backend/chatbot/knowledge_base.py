KNOWLEDGE_BASE = [
    {
        "id": "display_theme",
        "title": "Display Theme, Dark Mode and Light Mode",
        "content": """
        Display Theme is an implemented feature of the Smart Matrimonial
        Platform. Users can change the dashboard appearance between Light
        Mode and Dark Mode.

        How to change display theme:
        1. Log in to the Smart Matrimonial Platform.
        2. Open the Dashboard.
        3. Click Settings in the dashboard sidebar.
        4. Find the Display Theme section.
        5. Select Light for light mode or Dark for dark mode.

        The selected theme is applied to the dashboard. The application
        saves the selected theme in browser localStorage using the key
        app_theme. When the application reloads, it reads the saved theme
        and restores the selected appearance.

        Common questions and keywords:
        How to change display theme, how to change theme, change dashboard
        appearance, switch theme, dark mode, enable dark mode, turn on dark
        mode, light mode, enable light mode, switch to light theme,
        theme settings, where is theme setting, theme kaise change karein,
        dark mode kaise on karein, light mode kaise lagayein.
        """
    },
    {
        "id": "dashboard_navigation",
        "title": "Dashboard Navigation and Available Pages",
        "content": """
        The Smart Matrimonial Platform dashboard contains these main
        navigation pages:

        1. Dashboard: Main dashboard and photo posts feed.
        2. My Profile: View and update the user's matrimonial profile,
        manage profile information and profile photos.
        3. Matches: Discover profiles, send match requests, manage
        connections and blocked profiles.
        4. Requests: View incoming and outgoing match requests and
        respond to pending requests.
        5. Compatibility: View compatibility scores and match explanations.
        6. Settings: Manage account information, privacy preferences,
        notification preferences and display theme.

        Users can navigate between these sections using the dashboard
        sidebar. Logout is also available from the dashboard.
        """
    },
    {
        "id": "account_settings",
        "title": "Account Settings and Account Management",
        "content": """
        The Settings page contains Account Information, Privacy Settings,
        Notification Preferences, Change Password, Delete Account and
        Logout sections.

        Account Information displays the available username, email address,
        account type and active session status using the account API.

        Change Password is currently not connected to a backend password
        change API. The password change operation is not active.

        Delete Account is currently not connected to a backend account
        deletion API. The account deletion operation is not active.
        The confirmation dialog does not delete account data.

        Users can log out from the Settings page. Logout clears the saved
        access token, refresh token and username from browser localStorage.
        """
    },
    {
        "id": "privacy_notification_preferences",
        "title": "Privacy and Notification Preferences",
        "content": """
        The Settings page contains Privacy Settings and Notification
        Preferences.

        Privacy preference options:
        1. Profile Visibility.
        2. Online Status.
        3. Private Photo Access.

        Notification preference options:
        1. Email Notifications.
        2. Match Request Notifications.
        3. Chat Notifications.

        Users can select or deselect these options and save their
        preferences. Preferences are saved in browser localStorage
        using a username-specific storage key.

        Important limitation: These privacy and notification preferences
        are currently stored only in the browser. They do not yet change
        backend profile visibility, private photo permissions or actual
        email and in-app notification delivery.

        Do not tell users that these preference switches enforce backend
        privacy permissions or send actual notifications.
        """
    },
    {
        "id": "online_presence",
        "title": "Online Offline Status and Last Seen",
        "content": """
        The platform includes online presence functionality for accepted
        matches. Users can see the online or offline status and last seen
        information of their accepted matches.

        Presence updates use an authenticated WebSocket connection.
        The dashboard receives presence snapshots and real-time presence
        updates. The WebSocket connection uses the user's authentication
        token and sends periodic heartbeat messages.

        Presence information is restricted to accepted matches rather
        than being available to every platform user.

        Common questions:
        How can I see whether a match is online?
        How does online status work?
        What is last seen?
        How can I check when a match was last active?
        """
    },
    {
        "id": "audio_video_calling",
        "title": "Voice Calling and Video Calling",
        "content": """
        The platform includes voice calling and video calling functionality
        for accepted matches. Calling is intended only between users who
        have an accepted match and belong to the same tenant.

        The calling feature uses WebRTC for audio and video communication
        and WebSocket signaling for call setup and call events.

        Users need to grant browser microphone permission for voice calls
        and microphone plus camera permission for video calls.

        The calling interface supports starting a call, accepting an
        incoming call, rejecting a call, ending a call, muting the
        microphone and turning the camera on or off.

        Camera and microphone access requires HTTPS or localhost in
        supported browsers.

        Local two-user calling has been tested successfully. This does
        not guarantee production-ready reliability on every network.
        Production deployment may require TURN configuration, secure
        HTTPS/WSS, Redis and wider network testing.

        Common questions:
        How to make a voice call?
        How to start a video call?
        Can I call a pending match?
        Can I call an unaccepted profile?

        Calls are restricted to accepted matches.
        """
    },
    {
        "id": "subscription_plans",
        "title": "Subscription Plans and Tenant Subscriptions",
        "content": """
        The backend includes subscription plan and tenant subscription
        functionality.

        Available subscription plan types are Free, Basic and Premium.

        A subscription plan stores its name, price, duration in days,
        maximum profile limit and active status.

        Authenticated users can retrieve active subscription plans.
        Super Admin can retrieve all plans and create subscription plans.
        Non-admin users can see active plans only.

        A tenant subscription record is associated with a tenant and
        a subscription plan. It stores the subscription status, start
        date and end date.

        Supported subscription statuses are pending, active, expired
        and cancelled.

        Do not invent plan prices, payment details or payment gateway
        features. Only provide exact plan prices when they are available
        from the platform's current data.
        """
    },
    {
        "id": "signup_login_session",
        "title": "Signup, Login, JWT Authentication and Session",
        "content": """
        New users can register using the signup form with username,
        email address and password. Signup requires acceptance of
        Terms and Conditions and Privacy Policy.

        After successful signup, users can log in using their account
        credentials. The backend uses JWT access and refresh tokens
        for authentication.

        Protected APIs require a valid authenticated access token.
        The frontend automatically attaches the access token to API
        requests.

        The application can restore a saved login session after a
        browser refresh. If the access token expires, the application
        can use the refresh token to request a new access token.

        If an authenticated account does not yet have a matrimonial
        profile, the application routes the user to the Create Profile
        screen. After profile creation, the user can access the dashboard.

        Logout clears the locally stored authentication tokens.
        """
    }
]