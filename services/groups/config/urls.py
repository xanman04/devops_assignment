from django.urls import path
from . import api

urlpatterns = [
    path("health", api.health),
    path("api/events/<int:event_id>/groups/", api.public_groups),
    path("api/groups/", api.create),
    path("api/groups/mine/", api.mine),
    path("api/groups/<int:group_id>/", api.detail),
    path("api/groups/<int:group_id>/edit/", api.edit),
    path("api/groups/<int:group_id>/delete/", api.delete_group),
    path("api/groups/<int:group_id>/requests/", api.requests),
    path("api/groups/<int:group_id>/members/<int:user_id>/remove/", api.remove),
    path("api/groups/<int:group_id>/chat/", api.chat),
    path("api/groups/<int:group_id>/messages/", api.post_message),
    path("api/groups/<int:group_id>/photo/", api.photo),
    path("api/bans/<int:ban_id>/lift/", api.lift_ban),
    path("api/messages/<int:message_id>/", api.message),
    path("api/notifications/", api.inbox),
    path("api/notifications/<int:notice_id>/read/", api.read_notice),
]
for action in ("join", "request", "leave"):
    urlpatterns.append(path("api/groups/<int:group_id>/"+action+"/", api.group_action, {"action": action}))
for action in ("review", "accept", "cancel"):
    urlpatterns.append(path("api/requests/<int:request_id>/"+action+"/", api.request_action, {"action": action}))
