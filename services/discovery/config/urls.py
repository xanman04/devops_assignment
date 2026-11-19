from django.urls import path
from discovery.views import event_details, map_events
from . import api, content_api

urlpatterns = [
    path("api/browse/", content_api.browse),
    path("api/artists/", content_api.artists),
    path("api/artists/<int:artist_id>/", content_api.artist),
    path("api/genres/<int:genre_id>/", content_api.genre),
    path("api/events/<int:event_id>/content/", content_api.detail),
    path("api/events/<int:event_id>/poster/", content_api.poster),
    path("health", api.health),
    path("api/auth/token/", api.token),
    path("api/auth/identity/", api.whoami),
    path("api/auth/logout/", api.logout),
    path("api/genres/", api.categories),
    path("api/venues/", api.venues),
    path("api/events/", api.events),
    path("api/events/<int:event_id>/", event_details, name="api-event-details"),
    path("api/events/<int:event_id>/edit/", api.edit_event),
    path("api/events/<int:event_id>/follow/", api.follow),
    path("api/events/<int:event_id>/unfollow/", api.unfollow),
    path("api/map/events/", map_events),
    path("api/notifications/", api.inbox),
]
