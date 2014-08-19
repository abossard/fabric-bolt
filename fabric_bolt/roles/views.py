from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.detail import DetailView
from django.core.urlresolvers import reverse_lazy, reverse
from django.contrib import messages
from django_tables2.views import SingleTableView

from fabric_bolt.core.mixins.views import MultipleGroupRequiredMixin, GroupRequiredMixin
from fabric_bolt.roles import models, tables, forms


class RoleList(SingleTableView):
    group_required = ['Admin', 'Deployer', ]
    table_class = tables.RoleTable
    model = models.Role


class RoleDetail(DetailView):
    group_required = ['Admin', 'Deployer', ]
    model = models.Role


class RoleCreate(CreateView):
    """View for creating a role. Roles let us know where we can shovel code to."""
    group_required = ['Admin', 'Deployer', ]
    model = models.Role
    form_class = forms.RoleCreateForm
    template_name_suffix = '_create'

    def form_valid(self, form):
        """First call the parent's form valid then let the user know it worked."""

        form_valid_from_parent = super(RoleCreate, self).form_valid(form)
        messages.success(self.request, 'Role {} Successfully Created'.format(self.object))

        return form_valid_from_parent

    def get_success_url(self):
        """Send them back to the detail view for that role"""

        return reverse('roles_role_detail', kwargs={'pk': self.object.pk})


class RoleUpdate(GroupRequiredMixin, UpdateView):
    role_required = 'Admin'
    model = models.Role
    form_class = forms.RoleUpdateForm
    template_name_suffix = '_update'

    def form_valid(self, form):
        """First call the parent's form valid then let the user know it worked."""

        form_valid_from_parent = super(RoleUpdate, self).form_valid(form)
        messages.success(self.request, 'Role {} Successfully Updated'.format(self.object))

        return form_valid_from_parent

    def get_success_url(self):
        """"""
        return reverse('roles_role_detail', kwargs={'pk': self.object.pk})


class RoleDelete(GroupRequiredMixin, DeleteView):
    group_required = 'Admin'
    model = models.Role
    success_url = reverse_lazy('roles_role_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Role {} Successfully Deleted'.format(self.get_object()))
        return super(RoleDelete, self).delete(self, request, *args, **kwargs)
