from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db.models import Q
from django.utils import timezone

from accounts.tenant_utils import get_user_tenant
from .models import Profile, Match, ProfileBlock, RemovedProfile


@database_sync_to_async
def get_call_connection_details(user, target_profile_id):

    if not user or not user.is_authenticated:
        return None

    tenant = get_user_tenant(user)

    # No tenant means no end-user calling access.
    if tenant is None:
        return None

    current_profile = Profile.objects.filter(
        user=user,
        tenant=tenant,
    ).first()

    target_profile = (
        Profile.objects
        .select_related("user")
        .filter(
            id=target_profile_id,
            tenant=tenant,
        )
        .first()
    )

    if not current_profile or not target_profile:
        return None

    if current_profile.id == target_profile.id:
        return None

    if not target_profile.user.is_active:
        return None

    accepted_match = Match.objects.filter(
        Q(
            sender=current_profile,
            receiver=target_profile,
        )
        | Q(
            sender=target_profile,
            receiver=current_profile,
        ),
        status="accepted",
        sender__tenant=tenant,
        receiver__tenant=tenant,
    ).exists()

    if not accepted_match:
        return None

    profile_ids = sorted([
        current_profile.id,
        target_profile.id,
    ])

    return {
        "current_profile_id": current_profile.id,
        "target_profile_id": target_profile.id,
        "current_profile_name": current_profile.full_name,
        "group_name": f"call_{profile_ids[0]}_{profile_ids[1]}",
    }


class CallConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):

        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        target_profile_id = self.scope[
            "url_route"
        ]["kwargs"].get("profile_id")

        details = await get_call_connection_details(
            user,
            target_profile_id,
        )

        if not details:
            await self.close(code=4403)
            return

        self.current_profile_id = details["current_profile_id"]
        self.target_profile_id = details["target_profile_id"]
        self.current_profile_name = details["current_profile_name"]
        self.group_name = details["group_name"]

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):

        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):

        if not isinstance(content, dict):
            await self.send_json({
                "type": "error",
                "message": "Invalid message format.",
            })
            return

        message_type = content.get("type")
        data = content.get("data", {})

        allowed_types = {
            "call_offer",
            "call_answer",
            "ice_candidate",
            "call_reject",
            "call_end",
        }

        if message_type not in allowed_types:
            await self.send_json({
                "type": "error",
                "message": "Unsupported call event.",
            })
            return

        if not isinstance(data, dict):
            await self.send_json({
                "type": "error",
                "message": "Invalid event data.",
            })
            return

        # Validate audio/video call offer.
        if message_type == "call_offer":

            call_type = data.get("call_type")
            sdp = data.get("sdp")

            if call_type not in ["audio", "video"]:
                return

            if not isinstance(sdp, str) or len(sdp) > 20000:
                return

        # Validate WebRTC answer.
        elif message_type == "call_answer":

            sdp = data.get("sdp")

            if not isinstance(sdp, str) or len(sdp) > 20000:
                return

        # Validate WebRTC ICE candidate.
        elif message_type == "ice_candidate":

            candidate = data.get("candidate")

            if candidate is not None:

                if not isinstance(candidate, dict):
                    return

                candidate_value = candidate.get("candidate", "")

                if not isinstance(candidate_value, str):
                    return

                if len(candidate_value) > 4096:
                    return

        elif message_type in ["call_reject", "call_end"]:
            data = {}

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "call.signal",
                "sender_profile_id": self.current_profile_id,
                "sender_name": self.current_profile_name,
                "message_type": message_type,
                "data": data,
            },
        )

    async def call_signal(self, event):

        # Do not send the event back to the sender.
        if event["sender_profile_id"] == self.current_profile_id:
            return

        await self.send_json({
            "type": event["message_type"],
            "from_profile_id": event["sender_profile_id"],
            "from_name": event["sender_name"],
            "data": event["data"],
        })

# =========================================================
# ONLINE / OFFLINE PRESENCE SYSTEM
# =========================================================

def _get_presence_details(user):

    if not user or not user.is_authenticated:
        return None

    tenant = get_user_tenant(user)

    if tenant is None:
        return None

    current_profile = Profile.objects.filter(
        user=user,
        tenant=tenant,
    ).first()

    if not current_profile:
        return None

    # Only accepted matches from the same tenant.
    match_rows = Match.objects.filter(
        Q(sender_id=current_profile.id)
        | Q(receiver_id=current_profile.id),
        status="accepted",
        sender__tenant_id=tenant.id,
        receiver__tenant_id=tenant.id,
    ).values_list("sender_id", "receiver_id")

    matched_ids = set()

    for sender_id, receiver_id in match_rows:
        other_id = (
            receiver_id
            if sender_id == current_profile.id
            else sender_id
        )

        if other_id != current_profile.id:
            matched_ids.add(other_id)

    if not matched_ids:
        return {
            "profile_id": current_profile.id,
            "tenant_id": tenant.id,
            "profile_name": current_profile.full_name,
            "matched_profile_ids": [],
        }

    # Exclude profiles blocked in either direction.
    blocked_pairs = ProfileBlock.objects.filter(
        tenant_id=tenant.id,
    ).filter(
        Q(
            blocker_id=current_profile.id,
            blocked_id__in=matched_ids,
        )
        | Q(
            blocked_id=current_profile.id,
            blocker_id__in=matched_ids,
        )
    ).values_list("blocker_id", "blocked_id")

    excluded_ids = set()

    for blocker_id, blocked_id in blocked_pairs:
        excluded_ids.add(
            blocked_id
            if blocker_id == current_profile.id
            else blocker_id
        )

    # Exclude profiles removed in either direction.
    removed_pairs = RemovedProfile.objects.filter(
        tenant_id=tenant.id,
    ).filter(
        Q(
            owner_id=current_profile.id,
            removed_profile_id__in=matched_ids,
        )
        | Q(
            removed_profile_id=current_profile.id,
            owner_id__in=matched_ids,
        )
    ).values_list("owner_id", "removed_profile_id")

    for owner_id, removed_profile_id in removed_pairs:
        excluded_ids.add(
            removed_profile_id
            if owner_id == current_profile.id
            else owner_id
        )

    allowed_ids = sorted(matched_ids - excluded_ids)

    return {
        "profile_id": current_profile.id,
        "tenant_id": tenant.id,
        "profile_name": current_profile.full_name,
        "matched_profile_ids": allowed_ids,
    }


@database_sync_to_async
def get_presence_connection_details(user):
    return _get_presence_details(user)


@database_sync_to_async
def get_allowed_presence_profile_ids(user):

    details = _get_presence_details(user)

    if not details:
        return []

    return details["matched_profile_ids"]


@database_sync_to_async
def get_presence_snapshot(profile_ids, tenant_id):

    profiles = Profile.objects.filter(
        id__in=profile_ids,
        tenant_id=tenant_id,
    ).values("id", "last_seen")

    return [
        {
            "profile_id": item["id"],
            "last_seen": (
                item["last_seen"].isoformat()
                if item["last_seen"]
                else None
            ),
        }
        for item in profiles
    ]


@database_sync_to_async
def update_profile_last_seen(profile_id, tenant_id):

    last_seen = timezone.now()

    Profile.objects.filter(
        id=profile_id,
        tenant_id=tenant_id,
    ).update(
        last_seen=last_seen,
    )

    return last_seen.isoformat()


class PresenceConsumer(AsyncJsonWebsocketConsumer):

    # Local single-process connection registry.
    # Production multi-worker setup should use shared Redis presence.

    active_connections = {}

    async def connect(self):

        self.profile_id = None
        self.tenant_id = None
        self.profile_name = None

        self.watched_profile_ids = set()
        self.watched_groups = set()

        self.is_registered = False

        user = self.scope.get("user")

        details = await get_presence_connection_details(user)

        if not details:
            await self.close(code=4403)
            return

        self.profile_id = details["profile_id"]
        self.tenant_id = details["tenant_id"]
        self.profile_name = details["profile_name"]

        self.watched_profile_ids = set(
            details["matched_profile_ids"]
        )

        self.watched_groups = {
            f"presence_profile_{profile_id}"
            for profile_id in self.watched_profile_ids
        }

        # Subscribe only to authorized accepted-match profiles.
        for group_name in self.watched_groups:
            await self.channel_layer.group_add(
                group_name,
                self.channel_name,
            )

        await self.accept()

        # Register this WebSocket connection.
        connections = self.active_connections.setdefault(
            self.profile_id,
            set(),
        )

        first_connection = len(connections) == 0

        connections.add(self.channel_name)
        self.is_registered = True

        # Send initial presence information for accepted matches.
        snapshot = await get_presence_snapshot(
            list(self.watched_profile_ids),
            self.tenant_id,
        )

        statuses = []

        for item in snapshot:

            other_id = item["profile_id"]

            is_online = bool(
                self.active_connections.get(other_id)
            )

            statuses.append({
                "profile_id": other_id,
                "is_online": is_online,
                "last_seen": (
                    None
                    if is_online
                    else item["last_seen"]
                ),
            })

        await self.send_json({
            "type": "presence_snapshot",
            "statuses": statuses,
        })

        # Notify accepted matches when this profile becomes online.
        if first_connection:

            await self.channel_layer.group_send(
                f"presence_profile_{self.profile_id}",
                {
                    "type": "presence.event",
                    "payload": {
                        "type": "presence_update",
                        "profile_id": self.profile_id,
                        "profile_name": self.profile_name,
                        "is_online": True,
                        "last_seen": None,
                    },
                },
            )

    async def disconnect(self, close_code):

        # Remove this connection from all watched groups.
        for group_name in list(self.watched_groups):

            await self.channel_layer.group_discard(
                group_name,
                self.channel_name,
            )

        self.watched_groups.clear()

        if not self.is_registered:
            return

        connections = self.active_connections.get(
            self.profile_id,
            set(),
        )

        connections.discard(self.channel_name)

        # Mark offline only when the last tab/connection closes.
        if not connections:

            self.active_connections.pop(
                self.profile_id,
                None,
            )

            last_seen = await update_profile_last_seen(
                self.profile_id,
                self.tenant_id,
            )

            await self.channel_layer.group_send(
                f"presence_profile_{self.profile_id}",
                {
                    "type": "presence.event",
                    "payload": {
                        "type": "presence_update",
                        "profile_id": self.profile_id,
                        "profile_name": self.profile_name,
                        "is_online": False,
                        "last_seen": last_seen,
                    },
                },
            )

        self.is_registered = False

    async def receive_json(self, content, **kwargs):

        if content.get("type") != "heartbeat":
            return

        # Recheck authorization periodically.
        # This removes access if a match is blocked or removed.
        allowed_ids = set(
            await get_allowed_presence_profile_ids(
                self.scope.get("user")
            )
        )

        added_ids = allowed_ids - self.watched_profile_ids
        removed_ids = self.watched_profile_ids - allowed_ids

        # Remove revoked subscriptions.
        for profile_id in removed_ids:

            group_name = f"presence_profile_{profile_id}"

            await self.channel_layer.group_discard(
                group_name,
                self.channel_name,
            )

            self.watched_groups.discard(group_name)

        # Add newly authorized subscriptions.
        for profile_id in added_ids:

            group_name = f"presence_profile_{profile_id}"

            await self.channel_layer.group_add(
                group_name,
                self.channel_name,
            )

            self.watched_groups.add(group_name)

        self.watched_profile_ids = allowed_ids

        if removed_ids:

            await self.send_json({
                "type": "presence_access_revoked",
                "profile_ids": list(removed_ids),
            })

        # Send initial status for newly accepted matches.
        if added_ids:

            snapshot = await get_presence_snapshot(
                list(added_ids),
                self.tenant_id,
            )

            statuses = []

            for item in snapshot:

                other_id = item["profile_id"]

                is_online = bool(
                    self.active_connections.get(other_id)
                )

                statuses.append({
                    "profile_id": other_id,
                    "is_online": is_online,
                    "last_seen": (
                        None
                        if is_online
                        else item["last_seen"]
                    ),
                })

            await self.send_json({
                "type": "presence_snapshot",
                "statuses": statuses,
            })

    async def presence_event(self, event):

        payload = event.get("payload")

        if payload:
            await self.send_json(payload)

# =========================================================
# CHAT TYPING INDICATOR WEBSOCKET
# =========================================================


def _get_chat_connection_details(user, target_profile_id):

    if not user or not user.is_authenticated:
        print("[CHAT WS] Rejected: User not authenticated")
        return None

    tenant = get_user_tenant(user)

    if tenant is None:
        print("[CHAT WS] Rejected: Tenant not found")
        return None

    current_profile = Profile.objects.filter(
        user=user,
        tenant=tenant,
    ).first()

    target_profile = (
        Profile.objects
        .select_related("user")
        .filter(
            id=target_profile_id,
            tenant=tenant,
        )
        .first()
    )

    if not current_profile or not target_profile:
        print(
            "[CHAT WS] Rejected: Profile not found",
            "Current:", bool(current_profile),
            "Target:", bool(target_profile),
        )
        return None

    if current_profile.id == target_profile.id:
        print("[CHAT WS] Rejected: Same profile")
        return None

    if not target_profile.user.is_active:
        print("[CHAT WS] Rejected: Target user inactive")
        return None

    accepted_match = Match.objects.filter(
        Q(
            sender=current_profile,
            receiver=target_profile,
        )
        | Q(
            sender=target_profile,
            receiver=current_profile,
        ),
        status="accepted",
        sender__tenant=tenant,
        receiver__tenant=tenant,
    ).exists()

    if not accepted_match:
        print("[CHAT WS] Rejected: Accepted match not found")
        return None

    is_blocked = ProfileBlock.objects.filter(
        tenant=tenant,
    ).filter(
        Q(
            blocker=current_profile,
            blocked=target_profile,
        )
        | Q(
            blocker=target_profile,
            blocked=current_profile,
        )
    ).exists()

    if is_blocked:
        print("[CHAT WS] Rejected: Profile block exists")
        return None

    is_removed = RemovedProfile.objects.filter(
        tenant=tenant,
    ).filter(
        Q(
            owner=current_profile,
            removed_profile=target_profile,
        )
        | Q(
            owner=target_profile,
            removed_profile=current_profile,
        )
    ).exists()

    if is_removed:
        print("[CHAT WS] Rejected: Removed profile exists")
        return None

    profile_ids = sorted([
        current_profile.id,
        target_profile.id,
    ])

    print("[CHAT WS] Connection authorized")

    return {
        "current_profile_id": current_profile.id,
        "target_profile_id": target_profile.id,
        "current_profile_name": current_profile.full_name,
        "group_name": f"chat_{profile_ids[0]}_{profile_ids[1]}",
    }

@database_sync_to_async
def get_chat_connection_details(user, target_profile_id):
    return _get_chat_connection_details(
        user,
        target_profile_id,
    )


class ChatConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        print("[CHAT WS] Connect method called")

        user = self.scope.get("user")

        target_profile_id = self.scope[
            "url_route"
        ]["kwargs"].get("profile_id")

        details = await get_chat_connection_details(
            user,
            target_profile_id,
        )

        if not details:
            await self.close(code=4403)
            return

        self.current_profile_id = details[
            "current_profile_id"
        ]

        self.target_profile_id = details[
            "target_profile_id"
        ]

        self.current_profile_name = details[
            "current_profile_name"
        ]

        self.group_name = details["group_name"]

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()
        print("[CHAT WS] WebSocket accepted")

    async def disconnect(self, close_code):

        if hasattr(self, "group_name"):

            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):

        if not isinstance(content, dict):
            await self.send_json({
                "type": "error",
                "message": "Invalid message format.",
            })
            return

        message_type = content.get("type")

        allowed_types = {
            "typing",
            "stop_typing",
        }

        if message_type not in allowed_types:
            await self.send_json({
                "type": "error",
                "message": "Unsupported chat event.",
            })
            return

        # Recheck authorization before every event.
        # This prevents typing events after block/remove/unmatch.
        details = await get_chat_connection_details(
            self.scope.get("user"),
            self.target_profile_id,
        )

        if not details:
            await self.send_json({
                "type": "chat_access_revoked",
                "message": "Chat access is no longer available.",
            })

            await self.close(code=4403)
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.typing_event",
                "sender_profile_id": self.current_profile_id,
                "sender_name": self.current_profile_name,
                "target_profile_id": self.target_profile_id,
                "message_type": message_type,
            },
        )

    async def chat_typing_event(self, event):

        # Do not send the event back to the sender.
        if (
            event["sender_profile_id"]
            == self.current_profile_id
        ):
            return

        # Only the intended recipient receives this event.
        if (
            event["target_profile_id"]
            != self.current_profile_id
        ):
            return

        await self.send_json({
            "type": event["message_type"],
            "from_profile_id": event["sender_profile_id"],
            "from_name": event["sender_name"],
        })