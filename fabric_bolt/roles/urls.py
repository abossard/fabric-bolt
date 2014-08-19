from django.conf.urls import patterns, url

from fabric_bolt.roles import views


urlpatterns = patterns(
    '',
    url(r'^$', views.RoleList.as_view(), name='roles_role_list'),
    url(r'^create$', views.RoleCreate.as_view(), name='roles_role_create'),
    url(r'^update/(?P<pk>[^\s]+)/', views.RoleUpdate.as_view(), name='roles_role_update'),
    url(r'^view/(?P<pk>[^\s]+)/', views.RoleDetail.as_view(), name='roles_role_detail'),
    url(r'^delete/(?P<pk>[^\s]+)/', views.RoleDelete.as_view(), name='roles_role_delete'),
)
