from django.conf.urls import patterns, url

from fabric_bolt.hosts import views


urlpatterns = patterns('',
    url(r'^$', views.HostList.as_view(), name='fabfiles_list'),
    url(r'^add$', views.HostCreate.as_view(), name='fabfiles_add'),
    url(r'^update/(?P<pk>\d+)/', views.HostUpdate.as_view(), name='fabfiles_update'),
    url(r'^view/(?P<pk>\d+)/', views.HostDetail.as_view(), name='fabfiles_view'),
    url(r'^delete/(?P<pk>\d+)/', views.HostDelete.as_view(), name='fabfiles_delete'),
)